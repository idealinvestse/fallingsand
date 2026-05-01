"""Simulation state management for explosions and wind."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class ExplosionType(IntEnum):
    """Types of explosions with distinct characteristics."""

    HIGH_EXPLOSIVE = 0   # Fast, brisance, shattering (C4)
    DEFLAGRATION = 1     # Slower burn, more push than shatter (gunpowder)
    THERMOBARIC = 2      # Air-fuel, uses oxygen, large radius (fuel-air)
    NAPALM = 3           # Persistent burning, spreads fire
    FRAGMENTATION = 4    # Produces many small fragments (grenade)


@dataclass(slots=True)
class ExplosionState:
    """State for explosion physics and visual effects."""

    center: tuple[float, float] = (0.0, 0.0)
    radius: float = 0.0
    force: float = 0.0
    is_active: int = 0
    frames_remaining: int = 0
    explosion_type: int = 0  # ExplosionType value
    crater_radius: float = 0.0
    fragment_count: int = 0

    def trigger(
        self,
        x: float,
        y: float,
        radius: float,
        force: float,
        duration: int,
        explosion_type: int = 0,
        crater_radius: float = 0.0,
    ) -> None:
        """Trigger a new explosion with optional type and crater size."""
        self.center = (x, y)
        self.radius = radius
        self.force = force
        self.is_active = 1
        self.frames_remaining = duration
        self.explosion_type = explosion_type
        self.crater_radius = crater_radius
        self.fragment_count = 0

    def update(self) -> None:
        """Update explosion state (call each frame)."""
        if self.is_active == 1:
            self.frames_remaining -= 1
            if self.frames_remaining <= 0:
                self.is_active = 0


@dataclass(slots=True)
class ExplosionVfxState:
    """State for explosion visual effects."""

    flash: float = 0.0
    age: float = 0.0
    max_age: float = 1.5
    decay_rate: float = 0.1
    center: tuple[float, float] = (0.0, 0.0)

    def trigger(self, x: float, y: float, flash_intensity: float = 0.6) -> None:
        """Trigger visual effects for an explosion."""
        self.flash = flash_intensity
        self.age = 0.0
        self.center = (x, y)

    def update(self) -> None:
        """Update visual effects state (call each frame)."""
        if self.flash > 0.0:
            self.flash = max(0.0, self.flash - 0.05)
        if self.flash > 0.0 or self.age > 0.0:
            self.age += self.decay_rate
            if self.age > self.max_age:
                self.age = 0.0


@dataclass(slots=True)
class WindState:
    """State for wind simulation."""

    vector: list[float] = field(default_factory=lambda: [0.0, 0.0])
    enabled: bool = False

    def adjust(self, dx: float, dy: float) -> None:
        """Adjust wind vector with clamping."""
        self.vector[0] = max(-1.0, min(1.0, self.vector[0] + dx))
        self.vector[1] = max(-1.0, min(1.0, self.vector[1] + dy))
        if dx != 0 or dy != 0:
            self.enabled = True

    def toggle(self) -> None:
        """Toggle wind on/off."""
        self.enabled = not self.enabled

    def get_vector(self) -> tuple[float, float]:
        """Get wind vector (returns (0,0) if disabled)."""
        if self.enabled:
            return (self.vector[0], self.vector[1])
        return (0.0, 0.0)
