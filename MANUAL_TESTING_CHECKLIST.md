# Manual Testing Checklist

## Phase 4: v6.0 Final Polish

### CLI Flags
- [ ] All CLI flags parse correctly
  - [ ] --charge-decay
  - [ ] --max-charge
  - [ ] --breakdown-threshold
  - [ ] --arc-temp-delta
  - [ ] --arc-pressure-pulse
  - [ ] --nutrient-diffuse-rate
  - [ ] --moisture-diffuse-rate
  - [ ] --growth-rate
  - [ ] --decay-rate
  - [ ] --humidity-diffuse-rate
  - [ ] --evaporation-rate
  - [ ] --condensation-rate
  - [ ] --saturation-threshold
  - [ ] --rain-speed
  - [ ] --bloom-intensity
  - [ ] --bloom-radius
  - [ ] --bloom-quality (low/medium/high)
  - [ ] --adaptive-quality
  - [ ] --min-fps-target
  - [ ] --transpiration-rate

### System Controls Panel
- [ ] System controls panel updates config in real-time
  - [ ] Electricity enable/disable toggle works
  - [ ] Charge decay slider adjusts parameter
  - [ ] Breakdown threshold slider adjusts parameter
  - [ ] Biology enable/disable toggle works
  - [ ] Growth rate slider adjusts parameter
  - [ ] Decay rate slider adjusts parameter
  - [ ] Weather enable/disable toggle works
  - [ ] Evaporation rate slider adjusts parameter
  - [ ] Saturation threshold slider adjusts parameter
  - [ ] Bloom enable/disable toggle works
  - [ ] Bloom threshold slider adjusts parameter
  - [ ] Bloom intensity slider adjusts parameter
  - [ ] Sparse mode toggle works

### Performance Overlay
- [ ] Performance overlay shows accurate timings
  - [ ] Ctrl+P toggles overlay visibility
  - [ ] FPS display updates correctly
  - [ ] FPS history graph renders
  - [ ] Per-pass timing bars show correct values
  - [ ] Budget-exceeded passes highlighted in red
  - [ ] Memory usage displays (placeholder)
  - [ ] Quality tier indicator shows when adaptive mode enabled

### Transpiration Rate
- [ ] Transpiration rate uniform passed to weather shader
  - [ ] --transpiration-rate flag parses correctly
  - [ ] Transpiration affects humidity in weather simulation

## Phase 5: v7 Foundation

### Quality Tier Auto-Adjustment
- [ ] Adaptive quality mode adjusts tiers under load
  - [ ] --adaptive-quality flag enables mode
  - [ ] Quality tier indicator shows current tier (High/Medium/Low)
  - [ ] FPS drops below min_fps_target triggers downgrade
  - [ ] FPS consistently high triggers upgrade
  - [ ] Quality tier changes apply pressure_iterations, acoustic_substeps, bloom_enabled

### Sparse Region Optimization
- [ ] Sparse mode toggle works
  - [ ] Sparse mode toggle in system controls panel
  - [ ] enable_sparse_mode() method called correctly
  - [ ] Sparse mask updates with cell data
  - [ ] Dispatch ranges generated for active regions

### Enhanced Adaptive Pass Skipping
- [ ] Pass priority system works
  - [ ] Low-priority passes (biology, weather) skip when budget exceeded
  - [ ] Medium-priority passes (electricity) skip at higher threshold
  - [ ] High-priority passes (vorticity, heat) skip only at extreme threshold

## Phase 6: Cross-System Couplings

### Cross-System Coupling Effects
- [ ] Cross-system couplings produce visible effects
  - [ ] Weather → Electricity: Evaporation increases conductivity (commented in shader)
  - [ ] Electricity → Biology: Electric fields affect growth rate
  - [ ] Biology → Weather: Transpiration increases humidity
  - [ ] Fluid → Electricity: Velocity affects charge advection

## Phase 6: Save/Load

### Save/Load Preservation
- [ ] Save/load preserves all new fields
  - [ ] Charge field preserved in v8 format
  - [ ] Nutrient field preserved in v8 format
  - [ ] Moisture field preserved in v8 format
  - [ ] Humidity field preserved in v8 format
  - [ ] CLI flags affect save format selection (--save-format v8)

## Phase 7: Documentation

### Documentation Updates
- [ ] docs/PERFORMANCE.md updated with adaptive simulation details
- [ ] docs/GPU_PIPELINE.md updated with sparse region dispatch
- [ ] docs/ARCHITECTURE.md updated with performance monitoring section
- [ ] docs/ADAPTIVE_SIMULATION.md created with quality tier system details
- [ ] CHANGELOG.md updated with v6.0 final polish completion
