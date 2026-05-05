"""GPU simulation pipeline orchestrating the v5 multi-pass compute dispatch."""

from __future__ import annotations

import moderngl
import numpy as np
import time

from core.config import SimulationConfig
from core.constants import MAX_SUBSTEPS, RULE_STRIDE, TEMP_AMBIENT
from gpu.buffers import BufferManager
from gpu.sparse_mask import SparseMask
from gpu.uniforms import (
    UBOManager,
    SimConfigData,
    ExplosionConfigData,
    ExplosionVfxConfigData,
    WindConfigData,
)
from gpu.pass_graph import ComputePass, default_render_passes, default_step_passes
from gpu.profiler import PassProfiler
from gpu.resources import (
    IMAGE_BLOOM_A,
    IMAGE_BLOOM_B,
    IMAGE_CHARGE_IN,
    IMAGE_CHARGE_OUT,
    IMAGE_DISPLAY,
    IMAGE_DIVERGENCE,
    IMAGE_HUMIDITY_IN,
    IMAGE_HUMIDITY_OUT,
    IMAGE_MOISTURE_IN,
    IMAGE_MOISTURE_OUT,
    IMAGE_NUTRIENT_IN,
    IMAGE_NUTRIENT_OUT,
    IMAGE_PRESSURE_IN,
    IMAGE_PRESSURE_OUT,
    IMAGE_TEMPERATURE_IN,
    IMAGE_TEMPERATURE_OUT,
    IMAGE_VELOCITY_IN,
    IMAGE_VELOCITY_OUT,
    IMAGE_VORTICITY,
    SSBO_CELLS_READ,
)
from simulation.state import ExplosionState, ExplosionVfxState, WindState

# OpenGL image format constants (avoid importing GL headers)
_FMT_RG32F = 0x8230   # GL_RG32F
_FMT_R32F  = 0x822E   # GL_R32F
_FMT_RGBA8 = 0x8058   # GL_RGBA8


