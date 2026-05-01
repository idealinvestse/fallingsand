import pytest
import numpy as np
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import pack_cell, make_cell, PARTICLES, TEMP_AMBIENT, read_stats


class TestPackCell:
    """Test the pack_cell utility function."""

    def test_pack_cell_basic(self):
        """Test basic cell packing."""
        result = pack_cell(5, 10, 0)
        assert isinstance(result, np.uint32)

        # Verify bit packing: type[0..7] | life[8..15] | flags[16..23]
        typ = result & 0xFF
        life = (result >> 8) & 0xFF
        flags = (result >> 16) & 0xFF

        assert typ == 5
        assert life == 10
        assert flags == 0

    def test_pack_cell_edge_values(self):
        """Test packing with edge case values using valid material ID."""
        result = pack_cell(40, 255, 255)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF
        flags = (result >> 16) & 0xFF

        assert typ == 40
        assert life == 255
        assert flags == 255

    def test_pack_cell_zero_values(self):
        """Test packing with all zero values."""
        result = pack_cell(0, 0, 0)
        assert result == 0

    def test_pack_cell_type_only(self):
        """Test packing with only type specified."""
        result = pack_cell(10)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF
        flags = (result >> 16) & 0xFF

        assert typ == 10
        assert life == 0  # Default life is 0
        assert flags == 0

    def test_pack_cell_overflow_protection(self):
        """Test that values > 255 are truncated to 8 bits."""
        result = pack_cell(40, 300, 300)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF
        flags = (result >> 16) & 0xFF

        # Material ID should remain valid (40), others truncated to 8 bits (300 & 0xFF = 44)
        assert typ == 40
        assert life == 44
        assert flags == 44


class TestMakeCell:
    """Test the make_cell utility function."""

    def test_make_cell_air(self):
        """Test creating an air cell."""
        result = make_cell(0)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF
        flags = (result >> 16) & 0xFF

        assert typ == 0
        assert life == 0
        assert flags == 0

    def test_make_cell_sand(self):
        """Test creating a sand cell."""
        result = make_cell(1)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF

        assert typ == 1
        assert life == 0

    def test_make_cell_fire(self):
        """Test creating a fire cell."""
        result = make_cell(4)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF

        assert typ == 4
        # Fire should have default flame life
        assert life == 24  # default flame life

    def test_make_cell_water(self):
        """Test creating a water cell."""
        result = make_cell(2)
        typ = result & 0xFF
        life = (result >> 8) & 0xFF

        assert typ == 2
        assert life == 0

    def test_make_cell_uses_particle_defaults(self):
        """Test that make_cell uses default values from PARTICLES dict."""
        # Test with a material that has non-zero default life
        result = make_cell(4)  # fire
        life = (result >> 8) & 0xFF
        assert life == PARTICLES[4]['dfl']

    def test_make_cell_invalid_type(self):
        """Test creating a cell with invalid type raises ValueError."""
        # Material ID 100 is not defined, should raise ValueError
        with pytest.raises(ValueError):
            make_cell(100)


class TestReadStats:
    """Test the read_stats function."""

    def test_read_stats_empty_grid(self):
        """Test reading stats from empty grid."""
        # Create a mock buffer with all air cells
        mock_buf = MagicMock()
        mock_buf.read.return_value = np.full(100, make_cell(0), dtype=np.uint32).tobytes()

        stats = read_stats(mock_buf)

        assert stats['water'] == 0
        assert stats['steam'] == 0
        assert stats['fire'] == 0
        # avg_temp is 0.0 because temperature is no longer in cell buffer
        assert stats['avg_temp'] == 0.0

    def test_read_stats_water_cells(self):
        """Test reading stats with water cells."""
        # Create grid with water cells
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:10] = make_cell(2)  # 10 water cells

        mock_buf = MagicMock()
        mock_buf.read.return_value = grid.tobytes()

        stats = read_stats(mock_buf)

        assert stats['water'] == 10
        assert stats['steam'] == 0
        assert stats['fire'] == 0

    def test_read_stats_steam_cells(self):
        """Test reading stats with steam cells."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:5] = make_cell(14)  # 5 steam cells

        mock_buf = MagicMock()
        mock_buf.read.return_value = grid.tobytes()

        stats = read_stats(mock_buf)

        assert stats['water'] == 0
        assert stats['steam'] == 5
        assert stats['fire'] == 0

    def test_read_stats_fire_cells(self):
        """Test reading stats with fire cells."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:3] = make_cell(4)  # 3 fire cells

        mock_buf = MagicMock()
        mock_buf.read.return_value = grid.tobytes()

        stats = read_stats(mock_buf)

        assert stats['water'] == 0
        assert stats['steam'] == 0
        assert stats['fire'] == 3

    def test_read_stats_mixed_cells(self):
        """Test reading stats with mixed cell types."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:5] = make_cell(2)   # 5 water
        grid[5:8] = make_cell(14)  # 3 steam
        grid[8:10] = make_cell(4)   # 2 fire

        mock_buf = MagicMock()
        mock_buf.read.return_value = grid.tobytes()

        stats = read_stats(mock_buf)

        assert stats['water'] == 5
        assert stats['steam'] == 3
        assert stats['fire'] == 2

    def test_read_stats_average_temperature(self):
        """Test average temperature field is 0 (temp is in float textures)."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        mock_buf = MagicMock()
        mock_buf.read.return_value = grid.tobytes()

        stats = read_stats(mock_buf)

        # Temperature is no longer stored in cell uint32
        assert stats['avg_temp'] == 0.0
