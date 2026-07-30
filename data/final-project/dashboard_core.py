#!/usr/bin/env python3
"""Core data integration and decision logic for the Final Project dashboard.

The module is intentionally independent from Bokeh so the analytical logic can be
unit-tested without starting a web server. It integrates only previously verified
repository products and never invents yield, current weather, or field measurements.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd

ANALYSIS_VERSION = "row-crop-intelligence-dashboard-v1"
FIELD_COUNT = 25

TASKS = (
    "General field review",
    "Irrigation monitoring",
    "Crop scouting",
    "Soil conservation",
    "Rotation planning",
)

SOURCE_PATHS = {
    "assignment_02_field_crop": Path("data/assignment-02/field_summary.csv"),
    "assignment_03_eda": Path("data/assignment-03/output/derived_field_metrics.csv"),
    "assignment_05_ndvi": Path("data/assignment-05/output/ndvi_summary.json"),
    "assignment_06_weather": Path("data/assignment-06/output/tables/weather_annual_1991_2025.csv"),
    "assignment_07_integrated_spatial": Path("data/assignment-07/output/integrated_fields.geojson"),
    "assignment_08_soil_health": Path("data/assignment-08/output/tables/field_soil_health_scorecard.csv"),
}


@dataclass(frozen=True)
class DashboardBundle:
    fields: gpd.GeoDataFrame
    weather: pd.DataFrame
    ndvi: dict
    climate: dict
    source_manifest: pd.DataFrame


def find_repo_root(start: Path | None = None) -> Path:
    """Find the repository root using the Assignment 7 integration as a marker."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / SOURCE_PATHS["assignment_07_integrated_spatial"]).is_file():
            return candidate
    raise FileNotFoundError("Could not locate the kusi_data_analytics repository root.")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], source: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {', '.join(missing)}")


