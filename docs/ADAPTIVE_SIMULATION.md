# Adaptive Simulation

## Overview

Adaptive simulation is a v7 foundation feature that dynamically adjusts simulation quality based on real-time performance metrics. The system monitors frame timing and automatically scales quality tiers to maintain target FPS.

## Quality Tier System

The simulation supports three quality tiers:

### High Quality (Tier 0)
- Pressure iterations: 20
- Acoustic substeps: 6
- Bloom enabled: True
- Target: 60+ FPS

### Medium Quality (Tier 1)
- Pressure iterations: 12
- Acoustic substeps: 4
- Bloom enabled: True
- Target: 45+ FPS

### Low Quality (Tier 2)
- Pressure iterations: 8
- Acoustic substeps: 2
- Bloom enabled: False
- Target: 30+ FPS

## Auto-Adjustment Logic

The system monitors FPS over a sliding window of 60 frames. Quality tier adjustments are made based on sustained performance:

- **Downgrade**: If average FPS < min_fps_target * 0.9 for 30+ frames
- **Upgrade**: If average FPS > min_fps_target * 1.2 for 30+ frames

After each adjustment, the FPS history is cleared to allow the new tier to stabilize.

## Configuration

Enable adaptive quality via CLI flag:

```bash
python main.py --adaptive-quality --min-fps-target 30.0
```

Or via `SimulationConfig`:

```python
config.adaptive_quality = True
config.min_fps_target = 30.0
```

## Sparse Region Optimization

Sparse region optimization tracks active (non-air) cells and limits GPU dispatch to bounding boxes around these regions. This reduces compute when the simulation is mostly empty.

Enable sparse mode via System Controls Panel (Ctrl+E) or programmatically:

```python
engine.pipeline.enable_sparse_mode(True)
```

## Adaptive Pass Skipping

When adaptive quality is enabled, optional passes are skipped based on pass priority and frame budget:

- **Priority 0**: Lowest (skip at 80% budget)
- **Priority 1**: Biology, Weather (skip at 90% budget)
- **Priority 2**: Electricity, Arc (skip at 95% budget)
- **Priority 3**: Acoustic (rarely skipped)
- **Priority 4**: Vorticity, Heat (rarely skipped)

## Performance Monitoring

The performance overlay (Ctrl+P) displays:
- Real-time FPS with color coding
- FPS history graph
- Per-pass timing bars
- Budget-exceeded pass highlighting
- Current quality tier indicator

## Integration with Pipeline

Quality tier adjustments are applied via `Pipeline._apply_quality_tier()`:

```python
def _apply_quality_tier(self) -> None:
    tier = self.config.quality_tiers[self.quality_tier_index]
    self.config.pressure_iterations = tier["pressure_iterations"]
    self.config.acoustic_substeps = tier["acoustic_substeps"]
    self.config.bloom_enabled = tier["bloom_enabled"]
```

## Limitations

- Adaptive quality requires the `--adaptive-quality` flag
- Sparse region optimization is experimental and may not benefit all scenarios
- Quality tier changes reset FPS history, which can cause oscillation in edge cases
