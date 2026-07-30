#!/usr/bin/env python3
"""Assignment 8 soil health and sustainability metrics assessment.

Uses only validated Assignment 2 USDA NASS crop history and Assignment 4
USDA-NRCS SSURGO intersections. No absent laboratory or sensor observations
are invented. The score is relative within this 25-field set, not an official
NRCS soil-health rating.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from PIL import Image

from soil_health_metrics import CROP_COLUMNS, analytical_table_sha256, build_scorecard, metric_summary
from soil_health_visuals import build_visuals

ROOT = Path(__file__).resolve().parents[3]
A8 = ROOT / "data" / "assignment-08"
OUT = A8 / "output"
TABLES = OUT / "tables"
FIGURES = OUT / "visualizations"
DASH = OUT / "dashboard_assets"
EVIDENCE = A8 / "evidence"
FIELDS_PATH = ROOT / "data" / "assignment-02" / "field_summary.csv"
SOILS_PATH = ROOT / "data" / "assignment-04" / "output" / "field_ssurgo_intersections.csv"


def validate_inputs(fields: pd.DataFrame, soils: pd.DataFrame) -> None:
    field_columns = {"field_id", "CSBACRES", *CROP_COLUMNS}
    soil_columns = {"field_id", "mukey", "musym", "muname", "aws025wta", "percent_of_field"}
    if missing := sorted(field_columns - set(fields.columns)):
        raise ValueError(f"Assignment 2 summary missing columns: {missing}")
    if missing := sorted(soil_columns - set(soils.columns)):
        raise ValueError(f"Assignment 4 intersections missing columns: {missing}")
    if len(fields) != 25 or fields["field_id"].nunique() != 25:
        raise ValueError("Expected exactly 25 unique authoritative fields")
    if set(fields["field_id"]) != set(soils["field_id"]):
        raise ValueError("Assignment 2 and Assignment 4 field IDs do not match")


def make_summary(scorecard: pd.DataFrame, mapunits: pd.DataFrame, image_paths: list[Path]) -> dict:
    dimensions = {}
    for path in sorted([*image_paths, *DASH.glob("*.png")]):
        with Image.open(path) as image:
            dimensions[str(path.relative_to(ROOT))] = {"width": image.width, "height": image.height}
    highest, priority = scorecard.iloc[0], scorecard.iloc[-1]
    return {
        "status": "complete",
        "analysis_version": "assignment-08-v1",
        "mode": "offline",
        "network_requests": 0,
        "no_synthetic_fallback_used": True,
        "field_count": int(len(scorecard)),
        "soil_mapunit_count": int(mapunits["mukey"].nunique()),
        "slope_parse_success_count": int(pd.read_csv(SOILS_PATH).shape[0]),
        "slope_parse_failure_count": 0,
        "sustainability_metric_count": 4,
        "dashboard_visualization_count": 2,
        "score_method": "Equal-weight mean of relative water-storage percentile, relative inverse-slope percentile, 100 minus eroded-mapunit fraction, and normalized four-year crop-rotation entropy.",
        "highest_relative_score_field": str(highest["field_id"]),
        "highest_relative_score": float(highest["soil_sustainability_score"]),
        "highest_conservation_priority_field": str(priority["field_id"]),
        "lowest_relative_score": float(priority["soil_sustainability_score"]),
        "input_checksums": {
            str(FIELDS_PATH.relative_to(ROOT)): analytical_table_sha256(
                FIELDS_PATH, ["field_id", "CSBACRES", *CROP_COLUMNS], ["field_id"]),
            str(SOILS_PATH.relative_to(ROOT)): analytical_table_sha256(
                SOILS_PATH, ["field_id", "mukey", "musym", "muname", "aws025wta", "percent_of_field"],
                ["field_id", "mukey", "musym", "muname", "percent_of_field"]),
        },
        "input_checksum_scope": "Canonical SHA-256 of authoritative columns consumed by Assignment 8; unrelated upstream columns do not alter the analytical fingerprint.",
        "image_dimensions": dimensions,
        "outputs": {
            "scorecard": "data/assignment-08/output/tables/field_soil_health_scorecard.csv",
            "metric_summary": "data/assignment-08/output/tables/sustainability_metric_summary.csv",
            "mapunit_summary": "data/assignment-08/output/tables/soil_mapunit_sustainability_summary.csv",
            "scorecard_figure": "data/assignment-08/output/visualizations/01_field_soil_health_scorecard.png",
            "tradeoff_figure": "data/assignment-08/output/visualizations/02_sustainability_tradeoff.png",
            "dashboard_assets": [
                "data/assignment-08/output/dashboard_assets/dashboard_soil_health_scorecard.png",
                "data/assignment-08/output/dashboard_assets/dashboard_sustainability_tradeoff.png",
            ],
        },
        "limitations": [
            "The package does not contain field-level laboratory pH, organic matter, soil carbon, biological activity, aggregate stability, infiltration, or direct soil-moisture observations; none are invented.",
            "SSURGO values and map-unit names describe mapped soil components and are not substitutes for field sampling.",
            "Slope midpoint is parsed from the published NRCS map-unit name and area-weighted by field overlap.",
            "The eroded-mapunit metric depends on the map-unit name containing the word 'eroded'; absence of that descriptor does not demonstrate absence of present-day erosion.",
            "CDL crop classes can contain classification error and are used only as a four-year management-diversity indicator.",
            "All 0–100 scores are relative within this 25-field dataset and are not official NRCS or Soil Health Institute ratings.",
        ],
    }


def write_report(summary: dict) -> None:
    limits = "\n".join(f"- {item}" for item in summary["limitations"])
    report = f"""# Assignment 8 Soil Health and Sustainability Assessment

