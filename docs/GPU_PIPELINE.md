# GPU Pipeline

The simulation is GPU-first. Cells live in double-buffered SSBOs, while velocity, pressure, temperature, charge, nutrient, moisture, humidity, vorticity, display output, and auxiliary fields live in textures.

## Sparse Region Optimization (v7 Foundation)

When sparse mode is enabled, the pipeline tracks active (non-air) cells and limits GPU dispatch to bounding boxes around these regions. This reduces compute when the simulation is mostly empty.

Enable via System Controls Panel or `engine.pipeline.enable_sparse_mode(True)`.

## Frame Step Order

`gpu/pipeline.py` dispatches these passes for each adaptive substep:

1. `state_shader.glsl`
2. `liquid_step.glsl`
3. `heat_shader.glsl`
4. `vorticity_shader.glsl`
5. `velocity_advect_shader.glsl`
6. `force_shader.glsl`
7. `divergence_shader.glsl`
8. `pressure_shader.glsl`
9. `project_shader.glsl`
10. `electricity_step.glsl` (optional)
11. `electricity_arc.glsl` (optional)
12. `biology_step.glsl` (optional)
13. `weather_step.glsl` (optional)
14. `acoustic_pressure_step.glsl` / `acoustic_velocity_step.glsl` (optional, iterative)
15. `advect_shader.glsl`

Rendering dispatches `render_shader.glsl` with ambient occlusion, emissive glow, water depth, and optional debug overlay, then blits `display_texture` to the screen.

Bloom post-FX is applied after rendering (if enabled): extract → blur H → blur V → composite.

## Phase 1 Passes (Optional)

### Electricity

**Shader**: `electricity_step.glsl`

**Purpose**: Charge propagation through conductive materials using harmonic mean conductivity weighting.

**Reads**:
- cells (SSBO, binding 0)
- rules (SSBO, binding 2)
- charge_in (r32f, binding 9)

**Writes**:
- charge_out (r32f, binding 10)

**Optional**: True (config.enable_electricity)

**Parameters**:
- dt: Integration timestep
- chargeDecay: Exponential decay rate
- maxCharge: Hard cap for stability

**Documentation**: See `docs/ELECTRICITY.md`

### Electricity Arc

**Shader**: `electricity_arc.glsl`

**Purpose**: Arc breakdown when charge exceeds material breakdown threshold.

**Reads**:
- cells (SSBO, binding 0)
- rules (SSBO, binding 2)
- charge_in (r32f, binding 9)
- temp_in (r32f, binding 11)

**Writes**:
- charge_out (r32f, binding 10)
- temp_out (r32f, binding 12)
- divergence (r32f, binding 4)

**Optional**: True (config.enable_electricity)

**Parameters**:
- dt: Integration timestep
- breakdownThreshold: Charge level for arc
- arcTempDelta: Temperature spike
- arcPressurePulse: Divergence magnitude

**Documentation**: See `docs/ELECTRICITY.md`

### Biology

**Shader**: `biology_step.glsl`

**Purpose**: Nutrient cycling, moisture dynamics, and bio-material growth/decay.

**Reads**:
- cells (SSBO, binding 0)
- rules (SSBO, binding 2)
- nutrient_in (r32f, binding 13)
- moisture_in (r32f, binding 15)
- temp_in (r32f, binding 11)

**Writes**:
- nutrient_out (r32f, binding 14)
- moisture_out (r32f, binding 16)

**Optional**: True (config.enable_biology)

**Parameters**:
- dt: Integration timestep
- nutrientDiffuseRate: Nutrient diffusion speed
- moistureDiffuseRate: Moisture diffusion speed
- growthRate: Bio growth speed
- decayRate: Bio decay speed

**Documentation**: See `docs/BIOLOGY.md`

### Weather

**Shader**: `weather_step.glsl`

**Purpose**: Atmospheric humidity, condensation, evaporation, and rain.

**Reads**:
- cells (SSBO, binding 0)
- humidity_in (r32f, binding 17)
- temp_in (r32f, binding 11)

**Writes**:
- humidity_out (r32f, binding 18)

**Optional**: True (config.enable_weather)

**Parameters**:
- dt: Integration timestep
- humidityDiffuseRate: Humidity diffusion speed
- evaporationRate: Water to humidity conversion
- condensationRate: Humidity to water conversion
- saturationThreshold: Humidity level for condensation

