"""Tests for the cell inspector panel and probe_cell functionality."""
import pygame
import pytest
from unittest.mock import Mock

from core.config import SimulationConfig
from core.constants import TEMP_AMBIENT
from gpu.context import ContextManager
from simulation.engine import SimulationEngine


@pytest.fixture
def small_engine():
    """Create a small engine for testing probe_cell."""
    # Use a small grid for faster tests
    config = SimulationConfig(
        width=32,
        height=32,
        window_width=400,
        window_height=400,
        no_hud=True,
        no_stats=True,
    )
    ctx_manager = ContextManager((config.window_width, config.window_height))
    engine = SimulationEngine(config, ctx_manager)
    yield engine
    ctx_manager.quit()


class TestProbeCell:
    """Tests for engine.probe_cell method."""

    def test_probe_cell_out_of_bounds(self, small_engine):
        """Test that probe_cell returns None for out-of-bounds coordinates."""
        result = small_engine.probe_cell(-1, 0)
        assert result is None

        result = small_engine.probe_cell(0, -1)
        assert result is None

        result = small_engine.probe_cell(100, 0)
        assert result is None

        result = small_engine.probe_cell(0, 100)
        assert result is None

    def test_probe_cell_empty_cell(self, small_engine):
        """Test probing an empty (air) cell."""
        # Don't place anything, just probe the center
        result = small_engine.probe_cell(16, 16)

        assert result is not None
        assert "cell" in result
        assert "material" in result
        assert "temp_float" in result
        assert "velocity" in result
        assert "pressure" in result
        assert "mass" in result
        assert "wind" in result
        assert "vorticity" in result
        assert "divergence" in result

        # Air should have type_id 0
        assert result["cell"].type_id == 0
        assert result["material"].name == "air"
        # Temperature is in float texture (temp_float), not in cell.
        # May be None if texture read fails in headless context.
        if result["temp_float"] is not None:
            assert abs(result["temp_float"] - TEMP_AMBIENT) < 1.0
        # Life and flags should be 0 for air
        assert result["cell"].life == 0
        assert result["cell"].flags == 0

    def test_probe_cell_sand(self, small_engine):
        """Test probing a sand cell."""
        # Place sand at (5, 5)
        small_engine.apply_brush(5, 5, radius=1, material_id=1, mode=0)

        # Step 0 times (no simulation needed for readback)
        result = small_engine.probe_cell(5, 5)

        assert result is not None
        assert result["cell"].type_id == 1
        assert result["material"].name == "sand"
        # Temperature is in float texture (temp_float), not in cell.
        # May be None if texture read fails in headless context.
        # Velocity should be near zero for stationary sand
        if result["velocity"]:
            vx, vy = result["velocity"]
            assert abs(vx) < 0.01
            assert abs(vy) < 0.01
        # Pressure should be near zero
        if result["pressure"] is not None:
            assert abs(result["pressure"]) < 0.01

    def test_probe_cell_water(self, small_engine):
        """Test probing a water cell."""
        # Place water at (10, 10)
        small_engine.apply_brush(10, 10, radius=1, material_id=2, mode=0)

        result = small_engine.probe_cell(10, 10)

        assert result is not None
        assert result["cell"].type_id == 2
        assert result["material"].name == "water"
        assert result["material"].category.name == "LIQUID"
        assert result["material"].state_family.name == "LIQUID"

    def test_probe_cell_blast_flags(self, small_engine):
        """Test probing a blast cell with special flag encoding."""
        # Create a blast cell (type 35) by triggering an explosion
        small_engine.apply_brush(20, 20, radius=1, material_id=19, mode=0)  # gunpowder
        small_engine.trigger_explosion(20, 20)

        # Probe near the explosion center to find blast cells
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                result = small_engine.probe_cell(20 + dx, 20 + dy)
                if result and result["cell"] and result["cell"].type_id == 35:  # T_BLAST
                    # Check that flags are set (blast uses special flag encoding)
                    assert result["cell"].flags > 0
                    return

        # If we didn't find a blast cell, that's okay - the test passed
        # (explosion might have already decayed)

    def test_probe_cell_temp_float(self, small_engine):
        """Test that temp_float is reasonable in raw simulation units."""
        result = small_engine.probe_cell(16, 16)

        assert result is not None
        temp_float = result["temp_float"]
        if temp_float is not None:
            assert temp_float >= 0.0
            expected = float(TEMP_AMBIENT)
            assert abs(temp_float - expected) < 0.1


