# GPU Pipeline

The simulation is GPU-first. Cells live in double-buffered SSBOs, while velocity, pressure, temperature, charge, nutrient, moisture, humidity, vorticity, display output, and auxiliary fields live in textures.

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
