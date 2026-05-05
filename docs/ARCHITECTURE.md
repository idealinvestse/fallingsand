# Architecture

Falling Sand is organized around a Python runtime shell and a GPU-resident simulation core.

## Runtime Layers

1. **Application shell**
   - `main.py` parses CLI flags, creates the window/context, manages UI state, handles input, steps the simulation, renders overlays, and presents frames.
   - `launcher.py` provides a Tk-based launcher for play/settings/about workflows.

2. **Simulation API**
   - `simulation/engine.py` exposes actions such as `step`, `render`, `apply_brush`, `trigger_explosion`, `save_state`, `load_state`, `undo`, `probe_cell`, `cycle_debug_view`, and `toggle_pressure_overlay`.
   - UI code should prefer this API instead of directly mutating GPU buffers.

3. **GPU infrastructure**
   - `gpu/context.py` creates the Pygame OpenGL context.
   - `gpu/buffers.py` owns SSBOs and textures (cells, velocity, pressure, temperature, charge, nutrient, moisture, humidity, mass, wind, vorticity, divergence, display).
   - `gpu/resources.py` defines the centralized resource binding registry (SSBO, image, UBO bindings with names, types, and purposes).
   - `gpu/pass_graph.py` declares compute passes with their reads, writes, swaps, and optional/iterative flags.
   - `gpu/uniforms.py` packs UBO data for SimConfig, ExplosionConfig, ExplosionVfxConfig, and WindConfig.
   - `gpu/shader_registry.py` loads every compute shader with `shaders/common.glsl` prepended via a manifest.
   - `gpu/pipeline.py` binds resources and dispatches compute passes in order defined by pass_graph.
   - `gpu/profiler.py` instruments per-pass GPU timing via `_timed_run`.

4. **Domain data**
   - `simulation/materials.yaml` is the material source of truth.
   - `simulation/materials.py` validates the registry and creates the GPU rule buffer.
   - `simulation/state.py` owns runtime explosion, VFX, and wind state.
   - `simulation/persistence.py` owns save/load/undo behavior.

   - `simulation/brush.py` provides GPU brush painting with modes for material, heat, cool, spark, and charge injection.

5. **Presentation**
   - `hud.py` renders material/brush HUD.
   - `ui/` renders pause menu, inspector (with ecology fields), overlays, theme helpers, and sound placeholders.
   - `ui/performance_overlay.py` provides real-time FPS monitoring and per-pass timing visualization.
   - `ui/system_controls.py` provides real-time parameter tuning for electricity, biology, weather, and bloom settings.
   - `levels/` provides built-in and persisted custom levels.

## Performance Monitoring (v7 Foundation)

### Performance Overlay

The performance overlay (Ctrl+P) displays:
- Real-time FPS with color coding (green ≥55, yellow 30-55, red <30)
- FPS history graph (60-frame sliding window)
- Per-pass timing bars with budget-exceeded highlighting
- Memory usage estimate
- Quality tier indicator when adaptive mode enabled

### Adaptive Quality

When `--adaptive-quality` is enabled, the pipeline automatically adjusts quality tiers based on sustained FPS:
- Downgrade: FPS < min_fps_target * 0.9 for 30+ frames
- Upgrade: FPS > min_fps_target * 1.2 for 30+ frames
- Quality tiers affect pressure iterations, acoustic substeps, and bloom enabled state

## Key Data Flow

1. `main.py` builds `SimulationConfig`.
2. `SimulationEngine` allocates buffers, UBOs, shaders, brush painter, and persistence manager.
3. User input calls engine methods.
4. `Pipeline.step()` updates UBOs and dispatches compute passes (state → liquid → heat → vorticity → vel_advect → force → divergence → pressure → project → electricity → electricity_arc → biology → weather → acoustic_pressure → acoustic_velocity → advect).
5. `Pipeline.render()` writes `display_texture` with AO, emissive glow, water depth, and optional debug overlay, then blits to the default framebuffer.
6. UI overlays render after the simulation frame.

## GPU Resource Fields

| Field | Format | Binding | Buffers |
|-------|--------|---------|---------|
| Cells | uint32 SSBO | 0/1 | read_buf / write_buf |
| Rules | float32 SSBO | 2 | rule_ssbo |
| Velocity | rg32f | 3/4 | vel_a / vel_b |
| Divergence | r32f | 4 | div_tex |
| Pressure | r32f | 5/6 | pres_a / pres_b |
| Display | rgba8 | 7 | display_texture |
| Vorticity | r32f | 8 | vorticity_tex |
| Charge | r32f | 9/10 | charge_a / charge_b |
| Temperature | r32f | 11/12 | temp_a / temp_b |
| Nutrient | r32f | 13/14 | nutrient_a / nutrient_b |
| Moisture | r32f | 15/16 | moisture_a / moisture_b |
| Humidity | r32f | 17/18 | humidity_a / humidity_b |
| Bloom A | rgba8 | 19 | bloom_a (half-res) |
| Bloom B | rgba8 | 20 | bloom_b (half-res) |
| Mass | r16f | — | mass_a / mass_b |
| Wind | rg16f | — | wind_tex |

## Performance Monitoring

- **PassProfiler**: Per-pass timing in `gpu/profiler.py`
- **Adaptive substeps**: CFL-based in `gpu/pipeline.py`
- **Quality tiers**: Dynamic adjustment based on fps (planned)
- **Benchmark suite**: `tests/benchmark_performance.py` (planned)
- **Performance overlay**: UI overlay for real-time metrics (planned)

See `docs/PERFORMANCE.md` for complete performance guide.

## High-Risk Couplings

- Shader bindings must match `gpu/pipeline.py`, `gpu/buffers.py`, `gpu/resources.py`, and `shaders/BUFFER_BINDINGS.md`.
- Cell packing must match `core/types.py`, `simulation/materials.py`, `shaders/common.glsl`, and `simulation/persistence.py`.
- Material rule stride must match `core/constants.py`, `simulation/materials.py`, and `shaders/common.glsl`.
- Pass order must match `gpu/pass_graph.py`, `gpu/pipeline.py`, and `tests/test_pass_graph_contracts.py`.
- Save format migration must remain compatible with older saves.
- Main-loop refactors require tests for input, pause, save/load, brush, debug view, and overlay behavior.
