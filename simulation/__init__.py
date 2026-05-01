"""Simulation module for physics engine and state management."""

from .brush import BrushPainter
from .materials import MaterialRegistry
from .persistence import PersistenceManager
from .state import ExplosionState, ExplosionVfxState, WindState
from .yaml_loader import load_material_definitions

__all__ = [
    "BrushPainter",
    "MaterialRegistry",
    "PersistenceManager",
    "ExplosionState",
    "ExplosionVfxState",
    "WindState",
    "load_material_definitions",
]
