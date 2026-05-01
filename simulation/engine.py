"""Main simulation engine — coordinates GPU pipeline, state, and user interactions."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from core.config import SimulationConfig
from core.constants import TEMP_AMBIENT
from simulation.state import ExplosionState, ExplosionType, ExplosionVfxState, WindState
from gpu.buffers import BufferManager
from gpu.context import ContextManager
from gpu.pipeline import Pipeline
from gpu.shader_registry import load_all_shaders
from gpu.uniforms import UBOManager
from simulation.brush import BrushPainter
from simulation.persistence import PersistenceManager


class SimulationEngine:
    """Orchestrates the GPU simulation pipeline (v5: state→force→div→pressure×N→project→advect→render)."""

    def __init__(self, config: SimulationConfig, ctx_manager: ContextManager):
        self.config = config
        self.ctx_manager = ctx_manager
        self.ctx = ctx_manager.get_context()
        self.width = config.width
        self.height = config.height

        self.buffers = BufferManager(self.ctx, (self.width, self.height))
        self.ubo_manager = UBOManager(self.ctx)

        if not config.no_stats:
            from gpu.stats_counter import GPUStatsCounter
            self.stats_counter: GPUStatsCounter | None = GPUStatsCounter(
                self.ctx, (self.width, self.height)
            )
        else:
            self.stats_counter = None

        # Runtime state
        self.explosion_state = ExplosionState()
        self.explosion_vfx_state = ExplosionVfxState()
        self.wind_state = WindState(vector=[0.0, 0.0], enabled=False)

        self._initialize_grid()
        shaders = load_all_shaders(self.ctx)
        self.pipeline = Pipeline(
            self.ctx, self.buffers, self.ubo_manager, self.config,
            shaders, (self.width, self.height),
        )
        self.brush = BrushPainter(self.buffers, (self.width, self.height))
        self.persistence = PersistenceManager(self.buffers, (self.width, self.height), config.atm_pressure)
        self._initialize_pressure()

        self.frame = 0
        self._show_pressure_overlay: bool = False

    # ── Setup ────────────────────────────────────────────────────────────────

    def _initialize_grid(self) -> None:
        from simulation.materials import pack_cell
        empty = np.full(self.width * self.height, pack_cell(0), dtype=np.uint32)
        self.buffers.get_read_buf().write(empty.tobytes())
        self.buffers.get_write_buf().write(empty.tobytes())

    def _initialize_pressure(self) -> None:
        """Fill pressure textures with ambient atmospheric pressure.

        This ensures hydrostatic equilibrium from the start — gas cells
        see ambient pressure rather than zero, preventing an initial
        transient shock wave on frame 1.
        """
        n = self.width * self.height
        pres_data = np.full(n, self.config.atm_pressure, dtype=np.float32)
        self.buffers.pres_a.write(pres_data.tobytes())
        self.buffers.pres_b.write(pres_data.tobytes())

    # ── Public API ───────────────────────────────────────────────────────────

    def trigger_explosion(
        self,
        x: float,
        y: float,
        radius: float = 25.0,
        force: float = 8.0,
        duration: int = 3,
        explosion_type: int = 0,
        crater_radius: float = 0.0,
    ) -> None:
        self.explosion_state.trigger(x, y, radius, force, duration, explosion_type, crater_radius)
        self.explosion_vfx_state.trigger(x, y, flash_intensity=min(0.6, force / 20.0))

    def trigger_big_explosion(self, x: float, y: float) -> None:
        self.trigger_explosion(x, y, radius=40.0, force=12.0, duration=5, explosion_type=ExplosionType.HIGH_EXPLOSIVE)

    def trigger_deflagration(self, x: float, y: float, radius: float = 30.0, force: float = 6.0) -> None:
        """Gunpowder-style deflagration - more push, less shatter."""
        self.trigger_explosion(x, y, radius, force, 8, ExplosionType.DEFLAGRATION, crater_radius=radius * 0.4)

    def trigger_thermobaric(self, x: float, y: float, radius: float = 50.0, force: float = 10.0) -> None:
        """Fuel-air explosion - large radius, uses up oxygen."""
        self.trigger_explosion(x, y, radius, force, 6, ExplosionType.THERMOBARIC, crater_radius=radius * 0.3)

    def trigger_napalm_burst(self, x: float, y: float, radius: float = 35.0) -> None:
        """Napalm burst - persistent fire, less concussive."""
        self.trigger_explosion(x, y, radius, 4.0, 10, ExplosionType.NAPALM, crater_radius=radius * 0.2)

    def adjust_wind(self, dx: float, dy: float) -> None:
        self.wind_state.adjust(dx, dy)

    def toggle_wind(self) -> None:
        self.wind_state.toggle()

    def toggle_pressure_overlay(self) -> bool:
        """Toggle pressure visualization overlay. Returns new state."""
        self._show_pressure_overlay = not self._show_pressure_overlay
        return self._show_pressure_overlay

    def step(self, dt: float = 0.016) -> None:
        self.pipeline.step(dt, self.frame, self.explosion_state, self.explosion_vfx_state, self.wind_state)
        self.frame += 1
        self.explosion_state.update()
        self.explosion_vfx_state.update()

    def render(self) -> None:
        """Render cells into display_texture and blit to the default framebuffer."""
        self.pipeline.render(self._show_pressure_overlay, self.explosion_vfx_state)

    def get_display_texture(self):
        return self.buffers.display_texture

    # ── Save/load ────────────────────────────────────────────────────────────

    def save_state(self, filepath: Path) -> None:
        self.persistence.save_state(filepath)

    def get_state(self) -> np.ndarray:
        return self.persistence.get_state()

    def set_state(self, state: np.ndarray) -> None:
        self.persistence.set_state(state)

    def push_undo_snapshot(self) -> None:
        self.persistence.push_undo_snapshot()

    def undo(self) -> bool:
        return self.persistence.undo()

    def probe_cell(self, gx: int, gy: int) -> dict | None:
        """Probe a single cell at grid coordinates (gx, gy) and return its state.

        Returns None if coordinates are out of bounds. Otherwise returns a dict with:
        - cell: Cell dataclass with type_id, life, flags
        - material: Material object for the type_id
        - temp_float: Raw temperature from the float texture
        - velocity: (vx, vy) tuple from velocity texture
        - pressure: Scalar from pressure texture
        - mass: Scalar from mass texture
        - wind: (wx, wy) tuple from wind texture
        - vorticity: Scalar from vorticity texture
        - divergence: Scalar from divergence texture
        """
        # Bounds check
        if not (0 <= gx < self.width and 0 <= gy < self.height):
            return None

        from core.types import Cell
        from simulation.materials import get_material

        result = {}

        # Read cell uint32 from SSBO
        try:
            offset = (gy * self.width + gx) * 4
            cell_bytes = self.buffers.get_read_buf().read(size=4, offset=offset)
            cell_packed = int.from_bytes(cell_bytes, byteorder='little')
            result["cell"] = Cell.unpack(cell_packed)
        except Exception:
            result["cell"] = None

        # Read temperature texture (1 texel, r32f)
        try:
            temp_data = self.buffers.temp_a.read(viewport=(gx, gy, 1, 1))
            temp_array = np.frombuffer(temp_data, dtype=np.float32)
            result["temp_float"] = float(temp_array[0])
        except Exception:
            result["temp_float"] = None

        # Read velocity texture (1 texel, rg32f)
        try:
            vel_data = self.buffers.vel_a.read(viewport=(gx, gy, 1, 1))
            vel_array = np.frombuffer(vel_data, dtype=np.float32)
            result["velocity"] = (float(vel_array[0]), float(vel_array[1]))
        except Exception:
            result["velocity"] = None

        # Read pressure texture (1 texel, r32f)
        try:
            pres_data = self.buffers.pres_a.read(viewport=(gx, gy, 1, 1))
            pres_array = np.frombuffer(pres_data, dtype=np.float32)
            result["pressure"] = float(pres_array[0])
        except Exception:
            result["pressure"] = None

        # Read mass texture (1 texel, r16f)
        try:
            mass_data = self.buffers.mass_a.read(viewport=(gx, gy, 1, 1))
            mass_array = np.frombuffer(mass_data, dtype=np.float16)
            result["mass"] = float(mass_array[0])
        except Exception:
            result["mass"] = None

        # Read wind texture (1 texel, rg16f)
        try:
            wind_data = self.buffers.wind_tex.read(viewport=(gx, gy, 1, 1))
            wind_array = np.frombuffer(wind_data, dtype=np.float16)
            result["wind"] = (float(wind_array[0]), float(wind_array[1]))
        except Exception:
            result["wind"] = None

        # Read vorticity texture (1 texel, r32f)
        try:
            vort_data = self.buffers.vorticity_tex.read(viewport=(gx, gy, 1, 1))
            vort_array = np.frombuffer(vort_data, dtype=np.float32)
            result["vorticity"] = float(vort_array[0])
        except Exception:
            result["vorticity"] = None

        # Read divergence texture (1 texel, r32f)
        try:
            div_data = self.buffers.div_tex.read(viewport=(gx, gy, 1, 1))
            div_array = np.frombuffer(div_data, dtype=np.float32)
            result["divergence"] = float(div_array[0])
        except Exception:
            result["divergence"] = None

        # Get material object
        if result["cell"] is not None:
            result["material"] = get_material(result["cell"].type_id)
        else:
            result["material"] = None

        return result

    def clear_grid(self) -> None:
        self._initialize_grid()
        self.buffers.clear_temp_buffers(float(TEMP_AMBIENT))
        # Reset fluid dynamics so the cleared grid starts from a clean state.
        self.buffers.clear_physics_buffers(ambient_pressure=self.config.atm_pressure)

    def load_level(self, level) -> None:
        self.clear_grid()
        level.build(self)

    def load_state(self, filepath: Path) -> None:
        self.persistence.load_state(filepath)

    # ── Stats & brush ───────────────────────────────────────────────────────────

    def apply_brush(
        self,
        cx: int,
        cy: int,
        radius: int,
        material_id: int,
        mode: int = 0,
        delta: int = 0,
    ) -> None:
        """Paint cells onto the grid. Delegates to BrushPainter."""
        self.brush.apply_brush(cx, cy, radius, material_id, mode, delta)