from __future__ import annotations

import numpy as np
import pytest

from tests.audit_helpers import (
    AuditScenario,
    assert_no_anomalies,
    centroid_y,
    create_standalone_context,
    metrics,
    paint_rect,
    positions,
    run_scenario,
    snapshot,
)


@pytest.fixture(scope="module")
def gl_ctx():
    ctx, fbo = create_standalone_context()
    yield ctx
    fbo.release()
    ctx.release()


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_sand_falls_and_render_is_visible(gl_ctx):
    def setup(engine):
        paint_rect(engine, 1, 28, 42, 36, 46)

    start_engine = run_scenario(gl_ctx, AuditScenario("sand-start", setup, frames=0))
    start = snapshot(start_engine)
    end_engine = run_scenario(gl_ctx, AuditScenario("sand-fall", setup, frames=45))
    end = snapshot(end_engine, include_display=True)

    assert_no_anomalies(end)
    assert centroid_y(end, 1) is not None
    assert centroid_y(start, 1) is not None
    assert centroid_y(end, 1) < centroid_y(start, 1)
    assert metrics(end).display_nonzero_pixels and metrics(end).display_nonzero_pixels > 0


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_liquids_spread_and_layer_by_density(gl_ctx):
    def setup(engine):
        paint_rect(engine, 6, 24, 8, 40, 18)
        paint_rect(engine, 2, 24, 18, 40, 28)

    end_engine = run_scenario(gl_ctx, AuditScenario("water-oil-density", setup, frames=150, config_overrides={"no_acoustics": True}))
    end = snapshot(end_engine)

    assert_no_anomalies(end)
    oil_y = centroid_y(end, 6)
    water_y = centroid_y(end, 2)
    assert oil_y is not None, "oil disappeared during density audit"
    assert water_y is not None, "water disappeared during density audit"
    assert oil_y > water_y, f"oil should float above water: oil_y={oil_y:.2f}, water_y={water_y:.2f}"


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_water_lava_reaction_produces_expected_products(gl_ctx):
    def setup(engine):
        paint_rect(engine, 9, 24, 16, 40, 24)
        paint_rect(engine, 2, 24, 24, 40, 32)

    end_engine = run_scenario(gl_ctx, AuditScenario("water-lava-reaction", setup, frames=35, config_overrides={"no_thermal": False}))
    end = snapshot(end_engine)
    counts = end.counts

    assert_no_anomalies(end)
    assert counts.get(3, 0) + counts.get(12, 0) > 0, f"water/lava produced no stone or glass: {counts}"
    assert counts.get(9, 0) < 128 or counts.get(2, 0) < 128, f"water/lava interaction did not consume reactants: {counts}"


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_acid_corrosion_reaches_products(gl_ctx):
    def setup(engine):
        paint_rect(engine, 7, 20, 22, 28, 30)
        paint_rect(engine, 22, 28, 22, 36, 30)
        paint_rect(engine, 3, 36, 22, 44, 30)

    end_engine = run_scenario(gl_ctx, AuditScenario("acid-corrosion", setup, frames=80))
    end = snapshot(end_engine)
    counts = end.counts

    assert_no_anomalies(end)
    assert counts.get(23, 0) > 0 or counts.get(14, 0) > 0 or counts.get(0, 0) > 64 * 64 - 192, f"acid corrosion produced no detectable products: {counts}"


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_hot_lava_spreads_heat_to_neighbors(gl_ctx):
    def setup(engine):
        paint_rect(engine, 2, 20, 20, 44, 32)
        paint_rect(engine, 9, 30, 24, 34, 28)

    end_engine = run_scenario(gl_ctx, AuditScenario("lava-heat-spread", setup, frames=50, config_overrides={"no_thermal": False}))
    end = snapshot(end_engine)

    assert_no_anomalies(end)
    assert float(np.max(end.temp)) > 120.0, f"thermal audit did not observe elevated temperatures: max={np.max(end.temp):.2f}"


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_explosion_pressure_and_velocity_stay_bounded(gl_ctx):
    def setup(engine):
        paint_rect(engine, 32, 12, 12, 52, 52)
        engine.trigger_explosion(32.0, 32.0, radius=14.0, force=6.0, duration=3)

    end_engine = run_scenario(
        gl_ctx,
        AuditScenario(
            "bounded-explosion",
            setup,
            frames=45,
            config_overrides={"no_acoustics": False, "acoustic_substeps": 6, "sound_speed": 4.0},
        ),
    )
    end = snapshot(end_engine)

    assert_no_anomalies(end, velocity_limit=150.0, pressure_limit=5000.0)
    m = metrics(end)
    assert m.pressure_max > 0.0
    assert m.velocity_max > 0.0


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_hydrostatic_tank_has_bounded_divergence(gl_ctx):
    def setup(engine):
        paint_rect(engine, 3, 8, 4, 56, 8)
        paint_rect(engine, 3, 8, 8, 12, 36)
        paint_rect(engine, 3, 52, 8, 56, 36)
        paint_rect(engine, 2, 12, 8, 52, 30)

    end_engine = run_scenario(gl_ctx, AuditScenario("hydrostatic-tank", setup, frames=45, config_overrides={"pressure_iterations": 16}))
    end = snapshot(end_engine)
    m = metrics(end)

    assert_no_anomalies(end)
    assert m.divergence_rms < 1.0, f"hydrostatic tank divergence too high: {m.divergence_rms:.3f}"


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_smoke_rises_before_decay(gl_ctx):
    def setup(engine):
        paint_rect(engine, 5, 28, 12, 36, 20)

    start_engine = run_scenario(gl_ctx, AuditScenario("smoke-start", setup, frames=0))
    start = snapshot(start_engine)
    end_engine = run_scenario(gl_ctx, AuditScenario("smoke-rise", setup, frames=18))
    end = snapshot(end_engine)

    assert_no_anomalies(end)
    start_y = centroid_y(start, 5)
    end_y = centroid_y(end, 5)
    assert start_y is not None
    assert end_y is not None, "smoke fully decayed before audit could measure rise"
    assert end_y > start_y, f"smoke should rise: start={start_y:.2f}, end={end_y:.2f}"


@pytest.mark.gpu
@pytest.mark.physics
def test_audit_solids_remain_stable(gl_ctx):
    def setup(engine):
        paint_rect(engine, 3, 24, 28, 40, 36)

    start_engine = run_scenario(gl_ctx, AuditScenario("stone-start", setup, frames=0))
    start = snapshot(start_engine)
    end_engine = run_scenario(gl_ctx, AuditScenario("stone-stable", setup, frames=60))
    end = snapshot(end_engine)

    assert_no_anomalies(end)
    assert len(positions(end, 3)) == len(positions(start, 3))
    assert abs((centroid_y(end, 3) or 0.0) - (centroid_y(start, 3) or 0.0)) <= 0.5
