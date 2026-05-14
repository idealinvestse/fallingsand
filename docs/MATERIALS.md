# Materials

Materials are data-driven and loaded from `simulation/materials.yaml` (legacy v5) or `simulation/materials_v6.yaml` (v6 schema).

## Source of Truth

**Legacy v5:**
- `simulation/materials.yaml`: canonical material definitions.
- `simulation/yaml_loader.py`: YAML loading and constant resolution.
- `simulation/materials.py`: registry construction, validation, packing, public accessors.
- `core/types.py`: `Material`, `Category`, `StateFamily`, and `Cell` dataclasses/enums.
- `shaders/common.glsl`: shader-side material IDs, cell packing helpers, and rule-buffer unpacking.

**v6 Schema:**
- `simulation/materials_v6.yaml`: structured material definitions with grouped properties.
- `simulation/material_schema.py`: v6 schema dataclasses, loading, validation, legacy adapter.
- `simulation/material_schema.py::to_legacy_defs()`: Converts v6 to legacy format for rule buffer.
- See `docs/V6_MATERIAL_SCHEMA.md` for complete v6 specification.

## Material IDs

The active material ID range is `0..60`; `core.constants.NUM_TYPES` is `61`.

The registry validates that material IDs, scalar ranges, reaction references, and rule-buffer length stay compatible with the GPU layout.

## Rule Buffer

The material rule buffer is an SSBO of `float32` values with:

```text
NUM_TYPES * RULE_STRIDE
```

Current `RULE_STRIDE` is `64`.

Layout groups:

- `0..17`: base visual, density, category, thermal, phase, electrical, burn, viscosity, turbulence, wet/dry fields.
- `18..25`: heat capacity, phase points, surface tension, solubility, cohesion, restitution, state family.
- `26..40`: three reaction slots.
- `41..46`: explosive properties.
- `47..48`: oxygen/combustion properties.
- `49..60`: reserved magnetic, plasma, and glass property slots.
- `61..63`: per-material moisture combustion properties (`moisture_resistance`, `wet_ignition_penalty`, `wet_burn_rate_multiplier`).

**Electrical Properties (slots 13-16):**
- Slot 13: conductivity (0.0 = insulator, 1.0 = superconductor)
- Slot 14: capacitance (reserved for future use)
- Slot 15: breakdown_voltage (arc threshold)
- Slot 16: arc_emission (visual effect intensity)

**Biology Properties (planned for v7):**
- To be added to rule buffer slots
- Will include biomass, growth_rate, decay_rate, nutrient_value

Keep `core/constants.py`, `simulation/materials.py`, and `shaders/common.glsl` synchronized when the schema changes.

## Cell Packing

Current cell packing is:

```text
type[0..7] | life[8..15] | flags[16..23] | unused[24..31]
```

Temperature is not packed into the cell. It is stored in `r32f` textures.

## Temperature

The authoritative temperature field is the double-buffered `temp_a`/`temp_b` texture pair in `gpu/buffers.py`.

Save format v7 stores cell bytes and temperature bytes separately.


### v7.2 Moisture Sensitivity Fields

Each material can tune wet combustion independently:

- `moisture_resistance` (`0.0..1.0`): how much local moisture/humidity is ignored. Dry plant matter should be low (`0.05..0.15`), while coal/thermite-like fuels can be high (`0.7+`).
- `wet_ignition_penalty`: extra temperature required at full effective wetness. Sensitive organics use high penalties (`45..60`); resistant fuels use lower penalties (`10..25`).
- `wet_burn_rate_multiplier`: burn/life sustain multiplier under wet conditions. Low values extinguish quickly; values near `1.0` keep burning when wet.

Recommended custom fuel starting points:

| Fuel type | moisture_resistance | wet_ignition_penalty | wet_burn_rate_multiplier |
| --- | ---: | ---: | ---: |
| dry grass/plant | 0.05 | 55 | 0.35 |
| wood | 0.10 | 52 | 0.40 |
| oil/gas | 0.25-0.35 | 34-42 | 0.65-0.75 |
| char/hot ash | 0.40-0.55 | 24 | 0.70-0.75 |
| coal | 0.75 | 20 | 0.90 |

## Combustion Stabilization

Fire propagation is handled in `shaders/state_shader.glsl` using the material `flamm`, `Th`, `bto`, `o2_req`, and `o2_yield` fields from `simulation/materials.yaml`.

Phase 2 combustion stabilization keeps large gas/air regions from becoming an unlimited oxidizer:

- `air` is treated as a weak oxidizer in the shader. Explicit `oxygen` satisfies combustion more readily, while air-only ignition requires multiple air neighbors and higher temperature.
- Moisture from the weather/biology moisture texture suppresses fire by damping heat gain, raising the effective ignition threshold, and shortening `fire`/`ember` life.
- `gas` is now a controlled fuel rather than a near-instant atmospheric flame front: lower flammability, higher ignition temperature, and higher oxygen requirement.
- `oil` still burns readily, but with a higher ignition temperature and oxygen requirement so it is less likely to ignite from incidental warming.

## Combustion, Fire & Byproducts

The current staged-combustion path is intentionally GPU-friendly and reuses existing cell `life`, temperature, material rules, and reaction slots:

1. **Ignition:** flammable materials near fire/ember/spark gain heat and require suitable oxygen availability.
2. **Pyrolysis/charring:** wood, plant, sugar, honey, and sap first become `char` instead of immediately becoming raw fire.
3. **Active burning:** liquids/gases burn as `fire`; solids and char burn as `ember`.
4. **Residue:** embers cool to `ash`; hydrocarbon and coal fuels can produce `soot` as heavy black smoke residue.
5. **Extinguishing:** moisture suppresses heat gain, raises ignition thresholds, and drains fire/ember life.

New Phase 3 byproduct materials:

- `char` (`57`): solid, partially burned organic residue. It can smolder into `ember` when hot and oxidized, or cool/wet down to `ash`.
- `soot` (`58`): dark gas/aerosol byproduct from oil, gas, napalm, and coal combustion. It is non-flammable and eventually clears/cools toward ash/air behavior.

Fuel-specific byproduct behavior:

- Wood/plant/sugar/honey/sap: favor `char` first, then `ember`, then `ash`.
- Oil/gas/napalm: favor active `fire`, with `soot` more likely in oxygen-poor burning.
- Coal/char: favor slower smoldering and darker soot/ash residues.
- Explicit `oxygen` increases combustion intensity and reduces soot likelihood; air-only combustion is weaker and dirtier.

Weather and wind integration:

- The state pass reads both moisture and atmospheric humidity. Local humidity contributes to `wetSuppression`, so rain/humid air can damp heat gain, raise ignition thresholds, and shorten fire/ember life even before explicit water contact.
- The force pass applies wind to `fire`, `ember`, `char`, `soot`, and blast fronts. Char is moved weakly as heavier smoldering debris, while soot follows wind more readily as a smoke-like aerosol.

Regression coverage for combustion balance lives in `tests/test_combustion_stability.py`. It locks in gas anti-runaway thresholds, weak-air ignition gating, staged organic charring, dirty-fuel soot generation, moisture/humidity suppression, and wind coupling for combustion byproducts.
