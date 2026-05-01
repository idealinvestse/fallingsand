# Buffer and Texture Binding Conventions

This document describes the GPU resource binding layout used across all shaders.

## SSBO Bindings (Shader Storage Buffer Objects)

| Binding | Name | Type | Purpose | Used In |
|---------|------|------|---------|---------|
| 0 | cells / cellsIn | readonly uint[] | Cell data read buffer | All shaders except render |
| 1 | cellsOut / write_buf | writeonly uint[] | Cell data write buffer | state, advect shaders |
| 2 | rules | readonly float[] | Material properties | All shaders |
| 8 | reservations | coherent uint[] | Cell move reservations | advect_shader |
| 9 | counters | coherent uint[] | Statistics counters | stats_counter |

## Image2D Texture Bindings

| Binding | Format | Name | Purpose | Read/Write |
|---------|--------|------|---------|------------|
| 3 | RG32F | velTex / velIn | Velocity field (vx, vy) | Read |
| 4 | RG32F | velOut / vel_b | Velocity output | Write |
| 4 | R32F | divergenceTex | Divergence field | Write |
| 5 | R32F | pressureTex / pres_a | Pressure field | Read |
| 6 | R32F | pressureOut / pres_b | Pressure output | Write |
| 7 | RGBA8 | displayTexture | Final render output | Write |
| 8 | R32F | vorticityTex | Vorticity for confinement | Read/Write |
| 11 | R32F | tempTex / tempIn / temp_a | Temperature field | Read |
| 12 | R32F | tempOut / temp_b | Temperature output | Write |

## UBO Bindings (Uniform Buffer Objects)

Defined in `uniforms.glsl`:

| Binding | Name | Purpose |
|---------|------|---------|
| 3 | SimConfig | Grid size, dt, frame |
| 4 | ExplosionConfig | Explosion physics params |
| 5 | ExplosionVfxConfig | Explosion visual effects |
| 6 | WindConfig | Wind vector and enabled flag |

## Notes

- **Binding 3 conflict**: UBO (uniforms.glsl) and Image2D (velTex) both use binding 3,
  but they are different resource types (UBO vs image), so this is valid in OpenGL 4.3+.

- **Double buffering**: Most textures have _a and _b variants that are swapped via
  `swap_*_buffers()` methods in BufferManager.

- **Auxiliary textures**: mass_a/b and wind_tex are allocated for wet-mass and wind
  workflows. Wind is also represented through runtime state and UBO data.

- **Image formats**: RG32F = vec2 float32, R32F = float32, RG16F = vec2 float16,
  RGBA8 = 4x uint8 normalized.

## Adding New Resources

When adding new bindings:
1. Use the next available binding number
2. Document it here
3. Update BufferManager if it's a new buffer type
4. Update all shaders that need access
5. Ensure consistent format across all shaders