**Documentation**: See `docs/WEATHER.md`

## v6.1 Deep System Interactions

### Overview

v6.1 introduces bidirectional coupling between previously isolated simulation subsystems: Electricity ↔ Fluid, Electricity ↔ Biology, Weather ↔ Fluid, and Biology ↔ Fluid. All interactions are physics-based and respect the existing double-buffered texture architecture.

### Cross-System Data Flow

| From System | To System | Mechanism | Pass Order Dependency |
|-------------|-----------|-----------|---------------------|
| Fluid (moisture) | Electricity | Moisture boosts conductivity in wet conductors | biology → electricity |
| Electricity (charge) | Biology | Moderate charge stimulates growth, high charge causes damage | electricity → biology |
| Electricity (charge) | Weather | Rain washes charge from surfaces | weather reads charge |
| Weather (humidity) | Fluid | Condensation adds moisture to solid surfaces | weather → biology (moisture) |
| Biology (nutrient) | Fluid | Nutrients advect with liquid velocity | liquid_step → biology |

### Modified Pass Specifications

#### electricity_step.glsl (v6.1)

**New Reads**:
- moisture_in (r32f, binding 15)
- velocity_in (rg32f, binding 3)

**New Uniforms**:
- electricity_moisture_boost: Conductivity multiplier per moisture unit (default: 2.0)
- wet_arc_temp_multiplier: Arc heat reduction when wet (default: 0.5)
- electrolysis_strength: Charge transport via liquid velocity (default: 0.3)

**Interaction Rules**:
- Moisture-based conductivity: `effective_cond = base_cond × (1.0 + moisture × 2.0)`
- Wet conductors propagate charge faster: `rate = 4.0 × (1.0 + moisture × 0.5)`
- Electrolysis: Charged liquid cells transport charge downstream via velocity field

#### electricity_arc.glsl (v6.1)

**New Reads**:
- moisture_in (r32f, binding 15)

**New Uniforms**:
- wet_arc_temp_multiplier: Arc heat reduction when wet (default: 0.5)

**Interaction Rules**:
- Wet arcs: Less heat (multiplied by 0.5 when fully wet), more pressure wave (2× when wet)
- Discharge rate slower when wet: `discharge_rate = mix(1.0, 0.7, wetness)`

#### biology_step.glsl (v6.1)

**New Reads**:
- charge_in (r32f, binding 9)

**New Uniforms**:
- biology_electro_stim: Growth boost from moderate charge (default: 0.3)
- charge_damage_threshold: Charge level causing bio damage (default: 500.0)
- charge_stim_range_low: Lower bound for electro-stimulation (default: 10.0)
- charge_stim_range_high: Upper bound for electro-stimulation (default: 100.0)
- temp_effect_multiplier: Global temperature coupling strength (default: 1.0)

**Interaction Rules**:
- Electro-stimulation: `growth_modifier = 1.0 + clamp(charge × 0.3, 0.0, 1.5)` for 10-100 charge
- High charge damage: `growth_modifier = max(0.2, 1.0 - damage)` for charge > 500
- Temperature coupling: `growth_modifier *= smoothstep(50.0, 150.0, temp)`

#### weather_step.glsl (v6.1)

**New Reads**:
- moisture_in (r32f, binding 15)
- charge_in (r32f, binding 9)

**New Uniforms**:
- condensation_temp_boost: Temperature effect on condensation (default: 2.0)
- rain_charge_wash_rate: Charge dissipation from rain (default: 0.1)
- rain_moisture_boost: Moisture added by rain (default: 50.0)
- evap_temp_multiplier: Temperature coupling for evaporation (default: 1.0)

**Interaction Rules**:
- Surface condensation: `condensation_chance = clamp((humidity - 0.6) × 2.0 × temp_factor, 0.0, 0.15)`
- Rain charge wash: Rain reduces charge on solid surfaces (visual effect)
- Enhanced evaporation: Temperature-coupled evaporation rate

#### liquid_step.glsl (v6.1)

**New Reads**:
- nutrient_in (r32f, binding 13)
- velocity_in (rg32f, binding 3)

**New Writes**:
- nutrient_out (r32f, binding 14)

**Interaction Rules**:
- Nutrient advection: Semi-Lagrangian transport via velocity field
- `nutrient_new = mix(nutrient_old, nutrient_upwind, min(velocity_magnitude × 0.5, 0.8))`
- Water cells gain nutrients from flow: `nutrient = mix(nutrient, advectedNutrient, 0.7)`

