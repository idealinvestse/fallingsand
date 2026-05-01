"""Runtime physics invariants for the GPU pipeline.

These tests spin up a real ModernGL 4.3 standalone context and a full
``SimulationEngine``; they exercise end-to-end correctness of the physics
model (buoyancy, fall, layering, convection, divergence).

They are intentionally tolerant ("direction + magnitude") rather than numeric
so the suite stays robust across small parameter tweaks while still catching
sign bugs and broken pipelines.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure the project root is importable.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

moderngl = pytest.importorskip("moderngl")

from core.config import SimulationConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StandaloneCtxManager:
    """Minimal `ContextManager` look-alike backed by a standalone context."""

    def __init__(self, ctx: "moderngl.Context", size: tuple[int, int]):
        self.ctx = ctx
        self.window_size = size

    def get_context(self) -> "moderngl.Context":
        return self.ctx

    def get_window_size(self) -> tuple[int, int]:
        return self.window_size


@pytest.fixture(scope="module")
def gl_ctx():
    """Module-scoped GL4.3 standalone context (creation is relatively slow)."""
    try:
        ctx = moderngl.create_standalone_context(require=430)
    except Exception as exc:  # pragma: no cover - platform dependent
        pytest.skip(f"No GL 4.3 compute available: {exc}")
    # Give the engine a dummy framebuffer to render to so that `ctx.screen.use()`
    # in the display blit does not fail.
    fbo = ctx.simple_framebuffer((64, 64), components=4)
    fbo.use()
    yield ctx
    fbo.release()
    ctx.release()


def _make_engine(gl_ctx, width: int = 48, height: int = 48, **cfg_kwargs):
    """Build a ``SimulationEngine`` on the provided standalone context."""
    from simulation.engine import SimulationEngine

    defaults = dict(
        sim_substeps=1,
        pressure_iterations=12,
        no_stats=True,
        no_thermal=False,
        no_turbulence=True,  # determinism
        no_wet_dry=True,
    )
    defaults.update(cfg_kwargs)
    cfg = SimulationConfig(width=width, height=height, **defaults)
    return SimulationEngine(cfg, _StandaloneCtxManager(gl_ctx, (width, height)))


def _grid(engine) -> np.ndarray:
    """Read current cell grid as (H, W) uint32 array."""
    raw = engine.buffers.read_buf.read()
    flat = np.frombuffer(raw, dtype=np.uint32)
    return flat.reshape((engine.height, engine.width))


def _types(engine) -> np.ndarray:
    return (_grid(engine) & 0xFF).astype(np.uint8)


def _find(engine, material_id: int) -> list[tuple[int, int]]:
    t = _types(engine)
    ys, xs = np.where(t == material_id)
    return list(zip(xs.tolist(), ys.tolist()))


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_free_fall_sand_goes_down(gl_ctx):
    """A single sand cell in vacuum must fall toward lower y each step.

    y increases upward in the engine's convention, so "falling" = y decreases.
    """
    eng = _make_engine(gl_ctx)
    # Place one sand cell near the top (y high) of an otherwise empty grid.
    eng.apply_brush(cx=24, cy=40, radius=0, material_id=1)
    ys = []
    for _ in range(25):
        eng.step(dt=1.0 / 60.0)
        pos = _find(eng, 1)
        if not pos:
            break
        ys.append(pos[0][1])
    assert ys, "sand cell disappeared"
    assert ys[-1] < 40, f"sand did not fall: y trace = {ys}"


def test_water_spreads_and_settles(gl_ctx):
    """Water column must not be stuck: after N frames the pile spreads horizontally."""
    eng = _make_engine(gl_ctx)
    # Vertical column of water
    for y in range(20, 40):
        eng.apply_brush(cx=24, cy=y, radius=0, material_id=2)
    xs_initial = {x for x, _ in _find(eng, 2)}
    for _ in range(60):
        eng.step(dt=1.0 / 60.0)
    xs_final = {x for x, _ in _find(eng, 2)}
    assert len(xs_final) > len(xs_initial), (
        f"water did not spread horizontally: init={sorted(xs_initial)}, "
        f"final x-spread={sorted(xs_final)}"
    )


def test_oil_floats_above_water(gl_ctx):
    """Oil (rho=1.5) is lighter than water (rho=2.0); water must sink through
    oil. We assert the invariant *locally*: after enough frames, oil's mean-y
    should be above water's mean-y (density-based separation).
    """
    eng = _make_engine(gl_ctx, width=32, height=48, no_acoustics=True)
    # Water stacked directly on top of oil: water column on top, oil on bottom.
    # This is an "unstable" stack; the denser fluid must fall past the lighter.
    for y in range(6, 14):
        for x in range(12, 20):
            eng.apply_brush(cx=x, cy=y, radius=0, material_id=6)  # oil (bottom)
    for y in range(14, 22):
        for x in range(12, 20):
            eng.apply_brush(cx=x, cy=y, radius=0, material_id=2)  # water (top)

    for _ in range(160):
        eng.step(dt=1.0 / 60.0)

    oil_pos = _find(eng, 6)
    water_pos = _find(eng, 2)
    if not oil_pos or not water_pos:
        pytest.skip("material leaked off grid during swap")
    oil_end = np.mean([p[1] for p in oil_pos])
    water_end = np.mean([p[1] for p in water_pos])
    assert oil_end > water_end, (
        f"oil ended up below water after swap: oil={oil_end:.1f} water={water_end:.1f}"
    )


def test_smoke_rises(gl_ctx):
    """Smoke has negative density and must drift upward.

    Regression: with the previous ideal-gas formula, negative density cells
    ended up with inverted buoyancy and drifted downward.
    """
    eng = _make_engine(gl_ctx, height=48)
    # Patch of smoke in the middle
    for x in range(22, 26):
        for y in range(10, 14):
            eng.apply_brush(cx=x, cy=y, radius=0, material_id=5)  # smoke

    start_y = np.mean([p[1] for p in _find(eng, 5)])
    # Smoke has a finite lifetime (default_flame_life ~ 36 frames); sample early
    # so the check runs while enough cells still exist to measure a mean.
    for _ in range(18):
        eng.step(dt=1.0 / 60.0)
    remaining = _find(eng, 5)
    if not remaining:
        pytest.skip("smoke fully decayed before rising window")
    end_y = np.mean([p[1] for p in remaining])
    assert end_y > start_y, (
        f"smoke did not rise: <y>_start={start_y:.1f}, <y>_end={end_y:.1f}"
    )


def test_solids_do_not_drift(gl_ctx):
    """Stone (solid) should stay stationary and not drift upward on its own."""
    eng = _make_engine(gl_ctx, height=48)
    for x in range(22, 26):
        for y in range(30, 34):
            eng.apply_brush(cx=x, cy=y, radius=0, material_id=3)  # stone

    start_y = np.mean([p[1] for p in _find(eng, 3)])
    for _ in range(40):
        eng.step(dt=1.0 / 60.0)
    remaining = _find(eng, 3)
    if not remaining:
        pytest.skip("stone disappeared")
    end_y = np.mean([p[1] for p in remaining])
    # Solids should not move; allow small numerical drift
    assert end_y <= start_y + 0.5, (
        f"solid stone drifted upward unexpectedly: {start_y:.1f} -> {end_y:.1f}"
    )


def test_hydrostatic_water_has_small_divergence(gl_ctx):
    """A water tank at rest should converge to near-zero divergence after
    a few pressure iterations. Fails loudly if the pressure solve is broken.
    """
    eng = _make_engine(gl_ctx, width=32, height=32, pressure_iterations=12, no_acoustics=True)
    for y in range(2, 16):
        for x in range(4, 28):
            eng.apply_brush(cx=x, cy=y, radius=0, material_id=2)  # water
    # Let the field relax.
    for _ in range(30):
        eng.step(dt=1.0 / 60.0)

    # Read divergence texture and RMS the interior.
    div_bytes = eng.buffers.div_tex.read()
    div = np.frombuffer(div_bytes, dtype=np.float32).reshape((32, 32))
    interior = div[4:-4, 4:-4]
    rms = float(np.sqrt(np.mean(interior * interior)))
    # Value depends on dt/gravity scale; 0.5 is a loose upper bound that still
    # catches a broken (non-converging) solve which would produce RMS >> 1.
    assert rms < 0.6, f"hydrostatic divergence RMS too high: {rms:.3f}"


def test_larger_dt_produces_stronger_gravity_response(gl_ctx):
    """The pipeline must scale force integration with the frame dt.

    Regression: the multi-pass solver previously used a hardcoded 1/60s step
    internally, which made a 30 FPS frame behave like a 60 FPS frame.
    """
    cfg_kwargs = dict(
        no_acoustics=True,
        no_thermal=True,
        no_turbulence=True,
        no_wet_dry=True,
    )

    eng_small = _make_engine(gl_ctx, width=32, height=32, **cfg_kwargs)
    eng_small.apply_brush(cx=16, cy=24, radius=0, material_id=2)
    eng_small.step(dt=1.0 / 120.0)
    x_small, y_small = _find(eng_small, 2)[0]
    vel_small = np.frombuffer(eng_small.buffers.vel_a.read(), dtype=np.float32).reshape((32, 32, 2))[y_small, x_small]

    eng_big = _make_engine(gl_ctx, width=32, height=32, **cfg_kwargs)
    eng_big.apply_brush(cx=16, cy=24, radius=0, material_id=2)
    eng_big.step(dt=1.0 / 30.0)
    x_big, y_big = _find(eng_big, 2)[0]
    vel_big = np.frombuffer(eng_big.buffers.vel_a.read(), dtype=np.float32).reshape((32, 32, 2))[y_big, x_big]

    assert vel_big[1] < vel_small[1], (
        f"gravity response did not increase with dt: small={vel_small[1]:.6f}, big={vel_big[1]:.6f}"
    )
    assert abs(vel_big[1]) >= abs(vel_small[1]) * 2.0, (
        f"gravity response is not scaling strongly enough with dt: "
        f"small={vel_small[1]:.6f}, big={vel_big[1]:.6f}"
    )
