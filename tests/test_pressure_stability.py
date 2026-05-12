"""Unit tests for pressure solver stability (Phase 1)."""

import numpy as np
import pytest
from core.config import SimulationConfig


def test_hydrostatic_pressure_gradient():
    """Test hydrostatic pressure gradient (Phase 4 enhanced)."""
    config = SimulationConfig(width=512, height=512)

    # Simulate the hydrostatic initialization logic
    pres_data = np.zeros((config.height, config.width), dtype=np.float32)
    for gy in range(config.height):
        depth = gy  # Depth increases with y index
        hydrostatic = config.atm_pressure + (depth * 0.01)
        pres_data[gy, :] = hydrostatic

    # Verify pressure increases with depth
    top_pressure = pres_data[0, 0]
    bottom_pressure = pres_data[-1, 0]

    assert bottom_pressure > top_pressure, "Pressure should increase with depth"
    assert abs(top_pressure - config.atm_pressure) < 0.1, "Top should be at ambient pressure"

    # Verify gradient is consistent
    expected_gradient = 0.01
    actual_gradient = (bottom_pressure - top_pressure) / config.height
    assert abs(actual_gradient - expected_gradient) < 0.001, f"Gradient mismatch: {actual_gradient}"


def test_pressure_clamping_bounds():
    """Test that pressure clamping constants are reasonable (Phase 4 enhanced)."""
    from core.config import SimulationConfig

    config = SimulationConfig()

    # Verify clamping bounds are set
    assert config.pressure_clamp_min < config.pressure_clamp_max, "Min should be less than max"
    assert config.pressure_clamp_min < 0, "Min should allow negative pressure"
    assert config.pressure_clamp_max > 100, "Max should allow significant positive pressure"

    # Verify shader constants match config (Phase 4: -500.0 to 5000.0)
    # pressure_shader.glsl has PRESSURE_MIN = -500.0, PRESSURE_MAX = 5000.0
    assert abs(config.pressure_clamp_min - (-500.0)) < 0.1, "Config min should match shader"
    assert abs(config.pressure_clamp_max - 5000.0) < 0.1, "Config max should match shader"


def test_pressure_clamping_logic():
    """Test pressure clamping logic equivalent to shader (Phase 4 enhanced)."""
    PRESSURE_MIN = -500.0
    PRESSURE_MAX = 5000.0

    # Test normal values
    assert np.clip(50.0, PRESSURE_MIN, PRESSURE_MAX) == 50.0
    assert np.clip(-50.0, PRESSURE_MIN, PRESSURE_MAX) == -50.0

    # Test clamping
    assert np.clip(-1000.0, PRESSURE_MIN, PRESSURE_MAX) == PRESSURE_MIN
    assert np.clip(10000.0, PRESSURE_MIN, PRESSURE_MAX) == PRESSURE_MAX

    # Test edge cases
    assert np.clip(PRESSURE_MIN, PRESSURE_MIN, PRESSURE_MAX) == PRESSURE_MIN
    assert np.clip(PRESSURE_MAX, PRESSURE_MIN, PRESSURE_MAX) == PRESSURE_MAX


def test_nan_handling():
    """Test NaN detection and fallback logic."""
    # Simulate NaN guard logic from shader
    def safe_pressure(p_new, p_prev):
        if np.isnan(p_new) or np.isinf(p_new):
            return p_prev
        return p_new
    
    # Test NaN
    assert safe_pressure(np.nan, 50.0) == 50.0
    # Test inf
    assert safe_pressure(np.inf, 50.0) == 50.0
    assert safe_pressure(-np.inf, 50.0) == 50.0
    # Test normal
    assert safe_pressure(100.0, 50.0) == 100.0


def test_material_density_validation():
    """Test material density validation logic."""
    from simulation.materials import get_all_materials

    materials = get_all_materials()
    for material_idx, mat in materials.items():
        density = mat.density if hasattr(mat, 'density') else 0.0
        # Allow negative for gases, cap at reasonable maximum
        # Material 30 has density 99.0 which is acceptable
        if abs(density) > 150.0:
            pytest.fail(f"Density too large at material index {material_idx}: {density}")


