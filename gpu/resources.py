"""Central GPU resource binding contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResourceKind(str, Enum):
    SSBO = "ssbo"
    IMAGE = "image"
    UBO = "ubo"


@dataclass(frozen=True, slots=True)
class ResourceBinding:
    name: str
    kind: ResourceKind
    binding: int
    glsl_type: str
    access: str
    purpose: str


SSBO_BINDINGS: tuple[ResourceBinding, ...] = (
    ResourceBinding("cells_read", ResourceKind.SSBO, 0, "uint[]", "readonly", "Cell data read buffer"),
    ResourceBinding("cells_write", ResourceKind.SSBO, 1, "uint[]", "writeonly", "Cell data write buffer"),
    ResourceBinding("rules", ResourceKind.SSBO, 2, "float[]", "readonly", "Material rule buffer"),
    ResourceBinding("reservations", ResourceKind.SSBO, 8, "uint[]", "coherent", "Cell move reservations"),
    ResourceBinding("counters", ResourceKind.SSBO, 9, "uint[]", "coherent", "Statistics counters"),
)

IMAGE_BINDINGS: tuple[ResourceBinding, ...] = (
    ResourceBinding("velocity_in", ResourceKind.IMAGE, 3, "rg32f", "read", "Velocity field input"),
    ResourceBinding("velocity_out", ResourceKind.IMAGE, 4, "rg32f", "write", "Velocity field output"),
    ResourceBinding("divergence", ResourceKind.IMAGE, 4, "r32f", "write", "Divergence field output"),
    ResourceBinding("pressure_in", ResourceKind.IMAGE, 5, "r32f", "read", "Pressure field input"),
    ResourceBinding("pressure_out", ResourceKind.IMAGE, 6, "r32f", "write", "Pressure field output"),
    ResourceBinding("display", ResourceKind.IMAGE, 7, "rgba8", "write", "Final render output"),
    ResourceBinding("vorticity", ResourceKind.IMAGE, 8, "r32f", "readwrite", "Vorticity field"),
    ResourceBinding("temperature_in", ResourceKind.IMAGE, 11, "r32f", "read", "Temperature field input"),
    ResourceBinding("temperature_out", ResourceKind.IMAGE, 12, "r32f", "write", "Temperature field output"),
    ResourceBinding("charge_in", ResourceKind.IMAGE, 9, "r32f", "read", "Electric charge/potential input"),
    ResourceBinding("charge_out", ResourceKind.IMAGE, 10, "r32f", "write", "Electric charge/potential output"),
    ResourceBinding("nutrient_in", ResourceKind.IMAGE, 13, "r32f", "read", "Nutrient field input"),
    ResourceBinding("nutrient_out", ResourceKind.IMAGE, 14, "r32f", "write", "Nutrient field output"),
    ResourceBinding("moisture_in", ResourceKind.IMAGE, 15, "r32f", "read", "Moisture field input"),
    ResourceBinding("moisture_out", ResourceKind.IMAGE, 16, "r32f", "write", "Moisture field output"),
    ResourceBinding("humidity_in", ResourceKind.IMAGE, 17, "r32f", "read", "Atmospheric humidity input"),
    ResourceBinding("humidity_out", ResourceKind.IMAGE, 18, "r32f", "write", "Atmospheric humidity output"),
)

UBO_BINDINGS: tuple[ResourceBinding, ...] = (
    ResourceBinding("SimConfig", ResourceKind.UBO, 3, "std140", "read", "Grid size, dt, frame"),
    ResourceBinding("ExplosionConfig", ResourceKind.UBO, 4, "std140", "read", "Explosion physics parameters"),
    ResourceBinding("ExplosionVfxConfig", ResourceKind.UBO, 5, "std140", "read", "Explosion visual effects"),
    ResourceBinding("WindConfig", ResourceKind.UBO, 6, "std140", "read", "Wind vector and enabled flag"),
)


ALL_BINDINGS: tuple[ResourceBinding, ...] = SSBO_BINDINGS + IMAGE_BINDINGS + UBO_BINDINGS

SSBO_CELLS_READ = 0
SSBO_CELLS_WRITE = 1
SSBO_RULES = 2
SSBO_RESERVATIONS = 8
SSBO_COUNTERS = 9

IMAGE_VELOCITY_IN = 3
IMAGE_VELOCITY_OUT = 4
IMAGE_DIVERGENCE = 4
IMAGE_PRESSURE_IN = 5
IMAGE_PRESSURE_OUT = 6
IMAGE_DISPLAY = 7
IMAGE_VORTICITY = 8
IMAGE_TEMPERATURE_IN = 11
IMAGE_TEMPERATURE_OUT = 12
IMAGE_CHARGE_IN = 9
IMAGE_CHARGE_OUT = 10
IMAGE_NUTRIENT_IN = 13
IMAGE_NUTRIENT_OUT = 14
IMAGE_MOISTURE_IN = 15
IMAGE_MOISTURE_OUT = 16
IMAGE_HUMIDITY_IN = 17
IMAGE_HUMIDITY_OUT = 18

UBO_SIM_CONFIG = 3
UBO_EXPLOSION = 4
UBO_EXPLOSION_VFX = 5
UBO_WIND = 6


def bindings_by_kind(kind: ResourceKind) -> tuple[ResourceBinding, ...]:
    return tuple(binding for binding in ALL_BINDINGS if binding.kind == kind)


def find_binding(kind: ResourceKind, name: str) -> ResourceBinding:
    for binding in ALL_BINDINGS:
        if binding.kind == kind and binding.name == name:
            return binding
    raise KeyError(f"Unknown {kind.value} binding: {name}")
