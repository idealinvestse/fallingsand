import pytest

from levels import get_all_levels, get_builtin_levels, get_level_by_id


class _FakeEngine:
    """Minimal stand-in for SimulationEngine used by level build functions.

    Records every cell painted via apply_brush so tests can assert on
    placed materials and coordinates without initialising an OpenGL context.
    """

    def __init__(self, width: int = 256, height: int = 256) -> None:
        self.width = width
        self.height = height
        self.cells: dict[tuple[int, int], int] = {}

    def apply_brush(self, cx: int, cy: int, radius: int, material_id: int,
                    mode: int = 0, delta: int = 0) -> None:
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > r2:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.cells[(x, y)] = material_id


def _run(level_id: str, width: int = 256, height: int = 256) -> _FakeEngine:
    level = get_level_by_id(level_id)
    assert level is not None, f"Missing level: {level_id}"
    engine = _FakeEngine(width, height)
    level.build(engine)
    return engine


def test_builtin_levels_are_unique() -> None:
    levels = get_builtin_levels()
    ids = [lvl.level_id for lvl in levels]
    assert len(ids) >= 7
    assert len(ids) == len(set(ids))


def test_all_levels_resolve_by_id() -> None:
    levels = get_all_levels()
    for level in levels:
        found = get_level_by_id(level.level_id)
        assert found is not None
        assert found.level_id == level.level_id


def test_level_metadata_populated() -> None:
    for level in get_builtin_levels():
        assert level.name
        assert level.description
        assert len(level.thumbnail_color) == 3
        assert isinstance(level.tags, tuple)
        assert 1 <= level.difficulty <= 5
        assert level.objective


@pytest.mark.parametrize(
    "level_id,min_cells,required_materials",
    [
        ("sandbox",     50,   {3, 1, 2, 11, 16}),
        ("volcano",    500,   {3, 9, 2, 33}),
        ("water_tank", 500,   {3, 2, 6, 8, 13}),
        ("fireworks",  200,   {3, 19, 38, 39, 24}),
        ("forest_fire", 500,  {16, 2, 11, 8, 24, 3}),
        ("pressure_lab", 400, {3, 2, 12, 24, 32}),
        ("erosion_course", 600, {3, 1, 2, 8, 11, 16}),
    ],
)
def test_level_places_expected_materials(
    level_id: str, min_cells: int, required_materials: set[int]
) -> None:
    engine = _run(level_id)
    placed = set(engine.cells.values())

    missing = required_materials - placed
    assert not missing, f"{level_id} missing materials: {sorted(missing)}"
    assert len(engine.cells) >= min_cells, (
        f"{level_id} placed only {len(engine.cells)} cells (expected >= {min_cells})"
    )

    for (x, y) in engine.cells:
        assert 0 <= x < engine.width
        assert 0 <= y < engine.height


def test_level_builds_are_deterministic() -> None:
    # forest_fire uses RNG; same seed must reproduce identical layouts.
    a = _run("forest_fire")
    b = _run("forest_fire")
    assert a.cells == b.cells
