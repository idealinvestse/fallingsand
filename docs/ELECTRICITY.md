# Electricity System

## Overview

Charge propagation through conductive materials using harmonic mean conductivity weighting. The electricity system consists of two passes: `electricity_step.glsl` for charge diffusion and `electricity_arc.glsl` for arc breakdown effects.

## Algorithm

### Charge Propagation (electricity_step.glsl)

The electricity pass uses a 4-neighbor stencil diffusion algorithm:

1. **Conductivity Check**: Only cells with `conductivity > 0` propagate charge. Insulators (conductivity ≈ 0) store charge frozen.
2. **Flux Calculation**: Flux proportional to conductivity-weighted charge gradient using harmonic mean:
   ```
   wL = (r.cond * cL) / max(r.cond + cL, 1e-6) * 2.0
   wR = (r.cond * cR) / max(r.cond + cR, 1e-6) * 2.0
   wD = (r.cond * cD) / max(r.cond + cD, 1e-6) * 2.0
   wU = (r.cond * cU) / max(r.cond + cU, 1e-6) * 2.0
   flux = wL*(qL - q) + wR*(qR - q) + wD*(qD - q) + wU*(qU - q)
   ```
3. **Explicit Integration**: 
   ```
   rate = 4.0  # heuristic diffusion speed
   qNew = q + clamp(flux * rate * dt, -maxCharge, maxCharge)
   ```
4. **Decay**: Optional exponential decay toward zero:
   ```
   qNew = mix(qNew, 0.0, clamp(chargeDecay * dt, 0.0, 1.0))
   ```
5. **Clamping**: Hard cap to prevent runaway accumulation:
   ```
   qNew = clamp(qNew, -maxCharge, maxCharge)
   ```

### Arc Breakdown (electricity_arc.glsl)

Arc breakdown occurs when charge exceeds the material's breakdown threshold:

1. **Trigger Condition**: `abs(q) > breakdownThreshold AND conductivity > 0.3`
2. **Effects on Breakdown**:
   - Charge discharged to zero: `q = 0.0`
   - Temperature spike: `temp += arcTempDelta`
   - Pressure pulse: writes to divergence texture with `arcPressurePulse`
3. **No Arc**: Preserves divergence by writing zero

## Material Properties

### ElectricalProps (simulation/material_schema.py)

- **conductivity** (float): Electrical conductivity, range [0.0, 1.0]
  - 0.0 = perfect insulator (charge frozen)
  - 1.0 = superconductor (maximum charge flow)
  - Used in harmonic mean calculation for series resistance

- **capacitance** (float): Charge storage capacity (reserved for future use)

- **breakdown_voltage** (float): Arc threshold in charge units
  - When `abs(charge) > breakdown_voltage`, arc breakdown occurs
  - Typical values: 0.0 (never arcs) to 1000.0 (arcs easily)

- **arc_emission** (float): Light emission intensity on arc (reserved for future use)

## Uniform Parameters

### electricity_step.glsl

- **dt** (float): Integration timestep from adaptive substepping
- **chargeDecay** (float): Exponential decay rate per frame (0.0 = none, typical 0.01-0.1)
- **maxCharge** (float): Hard cap for stability (default 1000.0)

### electricity_arc.glsl

- **dt** (float): Integration timestep
- **breakdownThreshold** (float): Charge level that triggers arc (default 500.0)
- **arcTempDelta** (float): Temperature added on breakdown (default 200.0)
- **arcPressurePulse** (float): Divergence spike magnitude (default 5.0)

## Performance

- **Typical Cost**: ~1.0ms @ 1024×1024 grid
- **Optional Pass**: Can be skipped via `config.enable_electricity = False`
- **Memory**: 2 × r32f textures (charge_a, charge_b) = 8MB @ 1024×1024
- **Workgroups**: 64×64 = 4096 workgroups @ 1024×1024

## Interactions

