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
