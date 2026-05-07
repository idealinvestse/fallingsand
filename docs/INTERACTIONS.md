# System Interactions Reference (v6.1)

This document describes the bidirectional coupling between simulation subsystems introduced in v6.1 Deep System Interactions.

## Bidirectional Coupling Matrix

| From \ To | Electricity | Biology | Weather | Fluid |
|-----------|-------------|---------|---------|-------|
| Electricity | - | Charge → growth/decay | Rain washes charge | Moisture → conductivity |
| Biology | - | - | Transpiration | Nutrient consumption |
| Weather | - | - | - | Humidity → condensation |
| Fluid | Charge transport | Nutrient advection | Temperature → evaporation | - |

## Detailed Interactions

### Electricity ↔ Fluid

**Mechanism**: Moisture-based conductivity enhancement and electrolysis

**Shader**: `electricity_step.glsl`

**Formula**:
```
effective_conductivity = base_conductivity × (1.0 + moisture × electricity_moisture_boost)
propagation_rate = 4.0 × (1.0 + moisture × 0.5)
```

**Behavior**:
- Wet conductors (high moisture) have significantly higher conductivity
- Charge propagates faster through wet materials
- Charged liquid cells transport charge downstream via velocity field (electrolysis)

**Configuration**:
```python
config.electricity_moisture_boost = 2.0  # Conductivity multiplier
config.electrolysis_strength = 0.3         # Charge transport rate
```

**Pass Order**: biology (writes moisture) → electricity (reads moisture)

---

### Electricity ↔ Biology

**Mechanism**: Electro-stimulation and electrocution damage

**Shader**: `biology_step.glsl`

**Formula**:
```
# Moderate charge (10-100): Electro-stimulation
if charge_stim_low < |charge| < charge_stim_high:
    growth_modifier = 1.0 + clamp(charge × 0.3, 0.0, 1.5)

# High charge (>500): Electrocution damage
if |charge| > charge_damage_threshold:
    damage = (|charge| - threshold) / threshold
    growth_modifier = max(0.2, 1.0 - damage)
    # Additional nutrient/moisture release from damaged cells
```

**Behavior**:
- Moderate electric fields (10-100 charge) stimulate biological growth up to 150%
- Strong electric fields (>500 charge) cause damage, reducing growth to minimum 20%
- Damaged cells release extra nutrients and moisture (cell rupture)

**Configuration**:
```python
config.biology_electro_stim = 0.3         # Growth boost multiplier
config.charge_damage_threshold = 500.0    # Damage threshold
config.charge_stim_range_low = 10.0       # Stimulation range lower bound
config.charge_stim_range_high = 100.0     # Stimulation range upper bound
```

**Pass Order**: electricity (writes charge) → biology (reads charge)

---

### Weather ↔ Fluid

**Mechanism**: Condensation on solid surfaces and rain charge washing

**Shader**: `weather_step.glsl`

**Condensation Formula**:
```
condensation_chance = clamp((humidity - 0.6 × saturation) × 2.0 × temp_factor, 0.0, 0.15)
temp_factor = 1.0 - smoothstep(80.0, 120.0, temperature)
```

**Behavior**:
- High humidity (>60% saturation) on cold solid surfaces causes condensation
- Colder temperatures increase condensation probability
- Condensed humidity becomes local moisture (picked up by biology_step)
- Rain washes charge from solid surfaces (visual effect only in v6.1)

**Configuration**:
```python
config.condensation_temp_boost = 2.0       # Temperature effect on condensation
config.rain_charge_wash_rate = 0.1         # Charge dissipation from rain
config.rain_moisture_boost = 50.0         # Moisture added by rain
```

**Pass Order**: weather (writes humidity) → biology (reads moisture from condensation)

---

### Biology ↔ Fluid

**Mechanism**: Nutrient advection via fluid flow

**Shader**: `liquid_step.glsl`

**Formula**:
```
nutrient_new = mix(nutrient_old, nutrient_upwind, min(velocity_magnitude × 0.5, 0.8))
```

