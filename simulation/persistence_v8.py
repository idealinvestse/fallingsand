"""FSND v8 chunked binary save format.

Header:
  magic:        4 bytes  b"FSND"
  version:      uint32   8
  width:        uint32
  height:       uint32
  flags:        uint32   (reserved)
  chunk_count:  uint32
  header_crc32: uint32   (CRC32 of header bytes 0..23)

Chunk directory (chunk_count entries):
  tag:          4 bytes   (e.g. b"CELL", b"TEMP", b"META")
  offset:       uint64    (byte offset from start of file)
  size:         uint64    (byte size of chunk data)
  crc32:        uint32    (CRC32 of chunk data)
  compression:  uint32    (0=none, 1=zstd reserved)

Required chunks:
  CELL  uint32[width*height]   cell data
  TEMP  float32[width*height]  temperature data
  META  utf8 json/yaml         metadata (name, timestamp, config)

Optional chunks:
  VEL2  float32[width*height*2]  velocity field
  PRES  float32[width*height]    pressure field
  MASS  float16[width*height]    wet mass
  CHRG  float32[width*height]    charge field
  NUTR  float32[width*height]    nutrient field
  MOIS  float32[width*height]    moisture field
  HUMD  float32[width*height]    humidity field
"""

from __future__ import annotations

import json
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.constants import RULE_STRIDE

SAVE_MAGIC = b"FSND"
SAVE_VERSION_V8 = 8

# Chunk tags
TAG_CELL = b"CELL"
TAG_TEMP = b"TEMP"
TAG_META = b"META"
TAG_VEL2 = b"VEL2"
TAG_PRES = b"PRES"
TAG_MASS = b"MASS"
TAG_CHRG = b"CHRG"
TAG_NUTR = b"NUTR"
TAG_MOIS = b"MOIS"
TAG_HUMD = b"HUMD"

# Header format: magic(4) + version(4) + width(4) + height(4) + flags(4) + chunk_count(4) + crc32(4) = 28 bytes
HEADER_STRUCT = struct.Struct("<4s 5I I")
HEADER_SIZE = HEADER_STRUCT.size  # 28

# Chunk directory entry: tag(4) + offset(8) + size(8) + crc32(4) + compression(4) = 28 bytes
CHUNK_ENTRY_STRUCT = struct.Struct("<4s Q Q I I")
CHUNK_ENTRY_SIZE = CHUNK_ENTRY_STRUCT.size  # 28


def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _build_header(width: int, height: int, flags: int, chunk_count: int) -> bytes:
    """Build header bytes (without CRC32)."""
    return HEADER_STRUCT.pack(SAVE_MAGIC, SAVE_VERSION_V8, width, height, flags, chunk_count, 0)


def _build_chunk_entry(tag: bytes, offset: int, size: int, data: bytes) -> bytes:
    """Build a chunk directory entry."""
    return CHUNK_ENTRY_STRUCT.pack(tag, offset, size, _crc32(data), 0)


def _build_meta_json(width: int, height: int) -> bytes:
    """Build META chunk as JSON."""
    meta = {
        "name": "Falling Sand save",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": SAVE_VERSION_V8,
        "width": width,
        "height": height,
        "rule_stride": RULE_STRIDE,
    }
    return json.dumps(meta, indent=2).encode("utf-8")


