# Changelog

Consolidated implementation history for the Falling Sand simulation.

## v6.0 Final Polish (2026-05)

### Phase 4 — UI & CLI Enhancements
- **Performance overlay**: Real-time FPS monitoring with Ctrl+P, per-pass timing bars, FPS history graph, budget-exceeded highlighting, and quality tier indicator.
- **System controls panel**: Real-time parameter tuning for electricity (charge decay, breakdown threshold), biology (growth rate, decay rate), weather (evaporation rate, saturation threshold), and bloom (threshold, intensity, radius, quality).
- **CLI flags**: Added 20+ new CLI flags for all system parameters including electricity, biology, weather, bloom, and adaptive performance settings.
- **Transpiration rate**: Added `transpiration_rate` uniform to weather shader for biology → weather coupling.

### Phase 5 — v7 Foundation Features
- **Quality tier auto-adjustment**: Three-tier system (High/Medium/Low) that automatically adjusts pressure iterations, acoustic substeps, and bloom enabled based on sustained FPS.
- **Sparse region optimization**: Tracks active (non-air) cells and limits GPU dispatch to bounding boxes, reducing compute for mostly-empty simulations.
- **Enhanced adaptive pass skipping**: Pass priority system (0-4) for selective skipping of optional passes when frame budget exceeded.
- **Adaptive quality mode**: Enable via `--adaptive-quality` flag with `--min-fps-target` for automatic quality scaling.

### Phase 6 — Testing & Validation
- **Integration tests**: Created `tests/test_cross_system_coupling.py` with test cases for electricity → biology, biology → weather, fluid → electricity, and bloom effects.
- **Performance benchmarks**: Extended `tests/benchmark_performance.py` with 512×512 low-res, adaptive mode, and sparse region benchmarks.
- **Manual testing checklist**: Created `MANUAL_TESTING_CHECKLIST.md` with comprehensive testing coverage for all new features.

### Phase 7 — Documentation
- **ADAPTIVE_SIMULATION.md**: New documentation for quality tier system, sparse region optimization, and adaptive pass skipping.
- **PERFORMANCE.md**: Updated with adaptive simulation details and quality tier information.
- **GPU_PIPELINE.md**: Updated with sparse region optimization section.
- **ARCHITECTURE.md**: Updated with performance monitoring section describing performance overlay and adaptive quality.

## Phase 3 — Rendering (2026-05)

- **Ambient occlusion**: cells below solid surfaces are darkened 25%; stacked solids darken 8% per layer.
- **Emissive light propagation**: hot/emissive neighbors (8-direction stencil) cast blackbody-colored light onto surroundings with inverse-square falloff.
- **Water depth**: water cells probe downward (up to 8 cells) and render darker/more saturated blue with depth.
- All effects are computed in `render_shader.glsl` and are inactive when debug overlay is active.

## Phase 2 — Debug & UI (2026-05)

- **Debug overlay**: `render_shader.glsl` supports `debugView` uniform (0=off, 1=pressure, 2=charge, 3=nutrient, 4=moisture, 5=humidity) with per-field heatmap color scales.
- **Tab keybinding**: cycles through debug views when unpaused (paused Tab still cycles levels).
- **Inspector ecology section**: panel shows charge, nutrient, moisture, humidity values; panel height increased to 480px.
- **probe_cell**: reads charge, nutrient, moisture, humidity textures alongside existing fields.

## Phase 1 — Extended Physics (2026-05)

### Electricity
- **Charge propagation**: `electricity_step.glsl` with 4-neighbor conductivity-weighted diffusion, harmonic mean weighting across material boundaries, exponential decay, and hard cap.
- **Arc breakdown**: `electricity_arc.glsl` triggers when charge exceeds `breakdownThreshold` on conductive materials (cond > 0.3), discharging to zero with temperature spike and pressure pulse.
- **Brush charge injection**: mode 4 in `brush_shader.glsl` adds `chargeDelta` to the charge field.
- **GPU resources**: `charge_a/b` textures (r32f, binding 9/10), swap/clear/resize support.

### Biology/Ecology
- **Nutrient cycling**: `biology_step.glsl` diffuses nutrients through soil and water, consumed by bio materials for growth, replenished by decay.
- **Moisture dynamics**: diffuses through all materials, evaporates with heat, replenished by water cells.
- **Growth/decay**: bio cells (plant, slime, blood, virus) consume nutrients + moisture + warmth to grow; decay without resources returns nutrients.
- **GPU resources**: `nutrient_a/b` (binding 13/14), `moisture_a/b` (binding 15/16).

### Weather
- **Atmospheric humidity**: `weather_step.glsl` diffuses through air/gas, advected by wind, evaporates from water, condenses when saturated.
- **Rain**: humidity above saturation falls downward.
- **GPU resources**: `humidity_a/b` (binding 17/18).

## Core Physics (pre-Phase 1)

- Multi-pass GPU pipeline: state → liquid_step → heat → vorticity → velocity_advect → force → divergence → pressure → project → advect.
- Acoustic solver: weakly-compressible gas pressure waves with iterative substeps.
- Explosion system: multiple types (high explosive, deflagration, thermobaric, napalm, fragmentation), crater formation, shrapnel, shockwave rings, screen flash.
- Thermal simulation: heat diffusion, Newton cooling, blackbody radiation glow, pre-ignition charring.
- Liquid dynamics: gravity-driven flow with viscosity, surface tension, cohesion, capillary action.
- Wind system: UBO-driven wind vector with toggle and arrow-key adjustment.

## Infrastructure

- **Save format**: `FSND` v7 with separate cell (uint32) and temperature (float32) storage.
- **Material system**: YAML-driven definitions, `RULE_STRIDE = 49`, validated at import time.
- **Shader registry**: manifest-based loading with `common.glsl` prepended.
- **Pass graph**: declarative `ComputePass` definitions with reads/writes/swaps/optional/iterative metadata.
- **Resource registry**: centralized `ResourceBinding` definitions for SSBOs, images, and UBOs.
- **Profiler**: per-pass GPU timing via `_timed_run` with `PassProfiler`.
- **Testing**: 441 tests covering contracts, physics invariants, GPU integration, materials, shaders, and UI.
