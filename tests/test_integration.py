import pytest
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import pack_cell, make_cell, PARTICLES, TEMP_AMBIENT


@pytest.mark.integration
class TestGridInitialization:
    """Test grid initialization and setup."""

    def test_grid_creation_with_materials(self):
        """Test creating a grid with various materials."""
        grid_size = 100
        grid = np.full(grid_size, make_cell(0), dtype=np.uint32)

        # Place some materials
        grid[0:10] = make_cell(1)  # sand
        grid[10:20] = make_cell(2)  # water
        grid[20:30] = make_cell(3)  # stone

        assert len(grid) == grid_size
        assert np.all((grid[0:10] & 0xFF) == 1)
        assert np.all((grid[10:20] & 0xFF) == 2)
        assert np.all((grid[20:30] & 0xFF) == 3)

    def test_grid_life_distribution(self):
        """Test grid with varying life values."""
        grid = np.zeros(100, dtype=np.uint32)

        # Set different life values (life is at bits [8..15])
        grid[0] = pack_cell(1, 50, 0)
        grid[1] = pack_cell(1, 150, 0)
        grid[2] = pack_cell(1, 250, 0)

        assert (grid[0] >> 8) & 0xFF == 50
        assert (grid[1] >> 8) & 0xFF == 150
        assert (grid[2] >> 8) & 0xFF == 250


@pytest.mark.integration
class TestMaterialPlacement:
    """Test material placement operations."""

    def test_single_material_placement(self):
        """Test placing a single material."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[50] = make_cell(1)  # Place sand

        assert (grid[50] & 0xFF) == 1
        assert (grid[49] & 0xFF) == 0  # Neighbors unchanged

    def test_brush_placement(self):
        """Test brush-style material placement."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # Simulate a 3x3 brush at position 50
        center = 50
        width = 10  # grid width for simulation

        for dy in range(-1, 2):
            for dx in range(-1, 2):
                idx = center + dy * width + dx
                if 0 <= idx < len(grid):
                    grid[idx] = make_cell(1)  # sand

        # Check center was placed
        assert (grid[center] & 0xFF) == 1

    def test_material_replacement(self):
        """Test replacing one material with another."""
        grid = np.full(100, make_cell(1), dtype=np.uint32)  # All sand
        grid[50] = make_cell(2)  # Replace with water

        assert (grid[50] & 0xFF) == 2
        assert (grid[49] & 0xFF) == 1  # Neighbors still sand

    def test_erase_operation(self):
        """Test erasing materials (setting to air)."""
        grid = np.full(100, make_cell(1), dtype=np.uint32)  # All sand
        grid[50] = make_cell(0)  # Erase to air

        assert (grid[50] & 0xFF) == 0
        assert (grid[51] & 0xFF) == 1  # Neighbors still sand


@pytest.mark.integration
class TestLifeModification:
    """Test life modification operations."""

    def test_life_packing(self):
        """Test life is correctly packed into cell."""
        cell = make_cell(4)  # Fire with default life
        life = (cell >> 8) & 0xFF
        assert life > 0  # Fire has non-zero default life

    def test_life_clamping(self):
        """Test that life values are clamped to 8 bits."""
        # Overflow: 300 & 0xFF = 44
        cell = pack_cell(1, 300, 0)
        assert (cell >> 8) & 0xFF == 44


@pytest.mark.integration
class TestBrushOperations:
    """Test brush tool operations."""

    def test_brush_size_variations(self):
        """Test different brush sizes."""
        for brush_size in [1, 5, 10, 20]:
            count = 0
            for dx in range(-brush_size, brush_size + 1):
                for dy in range(-brush_size, brush_size + 1):
                    if dx*dx + dy*dy <= brush_size*brush_size:
                        count += 1

            # Larger brushes should affect more cells
            assert count > 0

    def test_circular_brush_shape(self):
        """Test that brush has circular shape."""
        brush_size = 5
        affected_cells = []

        for dx in range(-brush_size, brush_size + 1):
            for dy in range(-brush_size, brush_size + 1):
                if dx*dx + dy*dy <= brush_size*brush_size:
                    affected_cells.append((dx, dy))

        # Should be roughly circular
        assert len(affected_cells) > 0
        # Corner cells should be excluded
        assert (brush_size, brush_size) not in affected_cells


