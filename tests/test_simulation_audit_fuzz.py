from __future__ import annotations

import random

import pytest

from simulation.materials import get_all_materials
from tests.audit_helpers import AuditScenario, assert_no_anomalies, create_standalone_context, paint_rect, run_scenario, snapshot


@pytest.fixture(scope="module")
def gl_ctx():
    ctx, fbo = create_standalone_context((64, 64))
    yield ctx
    fbo.release()
    ctx.release()


def _random_world(seed: int, materials: list[int]):
    rng = random.Random(seed)

    def setup(engine):
        for _ in range(18):
            material_id = rng.choice(materials)
            w = rng.randint(1, 7)
            h = rng.randint(1, 7)
            x0 = rng.randint(2, engine.width - w - 2)
            y0 = rng.randint(2, engine.height - h - 2)
            paint_rect(engine, material_id, x0, y0, x0 + w, y0 + h)
        for _ in range(6):
            x = rng.randint(4, engine.width - 5)
            y = rng.randint(4, engine.height - 5)
            delta = rng.choice([-30, -15, 15, 30, 60])
            engine.apply_brush(x, y, radius=rng.randint(1, 3), material_id=0, mode=1 if delta > 0 else 2, delta=abs(delta))
        if rng.random() < 0.35:
            engine.trigger_explosion(
                float(rng.randint(12, engine.width - 13)),
                float(rng.randint(12, engine.height - 13)),
                radius=float(rng.randint(6, 14)),
                force=float(rng.uniform(2.0, 7.0)),
                duration=rng.randint(1, 4),
            )

    return setup


@pytest.mark.gpu
@pytest.mark.physics
@pytest.mark.slow
@pytest.mark.parametrize("seed", [101, 202, 303, 404, 505])
def test_seeded_random_worlds_do_not_enter_impossible_states(gl_ctx, seed):
    materials = sorted(get_all_materials().keys())
    materials = [m for m in materials if m not in (35, 36, 37, 38, 39, 40)]
    scenario = AuditScenario(
        name=f"seeded-random-{seed}",
        setup=_random_world(seed, materials),
        frames=35,
        width=48,
        height=48,
        config_overrides={
            "no_turbulence": False,
            "no_wet_dry": False,
            "no_thermal": False,
            "no_acoustics": seed % 2 == 0,
            "pressure_iterations": 10,
        },
    )
    engine = run_scenario(gl_ctx, scenario)
    snap = snapshot(engine, include_display=True)

    assert_no_anomalies(snap, velocity_limit=250.0, pressure_limit=10000.0, temp_limit=20000.0)