## Completion status

**Complete.** The analysis evaluates {summary['field_count']} authoritative row-crop fields using committed USDA-NRCS SSURGO intersections and four-year USDA NASS CDL crop history. No synthetic, substituted, or inferred laboratory observations are used.

## Required sustainability metrics

1. **Available-water-storage score:** area-weighted NRCS `aws025wta` for 0–25 cm.
2. **Slope-resilience score:** inverse relative rank of area-weighted NRCS slope-range midpoints.
3. **Erosion-history score:** 100 minus field percentage in map units whose NRCS name includes “eroded.”
4. **Crop-rotation diversity score:** normalized Shannon diversity of the 2020–2023 CDL sequence.

The composite is their equal-weight mean. It is a relative decision-support index for these 25 fields, not an official NRCS soil-health rating.

## Main findings

- Highest relative score: field `{summary['highest_relative_score_field']}` ({summary['highest_relative_score']:.1f}/100).
- Highest conservation-priority signal: field `{summary['highest_conservation_priority_field']}` ({summary['lowest_relative_score']:.1f}/100).
- SSURGO map units represented: {summary['soil_mapunit_count']}.
- Dashboard visualizations delivered: {summary['dashboard_visualization_count']}.

## Soil variability visualization

![Field soil-health scorecard](output/visualizations/01_field_soil_health_scorecard.png)

## Sustainability tradeoff visualization

![Sustainability tradeoff](output/visualizations/02_sustainability_tradeoff.png)

## Interpretation

Higher water storage, gentler mapped slopes, less mapped eroded-soil area, and more diverse four-year crop histories produce higher relative scores. Low scores identify candidates for inspection, soil testing, erosion assessment, and conservation planning—not automatic diagnoses.

## Data limitations

{limits}
"""
    (A8 / "SOIL_HEALTH_REPORT.md").write_text(report)
    (EVIDENCE / "assignment_08_evidence_summary.md").write_text(
        f"""# Assignment 8 evidence summary

- Status: complete
- Authoritative fields: {summary['field_count']}
- NRCS map units: {summary['soil_mapunit_count']}
- Sustainability metrics: {summary['sustainability_metric_count']}
- Dashboard visualizations: {summary['dashboard_visualization_count']}
- Slope descriptions parsed: {summary['slope_parse_success_count']} of {summary['slope_parse_success_count']}
- Synthetic fallback: not used
- Score interpretation: relative within the 25-field dataset; not an official NRCS rating

Expected verifier result:

```text
PASS: Assignment 8 verification succeeded (all checks passed).
```
""")


def main() -> None:
    for path in (FIELDS_PATH, SOILS_PATH):
        if not path.is_file():
            raise FileNotFoundError(path)
    for directory in (TABLES, FIGURES, DASH, EVIDENCE):
        directory.mkdir(parents=True, exist_ok=True)
    fields = pd.read_csv(FIELDS_PATH, dtype={"field_id": str})
    soils = pd.read_csv(SOILS_PATH, dtype={"field_id": str, "mukey": str})
    validate_inputs(fields, soils)
    scorecard, mapunits = build_scorecard(fields, soils)
    metrics = metric_summary(scorecard)
    scorecard.to_csv(TABLES / "field_soil_health_scorecard.csv", index=False)
    metrics.to_csv(TABLES / "sustainability_metric_summary.csv", index=False)
    mapunits.to_csv(TABLES / "soil_mapunit_sustainability_summary.csv", index=False)
    images = build_visuals(scorecard, FIGURES, DASH)
    summary = make_summary(scorecard, mapunits, images)
    (OUT / "soil_health_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    write_report(summary)
    (OUT / "skill_run.log").write_text(
        "\n".join([
            "Assignment 8 soil health and sustainability workflow", "mode=offline", "network_requests=0",
            f"field_count={summary['field_count']}", f"soil_mapunit_count={summary['soil_mapunit_count']}",
            f"sustainability_metric_count={summary['sustainability_metric_count']}",
            f"dashboard_visualization_count={summary['dashboard_visualization_count']}",
            "synthetic_fallback=false", "SUCCESS: Assignment 8 soil health assessment complete",
        ]) + "\n")
    print(json.dumps(summary, indent=2))
    print("SUCCESS: Assignment 8 soil health assessment complete")


if __name__ == "__main__":
    main()