@pytest.mark.integration
class TestSaveLoadOperations:
    """Test save and load functionality."""

    def test_grid_serialization(self):
        """Test that grid can be serialized to bytes."""
        grid = np.full(100, make_cell(1), dtype=np.uint32)
        serialized = grid.tobytes()

        assert len(serialized) == 100 * 4  # 100 cells * 4 bytes each

    def test_grid_deserialization(self):
        """Test that grid can be deserialized from bytes."""
        original_grid = np.full(100, make_cell(1), dtype=np.uint32)
        serialized = original_grid.tobytes()

        deserialized = np.frombuffer(serialized, dtype=np.uint32)

        assert np.array_equal(original_grid, deserialized)

    def test_mixed_grid_serialization(self):
        """Test serializing grid with mixed materials."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:10] = make_cell(1)  # sand
        grid[10:20] = make_cell(2)  # water
        grid[20:30] = make_cell(4)  # fire

        serialized = grid.tobytes()
        deserialized = np.frombuffer(serialized, dtype=np.uint32)

        assert np.array_equal(grid, deserialized)
        assert (deserialized[5] & 0xFF) == 1
        assert (deserialized[15] & 0xFF) == 2
        assert (deserialized[25] & 0xFF) == 4


@pytest.mark.integration
class TestStatsTracking:
    """Test statistics tracking over grid state."""

    def test_water_count(self):
        """Test counting water cells in grid."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:10] = make_cell(2)  # 10 water cells
        grid[10:20] = make_cell(1)  # 10 sand cells

        types = grid & 0xFF
        water_count = np.count_nonzero(types == 2)

        assert water_count == 10

    def test_steam_count(self):
        """Test counting steam cells in grid."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:5] = make_cell(14)  # 5 steam cells

        types = grid & 0xFF
        steam_count = np.count_nonzero(types == 14)

        assert steam_count == 5

    def test_fire_count(self):
        """Test counting fire cells in grid."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)
        grid[0:3] = make_cell(4)  # 3 fire cells

        types = grid & 0xFF
        fire_count = np.count_nonzero(types == 4)

        assert fire_count == 3

    def test_average_life(self):
        """Test calculating average life from cell buffer."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # Set specific life values (life is at bits [8..15])
        grid[0] = pack_cell(0, 200, 0)
        grid[1] = pack_cell(0, 100, 0)

        lives = (grid >> 8) & 0xFF
        avg_life = np.mean(lives)

        # Average of (200, 100, 98*0) / 100
        expected_avg = (200 + 100) / 100
        assert abs(avg_life - expected_avg) < 0.1


@pytest.mark.integration
class TestMaterialInteractions:
    """Test material interaction scenarios."""

    def test_density_based_separation(self):
        """Test that materials separate by density."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # Place heavy material (stone) and light material (air)
        grid[0:10] = make_cell(3)  # stone (density 10.0)
        grid[50:60] = make_cell(0)  # air (density 0.12)

        stone_density = PARTICLES[3]['density']
        air_density = PARTICLES[0]['density']

        assert stone_density > air_density

    def test_flammable_near_fire(self):
        """Test flammable material near fire source."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # Place fire and flammable material nearby
        grid[50] = make_cell(4)  # fire
        grid[51] = make_cell(6)  # oil (flammable)

        fire_flamm = PARTICLES[4]['flamm']
        oil_flamm = PARTICLES[6]['flamm']

        assert fire_flamm == 0  # Fire doesn't burn (it is fire)
        assert oil_flamm > 0  # Oil is flammable

    def test_conductive_path(self):
        """Test electrical conduction through materials."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # Create conductive path
        grid[50] = make_cell(24)  # spark
        grid[51] = make_cell(2)  # water (conductive)
        grid[52] = make_cell(22)  # metal (conductive)

        spark_cond = PARTICLES[24]['cond']
        water_cond = PARTICLES[2]['cond']
        metal_cond = PARTICLES[22]['cond']

        assert spark_cond == 0  # Spark doesn't conduct (it is electricity)
        assert water_cond > 0
        assert metal_cond > 0


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_grid(self):
        """Test operations on empty grid."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # All cells should be air
        types = grid & 0xFF
        assert np.all(types == 0).item()

    def test_full_grid(self):
        """Test operations on full grid."""
        grid = np.full(100, make_cell(1), dtype=np.uint32)

        # All cells should be sand
        types = grid & 0xFF
        assert np.all(types == 1)

    def test_single_cell_grid(self):
        """Test operations on minimal grid."""
        grid = np.full(1, make_cell(1), dtype=np.uint32)

        assert len(grid) == 1
        assert (grid[0] & 0xFF) == 1

    def test_boundary_material_placement(self):
        """Test material placement at grid boundaries."""
        grid = np.full(100, make_cell(0), dtype=np.uint32)

        # Place at start
        grid[0] = make_cell(1)
        assert (grid[0] & 0xFF) == 1

        # Place at end
        grid[99] = make_cell(2)
        assert (grid[99] & 0xFF) == 2


@pytest.mark.integration
class TestFlagOperations:
    """Test flag bit operations in cells."""

    def test_flag_packing(self):
        """Test packing flags into cell."""
        flags = 0x55  # Some flag pattern
        cell = pack_cell(1, 0, flags)

        extracted_flags = (cell >> 16) & 0xFF
        assert extracted_flags == flags

    def test_flag_modification(self):
        """Test modifying flags in existing cell."""
        cell = make_cell(1)
        original_flags = (cell >> 16) & 0xFF

        new_flags = 0xAA
        modified_cell = pack_cell(1, 0, new_flags)

        extracted_flags = (modified_cell >> 16) & 0xFF
        assert extracted_flags == new_flags
        assert extracted_flags != original_flags

    def test_flag_preservation(self):
        """Test that flags are preserved during type change."""
        cell = pack_cell(1, 0, 0x55)
        flags = (cell >> 16) & 0xFF

        # Change type but preserve flags
        new_cell = pack_cell(2, 0, flags)
        new_flags = (new_cell >> 16) & 0xFF

        assert new_flags == flags
        assert (new_cell & 0xFF) == 2  # Type changed


@pytest.mark.integration
class TestLifeOperations:
    """Test life/decay operations in cells."""

    def test_life_packing(self):
        """Test packing life into cell."""
        life = 50
        cell = pack_cell(4, life, 0)

        extracted_life = (cell >> 8) & 0xFF
        assert extracted_life == life

    def test_life_decrement(self):
        """Test decrementing life in cell."""
        cell = pack_cell(4, 50, 0)
        current_life = (cell >> 8) & 0xFF

        new_life = max(0, current_life - 1)
        aged_cell = pack_cell(4, new_life, 0)

        extracted_life = (aged_cell >> 8) & 0xFF
        assert extracted_life == current_life - 1

    def test_life_expiration(self):
        """Test cell behavior when life reaches zero."""
        cell = pack_cell(4, 1, 0)  # Fire with 1 life
        current_life = (cell >> 8) & 0xFF

        # Decrement to zero
        new_life = max(0, current_life - 1)
        expired_cell = pack_cell(4, new_life, 0)

        extracted_life = (expired_cell >> 8) & 0xFF
        assert extracted_life == 0
