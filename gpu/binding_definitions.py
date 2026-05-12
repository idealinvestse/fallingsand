"""Single source of truth for GPU resource bindings.

This file defines all GPU buffer and texture bindings in a structured format.
Run tools/generate_bindings.py to regenerate Python constants and GLSL includes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BindingKind(str, Enum):
    """Type of GPU resource binding."""
    SSBO = "ssbo"
    IMAGE = "image"
    UBO = "ubo"


@dataclass(frozen=True, slots=True)
class BindingDef:
    """Definition of a single GPU resource binding."""
    name: str
    kind: BindingKind
    binding: int
    glsl_type: str
    access: str  # readonly, writeonly, readwrite, coherent
    purpose: str


# ── SSBO Bindings (Shader Storage Buffer Objects) ─────────────────────────────

SSBO_BINDINGS: tuple[BindingDef, ...] = (
    BindingDef(
        name="cells_read",
        kind=BindingKind.SSBO,
        binding=0,
        glsl_type="uint[]",
        access="readonly",
        purpose="Cell data read buffer",
    ),
    BindingDef(
        name="cells_write",
        kind=BindingKind.SSBO,
        binding=1,
        glsl_type="uint[]",
        access="writeonly",
        purpose="Cell data write buffer",
    ),
    BindingDef(
        name="rules",
        kind=BindingKind.SSBO,
        binding=2,
        glsl_type="float[]",
        access="readonly",
        purpose="Material rule buffer",
    ),
    BindingDef(
        name="reservations",
        kind=BindingKind.SSBO,
        binding=8,
        glsl_type="uint[]",
        access="coherent",
        purpose="Cell move reservations",
    ),
    BindingDef(
        name="counters",
        kind=BindingKind.SSBO,
        binding=9,
        glsl_type="uint[]",
        access="coherent",
        purpose="Statistics counters",
    ),
)

# ── Image2D Texture Bindings ───────────────────────────────────────────────────

IMAGE_BINDINGS: tuple[BindingDef, ...] = (
    BindingDef(
        name="velocity_in",
        kind=BindingKind.IMAGE,
        binding=3,
        glsl_type="rg32f",
        access="read",
        purpose="Velocity field input",
    ),
    BindingDef(
        name="velocity_out",
        kind=BindingKind.IMAGE,
        binding=4,
        glsl_type="rg32f",
        access="write",
        purpose="Velocity field output",
    ),
    BindingDef(
        name="divergence",
        kind=BindingKind.IMAGE,
        binding=4,
        glsl_type="r32f",
        access="write",
        purpose="Divergence field output",
    ),
    BindingDef(
        name="pressure_in",
        kind=BindingKind.IMAGE,
        binding=5,
        glsl_type="r32f",
        access="read",
        purpose="Pressure field input",
    ),
    BindingDef(
        name="pressure_out",
        kind=BindingKind.IMAGE,
        binding=6,
        glsl_type="r32f",
        access="write",
        purpose="Pressure field output",
    ),
    BindingDef(
        name="display",
        kind=BindingKind.IMAGE,
        binding=7,
        glsl_type="rgba8",
        access="write",
        purpose="Final render output",
    ),
    BindingDef(
        name="vorticity",
        kind=BindingKind.IMAGE,
        binding=8,
        glsl_type="r32f",
        access="readwrite",
        purpose="Vorticity field",
    ),
    BindingDef(
        name="temperature_in",
        kind=BindingKind.IMAGE,
        binding=11,
        glsl_type="r32f",
        access="read",
        purpose="Temperature field input",
    ),
    BindingDef(
        name="temperature_out",
        kind=BindingKind.IMAGE,
        binding=12,
        glsl_type="r32f",
        access="write",
        purpose="Temperature field output",
    ),
    BindingDef(
        name="charge_in",
        kind=BindingKind.IMAGE,
        binding=9,
        glsl_type="r32f",
        access="read",
        purpose="Electric charge/potential input",
    ),
    BindingDef(
        name="charge_out",
        kind=BindingKind.IMAGE,
        binding=10,
        glsl_type="r32f",
        access="write",
        purpose="Electric charge/potential output",
    ),
    BindingDef(
        name="nutrient_in",
        kind=BindingKind.IMAGE,
        binding=13,
        glsl_type="r32f",
        access="read",
        purpose="Nutrient field input",
    ),
    BindingDef(
        name="nutrient_out",
        kind=BindingKind.IMAGE,
        binding=14,
        glsl_type="r32f",
        access="write",
        purpose="Nutrient field output",
    ),
    BindingDef(
        name="moisture_in",
        kind=BindingKind.IMAGE,
        binding=15,
        glsl_type="r32f",
        access="read",
        purpose="Moisture field input",
    ),
    BindingDef(
        name="moisture_out",
        kind=BindingKind.IMAGE,
        binding=16,
        glsl_type="r32f",
        access="write",
        purpose="Moisture field output",
    ),
    BindingDef(
        name="humidity_in",
        kind=BindingKind.IMAGE,
        binding=17,
        glsl_type="r32f",
        access="read",
        purpose="Atmospheric humidity input",
    ),
    BindingDef(
        name="humidity_out",
        kind=BindingKind.IMAGE,
        binding=18,
        glsl_type="r32f",
        access="write",
        purpose="Atmospheric humidity output",
    ),
    BindingDef(
        name="bloom_a",
        kind=BindingKind.IMAGE,
        binding=19,
        glsl_type="rgba8",
        access="readwrite",
        purpose="Bloom buffer A (half-res)",
    ),
    BindingDef(
        name="bloom_b",
        kind=BindingKind.IMAGE,
        binding=20,
        glsl_type="rgba8",
        access="readwrite",
        purpose="Bloom buffer B (half-res)",
    ),
)

# ── UBO Bindings (Uniform Buffer Objects) ───────────────────────────────────────

UBO_BINDINGS: tuple[BindingDef, ...] = (
    BindingDef(
        name="SimConfig",
        kind=BindingKind.UBO,
        binding=3,
        glsl_type="std140",
        access="read",
        purpose="Grid size, dt, frame",
    ),
    BindingDef(
        name="ExplosionConfig",
        kind=BindingKind.UBO,
        binding=4,
        glsl_type="std140",
        access="read",
        purpose="Explosion physics parameters",
    ),
    BindingDef(
        name="ExplosionVfxConfig",
        kind=BindingKind.UBO,
        binding=5,
        glsl_type="std140",
        access="read",
        purpose="Explosion visual effects",
    ),
    BindingDef(
        name="WindConfig",
        kind=BindingKind.UBO,
        binding=6,
        glsl_type="std140",
        access="read",
        purpose="Wind vector and enabled flag",
    ),
)

# ── All Bindings Combined ────────────────────────────────────────────────────────

ALL_BINDINGS: tuple[BindingDef, ...] = SSBO_BINDINGS + IMAGE_BINDINGS + UBO_BINDINGS
