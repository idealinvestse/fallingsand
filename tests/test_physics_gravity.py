"""Static assertions on physics convention in force_shader.

These tests enforce the sign conventions agreed upon in the physics rework:
  * y increases upward, so gravity subtracts from v.y for falling cells.
  * Gas buoyancy is sign-independent of r.density (so fire with rho<0 still rises).
  * Pump boost keeps its +gravity kick on liquids.
"""

from pathlib import Path


def test_force_shader_gravity_signs_are_consistent() -> None:
    shader = Path("shaders/force_shader.glsl").read_text(encoding="utf-8")

    # Powder and liquid both feel gravity pulling them down (v.y decreases).
    assert "v.y -= gravity * densityScale * dt;" in shader
    assert "v.y -= gravity * 1.25 * dt;" in shader
    # Shrapnel should also fall downward under reduced gravity.
    assert "v.y -= gravity * 0.6 * dt;" in shader
    # Pump boost is still upward.
    assert "v.y += gravity * 2.2 * dt;" in shader


def test_force_shader_gas_buoyancy_is_sign_independent() -> None:
    """Gas buoyancy must be relative to air density so air is neutral.

    Concretely, the shader uses baseBuoy = RHO_AIR - r.density so:
    - Air (ρ=0.12) → baseBuoy=0 (neutral, no self-buoyancy).
    - Buoyant gases (ρ<0.12, e.g. fire, smoke) → positive (↑ rise).
    - Heavy gases (ρ>0.12, e.g. O₂) → negative (↓ sink).
    """
    shader = Path("shaders/force_shader.glsl").read_text(encoding="utf-8")
    assert "float baseBuoy = RHO_AIR - r.density;" in shader
    # ALPHA_GAS * dT adds an upward thermal term; ΔT is computed relative to ambient.
    assert "ALPHA_GAS" in shader
    assert "dT = tempF - ambientN" in shader
    # The previous ideal-gas formulation that produced sign-flip bugs is gone.
    assert "T_kelvin = tempF * 373.15" not in shader


def test_force_shader_liquid_thermal_expansion() -> None:
    """Hot liquid must rise: buoyancy uses (rho_0 - rho_eff) with rho_eff<rho_0 when hot."""
    shader = Path("shaders/force_shader.glsl").read_text(encoding="utf-8")
    assert "BETA_LIQ" in shader
    assert "(1.0 - BETA_LIQ * dT)" in shader
    assert "(r.density - effectiveDensity)" in shader


def test_force_shader_low_viscosity_damping_floor() -> None:
    shader = Path("shaders/force_shader.glsl").read_text(encoding="utf-8")
    assert "mix(0.985, 0.82" in shader
