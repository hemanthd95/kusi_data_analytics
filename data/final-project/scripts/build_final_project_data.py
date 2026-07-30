#!/usr/bin/env python3
"""Build the deterministic Final Project decision-support data package."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from dashboard_core import (  # noqa: E402
    ANALYSIS_VERSION,
    TASKS,
    build_decision_table,
    build_sqlite,
    build_summary,
    find_repo_root,
    load_dashboard_bundle,
)


def normalize_climate_outputs(climate: dict) -> None:
    """Stabilize regression outputs across CPU/BLAS implementations.

    ``numpy.polyfit`` can differ in the final machine-precision digits on
    different clean runners. Twelve decimal places retain substantially more
    precision than the dashboard displays while ensuring that committed JSON
    and SQLite artifacts remain byte-stable across environments.
    """
    for key in (
        "temperature_trend_C_per_decade",
        "precipitation_trend_mm_per_decade",
    ):
        climate[key] = round(float(climate[key]), 12)


def main() -> None:
    root = find_repo_root(HERE)
    output = PROJECT / "output"
    tables = output / "tables"
    output.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    bundle = load_dashboard_bundle(root)
    normalize_climate_outputs(bundle.climate)
    build_sqlite(bundle, output / "dashboard_data.sqlite")

    all_priorities = pd.concat(
        [build_decision_table(bundle, task) for task in TASKS], ignore_index=True
    )
    all_priorities.to_csv(tables / "field_management_priorities.csv", index=False)

    fields = bundle.fields.drop(columns="geometry").copy()
    fields.sort_values("field_id").to_csv(tables / "dashboard_field_metrics.csv", index=False)
    bundle.weather.sort_values("year").to_csv(tables / "dashboard_weather_annual.csv", index=False)
    bundle.source_manifest.to_csv(tables / "dashboard_source_manifest.csv", index=False)

    summary = build_summary(bundle)
    (output / "dashboard_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    log = [
        f"Analysis version: {ANALYSIS_VERSION}",
        f"Fields: {summary['field_count']}",
        f"Acres: {summary['total_acres']:.3f}",
        f"Assignments integrated: {summary['assignments_integrated']}",
        f"Visualizations: {summary['visualization_count']}",
        f"Filters: {summary['navigation_filters']}",
        "Climate trends: normalized to 12 decimal places for cross-run reproducibility.",
        "Yield prediction: intentionally omitted because validated yield observations are absent.",
        "SUCCESS: Final Project dashboard data package complete",
    ]
    (output / "skill_run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(log[-1])


if __name__ == "__main__":
    main()
