# Falling Sand

GPU-accelerated falling-sand simulation built with Python, Pygame, ModernGL, and GLSL 4.30 compute shaders.

Multi-pass GPU pipeline: materials, thermal state, liquid behavior, pressure/velocity fields, acoustic pressure waves, electricity propagation, biology/ecology, weather, explosions, and final rendering with ambient occlusion and emissive glow.

## Current Version

**v7.1 Combustion Overhaul** — Realistic staged burning, weather suppression, and stable fuel propagation.

### Combustion Overhaul Highlights

- **Atmosphere ignition prevention**: gas and oil ignition thresholds retuned; air is now a weak oxidizer instead of unlimited combustion support
- **Staged burning**: organic fuels progress through char/smolder/ember/ash behavior instead of jumping straight to fire
- **Richer byproducts**: added `char` and `soot`, with dirty-fuel soot production tied to local oxygen availability
- **Weather integration**: moisture and humidity suppress heat gain, ignition, and fire/ember lifetime
- **Wind integration**: fire, embers, char, and soot respond to wind with material-specific coupling
- **Regression coverage**: dedicated combustion stability tests lock in anti-runaway and byproduct behavior

See `docs/CHANGELOG.md` for complete implementation history.

## Version Model

The project separates user-facing version labels from internal compatibility versions:

- **Application line**: v7.0 Evolution — final polish and release preparation.
- **Save format**: `FSND` v7 (legacy) and `FSND` v8 (chunked binary with CRC32).
- **Cell layout**: `type[0..7] | life[8..15] | flags[16..23] | unused[24..31]`.
- **Temperature storage**: `r32f` float textures are the authoritative temperature store.
- **Material rule stride**: `RULE_STRIDE = 49`.

See `docs/SAVE_FORMAT.md`, `docs/MATERIALS.md`, and `docs/GPU_PIPELINE.md` for implementation details.

## Requirements

- Python 3.11+
- OpenGL 4.3+ with compute shader support
- `pygame`
- `moderngl`
- `numpy`
- `pyyaml`

Development/test dependencies are listed in `requirements-dev.txt`.

## Install and Run

```bash
pip install pygame moderngl numpy pyyaml
python main.py
```

Optional launcher:

```bash
python launcher.py
```

## Controls

| Input | Action |
| --- | --- |
| Left click | Paint / use active brush mode |
| Right click | Erase to air in material mode |
| Mouse wheel | Change material |
| `1` | Material brush |
| `2` | Heat brush |
| `3` | Cool brush |
| `4` | Spark brush |
| `[` / `]` | Change brush size |
| `S` | Save `save_grid.npy` using current save format |
| `L` | Load `save_grid.npy` |
| `C` | Clear grid |
| `X` | Explosion at cursor; Shift+`X` for larger explosion |
| Arrow keys | Adjust wind vector |
| `W` | Toggle wind |
| `Tab` | Cycle debug overlay: pressure → charge → nutrient → moisture → humidity → off |
| `V` | Toggle pressure overlay |
| `I` | Toggle inspector (cell, thermal, motion, fluids, material, ecology) |
| `ESC` / `P` | Pause menu |
| `Ctrl+Z` | Undo |
| `F12` | Screenshot |
| `H` | Keybind overlay |

## Common CLI Flags

```text
--width / --height               Simulation grid size
--window-width / --window-height Window size
--sim-substeps N                 Base simulation substeps per frame
--pressure-iterations N          Pressure solver iterations
--no-turbulence                  Disable turbulence/vorticity effects
--no-wet-dry                     Disable wet/dry behavior
--no-thermal                     Disable thermal diffusion/effects
--no-acoustics                   Disable acoustic pressure solver
--no-bloom                       Disable bloom post-processing
--bloom-threshold N              Bloom luminance threshold (default 0.6)
--level ID                       Start with a built-in or custom level
--preset {low,med,high}          Apply a quick performance/quality preset
--paused                         Start paused
--perf                           Print periodic timing data
```

## Features

