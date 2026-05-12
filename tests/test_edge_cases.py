"""Edge-case tests (Phase 4)."""

import pytest
from core.config import SimulationConfig


class TestEmptyGridStability:
    """Test empty grid stability (Phase 4)."""

    def test_empty_grid_config(self):
        """Empty grid configuration should be valid (Phase 4)."""
        config = SimulationConfig(width=256, height=256)
        errors = config.validate()
        assert len(errors) == 0, f"Empty grid config should be valid, got errors: {errors}"


class TestBoundaryConditions:
    """Test boundary condition tests (Phase 4)."""

    def test_minimum_grid_size(self):
        """Minimum grid size should be valid (Phase 4)."""
        from core.constants import MIN_GRID_SIZE
        config = SimulationConfig(width=MIN_GRID_SIZE, height=MIN_GRID_SIZE)
        errors = config.validate()
        assert len(errors) == 0, f"Minimum grid size should be valid, got errors: {errors}"

    def test_maximum_grid_size(self):
        """Maximum grid size should be valid (Phase 4)."""
        from core.constants import MAX_GRID_SIZE
        config = SimulationConfig(width=MAX_GRID_SIZE, height=MAX_GRID_SIZE)
        errors = config.validate()
        # May have VRAM warnings but should not have hard errors
        hard_errors = [e for e in errors if "must not exceed" in e]
        assert len(hard_errors) == 0, f"Maximum grid size should be valid, got errors: {hard_errors}"

    def test_grid_size_exceeds_maximum(self):
        """Grid size exceeding maximum should be rejected (Phase 4)."""
        from core.constants import MAX_GRID_SIZE
        config = SimulationConfig(width=MAX_GRID_SIZE + 1, height=MAX_GRID_SIZE + 1)
        errors = config.validate()
        assert any("must not exceed" in e for e in errors), "Should reject grid size exceeding maximum"

    def test_grid_size_below_minimum(self):
        """Grid size below minimum should be rejected (Phase 4)."""
        from core.constants import MIN_GRID_SIZE
        config = SimulationConfig(width=MIN_GRID_SIZE - 1, height=MIN_GRID_SIZE - 1)
        errors = config.validate()
        assert any("must be at least" in e for e in errors), "Should reject grid size below minimum"


class TestExtremeParameterValues:
    """Test extreme parameter values (Phase 4)."""

    def test_extreme_pressure_iterations(self):
        """Extreme pressure iterations should be handled (Phase 4)."""
        from core.constants import MIN_PRESSURE_ITERATIONS, MAX_PRESSURE_ITERATIONS

        # Test minimum
        config = SimulationConfig(pressure_iterations=MIN_PRESSURE_ITERATIONS)
        errors = config.validate()
        assert len(errors) == 0 or all("pressure_iterations" not in e for e in errors)

        # Test maximum
        config = SimulationConfig(pressure_iterations=MAX_PRESSURE_ITERATIONS)
        errors = config.validate()
        assert len(errors) == 0 or all("pressure_iterations" not in e for e in errors)

        # Test exceeding maximum
        config = SimulationConfig(pressure_iterations=MAX_PRESSURE_ITERATIONS + 1)
        errors = config.validate()
        assert any("pressure_iterations" in e for e in errors)

    def test_extreme_substeps(self):
        """Extreme substeps should be handled (Phase 4)."""
        from core.constants import MIN_SUBSTEPS, MAX_SUBSTEPS

        # Test minimum
        config = SimulationConfig(sim_substeps=MIN_SUBSTEPS)
        errors = config.validate()
        assert len(errors) == 0 or all("sim_substeps" not in e for e in errors)

        # Test maximum
        config = SimulationConfig(sim_substeps=MAX_SUBSTEPS)
        errors = config.validate()
        assert len(errors) == 0 or all("sim_substeps" not in e for e in errors)

        # Test exceeding maximum
        config = SimulationConfig(sim_substeps=MAX_SUBSTEPS + 1)
        errors = config.validate()
        assert any("sim_substeps" in e for e in errors)

    def test_extreme_window_size(self):
        """Extreme window sizes should be handled (Phase 4)."""
        from core.constants import MIN_WINDOW_SIZE

        # Test below minimum
        config = SimulationConfig(window_width=MIN_WINDOW_SIZE - 1, window_height=MIN_WINDOW_SIZE - 1)
        errors = config.validate()
        assert any("Window size must be at least" in e for e in errors)

        # Test very large window size
        config = SimulationConfig(window_width=4096, window_height=4096)
        errors = config.validate()
        # Window size has no maximum, should not have hard errors
        hard_errors = [e for e in errors if "Window size" in e and "must not" in e]
        assert len(hard_errors) == 0


