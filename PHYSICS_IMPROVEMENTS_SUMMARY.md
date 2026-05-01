# Physics and Explosion Improvements Summary

## Implemented Enhancements

### 1. Enhanced Explosion Types
**File:** `simulation/state.py`

Added `ExplosionType` enum with distinct explosion behaviors:
- **HIGH_EXPLOSIVE (0)** - Fast detonation, brisance, shattering (C4-style)
- **DEFLAGRATION (1)** - Slower burn, more push than shatter (gunpowder-style)
- **THERMOBARIC (2)** - Air-fuel, uses oxygen, larger radius (fuel-air)
- **NAPALM (3)** - Persistent burning, spreads fire, less concussive
- **FRAGMENTATION (4)** - Produces many small fragments

Updated `ExplosionState` with:
- `explosion_type` - Type of explosion behavior
- `crater_radius` - Configurable crater size
- `fragment_count` - Track fragments produced

### 2. Improved Shockwave Propagation
**File:** `shaders/acoustic_pressure_step.glsl`

Enhancements:
- **Explosion-type specific pulse shapes** - Different pressure profiles:
  - High explosive: sharp Gaussian spike (brisance effect)
  - Deflagration: broader, flatter pulse (more push)
  - Thermobaric: standard pulse with type multiplier
  - Napalm: gradual, low pressure expansion

- **Energy attenuation** - Distance-based energy loss accounting for material density
- **Reflection damping** - Shockwaves lose energy when reflecting off solid boundaries
- **Solid boundary detection** - Detects nearby solid walls and applies reflection loss

### 3. Crater Formation System
**File:** `shaders/state_shader.glsl`

New functions:
- `isGroundMaterial()` - Identifies crater-able materials (stone, sand, dirt, concrete, snow)
- `computeCraterDepth()` - Calculates crater depth based on blast power and material strength

Crater zones:
- **Center (0-30% radius)**: Material ejected upward as fragments, becomes air cavity
- **Rim (30-60% radius)**: Displaced material piles up at crater edge
- **Damage zone (60-80% radius)**: Cracked/weakened material becomes rubble

### 4. Enhanced Fragmentation
**Files:** `shaders/state_shader.glsl`, `shaders/force_shader.glsl`

Fragment improvements:
- **Size variation** - Larger fragments near blast center, smaller at edges
- **Power-based lifetime** - Stronger blasts produce longer-lived fragments
- **Velocity inheritance** - Fragments inherit blast velocity with randomized spread
- **Material-specific debris**:
  - Stone/Concrete → Sand (rubble) or shrapnel
  - Metal → Shrapnel (only from strong blasts)
  - Glass → Small shrapnel pieces
  - Wood/Plant → Embers or ash
  - Sand/Dirt → Dust cloud

Force shader improvements:
- **Age-based velocity decay** - Fragments slow down over time (air resistance)
- **Tumble/rotation effects** - Random rotation for realism
- **Ballistic trajectory** - Reduced gravity for fragment physics
- **Air resistance** - Drag factor applied to fragment velocity

### 5. Ground Scatter (Fragment Landing)
**File:** `shaders/state_shader.glsl`

When fragment life reaches 0:
- **Large fragments** (power > 20) → Sand (rubble piles)
- **Medium fragments** (power 10-20) → Dirt
- **Small fragments** (power < 10) → Ash/dust

This creates realistic material redistribution after explosions.

### 6. Engine API Updates
**File:** `simulation/engine.py`

New explosion trigger methods:
- `trigger_explosion()` - Now accepts `explosion_type` and `crater_radius`
- `trigger_deflagration()` - Gunpowder-style deflagration
- `trigger_thermobaric()` - Fuel-air explosive
- `trigger_napalm_burst()` - Persistent fire burst

## Technical Details

### Material Strength Updates
Extended `getMaterialStrength()` to include:
- Ash (1), Snow (1), Ice (2)
- Sand (2), Dirt (2)
- Stone (3), Metal (4), Concrete (5)

### Uniforms Added
- `explosionType` - Shader-side explosion type
- `energyDecayRate` - Shockwave energy decay
- `reflectionDamping` - Wall reflection energy loss

## Testing
All 313 tests pass:
- Material registry tests
- Shader logic tests
- Explosion state tests
- Pipeline integration tests

## Usage Example

```python
# High explosive (C4 style) - shattering blast
engine.trigger_explosion(x, y, radius=25, force=12, duration=3, 
                         explosion_type=ExplosionType.HIGH_EXPLOSIVE)

# Deflagration (gunpowder) - more push, less shatter
engine.trigger_deflagration(x, y, radius=30, force=6)

# Thermobaric - large radius, oxygen-consuming
engine.trigger_thermobaric(x, y, radius=50, force=10)

# Napalm - persistent fire
engine.trigger_napalm_burst(x, y, radius=35)
```

## Visual Results
- Craters form in ground materials with realistic depth profiles
- Fragments follow ballistic trajectories and scatter when landing
- Different explosion types produce distinct visual signatures
- Shockwaves reflect off walls with appropriate energy loss
