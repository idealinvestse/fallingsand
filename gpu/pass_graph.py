"""Declarative metadata for the GPU compute pass graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComputePass:
    name: str
    shader_key: str
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    swaps: tuple[str, ...] = ()
    optional: bool = False
    iterative: bool = False


STEP_PASS_ORDER: tuple[str, ...] = (
    "state",
    "liquid_step",
    "heat",
    "vorticity",
    "velocity_advect",
    "force",
    "divergence",
    "pressure",
    "project",
    "electricity",
    "electricity_arc",
    "biology",
    "weather",
    "acoustic_pressure",
    "acoustic_velocity",
    "advect",
)

RENDER_PASS_ORDER: tuple[str, ...] = ("render",)

DEFAULT_STEP_PASSES: tuple[ComputePass, ...] = (
    ComputePass(
        name="state",
        shader_key="state",
        reads=("cells_read", "rules", "temperature_in", "moisture_in", "humidity_in"),
        writes=("cells_write", "temperature_out"),
        swaps=("cells", "temperature"),
    ),
    ComputePass(
        name="liquid_step",
        shader_key="liquid_step",
        reads=("cells_read", "rules", "temperature_in", "nutrient_in", "velocity_in"),
        writes=("cells_write", "temperature_out", "nutrient_out"),
        swaps=("cells", "temperature", "nutrient"),
    ),
    ComputePass(
        name="heat",
        shader_key="heat",
        reads=("cells_read", "rules", "temperature_in"),
        writes=("temperature_out",),
        swaps=("temperature",),
        optional=True,
        iterative=True,
    ),
    ComputePass(
        name="vorticity",
        shader_key="vorticity",
        reads=("velocity_in",),
        writes=("vorticity",),
        optional=True,
    ),
    ComputePass(
        name="velocity_advect",
        shader_key="vel_advect",
        reads=("cells_read", "rules", "velocity_in", "temperature_in"),
        writes=("velocity_out", "temperature_out"),
        swaps=("velocity", "temperature"),
    ),
    ComputePass(
        name="force",
        shader_key="force",
        reads=("cells_read", "rules", "velocity_in", "vorticity", "temperature_in"),
        writes=("velocity_out",),
        swaps=("velocity",),
    ),
    ComputePass(
        name="divergence",
        shader_key="divergence",
        reads=("velocity_in",),
        writes=("divergence",),
    ),
    ComputePass(
        name="pressure",
        shader_key="pressure",
        reads=("cells_read", "rules", "divergence", "pressure_in"),
        writes=("pressure_out",),
        swaps=("pressure",),
        iterative=True,
    ),
    ComputePass(
        name="project",
        shader_key="project",
        reads=("cells_read", "rules", "velocity_in", "pressure_in"),
        writes=("velocity_out",),
        swaps=("velocity",),
    ),
    ComputePass(
        name="electricity",
        shader_key="electricity",
        reads=("cells_read", "rules", "charge_in", "moisture_in", "velocity_in"),
        writes=("charge_out",),
        swaps=("charge",),
        optional=True,
    ),
    ComputePass(
        name="electricity_arc",
        shader_key="electricity_arc",
        reads=("cells_read", "rules", "charge_in", "temperature_in", "moisture_in"),
        writes=("charge_out", "temperature_out", "divergence"),
        swaps=("charge", "temperature"),
        optional=True,
    ),
    ComputePass(
        name="biology",
        shader_key="biology",
        reads=("cells_read", "rules", "nutrient_in", "moisture_in", "temperature_in", "charge_in"),
        writes=("nutrient_out", "moisture_out"),
        swaps=("nutrient", "moisture"),
        optional=True,
    ),
    ComputePass(
        name="weather",
        shader_key="weather",
        reads=("cells_read", "humidity_in", "temperature_in", "moisture_in", "charge_in"),
        writes=("humidity_out",),
        swaps=("humidity",),
        optional=True,
    ),
    ComputePass(
        name="acoustic_pressure",
        shader_key="acoustic_pressure",
        reads=("velocity_in", "pressure_in"),
        writes=("pressure_out",),
        swaps=("pressure",),
        optional=True,
        iterative=True,
    ),
    ComputePass(
        name="acoustic_velocity",
        shader_key="acoustic_velocity",
        reads=("velocity_in", "pressure_in"),
        writes=("velocity_out",),
        swaps=("velocity",),
        optional=True,
        iterative=True,
    ),
    ComputePass(
        name="advect",
        shader_key="advect",
        reads=("cells_read", "rules", "reservations", "velocity_in", "temperature_in"),
        writes=("cells_write", "reservations", "temperature_out"),
        swaps=("cells", "temperature"),
    ),
)

DEFAULT_RENDER_PASSES: tuple[ComputePass, ...] = (
    ComputePass(
        name="render",
        shader_key="render",
        reads=("cells_read", "rules", "velocity_in", "pressure_in", "temperature_in"),
        writes=("display",),
    ),
)


def default_step_passes() -> tuple[ComputePass, ...]:
    return DEFAULT_STEP_PASSES


def default_render_passes() -> tuple[ComputePass, ...]:
    return DEFAULT_RENDER_PASSES
