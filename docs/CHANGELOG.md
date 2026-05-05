# Changelog

Consolidated implementation history for the Falling Sand simulation.

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
