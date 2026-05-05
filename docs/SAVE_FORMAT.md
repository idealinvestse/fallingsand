# Save Format

Persistence is implemented in `simulation/persistence.py` (v7) and `simulation/persistence_v8.py` (v8).

## Current Format

### FSND v7 (Legacy)

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

### FSND v8 (Chunked Binary)

See `simulation/persistence_v8.py` for implementation.

**Header (28 bytes):**

```text
magic:           4 bytes  b"FSND"
version:         uint32   8
width:           uint32
height:          uint32
flags:           uint32   (reserved)
chunk_count:     uint32
header_crc32:    uint32   (CRC32 of header bytes 0..23)
```

**Chunk Directory (28 bytes per entry):**

```text
tag:          4 bytes   (e.g. b"CELL", b"TEMP", b"META")
offset:       uint64    (byte offset from start of file)
size:         uint64    (byte size of chunk data)
crc32:        uint32    (CRC32 of chunk data)
compression:  uint32    (0=none, 1=zstd reserved)
```

**Required Chunks:**

- `CELL`: uint32[width*height] - cell data
- `TEMP`: float32[width*height] - temperature data
- `META`: utf8 json/yaml - metadata (name, timestamp, config)

**Optional Chunks:**

- `VEL2`: float32[width*height*2] - velocity field
- `PRES`: float32[width*height] - pressure field
- `MASS`: float16[width*height] - wet mass
- `CHRG`: float32[width*height] - charge field
- `NUTR`: float32[width*height*2] - nutrient + moisture (packed)
- `HUMD`: float32[width*height] - humidity field

**Benefits:**

- CRC32 validation for header and each chunk
- Optional chunks for extensibility
- Future compression support (zstd reserved)
- Better error detection and recovery

## Cell Layout History

```text
v6 and earlier: type[0..7] | temp[8..15] | life[16..23] | flags[24..31]
v7 and later:   type[0..7] | life[8..15] | flags[16..23] | unused[24..31]
```

## Migration Policy

- Raw legacy saves without `FSND` magic are treated as cell-only saves.
- `FSND` saves with version `6` include cell bytes plus temperature bytes and migrate cell packing to v7.
- `FSND` saves with version `7` are loaded directly.
- `FSND` saves with version `8` use chunked binary format with CRC32 validation.
- Legacy saves without temperature data initialize temperature to ambient.
- Loading resets velocity, pressure, divergence, and vorticity buffers to avoid stale physics state.
- v7 saves auto-migrate to v8 on load (planned).
- Batch migration tool available: `tools/migrate_saves.py` (planned).

## Compatibility Rules

- Do not reuse old bit positions for new cell fields without a save-format bump.
- Save-format version is independent from the application version.
- Any rule-stride mismatch should remain visible to users/developers.
