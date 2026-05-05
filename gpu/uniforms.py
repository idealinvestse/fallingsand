"""Uniform Buffer Object manager for efficient GPU uniform updates."""

import moderngl
import numpy as np
from typing import TYPE_CHECKING
from dataclasses import dataclass

from gpu.resources import UBO_EXPLOSION, UBO_EXPLOSION_VFX, UBO_SIM_CONFIG, UBO_WIND

if TYPE_CHECKING:
    pass


@dataclass(slots=True)
class SimConfigData:
    """Simulation configuration data for UBO."""
    gridSize: tuple[int, int]
    frame: int
    dt: float
    ambientTemp: float
    ruleStride: int
    enableThermal: int
    enableTurbulence: int
    enableWetDry: int
    gravity: float
    vorticityStrength: float

    def to_bytes(self) -> bytes:
        """Convert to bytes for UBO upload (std140 layout)."""
        # std140: uvec2 (8), uint (4), float (4) = 16 bytes aligned
        # Total: uvec2(8) + uint(4) + float(4) + float(4) + uint(4) + int(4) + int(4) + int(4) + float(4) + float(4) = 48 bytes
        # 48 bytes = 12 float32 elements
        data = np.zeros(12, dtype=np.float32)
        data[0] = self.gridSize[0]
        data[1] = self.gridSize[1]
        data[2] = float(self.frame)
        data[3] = self.dt
        data[4] = self.ambientTemp
        data[5] = float(self.ruleStride)
        data[6] = float(self.enableThermal)
        data[7] = float(self.enableTurbulence)
        data[8] = float(self.enableWetDry)
        data[9] = self.gravity
        data[10] = self.vorticityStrength
        return data.tobytes()


@dataclass(slots=True)
class ExplosionConfigData:
    """Explosion physics data for UBO."""
    center: tuple[float, float]
    radius: float
    force: float
    isActive: int
    age: float
    maxAge: float
    type: int
    soundSpeed: float
    dtAcoustic: float
    energyDecayRate: float
    reflectionDamping: float

    def to_bytes(self) -> bytes:
        """Convert to bytes for UBO upload (std140 layout)."""
        # vec2(8) + float(4) + float(4) + int(4) + float(4) + float(4) + int(4) + float(4) + float(4) + float(4) + float(4) = 52 bytes
        # Round up to nearest 16-byte multiple: 64 bytes = 16 float32 elements
        data = np.zeros(16, dtype=np.float32)
        data[0] = self.center[0]
        data[1] = self.center[1]
        data[2] = self.radius
        data[3] = self.force
        data[4] = float(self.isActive)
        data[5] = self.age
        data[6] = self.maxAge
        data[7] = float(self.type)
        data[8] = self.soundSpeed
        data[9] = self.dtAcoustic
        data[10] = self.energyDecayRate
        data[11] = self.reflectionDamping
        return data.tobytes()


@dataclass(slots=True)
class ExplosionVfxConfigData:
    """Explosion visual effects data for UBO."""
    flash: float
    pressurePulse: float
    isFirstSubstep: int

    def to_bytes(self) -> bytes:
        """Convert to bytes for UBO upload (std140 layout)."""
        # float(4) + float(4) + int(4) = 12 bytes, round to 16 bytes = 4 float32 elements
        data = np.zeros(4, dtype=np.float32)
        data[0] = self.flash
        data[1] = self.pressurePulse
        data[2] = float(self.isFirstSubstep)
        return data.tobytes()


@dataclass(slots=True)
class WindConfigData:
    """Wind configuration data for UBO."""
    vector: tuple[float, float]
    enabled: int

    def to_bytes(self) -> bytes:
        """Convert to bytes for UBO upload (std140 layout)."""
        # vec2(8) + int(4) = 12 bytes, round to 16 bytes = 4 float32 elements
        data = np.zeros(4, dtype=np.float32)
        data[0] = self.vector[0]
        data[1] = self.vector[1]
        data[2] = float(self.enabled)
        return data.tobytes()


class UBOManager:
    """Manages Uniform Buffer Objects for efficient GPU updates."""

    def __init__(self, ctx: moderngl.Context):
        """Initialize all UBOs."""
        self.ctx = ctx

        # Sim config UBO (binding 3) - 48 bytes
        self.sim_config_ubo = ctx.buffer(reserve=48)

        # Explosion physics UBO (binding 4) - 64 bytes
        self.explosion_ubo = ctx.buffer(reserve=64)

        # Explosion VFX UBO (binding 5) - 16 bytes
        self.explosion_vfx_ubo = ctx.buffer(reserve=16)

        # Wind UBO (binding 6) - 16 bytes
        self.wind_ubo = ctx.buffer(reserve=16)

    def bind_all(self) -> None:
        """Bind all UBOs to their binding points."""
        self.sim_config_ubo.bind_to_uniform_block(UBO_SIM_CONFIG)
        self.explosion_ubo.bind_to_uniform_block(UBO_EXPLOSION)
        self.explosion_vfx_ubo.bind_to_uniform_block(UBO_EXPLOSION_VFX)
        self.wind_ubo.bind_to_uniform_block(UBO_WIND)

    def update_sim_config(self, data: SimConfigData) -> None:
        """Update simulation config UBO."""
        self.sim_config_ubo.write(data.to_bytes())

    def update_explosion(self, data: ExplosionConfigData) -> None:
        """Update explosion physics UBO."""
        self.explosion_ubo.write(data.to_bytes())

    def update_explosion_vfx(self, data: ExplosionVfxConfigData) -> None:
        """Update explosion VFX UBO."""
        self.explosion_vfx_ubo.write(data.to_bytes())

    def update_wind(self, data: WindConfigData) -> None:
        """Update wind UBO."""
        self.wind_ubo.write(data.to_bytes())
