# Performance Guide

## Overview

This document covers performance profiling, target metrics, adaptive techniques, memory bandwidth analysis, and optimization strategies for the Falling Sand simulation.

## Adaptive Simulation (v7 Foundation)

### Quality Tier System

The simulation supports three quality tiers that automatically adjust based on FPS:

- **High**: 20 pressure iterations, 6 acoustic substeps, bloom enabled (60+ FPS target)
- **Medium**: 12 pressure iterations, 4 acoustic substeps, bloom enabled (45+ FPS target)
- **Low**: 8 pressure iterations, 2 acoustic substeps, bloom disabled (30+ FPS target)

Enable via `--adaptive-quality` flag or `SimulationConfig.adaptive_quality = True`.

### Sparse Region Optimization

Tracks active (non-air) cells and limits GPU dispatch to bounding boxes around these regions. Enable via System Controls Panel or `engine.pipeline.enable_sparse_mode(True)`.

### Adaptive Pass Skipping

Optional passes are skipped based on pass priority and frame budget when adaptive quality is enabled:
- Priority 0: Lowest (skip at 80% budget)
- Priority 1: Biology, Weather (skip at 90% budget)
- Priority 2: Electricity, Arc (skip at 95% budget)
- Priority 3+: Acoustic, Vorticity, Heat (rarely skipped)

## Profiler Architecture

### PassProfiler Class (gpu/profiler.py)

The PassProfiler tracks per-pass GPU dispatch timings:

```python
@dataclass(slots=True)
class PassTiming:
    """Timing data for a single pass."""
    elapsed_ms: float
    call_count: int

class PassProfiler:
    """Tracks per-pass GPU dispatch timings."""
    
    def __init__(self) -> None:
        self._timings: dict[str, list[float]] = {}
    
    def record(self, pass_name: str, elapsed_ms: float) -> None:
        """Record a pass timing."""
        if pass_name not in self._timings:
            self._timings[pass_name] = []
        self._timings[pass_name].append(elapsed_ms)
    
    def get_all(self) -> dict[str, PassTiming]:
        """Get aggregated timing data."""
        result = {}
        for name, times in self._timings.items():
            result[name] = PassTiming(
                elapsed_ms=sum(times) / len(times),
                call_count=len(times)
            )
        return result
    
    def total_step_ms(self) -> float:
        """Get total frame time."""
        return sum(ts.elapsed_ms for ts in self.get_all().values())
```

### Usage in Pipeline

Pipeline.dispatch() wraps each pass with _timed_run():

```python
def _timed_run(self, pass_name: str, shader, **kwargs) -> None:
    """Run a shader pass with timing."""
    start = time.perf_counter()
    shader(**kwargs)
    elapsed = (time.perf_counter() - start) * 1000.0
    self.profiler.record(pass_name, elapsed)
```

## Target Metrics

### Resolution-Specific Targets

| Resolution | Systems Enabled | Target FPS | Frame Budget |
|------------|----------------|------------|--------------|
| 1024×1024  | Fluid only     | ≥60        | 16.67ms      |
| 1024×1024  | All systems    | ≥50        | 20.00ms      |
| 2048×2048  | Fluid only     | ≥40        | 25.00ms      |
| 2048×2048  | All systems    | ≥30        | 33.33ms      |

### Per-Pass Budget Allocation (1024×1024, All Systems)

```
state:           2.0ms  (10%)   - Cell state update
liquid_step:     1.5ms  (7.5%)  - Liquid physics
heat:            1.0ms  (5%)    - Thermal diffusion
vorticity:       0.5ms  (2.5%)  - Vorticity confinement
velocity_advect: 2.0ms  (10%)   - Velocity advection
force:           1.5ms  (7.5%)  - External forces
divergence:      0.5ms  (2.5%)  - Divergence calculation
pressure:        4.0ms  (20%)   - Jacobi pressure (12 iterations)
project:         1.0ms  (5%)    - Velocity projection
electricity:     1.0ms  (5%)    - Charge propagation
electricity_arc: 0.5ms  (2.5%)  - Arc breakdown
biology:         1.0ms  (5%)    - Nutrient/moisture
weather:         1.0ms  (5%)    - Humidity/atmosphere
acoustic:        2.0ms  (10%)   - Acoustic waves (6 substeps)
advect:          1.5ms  (7.5%)  - Final advection
render:          1.0ms  (5%)    - Render pass
bloom:           1.0ms  (5%)    - Bloom post-FX
Total:           20.0ms (50fps target)
```

## Adaptive Substeps

### CFL-Based Adaptive Substepping

