"""Core type definitions for the simulation."""

from dataclasses import dataclass
from enum import IntEnum


class Category(IntEnum):
    """Material movement category used by the physics pipeline."""
    GAS = 0
    POWDER = 1
    LIQUID = 2
    SOLID = 3


class StateFamily(IntEnum):
    """Finer-grained material classification used by rendering/AI."""
    POWDER = 0
    LIQUID = 1
    GAS = 2
    SOLID = 3
    ENERGETIC = 4
    BIO = 5


@dataclass(frozen=True, slots=True)
class Material:
    """Material definition with all physical properties."""
    name: str
    color: tuple[int, int, int]
    density: float
    category: Category
    flammability: float
    thermal_conductivity: float
    phase_high_id: int
    phase_high_temp: int
    phase_low_id: int
    phase_low_temp: int
    electrical_conductivity: float
    emissivity: float
    cooling_rate: float
    burn_to: int
    viscosity: float
    turbulence: float
    wet_dry: int
    default_flame_temp: int
    default_flame_life: int
    # New fields for expanded physics
    heat_capacity: float  # Scales temp delta per absorbed heat
    melting_point: int  # Temperature at which material melts (0-255 scale)
    boiling_point: int  # Temperature at which material boils (0-255 scale)
    surface_tension: float  # 0-1, liquid cohesion bias
    solubility: float  # 0-1, probability to dissolve in water
    cohesion: float  # 0-1, powder pile angle (higher = steeper)
    restitution: float  # 0-1, velocity preserved on bounce from solids
    state_family: StateFamily  # More detailed classification
    # Reaction slots (up to 3 reactions per material)
    # Each reaction: partner_type, product_self, product_neighbor, prob, temp_threshold
    reaction_1_partner: int
    reaction_1_product_self: int
    reaction_1_product_neighbor: int
    reaction_1_prob: float
    reaction_1_temp_threshold: int
    reaction_2_partner: int
    reaction_2_product_self: int
    reaction_2_product_neighbor: int
    reaction_2_prob: float
    reaction_2_temp_threshold: int
    reaction_3_partner: int
    reaction_3_product_self: int
    reaction_3_product_neighbor: int
    reaction_3_prob: float
    reaction_3_temp_threshold: int
    # Explosive properties (for energetic materials)
    explosive_power: float  # 0-1, explosion strength
    detonation_temp: int  # Temperature threshold for detonation
    blast_radius: int  # Base blast radius in cells
    blast_duration: int  # Frames the blast lasts
    fragment_type: int  # Material ID for fragments
    shockwave_speed: float  # Cells per frame shockwave expands
    # Oxygen / combustion properties
    oxygen_requirement: float  # 0-1, how much O2 this material needs to sustain combustion
    oxygen_yield: float  # 0-1, how much O2 is consumed per combustion tick
    moisture_resistance: float = 0.0  # 0-1, resistance to wet fire suppression
    wet_ignition_penalty: float = 0.0  # extra temperature needed when wet
    wet_burn_rate_multiplier: float = 1.0  # fire life/heat multiplier when wet


@dataclass(slots=True)
class Cell:
    """Single simulation cell with packed representation.

    Cell packing: type[0..7] | life[8..15] | flags[16..23] | unused[24..31]
    Temperature is stored separately in r32f float textures.
    """
    type_id: int
    life: int  # 0-255
    flags: int  # 0-255

    def pack(self) -> int:
        """Pack cell into 32-bit uint."""
        return (
            (self.type_id & 0xFF)
            | ((self.life & 0xFF) << 8)
            | ((self.flags & 0xFF) << 16)
        )

    @classmethod
    def unpack(cls, packed: int) -> "Cell":
        """Unpack 32-bit uint into Cell."""
        return cls(
            type_id=packed & 0xFF,
            life=(packed >> 8) & 0xFF,
            flags=(packed >> 16) & 0xFF,
        )


