"""Performance benchmarking suite for the simulation."""

import time
from dataclasses import dataclass
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass(slots=True)
class BenchmarkResult:
    """Result of a performance benchmark."""
    name: str
    width: int
    height: int
    duration_sec: float
    frames: int
    fps_min: float
    fps_avg: float
    fps_max: float
    pass_timings: dict[str, float]


class PerformanceBenchmark:
    """Performance benchmarking for the simulation."""

    def __init__(self, ctx_manager, config):
        """Initialize benchmark with GPU context and config."""
        self.ctx_manager = ctx_manager
        self.config = config

    def benchmark_1024_all_systems(self) -> BenchmarkResult:
        """Benchmark 1024×1024 with all systems enabled."""
        from simulation.engine import SimulationEngine

        # Enable all new systems
        self.config.enable_electricity = True
        self.config.enable_biology = True
        self.config.enable_weather = True
        self.config.width = 1024
        self.config.height = 1024

        engine = SimulationEngine(self.config, self.ctx_manager)
        
        return self._run_benchmark("1024_all_systems", engine, duration_sec=60)

    def benchmark_2048_all_systems(self) -> BenchmarkResult:
        """Benchmark 2048×2048 with all systems enabled."""
        from simulation.engine import SimulationEngine

        # Enable all new systems
        self.config.enable_electricity = True
        self.config.enable_biology = True
        self.config.enable_weather = True
        self.config.width = 2048
        self.config.height = 2048

        engine = SimulationEngine(self.config, self.ctx_manager)
        
        return self._run_benchmark("2048_all_systems", engine, duration_sec=60)

    def benchmark_512_low_res(self) -> BenchmarkResult:
        """Benchmark 512×512 low-resolution grid."""
        from simulation.engine import SimulationEngine

        self.config.width = 512
        self.config.height = 512

        engine = SimulationEngine(self.config, self.ctx_manager)
        
        return self._run_benchmark("512_low_res", engine, duration_sec=30)

    def benchmark_adaptive_mode(self) -> BenchmarkResult:
        """Benchmark adaptive quality mode."""
        from simulation.engine import SimulationEngine

        self.config.adaptive_quality = True
        self.config.min_fps_target = 30.0
        self.config.width = 1024
        self.config.height = 1024

        engine = SimulationEngine(self.config, self.ctx_manager)
        engine.pipeline.adaptive_quality = True
        
        return self._run_benchmark("adaptive_mode", engine, duration_sec=60)

    def benchmark_sparse_region(self) -> BenchmarkResult:
        """Benchmark sparse region optimization."""
        from simulation.engine import SimulationEngine

        self.config.width = 1024
        self.config.height = 1024

        engine = SimulationEngine(self.config, self.ctx_manager)
        engine.pipeline.enable_sparse_mode(True)
        
        return self._run_benchmark("sparse_region", engine, duration_sec=30)

    def benchmark_pass_cost(self, pass_name: str) -> float:
        """Measure single pass cost in isolation."""
        from simulation.engine import SimulationEngine

        engine = SimulationEngine(self.config, self.ctx_manager)
        
        # Clear profiler
        engine.pipeline.profiler._timings.clear()
        
        # Run single frame
        dt = 1.0 / 60.0
        engine.step(dt)
        
        # Get pass timing
        timings = engine.pipeline.profiler.get_all()
        if pass_name in timings:
            return timings[pass_name].elapsed_ms
        
        return 0.0

    def _run_benchmark(self, name: str, engine, duration_sec: float) -> BenchmarkResult:
        """Run benchmark and collect timing data."""
        frames = 0
        fps_samples = []
        start_time = time.time()
        
        while time.time() - start_time < duration_sec:
            frame_start = time.time()
            
            dt = 1.0 / 60.0
            engine.step(dt)
            engine.render()
            
            frame_end = time.time()
            frame_ms = (frame_end - frame_start) * 1000.0
            fps = 1000.0 / frame_ms if frame_ms > 0 else 0.0
            fps_samples.append(fps)
            frames += 1
            
            # Present
            self.ctx_manager.swap_buffers()
        
        # Collect pass timings
        pass_timings = {}
        for pass_name, timing in engine.pipeline.profiler.get_all().items():
            pass_timings[pass_name] = timing.elapsed_ms
        
        return BenchmarkResult(
            name=name,
            width=self.config.width,
            height=self.config.height,
            duration_sec=duration_sec,
            frames=frames,
            fps_min=min(fps_samples) if fps_samples else 0.0,
            fps_avg=sum(fps_samples) / len(fps_samples) if fps_samples else 0.0,
            fps_max=max(fps_samples) if fps_samples else 0.0,
            pass_timings=pass_timings,
        )

    def print_result(self, result: BenchmarkResult) -> None:
        """Print benchmark results."""
        print(f"\n=== {result.name} ===")
        print(f"Grid: {result.width}x{result.height}")
        print(f"Duration: {result.duration_sec:.1f}s")
        print(f"Frames: {result.frames}")
        print(f"FPS: min={result.fps_min:.1f}, avg={result.fps_avg:.1f}, max={result.fps_max:.1f}")
        print("\nPass timings (ms):")
        for pass_name, timing in sorted(result.pass_timings.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pass_name}: {timing:.2f}")

    def validate_targets(self, result: BenchmarkResult) -> bool:
        """Validate benchmark against performance targets."""
        if result.width == 1024:
            target = 50.0
        elif result.width == 2048:
            target = 30.0
        else:
            target = 30.0
        
        passed = result.fps_avg >= target
        print(f"\nTarget: {target} FPS, Achieved: {result.fps_avg:.1f} FPS - {'PASS' if passed else 'FAIL'}")
        return passed


def main():
    """Run performance benchmarks."""
    import argparse
    from gpu.context import ContextManager
    from core.config import SimulationConfig

    parser = argparse.ArgumentParser(description="Performance benchmarking")
    parser.add_argument("--benchmark", choices=("1024", "2048", "512", "adaptive", "sparse", "pass"), default="1024", help="Benchmark to run")
    parser.add_argument("--pass-name", type=str, help="Pass name for single-pass benchmark")
    args = parser.parse_args()

    # Create config
    config = SimulationConfig()
    config.width = 1024
    config.height = 1024
    config.window_width = 900
    config.window_height = 900

    # Create GPU context
    ctx_manager = ContextManager((config.window_width, config.window_height))

    # Run benchmark
    benchmark = PerformanceBenchmark(ctx_manager, config)

    if args.benchmark == "1024":
        result = benchmark.benchmark_1024_all_systems()
        benchmark.print_result(result)
        benchmark.validate_targets(result)
    elif args.benchmark == "2048":
        result = benchmark.benchmark_2048_all_systems()
        benchmark.print_result(result)
        benchmark.validate_targets(result)
    elif args.benchmark == "512":
        result = benchmark.benchmark_512_low_res()
        benchmark.print_result(result)
        benchmark.validate_targets(result)
    elif args.benchmark == "adaptive":
        result = benchmark.benchmark_adaptive_mode()
        benchmark.print_result(result)
        benchmark.validate_targets(result)
    elif args.benchmark == "sparse":
        result = benchmark.benchmark_sparse_region()
        benchmark.print_result(result)
        benchmark.validate_targets(result)
    elif args.benchmark == "pass":
        if not args.pass_name:
            print("Error: --pass-name required for pass benchmark")
            return
        cost = benchmark.benchmark_pass_cost(args.pass_name)
        print(f"Pass '{args.pass_name}' cost: {cost:.2f}ms")

    # Cleanup
    ctx_manager.quit()


if __name__ == "__main__":
    main()
