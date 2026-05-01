# Save Format

Persistence is implemented in `simulation/persistence.py`.

## Current Format

Current saves use:

```text
magic:        4 bytes  b"FSND"
version:      uint32   7
width:        uint32
height:       uint32
rule_stride:  uint32
cell bytes:   width * height * 4 bytes
temp bytes:   width * height * 4 bytes
```

Temperature bytes are `float32` because the simulation uses `r32f` textures.

## Cell Layout History

```text
v6 and earlier: type[0..7] | temp[8..15] | life[16..23] | flags[24..31]
v7 and later:   type[0..7] | life[8..15] | flags[16..23] | unused[24..31]
```

## Migration Policy

- Raw legacy saves without `FSND` magic are treated as cell-only saves.
- `FSND` saves with version `6` include cell bytes plus temperature bytes and migrate cell packing to v7.
- `FSND` saves with version `7` are loaded directly.
- Legacy saves without temperature data initialize temperature to ambient.
- Loading resets velocity, pressure, divergence, and vorticity buffers to avoid stale physics state.

## Compatibility Rules

- Do not reuse old bit positions for new cell fields without a save-format bump.
- Save-format version is independent from the application version.
- Any rule-stride mismatch should remain visible to users/developers.
