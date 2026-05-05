"""Save/load and undo management for the simulation grid."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np

from core.constants import RULE_STRIDE
from gpu.buffers import BufferManager


_SAVE_MAGIC = b"FSND"
_SAVE_VERSION = 7
_SAVE_VERSION_V8 = 8

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

    def save_state(self, filepath: Path, use_v8: bool = False) -> None:
        if use_v8:
            self._save_state_v8(filepath)
            return
        cell_bytes = self.buffers.save_state()
        temp_bytes = self.buffers.temp_a.read()
        header = bytearray()
        header += _SAVE_MAGIC
        header += np.array(
            [_SAVE_VERSION, self.width, self.height, RULE_STRIDE],
            dtype=np.uint32,
        ).tobytes()
        filepath.write_bytes(bytes(header) + cell_bytes + temp_bytes)

    def _save_state_v8(self, filepath: Path) -> None:
        from simulation.persistence_v8 import V8Writer
        w = V8Writer(self.width, self.height)
        w.add_cells(self.buffers.save_state())
        w.add_temperature(self.buffers.temp_a.read())
        w.add_meta()
        # Optional: save physics fields if available
        try:
            w.add_charge(self.buffers.charge_a.read())
        except Exception:
            pass
        try:
            w.add_nutrient(self.buffers.nutrient_a.read() + self.buffers.moisture_a.read())
        except Exception:
            pass
        try:
            w.add_humidity(self.buffers.humidity_a.read())
        except Exception:
            pass
        w.write(filepath)

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

        # Detect v8 format
        if raw[:4] == _SAVE_MAGIC and len(raw) >= 8:
            version_check = int(np.frombuffer(raw[4:8], dtype=np.uint32)[0])
            if version_check == _SAVE_VERSION_V8:
                self._load_state_v8(filepath)
                return

        self._load_state_v7(raw)

    def _load_state_v7(self, raw: bytes) -> None:
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
            if raw[:4] == _SAVE_MAGIC and _version < 6:
                payload = _migrate_v6_cells(payload, self.width * self.height)
            self.buffers.load_state(payload)
            from core.constants import TEMP_AMBIENT
            self.buffers.clear_temp_buffers(float(TEMP_AMBIENT))

        self.buffers.clear_physics_buffers(ambient_pressure=self.atm_pressure)

    def _load_state_v8(self, filepath: Path) -> None:
        from simulation.persistence_v8 import V8Reader
        r = V8Reader(filepath)
        if (r.width, r.height) != (self.width, self.height):
            raise ValueError(
                f"Save grid size {(r.width, r.height)} does not match current {(self.width, self.height)}"
            )
        cell_bytes = r.get_cells()
        temp_bytes = r.get_temperature()
        self.buffers.read_buf.write(cell_bytes)
        self.buffers.write_buf.write(cell_bytes)
        self.buffers.temp_a.write(temp_bytes)
        self.buffers.temp_b.write(temp_bytes)
        # Restore optional fields
        charge = r.get_charge()
        if charge is not None:
            try:
                self.buffers.charge_a.write(charge)
                self.buffers.charge_b.write(charge)
            except Exception:
                pass
        nutrient = r.get_nutrient()
        if nutrient is not None:
            try:
                half = len(nutrient) // 2
                self.buffers.nutrient_a.write(nutrient[:half])
                self.buffers.moisture_a.write(nutrient[half:])
            except Exception:
                pass
        humidity = r.get_humidity()
        if humidity is not None:
            try:
                self.buffers.humidity_a.write(humidity)
                self.buffers.humidity_b.write(humidity)
            except Exception:
                pass
        self.buffers.clear_physics_buffers(ambient_pressure=self.atm_pressure)

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
