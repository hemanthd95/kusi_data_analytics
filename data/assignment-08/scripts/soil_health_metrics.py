#!/usr/bin/env python3
"""Core metrics for Assignment 8 soil-health assessment."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

CROP_COLUMNS = ["crop_2020", "crop_2021", "crop_2022", "crop_2023"]
SLOPE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s+percent slopes", re.I)


def analytical_table_sha256(path: Path, columns: list[str], sort_by: list[str]) -> str:
    """Hash only authoritative columns consumed by this analysis."""
    frame = pd.read_csv(path, dtype={"field_id": str, "mukey": str})
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Cannot fingerprint {path}: missing columns {missing}")
    canonical = frame[columns].sort_values(sort_by, kind="stable").reset_index(drop=True)
    payload = canonical.to_csv(index=False, float_format="%.15g", lineterminator="\n").encode()
    return hashlib.sha256(payload).hexdigest()


def slope_midpoint(name: str) -> float:
    match = SLOPE_PATTERN.search(str(name))
    if not match:
        raise ValueError(f"Cannot parse NRCS slope range: {name!r}")
    return (float(match.group(1)) + float(match.group(2))) / 2.0


def rotation_entropy(row: pd.Series) -> float:
    values = [str(row[c]).strip() for c in CROP_COLUMNS if pd.notna(row[c])]
    if len(values) != 4:
        raise ValueError(f"Field {row['field_id']} lacks four crop-history values")
    counts = pd.Series(values).value_counts().to_numpy(float)
    probability = counts / counts.sum()
    entropy = -float(np.sum(probability * np.log(probability)))
    return max(0.0, 100.0 * entropy / math.log(4.0))


def percentile_score(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="raise").rank(method="average", pct=True) * 100.0


def build_scorecard(fields: pd.DataFrame, intersections: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return field scorecard and NRCS map-unit summary."""
    fields = fields.copy()
    intersections = intersections.copy()
    intersections["slope_midpoint_pct"] = intersections["muname"].map(slope_midpoint)
    intersections["eroded_mapunit"] = intersections["muname"].str.contains("eroded", case=False, na=False)
    sums = intersections.groupby("field_id")["percent_of_field"].sum().to_numpy(float)
    if not np.allclose(sums, 100.0, atol=1e-6):
        raise ValueError("SSURGO percentages must sum to 100% per field")

    rows = []
    for field_id, group in intersections.groupby("field_id", sort=True):
        weights = group["percent_of_field"].to_numpy(float)
        dominant = group.loc[group["percent_of_field"].idxmax()]
        rows.append({
            "field_id": field_id,
            "area_weighted_aws025wta": float(np.average(group["aws025wta"], weights=weights)),
            "area_weighted_slope_midpoint_pct": float(np.average(group["slope_midpoint_pct"], weights=weights)),
            "eroded_mapunit_fraction_pct": float(group.loc[group["eroded_mapunit"], "percent_of_field"].sum()),
            "soil_mapunit_count": int(group["mukey"].nunique()),
            "dominant_musym": str(dominant["musym"]),
            "dominant_muname": str(dominant["muname"]),
        })
    soil = pd.DataFrame(rows)

    fields["rotation_unique_crop_count"] = fields[CROP_COLUMNS].nunique(axis=1)
    fields["rotation_diversity_score"] = fields.apply(rotation_entropy, axis=1)
    keep = ["field_id", "CSBACRES", *CROP_COLUMNS, "rotation_unique_crop_count", "rotation_diversity_score"]
    scorecard = fields[keep].merge(soil, on="field_id", validate="one_to_one")
    if scorecard.isna().any().any():
        raise ValueError("Integrated scorecard contains missing values")

    scorecard["water_storage_score"] = percentile_score(scorecard["area_weighted_aws025wta"])
    scorecard["slope_resilience_score"] = percentile_score(-scorecard["area_weighted_slope_midpoint_pct"])
    scorecard["erosion_history_score"] = 100.0 - scorecard["eroded_mapunit_fraction_pct"]
    components = ["water_storage_score", "slope_resilience_score", "erosion_history_score", "rotation_diversity_score"]
    scorecard["soil_sustainability_score"] = scorecard[components].mean(axis=1)
    lower = float(scorecard["soil_sustainability_score"].quantile(1 / 3))
    upper = float(scorecard["soil_sustainability_score"].quantile(2 / 3))
    scorecard["relative_condition_class"] = np.select(
        [scorecard["soil_sustainability_score"] <= lower, scorecard["soil_sustainability_score"] <= upper],
        ["Higher conservation priority", "Moderate relative condition"],
        default="Stronger relative condition",
    )
    scorecard = scorecard.sort_values(["soil_sustainability_score", "field_id"], ascending=[False, True])

    acreage = fields.set_index("field_id")["CSBACRES"]
    intersections["overlap_acres"] = intersections.apply(
        lambda row: acreage.loc[row["field_id"]] * float(row["percent_of_field"]) / 100.0, axis=1
    )
    mapunits = intersections.groupby(["mukey", "musym", "muname"], as_index=False).agg(
        field_count=("field_id", "nunique"), total_overlap_acres=("overlap_acres", "sum"),
        aws025wta=("aws025wta", "first"), slope_midpoint_pct=("slope_midpoint_pct", "first"),
        eroded_descriptor=("eroded_mapunit", "max"),
    ).sort_values(["total_overlap_acres", "mukey"], ascending=[False, True])
    return scorecard, mapunits


def metric_summary(scorecard: pd.DataFrame) -> pd.DataFrame:
    definitions = {
        "area_weighted_aws025wta": ("NRCS available water storage, 0–25 cm", "cm", "Higher generally indicates more near-surface water storage capacity."),
        "area_weighted_slope_midpoint_pct": ("Area-weighted NRCS slope-range midpoint", "%", "Higher values indicate greater topographic erosion exposure."),
        "eroded_mapunit_fraction_pct": ("Field share mapped with 'eroded' in the NRCS map-unit name", "%", "Mapped descriptor; absence does not prove no current erosion."),
        "rotation_diversity_score": ("Four-year crop-rotation Shannon diversity", "0–100", "Higher values indicate more diverse observed CDL crop history."),
        "soil_sustainability_score": ("Equal-weight relative sustainability score", "0–100", "Mean of four components; not an official NRCS rating."),
    }
    rows = []
    for column, (label, unit, interpretation) in definitions.items():
        values = scorecard[column].astype(float)
        rows.append({"metric": column, "label": label, "unit": unit, "minimum": float(values.min()),
                     "median": float(values.median()), "mean": float(values.mean()),
                     "maximum": float(values.max()), "interpretation": interpretation})
    return pd.DataFrame(rows)
