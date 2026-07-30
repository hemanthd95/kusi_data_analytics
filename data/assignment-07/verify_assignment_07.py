#!/usr/bin/env python3
"""Independent verification for Assignment 7."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
A7 = ROOT / "data" / "assignment-07"
OUT = A7 / "output"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    required = [
        A7 / "README.md",
        A7 / "requirements.txt",
        A7 / "scripts" / "run_assignment_07_integrated_spatial.py",
        OUT / "assignment_07_summary.json",
        OUT / "integrated_fields.geojson",
        OUT / "tables" / "integrated_field_zonal_statistics.csv",
        OUT / "tables" / "crop_group_zonal_statistics.csv",
        OUT / "tables" / "soil_mapunit_zonal_statistics.csv",
        OUT / "visualizations" / "assignment_07_integrated_spatial_panel.png",
        OUT / "visualizations" / "assignment_07_integrated_spatial_panel.svg",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail("missing required artifacts: " + ", ".join(missing))

    summary = json.loads((OUT / "assignment_07_summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete":
        fail("summary status is not complete")
    if summary.get("mode") != "offline" or summary.get("network_requests") != 0:
        fail("workflow was not recorded as offline")
    if summary.get("no_synthetic_fallback_used") is not True:
        fail("synthetic-data attestation is absent")
    if int(summary.get("field_count", -1)) != 25:
        fail("expected exactly 25 authoritative fields")

    fields = gpd.read_file(OUT / "integrated_fields.geojson")
    table = pd.read_csv(OUT / "tables" / "integrated_field_zonal_statistics.csv")
    crops = pd.read_csv(OUT / "tables" / "crop_group_zonal_statistics.csv")
    soils = pd.read_csv(OUT / "tables" / "soil_mapunit_zonal_statistics.csv")

    if len(fields) != 25 or len(table) != 25:
        fail("integrated geometry and table must each contain 25 rows")
    if fields["field_id"].astype(str).nunique() != 25:
        fail("integrated geometry has duplicate field identifiers")
    if table["field_id"].astype(str).nunique() != 25:
        fail("integrated table has duplicate field identifiers")

    required_columns = {
        "field_id",
        "crop_2023",
        "dominant_pct_2023",
        "area_weighted_aws025wta",
        "dominant_mukey",
        "dominant_musym",
        "soil_water_class",
        "crop_soil_zone",
    }
    absent = sorted(required_columns - set(table.columns))
    if absent:
        fail("integrated table is missing columns: " + ", ".join(absent))
    if table["crop_2023"].isna().any() or table["area_weighted_aws025wta"].isna().any():
        fail("required zonal attributes contain missing values")
    if len(crops) != int(summary["crop_group_count_2023"]):
        fail("crop-group summary count disagrees with summary JSON")
    if len(soils) != int(summary["soil_mapunit_count"]):
        fail("soil-mapunit summary count disagrees with summary JSON")
    if crops["field_count"].sum() != 25:
        fail("crop-group field counts do not sum to 25")

    image_path = OUT / "visualizations" / "assignment_07_integrated_spatial_panel.png"
    with Image.open(image_path) as image:
        width, height = image.size
    if width < 1600 or height < 700:
        fail(f"integrated panel is unexpectedly small: {width}x{height}")

    svg = (OUT / "visualizations" / "assignment_07_integrated_spatial_panel.svg").read_text(
        encoding="utf-8"
    )
    if "Assignment 7" not in svg or "Integrated Spatial Analysis" not in svg:
        fail("SVG does not contain the expected Assignment 7 title")

    script = (A7 / "scripts" / "run_assignment_07_integrated_spatial.py").read_text(encoding="utf-8")
    forbidden = ("np.random", "numpy.random", "random.uniform", "synthetic data", "mock data")
    if any(token in script.lower() for token in forbidden):
        fail("workflow contains a prohibited synthetic/random-data pattern")

    print("PASS: Assignment 7 verification succeeded (all checks passed).")


if __name__ == "__main__":
    main()
