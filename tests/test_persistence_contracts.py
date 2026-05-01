from pathlib import Path

import numpy as np

from core.constants import RULE_STRIDE, TEMP_AMBIENT
from simulation.persistence import PersistenceManager, _SAVE_MAGIC, _SAVE_VERSION


class FakeBuffer:
    def __init__(self, data: bytes = b""):
        self.data = bytearray(data)

    def read(self, size=None, offset=0):
        if size is None:
            return bytes(self.data)
        return bytes(self.data[offset:offset + size])

    def write(self, data: bytes):
        self.data = bytearray(data)


class FakeTexture(FakeBuffer):
    pass


class FakeBuffers:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        count = width * height
        self.read_buf = FakeBuffer(np.zeros(count, dtype=np.uint32).tobytes())
        self.write_buf = FakeBuffer(np.zeros(count, dtype=np.uint32).tobytes())
        self.temp_a = FakeTexture(np.full(count, TEMP_AMBIENT, dtype=np.float32).tobytes())
        self.temp_b = FakeTexture(np.full(count, TEMP_AMBIENT, dtype=np.float32).tobytes())
        self.cleared_physics_with = None

    def save_state(self) -> bytes:
        return self.read_buf.read()

    def get_read_buf(self):
        return self.read_buf

    def get_write_buf(self):
        return self.write_buf

    def load_state(self, data: bytes) -> None:
        self.read_buf.write(data)
        self.write_buf.write(data)

    def clear_temp_buffers(self, ambient_temp: float = TEMP_AMBIENT) -> None:
        count = self.width * self.height
        data = np.full(count, ambient_temp, dtype=np.float32).tobytes()
        self.temp_a.write(data)
        self.temp_b.write(data)

    def clear_physics_buffers(self, ambient_pressure: float = 1.0) -> None:
        self.cleared_physics_with = ambient_pressure


def _manager(width=2, height=2, atm_pressure=1.25):
    buffers = FakeBuffers(width, height)
    return PersistenceManager(buffers, (width, height), atm_pressure), buffers


def test_save_state_writes_v7_header_and_temperature_payload(tmp_path: Path):
    manager, buffers = _manager()
    cells = np.array([1, 2, 3, 4], dtype=np.uint32)
    temps = np.array([96.0, 100.0, 110.0, 120.0], dtype=np.float32)
    buffers.read_buf.write(cells.tobytes())
    buffers.temp_a.write(temps.tobytes())

    out = tmp_path / "state.fsnd"
    manager.save_state(out)

    raw = out.read_bytes()
    header = np.frombuffer(raw[4:20], dtype=np.uint32)
    assert raw[:4] == _SAVE_MAGIC
    assert tuple(header) == (_SAVE_VERSION, 2, 2, RULE_STRIDE)
    assert raw[20:36] == cells.tobytes()
    assert raw[36:] == temps.tobytes()


def test_load_v6_migrates_cell_layout_and_preserves_float_temperature(tmp_path: Path):
    manager, buffers = _manager()
    v6_cells = np.array([
        1 | (55 << 8) | (7 << 16) | (3 << 24),
        2 | (56 << 8) | (8 << 16) | (4 << 24),
        3 | (57 << 8) | (9 << 16) | (5 << 24),
        4 | (58 << 8) | (10 << 16) | (6 << 24),
    ], dtype=np.uint32)
    temps = np.array([55.0, 56.0, 57.0, 58.0], dtype=np.float32)
    header = _SAVE_MAGIC + np.array([6, 2, 2, RULE_STRIDE], dtype=np.uint32).tobytes()
    save_path = tmp_path / "v6.fsnd"
    save_path.write_bytes(header + v6_cells.tobytes() + temps.tobytes())

    manager.load_state(save_path)

    migrated = np.frombuffer(buffers.read_buf.read(), dtype=np.uint32)
    assert migrated.tolist() == [
        1 | (7 << 8) | (3 << 16),
        2 | (8 << 8) | (4 << 16),
        3 | (9 << 8) | (5 << 16),
        4 | (10 << 8) | (6 << 16),
    ]
    assert buffers.temp_a.read() == temps.tobytes()
    assert buffers.temp_b.read() == temps.tobytes()
    assert buffers.cleared_physics_with == 1.25


def test_load_legacy_raw_cells_initializes_temperature_to_ambient(tmp_path: Path):
    manager, buffers = _manager()
    cells = np.array([1, 2, 3, 4], dtype=np.uint32)
    save_path = tmp_path / "legacy.bin"
    save_path.write_bytes(cells.tobytes())

    manager.load_state(save_path)

    temps = np.frombuffer(buffers.temp_a.read(), dtype=np.float32)
    assert np.array_equal(np.frombuffer(buffers.read_buf.read(), dtype=np.uint32), cells)
    assert np.all(temps == float(TEMP_AMBIENT))
    assert buffers.cleared_physics_with == 1.25