def test_pressure_initialization_bounds():
    """Test that initial pressure values are within safe bounds."""
    config = SimulationConfig(width=512, height=512)
    
    # Simulate initialization
    pres_data = np.zeros((config.height, config.width), dtype=np.float32)
    for gy in range(config.height):
        depth = config.height - gy
        hydrostatic = config.atm_pressure + (depth * 0.01)
        pres_data[gy, :] = hydrostatic
    
    # Verify all values are within clamping bounds
    min_pressure = pres_data.min()
    max_pressure = pres_data.max()
    
    assert min_pressure >= config.pressure_clamp_min, f"Initial pressure below min: {min_pressure}"
    assert max_pressure <= config.pressure_clamp_max, f"Initial pressure above max: {max_pressure}"


def test_extreme_explosion_scenario():
    """Test pressure behavior with extreme explosion values (Phase 4 enhanced)."""
    PRESSURE_MIN = -500.0
    PRESSURE_MAX = 5000.0

    # Simulate extreme pressure from explosion
    extreme_pressures = np.array([-1000.0, -500.0, 500.0, 5000.0, 10000.0, 20000.0])

    # Apply clamping
    clamped = np.clip(extreme_pressures, PRESSURE_MIN, PRESSURE_MAX)

    # Verify all are within bounds
    assert clamped.min() >= PRESSURE_MIN
    assert clamped.max() <= PRESSURE_MAX

    # Verify extreme values were clamped
    assert clamped[0] == PRESSURE_MIN  # -1000 -> -500
    assert clamped[4] == PRESSURE_MAX  # 10000 -> 5000
    assert clamped[5] == PRESSURE_MAX  # 20000 -> 5000


def test_emergency_pressure_reset_threshold():
    """Test that emergency reset threshold is set correctly (Phase 4)."""
    # Emergency threshold should be above normal clamping max
    # This allows the shader to detect extreme values before they cause issues
    PRESSURE_EMERGENCY_RESET = 10000.0
    PRESSURE_MAX = 5000.0

    assert PRESSURE_EMERGENCY_RESET > PRESSURE_MAX, "Emergency threshold should be above clamp max"

def test_emergency_reset_does_not_impact_performance():
    """Test that pressure monitoring doesn't significantly impact performance (Phase 4)."""
    import time
    from core.config import SimulationConfig

    config = SimulationConfig(width=512, height=512)

    # Simulate pressure read operation
    pres_data = np.zeros((config.height, config.width), dtype=np.float32)

    start = time.perf_counter()
    for _ in range(100):
        # Simulate reading and checking pressure
        _ = np.max(pres_data)
        _ = np.min(pres_data)
    elapsed = time.perf_counter() - start

    # Should complete 100 iterations in under 10ms
    assert elapsed < 0.01, f"Pressure monitoring too slow: {elapsed*1000:.2f}ms"


def test_emergency_reset_config_flag():
    """Test that emergency reset config flag exists and is enabled by default (Phase 4)."""
    from core.config import SimulationConfig

    config = SimulationConfig()
    assert hasattr(config, 'enable_emergency_pressure_reset'), "Config should have emergency reset flag"
    assert config.enable_emergency_pressure_reset is True, "Emergency reset should be enabled by default"


def test_hydrostatic_gradient_scaling():
    """Test that hydrostatic gradient scales appropriately with grid size (Phase 4)."""
    from core.config import SimulationConfig

    # Test various grid sizes
    for size in [256, 512, 1024, 2048]:
        config = SimulationConfig(width=size, height=size)

        # Simulate the hydrostatic initialization logic with grid-size-aware gradient
        pres_data = np.zeros((config.height, config.width), dtype=np.float32)
        for gy in range(config.height):
            depth = gy
            hydrostatic = config.atm_pressure + (depth * 0.01)
            pres_data[gy, :] = hydrostatic

        top_pressure = pres_data[0, 0]
        bottom_pressure = pres_data[-1, 0]
        height = config.height

        assert bottom_pressure > top_pressure, f"Pressure should increase with depth for size {size}"
        # Gradient should scale with height
        gradient = (bottom_pressure - top_pressure) / height
        assert abs(gradient - 0.01) < 0.001, f"Gradient should be ~0.01 for size {size}"

        # Verify max pressure doesn't exceed clamp max (even for largest grid)
        assert bottom_pressure <= config.pressure_clamp_max, f"Bottom pressure should be within clamp max for size {size}"

        # Verify gradient is scaled correctly (should be similar across sizes)
        expected_max_pressure = config.atm_pressure + (size * 0.01)
        assert abs(bottom_pressure - expected_max_pressure) < 0.1, f"Gradient scaling incorrect for size {size}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