class Pipeline:
    """Owns shader programs, UBO updates, and the multi-pass GPU dispatch."""

    def __init__(
        self,
        ctx: moderngl.Context,
        buffers: BufferManager,
        ubo_manager: UBOManager,
        config: SimulationConfig,
        shaders: dict[str, moderngl.ComputeShader],
        context: moderngl.Context,
    ):
        self.ctx = ctx
        self.buffers = buffers
        self.ubo_manager = ubo_manager
        self.ctx = context
        self.config = config
        self.width = config.width
        self.height = config.height
        self.gx = (self.width + 31) // 32
        self.gy = (self.height + 31) // 32
        self.profiler = PassProfiler()
        self.frame = 0
        self.last_step_ms = 0.0
        self.last_render_ms = 0.0
        self.adaptive_quality = False  # Adaptive pass skipping enabled
        self.budget_ms = 1000.0 / 60.0  # 16.67ms for 60fps
        self._frame = 0
        # Quality tier state (v7 foundation)
        self.quality_tier_index = 0  # 0=high, 1=medium, 2=low
        self.fps_history = []  # FPS history for monitoring
        # Sparse region optimization (v7 foundation)
        self.sparse_mask = SparseMask(self.width, self.height)
        self.step_passes: tuple[ComputePass, ...] = default_step_passes()
        self.render_passes: tuple[ComputePass, ...] = default_render_passes()
        self.profiler = PassProfiler()

        # Ceil-dispatch so edges are always covered
        # Bind UBOs once at initialization
        self.ubo_manager.bind_all()

    def _timed_run(self, name: str, shader: moderngl.ComputeShader, **kwargs) -> None:
        """Dispatch *shader* while recording elapsed ms under *name*."""
        t0 = time.perf_counter()
        shader.run(**kwargs)
        elapsed = (time.perf_counter() - t0) * 1000.0
        self.profiler.record(name, elapsed)

    def set_shaders(self, shaders: dict[str, moderngl.ComputeShader]) -> None:
        self.state_shader = shaders["state"]
        self.liquid_step_shader = shaders["liquid_step"]
        self.heat_shader = shaders["heat"]
        self.force_shader = shaders["force"]
        self.divergence_shader = shaders["divergence"]
        self.pressure_shader = shaders["pressure"]
        self.project_shader = shaders["project"]
        self.vorticity_shader = shaders["vorticity"]
        self.vel_advect_shader = shaders["vel_advect"]
        self.advect_shader = shaders["advect"]
        self.render_shader = shaders["render"]
        self.acoustic_pressure_shader = shaders["acoustic_pressure"]
        self.acoustic_velocity_shader = shaders["acoustic_velocity"]
        self.electricity_shader = shaders["electricity"]
        self.electricity_arc_shader = shaders["electricity_arc"]
        self.biology_shader = shaders["biology"]
        self.weather_shader = shaders["weather"]
        self.bloom_extract_shader = shaders["bloom_extract"]
        self.bloom_blur_shader = shaders["bloom_blur"]

    # ── Display blit setup ──────────────────────────────────────────────────

    def _build_display_program(self) -> None:
        """Create fullscreen quad program to blit display_texture to the default framebuffer."""
        self._display_prog = self.ctx.program(
            vertex_shader=(
                "#version 330\n"
                "in vec2 in_vert; in vec2 in_uv; out vec2 v_uv;\n"
                "void main(){ v_uv = in_uv; gl_Position = vec4(in_vert, 0.0, 1.0); }\n"
            ),
            fragment_shader=(
                "#version 330\n"
                "in vec2 v_uv; out vec4 f_color;\n"
                "uniform sampler2D display;\n"
                "void main(){ f_color = texture(display, v_uv); }\n"
            ),
        )
        quad = np.array([
            -1.0, -1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 0.0,
            -1.0,  1.0, 0.0, 1.0,
             1.0,  1.0, 1.0, 1.0,
        ], dtype="f4")
        self._display_vbo = self.ctx.buffer(quad.tobytes())
        self._display_vao = self.ctx.vertex_array(
            self._display_prog, [(self._display_vbo, "2f 2f", "in_vert", "in_uv")]
        )

    # ── Legacy-uniform helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _set_if(prog, name, value, strict: bool = False) -> None:
        try:
            prog[name] = value
        except KeyError:
            if strict:
                raise  # Strict mode: raise error if uniform not found
            pass  # Uniform not declared in this shader — safe to skip

    def _set_common_uniforms(self, prog) -> None:
        self._set_if(prog, "gridSize", (self.width, self.height))
        self._set_if(prog, "frame", self._frame)
        self._set_if(prog, "ruleStride", RULE_STRIDE)
        self._set_if(prog, "ambientTemp", TEMP_AMBIENT)
        self._set_if(prog, "enableThermal", int(not self.config.no_thermal))
        self._set_if(prog, "enableTurbulence", int(not self.config.no_turbulence))
        self._set_if(prog, "enableWetDry", int(not self.config.no_wet_dry))
    # ── UBO updates ──────────────────────────────────────────────────────────
    # Shaders now use UBOs via #define macros in common.glsl.
    # The _set_common_uniforms calls are kept for backward compatibility during transition.

    def _update_ubos(
        self,
        dt: float,
        frame: int,
        explosion_state: ExplosionState,
        explosion_vfx_state: ExplosionVfxState,
        wind_state: WindState,
    ) -> None:
        self._frame = frame

        # Update SimConfig UBO (binding 3)
        sim_config = SimConfigData(
            gridSize=(self.width, self.height),
            frame=frame,
            dt=dt,
            ambientTemp=float(TEMP_AMBIENT),
            ruleStride=RULE_STRIDE,
            enableThermal=int(not self.config.no_thermal),
            enableTurbulence=int(not self.config.no_turbulence),
            enableWetDry=int(not self.config.no_wet_dry),
            gravity=9.8,  # Default gravity
            vorticityStrength=self.config.vorticity_confinement,
        )
        self.ubo_manager.update_sim_config(sim_config)

        # Update ExplosionConfig UBO (binding 4)
        explosion_config = ExplosionConfigData(
            center=explosion_state.center,
            radius=explosion_state.radius,
            force=explosion_state.force,
            isActive=int(explosion_state.is_active),
            age=float(explosion_state.frames_remaining),
            maxAge=float(max(1, explosion_state.frames_remaining)),
            type=explosion_state.explosion_type,
            soundSpeed=343.0,  # Default sound speed in m/s
            dtAcoustic=dt / max(1, self._compute_adaptive_substeps(dt) * max(1, self.config.acoustic_substeps)),
            energyDecayRate=0.95,
            reflectionDamping=0.8,
        )
        self.ubo_manager.update_explosion(explosion_config)

        # Update ExplosionVfxConfig UBO (binding 5)
        explosion_vfx_config = ExplosionVfxConfigData(
            flash=explosion_vfx_state.flash,
            pressurePulse=explosion_state.force * self.config.sound_speed,
            isFirstSubstep=1,  # Will be updated per substep
        )
        self.ubo_manager.update_explosion_vfx(explosion_vfx_config)

        # Update WindConfig UBO (binding 6)
        wind_config = WindConfigData(
            vector=wind_state.vector,
            enabled=int(wind_state.enabled),
        )
        self.ubo_manager.update_wind(wind_config)

    # ── Adaptive substeps ────────────────────────────────────────────────────

    def _compute_adaptive_substeps(self, dt_frame: float) -> int:
        """Compute substeps from config and frame dt for smoother stability."""
        base_substeps = max(1, self.config.sim_substeps)
        if not self.config.adaptive_substeps:
            return min(MAX_SUBSTEPS, base_substeps)

        reference_dt = 1.0 / 60.0
        dt_scale = max(1.0, dt_frame / reference_dt)
        adaptive_substeps = int(np.ceil(dt_scale))
        return min(MAX_SUBSTEPS, max(base_substeps, adaptive_substeps))

    def _should_skip_pass(self, pass_name: str, dt: float) -> bool:
        """Skip optional passes if frame budget exceeded."""
        if not self.adaptive_quality:
            return False
        
        budget_ms = self.budget_ms
        elapsed = self.profiler.total_step_ms()
        
        # Pass priority mapping (higher = more important)
        priority = {
            "biology": 1,
            "weather": 1,
            "electricity": 2,
            "electricity_arc": 2,
            "acoustic_pressure": 3,
            "acoustic_velocity": 3,
            "vorticity": 4,
            "heat": 4,
        }
        
        pass_priority = priority.get(pass_name, 0)
        
        # Skip non-critical optional passes if over budget
        if elapsed > budget_ms * 0.9:
            # Only skip low-priority passes
            if pass_priority <= 1:
                return True
        elif elapsed > budget_ms * 0.8:
            # Skip lowest priority passes
            if pass_priority <= 0:
                return True
        return False

    def update_quality_tier(self, fps: float) -> None:
        """Auto-adjust quality tier based on FPS."""
        if not self.config.adaptive_quality:
            return
        
        # Update FPS history
        self.fps_history.append(fps)
        if len(self.fps_history) > 60:
            self.fps_history.pop(0)
        
        # Only adjust after we have enough samples
        if len(self.fps_history) < 30:
            return
        
        avg_fps = sum(self.fps_history) / len(self.fps_history)
        min_fps = self.config.min_fps_target
        
        # Downgrade if FPS is too low for sustained period
        if avg_fps < min_fps * 0.9 and self.quality_tier_index < 2:
            self.quality_tier_index += 1
            self._apply_quality_tier()
            self.fps_history.clear()  # Reset history after adjustment
        
        # Upgrade if FPS is consistently high
        elif avg_fps > min_fps * 1.2 and self.quality_tier_index > 0:
            self.quality_tier_index -= 1
            self._apply_quality_tier()
            self.fps_history.clear()  # Reset history after adjustment

    def _apply_quality_tier(self) -> None:
        """Apply current quality tier settings."""
        tier = self.config.quality_tiers[self.quality_tier_index]
        self.config.pressure_iterations = tier["pressure_iterations"]
        self.config.acoustic_substeps = tier["acoustic_substeps"]
        self.config.bloom_enabled = tier["bloom_enabled"]

    def enable_sparse_mode(self, enabled: bool) -> None:
        """Enable or disable sparse region optimization."""
        self.sparse_mask.enable_sparse(enabled)

    # ── Multi-pass pipeline ──────────────────────────────────────────────────

    def step(
        self,
        dt: float,
        frame: int,
        explosion_state: ExplosionState,
        explosion_vfx_state: ExplosionVfxState,
        wind_state: WindState,
    ) -> None:
        """Run one frame of the GPU simulation pipeline."""
        start = time.perf_counter()
        self._update_ubos(dt, frame, explosion_state, explosion_vfx_state, wind_state)
        
        # Update sparse mask if enabled
        if self.sparse_mask.sparse_enabled:
            cells = self.buffers.cells_read.read()
            self.sparse_mask.update_mask(cells)
        
        self._step_multi_pass(dt, explosion_state, wind_state)
        self.last_step_ms = (time.perf_counter() - start) * 1000.0

    def _step_multi_pass(self, dt_frame: float, explosion_state: ExplosionState, wind_state: WindState) -> None:
        pressure_iterations = self.config.pressure_iterations

        adaptive_substeps = self._compute_adaptive_substeps(dt_frame)
        dt = dt_frame / max(1, adaptive_substeps)

        for _ in range(adaptive_substeps):
            # 1. State / reactions (no movement)
            self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.state_shader)
            self._timed_run("state", self.state_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_temp_buffers()
            self.buffers.swap_cell_buffers()

            # 1.5. Liquid physics (density separation, viscosity, surface tension)
            self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.liquid_step_shader)
            self._timed_run("liquid_step", self.liquid_step_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_temp_buffers()
            self.buffers.swap_cell_buffers()

            # 2. Heat diffusion
            if not self.config.no_thermal and self.config.heat_diffusion_iterations > 0:
                self.buffers.get_read_buf().bind_to_storage_buffer(SSBO_CELLS_READ)
                self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.heat_shader)
                self._set_if(self.heat_shader, "ambientTemp", float(TEMP_AMBIENT))
                self._set_if(self.heat_shader, "dt", dt)
                for heat_iter in range(self.config.heat_diffusion_iterations):
                    self._timed_run("heat", self.heat_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                    self.ctx.memory_barrier()
                    self.buffers.swap_temp_buffers()

            # 3. Compute vorticity for confinement
            if not self.config.no_turbulence and self.config.vorticity_confinement > 0.0:
                self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
                self.buffers.vorticity_tex.bind_to_image(IMAGE_VORTICITY, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.vorticity_shader)
                self._set_if(self.vorticity_shader, "confinementStrength", self.config.vorticity_confinement)
                self._timed_run("vorticity", self.vorticity_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()

            # 4. Semi-Lagrangian BFECC advection for velocity and temperature
            self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.vel_b.bind_to_image(IMAGE_VELOCITY_OUT, read=False, write=True, level=0, format=_FMT_RG32F)
            self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.vel_advect_shader)
            self._set_if(self.vel_advect_shader, "dt", dt)
            self._set_if(self.vel_advect_shader, "enableBFECC", int(self.config.use_maccormack))
            self._timed_run("velocity_advect", self.vel_advect_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_velocity_buffers()
            self.buffers.swap_temp_buffers()

            # 5. Forces → velocity (gravity, buoyancy, confinement)
            self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.vorticity_tex.bind_to_image(IMAGE_VORTICITY, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.vel_b.bind_to_image(IMAGE_VELOCITY_OUT, read=False, write=True, level=0, format=_FMT_RG32F)
            self._set_common_uniforms(self.force_shader)
            self._set_if(self.force_shader, "gravity", self.config.gravity)
            self._set_if(self.force_shader, "dt", dt)
            self._set_if(self.force_shader, "vorticityStrength", self.config.vorticity_confinement)
            self._set_if(self.force_shader, "enableVorticityConfinement", int(self.config.vorticity_confinement > 0.0))
            self._set_if(self.force_shader, "surfaceTensionStrength", self.config.surface_tension)
            self._set_if(self.force_shader, "thermalBuoyancyScale", self.config.thermal_convection)
            self._set_if(self.force_shader, "explosionRadius", explosion_state.radius)
            self._set_if(self.force_shader, "explosionForce", explosion_state.force)
            self._set_if(self.force_shader, "explosionIsActive", int(explosion_state.is_active))
            self._set_if(self.force_shader, "windVector", wind_state.get_vector())
            self._timed_run("force", self.force_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_velocity_buffers()

            # 6. Divergence calculation
            self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.div_tex.bind_to_image(IMAGE_DIVERGENCE, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.divergence_shader)
            self._timed_run("divergence", self.divergence_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()

            # 7. Pressure Jacobi iterations (red-black Gauss-Seidel)
            for i in range(pressure_iterations):
                self.buffers.div_tex.bind_to_image(IMAGE_DIVERGENCE, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.pres_a.bind_to_image(IMAGE_PRESSURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.pres_b.bind_to_image(IMAGE_PRESSURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.pressure_shader)
                self._set_if(self.pressure_shader, "iteration", i)
                self._timed_run("pressure", self.pressure_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()
                self.buffers.swap_pressure_buffers()

            # 8. Projection: v -= grad(p)
            self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.pres_a.bind_to_image(IMAGE_PRESSURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.vel_b.bind_to_image(IMAGE_VELOCITY_OUT, read=False, write=True, level=0, format=_FMT_RG32F)
            self._set_common_uniforms(self.project_shader)
            self._timed_run("project", self.project_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_velocity_buffers()

            # 9. Electricity propagation
            if self.config.enable_electricity:
                self.buffers.get_read_buf().bind_to_storage_buffer(SSBO_CELLS_READ)
                self.buffers.charge_a.bind_to_image(IMAGE_CHARGE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.charge_b.bind_to_image(IMAGE_CHARGE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.electricity_shader)
                self._set_if(self.electricity_shader, "dt", dt)
                self._set_if(self.electricity_shader, "chargeDecay", self.config.charge_decay)
                self._set_if(self.electricity_shader, "maxCharge", self.config.max_charge)
                self._timed_run("electricity", self.electricity_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()
                self.buffers.swap_charge_buffers()

                # 9b. Electricity arc breakdown
                self.buffers.get_read_buf().bind_to_storage_buffer(SSBO_CELLS_READ)
                self.buffers.charge_a.bind_to_image(IMAGE_CHARGE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.charge_b.bind_to_image(IMAGE_CHARGE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self.buffers.div_tex.bind_to_image(IMAGE_DIVERGENCE, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.electricity_arc_shader)
                self._set_if(self.electricity_arc_shader, "dt", dt)
                self._set_if(self.electricity_arc_shader, "breakdownThreshold", self.config.breakdown_threshold)
                self._set_if(self.electricity_arc_shader, "arcTempDelta", self.config.arc_temp_delta)
                self._set_if(self.electricity_arc_shader, "arcPressurePulse", self.config.arc_pressure_pulse)
                self._timed_run("electricity_arc", self.electricity_arc_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()
                self.buffers.swap_charge_buffers()
                self.buffers.swap_temp_buffers()

            # 10. Biology / ecology
            if self.config.enable_biology and not self._should_skip_pass("biology", dt):
                self.buffers.get_read_buf().bind_to_storage_buffer(SSBO_CELLS_READ)
                self.buffers.nutrient_a.bind_to_image(IMAGE_NUTRIENT_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.nutrient_b.bind_to_image(IMAGE_NUTRIENT_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self.buffers.moisture_a.bind_to_image(IMAGE_MOISTURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.moisture_b.bind_to_image(IMAGE_MOISTURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.biology_shader)
                self._set_if(self.biology_shader, "dt", dt)
                self._set_if(self.biology_shader, "nutrientDiffuseRate", self.config.nutrient_diffuse_rate)
                self._set_if(self.biology_shader, "moistureDiffuseRate", self.config.moisture_diffuse_rate)
                self._set_if(self.biology_shader, "moistureEvapRate", getattr(self.config, "moisture_evap_rate", 0.02))
                self._set_if(self.biology_shader, "growthRate", self.config.growth_rate)
                self._set_if(self.biology_shader, "decayRate", self.config.decay_rate)
                self._set_if(self.biology_shader, "nutrientConsumeRate", getattr(self.config, "nutrient_consume_rate", 0.2))
                self._set_if(self.biology_shader, "moistureConsumeRate", getattr(self.config, "moisture_consume_rate", 0.15))
                self._set_if(self.biology_shader, "waterMoistureBoost", getattr(self.config, "water_moisture_boost", 5.0))
                self._set_if(self.biology_shader, "dirtNutrientRegen", getattr(self.config, "dirt_nutrient_regen", 0.01))
                self._timed_run("biology", self.biology_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()
                self.buffers.swap_nutrient_buffers()
                self.buffers.swap_moisture_buffers()

            # 11. Weather / atmospheric
            if self.config.enable_weather and not self._should_skip_pass("weather", dt):
                self.buffers.get_read_buf().bind_to_storage_buffer(SSBO_CELLS_READ)
                self.buffers.humidity_a.bind_to_image(IMAGE_HUMIDITY_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.humidity_b.bind_to_image(IMAGE_HUMIDITY_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.weather_shader)
                self._set_if(self.weather_shader, "dt", dt)
                self._set_if(self.weather_shader, "humidityDiffuseRate", self.config.humidity_diffuse_rate)
                self._set_if(self.weather_shader, "evaporationRate", self.config.evaporation_rate)
                self._set_if(self.weather_shader, "condensationRate", self.config.condensation_rate)
                self._set_if(self.weather_shader, "saturationThreshold", self.config.saturation_threshold)
                self._set_if(self.weather_shader, "rainSpeed", self.config.rain_speed)
                self._set_if(self.weather_shader, "transpirationRate", self.config.transpiration_rate)
                self._set_if(self.weather_shader, "windAdvectStrength", getattr(self.config, "wind_advect_strength", 0.5))
                self._set_if(self.weather_shader, "windVector", getattr(self.config, "wind_vector", (0.0, 0.0)))
                self._timed_run("weather", self.weather_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()
                self.buffers.swap_humidity_buffers()

            # 12. Acoustic solver loop (weakly-compressible gas)
            if not self.config.no_acoustics:
                acoustic_substeps = self.config.acoustic_substeps
                dt_ac = dt / max(1, acoustic_substeps)
                for sub_i in range(acoustic_substeps):
                    # 9a. Acoustic pressure step
                    self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
                    self.buffers.pres_a.bind_to_image(IMAGE_PRESSURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                    self.buffers.pres_b.bind_to_image(IMAGE_PRESSURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
                    self._set_common_uniforms(self.acoustic_pressure_shader)
                    self._set_if(self.acoustic_pressure_shader, "soundSpeed", self.config.sound_speed)
                    self._set_if(self.acoustic_pressure_shader, "dtAcoustic", dt_ac)
                    self._set_if(self.acoustic_pressure_shader, "ambientPressure", self.config.atm_pressure)
                    self._set_if(self.acoustic_pressure_shader, "explosionCenter", explosion_state.center)
                    self._set_if(self.acoustic_pressure_shader, "explosionRadius", explosion_state.radius)
                    self._set_if(self.acoustic_pressure_shader, "explosionPressurePulse", explosion_state.force * self.config.sound_speed)
                    self._set_if(self.acoustic_pressure_shader, "explosionIsActive", int(explosion_state.is_active))
                    self._set_if(self.acoustic_pressure_shader, "isFirstSubstep", 1 if sub_i == 0 else 0)
                    self._set_if(self.acoustic_pressure_shader, "explosionType", explosion_state.explosion_type)
                    self._set_if(self.acoustic_pressure_shader, "energyDecayRate", 0.15)
                    self._set_if(self.acoustic_pressure_shader, "reflectionDamping", 0.3)
                    self._timed_run("acoustic_pressure", self.acoustic_pressure_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                    self.ctx.memory_barrier()
                    self.buffers.swap_pressure_buffers()

                    # 9b. Acoustic velocity step
                    self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
                    self.buffers.pres_a.bind_to_image(IMAGE_PRESSURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
                    self.buffers.vel_b.bind_to_image(IMAGE_VELOCITY_OUT, read=False, write=True, level=0, format=_FMT_RG32F)
                    self._set_common_uniforms(self.acoustic_velocity_shader)
                    self._set_if(self.acoustic_velocity_shader, "dtAcoustic", dt_ac)
                    self._set_if(self.acoustic_velocity_shader, "ambientPressure", self.config.atm_pressure)
                    self._timed_run("acoustic_velocity", self.acoustic_velocity_shader, group_x=self.gx, group_y=self.gy, group_z=1)
                    self.ctx.memory_barrier()
                    self.buffers.swap_velocity_buffers()

            # 10. Advect cells along velocity (also handles powder fall).
            #     Carries float temperature alongside cell moves.
            self.buffers.clear_reservations()
            self.buffers.clear_write_buf_to_air()
            self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.advect_shader)
            self._set_if(self.advect_shader, "dt", dt)
            self._timed_run("advect", self.advect_shader, group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_cell_buffers()
            self.buffers.swap_temp_buffers()

    # ── Render ──────────────────────────────────────────────────────────────

    def render(
        self,
        show_pressure: bool,
        explosion_vfx_state: ExplosionVfxState,
        debug_view: int = 0,
    ) -> None:
        """Render cells into display_texture and blit to the default framebuffer."""
        # ── Bloom post-FX (if enabled) ────────────────────────────────────────
        bloom_enabled = getattr(self.config, "bloom_enabled", True) and debug_view == 0
        if bloom_enabled:
            # 1. Extract bright pixels + downsample to half-res
            self.buffers.display_texture.bind_to_image(IMAGE_DISPLAY, read=True, write=False, level=0, format=_FMT_RGBA8)
            self.buffers.bloom_a.bind_to_image(IMAGE_BLOOM_A, read=False, write=True, level=0, format=_FMT_RGBA8)
            self._set_common_uniforms(self.bloom_extract_shader)
            self._set_if(self.bloom_extract_shader, "bloomThreshold", self.config.bloom_threshold)
            self._set_if(self.bloom_extract_shader, "bloomIntensity", self.config.bloom_intensity)
            self._timed_run("bloom_extract", self.bloom_extract_shader,
                            group_x=max(1, (self.width + 31) // 32),
                            group_y=max(1, (self.height + 31) // 32), group_z=1)
            self.ctx.memory_barrier()

            # 2. Horizontal blur: bloom_a → bloom_b
            self.buffers.bloom_a.bind_to_image(IMAGE_BLOOM_A, read=True, write=False, level=0, format=_FMT_RGBA8)
            self.buffers.bloom_b.bind_to_image(IMAGE_BLOOM_B, read=False, write=True, level=0, format=_FMT_RGBA8)
            self._set_common_uniforms(self.bloom_blur_shader)
            self._set_if(self.bloom_blur_shader, "blurDirection", 0)
            self._set_if(self.bloom_blur_shader, "blurRadius", self.config.bloom_radius)
            # Map quality string to sample count
            blur_samples = 5 if self.config.bloom_quality == "high" else (3 if self.config.bloom_quality == "medium" else 1)
            self._set_if(self.bloom_blur_shader, "blurSamples", blur_samples)
            self._timed_run("bloom_blur_h", self.bloom_blur_shader,
                            group_x=max(1, (self.width + 31) // 32),
                            group_y=max(1, (self.height + 31) // 32), group_z=1)
            self.ctx.memory_barrier()

            # 3. Vertical blur: bloom_b → bloom_a
            self.buffers.bloom_b.bind_to_image(IMAGE_BLOOM_A, read=True, write=False, level=0, format=_FMT_RGBA8)
            self.buffers.bloom_a.bind_to_image(IMAGE_BLOOM_B, read=False, write=True, level=0, format=_FMT_RGBA8)
            self._set_if(self.bloom_blur_shader, "blurDirection", 1)
            self._set_if(self.bloom_blur_shader, "blurRadius", self.config.bloom_radius)
            self._set_if(self.bloom_blur_shader, "blurSamples", blur_samples)
            self._timed_run("bloom_blur_v", self.bloom_blur_shader,
                            group_x=max(1, (self.width + 31) // 32),
                            group_y=max(1, (self.height + 31) // 32), group_z=1)
            self.ctx.memory_barrier()

        # ── Main render pass ──────────────────────────────────────────────────
        self.buffers.get_read_buf().bind_to_storage_buffer(SSBO_CELLS_READ)
        self.buffers.vel_a.bind_to_image(IMAGE_VELOCITY_IN, read=True, write=False, level=0, format=_FMT_RG32F)
        self.buffers.pres_a.bind_to_image(IMAGE_PRESSURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.charge_a.bind_to_image(IMAGE_CHARGE_IN, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.nutrient_a.bind_to_image(IMAGE_NUTRIENT_IN, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.moisture_a.bind_to_image(IMAGE_MOISTURE_IN, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.humidity_a.bind_to_image(IMAGE_HUMIDITY_IN, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.display_texture.bind_to_image(IMAGE_DISPLAY, read=False, write=True, level=0, format=_FMT_RGBA8)
        self.buffers.bloom_a.bind_to_image(IMAGE_BLOOM_A, read=True, write=False, level=0, format=_FMT_RGBA8)
        self._set_common_uniforms(self.render_shader)
        self._set_if(self.render_shader, "showPressure", int(show_pressure))
        self._set_if(self.render_shader, "debugView", debug_view)
        self._set_if(self.render_shader, "ambientPressure", self.config.atm_pressure)
        self._set_if(self.render_shader, "explosionFlash", float(explosion_vfx_state.flash))
        self._set_if(self.render_shader, "explosionCenter", explosion_vfx_state.center)
        self._set_if(self.render_shader, "explosionAge", float(explosion_vfx_state.age))
        self._set_if(self.render_shader, "explosionMaxAge", float(explosion_vfx_state.max_age))
        self._timed_run("render", self.render_shader, group_x=self.gx, group_y=self.gy, group_z=1)
        self.ctx.memory_barrier(moderngl.ALL_BARRIER_BITS)

        # Blit display_texture to screen
        self.ctx.screen.use()
        self.ctx.screen.clear(0.0, 0.0, 0.0)
        self.ctx.disable(moderngl.BLEND)
        self.buffers.display_texture.use(location=0)
        self._display_prog["display"] = 0
        self._display_vao.render(moderngl.TRIANGLE_STRIP)
