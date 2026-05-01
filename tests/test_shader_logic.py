"""Static analysis of the v5 multi-pass GPU shaders.

These tests don't require a GPU context — they just verify that each shader
source file has the expected structure, bindings, and uniforms.
"""

from pathlib import Path

import pytest

SHADERS_DIR = Path(__file__).parent.parent / "shaders"

EXPECTED_SHADERS = [
    "state_shader.glsl",
    "liquid_step.glsl",
    "heat_shader.glsl",
    "force_shader.glsl",
    "divergence_shader.glsl",
    "pressure_shader.glsl",
    "project_shader.glsl",
    "vorticity_shader.glsl",
    "velocity_advect_shader.glsl",
    "advect_shader.glsl",
    "render_shader.glsl",
    "acoustic_pressure_step.glsl",
    "acoustic_velocity_step.glsl",
]


def _read(name: str) -> str:
    return (SHADERS_DIR / name).read_text(encoding="utf-8")


def _compiled_source(name: str) -> str:
    """Return the source as the runtime shader loader compiles it."""
    common_src = _read("common.glsl")
    return common_src + _read(name)


class TestShaderFiles:
    def test_shaders_dir_exists(self):
        assert SHADERS_DIR.is_dir()

    def test_no_legacy_single_pass_shader(self):
        """margolus_sim.glsl was removed in v5."""
        assert not (SHADERS_DIR.parent / "margolus_sim.glsl").exists()

    @pytest.mark.parametrize("name", EXPECTED_SHADERS)
    def test_shader_exists(self, name):
        assert (SHADERS_DIR / name).is_file()

    @pytest.mark.parametrize("name", EXPECTED_SHADERS)
    def test_shader_has_version_and_compute_layout(self, name):
        src = _compiled_source(name)
        assert src.lstrip().startswith("#version 430"), f"{name} must target GLSL 4.30"
        assert "layout(local_size_x" in src, f"{name} must declare compute local size"


class TestStatePass:
    def test_thermal_and_reactions(self):
        src = _read("state_shader.glsl")
        assert "THERMAL" in src or "thermal" in src.lower()
        assert "rxn1_p" in src, "state shader should consume reaction slots"

    def test_defines_near_virus(self):
        """Regression: v4 had an undefined `nearVirus` reference."""
        src = _read("state_shader.glsl")
        if "nearVirus" in src:
            assert "bool nearVirus" in src, "nearVirus must be defined before use"


class TestForcePass:
    def test_uses_gravity_and_dt(self):
        src = _read("force_shader.glsl")
        assert "gravity" in src
        assert "uniform float dt" in src

    def test_reads_velocity_in_writes_out(self):
        src = _read("force_shader.glsl")
        assert "velIn" in src and "velOut" in src


class TestDivergenceAndPressure:
    def test_divergence_writes_r32f(self):
        src = _read("divergence_shader.glsl")
        assert "divergenceTex" in src
        assert "r32f" in src.lower()

    def test_pressure_variable_density_poisson(self):
        """Variable-density Poisson: Σ w_n (p_n − p_self) = div_self.

        w_n = 1/ρ_face and ρ_face is the harmonic mean of neighbour densities.
        The shader no longer hard-codes the constant-density factor 0.25.
        """
        src = _read("pressure_shader.glsl")
        # Variable-density helpers must exist.
        assert "faceInvRho" in src, "pressure solver must use density-weighted face coefficients"
        assert "RHO_MIN" in src, "minimum density floor required for numerical safety"
        # Weighted sum denominator (wSum) replaces constant 1/4.
        assert "/ wSum" in src or "wSum" in src, "variable-density solve must divide by sum of weights"
        # Harmonic mean is the standard FV face density for two-phase flow.
        assert "harmonic" in src.lower() or "2.0 * a * b" in src, "face density should use harmonic mean"
        assert "pressureIn" in src and "pressureOut" in src


class TestProjectPass:
    def test_subtracts_gradient(self):
        src = _read("project_shader.glsl")
        assert "gradP" in src or "grad" in src.lower()
        assert "v -=" in src or "v -" in src


class TestAdvectPass:
    def test_declares_reservations_ssbo(self):
        src = _read("advect_shader.glsl")
        assert "ReservationBuf" in src or "reservations[" in src
        assert "binding = 8" in src

    def test_uses_atomic_reservation(self):
        src = _read("advect_shader.glsl")
        assert "atomicCompSwap" in src

    def test_handles_powders_and_fluids(self):
        src = _read("advect_shader.glsl")
        assert "cat == 1" in src, "advect must have a powder branch"
        assert "velTex" in src, "advect must read velocity"


class TestRenderPass:
    def test_writes_display_texture(self):
        src = _read("render_shader.glsl")
        assert "displayTexture" in src
        assert "imageStore" in src


class TestTemperatureBindings:
    @pytest.mark.parametrize("name", [
        "state_shader.glsl",
        "liquid_step.glsl",
        "heat_shader.glsl",
        "velocity_advect_shader.glsl",
        "advect_shader.glsl",
        "render_shader.glsl",
    ])
    def test_temperature_images_are_r32f(self, name):
        src = _read(name).lower()
        if "binding=11" in src or "binding = 11" in src:
            assert "r32f" in src
        if "binding=12" in src or "binding = 12" in src:
            assert "r32f" in src
