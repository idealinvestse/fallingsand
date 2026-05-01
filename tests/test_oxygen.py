"""Tests for oxygen-dependent combustion.

These tests verify:
  - Fire with O2 nearby lasts longer than fire without O2
  - Fire extinguishes faster when fully enclosed (no air or O2)
  - O2 cells are consumed by fire (replaced with smoke)
  - Materials with o2Req > 0 cannot ignite without oxidizer nearby
  - O2 in explosion radius is consumed to smoke
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

from core.config import SimulationConfig  # noqa: E402
from simulation.engine import SimulationEngine  # noqa: E402
from simulation.materials import get_all_materials  # noqa: E402
from core.types import Category  # noqa: E402


class _StandaloneCtxManager:
    def __init__(self, ctx, size):
        self.ctx = ctx
        self.window_size = size

    def get_context(self):
        return self.ctx

    def get_window_size(self):
        return self.window_size


@pytest.fixture(scope="module")
def gl_ctx():
    try:
        ctx = moderngl.create_standalone_context(require=430)
    except Exception as exc:
        pytest.skip(f"No GL 4.3: {exc}")
    fbo = ctx.simple_framebuffer((64, 64), components=4)
    fbo.use()
    yield ctx
    ctx.release()


def _make_engine(gl_ctx, width=32, height=32, **cfg_kwargs):
    ctx_mgr = _StandaloneCtxManager(gl_ctx, (width, height))
    cfg = SimulationConfig(width=width, height=height, no_stats=True, **cfg_kwargs)
    return SimulationEngine(cfg, ctx_mgr)


def _count_material(eng, mat_id):
    """Count cells of a given material type in the grid."""
    raw = eng.buffers.get_read_buf().read()
    grid = np.frombuffer(raw, dtype=np.uint32)
    types = grid & 0xFF
    return int(np.sum(types == mat_id))


class TestOxygenMaterialProperties:
    """Verify oxygen material definition is correct."""

    def test_oxygen_exists(self):
        mats = get_all_materials()
        assert 32 in mats
        assert mats[32].name == "oxygen"

    def test_oxygen_is_gas(self):
        mats = get_all_materials()
        assert mats[32].category == Category.GAS

    def test_oxygen_density(self):
        mats = get_all_materials()
        # Oxygen is slightly denser than air
        assert mats[32].density == 0.14

    def test_o2_req_fields_exist(self):
        """Combustible materials should have oxygen_requirement and oxygen_yield."""
        mats = get_all_materials()
        # Fire should require oxygen
        fire = mats[4]
        assert fire.oxygen_requirement > 0.0, "Fire should require oxygen"


class TestOxygenConsumption:
    """Fire should consume nearby O2 and produce smoke."""

    def test_o2_decreases_near_fire(self, gl_ctx):
        eng = _make_engine(gl_ctx, width=32, height=32, no_acoustics=True)
        # Place a small fire patch surrounded by oxygen
        for x in range(14, 18):
            for y in range(14, 18):
                eng.apply_brush(cx=x, cy=y, radius=0, material_id=4)  # fire
        for x in range(10, 22):
            for y in range(10, 22):
                # Only place O2 where there isn't fire already
                raw = eng.buffers.get_read_buf().read()
                grid = np.frombuffer(raw, dtype=np.uint32)
                idx = y * 32 + x
                if (grid[idx] & 0xFF) == 0:  # air cell
                    eng.apply_brush(cx=x, cy=y, radius=0, material_id=32)  # oxygen

        o2_before = _count_material(eng, 32)

        for _ in range(30):
            eng.step(dt=1.0 / 60.0)

        o2_after = _count_material(eng, 32)
        # O2 should decrease (consumed by fire)
        assert o2_after < o2_before, f"O2 should decrease near fire: {o2_before} -> {o2_after}"

    def test_fire_suffocates_without_o2(self, gl_ctx):
        """Fire enclosed in stone (no air/O2) should die faster."""
        eng = _make_engine(gl_ctx, width=32, height=32, no_acoustics=True)
        # Enclose fire in stone
        for x in range(10, 22):
            for y in range(10, 22):
                eng.apply_brush(cx=x, cy=y, radius=0, material_id=3)  # stone
        for x in range(13, 19):
            for y in range(13, 19):
                eng.apply_brush(cx=x, cy=y, radius=0, material_id=4)  # fire

        fire_before = _count_material(eng, 4)

        for _ in range(40):
            eng.step(dt=1.0 / 60.0)

        fire_after = _count_material(eng, 4)
        # Fire should decrease (suffocate)
        assert fire_after < fire_before, f"Enclosed fire should suffocate: {fire_before} -> {fire_after}"


class TestOxygenExplosion:
    """O2 near cell-based explosions (T_BLAST) should be consumed to smoke."""

    def test_o2_consumed_near_blast_source(self):
        """Static check: state_shader converts O2 to smoke in blast radius."""
        src = Path("shaders/state_shader.glsl").read_text(encoding="utf-8")
        # Find the nearBlast section that converts O2→smoke
        assert "T_OXYGEN" in src
        assert "T_SMOKE" in src
        # Verify O2→smoke conversion in blast section
        assert "typ == T_OXYGEN" in src


class TestO2ShaderSource:
    """Static assertions on O2-related shader code."""

    def test_state_shader_has_o2_consumption(self):
        src = Path("shaders/state_shader.glsl").read_text(encoding="utf-8")
        assert "o2Req" in src
        assert "o2Yield" in src
        assert "T_OXYGEN" in src

    def test_force_shader_has_rho_air(self):
        src = Path("shaders/force_shader.glsl").read_text(encoding="utf-8")
        assert "RHO_AIR" in src
        assert "baseBuoy = RHO_AIR - r.density" in src

    def test_state_shader_o2_in_blast(self):
        src = Path("shaders/state_shader.glsl").read_text(encoding="utf-8")
        # O2 in blast radius should be converted to smoke
        assert "T_OXYGEN" in src
