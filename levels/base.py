from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from simulation.engine import SimulationEngine


@dataclass(slots=True)
class Level:
    level_id: str
    name: str
    description: str
    thumbnail_color: tuple[int, int, int]
    build: Callable[[SimulationEngine], None]
    tags: tuple[str, ...] = ()
    difficulty: int = 1
    objective: str = ""
    is_custom: bool = False
