"""GPU simulation pipeline orchestrating the v5 multi-pass compute dispatch."""

from __future__ import annotations

import moderngl
import numpy as np
import time

from core.config import SimulationConfig
from core.constants import MAX_SUBSTEPS, RULE_STRIDE, TEMP_AMBIENT
from gpu.buffers import BufferManager
from gpu.uniforms import (
    UBOManager,
    SimConfigData,
    ExplosionConfigData,
    ExplosionVfxConfigData,
    WindConfigData,
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
        grid_size: tuple[int, int],
    ):
        self.ctx = ctx
        self.buffers = buffers
        self.ubo_manager = ubo_manager
        self.config = config
        self.width, self.height = grid_size

        # Shader programs
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

        # Ceil-dispatch so edges are always covered
        self.gx = (self.width + 15) // 16
        self.gy = (self.height + 15) // 16

        # Display blit program
        self._build_display_program()
        self.last_step_ms = 0.0
        self.last_render_ms = 0.0
        self._frame = 0

        # Bind UBOs once at initialization
        self.ubo_manager.bind_all()

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
        self._step_multi_pass(dt, explosion_state, wind_state)
        self.last_step_ms = (time.perf_counter() - start) * 1000.0

    def _step_multi_pass(self, dt_frame: float, explosion_state: ExplosionState, wind_state: WindState) -> None:
        pressure_iterations = self.config.pressure_iterations

        adaptive_substeps = self._compute_adaptive_substeps(dt_frame)
        dt = dt_frame / max(1, adaptive_substeps)

        for _ in range(adaptive_substeps):
            # 1. State / reactions (no movement)
            self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(12, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.state_shader)
            self.state_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_temp_buffers()
            self.buffers.swap_cell_buffers()

            # 1.5. Liquid physics (density separation, viscosity, surface tension)
            self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(12, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.liquid_step_shader)
            self.liquid_step_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_temp_buffers()
            self.buffers.swap_cell_buffers()

            # 2. Heat diffusion
            if not self.config.no_thermal and self.config.heat_diffusion_iterations > 0:
                self.buffers.get_read_buf().bind_to_storage_buffer(0)
                self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.temp_b.bind_to_image(12, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.heat_shader)
                self._set_if(self.heat_shader, "ambientTemp", float(TEMP_AMBIENT))
                self._set_if(self.heat_shader, "dt", dt)
                for heat_iter in range(self.config.heat_diffusion_iterations):
                    self.heat_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
                    self.ctx.memory_barrier()
                    self.buffers.swap_temp_buffers()

            # 3. Compute vorticity for confinement
            if not self.config.no_turbulence and self.config.vorticity_confinement > 0.0:
                self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
                self.buffers.vorticity_tex.bind_to_image(8, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.vorticity_shader)
                self._set_if(self.vorticity_shader, "confinementStrength", self.config.vorticity_confinement)
                self.vorticity_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()

            # 4. Semi-Lagrangian BFECC advection for velocity and temperature
            self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.vel_b.bind_to_image(4, read=False, write=True, level=0, format=_FMT_RG32F)
            self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(12, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.vel_advect_shader)
            self._set_if(self.vel_advect_shader, "dt", dt)
            self._set_if(self.vel_advect_shader, "enableBFECC", int(self.config.use_maccormack))
            self.vel_advect_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_velocity_buffers()
            self.buffers.swap_temp_buffers()

            # 5. Forces → velocity (gravity, buoyancy, confinement)
            self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.vorticity_tex.bind_to_image(8, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.vel_b.bind_to_image(4, read=False, write=True, level=0, format=_FMT_RG32F)
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
            self.force_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_velocity_buffers()

            # 6. Divergence calculation
            self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.div_tex.bind_to_image(4, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.divergence_shader)
            self.divergence_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()

            # 7. Pressure Jacobi iterations (red-black Gauss-Seidel)
            for i in range(pressure_iterations):
                self.buffers.div_tex.bind_to_image(4, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.pres_a.bind_to_image(5, read=True, write=False, level=0, format=_FMT_R32F)
                self.buffers.pres_b.bind_to_image(6, read=False, write=True, level=0, format=_FMT_R32F)
                self._set_common_uniforms(self.pressure_shader)
                self._set_if(self.pressure_shader, "iteration", i)
                self.pressure_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
                self.ctx.memory_barrier()
                self.buffers.swap_pressure_buffers()

            # 8. Projection: v -= grad(p)
            self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.pres_a.bind_to_image(5, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.vel_b.bind_to_image(4, read=False, write=True, level=0, format=_FMT_RG32F)
            self._set_common_uniforms(self.project_shader)
            self.project_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_velocity_buffers()

            # 9. Acoustic solver loop (weakly-compressible gas)
            if not self.config.no_acoustics:
                acoustic_substeps = self.config.acoustic_substeps
                dt_ac = dt / max(1, acoustic_substeps)
                for sub_i in range(acoustic_substeps):
                    # 9a. Acoustic pressure step
                    self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
                    self.buffers.pres_a.bind_to_image(5, read=True, write=False, level=0, format=_FMT_R32F)
                    self.buffers.pres_b.bind_to_image(6, read=False, write=True, level=0, format=_FMT_R32F)
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
                    self.acoustic_pressure_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
                    self.ctx.memory_barrier()
                    self.buffers.swap_pressure_buffers()

                    # 9b. Acoustic velocity step
                    self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
                    self.buffers.pres_a.bind_to_image(5, read=True, write=False, level=0, format=_FMT_R32F)
                    self.buffers.vel_b.bind_to_image(4, read=False, write=True, level=0, format=_FMT_RG32F)
                    self._set_common_uniforms(self.acoustic_velocity_shader)
                    self._set_if(self.acoustic_velocity_shader, "dtAcoustic", dt_ac)
                    self._set_if(self.acoustic_velocity_shader, "ambientPressure", self.config.atm_pressure)
                    self.acoustic_velocity_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
                    self.ctx.memory_barrier()
                    self.buffers.swap_velocity_buffers()

            # 10. Advect cells along velocity (also handles powder fall).
            #     Carries float temperature alongside cell moves.
            self.buffers.clear_reservations()
            self.buffers.clear_write_buf_to_air()
            self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
            self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
            self.buffers.temp_b.bind_to_image(12, read=False, write=True, level=0, format=_FMT_R32F)
            self._set_common_uniforms(self.advect_shader)
            self._set_if(self.advect_shader, "dt", dt)
            self.advect_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
            self.ctx.memory_barrier()
            self.buffers.swap_cell_buffers()
            self.buffers.swap_temp_buffers()

    # ── Render ──────────────────────────────────────────────────────────────

    def render(
        self,
        show_pressure: bool,
        explosion_vfx_state: ExplosionVfxState,
    ) -> None:
        """Render cells into display_texture and blit to the default framebuffer."""
        self.buffers.get_read_buf().bind_to_storage_buffer(0)
        self.buffers.vel_a.bind_to_image(3, read=True, write=False, level=0, format=_FMT_RG32F)
        self.buffers.pres_a.bind_to_image(5, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.temp_a.bind_to_image(11, read=True, write=False, level=0, format=_FMT_R32F)
        self.buffers.display_texture.bind_to_image(7, read=False, write=True, level=0, format=_FMT_RGBA8)
        self._set_common_uniforms(self.render_shader)
        self._set_if(self.render_shader, "showPressure", int(show_pressure))
        self._set_if(self.render_shader, "ambientPressure", self.config.atm_pressure)
        self._set_if(self.render_shader, "explosionFlash", float(explosion_vfx_state.flash))
        self._set_if(self.render_shader, "explosionCenter", explosion_vfx_state.center)
        self._set_if(self.render_shader, "explosionAge", float(explosion_vfx_state.age))
        self._set_if(self.render_shader, "explosionMaxAge", float(explosion_vfx_state.max_age))
        self.render_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)
        self.ctx.memory_barrier(moderngl.ALL_BARRIER_BITS)

        # Blit display_texture to screen
        self.ctx.screen.use()
        self.ctx.screen.clear(0.0, 0.0, 0.0)
        self.ctx.disable(moderngl.BLEND)
        self.buffers.display_texture.use(location=0)
        self._display_prog["display"] = 0
        self._display_vao.render(moderngl.TRIANGLE_STRIP)