class V8Writer:
    """Writes FSND v8 chunked save files."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._chunks: list[tuple[bytes, bytes]] = []  # (tag, data)

    def add_cells(self, data: bytes) -> None:
        self._chunks.append((TAG_CELL, data))

    def add_temperature(self, data: bytes) -> None:
        self._chunks.append((TAG_TEMP, data))

    def add_meta(self, data: bytes | None = None) -> None:
        if data is None:
            data = _build_meta_json(self.width, self.height)
        self._chunks.append((TAG_META, data))

    def add_velocity(self, data: bytes) -> None:
        self._chunks.append((TAG_VEL2, data))

    def add_pressure(self, data: bytes) -> None:
        self._chunks.append((TAG_PRES, data))

    def add_mass(self, data: bytes) -> None:
        self._chunks.append((TAG_MASS, data))

    def add_charge(self, data: bytes) -> None:
        self._chunks.append((TAG_CHRG, data))

    def add_nutrient(self, data: bytes) -> None:
        self._chunks.append((TAG_NUTR, data))

    def add_moisture(self, data: bytes) -> None:
        self._chunks.append((TAG_MOIS, data))

    def add_humidity(self, data: bytes) -> None:
        self._chunks.append((TAG_HUMD, data))

    def write(self, filepath: Path) -> None:
        """Write the complete v8 file."""
        chunk_count = len(self._chunks)
        header = _build_header(self.width, self.height, 0, chunk_count)

        # Compute directory offset: header + directory
        dir_offset = HEADER_SIZE + chunk_count * CHUNK_ENTRY_SIZE

        # Compute chunk offsets and build directory
        entries: list[bytes] = []
        offset = dir_offset
        for tag, data in self._chunks:
            entries.append(_build_chunk_entry(tag, offset, len(data), data))
            offset += len(data)

        # Finalize header with CRC32 of header bytes 0..23
        header_no_crc = header[:24]
        crc = _crc32(header_no_crc)
        header = HEADER_STRUCT.pack(SAVE_MAGIC, SAVE_VERSION_V8, self.width, self.height, 0, chunk_count, crc)

        # Write
        with open(filepath, "wb") as f:
            f.write(header)
            for entry in entries:
                f.write(entry)
            for _, data in self._chunks:
                f.write(data)


class V8Reader:
    """Reads FSND v8 chunked save files."""

    def __init__(self, filepath: Path):
        with open(filepath, "rb") as f:
            self._raw = f.read()

        if len(self._raw) < HEADER_SIZE:
            raise ValueError("File too small for v8 header")

        magic, version, width, height, flags, chunk_count, header_crc = HEADER_STRUCT.unpack_from(self._raw, 0)

        if magic != SAVE_MAGIC:
            raise ValueError(f"Invalid magic: {magic!r}")
        if version != SAVE_VERSION_V8:
            raise ValueError(f"Unsupported version: {version}")

        # Verify header CRC32
        computed_crc = _crc32(self._raw[:24])
        if computed_crc != header_crc:
            raise ValueError(f"Header CRC32 mismatch: computed {computed_crc:#x}, stored {header_crc:#x}")

        self.version = version
        self.width = width
        self.height = height
        self.flags = flags

        # Parse chunk directory
        self._chunks: dict[bytes, bytes] = {}
        dir_start = HEADER_SIZE
        for i in range(chunk_count):
            entry_offset = dir_start + i * CHUNK_ENTRY_SIZE
            tag, chunk_offset, chunk_size, chunk_crc, compression = CHUNK_ENTRY_STRUCT.unpack_from(
                self._raw, entry_offset
            )

            if compression != 0:
                raise ValueError(f"Chunk {tag!r} uses unsupported compression {compression}")

            chunk_data = self._raw[chunk_offset:chunk_offset + chunk_size]

            # Verify chunk CRC32
            computed_chunk_crc = _crc32(chunk_data)
            if computed_chunk_crc != chunk_crc:
                raise ValueError(
                    f"Chunk {tag!r} CRC32 mismatch: computed {computed_chunk_crc:#x}, stored {chunk_crc:#x}"
                )

            self._chunks[tag] = chunk_data

    def get_chunk(self, tag: bytes) -> bytes | None:
        return self._chunks.get(tag)

    def get_cells(self) -> bytes:
        data = self._chunks.get(TAG_CELL)
        if data is None:
            raise ValueError("Missing required CELL chunk")
        return data

    def get_temperature(self) -> bytes:
        data = self._chunks.get(TAG_TEMP)
        if data is None:
            raise ValueError("Missing required TEMP chunk")
        return data

    def get_meta(self) -> dict[str, Any]:
        data = self._chunks.get(TAG_META)
        if data is None:
            return {}
        return json.loads(data.decode("utf-8"))  # type: ignore[no-any-return]

    def get_velocity(self) -> bytes | None:
        return self._chunks.get(TAG_VEL2)

    def get_pressure(self) -> bytes | None:
        return self._chunks.get(TAG_PRES)

    def get_charge(self) -> bytes | None:
        return self._chunks.get(TAG_CHRG)

    def get_nutrient(self) -> bytes | None:
        return self._chunks.get(TAG_NUTR)

    def get_moisture(self) -> bytes | None:
        return self._chunks.get(TAG_MOIS)

    def get_humidity(self) -> bytes | None:
        return self._chunks.get(TAG_HUMD)

    def get_mass(self) -> bytes | None:
        return self._chunks.get(TAG_MASS)
