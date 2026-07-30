#!/usr/bin/env python3
"""Independent verification for Assignment 8."""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
A8 = ROOT / "data" / "assignment-08"
OUT = A8 / "output"
FIELD_SUMMARY = ROOT / "data" / "assignment-02" / "field_summary.csv"
INTERSECTIONS = ROOT / "data" / "assignment-04" / "output" / "field_ssurgo_intersections.csv"
CROPS = ["crop_2020", "crop_2021", "crop_2022", "crop_2023"]
SLOPE = re.compile(r"(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s+percent slopes", re.I)


def fail(message: str) -> None:
    raise SystemExit("FAIL: " + message)


def analytical_table_sha256(path: Path, columns: list[str], sort_by: list[str]) -> str:
    frame = pd.read_csv(path, dtype={"field_id": str, "mukey": str})
    canonical = frame[columns].sort_values(sort_by, kind="stable").reset_index(drop=True)
    payload = canonical.to_csv(index=False, float_format="%.15g", lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def entropy(values: list[str]) -> float:
    counts = pd.Series(values).value_counts().to_numpy(dtype=float)
    probability = counts / counts.sum()
    return 100.0 * (-float(np.sum(probability * np.log(probability)))) / math.log(4.0)


def main() -> None:
    required = [
        A8 / "README.md", A8 / "SOIL_HEALTH_REPORT.md", A8 / "requirements.txt",
        A8 / "scripts" / "run_assignment_08_soil_health.py",
        A8 / "scripts" / "build_assignment_08_notebook.py",
        A8 / "scripts" / "normalize_assignment_08_notebook.py",
        A8 / "scripts" / "soil_health_metrics.py", A8 / "scripts" / "soil_health_visuals.py",
        OUT / "soil_health_summary.json", OUT / "skill_run.log",
        OUT / "tables" / "field_soil_health_scorecard.csv",
        OUT / "tables" / "sustainability_metric_summary.csv",
        OUT / "tables" / "soil_mapunit_sustainability_summary.csv",
        OUT / "visualizations" / "01_field_soil_health_scorecard.png",
        OUT / "visualizations" / "01_field_soil_health_scorecard.svg",
        OUT / "visualizations" / "02_sustainability_tradeoff.png",
        OUT / "visualizations" / "02_sustainability_tradeoff.svg",
        OUT / "dashboard_assets" / "dashboard_soil_health_scorecard.png",
        OUT / "dashboard_assets" / "dashboard_sustainability_tradeoff.png",
        A8 / "evidence" / "assignment_08_evidence_summary.md",
        ROOT / "notebooks" / "08_soil_health_sustainability.ipynb",
        ROOT / "docs" / "project" / "assignment-08-tracker.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail("missing required artifacts: " + ", ".join(missing))

    summary = json.loads((OUT / "soil_health_summary.json").read_text())
    if summary.get("status") != "complete":
        fail("summary status")
    if summary.get("mode") != "offline" or summary.get("network_requests") != 0:
        fail("offline attestation")
    if summary.get("no_synthetic_fallback_used") is not True:
        fail("synthetic-data attestation")
    if summary.get("field_count") != 25:
        fail("field count")
    if summary.get("sustainability_metric_count", 0) < 2:
        fail("fewer than two sustainability metrics")
    if summary.get("dashboard_visualization_count") not in (1, 2):
        fail("dashboard must contain 1–2 visualizations")
    expected_checksums = {
        str(FIELD_SUMMARY.relative_to(ROOT)): analytical_table_sha256(
            FIELD_SUMMARY, ["field_id", "CSBACRES", *CROPS], ["field_id"]),
        str(INTERSECTIONS.relative_to(ROOT)): analytical_table_sha256(
            INTERSECTIONS,
            ["field_id", "mukey", "musym", "muname", "aws025wta", "percent_of_field"],
            ["field_id", "mukey", "musym", "muname", "percent_of_field"],
        ),
    }
    if summary.get("input_checksums") != expected_checksums:
        fail("input checksums")

    score = pd.read_csv(OUT / "tables" / "field_soil_health_scorecard.csv", dtype={"field_id": str})
    metrics = pd.read_csv(OUT / "tables" / "sustainability_metric_summary.csv")
    if len(score) != 25 or score.field_id.nunique() != 25:
        fail("scorecard rows/IDs")
    required_columns = {
        "area_weighted_aws025wta", "area_weighted_slope_midpoint_pct",
        "eroded_mapunit_fraction_pct", "rotation_diversity_score",
        "water_storage_score", "slope_resilience_score", "erosion_history_score",
        "soil_sustainability_score", "relative_condition_class",
    }
    if absent := sorted(required_columns - set(score.columns)):
        fail("missing scorecard columns: " + ", ".join(absent))
    numeric_columns = list(required_columns - {"relative_condition_class"})
    if score[numeric_columns].isna().any().any():
        fail("missing metric values")
    for column in [
        "rotation_diversity_score", "water_storage_score", "slope_resilience_score",
        "erosion_history_score", "soil_sustainability_score",
    ]:
        if not score[column].between(0, 100).all():
            fail(f"{column} outside 0–100")
    expected_composite = score[[
        "water_storage_score", "slope_resilience_score",
        "erosion_history_score", "rotation_diversity_score",
    ]].mean(axis=1)
    if not np.allclose(score.soil_sustainability_score, expected_composite, atol=1e-10):
        fail("composite arithmetic")
    if score.groupby("soil_sustainability_score")["relative_condition_class"].nunique().max() != 1:
        fail("equal composite scores received different condition classes")
    if len(metrics) < 5:
        fail("metric summary incomplete")

    fields = pd.read_csv(FIELD_SUMMARY, dtype={"field_id": str}).set_index("field_id")
    intersections = pd.read_csv(INTERSECTIONS, dtype={"field_id": str, "mukey": str})
    parsed = []
    for name in intersections.muname:
        match = SLOPE.search(str(name))
        if not match:
            fail("unparsed slope description")
        parsed.append((float(match.group(1)) + float(match.group(2))) / 2)
    intersections["slope_midpoint_pct"] = parsed
    by_id = score.set_index("field_id")
    for field_id, group in intersections.groupby("field_id"):
        weights = group.percent_of_field.to_numpy(float)
        aws = float(np.average(group.aws025wta, weights=weights))
        slope = float(np.average(group.slope_midpoint_pct, weights=weights))
        eroded = float(group.loc[
            group.muname.str.contains("eroded", case=False, na=False), "percent_of_field"
        ].sum())
        if not np.isclose(by_id.loc[field_id, "area_weighted_aws025wta"], aws):
            fail(f"AWS recomputation {field_id}")
        if not np.isclose(by_id.loc[field_id, "area_weighted_slope_midpoint_pct"], slope):
            fail(f"slope recomputation {field_id}")
        if not np.isclose(by_id.loc[field_id, "eroded_mapunit_fraction_pct"], eroded):
            fail(f"eroded fraction {field_id}")
        crops = [str(fields.loc[field_id, column]) for column in CROPS]
        if not np.isclose(by_id.loc[field_id, "rotation_diversity_score"], entropy(crops)):
            fail(f"rotation entropy {field_id}")

    image_paths = [
        OUT / "visualizations" / "01_field_soil_health_scorecard.png",
        OUT / "visualizations" / "02_sustainability_tradeoff.png",
        OUT / "dashboard_assets" / "dashboard_soil_health_scorecard.png",
        OUT / "dashboard_assets" / "dashboard_sustainability_tradeoff.png",
    ]
    for path in image_paths:
        with Image.open(path) as image:
            if image.width < 1600 or image.height < 900:
                fail(f"image too small: {path.name} {image.width}x{image.height}")

    notebook = nbformat.read(ROOT / "notebooks" / "08_soil_health_sustainability.ipynb", as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    if len(code_cells) < 4 or not all(cell.execution_count is not None for cell in code_cells):
        fail("notebook not fully executed")
    errors = [
        output for cell in code_cells for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    if errors:
        fail("notebook contains execution errors")
    if any("execution" in cell.metadata for cell in code_cells):
        fail("notebook contains nondeterministic execution timestamps")
    expected_ids = [f"assignment-08-{index:02d}" for index in range(len(notebook.cells))]
    if [cell.id for cell in notebook.cells] != expected_ids:
        fail("notebook cell IDs are not deterministic")

    report = (A8 / "SOIL_HEALTH_REPORT.md").read_text().lower()
    for phrase in [
        "available-water-storage", "slope-resilience",
        "crop-rotation diversity", "not an official nrcs",
    ]:
        if phrase not in report:
            fail(f"report missing phrase: {phrase}")
    script_text = "\n".join(path.read_text().lower() for path in (A8 / "scripts").glob("*.py"))
    for token in ["np.random", "numpy.random", "random.uniform", "faker.", "make_fake"]:
        if token in script_text:
            fail(f"prohibited pattern: {token}")
    print("PASS: Assignment 8 verification succeeded (all checks passed).")


if __name__ == "__main__":
    main()
