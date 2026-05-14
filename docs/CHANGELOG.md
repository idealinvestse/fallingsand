# Changelog

Consolidated implementation history for the Falling Sand simulation.


## v7.2 Combustion Polish & Fine-Tuning (2026-XX)

### Per-Material Wet Combustion

- Added `moisture_resistance`, `wet_ignition_penalty`, and `wet_burn_rate_multiplier` material fields.
- Extended the material rule buffer to expose per-material wet behavior to shaders.
- Updated state combustion logic so plant/wood are highly moisture-sensitive while coal/char/hot ash resist wet suppression better.

### HotAsh, Char & Soot Polish

- Increased HotAsh flammability and added hot-ash re-ignition behavior for adjacent fuels.
- Added dedicated render paths for Char, Soot, and HotAsh so new combustion stages are visually distinct.
- Expanded combustion stability tests to cover wet material properties, HotAsh re-ignition hooks, and byproduct rendering paths.

## v7.1 Combustion Overhaul (2026-XX)

### Realistic Combustion & Fire System

#### Atmosphere Ignition Stabilization

- Retuned gas and oil material properties to prevent large open gas/air regions from slowly self-igniting.
- Changed air-only combustion support from an unlimited oxidizer to weak, temperature-gated ignition support.
- Added moisture and humidity suppression in `state_shader.glsl`; wet environments dampen heat gain, raise effective ignition thresholds, and shorten fire/ember lifetime.

#### Staged Burning & New Byproducts

- Added `char` and `soot` material IDs for staged combustion and heavy smoke residue.
- Organic fuels now progress through a charring/smoldering path before ember/ash residue.
- Hydrocarbon and coal fuels now produce more soot under oxygen-poor conditions.
- Fire residue now depends on local oxygen availability, producing smoke when oxygenated and soot when oxygen-starved.

#### Weather, Wind & Cross-System Integration

- State pass now reads `moisture_in` and `humidity_in` for weather-driven fire suppression.
- Force pass now applies wind to fire, ember, char, soot, and blast fronts with material-specific coupling.
- Napalm reaction slots now differentiate fire-contact soot production from oxygen-fed active flame.

#### Tests & Documentation

- Added `tests/test_combustion_stability.py` covering gas anti-runaway thresholds, weak-air ignition gates, staged charring, soot generation, moisture/humidity suppression, and wind coupling.
- Updated material, shader, pass graph, and documentation tests for the expanded combustion behavior.
- Expanded `docs/MATERIALS.md` with combustion stages, byproduct behavior, weather integration, and regression coverage notes.

## v7.0 Evolution (2026-XX)

### Phase 4 — Final Polish, Testing & Release Preparation

#### Critical Bug Fixes & Stability Polish

- **Shader compilation fixes**:
  - Fixed duplicate `#version` directives: Modified gpu/shader_registry.py to remove `#version` from individual shaders when common.glsl is prepended (GLSL requires `#version` only once at the top)
  - Fixed undeclared variables in state_shader.glsl: Moved declarations of `blastSrcOff`, `blastSrcPow`, `nearHot`, `nearMagnet`, and `nearMagnetSouth` earlier in the shader before first use
  - Fixed missing uniform declaration: Added `velIn` uniform declaration to state_shader.glsl
  - Fixed duplicate variable declaration: Removed duplicate `pC` declaration in pressure_shader.glsl

- **Persistence manager initialization**:
  - Fixed buffers not being set: Changed PersistenceManager constructor to accept buffers as a required parameter instead of leaving it as None
  - Removed unused Optional typing from persistence.py after buffers became required

- **Brush index bounds**:
  - Fixed brush index out of range error: Changed brush wrapping from `NUM_TYPES` constant (61) to actual material count from `get_all_materials()`
  - Removed unused NUM_TYPES import from main.py

