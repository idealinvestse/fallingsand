# Bloom Post-FX

## Overview

Two-pass Gaussian blur post-processing for emissive glow effects. Bloom creates the characteristic glow around hot materials (fire, lava) and bright emissive materials by extracting bright pixels, blurring them, and compositing the result back onto the main render.

## Pipeline

The bloom pipeline consists of three compute passes followed by composite in the render shader:

1. **Extract**: Downsample to half-resolution, threshold luminance
2. **Blur H**: Horizontal Gaussian blur
3. **Blur V**: Vertical Gaussian blur
4. **Composite**: Add bloom to display with blend factor

### Extract Pass (bloom_extract.glsl)

Extracts bright pixels from the full-resolution display texture:

- **Input**: display_texture (rgba8, full resolution)
- **Output**: bloom_a (rgba8, half resolution)
- **Operation**: 
  - Compute luminance: `lum = dot(color, vec3(0.299, 0.587, 0.114))`
  - Threshold: `bright = max(0.0, lum - bloomThreshold)`
  - Scale: `output = color * (bright / (lum + 1e-6))`
- **Dispatch**: ceil(width/32, height/32) workgroups
- **Optimization**: Half-resolution reduces memory bandwidth

### Blur Pass (bloom_blur.glsl)

Separable Gaussian blur applied in two passes:

- **Input**: bloom_a / bloom_b (rgba8, half resolution)
- **Output**: bloom_b / bloom_a (rgba8, half resolution)
- **Operation**: 
  - Horizontal pass (blurDirection = 0): Blur along X axis
  - Vertical pass (blurDirection = 1): Blur along Y axis
  - Kernel: 5-tap Gaussian (current implementation)
  - Weighted sum of neighboring texels
- **Dispatch**: ceil(width/32, height/32) workgroups
- **Separability**: Two 1D passes cheaper than one 2D pass (O(n) vs O(n²))

### Composite Pass (render_shader.glsl)

Composites bloom texture onto main render:

- **Input**: bloom_a (rgba8, half resolution)
- **Operation**:
  - Bilinear sampling of bloom texture
  - Map UV coordinates to half-resolution space
  - 4-tap bilinear filter for smooth upscaling
  - Additive blend: `finalColor = baseColor + bloomSample * 0.6`
- **Location**: Lines 253-273 in render_shader.glsl
- **Condition**: Only when debugView == 0 (disabled in debug views)

## Uniform Parameters

### bloom_extract.glsl

- **bloomThreshold** (float): Luminance threshold for extraction (default 0.6)
  - Range: 0.0 to 1.0
  - Higher = fewer pixels contribute to bloom
  - Lower = more bloom, may wash out image

### bloom_blur.glsl

- **blurDirection** (int): 0 for horizontal, 1 for vertical
- **blurRadius** (float): Radius multiplier for blur kernel (default 1.0)
  - Currently unused in implementation (fixed 5-tap kernel)
  - Planned for v7 quality settings

### render_shader.glsl

- **bloomIntensity** (float): Composite blend factor (hardcoded to 0.6)
  - Planned to make configurable in v7
  - Range: 0.0 to 2.0

## Performance

### Timing (1024×1024 grid)

- **Extract**: ~0.3ms
  - Half-resolution dispatch: 32×32 = 1024 workgroups
  - Luminance computation per pixel

- **Blur H**: ~0.35ms
  - 5-tap horizontal kernel
  - Half-resolution dispatch

- **Blur V**: ~0.35ms
  - 5-tap vertical kernel
  - Half-resolution dispatch

- **Total**: ~1.0ms (5% of 20ms budget @ 50fps)

### Memory

- **bloom_a**: rgba8 @ 512×512 = 1MB
- **bloom_b**: rgba8 @ 512×512 = 1MB
- **Total**: 2MB GPU memory

### Optimization

- **Half-resolution**: 4x fewer pixels to process
- **Separable blur**: O(n) instead of O(n²)
- **Conditional dispatch**: Skipped if bloom_enabled = False
- **Debug view skip**: Disabled when visualizing scalar fields