Config: `adaptive_substeps: bool = True`

Formula in gpu/pipeline.py:

```python
# Calculate adaptive substeps based on frame time
if self.config.adaptive_substeps:
    dt_frame = 1.0 / current_fps
    adaptive_substeps = int(np.ceil(dt_frame / (1.0 / 60.0)))
    adaptive_substeps = min(adaptive_substeps, MAX_SUBSTEPS)
else:
    adaptive_substeps = self.config.sim_substeps
```

### Configuration

```python
# core/config.py
adaptive_substeps: bool = True

# core/constants.py
MAX_SUBSTEPS = 8
MIN_SUBSTEPS = 1
```

### Impact

- At 60 fps: 1 substep
- At 30 fps: 2 substeps
- At 15 fps: 4 substeps
- Ensures stability when framerate drops

## Memory Bandwidth Analysis

### GPU Memory Layout

| Field | Format | Size @ 1024×1024 | Double-Buffered |
|-------|--------|------------------|-----------------|
| Cells | uint32 SSBO | 4MB | No |
| Rules | float32 SSBO | 0.2MB | No |
| Velocity | rg32f | 8MB | Yes |
| Pressure | r32f | 4MB | Yes |
| Temperature | r32f | 4MB | Yes |
| Charge | r32f | 4MB | Yes |
| Nutrient | r32f | 4MB | Yes |
| Moisture | r32f | 4MB | Yes |
| Humidity | r32f | 4MB | Yes |
| Display | rgba8 | 4MB | No |
| Bloom A | rgba8 | 1MB | No |
| Bloom B | rgba8 | 1MB | No |
| Mass | r16f | 2MB | Yes |
| Wind | rg16f | 2MB | No |
| **Total** | | **42.2MB** | |

### Memory Bandwidth Estimates

Assuming 1024×1024 grid, 50fps:

- **Read**: ~42MB/frame × 50fps = 2.1GB/s
- **Write**: ~20MB/frame × 50fps = 1.0GB/s
- **Total**: ~3.1GB/s

This is well within typical GPU memory bandwidth (e.g., RTX 3060: 360GB/s).

## GPU Occupancy

### Workgroup Configuration

All compute shaders use 16×16 workgroup size:

```glsl
layout(local_size_x = 16, local_size_y = 16) in;
```

### Dispatch Calculation

```python
workgroups_x = ceil(width / 16)
workgroups_y = ceil(height / 16)
total_workgroups = workgroups_x * workgroups_y
```

For 1024×1024:
- workgroups_x = 64
- workgroups_y = 64
- total_workgroups = 4096

For 2048×2048:
- workgroups_x = 128
- workgroups_y = 128
- total_workgroups = 16384

### Occupancy Analysis

- 4096 workgroups @ 1024×1024
- Typical GPU has ~80-120 streaming multiprocessors (SMs)
- Each SM can execute multiple workgroups
- High occupancy achieved with current configuration

## Optimization Strategies

### 1. Skip Optional Passes

If frame budget exceeded, skip non-critical optional passes:

```python
def _should_skip_pass(self, pass_name: str, dt: float) -> bool:
    budget_ms = 1000.0 / 60.0  # 16.67ms for 60fps
    elapsed = self.profiler.total_step_ms()
    
    if elapsed > budget_ms * 0.9:
        if pass_name in ("biology", "weather"):
            return True
    return False
```

Priority order for skipping:
1. biology (lowest priority)
2. weather (low priority)
3. electricity (medium priority)
4. bloom (medium priority)
5. acoustic (high priority)

### 2. Reduce Pressure Iterations

Dynamic pressure iteration adjustment:

```python
if elapsed_ms > budget_ms:
    pressure_iterations = max(8, pressure_iterations - 2)
```

### 3. Disable Bloom for Performance

```python
if elapsed_ms > budget_ms * 1.2:
    bloom_enabled = False
```

### 4. Use Lower Quality Acoustic Substeps

```python
if elapsed_ms > budget_ms:
    acoustic_substeps = max(2, acoustic_substeps - 2)
```

### 5. Sparse Region Dispatch (v7)

Only dispatch compute for active regions:

```python
class SparseMask:
    def update_mask(self, cells: np.ndarray) -> None:
        """Track active regions."""
        # Compute bounding boxes of non-air cells
        # Generate dispatch ranges for each region
    
    def get_dispatch_ranges(self) -> list[tuple[int, int, int, int]]:
        """Return (x, y, w, h) for each active region."""
```

Expected savings: 30-50% on sparse scenes.

