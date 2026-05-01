"""Core module for falling sand simulation configuration and types."""

from .config import SimulationConfig
from .constants import NUM_TYPES, RULE_STRIDE, TEMP_AMBIENT
from .types import Category, Cell, Material

__all__ = [
    "SimulationConfig",
    "NUM_TYPES",
    "RULE_STRIDE",
    "TEMP_AMBIENT",
    "Category",
    "Cell",
    "Material",
]
