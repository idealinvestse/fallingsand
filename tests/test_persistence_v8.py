"""Tests for FSND v8 chunked save format."""

import numpy as np
import pytest
from pathlib import Path

from simulation.persistence_v8 import (
    V8Writer,
    V8Reader,
    SAVE_MAGIC,
    SAVE_VERSION_V8,
)


def test_v8_roundtrip(tmp_path: Path) -> None:
    """Test save/load cycle preserves all data."""
    width, height = 64, 64
    cells = np.random.randint(0, 255, size=(width * height,), dtype=np.uint32)
    temp = np.random.rand(width * height).astype(np.float32)
    charge = np.random.rand(width * height).astype(np.float32) * 1000.0
    nutrient = np.random.rand(width * height).astype(np.float32) * 200.0
    moisture = np.random.rand(width * height).astype(np.float32) * 200.0
    humidity = np.random.rand(width * height).astype(np.float32) * 200.0

    # Save
    save_path = tmp_path / "test.fsnd"
    w = V8Writer(width, height)
    w.add_cells(cells.tobytes())
    w.add_temperature(temp.tobytes())
    w.add_meta()
    w.add_charge(charge.tobytes())
    w.add_nutrient(nutrient.tobytes())
    w.add_moisture(moisture.tobytes())
    w.add_humidity(humidity.tobytes())
    w.write(save_path)

    # Load
    r = V8Reader(save_path)

    # Verify
    loaded_cells = np.frombuffer(r.get_cells(), dtype=np.uint32)
    loaded_temp = np.frombuffer(r.get_temperature(), dtype=np.float32)
    loaded_charge = np.frombuffer(r.get_charge(), dtype=np.float32)
    loaded_nutrient = np.frombuffer(r.get_nutrient(), dtype=np.float32)
    loaded_moisture = np.frombuffer(r.get_moisture(), dtype=np.float32)
    loaded_humidity = np.frombuffer(r.get_humidity(), dtype=np.float32)

    np.testing.assert_array_equal(loaded_cells, cells)
    np.testing.assert_array_almost_equal(loaded_temp, temp)
    np.testing.assert_array_almost_equal(loaded_charge, charge)
    np.testing.assert_array_almost_equal(loaded_nutrient, nutrient)
    np.testing.assert_array_almost_equal(loaded_moisture, moisture)
    np.testing.assert_array_almost_equal(loaded_humidity, humidity)


def test_v8_crc32_validation(tmp_path: Path) -> None:
    """Test CRC32 detection of corruption."""
    width, height = 32, 32
    cells = np.zeros(width * height, dtype=np.uint32)
    temp = np.zeros(width * height, dtype=np.float32)

    save_path = tmp_path / "test.fsnd"
    w = V8Writer(width, height)
    w.add_cells(cells.tobytes())
    w.add_temperature(temp.tobytes())
    w.add_meta()
    w.write(save_path)

    # Corrupt single byte
    with open(save_path, "r+b") as f:
        f.seek(30)  # Somewhere in the file
        f.write(b"\xFF")

    # Should raise CRC error
    with pytest.raises(ValueError, match="CRC32 mismatch"):
        V8Reader(save_path)


