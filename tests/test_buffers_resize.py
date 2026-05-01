"""Regression tests for BufferManager.resize()

The original resize() implementation was missing recreation of mass_a/b,
temp_a/b, and wind_tex textures. This caused crashes or corrupt data when
the grid was resized at runtime.

These tests verify that all expected buffers/textures exist after a resize
and have the correct dimensions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

moderngl = pytest.importorskip("moderngl")


@pytest.fixture
def gl_ctx():
    """Provide a standalone ModernGL context for buffer tests."""
    try:
        ctx = moderngl.create_standalone_context(require=430)
    except Exception as exc:
        pytest.skip(f"Cannot create standalone GL context: {exc}")
    yield ctx
    ctx.release()


def _all_required_attrs() -> list[str]:
    """All texture/buffer attributes that must exist after resize()."""
    return [
        "read_buf", "write_buf",
        "vel_a", "vel_b",
        "pres_a", "pres_b",
        "div_tex", "vorticity_tex",
        "mass_a", "mass_b",
        "temp_a", "temp_b",
        "wind_tex",
        "display_texture",
        "reservations_buf",
        "rule_ssbo",
    ]


def test_resize_recreates_all_buffers(gl_ctx):
    """Resize must recreate every buffer/texture created in __init__."""
    from gpu.buffers import BufferManager

    bm = BufferManager(gl_ctx, (64, 64))

    # Verify all attributes exist before resize
    for attr in _all_required_attrs():
        assert hasattr(bm, attr), f"Missing attribute before resize: {attr}"

    # Resize to new dimensions
    bm.resize(128, 96)

    # All attributes must still exist
    for attr in _all_required_attrs():
        assert hasattr(bm, attr), f"Missing attribute after resize: {attr}"

    # Verify dimensions updated
    assert bm.width == 128
    assert bm.height == 96
    assert bm.cell_count == 128 * 96


def test_resize_texture_dimensions(gl_ctx):
    """Textures must have the new dimensions after resize."""
    from gpu.buffers import BufferManager

    bm = BufferManager(gl_ctx, (64, 64))
    bm.resize(128, 96)

    # Check that all textures have the new size
    expected_size = (128, 96)
    texture_attrs = [
        "vel_a", "vel_b",
        "pres_a", "pres_b",
        "div_tex", "vorticity_tex",
        "mass_a", "mass_b",
        "temp_a", "temp_b",
        "wind_tex",
        "display_texture",
    ]
    for attr in texture_attrs:
        tex = getattr(bm, attr)
        assert tex.size == expected_size, (
            f"{attr} has size {tex.size}, expected {expected_size}"
        )


def test_resize_buffer_sizes(gl_ctx):
    """Buffers must have the correct byte size after resize."""
    from gpu.buffers import BufferManager

    bm = BufferManager(gl_ctx, (64, 64))
    bm.resize(128, 96)

    expected_cell_bytes = 128 * 96 * 4  # uint32 per cell
    assert bm.read_buf.size == expected_cell_bytes
    assert bm.write_buf.size == expected_cell_bytes
    assert bm.reservations_buf.size == expected_cell_bytes


def test_resize_temp_initialized_to_ambient(gl_ctx):
    """Temperature textures must be initialized to ambient after resize."""
    from gpu.buffers import BufferManager
    from core.constants import TEMP_AMBIENT

    bm = BufferManager(gl_ctx, (64, 64))
    bm.resize(32, 32)

    # Read temp_a contents
    temp_data = np.frombuffer(bm.temp_a.read(), dtype=np.float32).reshape(32, 32)
    expected = float(TEMP_AMBIENT)
    assert np.allclose(temp_data, expected, atol=1e-3), (
        f"temp_a not initialized to ambient: got mean {temp_data.mean()}, expected {expected}"
    )


def test_resize_mass_initialized_to_zero(gl_ctx):
    """Mass textures must be initialized to zero after resize."""
    from gpu.buffers import BufferManager

    bm = BufferManager(gl_ctx, (64, 64))
    bm.resize(32, 32)

    mass_data = np.frombuffer(bm.mass_a.read(), dtype=np.float16).reshape(32, 32)
    assert np.all(mass_data == 0.0), "mass_a not zero-initialized after resize"


def test_resize_wind_initialized_to_zero(gl_ctx):
    """Wind texture must be initialized to zero after resize."""
    from gpu.buffers import BufferManager

    bm = BufferManager(gl_ctx, (64, 64))
    bm.resize(32, 32)

    wind_data = np.frombuffer(bm.wind_tex.read(), dtype=np.float16).reshape(32, 32, 2)
    assert np.all(wind_data == 0.0), "wind_tex not zero-initialized after resize"


def test_resize_swap_methods_work(gl_ctx):
    """After resize, all swap methods should still work without error."""
    from gpu.buffers import BufferManager

    bm = BufferManager(gl_ctx, (64, 64))
    bm.resize(128, 128)

    # These must not raise
    bm.swap_cell_buffers()
    bm.swap_velocity_buffers()
    bm.swap_pressure_buffers()
    bm.swap_mass_buffers()
    bm.swap_temp_buffers()
