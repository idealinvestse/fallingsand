# Biology/Ecology System

## Overview

Nutrient cycling, moisture dynamics, and bio-material growth/decay simulation. The biology system models ecological processes including nutrient diffusion through soil/water, moisture evaporation and consumption, and biological growth/decay cycles.

## Algorithm

### Nutrient Field

Nutrients diffuse through permeable materials and are consumed by biological materials:

1. **Diffusion**: 4-neighbor stencil weighted by material type:
   - Soil (dirt, mud) and water: weight = 1.0
   - Bio materials (plant, slime, blood, virus): weight = 0.3
   - Other materials: weight = 0.0 (impermeable)
   - Update: `nut += (nutAvg - nut) * nutrientDiffuseRate * dt`

2. **Consumption**: Bio materials consume nutrients for growth:
   - Condition: `nut > 0.1 AND moist > 0.1 AND temp > 100.0`
   - Consumption: `nut -= nutrientConsumeRate * growthRate * dt`

3. **Regeneration**: Dirt/soil passively regenerates nutrients:
   - Rate: `nut += dirtNutrientRegen * dt`

4. **Decay**: Dead bio materials return nutrients to soil:
   - Decay: `nut += decayRate * dt * 0.5` (50% of decay mass becomes nutrients)

### Moisture Field

Moisture diffuses through all materials and is affected by temperature:

1. **Diffusion**: 4-neighbor stencil with uniform weighting:
   - Update: `moist += (moistAvg - moist) * moistureDiffuseRate * dt`

2. **Evaporation**: Heat-driven moisture loss:
   - Rate: `evap = moist * moistureEvapRate * max(0.0, temp - 96.0) * 0.01 * dt`
   - Update: `moist = max(0.0, moist - evap)`

3. **Water Contribution**: Water cells add moisture:
   - Rate: `moist = min(1000.0, moist + waterMoistureBoost * dt)`

4. **Consumption**: Bio materials consume moisture for growth:
   - Condition: `nut > 0.1 AND moist > 0.1 AND temp > 100.0`
   - Consumption: `moist -= moistureConsumeRate * growthRate * dt`

### Growth/Decay Rules

Bio materials follow a growth/decay cycle:

1. **Growth Condition**: `nut > 0.1 AND moist > 0.1 AND temp > 100.0`
2. **Growth Rate**: Material-specific (plant: 0.15, slime: 0.2, blood: 0.1, virus: 0.25)
3. **Decay Condition**: Not meeting growth conditions
4. **Decay Rate**: Material-specific (plant: 0.05, slime: 0.1, blood: 0.08, virus: 0.15)

## v7.0 New Material Biological Properties

### Magnetic Materials
Magnetic materials (magnet, magnet_south) have no biological properties (`biomass: 0.0`):
- Do not consume or produce nutrients
- Do not consume or produce moisture
- Do not grow or decay
- Act as inert solids in biological simulations

### Plasma Materials
Plasma materials (plasma, lightning_plasma) have no biological properties but interact with biology:
- **Sterilization effect**: Plasma's extreme temperature (>300°C) can sterilize nearby biological materials
- **Ignition**: Plasma instantly ignites combustible bio materials (plant, wood)
- **No nutrient/moisture interaction**: Plasma does not consume or produce nutrients or moisture

### Glass Materials
Glass materials (glass, obsidian) have no biological properties:
- Do not consume or produce nutrients
- Do not consume or produce moisture
- Do not grow or decay
- Act as impermeable barriers in biological simulations
- Glass shattering can create pathways for biological spread

### Enhanced Materials
**thermite_enhanced**: No biological properties, but extreme heat affects nearby biology
**acid_glass_corrosive**: No biological properties, but may interact with bio materials in future

## Material Properties

### BiologyProps (simulation/material_schema.py)

```python
@dataclass(slots=True)
class BiologyProps:
    biomass: float = 0.0
    growth_rate: float = 0.0
    decay_rate: float = 0.0
    nutrient_value: float = 0.0
```

- **biomass**: 0.0 (inert) to 1.0 (fully biological). Determines if material participates in biological cycles.
- **growth_rate**: Growth speed when conditions are met.
- **decay_rate**: Decay speed when conditions are not met.
- **nutrient_value**: Nutrient content when decayed (returned to soil).

1. **Growth Conditions**: All of the following must be true:
   - Nutrient > 0.1
   - Moisture > 0.1
   - Temperature > 100.0

2. **Growth**: When conditions met:
   - Consume nutrients: `nut -= nutrientConsumeRate * growthRate * dt`
   - Consume moisture: `moist -= moistureConsumeRate * growthRate * dt`
   - Cell spreading handled by state pass (not biology pass)

3. **Decay**: When conditions not met:
   - Bio material dies (cell type changes handled by state pass)
   - Return nutrients: `nut += decayRate * dt * 0.5`
   - Decay rate determines how quickly bio dies without resources

## Material Properties

### BiologyProps (simulation/material_schema.py)

- **biomass** (float): Organic content, range [0.0, 1.0]
  - Used for combustion calculations
  - Higher biomass = more fuel value

- **growth_rate** (float): Growth speed multiplier
  - Typical values: 0.05 (slow) to 0.3 (fast)
  - Affects nutrient/moisture consumption rate

- **decay_rate** (float): Decay speed multiplier
  - Typical values: 0.01 (slow decay) to 0.1 (rapid decay)
  - Determines how quickly bio dies without resources

- **nutrient_value** (float): Nutrient value when decayed
  - Returned to soil as nutrients on decay
  - Typical values: 0.0 to 1.0