- **Pressure solver stabilization**:
  - Enhanced clamping bounds: increased from -100.0/1000.0 to -500.0/5000.0 in pressure_shader.glsl
  - Emergency reset detection: PRESSURE_EMERGENCY_RESET = 10000.0 with fallback to previous pressure
  - Emergency reset method: `emergency_pressure_reset()` in simulation/engine.py
  - Pressure monitoring: periodic sampling every 60 frames with auto-reset on extreme values
  - Grid-size-aware hydrostatic gradient: scales with grid height (normalized to 512px baseline)

- **OpenGL context loss handling**:
  - Context validity check: `check_context_valid()` in gpu/context.py
  - Context recreation: `recreate_context()` method with shader reloading
  - Window resize handling: VIDEORESIZE event support with UI overlay updates
  - Context error recovery: try/except in main loop for simulation step and render

- **Memory management for large grids**:
  - VRAM estimation: `estimate_vram_usage()` static method in gpu/buffers.py
  - VRAM warnings: launcher, CLI, and config validation warnings for grids > 1024×1024
  - Config validation: GPU memory query with 70% threshold warning
  - Launcher VRAM display: status label shows VRAM usage for large resolutions

- **Material property validation**:
  - GPU-safe range checks: density (0-50), viscosity (0-100), restitution (0-2)
  - NaN/inf detection: validates all material properties at startup
  - Enhanced validation: `_validate_material_properties()` in gpu/buffers.py
  - Startup validation: `validate_all_buffers()` called in simulation/engine.py

#### Comprehensive Testing

- **Cross-system interaction tests**: tests/test_cross_system_interactions.py
  - Electricity ↔ Biology coupling validation
  - Biology ↔ Weather coupling validation
  - Weather ↔ Electricity coupling validation
  - Fluid ↔ Electricity coupling validation
  - Cross-system edge cases and parameter validation

- **Edge-case tests**: tests/test_edge_cases.py
  - Empty grid stability
  - Boundary conditions (min/max grid sizes)
  - Extreme parameter values (pressure iterations, substeps, window sizes)
  - System toggle stability (all on/off)
  - Parameter range validation (charge, biology, weather, bloom)

- **Save/load migration tests**: tests/test_save_load_migration.py
  - Save format option validation (v7/v8)
  - Field preservation verification
  - CRC32 validation documentation
  - Migration path validation
  - Persistence infrastructure checks

- **Manual checklist automation**: tests/test_manual_checklist_automation.py
  - CLI flag parsing for all 20+ parameters
  - System controls configuration validation
  - Performance overlay configuration validation
  - Cross-system coupling parameter validation
  - Save/load configuration validation

- **Pressure stability tests**: Enhanced tests/test_pressure_stability.py
  - Enhanced clamping bounds validation
  - Emergency reset threshold validation
  - Config flag validation
  - Hydrostatic gradient scaling validation

#### Release Preparation

- **PyInstaller build script**: Enhanced tools/build_exe.py
  - `--debug` flag: builds with console output for debugging
  - `--onefile` flag: builds as single file (slower startup)
  - Auto-copy README to dist/
  - Auto-create VERSION.txt in dist/
  - Improved spec file: better hiddenimports, excludes, data files

### Phase 3 — New Features, Content & Polish

#### Extended Material System
- **New property groups**: Added MagneticProps, PlasmaProps, and GlassProps to v6 material schema (simulation/material_schema.py)
- **8 new materials**:
  - Magnetic: magnet (north polarity), magnet_south (south polarity)
  - Plasma: plasma (high-temperature ionized gas), lightning_plasma (ultra-hot arc plasma)
  - Glass: glass (transparent, shatters), obsidian (volcanic glass, very hard)
  - Enhanced: thermite_enhanced (magnetic ignition), acid_glass_corrosive (glass corrosion)
- **GPU rule buffer**: Increased RULE_STRIDE from 49 to 61 to accommodate 12 new material property fields
- **Shader interactions**: Implemented magnetic attraction/repulsion, plasma recombination and ignition, glass shattering from impact and thermal shock
- **Plasma conductivity**: Enhanced electricity_step.glsl with maximum conductivity and faster propagation for plasma materials

