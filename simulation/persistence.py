"""Save/load and undo management for the simulation grid."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np

from core.constants import RULE_STRIDE
from gpu.buffers import BufferManager


_SAVE_MAGIC = b"FSND"
_SAVE_VERSION = 7

# Cell packing layout history:
#   v6 and earlier: type[0..7] | temp[8..15] | life[16..23] | flags[24..31]
#   v7 and later:   type[0..7] | life[8..15]  | flags[16..23] | unused[24..31]


def _migrate_v6_cells(cell_bytes: bytes, count: int) -> bytes:
    """Remap v6 cell layout (type|temp|life|flags) to v7 (type|life|flags|0)."""
    grid = np.frombuffer(cell_bytes, dtype=np.uint32).copy()
    typ = grid & 0xFF
    life = (grid >> 16) & 0xFF
    flags = (grid >> 24) & 0xFF
    grid = typ | (life << 8) | (flags << 16)
    return grid.tobytes()


class PersistenceManager:
    """Handles save/load and undo for the simulation grid state."""

    def __init__(self, buffers: BufferManager, grid_size: tuple[int, int], atm_pressure: float):
        self.buffers = buffers
        self.width, self.height = grid_size
        self.atm_pressure = atm_pressure
        self._undo_stack: deque[np.ndarray] = deque(maxlen=5)

    # ── Save / Load ─────────────────────────────────────────────────────────

    def save_state(self, filepath: Path) -> None:
        cell_bytes = self.buffers.save_state()
        temp_bytes = self.buffers.temp_a.read()
        header = bytearray()
        header += _SAVE_MAGIC
        header += np.array(
            [_SAVE_VERSION, self.width, self.height, RULE_STRIDE],
            dtype=np.uint32,
        ).tobytes()
        filepath.write_bytes(bytes(header) + cell_bytes + temp_bytes)

    def get_state(self) -> np.ndarray:
        return np.frombuffer(self.buffers.get_read_buf().read(), dtype=np.uint32).copy()

    def set_state(self, state: np.ndarray) -> None:
        expected = self.width * self.height
        if state.size != expected:
            raise ValueError(f"State has {state.size} cells, expected {expected}")
        data = state.astype(np.uint32, copy=False).tobytes()
        self.buffers.get_read_buf().write(data)
        self.buffers.get_write_buf().write(data)

    def load_state(self, filepath: Path) -> None:
        if not filepath.exists():
            raise FileNotFoundError(f"Save file not found: {filepath}")
        raw = filepath.read_bytes()
        expected_cell_bytes = self.width * self.height * 4

        if raw[:4] == _SAVE_MAGIC:
            hdr = np.frombuffer(raw[4:20], dtype=np.uint32)
            _version, w, h, stride = int(hdr[0]), int(hdr[1]), int(hdr[2]), int(hdr[3])
            if (w, h) != (self.width, self.height):
                raise ValueError(
                    f"Save grid size {(w, h)} does not match current {(self.width, self.height)}"
                )
            if stride != RULE_STRIDE:
                print(f"Warning: save RULE_STRIDE={stride}, current={RULE_STRIDE}")
            payload = raw[20:]
        else:
            # Legacy v4 save: raw uint32 cell data, no header
            if len(raw) != expected_cell_bytes:
                raise ValueError(
                    f"Legacy save size {len(raw)} bytes does not match expected {expected_cell_bytes}"
                )
            payload = raw

        if raw[:4] == _SAVE_MAGIC and _version >= 6:
            temp_offset = expected_cell_bytes
            expected_payload = expected_cell_bytes * 2
            if len(payload) != expected_payload:
                raise ValueError(
                    f"Save payload size {len(payload)} bytes does not match expected {expected_payload} for version {_version}"
                )
            temp_bytes = payload[temp_offset:temp_offset + expected_cell_bytes]
            cell_bytes = payload[:expected_cell_bytes]

            # Migrate old cell layout (v6: type|temp|life|flags → v7: type|life|flags|0)
            if _version < 7:
                cell_bytes = _migrate_v6_cells(cell_bytes, self.width * self.height)

            self.buffers.read_buf.write(cell_bytes)
            self.buffers.write_buf.write(cell_bytes)
            self.buffers.temp_a.write(temp_bytes)
            self.buffers.temp_b.write(temp_bytes)
        else:
            # Legacy save format (v4/v5): only cell data, no float temperature.
            # Migrate cell layout and initialize temps to ambient.
            if raw[:4] == _SAVE_MAGIC and _version < 6:
                payload = _migrate_v6_cells(payload, self.width * self.height)
            self.buffers.load_state(payload)
            # Legacy saves have no float temp data — initialize to ambient.
            from core.constants import TEMP_AMBIENT
            self.buffers.clear_temp_buffers(float(TEMP_AMBIENT))

        # Reset fluid dynamics to avoid stale pressure/velocity affecting loaded state.
        self.buffers.clear_physics_buffers(ambient_pressure=self.atm_pressure)

    # ── Undo ────────────────────────────────────────────────────────────────

    def push_undo_snapshot(self) -> None:
        self._undo_stack.append(self.get_state())

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        prev = self._undo_stack.pop()
        self.set_state(prev)
        # Reset fluid dynamics so the restored grid doesn't inherit
        # stale pressure/velocity from the post-undo simulation state.
        self.buffers.clear_physics_buffers(ambient_pressure=self.atm_pressure)
        return True
