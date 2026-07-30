#!/usr/bin/env python3
"""Assignment 7: integrated spatial analysis and field-level zonal statistics.

This workflow integrates only previously validated repository products:
- Assignment 2 authoritative field boundaries and USDA NASS CDL summaries
- Assignment 4 USDA-NRCS SSURGO field intersections and field summaries
- Assignment 5 authentic Landsat NDVI summary for the selected field

No synthetic or substituted observations are generated.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
A7 = ROOT / "data" / "assignment-07"
OUT = A7 / "output"
TABLES = OUT / "tables"
FIGURES = OUT / "visualizations"

FIELDS_PATH = ROOT / "data" / "assignment-02" / "fields_with_crops.geojson"
FIELD_CROPS_PATH = ROOT / "data" / "assignment-02" / "field_summary.csv"
SOIL_SUMMARY_PATH = ROOT / "data" / "assignment-04" / "output" / "field_soil_summary.csv"
SOIL_INTERSECTIONS_PATH = ROOT / "data" / "assignment-04" / "output" / "field_ssurgo_intersections.csv"
NDVI_SUMMARY_PATH = ROOT / "data" / "assignment-05" / "output" / "ndvi_summary.json"

ACRES_PER_M2 = 0.0002471053814671653


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required validated input is missing: {path.relative_to(ROOT)}")


def normalize_id(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return float("nan")
    return float(np.average(values[valid], weights=weights[valid]))


def main() -> None:
    for path in (FIELDS_PATH, FIELD_CROPS_PATH, SOIL_SUMMARY_PATH, SOIL_INTERSECTIONS_PATH, NDVI_SUMMARY_PATH):
        require(path)

    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    fields = gpd.read_file(FIELDS_PATH)
    crops = pd.read_csv(FIELD_CROPS_PATH)
    soils = pd.read_csv(SOIL_SUMMARY_PATH)
    intersections = pd.read_csv(SOIL_INTERSECTIONS_PATH)
    ndvi = json.loads(NDVI_SUMMARY_PATH.read_text(encoding="utf-8"))

    for frame in (fields, crops, soils, intersections):
        if "field_id" not in frame.columns:
            raise ValueError("Every authoritative input must contain field_id")
        frame["field_id"] = normalize_id(frame["field_id"])

    if fields["field_id"].duplicated().any():
        raise ValueError("Assignment 2 geometry contains duplicate field_id values")
    if crops["field_id"].duplicated().any():
        raise ValueError("Assignment 2 field summary contains duplicate field_id values")
    if soils["field_id"].duplicated().any():
        raise ValueError("Assignment 4 soil summary contains duplicate field_id values")

    crop_columns = [
        c
        for c in [
            "field_id",
            "CSBACRES",
            "crop_2020",
            "crop_2021",
            "crop_2022",
            "crop_2023",
            "dominant_pct_2023",
            "valid_pixels_2023",
        ]
        if c in crops.columns
    ]
    soil_columns = [
        c
        for c in [
            "field_id",
            "area_weighted_aws025wta",
            "dominant_mukey",
            "dominant_musym",
            "dominant_muname",
            "dominant_mapunit_percent",
            "mapunit_count",
            "coverage_percent",
        ]
        if c in soils.columns
    ]

    integrated = fields[["field_id", "geometry"]].merge(
        crops[crop_columns], on="field_id", how="left", validate="one_to_one"
    ).merge(soils[soil_columns], on="field_id", how="left", validate="one_to_one")

    if len(integrated) != len(fields):
        raise ValueError("Integrated field count changed during joins")
    if integrated["crop_2023"].isna().any():
        raise ValueError("At least one field is missing its Assignment 2 2023 crop result")
    if integrated["area_weighted_aws025wta"].isna().any():
        raise ValueError("At least one field is missing its Assignment 4 soil zonal statistic")

    integrated["soil_water_class"] = pd.cut(
        integrated["area_weighted_aws025wta"],
        bins=[-np.inf, 2.75, 3.25, np.inf],
        labels=["Lower", "Moderate", "Higher"],
        ordered=True,
    ).astype(str)
    integrated["crop_soil_zone"] = integrated["crop_2023"].astype(str) + " | " + integrated["soil_water_class"]

    area_col = "CSBACRES" if "CSBACRES" in integrated.columns else None
    if area_col is None:
        projected = integrated.to_crs("EPSG:32617")
        integrated["CSBACRES"] = projected.geometry.area * ACRES_PER_M2
        area_col = "CSBACRES"

    crop_zonal = (
        integrated.groupby("crop_2023", dropna=False)
        .apply(
            lambda group: pd.Series(
                {
                    "field_count": int(len(group)),
                    "total_acres": float(group[area_col].sum()),
                    "acreage_weighted_aws025wta": weighted_mean(
                        group["area_weighted_aws025wta"], group[area_col]
                    ),
                    "mean_dominant_crop_pct_2023": float(group["dominant_pct_2023"].mean()),
                }
            ),
            include_groups=False,
        )
        .reset_index()
        .sort_values(["total_acres", "crop_2023"], ascending=[False, True])
    )

    soil_zonal = (
        intersections.groupby(["mukey", "musym", "muname"], dropna=False)
        .agg(
            field_count=("field_id", "nunique"),
            intersection_count=("field_id", "size"),
            total_overlap_acres=("intersection_area_acres", "sum"),
            mean_aws025wta=("aws025wta", "mean"),
        )
        .reset_index()
        .sort_values(["total_overlap_acres", "mukey"], ascending=[False, True])
    )

    ndvi_field_id = str(ndvi.get("field_id", ""))
    integrated["assignment_05_ndvi_mean"] = np.where(
        integrated["field_id"] == ndvi_field_id,
        float(ndvi.get("ndvi_mean", np.nan)),
        np.nan,
    )
    integrated["assignment_05_ndvi_date"] = np.where(
        integrated["field_id"] == ndvi_field_id,
        str(ndvi.get("acquisition_datetime", ""))[:10],
        "",
    )

    non_geom = integrated.drop(columns="geometry")
    non_geom.to_csv(TABLES / "integrated_field_zonal_statistics.csv", index=False)
    crop_zonal.to_csv(TABLES / "crop_group_zonal_statistics.csv", index=False)
    soil_zonal.to_csv(TABLES / "soil_mapunit_zonal_statistics.csv", index=False)
    integrated.to_file(OUT / "integrated_fields.geojson", driver="GeoJSON")

    projected = integrated.to_crs("EPSG:32617")
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    projected.plot(
        column="area_weighted_aws025wta",
        cmap="viridis",
        legend=True,
        edgecolor="black",
        linewidth=0.5,
        ax=axes[0],
        legend_kwds={"label": "Available water storage, 0–25 cm (cm)"},
    )
    axes[0].set_title("Field-level SSURGO zonal statistic")
    axes[0].set_axis_off()

    projected.plot(
        column="crop_2023",
        categorical=True,
        legend=True,
        edgecolor="black",
        linewidth=0.5,
        ax=axes[1],
        legend_kwds={"title": "2023 dominant CDL class", "loc": "best", "fontsize": 8},
    )
    axes[1].set_title("Integrated 2023 crop and field geometry")
    axes[1].set_axis_off()

    fig.suptitle("Assignment 7 — Integrated Spatial Analysis and Zonal Statistics", fontsize=16)
    fig.text(
        0.5,
        0.02,
        "Sources: USDA NASS field/CDL products (Assignment 2), USDA-NRCS SSURGO (Assignment 4), and Landsat NDVI metadata (Assignment 5).",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIGURES / "assignment_07_integrated_spatial_panel.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIGURES / "assignment_07_integrated_spatial_panel.svg", bbox_inches="tight")
    plt.close(fig)

    top_crop = crop_zonal.iloc[0]
    summary = {
        "status": "complete",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "offline",
        "network_requests": 0,
        "no_synthetic_fallback_used": True,
        "field_count": int(len(integrated)),
        "total_acres": float(integrated[area_col].sum()),
        "crop_group_count_2023": int(integrated["crop_2023"].nunique()),
        "soil_mapunit_count": int(intersections["mukey"].nunique()),
        "mean_area_weighted_aws025wta": float(integrated["area_weighted_aws025wta"].mean()),
        "minimum_area_weighted_aws025wta": float(integrated["area_weighted_aws025wta"].min()),
        "maximum_area_weighted_aws025wta": float(integrated["area_weighted_aws025wta"].max()),
        "largest_2023_crop_group": str(top_crop["crop_2023"]),
        "largest_2023_crop_group_acres": float(top_crop["total_acres"]),
        "assignment_05_ndvi_field_id": ndvi_field_id,
        "assignment_05_ndvi_mean": float(ndvi.get("ndvi_mean", np.nan)),
        "input_checksums": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (FIELDS_PATH, FIELD_CROPS_PATH, SOIL_SUMMARY_PATH, SOIL_INTERSECTIONS_PATH, NDVI_SUMMARY_PATH)
        },
        "outputs": {
            "integrated_fields": "data/assignment-07/output/integrated_fields.geojson",
            "field_table": "data/assignment-07/output/tables/integrated_field_zonal_statistics.csv",
            "crop_zonal_table": "data/assignment-07/output/tables/crop_group_zonal_statistics.csv",
            "soil_zonal_table": "data/assignment-07/output/tables/soil_mapunit_zonal_statistics.csv",
            "figure_png": "data/assignment-07/output/visualizations/assignment_07_integrated_spatial_panel.png",
            "figure_svg": "data/assignment-07/output/visualizations/assignment_07_integrated_spatial_panel.svg",
        },
        "limitations": [
            "CDL classes are raster-derived dominant labels and can include mixed pixels or classification error.",
            "SSURGO values describe mapped soil components and are not direct field measurements.",
            "Assignment 5 NDVI is available for one selected field and is retained as contextual evidence rather than generalized to all fields.",
            "The integration is descriptive and does not establish causal crop-performance relationships.",
        ],
    }
    (OUT / "assignment_07_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("SUCCESS: Assignment 7 integrated spatial analysis complete")
    print(f"fields={summary['field_count']}")
    print(f"crop_groups_2023={summary['crop_group_count_2023']}")
    print(f"soil_mapunits={summary['soil_mapunit_count']}")
    print("synthetic_fallback=false")


if __name__ == "__main__":
    main()
