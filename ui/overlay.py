"""Shared overlay rendering infrastructure for pygame→OpenGL UI panels."""

from __future__ import annotations

import numpy as np
import pygame
import moderngl


class OverlayRenderer:
    """Base class providing pygame-surface→GL-texture→fullscreen-quad rendering.

    Subclasses create a pygame surface via their own logic, then call
    ``render_fullscreen()`` or ``render_positioned()`` to blit it to the
    default framebuffer.
    """

    def __init__(self, ctx: moderngl.Context, window_size: tuple[int, int]):
        self.ctx = ctx
        self.window_width, self.window_height = window_size

        # Fullscreen quad program
        self._prog = ctx.program(
            vertex_shader=(
                "#version 330\n"
                "in vec2 in_vert; in vec2 in_uv; out vec2 v_uv;\n"
                "void main(){ v_uv = in_uv; gl_Position = vec4(in_vert, 0.0, 1.0); }\n"
            ),
            fragment_shader=(
                "#version 330\n"
                "in vec2 v_uv; out vec4 f_color; uniform sampler2D overlay;\n"
                "void main(){ f_color = texture(overlay, v_uv); }\n"
            ),
        )

        # Positioned quad program (for inspector-style floating panels)
        self._pos_prog = ctx.program(
            vertex_shader="""
                #version 330
                uniform vec2 u_offset;
                uniform vec2 u_scale;
                in vec2 in_vert;
                in vec2 in_uv;
                out vec2 v_uv;
                void main() {
                    v_uv = in_uv;
                    gl_Position = vec4(in_vert * u_scale + u_offset, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                in vec2 v_uv;
                out vec4 f_color;
                uniform sampler2D overlay;
                void main() {
                    vec4 tex = texture(overlay, v_uv);
                    f_color = tex;
                }
            """,
        )

        quad = np.array([
            -1.0, -1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 0.0,
            -1.0,  1.0, 0.0, 1.0,
             1.0,  1.0, 1.0, 1.0,
        ], dtype="f4")
        self._vbo = ctx.buffer(quad.tobytes())

        self._vao = ctx.vertex_array(
            self._prog, [(self._vbo, "2f 2f", "in_vert", "in_uv")]
        )
        self._pos_vao = ctx.vertex_array(
            self._pos_prog, [(self._vbo, "2f 2f", "in_vert", "in_uv")]
        )

        self._texture: moderngl.Texture | None = None

    # ── Surface → texture ──────────────────────────────────────────────────

    def _surface_to_texture(self, surface: pygame.Surface) -> moderngl.Texture:
        """Upload a pygame surface (with alpha) to an OpenGL texture."""
        rgb = pygame.surfarray.array3d(surface)
        a = pygame.surfarray.array_alpha(surface)
        rgba = np.dstack((rgb, a))
        rgba = np.transpose(rgba, (1, 0, 2))
        rgba = np.flipud(rgba)

        if self._texture is None or self._texture.size != surface.get_size():
            self._texture = self.ctx.texture(
                surface.get_size(), 4, rgba.tobytes()
            )
        else:
            self._texture.write(rgba.tobytes())
        return self._texture

    # ── Rendering ──────────────────────────────────────────────────────────

    def render_fullscreen(self, surface: pygame.Surface) -> None:
        """Render a pygame surface covering the entire window."""
        tex = self._surface_to_texture(surface)
        self.ctx.screen.use()
        tex.use(location=0)
        self._prog["overlay"] = 0
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        self._vao.render(moderngl.TRIANGLE_STRIP)

    def render_positioned(
        self,
        surface: pygame.Surface,
        ndc_offset: tuple[float, float],
        ndc_scale: tuple[float, float],
    ) -> None:
        """Render a pygame surface at a specific NDC position/size."""
        tex = self._surface_to_texture(surface)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        self._pos_prog["u_offset"] = ndc_offset
        self._pos_prog["u_scale"] = ndc_scale
        tex.use(location=0)
        self._pos_prog["overlay"] = 0
        self._pos_vao.render(moderngl.TRIANGLE_STRIP)

        self.ctx.disable(moderngl.BLEND)