**Behavior**:
- Nutrients are transported by liquid velocity (semi-Lagrangian advection)
- Water cells gain nutrients from upstream flow (rivers carry sediment)
- Advection strength scales with velocity magnitude (up to 80%)
- Only active in liquid cells or cells adjacent to water

**Configuration**:
- No dedicated config parameters; uses velocity field directly

**Pass Order**: liquid_step (writes nutrient_out) → biology (reads nutrient_in)

---

### Temperature Coupling (All Systems)

**Mechanism**: Temperature affects all interaction rates

**Shader**: `biology_step.glsl`, `weather_step.glsl`, `electricity_arc.glsl`

**Formula**:
```
# Biology growth temperature factor
growth_multiplier *= smoothstep(50.0, 150.0, temperature) × temp_effect_multiplier

# Weather evaporation temperature coupling
evaporation_rate *= temperature_factor × evap_temp_multiplier

# Electricity arc temperature effect
# (implicit via material properties and arc energy)
```

**Behavior**:
- Biological growth optimal at 50-150 temperature units
- Evaporation rate increases with temperature
- Temperature affects arc energy and conductivity

**Configuration**:
```python
config.temp_effect_multiplier = 1.0        # Global temperature coupling strength
config.evap_temp_multiplier = 1.0          # Weather-specific evaporation multiplier
```

---

## Pass Order Dependencies

The current pass order naturally supports v6.1 interactions:

```
1. liquid_step (nutrient advection)
2. heat
3. vorticity
4. velocity_advect
5. force
6. divergence
7. pressure
8. project
9. electricity (reads moisture from biology)
10. electricity_arc (reads moisture)
11. biology (reads charge from electricity)
12. weather (reads moisture, charge)
13. acoustic_pressure
14. acoustic_velocity
15. advect
```

**Key Dependencies**:
- biology must run before electricity (for moisture)
- electricity must run before biology (for charge)
- weather runs after biology (reads moisture)
- liquid_step runs before biology (nutrient advection)

---

## Texture Binding Summary

| Texture | Binding | Written By | Read By (v6.1) |
|---------|---------|------------|----------------|
| moisture_in | 15 | biology_step | electricity_step, electricity_arc, weather_step |
| charge_in | 9 | electricity_step | biology_step, weather_step |
| nutrient_in | 13 | biology_step, liquid_step | biology_step, liquid_step |
| nutrient_out | 14 | biology_step, liquid_step | biology_step, liquid_step |
| velocity_in | 3 | velocity_advect | electricity_step, liquid_step |

---

## Performance Considerations

All v6.1 interactions add approximately **1.0%** GPU overhead on 1024×1024 grids (5.5% total vs 4.5% baseline).

**Optimization Notes**:
- Moisture reads are cache-friendly (spatial coherence)
- Nutrient advection uses semi-Lagrangian scheme (stable, efficient)
- No new textures allocated (reuses existing double-buffered set)
- All interactions are optional via `config.enable_deep_interactions`

---

## Tuning Guide

### Making Wet Conductors More Effective
```python
config.electricity_moisture_boost = 4.0  # Increase from 2.0
config.electrolysis_strength = 0.5      # Increase charge transport
```

### Increasing Electro-Stimulation Effect
```python
config.biology_electro_stim = 0.5       # Increase from 0.3
config.charge_stim_range_high = 200.0   # Widen stimulation range
```

### More Aggressive Condensation
```python
config.condensation_temp_boost = 3.0     # Increase from 2.0
```

### Stronger Nutrient Transport
- Modify `liquid_step.glsl` advection strength:
  ```glsl
  float advectionStrength = clamp(length(vel) * 0.8, 0.0, 0.95);  // Increase from 0.5, 0.8
  ```

---

## Future Extensions

Potential v6.2 additions:
- Direct charge writing in weather_step (actual rain charge wash, not just visual)
- Moisture feedback to electricity_step (wet arc writes moisture to steam)
- Nutrient consumption by weather (atmospheric nutrients)
- Temperature-based material property modulation
- Cross-system reaction chains (e.g., electricity + biology → new material)