### Current Reads/Writes

**electricity_step.glsl:**
- Reads: cells (SSBO), rules (SSBO), charge_in (r32f)
- Writes: charge_out (r32f)

**electricity_arc.glsl:**
- Reads: cells (SSBO), rules (SSBO), charge_in (r32f), temp_in (r32f)
- Writes: charge_out (r32f), temp_out (r32f), divergence (r32f)

### Cross-System Coupling (v7 Target)

1. **Weather → Electricity**: Rain increases conductivity
   - Planned: humidity field affects local conductivity boost
   - Implementation: Add `rainConductivityBoost` uniform

2. **Electricity → Biology**: Electric fields affect growth
   - Planned: Moderate fields stimulate growth, strong fields inhibit
   - Implementation: Read charge field in biology_step.glsl

3. **Fluid → Electricity**: Moving conductors carry charge
   - Planned: Velocity-dependent charge advection
   - Implementation: Read velocity field in electricity_step.glsl

## Shader Bindings

### electricity_step.glsl

```
SSBO:
  binding 0:  CellBuffer (readonly)
  binding 2:  RuleBuffer (readonly)

Image:
  binding 9:  chargeIn (r32f, readonly)
  binding 10: chargeOut (r32f, writeonly)

Uniforms:
  gridSize (uvec2)
  ruleStride (uint)
  dt (float)
  chargeDecay (float)
  maxCharge (float)
```

### electricity_arc.glsl

```
SSBO:
  binding 0:  CellBuffer (readonly)
  binding 2:  RuleBuffer (readonly)

Image:
  binding 9:  chargeIn (r32f, readonly)
  binding 10: chargeOut (r32f, writeonly)
  binding 11: tempIn (r32f, readonly)
  binding 12: tempOut (r32f, writeonly)
  binding 4:  divOut (r32f, writeonly)

Uniforms:
  gridSize (uvec2)
  ruleStride (uint)
  dt (float)
  breakdownThreshold (float)
  arcTempDelta (float)
  arcPressurePulse (float)
```

## Configuration

### CLI Flags (main.py)

```python
--enable-electricity  (default: False)
--charge-decay         (default: 0.0)
--max-charge           (default: 1000.0)
--breakdown-threshold  (default: 500.0)
--arc-temp-delta       (default: 200.0)
--arc-pressure-pulse   (default: 5.0)
```

### Config Fields (core/config.py)

```python
enable_electricity: bool = False
charge_decay: float = 0.0
max_charge: float = 1000.0
breakdown_threshold: float = 500.0
arc_temp_delta: float = 200.0
arc_pressure_pulse: float = 5.0
```

## Debug Visualization

Press `Tab` to cycle debug views. View 2 shows charge field:

- **Visualization**: Black → Yellow → White heatmap
- **Range**: 0 to ±500 charge units
- **Blend**: 80% overlay on material color

Inspector panel (press `I`) shows charge value for probed cell.

## Examples

### Copper Wire

```yaml
copper:
  electrical:
    conductivity: 0.95
    breakdown_voltage: 300.0
    arc_emission: 0.8
```

High conductivity, arcs at moderate charge levels.

### Insulator

```yaml
glass:
  electrical:
    conductivity: 0.0
    breakdown_voltage: 0.0
    arc_emission: 0.0
```

No charge flow, stores charge frozen.

## Known Limitations

1. No velocity-dependent charge advection (planned for v7)
2. No weather coupling (rain conductivity boost planned for v7)
3. No biology coupling (electric field growth effects planned for v7)
4. Arc emission not yet used for visual effects
5. Capacitance property reserved but not implemented

## Future Work (v7)

1. Implement velocity-dependent charge advection
2. Add rain conductivity boost from weather system
3. Add electric field growth modulation in biology
4. Use arc_emission for visual lightning effects
5. Implement capacitance for charge storage
6. Add spark/jump effects between nearby conductors
