from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pytest

from core.config import SimulationConfig
from core.constants import NUM_TYPES, TEMP_AMBIENT
from simulation.engine import SimulationEngine

moderngl = pytest.importorskip("moderngl")

_FMT_RG32F = 0x8230
_FMT_R32F = 0x822E
_FMT_RGBA8 = 0x8058


@dataclass(frozen=True)
class AuditSnapshot:
    types: np.ndarray
    temp: np.ndarray
    velocity: np.ndarray
    pressure: np.ndarray
    divergence: np.ndarray
    display: np.ndarray | None = None

    @property
    def counts(self) -> dict[int, int]:
        ids, counts = np.unique(self.types, return_counts=True)
        return {int(i): int(c) for i, c in zip(ids, counts)}


@dataclass(frozen=True)
class AuditMetrics:
    material_counts: dict[int, int]
    temp_min: float
    temp_max: float
    velocity_max: float
    pressure_min: float
    pressure_max: float
    divergence_rms: float
    non_air_cells: int
    display_nonzero_pixels: int | None


class StandaloneCtxManager:
    def __init__(self, ctx: "moderngl.Context", size: tuple[int, int]):
        self.ctx = ctx
        self.window_size = size

    def get_context(self) -> "moderngl.Context":
        return self.ctx

    def get_window_size(self) -> tuple[int, int]:
        return self.window_size


@dataclass(frozen=True)
class AuditScenario:
    name: str
    setup: Callable[[SimulationEngine], None]
    frames: int = 60
    width: int = 64
    height: int = 64
    dt: float = 1.0 / 60.0
    config_overrides: dict | None = None


def create_standalone_context(size: tuple[int, int] = (64, 64)):
    try:
        ctx = moderngl.create_standalone_context(require=430)
    except Exception as exc:
        pytest.skip(f"No GL 4.3 compute available: {exc}")
    fbo = ctx.simple_framebuffer(size, components=4)
    fbo.use()
    return ctx, fbo


def make_engine(ctx, width: int = 64, height: int = 64, **cfg_kwargs) -> SimulationEngine:
    defaults = dict(
        window_width=max(100, width),
        window_height=max(100, height),
        sim_substeps=1,
        pressure_iterations=12,
        no_stats=True,
        no_turbulence=True,
        no_wet_dry=True,
        no_acoustics=True,
    )
    defaults.update(cfg_kwargs)
    cfg = SimulationConfig(width=width, height=height, **defaults)
    return SimulationEngine(cfg, StandaloneCtxManager(ctx, (width, height)))


def paint_rect(engine: SimulationEngine, material_id: int, x0: int, y0: int, x1: int, y1: int, mode: int = 0, delta: int = 0) -> None:
    for y in range(y0, y1):
        for x in range(x0, x1):
            engine.apply_brush(x, y, radius=0, material_id=material_id, mode=mode, delta=delta)


def run_scenario(ctx, scenario: AuditScenario) -> SimulationEngine:
    overrides = scenario.config_overrides or {}
    engine = make_engine(ctx, scenario.width, scenario.height, **overrides)
    scenario.setup(engine)
    for _ in range(scenario.frames):
        engine.step(scenario.dt)
    return engine