### Core Physics
- **State machine**: material phase transitions, burning, melting, freezing
- **Liquid dynamics**: gravity-driven flow with viscosity, surface tension, cohesion
- **Thermal simulation**: heat diffusion, cooling, blackbody radiation glow
- **Fluid dynamics**: velocity advection, pressure projection (Jacobi), vorticity confinement
- **Acoustics**: weakly-compressible gas pressure waves, explosion shockwaves

### Phase 1 — Extended Physics
- **Electricity**: charge propagation through conductors, arc breakdown with heat/pressure pulses, brush charge injection (mode 4)
- **Biology/Ecology**: nutrient cycling, moisture dynamics, plant/slime growth and decay
- **Weather**: atmospheric humidity, evaporation, condensation, rain, wind advection

### Phase 2 — Debug & UI
- **Debug overlay**: heatmap visualization for pressure, charge, nutrient, moisture, humidity (Tab)
- **Inspector panel**: real-time cell properties including all ecology fields (I)

### Phase 3 — Rendering
- **Ambient occlusion**: depth shading below solid surfaces
- **Emissive glow**: hot materials illuminate neighboring cells
- **Water depth**: deeper water renders darker blue
- **Bloom post-FX**: extract/bright pass + separable gaussian blur + composite, disabled in debug view

## Materials

Material definitions are loaded from `simulation/materials.yaml` through `simulation/materials.py`.

### v6 Material Schema

The new v6 schema (`simulation/material_schema.py`) supports structured property groups:
- `physical` — density, viscosity, restitution, friction
- `thermal` — melting_point, boiling_point, thermal_conductivity
- `electrical` — conductivity, capacitance, breakdown_threshold
- `chemical` — reactivity, corrosion_resistance, ph_sensitivity
- `biological` — organic, nutrient_value, decomposition_rate, toxicity
- `explosive` — explosive, detonation_temp, blast_radius_multiplier

Load v6 YAML via `MaterialRegistry.from_v6_yaml()`; the loader validates and converts to the internal flat format for backward compatibility. See `simulation/materials_v6.yaml` for examples.

The active material IDs are `0..60`; the authoritative registry and GPU rule buffer are validated at import/test time. See `docs/MATERIALS.md` for schema and packing details.

## Architecture

Important files:

- `main.py`: game loop, input, UI orchestration, save/load actions.
- `launcher.py`: tabbed launcher UI.
- `simulation/engine.py`: public simulation API and high-level orchestration.
- `gpu/pipeline.py`: GPU compute pass order and resource binding.
- `gpu/pass_graph.py`: declarative compute pass definitions and ordering.
- `gpu/buffers.py`: GPU buffer/texture allocation and swap management.
- `gpu/resources.py`: centralized resource binding registry.
- `gpu/uniforms.py`: UBO packing for simulation, explosion, VFX, and wind data.
- `gpu/shader_registry.py`: shader manifest and loading with common.glsl prepended.
- `gpu/profiler.py`: per-pass GPU timing instrumentation.
- `levels/`: built-in and custom level support.
- `ui/` and `hud.py`: overlays, pause menu, inspector, HUD, sound placeholder.

See `docs/ARCHITECTURE.md` for a broader system map.

## Testing

Run headless/static tests:

```bash
python -m pytest tests/ -m "not gpu"
```

Run GPU-related tests only on machines with compatible OpenGL support:

```bash
python -m pytest tests/test_gpu_integration.py
```

See `docs/TESTING.md` for the recommended validation workflow.

## Documentation Index

- `docs/ARCHITECTURE.md`: project structure and data flow.
- `docs/GPU_PIPELINE.md`: compute pass order, resource ownership, binding contracts.
- `docs/MATERIALS.md`: material schema, rule buffer layout, cell packing.
- `docs/SAVE_FORMAT.md`: save versions and migration policy.
- `docs/TESTING.md`: test suites, GPU requirements, performance checks.
- `docs/CHANGELOG.md`: consolidated implementation history.
- `shaders/BUFFER_BINDINGS.md`: shader resource binding table.
