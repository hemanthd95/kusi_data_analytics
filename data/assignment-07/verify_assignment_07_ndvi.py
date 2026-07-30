#!/usr/bin/env python3
"""Verify that Assignment 7 preserves the authentic Assignment 5 NDVI value."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "assignment-07" / "output"
NDVI_PATH = ROOT / "data" / "assignment-05" / "output" / "ndvi_summary.json"


def main() -> None:
    ndvi = json.loads(NDVI_PATH.read_text(encoding="utf-8"))
    expected_field = str(ndvi["field_id"])
    expected_mean = float(ndvi["ndvi_statistics"]["mean"])

    summary = json.loads((OUT / "assignment_07_summary.json").read_text(encoding="utf-8"))
    observed_summary = float(summary["assignment_05_ndvi_mean"])
    if not math.isclose(observed_summary, expected_mean, rel_tol=0, abs_tol=1e-12):
        raise SystemExit("FAIL: Assignment 7 summary does not preserve authentic NDVI mean")

    table = pd.read_csv(OUT / "tables" / "integrated_field_zonal_statistics.csv")
    selected = table.loc[table["field_id"].astype(str) == expected_field]
    if len(selected) != 1:
        raise SystemExit("FAIL: authentic NDVI field is not unique in integrated table")
    observed_table = float(selected.iloc[0]["assignment_05_ndvi_mean"])
    if not math.isclose(observed_table, expected_mean, rel_tol=0, abs_tol=1e-12):
        raise SystemExit("FAIL: integrated table does not preserve authentic NDVI mean")
    if table.loc[table["field_id"].astype(str) != expected_field, "assignment_05_ndvi_mean"].notna().any():
        raise SystemExit("FAIL: NDVI was incorrectly extrapolated to other fields")

    print("PASS: Assignment 7 authentic NDVI integration verified.")


if __name__ == "__main__":
    main()