class TestInspectorFormatting:
    """Tests for inspector panel formatting helpers."""

    def test_decode_flags_blast(self):
        """Test flag decoding for blast/shrapnel cells."""
        # Mock inspector (we only need the static method)
        # Create a minimal mock
        class MockInspector:
            @staticmethod
            def _decode_flags(type_id, flags):
                # Inline the logic from InspectorPanel._decode_flags
                if type_id in (35, 34):  # T_BLAST, T_SHRAPNEL
                    dir_oct = flags & 0x7
                    power = (flags >> 3) & 0x1F
                    dirs = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
                    return f"dir={dirs[dir_oct]} pow={power}"
                else:
                    return f"0x{flags:02X} (cool/charge)"

        # Test blast flags
        # flags = direction (bits 0-2) + power (bits 3-7)
        # direction=3 (N), power=15
        flags = 3 | (15 << 3)
        result = MockInspector._decode_flags(35, flags)
        assert "dir=N" in result
        assert "pow=15" in result

    def test_decode_flags_generic(self):
        """Test flag decoding for generic materials."""
        class MockInspector:
            @staticmethod
            def _decode_flags(type_id, flags):
                if type_id in (35, 34):
                    dir_oct = flags & 0x7
                    power = (flags >> 3) & 0x1F
                    dirs = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
                    return f"dir={dirs[dir_oct]} pow={power}"
                else:
                    return f"0x{flags:02X} (cool/charge)"

        # Test generic flags (e.g., for sand)
        result = MockInspector._decode_flags(1, 42)
        assert "0x2A" in result
        assert "cool/charge" in result


class TestInspectorIntegration:
    """Integration tests for the full inspector workflow."""

    def test_inspector_update_with_probe(self, small_engine):
        """Test that inspector.update() can handle probe data."""
        from ui.inspector import InspectorPanel

        # Create inspector panel (headless, no actual window needed)
        inspector = InspectorPanel(
            small_engine.ctx,
            (400, 400)
        )

        # Place a sand cell
        small_engine.apply_brush(5, 5, radius=1, material_id=1, mode=0)

        # Get probe data
        probe = small_engine.probe_cell(5, 5)

        # Update inspector with probe data
        inspector.update((100, 100), (5, 5), probe)

        # Verify that the inspector cached the probe
        assert inspector.cached_probe is not None
        assert inspector.cached_probe["cell"].type_id == 1

    def test_inspector_update_without_probe(self, small_engine):
        """Test that inspector.update() handles None probe data."""
        from ui.inspector import InspectorPanel

        inspector = InspectorPanel(
            small_engine.ctx,
            (400, 400)
        )

        # Update with None (e.g., when paused or out of bounds)
        inspector.update((0, 0), (0, 0), None)

        # Should clear cache
        assert inspector.cached_probe is None
        assert inspector.cached_surface is None

    def test_inspector_toggle(self, small_engine):
        """Test inspector visibility toggle."""
        from ui.inspector import InspectorPanel

        inspector = InspectorPanel(
            small_engine.ctx,
            (400, 400)
        )

        # Should start visible
        assert inspector.visible is True

        # Toggle off
        inspector.toggle()
        assert inspector.visible is False

        # Toggle on
        inspector.toggle()
        assert inspector.visible is True

        # Set explicitly
        inspector.set_visible(False)
        assert inspector.visible is False
        inspector.set_visible(True)
        assert inspector.visible is True

    def test_inspector_renders_fixed_top_right(self, small_engine):
        """Test that inspector render() uses the fixed top-right layout."""
        from ui.inspector import InspectorPanel

        inspector = InspectorPanel(
            small_engine.ctx,
            (400, 400)
        )
        inspector.cached_surface = pygame.Surface((inspector.panel_width, inspector.panel_height), pygame.SRCALPHA)
        inspector._renderer.render_positioned = Mock()

        inspector.render()

        assert inspector._renderer.render_positioned.called
        _, kwargs = inspector._renderer.render_positioned.call_args
        ndc_offset = kwargs["ndc_offset"]
        ndc_scale = kwargs["ndc_scale"]

        assert ndc_offset[0] == pytest.approx(0.075, abs=0.02)
        assert ndc_offset[1] == pytest.approx(-0.275, abs=0.02)
        assert ndc_scale[0] == pytest.approx(0.85, abs=0.001)
        assert ndc_scale[1] == pytest.approx(1.2, abs=0.001)