#### Advanced Explosions & Chain Reactions
- **Enhanced chain reaction logic**: Material-specific sensitivity modifiers (C4: 0.95, gunpowder: 0.4, dynamite: 0.7, thermite: 0.6, napalm: 0.8)
- **Distance attenuation**: Chain reaction probability decreases with distance from blast source
- **Electrical ignition**: Conductive explosives (cond > 0.3) detonate from electrical sparks
- **Magnetic ignition**: Thermite materials can be ignited by nearby magnetic materials when heated
- **Hotkey exposure**:
  - X: Standard explosion
  - Shift+X: Big explosion
  - Ctrl+X: Thermobaric explosion
  - Alt+X: Deflagration explosion

#### Documentation Updates
- **PERFORMANCE.md**: Enhanced with new material performance impact notes
- **ELECTRICITY.md**: Updated with v6.1 cross-system interactions (moisture-based conductivity boost, electrolysis charge transport, plasma conductivity)
- **BIOLOGY.md**: Enhanced with new material biological properties and ecosystem interaction examples
- **WEATHER.md**: Updated with plasma atmospheric effects and weather interaction examples
- **CHANGELOG.md**: Comprehensive v6.0→v7.0 changes documented

## v6.1 Phase 1 Implementation (2026-05)

### Critical Stability Fixes

- **Pressure clamping**: Added PRESSURE_MIN (-100.0) and PRESSURE_MAX (1000.0) constants in pressure_shader.glsl with NaN/inf detection to prevent simulation explosions
- **Hydrostatic pressure initialization**: Implemented realistic pressure gradient in simulation/engine.py `_initialize_pressure()` using depth-based calculation (density × gravity × depth)
- **Material property validation**: Added validation in gpu/buffers.py `_create_rule_buffer()` to check rule buffer dimensions and density ranges at load time
- **Pressure clamping config**: Added `pressure_clamp_min`, `pressure_clamp_max`, and `enable_pressure_validation` options to core/config.py
- **Unit tests**: Created tests/test_pressure_stability.py with comprehensive tests for pressure clamping, hydrostatic initialization, and material validation

### Sparse Region Optimization (Complete)

- **Dispatch integration**: Fully integrated sparse dispatch ranges into gpu/pipeline.py `_step_multi_pass()` for all compute passes (state, liquid, heat, vorticity, velocity_advect, force, divergence, pressure, project, electricity, biology, weather, acoustic, advect)
- **Shader uniforms**: Added `sparseRegion` (uvec4) and `sparseEnabled` (bool) uniforms to shaders/common.glsl with `inSparseRegion()` helper function
- **Early-out support**: Added sparse region early-out check to state_shader.glsl
- **Public API**: Exposed `enable_sparse_mode(enabled: bool)` in simulation/engine.py for user control
- **Performance**: Expected 35-50% FPS improvement on mostly empty grids

### Adaptive Quality System (Complete)

- **Hysteresis logic**: Enhanced `update_quality_tier()` with 120-frame cooldown (2 seconds at 60fps) to prevent rapid tier switching
- **Tier logging**: Added console logging for tier changes with FPS context for debugging
- **Expanded tiers**: Enhanced quality tiers in core/config.py to include `bloom_quality`, `vorticity_confinement`, and `heat_diffusion_iterations` parameters
- **Full tier application**: Updated `_apply_quality_tier()` to apply all tier settings including new parameters
- **Pass priority mapping**: Expanded `_should_skip_pass()` with full priority mapping covering biology, weather, electricity, arc, acoustic, vorticity, and heat passes

### Performance Overlay (Complete)

- **VRAM estimation**: Added accurate VRAM estimation based on grid size and texture memory in ui/performance_overlay.py
- **FPS graph fix**: Fixed budget line to use target FPS (55.0) instead of current FPS
- **Status indicators**: Added sparse mode status, adaptive quality status, and quality tier display to performance overlay

### Documentation Updates

- **PERFORMANCE.md**: Updated with Phase 1 enhancements for quality tier system, sparse region optimization, and adaptive pass skipping
- **CHANGELOG.md**: Added comprehensive Phase 1 implementation notes

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
