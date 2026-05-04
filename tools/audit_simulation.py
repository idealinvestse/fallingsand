from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.audit_helpers import AuditScenario, anomaly_messages, create_standalone_context, metrics, paint_rect, run_scenario, snapshot


def _setup_sand(engine):
    paint_rect(engine, 1, 28, 42, 36, 46)


def _setup_water_lava(engine):
    paint_rect(engine, 9, 24, 16, 40, 24)
    paint_rect(engine, 2, 24, 24, 40, 32)


def _setup_explosion(engine):
    paint_rect(engine, 32, 12, 12, 52, 52)
    engine.trigger_explosion(32.0, 32.0, radius=14.0, force=6.0, duration=3)


def _setup_hydrostatic(engine):
    paint_rect(engine, 3, 8, 4, 56, 8)
    paint_rect(engine, 3, 8, 8, 12, 36)
    paint_rect(engine, 3, 52, 8, 56, 36)
    paint_rect(engine, 2, 12, 8, 52, 30)


SCENARIOS = {
    "sand": AuditScenario("sand", _setup_sand, frames=45),
    "water_lava": AuditScenario("water_lava", _setup_water_lava, frames=35, config_overrides={"no_thermal": False}),
    "explosion": AuditScenario("explosion", _setup_explosion, frames=45, config_overrides={"no_acoustics": False}),
    "hydrostatic": AuditScenario("hydrostatic", _setup_hydrostatic, frames=45, config_overrides={"pressure_iterations": 16}),
}


def _metric_dict(m):
    return {
        "material_counts": m.material_counts,
        "temp_min": m.temp_min,
        "temp_max": m.temp_max,
        "velocity_max": m.velocity_max,
        "pressure_min": m.pressure_min,
        "pressure_max": m.pressure_max,
        "divergence_rms": m.divergence_rms,
        "non_air_cells": m.non_air_cells,
        "display_nonzero_pixels": m.display_nonzero_pixels,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Falling Sand simulation audit scenarios.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--output", type=Path, help="Optional JSON summary output path")
    parser.add_argument("--include-display", action="store_true", help="Render and include display texture visibility metrics")
    args = parser.parse_args(argv)

    selected = SCENARIOS.values() if args.scenario == "all" else [SCENARIOS[args.scenario]]
    ctx, fbo = create_standalone_context((64, 64))
    results = []
    try:
        for scenario in selected:
            engine = run_scenario(ctx, scenario)
            snap = snapshot(engine, include_display=args.include_display)
            scenario_metrics = metrics(snap)
            anomalies = anomaly_messages(snap, velocity_limit=250.0, pressure_limit=10000.0, temp_limit=20000.0)
            result = {
                "name": scenario.name,
                "frames": scenario.frames,
                "passed": not anomalies,
                "anomalies": anomalies,
                "metrics": _metric_dict(scenario_metrics),
            }
            results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} {scenario.name}: non_air={scenario_metrics.non_air_cells} vmax={scenario_metrics.velocity_max:.3f} p={scenario_metrics.pressure_min:.3f}..{scenario_metrics.pressure_max:.3f}")
    finally:
        fbo.release()
        ctx.release()

    summary = {"passed": all(r["passed"] for r in results), "results": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
