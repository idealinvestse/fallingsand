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

The active material ID range is `0..48`; `core.constants.NUM_TYPES` is `49`.

The registry validates that material IDs, scalar ranges, reaction references, and rule-buffer length stay compatible with the GPU layout.

## Rule Buffer

The material rule buffer is an SSBO of `float32` values with:

```text
NUM_TYPES * RULE_STRIDE
```

Current `RULE_STRIDE` is `49`.

Layout groups:

- `0..17`: base visual, density, category, thermal, phase, electrical, burn, viscosity, turbulence, wet/dry fields.
- `18..25`: heat capacity, phase points, surface tension, solubility, cohesion, restitution, state family.
- `26..40`: three reaction slots.
- `41..46`: explosive properties.
- `47..48`: oxygen/combustion properties.

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
