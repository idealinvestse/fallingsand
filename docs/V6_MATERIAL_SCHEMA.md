# v6 Material Schema

## Overview

Structured YAML-based material definitions with grouped properties. The v6 schema organizes material properties into logical groups (display, physical, thermal, electrical, chemistry, biology, explosion) for better maintainability and validation.

## Schema Version

```yaml
schema_version: 6
```

Required field at the top of materials_v6.yaml. Loader validates this is >= 6.

## Property Groups

### DisplayProps

Visual appearance properties.

```python
@dataclass(slots=True)
class DisplayProps:
    color: tuple[int, int, int] = (255, 255, 255)
    emissive: float = 0.0
```

- **color**: RGB tuple (0-255) or hex string (e.g., "#FF0000")
- **emissive**: Emissive glow strength (0.0 - 1.0)
  - Used in render shader for blackbody glow
  - Higher values = brighter glow at temperature

### PhysicalProps

Physical simulation properties.

```python
@dataclass(slots=True)
class PhysicalProps:
    category: str = "solid"
    state_family: str = "solid"
    density: float = 1.0
    viscosity: float = 0.0
    cohesion: float = 0.0
    restitution: float = 0.0
    surface_tension: float = 0.0
    solubility: float = 0.0
    turbulence: float = 0.0
    wet_dry: float = 0.0
```

- **category**: Material category (gas, powder, liquid, solid)
  - Maps to CATEGORY_MAP integer (0-3)
  - Used for density sorting and collision

- **state_family**: State family (gas, liquid, solid, plasma, powder, paste, gel, foam, emulsion, aerosol)
  - Maps to STATE_FAMILY_MAP integer (0-9)
  - Used for advanced state transitions

- **density**: Mass density (kg/m³ equivalent)
  - Used for density sorting in liquids/powders
  - Negative for rising gases

- **viscosity**: Flow resistance (0.0 - 1.0)
  - Used in liquid_step shader
  - Higher = slower flow

- **cohesion**: Particle attraction (0.0 - 1.0)
  - Used for clumping behavior
  - Reserved for future use

- **restitution**: Bounce coefficient (0.0 - 1.0)
  - Used in collision response
  - Reserved for future use

- **surface_tension**: Surface tension (0.0 - 1.0)
  - Used in liquid simulation
  - Affects droplet formation

- **solubility**: Solubility in water (0.0 - 1.0)
  - Reserved for future dissolution mechanics

- **turbulence**: Turbulence factor (0.0 - 1.0)
  - Used in render shader for velocity visualization
  - Higher = more visible motion

- **wet_dry**: Wet/dry behavior (0.0 - 1.0)
  - Used in wet-dry physics
  - Affects capillary action

### ThermalProps

Thermal simulation properties.

```python
@dataclass(slots=True)
class ThermalProps:
    conductivity: float = 0.0
    heat_capacity: float = 1.0
    cooling_rate: float = 0.0
    melting_point: float = 0.0
    boiling_point: float = 0.0
    phase_high_material: str = ""
    phase_high_temp: float = 255.0
    phase_low_material: str = ""
    phase_low_temp: float = 0.0
    default_flame_temp: float = 0.0
    default_flame_life: int = 0
```

- **conductivity**: Thermal conductivity (0.0 - 1.0)
  - Used in heat diffusion shader
  - Higher = faster heat transfer

- **heat_capacity**: Specific heat capacity (default 1.0)
  - Affects temperature change rate
  - Higher = slower temperature change

- **cooling_rate**: Passive cooling rate
  - Used in heat shader
  - Materials cool toward ambient

- **melting_point**: Phase change temperature (solid → liquid)
  - Used in state shader for melting
  - Triggers phase_high transition

- **boiling_point**: Phase change temperature (liquid → gas)
  - Used in state shader for boiling
  - Triggers phase_high transition

- **phase_high_material**: Material to transform to at high temperature
  - String reference resolved to ID
  - Example: ice → water at melting_point

- **phase_high_temp**: Temperature threshold for high-phase transition
  - Default 255.0

- **phase_low_material**: Material to transform to at low temperature
  - String reference resolved to ID
  - Example: steam → water at condensation point

