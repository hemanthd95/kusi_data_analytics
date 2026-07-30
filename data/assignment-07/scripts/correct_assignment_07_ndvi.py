#!/usr/bin/env python3
"""Correct Assignment 7's nested Assignment 5 NDVI reference.

Assignment 5 stores the authentic mean under ``ndvi_statistics.mean``. This
post-processing step keeps the Assignment 7 integration reproducible while
correcting outputs produced by the original flat-key lookup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "assignment-07" / "output"
NDVI_PATH = ROOT / "data" / "assignment-05" / "output" / "ndvi_summary.json"


def main() -> None:
    ndvi = json.loads(NDVI_PATH.read_text(encoding="utf-8"))
    field_id = str(ndvi["field_id"])
    mean = float(ndvi["ndvi_statistics"]["mean"])

    table_path = OUT / "tables" / "integrated_field_zonal_statistics.csv"
    table = pd.read_csv(table_path)
    mask = table["field_id"].astype(str) == field_id
    if int(mask.sum()) != 1:
        raise ValueError("The authentic Assignment 5 field must occur exactly once")
    table.loc[mask, "assignment_05_ndvi_mean"] = mean
    table.to_csv(table_path, index=False)

    geojson_path = OUT / "integrated_fields.geojson"
    geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    matches = 0
    for feature in geojson["features"]:
        if str(feature["properties"].get("field_id")) == field_id:
            feature["properties"]["assignment_05_ndvi_mean"] = mean
            matches += 1
    if matches != 1:
        raise ValueError("The authentic Assignment 5 field must occur once in GeoJSON")
    geojson_path.write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    summary_path = OUT / "assignment_07_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["assignment_05_ndvi_mean"] = mean
    summary_path.write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )

    print(f"PASS: Assignment 7 authentic NDVI mean restored ({mean:.6f}).")


if __name__ == "__main__":
    main()
