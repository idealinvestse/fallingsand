"""Shader registry: loads and caches all compute shaders for the simulation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import moderngl

from shader_loader import load_shader


@dataclass(frozen=True, slots=True)
class ShaderManifestEntry:
    key: str
    filename: str
    include_common: bool = True


SHADER_MANIFEST: tuple[ShaderManifestEntry, ...] = (
    ShaderManifestEntry("state", "state_shader.glsl"),
    ShaderManifestEntry("liquid_step", "liquid_step.glsl"),
    ShaderManifestEntry("heat", "heat_shader.glsl"),
    ShaderManifestEntry("force", "force_shader.glsl"),
    ShaderManifestEntry("divergence", "divergence_shader.glsl"),
    ShaderManifestEntry("pressure", "pressure_shader.glsl"),
    ShaderManifestEntry("project", "project_shader.glsl"),
    ShaderManifestEntry("vorticity", "vorticity_shader.glsl"),
    ShaderManifestEntry("vel_advect", "velocity_advect_shader.glsl"),
    ShaderManifestEntry("advect", "advect_shader.glsl"),
    ShaderManifestEntry("render", "render_shader.glsl"),
    ShaderManifestEntry("acoustic_pressure", "acoustic_pressure_step.glsl"),
    ShaderManifestEntry("acoustic_velocity", "acoustic_velocity_step.glsl"),
    ShaderManifestEntry("electricity", "electricity_step.glsl"),
    ShaderManifestEntry("electricity_arc", "electricity_arc.glsl"),
    ShaderManifestEntry("biology", "biology_step.glsl"),
    ShaderManifestEntry("weather", "weather_step.glsl"),
)


def _shader_dir() -> Path:
    return Path(__file__).parent.parent / "shaders"


def shader_manifest_by_key() -> dict[str, ShaderManifestEntry]:
    return {entry.key: entry for entry in SHADER_MANIFEST}


def _load_shader_source(entry: ShaderManifestEntry) -> str:
    d = _shader_dir()
    shader_code = load_shader(d / entry.filename)
    if not entry.include_common:
        return shader_code
    common_code = load_shader(d / "common.glsl")
    return common_code + shader_code


def _load_shader_with_common(ctx: moderngl.Context, shader_path: Path) -> moderngl.ComputeShader:
    """Load a shader with common.glsl prepended for shared definitions."""
    d = _shader_dir()
    common_code = load_shader(d / "common.glsl")
    shader_code = load_shader(shader_path)
    combined = common_code + shader_code
    return ctx.compute_shader(combined)


def load_shader_by_key(ctx: moderngl.Context, key: str) -> moderngl.ComputeShader:
    manifest = shader_manifest_by_key()
    if key not in manifest:
        raise KeyError(f"Unknown shader key: {key}")
    return ctx.compute_shader(_load_shader_source(manifest[key]))


def reload_shader(ctx: moderngl.Context, shaders: dict[str, moderngl.ComputeShader], key: str) -> moderngl.ComputeShader:
    shader = load_shader_by_key(ctx, key)
    shaders[key] = shader
    return shader


def load_all_shaders(ctx: moderngl.Context) -> dict[str, moderngl.ComputeShader]:
    """Load every compute shader and return a name→program mapping."""
    return {entry.key: ctx.compute_shader(_load_shader_source(entry)) for entry in SHADER_MANIFEST}