- **phase_low_temp**: Temperature threshold for low-phase transition
  - Default 0.0

- **default_flame_temp**: Ignition temperature
  - Used in combustion mechanics
  - When material burns, creates flame at this temperature

- **default_flame_life**: Flame duration in frames
  - Used in combustion mechanics
  - How long flame persists

### ElectricalProps

Electrical simulation properties.

```python
@dataclass(slots=True)
class ElectricalProps:
    conductivity: float = 0.0
    capacitance: float = 0.0
    breakdown_voltage: float = 0.0
    arc_emission: float = 0.0
```

- **conductivity**: Electrical conductivity (0.0 - 1.0)
  - Used in electricity_step.glsl
  - 0.0 = insulator, 1.0 = superconductor
  - Mapped to rule buffer slot 13

- **capacitance**: Charge storage capacity
  - Reserved for future use
  - Mapped to rule buffer slot 14

- **breakdown_voltage**: Arc threshold
  - Used in electricity_arc.glsl
  - When |charge| > breakdown_voltage, arc occurs
  - Mapped to rule buffer slot 15

- **arc_emission**: Light emission on arc
  - Reserved for future visual effects
  - Mapped to rule buffer slot 16

### ChemistryProps

Chemical reaction properties.

```python
@dataclass(slots=True)
class ChemistryProps:
    flammability: float = 0.0
    burn_to: str = ""
    oxygen_requirement: float = 0.0
    oxygen_yield: float = 0.0
    reactions: list[ReactionDef] = field(default_factory=list)
```

- **flammability**: Flammability (0.0 - 1.0)
  - Used in state shader for combustion
  - Higher = more likely to burn

- **burn_to**: Material to transform to when burned
  - String reference resolved to ID
  - Example: wood → ash, oil → fire

- **oxygen_requirement**: Oxygen consumption (0.0 - 1.0)
  - Used in thermobaric explosions
  - How much oxygen consumed per burn

- **oxygen_yield**: Oxygen production (0.0 - 1.0)
  - Reserved for future use
  - Materials that release oxygen when burning

- **reactions**: List of reaction definitions (max 3)
  - Each reaction has partner, product_self, product_neighbor, probability, temp_threshold
  - Used in state shader for chemical reactions
  - Mapped to rule buffer slots 26-40

### ReactionDef

Single chemical reaction definition.

```python
@dataclass(slots=True)
class ReactionDef:
    partner: str = ""
    product_self: str = ""
    product_neighbor: str = ""
    probability: float = 0.0
    temp_threshold: float = 0.0
```

- **partner**: Material to react with (string reference)
- **product_self**: Material this cell transforms to (string reference)
- **product_neighbor**: Material neighbor transforms to (string reference)
- **probability**: Reaction probability (0.0 - 1.0)
- **temp_threshold**: Temperature threshold for reaction

### BiologyProps

Biological/ecological properties.

```python
@dataclass(slots=True)
class BiologyProps:
    biomass: float = 0.0
    growth_rate: float = 0.0
    decay_rate: float = 0.0
    nutrient_value: float = 0.0
    predator_mask: list[str] = field(default_factory=list)
```

- **biomass**: Organic content (0.0 - 1.0)
  - Used for combustion calculations
  - Higher biomass = more fuel value

- **growth_rate**: Growth speed multiplier
  - Used in biology_step.glsl
  - Affects nutrient/moisture consumption

- **decay_rate**: Decay speed multiplier
  - Used in biology_step.glsl
  - Determines how quickly bio dies without resources

- **nutrient_value**: Nutrient value when decayed
  - Returned to soil as nutrients
  - Used in biology_step.glsl

- **predator_mask**: List of predator material names
  - Reserved for future predator/prey system
  - Not currently used in shaders

### ExplosionProps

Explosive properties.

```python
@dataclass(slots=True)
class ExplosionProps:
    power: float = 0.0
    detonation_temp: float = 255.0
    blast_radius: int = 0
    blast_duration: int = 0
    fragment_type: str = ""
    shockwave_speed: float = 0.0
```