def test_v8_optional_chunks(tmp_path: Path) -> None:
    """Test optional chunk handling."""
    width, height = 32, 32
    cells = np.zeros(width * height, dtype=np.uint32)
    temp = np.zeros(width * height, dtype=np.float32)

    # Save with only required chunks
    save_path = tmp_path / "test_minimal.fsnd"
    w = V8Writer(width, height)
    w.add_cells(cells.tobytes())
    w.add_temperature(temp.tobytes())
    w.add_meta()
    w.write(save_path)

    # Load successfully
    r = V8Reader(save_path)
    assert r.get_cells() is not None
    assert r.get_temperature() is not None
    assert r.get_charge() is None
    assert r.get_nutrient() is None
    assert r.get_moisture() is None
    assert r.get_humidity() is None

    # Save with all optional chunks
    save_path_full = tmp_path / "test_full.fsnd"
    w2 = V8Writer(width, height)
    w2.add_cells(cells.tobytes())
    w2.add_temperature(temp.tobytes())
    w2.add_meta()
    w2.add_charge(np.zeros(width * height, dtype=np.float32).tobytes())
    w2.add_nutrient(np.zeros(width * height, dtype=np.float32).tobytes())
    w2.add_moisture(np.zeros(width * height, dtype=np.float32).tobytes())
    w2.add_humidity(np.zeros(width * height, dtype=np.float32).tobytes())
    w2.write(save_path_full)

    # Load and verify all fields
    r2 = V8Reader(save_path_full)
    assert r2.get_cells() is not None
    assert r2.get_temperature() is not None
    assert r2.get_charge() is not None
    assert r2.get_nutrient() is not None
    assert r2.get_moisture() is not None
    assert r2.get_humidity() is not None


def test_v8_header_validation(tmp_path: Path) -> None:
    """Test header validation."""
    width, height = 32, 32
    cells = np.zeros(width * height, dtype=np.uint32)
    temp = np.zeros(width * height, dtype=np.float32)

    save_path = tmp_path / "test.fsnd"
    w = V8Writer(width, height)
    w.add_cells(cells.tobytes())
    w.add_temperature(temp.tobytes())
    w.add_meta()
    w.write(save_path)

    # Invalid magic
    with open(save_path, "r+b") as f:
        f.seek(0)
        f.write(b"XXXX")
    with pytest.raises(ValueError, match="Invalid magic"):
        V8Reader(save_path)

    # Restore magic, corrupt version
    with open(save_path, "r+b") as f:
        f.seek(0)
        f.write(SAVE_MAGIC)
        f.seek(4)
        f.write(np.array([999], dtype=np.uint32).tobytes())
    with pytest.raises(ValueError, match="Unsupported version"):
        V8Reader(save_path)


def test_v8_separate_nutrient_moisture(tmp_path: Path) -> None:
    """Test that nutrient and moisture are saved as separate chunks."""
    width, height = 32, 32
    cells = np.zeros(width * height, dtype=np.uint32)
    temp = np.zeros(width * height, dtype=np.float32)
    nutrient = np.ones(width * height, dtype=np.float32) * 100.0
    moisture = np.ones(width * height, dtype=np.float32) * 50.0

    save_path = tmp_path / "test.fsnd"
    w = V8Writer(width, height)
    w.add_cells(cells.tobytes())
    w.add_temperature(temp.tobytes())
    w.add_meta()
    w.add_nutrient(nutrient.tobytes())
    w.add_moisture(moisture.tobytes())
    w.write(save_path)

    # Load and verify separate chunks
    r = V8Reader(save_path)
    loaded_nutrient = np.frombuffer(r.get_nutrient(), dtype=np.float32)
    loaded_moisture = np.frombuffer(r.get_moisture(), dtype=np.float32)

    np.testing.assert_array_almost_equal(loaded_nutrient, nutrient)
    np.testing.assert_array_almost_equal(loaded_moisture, moisture)

    # Verify they're not packed together
    assert len(loaded_nutrient) == width * height
    assert len(loaded_moisture) == width * height


def test_v8_meta_chunk(tmp_path: Path) -> None:
    """Test META chunk parsing."""
    width, height = 32, 32
    cells = np.zeros(width * height, dtype=np.uint32)
    temp = np.zeros(width * height, dtype=np.float32)

    save_path = tmp_path / "test.fsnd"
    w = V8Writer(width, height)
    w.add_cells(cells.tobytes())
    w.add_temperature(temp.tobytes())
    w.add_meta()
    w.write(save_path)

    r = V8Reader(save_path)
    meta = r.get_meta()

    assert meta is not None
    assert meta["version"] == SAVE_VERSION_V8
    assert meta["width"] == width
    assert meta["height"] == height
    assert "timestamp" in meta
    assert "name" in meta