## Configuration

### CLI Flags (main.py)

```python
--no-bloom              (default: False)
--bloom-threshold       (default: 0.6)
```

### Config Fields (core/config.py)

```python
bloom_enabled: bool = True
bloom_threshold: float = 0.6
```

### Planned v7 Additions

```python
bloom_intensity: float = 0.6
bloom_radius: float = 1.0
bloom_quality: str = "medium"  # low/medium/high
```

## Shader Bindings

### bloom_extract.glsl

```
Image:
  binding 7:  displayTexture (rgba8, readonly)
  binding 19: bloomA (rgba8, writeonly)

Uniforms:
  gridSize (uvec2)
  bloomThreshold (float)
```

### bloom_blur.glsl

```
Image:
  binding 19: bloomA (rgba8, readonly/writeonly)
  binding 20: bloomB (rgba8, readonly/writeonly)

Uniforms:
  gridSize (uvec2)
  blurDirection (int)
```

### render_shader.glsl (composite)

```
Image:
  binding 7:  displayTexture (rgba8, writeonly)
  binding 19: bloomA (rgba8, readonly)

Uniforms:
  gridSize (uvec2)
  debugView (int)
```

## Quality Settings (v7 Target)

### Low Quality

- Kernel size: 3 taps
- Resolution: Quarter (256×256 @ 1024×1024)
- Performance: ~0.4ms total

### Medium Quality (Current)

- Kernel size: 5 taps
- Resolution: Half (512×512 @ 1024×1024)
- Performance: ~1.0ms total

### High Quality

- Kernel size: 9 taps
- Resolution: Half (512×512 @ 1024×1024)
- Performance: ~1.5ms total

## Integration

### Pipeline Dispatch (gpu/pipeline.py)

Lines 491-521 in pipeline.py:

```python
if bloom_enabled and debug_view == 0:
    # 1. Extract bright pixels + downsample
    self._timed_run("bloom_extract", self.bloom_extract_shader, ...)
    
    # 2. Horizontal blur: bloom_a → bloom_b
    self._timed_run("bloom_blur_h", self.bloom_blur_shader, ...)
    
    # 3. Vertical blur: bloom_b → bloom_a
    self._timed_run("bloom_blur_v", self.bloom_blur_shader, ...)
```

### Render Integration

Lines 253-273 in render_shader.glsl:

```glsl
if (debugView == 0) {
    // Bilinear sample bloom texture
    vec3 bloomSample = bilinearSample(bloomTex, p);
    col += bloomSample * 0.6;
    col = clamp(col, 0.0, 1.0);
}
```

## Known Limitations

1. No intensity control (hardcoded to 0.6)
2. No radius control (fixed 5-tap kernel)
3. No quality settings (fixed medium quality)
4. No UI controls for bloom parameters
5. Bloom disabled in all debug views (could be selective)
6. No anamorphic bloom (different H/V radii)
7. No lens flare or streak effects

## Future Work (v7)

1. Add bloom intensity control (bloomIntensity uniform)
2. Add bloom radius control (blurRadius uniform)
3. Implement quality tiers (kernel size: 3/5/9 taps)
4. Add UI controls in system panel
5. Selective bloom in debug views (e.g., enable for pressure view)
6. Anamorphic bloom support
7. Lens flare/streak effects
8. Temporal bloom accumulation for motion blur
9. Chromatic aberration in bloom
10. Dirt/scratches overlay for cinematic effect

## Examples

### Subtle Bloom (High Threshold)

```yaml
bloom_threshold: 0.8
bloom_intensity: 0.4
```

Only very bright pixels glow, subtle effect.

### Strong Bloom (Low Threshold)

```yaml
bloom_threshold: 0.3
bloom_intensity: 1.0
```

More pixels contribute, intense glow effect.

### Cinematic Bloom (High Quality)

```yaml
bloom_threshold: 0.5
bloom_intensity: 0.8
bloom_quality: "high"
bloom_radius: 1.5
```

Large kernel, high intensity, cinematic look.