### Performance Impact

Estimated GPU overhead on 1024×1024 grids: **5.5%** (within 5-8% budget)

| Pass | Base Cost | v6.1 Addition |
|------|-----------|---------------|
| liquid_step | 1.0% | +0.3% |
| electricity | 0.8% | +0.2% |
| electricity_arc | 0.5% | +0.1% |
| biology | 1.2% | +0.1% |
| weather | 1.0% | +0.3% |
| **Total** | 4.5% | +1.0% |

### Configuration

All v6.1 features controlled by `config.enable_deep_interactions` (default: True). Individual interaction parameters can be tuned via config:

```python
# Electricity + Fluid
config.electricity_moisture_boost = 2.0
config.wet_arc_temp_multiplier = 0.5
config.electrolysis_strength = 0.3

# Biology + Electricity
config.biology_electro_stim = 0.3
config.charge_damage_threshold = 500.0

# Weather + Fluid
config.condensation_temp_boost = 2.0
config.rain_charge_wash_rate = 0.1

# Temperature coupling
config.temp_effect_multiplier = 1.0
```

### Memory Barriers

Required after modified passes:
- After electricity_step: charge texture written
- After electricity_arc: charge, temperature, divergence written
- After biology_step: nutrient, moisture written
- After weather_step: humidity written
- After liquid_step: cells, temperature, nutrient written

---

## Bloom Post-FX

### Extract Pass

**Shader**: `bloom_extract.glsl`

**Purpose**: Extract bright pixels from display texture and downsample to half resolution.

**Input**: display_texture (rgba8, binding 7, full resolution)

**Output**: bloom_a (rgba8, binding 19, half resolution)

**Parameters**:
- bloomThreshold: Luminance threshold (default 0.6)

**Dispatch**: ceil(width/32, height/32)

### Blur Pass

**Shader**: `bloom_blur.glsl`

**Purpose**: Separable Gaussian blur (horizontal and vertical passes).

**Input**: bloom_a / bloom_b (rgba8, binding 19/20, half resolution)

**Output**: bloom_b / bloom_a (rgba8, binding 20/19, half resolution)

**Parameters**:
- blurDirection: 0 for horizontal, 1 for vertical
- blurRadius: Radius multiplier (planned)

**Dispatch**: ceil(width/32, height/32)

**Kernel**: 5-tap Gaussian (current implementation)

### Composite

**Purpose**: Add bloom to main render.

**Location**: Integrated in `render_shader.glsl` (lines 253-273)

**Input**: bloom_a (rgba8, binding 19, half resolution)

**Operation**: Bilinear sampling with 0.6 blend factor

**Condition**: Only when debugView == 0 (disabled in debug views)

**Documentation**: See `docs/BLOOM.md`

## Resource Invariants

- Cell SSBOs are double-buffered and swapped after passes that write cells.
- Temperature textures are `r32f` and double-buffered.
- Velocity textures are `rg32f` and double-buffered.
- Pressure textures are `r32f` and double-buffered.
- Charge textures are `r32f` and double-buffered.
- Nutrient textures are `r32f` and double-buffered.
- Moisture textures are `r32f` and double-buffered.
- Humidity textures are `r32f` and double-buffered.
- `reservations_buf` is cleared before cell advection.
- `write_buf` is cleared to air before cell advection.
- Memory barriers are required after compute passes before consuming their outputs.
- All Phase 1 passes (electricity, biology, weather) are optional and disabled by default.

## Dispatch Size

The pipeline uses ceil-dispatch with 16x16 local workgroups:

```text
group_x = ceil(width / 16)
group_y = ceil(height / 16)
```

Shaders must bounds-check global invocation coordinates.

## Binding Contract

The detailed binding table lives in `shaders/BUFFER_BINDINGS.md`. Any new buffer, image, or UBO must be added there and covered by static tests where possible.

## Shader Loading

Shaders are loaded via `gpu/shader_registry.py` using a manifest-based system. The loader prepends `common.glsl` (which contains the `#version 430` directive and shared definitions) to individual shader files. Individual shader files must NOT include their own `#version` directive, as the loader removes it to prevent GLSL compilation errors from duplicate directives. The shader registry validates all shaders at startup and supports runtime reloading for context recovery.
