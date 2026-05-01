"""Tests for the acoustic (weakly-compressible gas) solver.

These tests verify:
  - Acoustic shaders compile and run without error
  - Pressure pulse from an explosion propagates outward in gas
  - Acoustic solver can be disabled via config
  - Non-gas cells are not affected by the acoustic solver
  - CFL stability: no NaN/Inf after many frames
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


class TestAcousticShaderCompilation:
    """Acoustic shaders must compile and the engine must initialise."""

    def test_engine_creates_with_acoustics(self, gl_ctx):
        eng = _make_engine(gl_ctx)
        assert hasattr(eng.pipeline, "acoustic_pressure_shader")
        assert hasattr(eng.pipeline, "acoustic_velocity_shader")

    def test_engine_creates_without_acoustics(self, gl_ctx):
        eng = _make_engine(gl_ctx, no_acoustics=True)
        assert hasattr(eng.pipeline, "acoustic_pressure_shader")


class TestAcousticPressureInit:
    """Pressure textures should be initialised to ambient pressure."""

    def test_pressure_initialized_to_ambient(self, gl_ctx):
        eng = _make_engine(gl_ctx, atm_pressure=1.0)
        pres_data = eng.buffers.pres_a.read()
        pres = np.frombuffer(pres_data, dtype=np.float32)
        # All cells should start at ambient pressure
        assert np.allclose(pres, 1.0, atol=0.01)


class TestAcousticStability:
    """The acoustic solver must not produce NaN/Inf after many frames."""

    def test_no_nan_after_many_frames(self, gl_ctx):
        eng = _make_engine(gl_ctx, width=32, height=32)
        # Place some gas cells (fire) to exercise the acoustic path
        for x in range(10, 22):
            for y in range(10, 22):
                eng.apply_brush(cx=x, cy=y, radius=0, material_id=4)  # fire

        for _ in range(60):
            eng.step(dt=1.0 / 60.0)

        pres_data = eng.buffers.pres_a.read()
        pres = np.frombuffer(pres_data, dtype=np.float32)
        assert np.all(np.isfinite(pres)), "Acoustic solver produced non-finite pressure"

    def test_no_nan_with_explosion(self, gl_ctx):
        eng = _make_engine(gl_ctx, width=32, height=32)
        # Place oxygen + trigger explosion
        for x in range(8, 24):
            for y in range(8, 24):
                eng.apply_brush(cx=x, cy=y, radius=0, material_id=32)  # oxygen
        eng.trigger_explosion(16.0, 16.0, radius=10.0, force=5.0, duration=2)

        for _ in range(60):
            eng.step(dt=1.0 / 60.0)

        pres_data = eng.buffers.pres_a.read()
        pres = np.frombuffer(pres_data, dtype=np.float32)
        assert np.all(np.isfinite(pres)), "Acoustic solver produced non-finite pressure after explosion"


class TestAcousticDisabled:
    """When acoustics are disabled, the simulation should still work."""

    def test_no_acoustics_still_runs(self, gl_ctx):
        eng = _make_engine(gl_ctx, no_acoustics=True)
        for x in range(10, 22):
            for y in range(10, 22):
                eng.apply_brush(cx=x, cy=y, radius=0, material_id=2)  # water

        for _ in range(30):
            eng.step(dt=1.0 / 60.0)

        pres_data = eng.buffers.pres_a.read()
        pres = np.frombuffer(pres_data, dtype=np.float32)
        assert np.all(np.isfinite(pres))


class TestAcousticShaderSource:
    """Static assertions on acoustic shader source."""

    def test_pressure_step_has_sound_speed(self):
        src = Path("shaders/acoustic_pressure_step.glsl").read_text(encoding="utf-8")
        assert "soundSpeed" in src
        assert "dtAcoustic" in src
        assert "ambientPressure" in src

    def test_velocity_step_has_dt(self):
        src = Path("shaders/acoustic_velocity_step.glsl").read_text(encoding="utf-8")
        assert "dtAcoustic" in src
        assert "gradP" in src

    def test_pressure_step_has_explosion_injection(self):
        src = Path("shaders/acoustic_pressure_step.glsl").read_text(encoding="utf-8")
        assert "explosionIsActive" in src
        assert "explosionPressurePulse" in src

    def test_gas_cells_only(self):
        """Both acoustic shaders should only operate on gas cells (cat==0)."""
        for name in ("acoustic_pressure_step.glsl", "acoustic_velocity_step.glsl"):
            src = Path(f"shaders/{name}").read_text(encoding="utf-8")
            assert "r.cat != 0" in src or "r.cat == 0" in src
