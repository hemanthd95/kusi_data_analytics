#!/usr/bin/env python3
"""Independent verifier for the Row Crop Intelligence Final Project."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

PROJECT = Path(__file__).resolve().parent
REPO = PROJECT.parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from dashboard_core import SOURCE_PATHS, TASKS, task_slug  # noqa: E402

OUT = PROJECT / "output"
TABLES = OUT / "tables"
SCREENSHOTS = PROJECT / "screenshots"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def require(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"missing or empty required file: {path.relative_to(REPO)}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def independent_priority(fields: pd.DataFrame, task: str) -> pd.Series:
    if task == "General field review":
        raw = 100.0 - fields["soil_sustainability_score"]
    elif task == "Irrigation monitoring":
        raw = (
            0.65 * (100.0 - fields["water_storage_score"])
            + 0.20 * (100.0 - fields["soil_sustainability_score"])
            + 0.15 * (100.0 - fields["slope_resilience_score"])
        )
    elif task == "Crop scouting":
        raw = (
            0.50 * (100.0 - fields["mean_dominant_pct"])
            + 0.30 * (100.0 - fields["soil_sustainability_score"])
            + 0.20 * (100.0 - fields["water_storage_score"])
        )
    elif task == "Soil conservation":
        raw = (
            0.45 * (100.0 - fields["soil_sustainability_score"])
            + 0.30 * (100.0 - fields["slope_resilience_score"])
            + 0.25 * (100.0 - fields["erosion_history_score"])
        )
    elif task == "Rotation planning":
        raw = (
            0.70 * (100.0 - fields["rotation_diversity_score"])
            + 0.30 * (100.0 - fields["soil_sustainability_score"])
        )
    else:
        fail(f"unsupported task in verifier: {task}")
    return raw.clip(0, 100).round(3)


def main() -> None:
    required = [
        PROJECT / "app.py",
        PROJECT / "dashboard_core.py",
        PROJECT / "README.md",
        PROJECT / "FINAL_PROJECT_REPORT.md",
        PROJECT / "LOCAL_VALIDATION.md",
        PROJECT / "evidence/final_project_evidence_summary.md",
        PROJECT / "requirements.txt",
        PROJECT / "scripts/build_final_project_data.py",
        PROJECT / "scripts/render_dashboard_screenshots.py",
        PROJECT / "scripts/smoke_test_dashboard_server.py",
        OUT / "dashboard_data.sqlite",
        OUT / "dashboard_summary.json",
        OUT / "skill_run.log",
        TABLES / "dashboard_field_metrics.csv",
        TABLES / "dashboard_source_manifest.csv",
        TABLES / "dashboard_weather_annual.csv",
        TABLES / "field_management_priorities.csv",
        REPO / "README.md",
        REPO / "docs/AI_DOCS.md",
        REPO / "docs/FINAL_PROJECT_REFLECTION.md",
        REPO / "docs/project/final-project-tracker.md",
    ]
    for path in required:
        require(path)

    summary = json.loads((OUT / "dashboard_summary.json").read_text(encoding="utf-8"))
    expected = {
        "status": "complete",
        "mode": "offline",
        "network_requests": 0,
        "no_synthetic_fallback_used": True,
        "field_count": 25,
        "assignment_source_count": 6,
        "visualization_count": 8,
        "kpi_tile_count": 5,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            fail(f"summary {key!r} expected {value!r}, found {summary.get(key)!r}")
    if summary.get("assignments_integrated") != [2, 3, 5, 6, 7, 8]:
        fail("dashboard does not integrate the expected six assignments")
    if len(summary.get("sections", [])) != 5 or len(summary.get("navigation_filters", [])) != 3:
        fail("dashboard section/filter inventory is incomplete")
    if not all(summary.get("requirement_matrix", {}).values()):
        fail("one or more Final Project requirement checks are false")
    if "Unavailable" not in summary.get("yield_status", ""):
        fail("yield limitation is not explicit")

    fields = pd.read_csv(TABLES / "dashboard_field_metrics.csv", dtype={"field_id": str})
    priorities = pd.read_csv(TABLES / "field_management_priorities.csv", dtype={"field_id": str})
    weather = pd.read_csv(TABLES / "dashboard_weather_annual.csv")
    manifest = pd.read_csv(TABLES / "dashboard_source_manifest.csv")

    if len(fields) != 25 or fields["field_id"].nunique() != 25:
        fail("field metrics must contain exactly 25 unique fields")
    if len(priorities) != 125 or set(priorities["task"]) != set(TASKS):
        fail("priority table must contain 25 fields for each of five tasks")
    if len(weather) != 35 or int(weather.year.min()) != 1991 or int(weather.year.max()) != 2025:
        fail("weather table must contain annual records for 1991–2025")
    if len(manifest) != 6 or set(manifest["assignment"].astype(int)) != {2, 3, 5, 6, 7, 8}:
        fail("source manifest must contain six previous assignments")

    # Recompute all five task scores without calling production priority_score().
    fields = fields.sort_values("field_id").reset_index(drop=True)
    for task in TASKS:
        expected_scores = independent_priority(fields, task)
        observed = (
            priorities.loc[priorities["task"] == task, ["field_id", "attention_score"]]
            .sort_values("field_id")
            .reset_index(drop=True)
        )
        if observed["field_id"].tolist() != fields["field_id"].tolist():
            fail(f"field IDs differ for task {task}")
        if not np.allclose(observed["attention_score"], expected_scores, atol=1e-9):
            fail(f"independent priority recomputation failed for {task}")
        output_col = f"priority_{task_slug(task)}"
        if output_col not in fields.columns or not np.allclose(fields[output_col], expected_scores, atol=1e-9):
            fail(f"field metrics priority column disagrees for {task}")

    # Authentic NDVI must occur once and only for its source field.
    ndvi = json.loads((REPO / SOURCE_PATHS["assignment_05_ndvi"]).read_text(encoding="utf-8"))
    ndvi_rows = fields.loc[fields["ndvi_mean"].notna()]
    if len(ndvi_rows) != 1 or str(ndvi_rows.iloc[0]["field_id"]) != str(ndvi["field_id"]):
        fail("NDVI was missing, duplicated, or attached to the wrong field")
    if not np.isclose(float(ndvi_rows.iloc[0]["ndvi_mean"]), float(ndvi["ndvi_statistics"]["mean"]), atol=1e-12):
        fail("dashboard NDVI value differs from Assignment 5")

    # Reject unsupported yield products.
    forbidden_columns = [c for c in fields.columns if "yield" in c.lower() or "bushel" in c.lower()]
    if forbidden_columns:
        fail("unsupported yield/bushel columns were added: " + ", ".join(forbidden_columns))

    # Source checksums must match the files actually consumed.
    manifest_map = dict(zip(manifest["path"], manifest["sha256"]))
    for relative in SOURCE_PATHS.values():
        key = str(relative)
        path = REPO / relative
        require(path)
        if manifest_map.get(key) != sha256(path):
            fail(f"source checksum mismatch: {key}")
        if summary.get("input_checksums", {}).get(key) != sha256(path):
            fail(f"summary checksum mismatch: {key}")

    # Portable SQLite layer and indexes.
    with sqlite3.connect(OUT / "dashboard_data.sqlite") as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("fields", "weather_annual", "data_sources", "task_priorities", "climate_context")
        }
        indexes = {row[1] for row in connection.execute("PRAGMA index_list('fields')")}
        priority_indexes = {row[1] for row in connection.execute("PRAGMA index_list('task_priorities')")}
    if counts != {"fields": 25, "weather_annual": 35, "data_sources": 6, "task_priorities": 125, "climate_context": 1}:
        fail(f"unexpected SQLite row counts: {counts}")
    if "idx_fields_field_id" not in indexes or "idx_priorities_task_score" not in priority_indexes:
        fail("required SQLite indexes are absent")

    app_text = (PROJECT / "app.py").read_text(encoding="utf-8")
    for token in (
        "Decision Center", "Crop & Vegetation", "Soil & Conservation", "Weather & Climate",
        "Data & Limitations", "Field ID", "Dominant soil type", "Management decision",
        "Which field should I inspect first?", "Measure before acting",
    ):
        if token not in app_text:
            fail(f"dashboard application is missing expected UI token: {token}")
    if app_text.count("figure(") < 8:
        fail("dashboard source contains fewer than eight Bokeh figures")

    screenshot_paths = sorted(SCREENSHOTS.glob("*.png"))
    if len(screenshot_paths) != 4:
        fail("exactly four demo screenshots are required")
    for path in screenshot_paths:
        with Image.open(path) as image:
            width, height = image.size
        if width < 1500 or height < 900:
            fail(f"screenshot is too small: {path.name} ({width}x{height})")

    root_readme = (REPO / "README.md").read_text(encoding="utf-8")
    project_readme = (PROJECT / "README.md").read_text(encoding="utf-8")
    for text in (root_readme, project_readme):
        if "bokeh serve" not in text or "Row Crop Intelligence" not in text:
            fail("README run instructions or project description are incomplete")
    if "AI assistance" not in (REPO / "docs/AI_DOCS.md").read_text(encoding="utf-8"):
        fail("AI usage summary is incomplete")

    print("PASS: Final Project verification succeeded (all checks passed).")


if __name__ == "__main__":
    main()
