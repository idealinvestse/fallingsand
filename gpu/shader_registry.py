"""Shader registry: loads and caches all compute shaders for the simulation pipeline."""

from __future__ import annotations

from pathlib import Path

import moderngl

from shader_loader import load_shader


def _shader_dir() -> Path:
    return Path(__file__).parent.parent / "shaders"


def _load_shader_with_common(ctx: moderngl.Context, shader_path: Path) -> moderngl.ComputeShader:
    """Load a shader with common.glsl prepended for shared definitions."""
    d = _shader_dir()
    common_code = load_shader(d / "common.glsl")
    shader_code = load_shader(shader_path)
    combined = common_code + shader_code
    return ctx.compute_shader(combined)


def load_all_shaders(ctx: moderngl.Context) -> dict[str, moderngl.ComputeShader]:
    """Load every compute shader and return a name→program mapping."""
    d = _shader_dir()
    return {
        "state":             _load_shader_with_common(ctx, d / "state_shader.glsl"),
        "liquid_step":       _load_shader_with_common(ctx, d / "liquid_step.glsl"),
        "heat":              _load_shader_with_common(ctx, d / "heat_shader.glsl"),
        "force":             _load_shader_with_common(ctx, d / "force_shader.glsl"),
        "divergence":        _load_shader_with_common(ctx, d / "divergence_shader.glsl"),
        "pressure":          _load_shader_with_common(ctx, d / "pressure_shader.glsl"),
        "project":           _load_shader_with_common(ctx, d / "project_shader.glsl"),
        "vorticity":         _load_shader_with_common(ctx, d / "vorticity_shader.glsl"),
        "vel_advect":        _load_shader_with_common(ctx, d / "velocity_advect_shader.glsl"),
        "advect":            _load_shader_with_common(ctx, d / "advect_shader.glsl"),
        "render":            _load_shader_with_common(ctx, d / "render_shader.glsl"),
        "acoustic_pressure": _load_shader_with_common(ctx, d / "acoustic_pressure_step.glsl"),
        "acoustic_velocity": _load_shader_with_common(ctx, d / "acoustic_velocity_step.glsl"),
    }
