from __future__ import annotations

from levels.base import Level
from levels.builtin import BUILTIN_LEVELS
from levels.custom import CustomLevelStore

_store = CustomLevelStore()


def get_builtin_levels() -> list[Level]:
    return list(BUILTIN_LEVELS)


def get_custom_levels() -> list[Level]:
    return _store.list_custom_levels()


def get_all_levels() -> list[Level]:
    return get_builtin_levels() + get_custom_levels()


def get_level_by_id(level_id: str) -> Level | None:
    for level in get_all_levels():
        if level.level_id == level_id:
            return level
    return None


def get_custom_store() -> CustomLevelStore:
    return _store