class TestSystemToggleStability:
    """Test rapid system toggle stability (Phase 4)."""

    def test_all_systems_off(self):
        """All systems disabled should be valid (Phase 4)."""
        config = SimulationConfig(
            enable_electricity=False,
            enable_biology=False,
            enable_weather=False,
            no_turbulence=True,
            no_wet_dry=True,
            no_thermal=True,
            no_acoustics=True,
            no_bloom=True,
        )
        errors = config.validate()
        assert len(errors) == 0, f"All systems off should be valid, got errors: {errors}"

    def test_all_systems_on(self):
        """All systems enabled should be valid (Phase 4)."""
        config = SimulationConfig(
            enable_electricity=True,
            enable_biology=True,
            enable_weather=True,
            no_turbulence=False,
            no_wet_dry=False,
            no_thermal=False,
            no_acoustics=False,
            no_bloom=False,
        )
        errors = config.validate()
        assert len(errors) == 0 or all("enable" not in e for e in errors)


class TestParameterRangeValidation:
    """Test parameter range validation (Phase 4)."""

    def test_charge_parameters(self):
        """Charge parameters should be within valid ranges (Phase 4)."""
        config = SimulationConfig(
            enable_electricity=True,
            charge_decay=0.5,
            max_charge=2000.0,
            breakdown_threshold=600.0,
            arc_temp_delta=300.0,
            arc_pressure_pulse=10.0,
        )
        errors = config.validate()
        # These are user parameters, should not cause validation errors
        assert len(errors) == 0 or all("charge" not in e.lower() for e in errors)

    def test_biology_parameters(self):
        """Biology parameters should be within valid ranges (Phase 4)."""
        config = SimulationConfig(
            enable_biology=True,
            nutrient_diffuse_rate=0.8,
            moisture_diffuse_rate=0.6,
            growth_rate=0.2,
            decay_rate=0.1,
            transpiration_rate=0.1,
        )
        errors = config.validate()
        # These are user parameters, should not cause validation errors
        assert len(errors) == 0 or all("nutrient" not in e.lower() and "moisture" not in e.lower() for e in errors)

    def test_weather_parameters(self):
        """Weather parameters should be within valid ranges (Phase 4)."""
        config = SimulationConfig(
            enable_weather=True,
            humidity_diffuse_rate=0.8,
            evaporation_rate=0.2,
            condensation_rate=0.5,
            saturation_threshold=150.0,
            rain_speed=3.0,
        )
        errors = config.validate()
        # These are user parameters, should not cause validation errors
        assert len(errors) == 0 or all("humidity" not in e.lower() and "evaporation" not in e.lower() for e in errors)

    def test_bloom_parameters(self):
        """Bloom parameters should be within valid ranges (Phase 4)."""
        config = SimulationConfig(
            bloom_enabled=True,
            bloom_threshold=0.8,
            bloom_intensity=1.0,
            bloom_radius=1.5,
            bloom_quality="high",
        )
        errors = config.validate()
        # These are user parameters, should not cause validation errors
        assert len(errors) == 0 or all("bloom" not in e.lower() for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