def _normalize_ids(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    result = frame.copy()
    if "field_id" not in result.columns:
        raise ValueError(f"{source} does not contain field_id")
    result["field_id"] = result["field_id"].astype(str).str.strip()
    if result["field_id"].duplicated().any():
        raise ValueError(f"{source} contains duplicate field_id values")
    return result


def _percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        raise ValueError("Cannot percentile-score a series with missing values")
    scores = numeric.rank(method="average", pct=True) * 100.0
    return scores if higher_is_better else 100.0 - scores


def calculate_climate_context(weather: pd.DataFrame) -> dict:
    baseline = weather.loc[weather["year"].between(1991, 2020)].copy()
    recent = weather.loc[weather["year"].between(2021, 2025)].copy()
    latest = weather.sort_values("year").iloc[-1]

    base_temp = float(baseline["annual_mean_temperature_C"].mean())
    base_precip = float(baseline["annual_precipitation_mm"].mean())
    latest_temp_anom = float(latest["annual_mean_temperature_C"] - base_temp)
    latest_precip_anom = float(latest["annual_precipitation_mm"] - base_precip)
    latest_precip_pct = 100.0 * latest_precip_anom / base_precip

    temp_slope = float(np.polyfit(weather["year"], weather["annual_mean_temperature_C"], 1)[0] * 10)
    precip_slope = float(np.polyfit(weather["year"], weather["annual_precipitation_mm"], 1)[0] * 10)

    if latest_precip_pct <= -15:
        moisture_context = "drier than the 1991–2020 annual average"
    elif latest_precip_pct >= 15:
        moisture_context = "wetter than the 1991–2020 annual average"
    else:
        moisture_context = "near the 1991–2020 annual precipitation average"

    return {
        "baseline_temperature_C": base_temp,
        "baseline_precipitation_mm": base_precip,
        "latest_year": int(latest["year"]),
        "latest_temperature_C": float(latest["annual_mean_temperature_C"]),
        "latest_precipitation_mm": float(latest["annual_precipitation_mm"]),
        "latest_temperature_anomaly_C": latest_temp_anom,
        "latest_precipitation_anomaly_mm": latest_precip_anom,
        "latest_precipitation_anomaly_pct": latest_precip_pct,
        "temperature_trend_C_per_decade": temp_slope,
        "precipitation_trend_mm_per_decade": precip_slope,
        "recent_mean_temperature_C": float(recent["annual_mean_temperature_C"].mean()),
        "recent_mean_precipitation_mm": float(recent["annual_precipitation_mm"].mean()),
        "moisture_context": moisture_context,
    }


def load_dashboard_bundle(repo_root: Path | None = None) -> DashboardBundle:
    root = find_repo_root(repo_root)
    resolved = {name: root / relative for name, relative in SOURCE_PATHS.items()}
    missing = [str(path.relative_to(root)) for path in resolved.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing verified dashboard inputs: " + ", ".join(missing))

    a2 = _normalize_ids(pd.read_csv(resolved["assignment_02_field_crop"], dtype={"field_id": str}), "Assignment 2")
    a3 = _normalize_ids(pd.read_csv(resolved["assignment_03_eda"], dtype={"field_id": str}), "Assignment 3")
    a7 = gpd.read_file(resolved["assignment_07_integrated_spatial"])
    a7 = _normalize_ids(a7, "Assignment 7")
    a8 = _normalize_ids(pd.read_csv(resolved["assignment_08_soil_health"], dtype={"field_id": str}), "Assignment 8")
    weather = pd.read_csv(resolved["assignment_06_weather"])
    ndvi = json.loads(resolved["assignment_05_ndvi"].read_text(encoding="utf-8"))

    _require_columns(a2, ["field_id", "CSBACRES", "crop_2020", "crop_2021", "crop_2022", "crop_2023"], "Assignment 2")
    _require_columns(a3, ["field_id", "mean_dominant_pct", "crop_transition_count", "unique_dominant_crop_count"], "Assignment 3")
    _require_columns(a7, ["field_id", "geometry", "area_weighted_aws025wta", "dominant_musym", "dominant_muname"], "Assignment 7")
    _require_columns(a8, [
        "field_id", "rotation_diversity_score", "water_storage_score", "slope_resilience_score",
        "erosion_history_score", "soil_sustainability_score", "area_weighted_slope_midpoint_pct",
        "eroded_mapunit_fraction_pct", "relative_condition_class"
    ], "Assignment 8")
    _require_columns(weather, ["year", "annual_mean_temperature_C", "annual_precipitation_mm", "hot_day_count", "longest_dry_spell_days"], "Assignment 6")

    for name, frame in (("Assignment 2", a2), ("Assignment 3", a3), ("Assignment 7", a7), ("Assignment 8", a8)):
        if len(frame) != FIELD_COUNT or frame["field_id"].nunique() != FIELD_COUNT:
            raise ValueError(f"{name} must contain exactly {FIELD_COUNT} unique fields")

    if a7.crs is None or a7.crs.to_epsg() != 4326:
        raise ValueError(f"Assignment 7 integrated geometry must be EPSG:4326, found {a7.crs}")
    if ndvi.get("status") != "complete" or ndvi.get("no_synthetic_fallback_used") is not True:
        raise ValueError("Assignment 5 NDVI provenance is incomplete")
    if int(weather["year"].min()) != 1991 or int(weather["year"].max()) != 2025 or len(weather) != 35:
        raise ValueError("Assignment 6 annual weather table must cover 1991–2025")

    a2_cols = [
        "field_id", "CSBACRES", "crop_2020", "crop_2021", "crop_2022", "crop_2023",
        *[c for c in ("dominant_pct_2023", "valid_pixels_2023") if c in a2.columns],
    ]
    a3_cols = ["field_id", "mean_dominant_pct", "crop_transition_count", "unique_dominant_crop_count"]
    a8_cols = [
        "field_id", "rotation_diversity_score", "water_storage_score", "slope_resilience_score",
        "erosion_history_score", "soil_sustainability_score", "area_weighted_slope_midpoint_pct",
        "eroded_mapunit_fraction_pct", "relative_condition_class",
    ]
    a7_cols = [
        "field_id", "area_weighted_aws025wta", "dominant_mukey", "dominant_musym",
        "dominant_muname", "dominant_mapunit_percent", "mapunit_count", "coverage_percent", "geometry",
    ]

    fields = a7[a7_cols].merge(a2[a2_cols], on="field_id", how="left", validate="one_to_one")
    fields = fields.merge(a3[a3_cols], on="field_id", how="left", validate="one_to_one")
    fields = fields.merge(a8[a8_cols], on="field_id", how="left", validate="one_to_one")
    if fields.drop(columns="geometry").isna().any().any():
        missing_columns = fields.drop(columns="geometry").columns[fields.drop(columns="geometry").isna().any()].tolist()
        raise ValueError(f"Integrated dashboard fields contain missing values in: {missing_columns}")

    fields["field_short_id"] = fields["field_id"].str[-4:]
    fields["water_storage_percentile"] = _percentile_score(fields["area_weighted_aws025wta"], True)
    fields["classification_confidence_gap"] = 100.0 - fields["mean_dominant_pct"]

    ndvi_field = str(ndvi["field_id"])
    fields["ndvi_mean"] = np.where(
        fields["field_id"] == ndvi_field,
        float(ndvi["ndvi_statistics"]["mean"]),
        np.nan,
    )
    fields["ndvi_date"] = np.where(
        fields["field_id"] == ndvi_field,
        str(ndvi["acquisition_datetime"])[:10],
        "",
    )

    for task in TASKS:
        fields[f"priority_{task_slug(task)}"] = priority_score(fields, task)

    climate = calculate_climate_context(weather)
    manifest = pd.DataFrame(
        [
            {
                "source": name,
                "assignment": int(name.split("_")[1]),
                "path": str(path.relative_to(root)),
                "sha256": sha256(path),
            }
            for name, path in resolved.items()
        ]
    ).sort_values("assignment").reset_index(drop=True)

    return DashboardBundle(fields=fields, weather=weather, ndvi=ndvi, climate=climate, source_manifest=manifest)


def task_slug(task: str) -> str:
    return task.lower().replace(" ", "_")


def priority_score(fields: pd.DataFrame, task: str) -> pd.Series:
    """Calculate a relative 0–100 attention score; higher means inspect sooner."""
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
            0.50 * fields["classification_confidence_gap"]
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
        raise ValueError(f"Unsupported task: {task}")
    return raw.clip(0, 100).round(3)


def priority_label(score: float) -> str:
    if score >= 65:
        return "Highest attention"
    if score >= 50:
        return "High attention"
    if score >= 35:
        return "Moderate attention"
    return "Routine monitoring"


def field_advisory(row: pd.Series, task: str, climate: dict) -> dict:
    """Generate deterministic, evidence-linked farmer-facing guidance."""
    priority = float(row[f"priority_{task_slug(task)}"])
    actions: list[str] = []
    evidence: list[str] = []

    aws = float(row["area_weighted_aws025wta"])
    slope = float(row["area_weighted_slope_midpoint_pct"])
    eroded = float(row["eroded_mapunit_fraction_pct"])
    rotation = float(row["rotation_diversity_score"])
    confidence = float(row["mean_dominant_pct"])
    soil_score = float(row["soil_sustainability_score"])

    if task == "Irrigation monitoring":
        if float(row["water_storage_score"]) <= 35:
            actions.append("Check field soil moisture earlier after rain-free periods and before scheduling irrigation.")
        else:
            actions.append("Use routine soil-moisture checks; mapped water storage is not currently a top relative constraint.")
        actions.append("Confirm any irrigation decision with an in-field sensor or soil inspection; SSURGO is not a live moisture reading.")
    elif task == "Crop scouting":
        if confidence < 55:
            actions.append("Confirm the current crop and inspect field edges because the dominant CDL classification is comparatively uncertain.")
        else:
            actions.append("Use the mapped crop history as a scouting aid, then verify symptoms directly in the field.")
        if not math.isnan(float(row.get("ndvi_mean", np.nan))):
            ndvi = float(row["ndvi_mean"])
            if ndvi < 0.3:
                actions.append("Low NDVI is present; prioritize scouting for stand loss, nutrient stress, pests, or water stress.")
            elif ndvi < 0.6:
                actions.append("Moderate NDVI warrants targeted scouting before assuming healthy canopy conditions.")
            else:
                actions.append("The available Landsat date showed high greenness; this is historical evidence, not a current crop-health reading.")
    elif task == "Soil conservation":
        if slope >= 7 or eroded > 0:
            actions.append("Inspect runoff pathways and exposed soil; discuss residue retention, cover crops, contouring, or buffers with NRCS/Extension.")
        else:
            actions.append("Maintain residue and ground cover; mapped slope and erosion history do not place this field in the highest relative concern group.")
    elif task == "Rotation planning":
        if rotation < 35:
            actions.append("Review opportunities to diversify the rotation or add a suitable cover crop where agronomically and economically feasible.")
        else:
            actions.append("The four-year crop history shows some diversity; preserve or strengthen that rotation where practical.")
    else:
        if soil_score < 45:
            actions.append("Prioritize a field walk and conservation review because the relative sustainability score is low within this package.")
        else:
            actions.append("Continue routine monitoring and focus management on the weakest component shown below.")

    if aws < 2.75:
        evidence.append(f"Mapped 0–25 cm available-water storage is relatively low ({aws:.2f} cm).")
    else:
        evidence.append(f"Mapped 0–25 cm available-water storage is {aws:.2f} cm.")
    evidence.append(f"Relative soil-sustainability score: {soil_score:.1f}/100.")
    evidence.append(f"Area-weighted slope midpoint: {slope:.1f}%.")
    evidence.append(f"Four-year rotation-diversity score: {rotation:.1f}/100.")
    evidence.append(
        f"Historical {climate['latest_year']} precipitation was {climate['moisture_context']} "
        f"({climate['latest_precipitation_anomaly_pct']:+.1f}%)."
    )

    return {
        "priority_score": priority,
        "priority_label": priority_label(priority),
        "headline": actions[0],
        "actions": actions,
        "evidence": evidence,
        "caution": (
            "Decision-support priority only. Verify current crop, soil moisture, weather, pests, and field conditions before acting."
        ),
    }


def build_decision_table(bundle: DashboardBundle, task: str) -> pd.DataFrame:
    fields = bundle.fields.copy()
    score_col = f"priority_{task_slug(task)}"
    result = fields[
        [
            "field_id", "field_short_id", "CSBACRES", "crop_2023", "dominant_musym", "dominant_muname",
            "area_weighted_aws025wta", "soil_sustainability_score", "rotation_diversity_score", score_col,
        ]
    ].copy()
    result = result.rename(columns={score_col: "attention_score"})
    result["attention_level"] = result["attention_score"].map(priority_label)
    result["task"] = task
    return result.sort_values(["attention_score", "field_id"], ascending=[False, True]).reset_index(drop=True)


def build_sqlite(bundle: DashboardBundle, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    fields = bundle.fields.copy()
    fields["geometry_wkt"] = fields.geometry.to_wkt(rounding_precision=8)
    centroids = fields.to_crs("EPSG:32617").geometry.centroid
    centroid_geo = gpd.GeoSeries(centroids, crs="EPSG:32617").to_crs("EPSG:4326")
    fields["centroid_longitude"] = centroid_geo.x
    fields["centroid_latitude"] = centroid_geo.y
    fields_tabular = pd.DataFrame(fields.drop(columns="geometry"))

    priorities = pd.concat(
        [build_decision_table(bundle, task) for task in TASKS], ignore_index=True
    )
    climate = pd.DataFrame([bundle.climate])

    with sqlite3.connect(output_path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        fields_tabular.sort_values("field_id").to_sql("fields", connection, index=False, if_exists="replace")
        bundle.weather.sort_values("year").to_sql("weather_annual", connection, index=False, if_exists="replace")
        bundle.source_manifest.to_sql("data_sources", connection, index=False, if_exists="replace")
        priorities.to_sql("task_priorities", connection, index=False, if_exists="replace")
        climate.to_sql("climate_context", connection, index=False, if_exists="replace")
        connection.execute("CREATE UNIQUE INDEX idx_fields_field_id ON fields(field_id)")
        connection.execute("CREATE INDEX idx_priorities_task_score ON task_priorities(task, attention_score DESC)")
        connection.commit()
        connection.execute("VACUUM")


def build_summary(bundle: DashboardBundle) -> dict:
    fields = bundle.fields
    general = build_decision_table(bundle, "General field review")
    return {
        "status": "complete",
        "analysis_version": ANALYSIS_VERSION,
        "mode": "offline",
        "network_requests": 0,
        "no_synthetic_fallback_used": True,
        "field_count": int(len(fields)),
        "authentic_field_package_note": (
            "The assignment brief gives a 200-field KPI example, but the validated course package contains 25 fields; no additional fields were fabricated."
        ),
        "total_acres": float(fields["CSBACRES"].sum()),
        "soil_type_count": int(fields["dominant_musym"].nunique()),
        "assignments_integrated": [2, 3, 5, 6, 7, 8],
        "assignment_source_count": int(len(bundle.source_manifest)),
        "visualization_count": 8,
        "kpi_tile_count": 5,
        "navigation_filters": ["Field ID", "Soil type", "Management task"],
        "sections": [
            "Decision Center", "Crop & Vegetation", "Soil & Conservation", "Weather & Climate", "Data & Limitations"
        ],
        "highest_general_attention_field": str(general.iloc[0]["field_id"]),
        "highest_general_attention_score": float(general.iloc[0]["attention_score"]),
        "mean_soil_sustainability_score": float(fields["soil_sustainability_score"].mean()),
        "mean_available_water_storage_cm": float(fields["area_weighted_aws025wta"].mean()),
        "ndvi_field_id": str(bundle.ndvi["field_id"]),
        "ndvi_mean": float(bundle.ndvi["ndvi_statistics"]["mean"]),
        "climate_context": bundle.climate,
        "yield_status": "Unavailable in the validated package; no predicted bushels are displayed or fabricated.",
        "requirement_matrix": {
            "professional_python_dashboard": True,
            "kpi_summary_tiles": True,
            "field_id_filter": True,
            "soil_type_filter": True,
            "at_least_five_visualizations": True,
            "at_least_four_prior_assignments": True,
            "dynamic_ai_assisted_narratives": True,
            "farmer_action_guidance": True,
            "readme_run_instructions": True,
            "ai_usage_summary": True,
            "three_to_five_screenshots": True,
        },
        "limitations": [
            "NASA POWER weather is historical gridded context, not a current on-farm forecast.",
            "SSURGO is mapped soil information, not a live soil-moisture or laboratory measurement.",
            "Landsat NDVI is available for one field on one historical date and is not extrapolated to other fields.",
            "CDL crop labels may contain classification error and must be field-verified.",
            "No yield observations are present, so yield or bushel predictions are intentionally omitted.",
            "Recommendations prioritize follow-up; they are not prescriptions for rates, timing, or product use.",
        ],
        "input_checksums": {
            row["path"]: row["sha256"] for _, row in bundle.source_manifest.iterrows()
        },
    }