- **power**: Explosion power
  - Used in explosion mechanics
  - Affects force and radius

- **detonation_temp**: Trigger temperature
  - Material explodes at this temperature
  - Default 255.0

- **blast_radius**: Explosion radius
  - Used in explosion mechanics
  - Cells within radius affected

- **blast_duration**: Explosion duration
  - How long explosion effects persist

- **fragment_type**: Fragment material
  - String reference resolved to ID
  - Material spawned on explosion

- **shockwave_speed**: Shockwave velocity
  - Used in acoustic simulation
  - Speed of pressure wave

## YAML Format

```yaml
schema_version: 6

materials:
  0:
    name: air
    display:
      color: [0, 0, 0]
      emissive: 0.0
    physical:
      category: gas
      state_family: gas
      density: 0.12
      viscosity: 0.0
      cohesion: 0.0
      restitution: 0.0
      surface_tension: 0.0
      solubility: 0.0
      turbulence: 0.0
      wet_dry: 0.0
    thermal:
      conductivity: 0.0
      heat_capacity: 1.0
      cooling_rate: 0.0
      melting_point: 0.0
      boiling_point: 0.0
      phase_high:
        material: steam
        temp: 140.0
      phase_low:
        material: ice
        temp: 48.0
      default_flame_temp: 0.0
      default_flame_life: 0
    electrical:
      conductivity: 0.0
      capacitance: 0.0
      breakdown_voltage: 0.0
      arc_emission: 0.0
    chemistry:
      flammability: 0.0
      oxygen_requirement: 0.0
      oxygen_yield: 0.0
      reactions: []
    biology:
      biomass: 0.0
      growth_rate: 0.0
      decay_rate: 0.0
      nutrient_value: 0.0
      predator_mask: []
    explosion:
      power: 0.0
      detonation_temp: 255.0
      blast_radius: 0
      blast_duration: 0
      shockwave_speed: 0.0
```

## Reference Resolution

String-based references are resolved to material IDs after loading:

1. **Phase materials**: phase_high.material, phase_low.material
2. **Burn target**: burn_to
3. **Reaction partners/products**: partner, product_self, product_neighbor
4. **Fragment type**: fragment_type

Resolution happens in `_resolve_references()` (material_schema.py lines 280-304):

```python
def _resolve_references(materials: dict[int, MaterialDefV6], name_to_id: dict[str, int]) -> None:
    for mat in materials.values():
        # Resolve phase materials
        if t.phase_high_material and t.phase_high_material in name_to_id:
            object.__setattr__(t, 'phase_high_material', name_to_id[t.phase_high_material])
        # Resolve burn_to
        if c.burn_to and c.burn_to in name_to_id:
            object.__setattr__(c, 'burn_to', name_to_id[c.burn_to])
        # Resolve reaction references
        for rx in c.reactions:
            if rx.partner and rx.partner in name_to_id:
                object.__setattr__(rx, 'partner', name_to_id[rx.partner])
            # ... similar for product_self, product_neighbor
        # Resolve fragment_type
        if e.fragment_type and e.fragment_type in name_to_id:
            object.__setattr__(e, 'fragment_type', name_to_id[e.fragment_type])
```

## Validation

`validate_v6_materials()` returns list of warning strings:

- Category in CATEGORY_MAP
- State family in STATE_FAMILY_MAP
- Viscosity in [0, 1]
- Surface tension in [0, 1]
- Flammability in [0, 1]
- Electrical conductivity in [0, 1]
- Density > 0 for non-gas materials

## Legacy Adapter

`to_legacy_defs()` converts MaterialDefV6 to flat dict for rule buffer:

- Maps to existing rule buffer layout (RULE_STRIDE = 49)
- Resolves string references to integer IDs
- Packs properties into legacy field names
- Used for backward compatibility with existing shaders

## Loading

```python
from simulation.material_schema import load_materials_v6

materials = load_materials_v6("simulation/materials_v6.yaml")
# Returns: dict[int, MaterialDefV6]
```

Loader:
1. Validates schema_version >= 6
2. Parses YAML
3. Creates MaterialDefV6 objects
4. Resolves string references
5. Returns dict mapping ID to MaterialDefV6