### 6. Quality Tier System

Dynamic quality adjustment based on sustained fps:

```python
QUALITY_TIERS = {
    "high": {
        "pressure_iterations": 20,
        "acoustic_substeps": 6,
        "bloom_enabled": True,
        "bloom_quality": "high",
    },
    "medium": {
        "pressure_iterations": 12,
        "acoustic_substeps": 4,
        "bloom_enabled": True,
        "bloom_quality": "medium",
    },
    "low": {
        "pressure_iterations": 8,
        "acoustic_substeps": 2,
        "bloom_enabled": False,
        "bloom_quality": "low",
    },
}

def adjust_quality_tier(self, sustained_fps: float) -> None:
    if sustained_fps < 30.0:
        self.current_tier = "low"
    elif sustained_fps < 45.0:
        self.current_tier = "medium"
    else:
        self.current_tier = "high"
```

## Benchmark Methodology

### Benchmark Configuration

Run benchmarks for 60 seconds per configuration:

```python
class PerformanceBenchmark:
    def benchmark_1024_all_systems(self) -> BenchmarkResult:
        """Benchmark 1024×1024 with all systems enabled."""
        engine = SimulationEngine(config)
        engine.enable_all_systems()
        
        fps_history = []
        for _ in range(60 * 60):  # 60 seconds @ 60fps
            engine.step()
            fps_history.append(engine.current_fps)
        
        return BenchmarkResult(
            min_fps=min(fps_history),
            avg_fps=sum(fps_history) / len(fps_history),
            max_fps=max(fps_history),
            pass_timings=engine.profiler.get_all(),
        )
```

### Test Scenarios

1. **Empty Grid**: Baseline with no cells
2. **Static Grid**: 50% fill with static materials
3. **Dynamic Grid**: 50% fill with moving materials
4. **Worst Case**: 100% fill with active physics
5. **All Systems**: Electricity + Biology + Weather enabled

### Reporting

Report:
- Min/Avg/Max fps
- Per-pass timing breakdown
- Memory usage
- GPU utilization (if available)
- Frame time distribution (percentiles)

## Performance Profiling Tools

### Built-in Profiler

Enable via CLI:

```bash
python main.py --perf
```

Output per-pass timings every 60 frames.

### Performance Overlay (v7)

UI overlay showing real-time performance:

```python
class PerformanceOverlay(OverlayRenderer):
    def render(self, profiler: PassProfiler) -> None:
        # Render per-pass timing bars
        # Show fps history graph
        # Display memory usage
        # Highlight budget-exceeded passes
```

### GPU Profiling

For deep profiling, use GPU vendor tools:
- NVIDIA Nsight Systems
- AMD Radeon GPU Profiler
- Intel Graphics Performance Analyzers

## Common Performance Issues

### Issue: Low FPS on High Resolution

**Symptoms**: <30 fps @ 2048×2048

**Causes**:
- Too many active cells
- High pressure iterations
- Acoustic substeps too high

**Solutions**:
- Reduce grid resolution
- Lower pressure_iterations
- Lower acoustic_substeps
- Disable optional systems

### Issue: Stuttering

**Symptoms**: Irregular frame times, occasional drops

**Causes**:
- Garbage collection
- Large memory allocations
- Shader compilation on first use

**Solutions**:
- Pre-compile all shaders
- Use object pooling
- Disable Python GC for critical loops

### Issue: Memory Leaks

**Symptoms**: Memory usage increases over time

**Causes**:
- Unreleased GPU resources
- Growing Python lists
- Circular references

**Solutions**:
- Use context managers for GPU resources
- Clear profiler timing history periodically
- Profile with memory_profiler

## Performance Monitoring Integration

### CLI Integration

```python
# main.py
if args.perf:
    engine.enable_profiling()
    engine.set_perf_callback(print_perf_report)
```

### Config Integration

```python
# core/config.py
perf_overlay: bool = False
perf_interval: int = 60  # Report every 60 frames
```

### Engine Integration

```python
# simulation/engine.py
def step(self) -> None:
    self._frame_count += 1
    if self._frame_count % self.config.perf_interval == 0:
        self._report_performance()
```

## Future Work (v7)

1. Implement sparse region dispatch
2. Add quality tier auto-adjustment
3. Implement performance overlay UI
4. Add GPU occupancy metrics
5. Implement adaptive pass skipping
6. Add memory bandwidth monitoring
7. Implement shader hot-reloading for tuning
8. Add multi-threaded CPU preprocessing
9. Implement GPU-driven dispatch (indirect)
10. Add async compute for post-FX