def snapshot(engine: SimulationEngine, include_display: bool = False) -> AuditSnapshot:
    width, height = engine.width, engine.height
    raw = engine.buffers.read_buf.read()
    cells = np.frombuffer(raw, dtype=np.uint32).reshape((height, width))
    types = (cells & 0xFF).astype(np.uint8)
    temp = np.frombuffer(engine.buffers.temp_a.read(), dtype=np.float32).reshape((height, width))
    velocity = np.frombuffer(engine.buffers.vel_a.read(), dtype=np.float32).reshape((height, width, 2))
    pressure = np.frombuffer(engine.buffers.pres_a.read(), dtype=np.float32).reshape((height, width))
    divergence = np.frombuffer(engine.buffers.div_tex.read(), dtype=np.float32).reshape((height, width))
    display = None
    if include_display:
        engine.buffers.get_read_buf().bind_to_storage_buffer(0)
        engine.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
        engine.buffers.pres_a.bind_to_image(5, read=True, write=False, level=0, format=_FMT_R32F)
        engine.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
        engine.buffers.display_texture.bind_to_image(7, read=False, write=True, level=0, format=_FMT_RGBA8)
        engine.pipeline._set_common_uniforms(engine.pipeline.render_shader)
        engine.pipeline._set_if(engine.pipeline.render_shader, "showPressure", int(engine._show_pressure_overlay))
        engine.pipeline._set_if(engine.pipeline.render_shader, "ambientPressure", engine.config.atm_pressure)
        engine.pipeline._set_if(engine.pipeline.render_shader, "explosionFlash", float(engine.explosion_vfx_state.flash))
        engine.pipeline._set_if(engine.pipeline.render_shader, "explosionCenter", engine.explosion_vfx_state.center)
        engine.pipeline._set_if(engine.pipeline.render_shader, "explosionAge", float(engine.explosion_vfx_state.age))
        engine.pipeline._set_if(engine.pipeline.render_shader, "explosionMaxAge", float(engine.explosion_vfx_state.max_age))
        engine.pipeline.render_shader.run(group_x=engine.pipeline.gx, group_y=engine.pipeline.gy, group_z=1)
        engine.ctx.memory_barrier(moderngl.ALL_BARRIER_BITS)
        display = np.frombuffer(engine.buffers.display_texture.read(), dtype=np.uint8).reshape((height, width, 4))
    return AuditSnapshot(types=types, temp=temp, velocity=velocity, pressure=pressure, divergence=divergence, display=display)


def metrics(snap: AuditSnapshot) -> AuditMetrics:
    speeds = np.sqrt(np.sum(snap.velocity * snap.velocity, axis=2))
    display_nonzero = None
    if snap.display is not None:
        display_nonzero = int(np.count_nonzero(np.any(snap.display[:, :, :3] > 0, axis=2)))
    return AuditMetrics(
        material_counts=snap.counts,
        temp_min=float(np.min(snap.temp)),
        temp_max=float(np.max(snap.temp)),
        velocity_max=float(np.max(speeds)),
        pressure_min=float(np.min(snap.pressure)),
        pressure_max=float(np.max(snap.pressure)),
        divergence_rms=float(np.sqrt(np.mean(snap.divergence * snap.divergence))),
        non_air_cells=int(np.count_nonzero(snap.types != 0)),
        display_nonzero_pixels=display_nonzero,
    )


def positions(snap: AuditSnapshot, material_id: int) -> list[tuple[int, int]]:
    ys, xs = np.where(snap.types == material_id)
    return list(zip(xs.tolist(), ys.tolist()))


def centroid_y(snap: AuditSnapshot, material_id: int) -> float | None:
    pos = positions(snap, material_id)
    if not pos:
        return None
    return float(np.mean([y for _, y in pos]))


def anomaly_messages(snap: AuditSnapshot, velocity_limit: float = 100.0, pressure_limit: float = 1000.0, temp_limit: float = 10000.0) -> list[str]:
    found: list[str] = []
    if np.any(snap.types >= NUM_TYPES):
        found.append("unknown material id present")
    if not np.all(np.isfinite(snap.temp)):
        found.append("non-finite temperature field")
    if not np.all(np.isfinite(snap.velocity)):
        found.append("non-finite velocity field")
    if not np.all(np.isfinite(snap.pressure)):
        found.append("non-finite pressure field")
    if not np.all(np.isfinite(snap.divergence)):
        found.append("non-finite divergence field")
    m = metrics(snap)
    if m.velocity_max > velocity_limit:
        found.append(f"velocity runaway: {m.velocity_max:.3f}")
    if max(abs(m.pressure_min), abs(m.pressure_max)) > pressure_limit:
        found.append(f"pressure runaway: {m.pressure_min:.3f}..{m.pressure_max:.3f}")
    if max(abs(m.temp_min - TEMP_AMBIENT), abs(m.temp_max - TEMP_AMBIENT)) > temp_limit:
        found.append(f"temperature runaway: {m.temp_min:.3f}..{m.temp_max:.3f}")
    if snap.display is not None and m.non_air_cells > 0 and m.display_nonzero_pixels == 0:
        found.append("render output is black despite non-air cells")
    return found


def assert_no_anomalies(snap: AuditSnapshot, **limits) -> None:
    found = anomaly_messages(snap, **limits)
    assert not found, "; ".join(found)
