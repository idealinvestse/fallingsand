from __future__ import annotations

import random

from levels.base import Level


def _fill_rect(engine, x0: int, y0: int, x1: int, y1: int, material_id: int) -> None:
    x0, x1 = max(0, min(x0, x1)), min(engine.width - 1, max(x0, x1))
    y0, y1 = max(0, min(y0, y1)), min(engine.height - 1, max(y0, y1))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            engine.apply_brush(x, y, 1, material_id)


def _place(engine, x: int, y: int, material_id: int) -> None:
    if 0 <= x < engine.width and 0 <= y < engine.height:
        engine.apply_brush(x, y, 1, material_id)


def _build_sandbox(engine) -> None:
    # Tunt stengolv som markerar "världens botten".
    _fill_rect(engine, 0, 0, engine.width - 1, 0, 3)

    # Små introduktionshögar av grundmaterial nära botten.
    base_y = 1
    step = max(12, engine.width // 8)
    anchors = [
        (step, 1, 8, 6),       # sand
        (step * 2, 2, 10, 8),  # water
        (step * 3, 11, 6, 10), # wood
        (step * 4, 16, 10, 6), # dirt
    ]
    for cx, mat, w, h in anchors:
        if cx + w >= engine.width:
            continue
        _fill_rect(engine, cx, base_y, cx + w, base_y + h, mat)


def _build_volcano(engine) -> None:
    cx = engine.width // 2
    base_y = engine.height // 6
    mountain_h = engine.height // 3

    # Symmetriskt stenberg.
    for y in range(base_y, base_y + mountain_h):
        half = max(4, (base_y + mountain_h - y) * 2)
        _fill_rect(engine, cx - half, y, cx + half, y, 3)

    # Lava-krater.
    crater_top = base_y + mountain_h - 8
    _fill_rect(engine, cx - 14, crater_top - 8, cx + 14, crater_top + 6, 9)

    # Lavaström som rinner ner på ena sidan (diagonal remsa ovanpå stenen).
    flow_x = cx + 6
    flow_y = crater_top + 5
    for step in range(min(mountain_h, 18)):
        fx = flow_x + step
        fy = flow_y - step
        if fx >= engine.width or fy <= base_y:
            break
        _fill_rect(engine, fx, fy, fx + 1, fy + 1, 9)

    # Vattendamm till vänster och sjö till höger som motvikt.
    _fill_rect(engine, 8, 4, engine.width // 3, base_y - 2, 2)
    right_left = engine.width - engine.width // 3
    _fill_rect(engine, right_left, 4, engine.width - 8, base_y - 2, 2)

    # Glöd/ember strax ovanför kratern ger visuell aktivitet vid start.
    ember_y = crater_top + 8
    for x in range(cx - 6, cx + 7, 4):
        _place(engine, x, ember_y, 33)


def _build_water_tank(engine) -> None:
    left = engine.width // 4
    right = engine.width - left
    floor = engine.height // 5
    top = engine.height - engine.height // 8

    # Sluten tank: golv + väggar.
    _fill_rect(engine, left, floor, right, floor + 2, 3)
    _fill_rect(engine, left, floor, left + 2, top, 3)
    _fill_rect(engine, right - 2, floor, right, top, 3)

    # Vatten fyller huvuddelen.
    _fill_rect(engine, left + 3, floor + 3, right - 3, top - 16, 2)
    # Oljelager ovanpå vattnet.
    _fill_rect(engine, left + 3, top - 15, right - 3, top - 8, 6)
    # Brännbart växtlock ovanpå oljan.
    _fill_rect(engine, left + 3, top - 7, right - 3, top - 5, 8)

    # Ispelare flyter på oljeytan (termisk demo).
    ice_cx = (left + right) // 2
    _fill_rect(engine, ice_cx - 3, top - 9, ice_cx + 3, top - 7, 13)


def _build_fireworks(engine) -> None:
    left = engine.width // 5
    right = engine.width - left
    base_y = engine.height // 8

    # Stenbas + sidoramar.
    _fill_rect(engine, left, base_y, right, base_y + 2, 3)
    _fill_rect(engine, left - 4, base_y, left - 2, base_y + 10, 3)
    _fill_rect(engine, right + 2, base_y, right + 4, base_y + 10, 3)

    cols = 6
    spacing = max(8, (right - left) // cols)
    fuse_y = base_y + 3
    column_xs: list[int] = []
    for i in range(cols):
        x = left + spacing // 2 + i * spacing
        column_xs.append(x)
        _fill_rect(engine, x - 2, base_y + 3, x + 2, base_y + 11, 39)   # dynamit
        _fill_rect(engine, x, base_y + 12, x, base_y + 20, 38)          # fuse-stubbe
        _fill_rect(engine, x - 1, base_y + 21, x + 1, base_y + 23, 19)  # krut på toppen

    # Gemensam lunta som binder ihop alla kolumner längs basen.
    if column_xs:
        _fill_rect(engine, column_xs[0], fuse_y, column_xs[-1], fuse_y, 38)
        # Självstartande tändgnista vid ena änden.
        _place(engine, column_xs[0] - 1, fuse_y, 24)


def _build_forest_fire(engine) -> None:
    ground_y = engine.height // 7
    _fill_rect(engine, 0, 0, engine.width - 1, ground_y, 16)

    # Vattensjö på vänster sida som potentiellt motmedel.
    lake_right = engine.width // 4
    _fill_rect(engine, 2, ground_y - 3, lake_right, ground_y, 2)

    rng = random.Random(1337)

    # Utspridda stenblock för variation.
    for _ in range(max(4, engine.width // 80)):
        sx = rng.randint(lake_right + 4, max(lake_right + 5, engine.width - 6))
        _fill_rect(engine, sx, ground_y + 1, sx + 2, ground_y + 3, 3)

    # Säkerställ minst 12 träd oavsett bredd; placera på höger sida av sjön.
    tree_count = max(12, engine.width // 24)
    for _ in range(tree_count):
        x = rng.randint(lake_right + 4, max(lake_right + 5, engine.width - 7))
        trunk_h = rng.randint(8, 20)
        _fill_rect(engine, x, ground_y + 1, x + 1, ground_y + trunk_h, 11)
        _fill_rect(engine, x - 4, ground_y + trunk_h - 1, x + 5, ground_y + trunk_h + 6, 8)

    # Antändningspunkter ovanför trädkronorna.
    for _ in range(14):
        x = rng.randint(lake_right + 4, max(lake_right + 5, engine.width - 8))
        y = rng.randint(ground_y + 6, ground_y + 26)
        engine.apply_brush(x, y, 2, 24)


def _build_pressure_lab(engine) -> None:
    left = engine.width // 8
    right = engine.width - left - 1
    floor = engine.height // 10
    ceiling = engine.height - engine.height // 8
    mid_y = (floor + ceiling) // 2
    membrane_x = engine.width // 2

    # Sealed outer chamber.
    _fill_rect(engine, left, floor, right, floor + 2, 3)
    _fill_rect(engine, left, floor, left + 2, ceiling, 3)
    _fill_rect(engine, right - 2, floor, right, ceiling, 3)
    _fill_rect(engine, left, ceiling - 2, right, ceiling, 3)

    # Split the chamber with a glass pressure window and a stone brace.
    _fill_rect(engine, membrane_x - 1, floor + 3, membrane_x + 1, ceiling - 3, 12)
    _fill_rect(engine, membrane_x - 5, floor + 3, membrane_x - 3, ceiling - 3, 3)
    _fill_rect(engine, membrane_x + 3, floor + 3, membrane_x + 5, ceiling - 3, 3)

    # Lower reservoir of water and a little air pocket near the window.
    _fill_rect(engine, left + 4, floor + 3, membrane_x - 6, mid_y - 4, 2)
    _fill_rect(engine, left + 4, mid_y - 3, membrane_x - 8, mid_y + 1, 0)

    # Upper gas chamber with oxygen and a spark source to generate a pulse.
    _fill_rect(engine, membrane_x + 6, mid_y - 2, right - 4, ceiling - 4, 32)
    _place(engine, membrane_x + 10, mid_y + 3, 24)
    _place(engine, membrane_x + 14, mid_y + 6, 4)

    # Small calibration markers.
    _place(engine, left + 8, ceiling - 6, 13)
    _place(engine, right - 8, floor + 6, 13)


def _build_erosion_course(engine) -> None:
    ground = engine.height // 8
    left = engine.width // 12
    right = engine.width - left - 1

    # Bedrock floor and outer walls.
    _fill_rect(engine, 0, 0, engine.width - 1, ground, 3)
    _fill_rect(engine, left, ground, right, ground + 2, 3)
    _fill_rect(engine, left, ground, left + 2, engine.height - 1, 3)
    _fill_rect(engine, right - 2, ground, right, engine.height - 1, 3)

    # Terraced slope made from dirt and sand.
    slope_top = engine.height - engine.height // 6
    for step in range(7):
        x0 = left + 6 + step * 12
        y0 = ground + 3 + step * 3
        x1 = min(right - 6, x0 + 22)
        y1 = min(engine.height - 4, y0 + 6)
        _fill_rect(engine, x0, y0, x1, y1, 16)
        if step % 2 == 0:
            _fill_rect(engine, x0 + 2, y0 + 1, x1 - 2, y1 - 1, 1)

    # Water source feeding the slope and a runoff basin.
    _fill_rect(engine, left + 4, slope_top, left + 18, engine.height - 6, 2)
    _fill_rect(engine, right - 24, ground + 4, right - 6, ground + 18, 2)

    # A few plants to show mud/erosion interactions.
    for x in range(left + 18, right - 18, 28):
        _fill_rect(engine, x, ground + 3, x + 1, ground + 8, 11)
        _fill_rect(engine, x - 2, ground + 8, x + 3, ground + 10, 8)


def _build_density_column(engine) -> None:
    left = engine.width // 4
    right = engine.width - left
    floor = engine.height // 6
    top = engine.height - engine.height // 6

    # Tall vertical tank.
    _fill_rect(engine, left, floor, right, floor + 2, 3)
    _fill_rect(engine, left, floor, left + 2, top, 3)
    _fill_rect(engine, right - 2, floor, right, top, 3)

    # Layered fluids with increasing density.
    h = (top - floor - 4) // 4
    _fill_rect(engine, left + 3, floor + 3, right - 3, floor + 3 + h, 9)     # Lava (3.5)
    _fill_rect(engine, left + 3, floor + 4 + h, right - 3, floor + 3 + 2*h, 2) # Water (2.0)
    _fill_rect(engine, left + 3, floor + 4 + 2*h, right - 3, floor + 3 + 3*h, 6) # Oil (1.5)
    _fill_rect(engine, left + 3, floor + 4 + 3*h, right - 3, top - 3, 10)    # Gas (-0.2)


def _build_acoustic_chamber(engine) -> None:
    # Large sealed chamber for sound wave demonstration.
    _fill_rect(engine, 10, 10, engine.width - 11, 12, 3)
    _fill_rect(engine, 10, 10, 12, engine.height - 11, 3)
    _fill_rect(engine, engine.width - 13, 10, engine.width - 11, engine.height - 11, 3)
    _fill_rect(engine, 10, engine.height - 13, engine.width - 11, engine.height - 11, 3)

    # Fill with oxygen (clear gas).
    _fill_rect(engine, 13, 13, engine.width - 14, engine.height - 14, 32)

    # Place some obstacles (glass) to see reflections.
    cx, cy = engine.width // 2, engine.height // 2
    _fill_rect(engine, cx - 40, cy - 40, cx - 35, cy + 40, 12)
    _fill_rect(engine, cx + 35, cy - 40, cx + 40, cy + 40, 12)
    
    # A single spark in the center to trigger a pulse when it burns out.
    _place(engine, cx, cy, 24)


def _build_density_column(engine) -> None:
    left = engine.width // 4
    right = engine.width - left
    floor = engine.height // 6
    top = engine.height - engine.height // 6

    # Tall vertical tank.
    _fill_rect(engine, left, floor, right, floor + 2, 3)
    _fill_rect(engine, left, floor, left + 2, top, 3)
    _fill_rect(engine, right - 2, floor, right, top, 3)

    # Layered fluids with increasing density.
    h = (top - floor - 4) // 4
    _fill_rect(engine, left + 3, floor + 3, right - 3, floor + 3 + h, 9)     # Lava (3.5)
    _fill_rect(engine, left + 3, floor + 4 + h, right - 3, floor + 3 + 2*h, 2) # Water (2.0)
    _fill_rect(engine, left + 3, floor + 4 + 2*h, right - 3, floor + 3 + 3*h, 6) # Oil (1.5)
    _fill_rect(engine, left + 3, floor + 4 + 3*h, right - 3, top - 3, 10)    # Gas (-0.2)


def _build_acoustic_chamber(engine) -> None:
    # Large sealed chamber for sound wave demonstration.
    _fill_rect(engine, 10, 10, engine.width - 11, 12, 3)
    _fill_rect(engine, 10, 10, 12, engine.height - 11, 3)
    _fill_rect(engine, engine.width - 13, 10, engine.width - 11, engine.height - 11, 3)
    _fill_rect(engine, 10, engine.height - 13, engine.width - 11, engine.height - 11, 3)

    # Fill with oxygen (clear gas).
    _fill_rect(engine, 13, 13, engine.width - 14, engine.height - 14, 32)

    # Place some obstacles (glass) to see reflections.
    cx, cy = engine.width // 2, engine.height // 2
    _fill_rect(engine, cx - 40, cy - 40, cx - 35, cy + 40, 12)
    _fill_rect(engine, cx + 35, cy - 40, cx + 40, cy + 40, 12)
    
    # A single spark in the center to trigger a pulse when it burns out.
    _place(engine, cx, cy, 24)


BUILTIN_LEVELS: tuple[Level, ...] = (
    Level(
        level_id="sandbox",
        name="Sandbox",
        description="Stengolv med provhögar av sand, vatten, trä och jord.",
        thumbnail_color=(80, 80, 95),
        build=_build_sandbox,
        tags=("starter", "freestyle", "materials"),
        difficulty=1,
        objective="Experiment with every core material without pressure.",
    ),
    Level(
        level_id="volcano",
        name="Volcano",
        description="Stenberg med lavakrater, rinnande ström och sjöar på sidorna.",
        thumbnail_color=(220, 90, 35),
        build=_build_volcano,
        tags=("heat", "lava", "challenge"),
        difficulty=3,
        objective="Keep the lava flow active while balancing the surrounding water.",
    ),
    Level(
        level_id="water_tank",
        name="Water Tank",
        description="Sluten tank med vatten, olja, växtlock och flytande ispelare.",
        thumbnail_color=(70, 140, 225),
        build=_build_water_tank,
        tags=("fluids", "layers", "thermal"),
        difficulty=2,
        objective="Preserve the layered fluid stack and watch the thermal cycle.",
    ),
    Level(
        level_id="fireworks",
        name="Fireworks",
        description="Dynamittorn med gemensam lunta och självtändande gnista.",
        thumbnail_color=(235, 190, 75),
        build=_build_fireworks,
        tags=("explosives", "chain_reaction", "challenge"),
        difficulty=4,
        objective="Light the fuse and survive the chain reaction.",
    ),
    Level(
        level_id="forest_fire",
        name="Forest Fire",
        description="Skog med sjö, stenar och glödande antändningspunkter.",
        thumbnail_color=(65, 150, 70),
        build=_build_forest_fire,
        tags=("combustion", "spread", "challenge"),
        difficulty=3,
        objective="Contain the fire before it consumes the forest.",
    ),
    Level(
        level_id="pressure_lab",
        name="Pressure Lab",
        description="Förseglad kammare med vatten, syre, glasruta och tändkälla.",
        thumbnail_color=(95, 120, 165),
        build=_build_pressure_lab,
        tags=("pressure", "acoustics", "fluids"),
        difficulty=4,
        objective="Trigger a pressure pulse without breaking the chamber.",
    ),
    Level(
        level_id="erosion_course",
        name="Erosion Course",
        description="Terrasserad sluttning som låter vatten gröpa ur sand och jord.",
        thumbnail_color=(145, 120, 80),
        build=_build_erosion_course,
        tags=("erosion", "terrain", "fluids"),
        difficulty=2,
        objective="Carve a channel through the hillside and form mud pools.",
    ),
    Level(
        level_id="density_column",
        name="Density Column",
        description="En vertikal tank med fyra lager av material med olika densitet.",
        thumbnail_color=(100, 50, 150),
        build=_build_density_column,
        tags=("fluids", "density", "physics"),
        difficulty=2,
        objective="Observe how materials with different densities separate and layer.",
    ),
    Level(
        level_id="acoustic_chamber",
        name="Acoustic Chamber",
        description="En sluten kammare fylld med syrgas för att demonstrera akustiska vågor.",
        thumbnail_color=(150, 200, 255),
        build=_build_acoustic_chamber,
        tags=("acoustics", "pressure", "gas"),
        difficulty=3,
        objective="Watch the pressure waves propagate and reflect off glass walls.",
    ),
)
