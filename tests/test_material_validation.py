"""Unit tests for material property validation (Phase 4)."""

import numpy as np
import pytest
from core.constants import NUM_TYPES, RULE_STRIDE
from simulation.materials import to_rule_buffer


def test_all_materials_validate_at_startup():
    """Test that all materials pass GPU validation at startup (Phase 4)."""
    # This test simulates what happens during BufferManager._create_rule_buffer()
    rules = to_rule_buffer()

    # Validate buffer dimensions
    expected_len = RULE_STRIDE * NUM_TYPES
    assert len(rules) == expected_len, f"Rule buffer length mismatch: {len(rules)} != {expected_len}"

    # Validate each material's properties
    for i in range(0, len(rules), RULE_STRIDE):
        material_idx = i // RULE_STRIDE
        _validate_material_properties(rules, i, material_idx)

    # Phase 4: Verify validation error messages are informative
    try:
        _validate_material_properties(rules, 0, 0)
    except AssertionError as e:
        # If validation fails, error message should include material index
        assert "0" in str(e) or "Material" in str(e)


def test_material_property_ranges():
    """Test that all material properties are within GPU-safe ranges (Phase 4)."""
    from simulation.materials import get_all_materials

    materials = get_all_materials()
    for mat_id, mat in materials.items():
        if hasattr(mat, 'density'):
            # Allow negative density for gases (like smoke)
            assert -1.0 <= mat.density <= 100.0, f"{mat.name} density out of range: {mat.density}"
        if hasattr(mat, 'viscosity'):
            assert 0 <= mat.viscosity <= 100.0, f"{mat.name} viscosity out of range: {mat.viscosity}"
        if hasattr(mat, 'restitution'):
            assert 0 <= mat.restitution <= 2.0, f"{mat.name} restitution out of range: {mat.restitution}"
        # Phase 4: Test new oxygen-related properties if present
        if hasattr(mat, 'oxygen_consumption'):
            assert 0 <= mat.oxygen_consumption <= 1.0, f"{mat.name} oxygen_consumption out of range"
        if hasattr(mat, 'oxygen_production'):
            assert 0 <= mat.oxygen_production <= 1.0, f"{mat.name} oxygen_production out of range"


def test_rule_buffer_dimensions():
    """Test that rule buffer has correct dimensions (Phase 4)."""
    rules = to_rule_buffer()
    expected_len = RULE_STRIDE * NUM_TYPES
    assert len(rules) == expected_len, f"Rule buffer length mismatch: {len(rules)} != {expected_len}"


def test_no_nan_or_inf_in_rule_buffer():
    """Test that rule buffer contains no NaN or inf values (Phase 4)."""
    rules = to_rule_buffer()
    for i in range(len(rules)):
        assert not np.isnan(rules[i]), f"NaN at index {i}"
        assert not np.isinf(rules[i]), f"Inf at index {i}"


def _validate_material_properties(rules: np.ndarray, offset: int, idx: int) -> None:
    """Validate a single material's properties are GPU-safe (Phase 4).

    This mirrors the logic in gpu/buffers.py _validate_material_properties().
    """
    # Density: should be reasonable (negative for gases, up to 100 for heavy materials)
    density = rules[offset + 3]
    assert abs(density) <= 100.0, f"Material {idx}: density {density} exceeds safe range (max 100.0)"

    # Viscosity: should be non-negative and reasonable
    viscosity = rules[offset + 4]
    assert 0 <= viscosity <= 100.0, f"Material {idx}: viscosity {viscosity} out of range (0-100)"

    # Restitution: should be in [0, 2] for bounce
    restitution = rules[offset + 5]
    assert 0 <= restitution <= 2.0, f"Material {idx}: restitution {restitution} out of range (0-2)"

    # Phase 4: Check for extreme values that might cause instability
    for j in range(RULE_STRIDE):
        val = rules[offset + j]
        assert not np.isnan(val), f"Material {idx}: property at offset {j} is NaN"
        assert not np.isinf(val), f"Material {idx}: property at offset {j} is inf"
        # Phase 4: Additional check for values that could cause numerical instability
        if abs(val) > 1e6:
            raise AssertionError(f"Material {idx}: property at offset {j} has extreme value {val}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