- **predator_mask** (list[str]): List of predator material names
  - Reserved for future predator/prey system
  - Not currently used in shaders

## Uniform Parameters

### biology_step.glsl

- **dt** (float): Integration timestep from adaptive substepping
- **nutrientDiffuseRate** (float): Diffusion speed for nutrients (default 0.5)
- **moistureDiffuseRate** (float): Diffusion speed for moisture (default 0.3)
- **moistureEvapRate** (float): Evaporation rate per heat unit (default 0.02)
- **growthRate** (float): Bio growth speed multiplier (default 0.1)
- **decayRate** (float): Bio decay speed multiplier (default 0.05)
- **nutrientConsumeRate** (float): Nutrients consumed per growth (default 0.2)
- **moistureConsumeRate** (float): Moisture consumed per growth (default 0.15)
- **waterMoistureBoost** (float): Moisture added by water cells (default 5.0)
- **dirtNutrientRegen** (float): Passive nutrient regeneration in dirt (default 0.01)

## Bio Materials

### Plant (T_PLANT)
- Solid bio material
- Requires nutrients, moisture, and warmth to grow
- Moderate growth rate, slow decay
- Used for vegetation simulation

### Slime (T_SLIME)
- Liquid bio material
- Spreads through diffusion
- High growth rate, moderate decay
- Used for organic fluid simulation

### Blood (T_BLOOD)
- Liquid bio material
- Decay-driven (no growth)
- Used for gore effects

### Virus (T_VIRUS)
- Bio material (future: infectious behavior)
- Currently behaves like other bio materials
- Planned: infection mechanics

## Performance

- **Typical Cost**: ~1.0ms @ 1024×1024 grid
- **Optional Pass**: Can be skipped via `config.enable_biology = False`
- **Memory**: 4 × r32f textures (nutrient_a/b, moisture_a/b) = 16MB @ 1024×1024
- **Workgroups**: 64×64 = 4096 workgroups @ 1024×1024

## Interactions

### Current Reads/Writes

**biology_step.glsl:**
- Reads: cells (SSBO), rules (SSBO), nutrient_in (r32f), moisture_in (r32f), temp_in (r32f)
- Writes: nutrient_out (r32f), moisture_out (r32f)

### Cross-System Coupling (v7 Target)

1. **Electricity → Biology**: Electric fields affect growth
   - Planned: Moderate fields (10-100 charge) stimulate growth 20%
   - Planned: Strong fields (>500 charge) inhibit growth 50%
   - Implementation: Read charge field in biology_step.glsl

2. **Biology → Weather**: Transpiration adds humidity
   - Planned: Bio materials with moisture transpire to atmosphere
   - Implementation: Write to humidity field in biology_step.glsl

3. **Weather → Biology**: Humidity affects decay rate
   - Planned: High humidity reduces decay rate
   - Implementation: Read humidity field in biology_step.glsl

## Shader Bindings

### biology_step.glsl

```
SSBO:
  binding 0:  CellBuffer (readonly)
  binding 2:  RuleBuffer (readonly)

Image:
  binding 13: nutrientIn (r32f, readonly)
  binding 14: nutrientOut (r32f, writeonly)
  binding 15: moistureIn (r32f, readonly)
  binding 16: moistureOut (r32f, writeonly)
  binding 11: tempIn (r32f, readonly)

Uniforms:
  gridSize (uvec2)
  ruleStride (uint)
  dt (float)
  nutrientDiffuseRate (float)
  moistureDiffuseRate (float)
  moistureEvapRate (float)
  growthRate (float)
  decayRate (float)
  nutrientConsumeRate (float)
  moistureConsumeRate (float)
  waterMoistureBoost (float)
  dirtNutrientRegen (float)
```

## Configuration

### CLI Flags (main.py)

```python
--enable-biology          (default: False)
--nutrient-diffuse-rate   (default: 0.5)
--moisture-diffuse-rate   (default: 0.3)
--growth-rate             (default: 0.1)
--decay-rate              (default: 0.05)
```

### Config Fields (core/config.py)

```python
enable_biology: bool = False
nutrient_diffuse_rate: float = 0.5
moisture_diffuse_rate: float = 0.3
growth_rate: float = 0.1
decay_rate: float = 0.05
```

## Debug Visualization

Press `Tab` to cycle debug views:

- View 3: Nutrient field (brown → green heatmap, 0-200 units)
- View 4: Moisture field (tan → blue heatmap, 0-200 units)

Inspector panel (press `I`) shows nutrient and moisture values for probed cell.

## Examples

### Plant

```yaml
plant:
  biology:
    biomass: 0.8
    growth_rate: 0.15
    decay_rate: 0.03
    nutrient_value: 0.5
    predator_mask: []
```

Moderate growth, slow decay, returns nutrients on death.

### Slime

```yaml
slime:
  biology:
    biomass: 0.6
    growth_rate: 0.25
    decay_rate: 0.08
    nutrient_value: 0.3
    predator_mask: []
```

Fast growth, moderate decay, lower nutrient value.

## Known Limitations

1. No electric field growth modulation (planned for v7)
2. No transpiration to humidity field (planned for v7)
3. No humidity decay rate modification (planned for v7)
4. Predator/prey system not implemented
5. Growth/decay handled by state pass, not biology pass
6. No age/lifecycle mechanics

## Future Work (v7)

1. Implement electric field growth stimulation/inhibition
2. Add transpiration from bio materials to humidity
3. Add humidity-dependent decay rate
4. Implement predator/prey interactions
5. Add age/lifecycle to bio materials
6. Implement seed/spawning mechanics
7. Add seasonal effects (temperature-dependent growth rates)