## Rule Buffer Layout

Current RULE_STRIDE is 49. Layout groups:

- Slots 0-17: Base visual, density, category, thermal, phase, electrical, burn, viscosity, turbulence, wet/dry
- Slots 18-25: Heat capacity, phase points, surface tension, solubility, cohesion, restitution, state family
- Slots 26-40: Three reaction slots (5 slots each)
- Slots 41-46: Explosive properties
- Slots 47-48: Oxygen/combustion properties

Keep synchronized:
- core/constants.py (RULE_STRIDE)
- simulation/materials.py (rule buffer construction)
- shaders/common.glsl (rule buffer unpacking)
- simulation/material_schema.py (to_legacy_defs)

## Migration from v5

v5 used flat YAML structure. v6 adds grouping:

1. Create v6 YAML with grouped properties
2. Set schema_version: 6
3. Use to_legacy_defs() for compatibility
4. Update material loading to use load_materials_v6()

## Examples

### Electrical Material (Copper)

```yaml
10:
  name: copper
  display:
    color: [184, 115, 51]
    emissive: 0.0
  physical:
    category: solid
    state_family: solid
    density: 8.9
    viscosity: 0.0
    cohesion: 0.0
    restitution: 0.1
    surface_tension: 0.0
    solubility: 0.0
    turbulence: 0.0
    wet_dry: 0.0
  thermal:
    conductivity: 0.4
    heat_capacity: 0.385
    cooling_rate: 0.05
    melting_point: 1085.0
    boiling_point: 2562.0
    phase_high:
      material: lava
      temp: 1200.0
  electrical:
    conductivity: 0.95
    capacitance: 0.01
    breakdown_voltage: 300.0
    arc_emission: 0.8
  chemistry:
    flammability: 0.0
    oxygen_requirement: 0.0
    oxygen_yield: 0.0
  biology:
    biomass: 0.0
    growth_rate: 0.0
    decay_rate: 0.0
    nutrient_value: 0.0
  explosion:
    power: 0.0
    detonation_temp: 255.0
    blast_radius: 0
    blast_duration: 0
    shockwave_speed: 0.0
```

### Biological Material (Plant)

```yaml
12:
  name: plant
  display:
    color: [34, 139, 34]
    emissive: 0.0
  physical:
    category: solid
    state_family: solid
    density: 0.5
    viscosity: 0.0
    cohesion: 0.3
    restitution: 0.0
    surface_tension: 0.0
    solubility: 0.0
    turbulence: 0.0
    wet_dry: 0.8
  thermal:
    conductivity: 0.02
    heat_capacity: 0.8
    cooling_rate: 0.01
    melting_point: 0.0
    boiling_point: 0.0
  electrical:
    conductivity: 0.1
    capacitance: 0.0
    breakdown_voltage: 0.0
    arc_emission: 0.0
  chemistry:
    flammability: 0.8
    burn_to: fire
    oxygen_requirement: 0.2
    oxygen_yield: 0.0
  biology:
    biomass: 0.8
    growth_rate: 0.15
    decay_rate: 0.03
    nutrient_value: 0.5
    predator_mask: []
  explosion:
    power: 0.0
    detonation_temp: 255.0
    blast_radius: 0
    blast_duration: 0
    shockwave_speed: 0.0
```

## Known Limitations

1. BiologyProps predator_mask not used
2. ElectricalProps capacitance not used
3. ElectricalProps arc_emission not used
4. ChemistryProps oxygen_yield not used
5. PhysicalProps cohesion, restitution, solubility not fully utilized
6. No validation for reaction probability ranges
7. No validation for temperature thresholds

## Future Work (v7)

1. Implement predator/prey system using predator_mask
2. Use capacitance for charge storage mechanics
3. Use arc_emission for visual lightning effects
4. Use oxygen_yield for combustion byproducts
5. Implement cohesion for clumping behavior
6. Implement restitution for bouncing
7. Implement solubility for dissolution
8. Add validation for all parameter ranges
9. Add material inheritance/templates
10. Add material tags for categorization
