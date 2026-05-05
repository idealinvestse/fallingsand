# Weather/Atmospheric System

## Overview

Atmospheric humidity, condensation, evaporation, and rain simulation. The weather system models the water cycle including humidity diffusion through air, wind-driven advection, evaporation from water surfaces, condensation into rain, and precipitation mechanics.

## Algorithm

### Humidity Field

Humidity represents atmospheric water vapor concentration and diffuses through gaseous materials:

1. **Diffusion**: 4-neighbor stencil weighted by material type:
   - Air, gas, steam, smoke: weight = 1.0
   - Other materials: weight = 0.1 (partial diffusion)
   - Update: `hum += (humAvg - hum) * humidityDiffuseRate * dt`

2. **Wind Advection**: First-order upwind scheme:
   - Sample humidity upwind based on wind direction
   - Update: `hum += (upHum - hum) * windAdvectStrength * length(windVector) * dt`
   - Wind vector from global wind state

3. **Clamping**: Range limited to prevent runaway:
   - Update: `hum = clamp(hum, 0.0, saturationThreshold * 3.0)`

### Evaporation

Water surfaces convert to atmospheric humidity when heated:

1. **Condition**: Water cell AND temperature > 100.0
2. **Rate**: `evap = evaporationRate * (temp - 96.0) * 0.01 * dt`
3. **Cap**: `hum = min(saturationThreshold * 2.0, hum + evap)`

Evaporation increases with temperature above ambient (96.0 units).

### Condensation

Saturated humidity condenses into water droplets when cooled:

1. **Condition**: humidity > saturationThreshold AND temperature < 120.0
2. **Rate**: `cond = condensationRate * (hum - saturationThreshold) * dt`
3. **Effect**: `hum = max(0.0, hum - cond)`
4. **Rain Formation**: If air cell and humidity drops below 50% saturation:
   - Actual water cell spawning handled by state pass
   - Weather pass only manages humidity field

### Rain

Precipitation mechanics for falling water:

1. **Condition**: humidity > saturationThreshold
2. **Transfer**: Downward humidity movement
   - Rate: `transfer = rainSpeed * (hum - saturationThreshold) * dt`
   - Update: `hum -= transfer`
3. **Deposition**: Humidity deposited to ground moisture
   - Handled by moisture field in biology system
   - Approximated by letting diffusion handle redistribution

## Uniform Parameters

### weather_step.glsl

- **dt** (float): Integration timestep from adaptive substepping
- **humidityDiffuseRate** (float): Diffusion speed for humidity (default 0.4)
- **evaporationRate** (float): Water to humidity conversion rate (default 0.1)
- **condensationRate** (float): Humidity to water conversion rate (default 0.3)
- **saturationThreshold** (float): Humidity level triggering condensation (default 100.0)
- **rainSpeed** (float): Downward speed of rain droplets (default 2.0)
- **windAdvectStrength** (float): How strongly wind pushes humidity (default 0.5)
- **windVector** (vec2): Global wind direction and strength (default (0.0, 0.0))

## Performance

- **Typical Cost**: ~1.0ms @ 1024×1024 grid
- **Optional Pass**: Can be skipped via `config.enable_weather = False`
- **Memory**: 2 × r32f textures (humidity_a, humidity_b) = 8MB @ 1024×1024
- **Workgroups**: 64×64 = 4096 workgroups @ 1024×1024

## Interactions

### Current Reads/Writes

**weather_step.glsl:**
- Reads: cells (SSBO), humidity_in (r32f), temp_in (r32f)
- Writes: humidity_out (r32f)
- Note: Wind texture referenced but not currently bound (uses uniform instead)

### Cross-System Coupling (v7 Target)

1. **Weather → Electricity**: Rain increases conductivity
   - Planned: Water evaporation adds local conductivity boost
   - Implementation: Output conductivity modifier or uniform
   - Effect: Wet materials conduct electricity better

2. **Biology → Weather**: Transpiration adds humidity
   - Planned: Bio materials with moisture transpire to atmosphere
   - Implementation: Read nutrient/moisture fields, write to humidity
   - Effect: Dense vegetation increases local humidity

3. **Weather → Biology**: Humidity affects decay rate
   - Planned: High humidity reduces bio decay rate
   - Implementation: Read humidity field in biology_step.glsl
   - Effect: Damp environments preserve bio materials longer

## Shader Bindings

### weather_step.glsl

```
SSBO:
  binding 0:  CellBuffer (readonly)

Image:
  binding 17: humidityIn (r32f, readonly)
  binding 18: humidityOut (r32f, writeonly)
  binding 11: tempIn (r32f, readonly)

Uniforms:
  gridSize (uvec2)
  dt (float)
  humidityDiffuseRate (float)
  evaporationRate (float)
  condensationRate (float)
  saturationThreshold (float)
  rainSpeed (float)
  windAdvectStrength (float)
  windVector (vec2)
```

## Configuration

### CLI Flags (main.py)

```python
--enable-weather           (default: False)
--humidity-diffuse-rate    (default: 0.4)
--evaporation-rate          (default: 0.1)
--condensation-rate         (default: 0.3)
--saturation-threshold      (default: 100.0)
--rain-speed                (default: 2.0)
```

### Config Fields (core/config.py)

```python
enable_weather: bool = False
humidity_diffuse_rate: float = 0.4
evaporation_rate: float = 0.1
condensation_rate: float = 0.3
saturation_threshold: float = 100.0
rain_speed: float = 2.0
```

### Wind Control

Wind is controlled via simulation engine API:

```python
engine.adjust_wind(dx, dy)  # Adjust wind vector
engine.toggle_wind()        # Enable/disable wind
```

Wind state stored in `simulation/state.py:WindState`.

## Debug Visualization

Press `Tab` to cycle debug views. View 5 shows humidity field:

- **Visualization**: Dark gray → Cyan heatmap
- **Range**: 0-200 humidity units
- **Blend**: Overlay on material color

Inspector panel (press `I`) shows humidity value for probed cell.

## Examples

### Clear Sky (Low Humidity)

```yaml
# Low saturation threshold, fast evaporation
saturationThreshold: 50.0
evaporationRate: 0.2
condensationRate: 0.1
```

Rapid evaporation, slow condensation, low rain.

### Rainy (High Humidity)

```yaml
# High saturation threshold, slow evaporation
saturationThreshold: 150.0
evaporationRate: 0.05
condensationRate: 0.5
rainSpeed: 3.0
```

Slow evaporation, rapid condensation, fast rain.

### Windy

```yaml
windAdvectStrength: 0.8
windVector: [1.0, 0.0]  # Strong east wind
```

Strong wind pushes humidity rapidly.

## Known Limitations

1. No conductivity boost for electricity (planned for v7)
2. No transpiration from bio materials (planned for v7)
3. No humidity effect on bio decay (planned for v7)
4. Wind texture not bound (uses uniform instead)
5. Rain droplet spawning not in weather pass (handled by state)
6. No cloud formation mechanics
7. No lightning coupling with electricity system

## Future Work (v7)

1. Implement rain conductivity boost for electricity
2. Add transpiration from bio materials to humidity
3. Add humidity-dependent bio decay rate
4. Bind wind texture for per-pixel wind field
5. Implement cloud formation and density
6. Add lightning coupling with electricity arc system
7. Implement snow mechanics (temperature-dependent rain)
8. Add fog/mist effects (high humidity near ground)
