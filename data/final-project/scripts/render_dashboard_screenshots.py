#!/usr/bin/env python3
"""Render four screenshot-style evidence views from the same dashboard data.

The production dashboard is interactive and served by Bokeh. These static captures use
exactly the same integrated dataset and decision logic so reviewers can inspect four
representative views without running a browser session.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from dashboard_core import (  # noqa: E402
    TASKS,
    field_advisory,
    find_repo_root,
    load_dashboard_bundle,
    priority_label,
    task_slug,
)

REPO = find_repo_root(PROJECT)
OUT = PROJECT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

COLORS = {
    "navy": "#17324d",
    "blue": "#2f6690",
    "green": "#477a45",
    "pale_green": "#edf5ea",
    "gold": "#d99b2b",
    "red": "#a23b32",
    "cream": "#fbfaf6",
    "gray": "#5f6b73",
    "light_gray": "#eef1f3",
}


def _header(fig, title: str, subtitle: str, filter_text: str) -> None:
    fig.patch.set_facecolor(COLORS["cream"])
    fig.text(0.025, 0.965, "ROW CROP INTELLIGENCE DASHBOARD", fontsize=10, color="#bcd1df",
             bbox=dict(boxstyle="round,pad=0.7", facecolor=COLORS["navy"], edgecolor=COLORS["navy"]))
    fig.text(0.025, 0.918, title, fontsize=25, weight="bold", color=COLORS["navy"])
    fig.text(0.025, 0.885, subtitle, fontsize=10.5, color=COLORS["gray"])
    fig.text(0.975, 0.927, filter_text, ha="right", fontsize=9, color=COLORS["navy"],
             bbox=dict(boxstyle="round,pad=0.55", facecolor="white", edgecolor="#cbd5db"))


def _kpi(fig, x: float, title: str, value: str, subtitle: str) -> None:
    box = FancyBboxPatch((x, 0.78), 0.17, 0.075, boxstyle="round,pad=0.008",
                         transform=fig.transFigure, facecolor="white", edgecolor="#d9e0e5", linewidth=1)
    fig.add_artist(box)
    fig.text(x + 0.012, 0.834, title.upper(), fontsize=7.3, color=COLORS["gray"], weight="bold")
    fig.text(x + 0.012, 0.802, value, fontsize=20, color=COLORS["navy"], weight="bold")
    fig.text(x + 0.012, 0.785, subtitle, fontsize=7.2, color=COLORS["gray"])


def _map_xy(gdf: gpd.GeoDataFrame, ax, column: str, title: str, selected: str | None = None) -> None:
    projected = gdf.to_crs("EPSG:32617")
    projected.plot(column=column, cmap="RdYlGn_r", vmin=0, vmax=100, linewidth=0.7,
                   edgecolor="white", legend=True, ax=ax, legend_kwds={"shrink": 0.65, "label": "Attention score"})
    if selected:
        projected.loc[projected["field_id"] == selected].boundary.plot(ax=ax, color="black", linewidth=3)
    for _, r in projected.iterrows():
        p = r.geometry.representative_point()
        ax.text(p.x, p.y, str(r["field_id"])[-4:], ha="center", va="center", fontsize=5.5, color="#18212a")
    ax.set_title(title, loc="left", color=COLORS["navy"], fontsize=13, weight="bold")
    ax.set_axis_off()


def decision_center(bundle) -> Path:
    fields = bundle.fields.copy()
    task = "Irrigation monitoring"
    score_col = f"priority_{task_slug(task)}"
    selected = fields.sort_values(score_col, ascending=False).iloc[0]
    ranked = fields.sort_values(score_col, ascending=False).head(8)
    advisory = field_advisory(selected, task, bundle.climate)

    fig = plt.figure(figsize=(16, 10), dpi=110)
    _header(fig, "Decision Center", "Rank fields for follow-up using verified crop, soil, climate, and sustainability evidence.",
            f"Field: {selected['field_id']}  |  Soil: All  |  Task: {task}")
    _kpi(fig, 0.025, "Fields in view", "25", "verified fields")
    _kpi(fig, 0.215, "Acreage", f"{fields.CSBACRES.sum():.1f}", "acres")
    _kpi(fig, 0.405, "Average soil score", f"{fields.soil_sustainability_score.mean():.1f}", "relative index")
    _kpi(fig, 0.595, "High attention", f"{int((fields[score_col] >= 50).sum())}", task.lower())
    _kpi(fig, 0.785, "2025 precipitation", f"{bundle.climate['latest_precipitation_anomaly_pct']:+.1f}%", "vs 1991–2020")

    gs = GridSpec(2, 3, figure=fig, left=0.035, right=0.98, bottom=0.055, top=0.745,
                  width_ratios=[1.42, 0.95, 0.82], height_ratios=[1.0, 0.48], wspace=0.24, hspace=0.22)
    ax_map = fig.add_subplot(gs[:, 0])
    _map_xy(fields, ax_map, score_col, "Which field should I inspect first?", selected=str(selected.field_id))

    ax_adv = fig.add_subplot(gs[0, 1:])
    ax_adv.axis("off")
    level = priority_label(float(selected[score_col]))
    text = [
        f"FIELD {selected.field_id}  ·  {level.upper()} ({selected[score_col]:.1f})",
        advisory["headline"], "",
        "SUGGESTED FOLLOW-UP",
        *[f"• {x}" for x in advisory["actions"]], "",
        "WHY IT IS RANKED HERE",
        *[f"• {x}" for x in advisory["evidence"]], "",
        "MEASURE BEFORE ACTING",
        advisory["caution"],
    ]
    ax_adv.text(0.02, 0.97, "\n".join(text), va="top", ha="left", fontsize=9.2, linespacing=1.35,
                color=COLORS["navy"], wrap=True,
                bbox=dict(boxstyle="round,pad=0.8", facecolor="white", edgecolor="#d9e0e5"))

    ax_rank = fig.add_subplot(gs[1, 1:])
    ax_rank.barh(ranked.field_short_id[::-1], ranked[score_col][::-1], color=COLORS["green"])
    ax_rank.set_xlim(0, 100)
    ax_rank.set_xlabel("Relative attention score")
    ax_rank.set_title("Top fields for irrigation monitoring", loc="left", fontsize=12, weight="bold", color=COLORS["navy"])
    for y, v in enumerate(ranked[score_col][::-1]):
        ax_rank.text(v + 1.5, y, f"{v:.1f}", va="center", fontsize=8)
    ax_rank.spines[["top", "right", "left"]].set_visible(False)
    ax_rank.grid(axis="x", alpha=0.2)

    path = OUT / "01_decision_center.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def crop_vegetation(bundle) -> Path:
    fields = bundle.fields.copy()
    selected = fields.loc[fields.field_id == str(bundle.ndvi["field_id"])].iloc[0]
    years = [2020, 2021, 2022, 2023]
    crops = [selected[f"crop_{y}"] for y in years]
    crop_colors = {"Grassland/Pasture": "#5b8c5a", "Other Hay/Non Alfalfa": "#a6b65c", "Winter Wheat": "#d9a441", "Oats": "#c9883b"}

    fig = plt.figure(figsize=(16, 10), dpi=110)
    _header(fig, "Crop & Vegetation", "Crop history, classification confidence, and authentic Landsat evidence.",
            f"Field: {selected.field_id}  |  Soil: {selected.dominant_musym}  |  View: Vegetation")
    _kpi(fig, 0.025, "Selected acreage", f"{selected.CSBACRES:.1f}", "acres")
    _kpi(fig, 0.215, "Mean confidence", f"{selected.mean_dominant_pct:.1f}%", "2020–2023 CDL")
    _kpi(fig, 0.405, "Crop transitions", f"{int(selected.crop_transition_count)}", "four-year history")
    _kpi(fig, 0.595, "NDVI mean", f"{selected.ndvi_mean:.3f}", str(selected.ndvi_date))
    _kpi(fig, 0.785, "Valid NDVI pixels", f"{bundle.ndvi['valid_pixel_count']}", "30 m Landsat")

    gs = GridSpec(2, 3, figure=fig, left=0.055, right=0.97, bottom=0.07, top=0.735, hspace=0.32, wspace=0.28)
    ax_crop = fig.add_subplot(gs[0, :2])
    ax_crop.bar([str(y) for y in years], [1]*4, color=[crop_colors.get(c, COLORS["gray"]) for c in crops], edgecolor="white")
    for i, c in enumerate(crops):
        ax_crop.text(i, 0.5, c.replace("/", "/\n"), ha="center", va="center", fontsize=9, weight="bold", color="white")
    ax_crop.set_ylim(0, 1.05); ax_crop.set_yticks([])
    ax_crop.set_title("Four-year dominant crop history", loc="left", fontsize=13, weight="bold", color=COLORS["navy"])
    ax_crop.spines[:].set_visible(False)

    ax_ndvi = fig.add_subplot(gs[0, 2])
    ax_ndvi.barh(["Historical NDVI"], [float(selected.ndvi_mean)], color=COLORS["green"], height=0.45)
    ax_ndvi.set_xlim(0, 1); ax_ndvi.axvline(0.3, color=COLORS["red"], ls="--"); ax_ndvi.axvline(0.6, color=COLORS["gold"], ls="--")
    ax_ndvi.text(float(selected.ndvi_mean), 0, f"  {selected.ndvi_mean:.3f}", va="center", weight="bold")
    ax_ndvi.set_title("Landsat greenness", loc="left", fontsize=13, weight="bold", color=COLORS["navy"])
    ax_ndvi.grid(axis="x", alpha=0.2); ax_ndvi.spines[["top","right","left"]].set_visible(False)

    ax_eda = fig.add_subplot(gs[1, :2])
    ax_eda.scatter(fields.CSBACRES, fields.mean_dominant_pct, s=70, alpha=0.75, color=COLORS["blue"], edgecolor="white")
    ax_eda.scatter([selected.CSBACRES], [selected.mean_dominant_pct], s=180, color=COLORS["gold"], edgecolor="black", label="Selected field")
    ax_eda.set_xlabel("Field acreage"); ax_eda.set_ylabel("Mean dominant-class confidence (%)")
    ax_eda.set_title("EDA relationship: field size vs classification confidence", loc="left", fontsize=13, weight="bold", color=COLORS["navy"])
    ax_eda.legend(); ax_eda.grid(alpha=0.2); ax_eda.spines[["top","right"]].set_visible(False)

    ax_note = fig.add_subplot(gs[1, 2]); ax_note.axis("off")
    note = (
        "FARMER INTERPRETATION\n\n"
        f"The available Landsat scene showed high greenness (NDVI {selected.ndvi_mean:.3f}) on {selected.ndvi_date}.\n\n"
        "Use the crop history and confidence to plan scouting, but verify the planted crop and field edges.\n\n"
        "This is one historical 30 m observation. It cannot diagnose current nutrient, pest, stand, or water stress."
    )
    ax_note.text(0, 1, note, va="top", fontsize=10, linespacing=1.45, color=COLORS["navy"],
                 bbox=dict(boxstyle="round,pad=0.8", facecolor="white", edgecolor="#d9e0e5"), wrap=True)

    path = OUT / "02_crop_vegetation.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def soil_conservation(bundle) -> Path:
    fields = bundle.fields.copy()
    task = "Soil conservation"
    score_col = f"priority_{task_slug(task)}"
    selected = fields.sort_values(score_col, ascending=False).iloc[0]
    components = ["Water storage", "Slope resilience", "Erosion history", "Rotation diversity"]
    values = [selected.water_storage_score, selected.slope_resilience_score, selected.erosion_history_score, selected.rotation_diversity_score]

    fig = plt.figure(figsize=(16, 10), dpi=110)
    _header(fig, "Soil & Conservation", "Relative soil condition components and conservation follow-up priorities.",
            f"Field: {selected.field_id}  |  Soil: {selected.dominant_musym}  |  Task: {task}")
    _kpi(fig, 0.025, "Soil score", f"{selected.soil_sustainability_score:.1f}", "relative 0–100")
    _kpi(fig, 0.215, "Mapped AWS", f"{selected.area_weighted_aws025wta:.2f}", "cm, 0–25 cm")
    _kpi(fig, 0.405, "Slope midpoint", f"{selected.area_weighted_slope_midpoint_pct:.1f}%", "area weighted")
    _kpi(fig, 0.595, "Eroded mapunit", f"{selected.eroded_mapunit_fraction_pct:.1f}%", "mapped fraction")
    _kpi(fig, 0.785, "Conservation attention", f"{selected[score_col]:.1f}", priority_label(selected[score_col]))

    gs = GridSpec(2, 3, figure=fig, left=0.045, right=0.98, bottom=0.06, top=0.74, wspace=0.27, hspace=0.28)
    ax_map = fig.add_subplot(gs[:, 0])
    _map_xy(fields, ax_map, score_col, "Conservation attention map", selected=str(selected.field_id))

    ax_comp = fig.add_subplot(gs[0, 1:])
    y = np.arange(len(components))
    ax_comp.barh(y, values, color=[COLORS["blue"], COLORS["green"], COLORS["gold"], "#7c5c99"])
    ax_comp.set_yticks(y, components); ax_comp.invert_yaxis(); ax_comp.set_xlim(0, 100)
    for i, v in enumerate(values): ax_comp.text(v+1.5, i, f"{v:.1f}", va="center")
    ax_comp.set_title(f"Field {selected.field_short_id}: sustainability components", loc="left", fontsize=13, weight="bold", color=COLORS["navy"])
    ax_comp.grid(axis="x", alpha=0.2); ax_comp.spines[["top","right","left"]].set_visible(False)

    ax_rank = fig.add_subplot(gs[1, 1])
    ranks = fields.sort_values("soil_sustainability_score").head(10)
    ax_rank.barh(ranks.field_short_id, ranks.soil_sustainability_score, color=COLORS["green"])
    ax_rank.set_xlim(0, 100); ax_rank.invert_yaxis(); ax_rank.set_xlabel("Soil sustainability score")
    ax_rank.set_title("Lowest-scoring fields", loc="left", fontsize=12, weight="bold", color=COLORS["navy"])
    ax_rank.grid(axis="x", alpha=0.2); ax_rank.spines[["top","right","left"]].set_visible(False)

    ax_note = fig.add_subplot(gs[1, 2]); ax_note.axis("off")
    advice = field_advisory(selected, task, bundle.climate)
    note = "CONSERVATION FOLLOW-UP\n\n" + "\n".join(f"• {x}" for x in advice["actions"]) + (
        "\n\nVerify runoff pathways, residue, compaction, and current soil cover in the field before choosing a practice. "
        "Use NRCS or Extension support for site-specific design."
    )
    ax_note.text(0, 1, note, va="top", fontsize=9.8, linespacing=1.45, color=COLORS["navy"],
                 bbox=dict(boxstyle="round,pad=0.8", facecolor="white", edgecolor="#d9e0e5"), wrap=True)

    path = OUT / "03_soil_conservation.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def weather_climate(bundle) -> Path:
    weather = bundle.weather.copy()
    climate = bundle.climate
    baseline_t = climate["baseline_temperature_C"]
    baseline_p = climate["baseline_precipitation_mm"]

    fig = plt.figure(figsize=(16, 10), dpi=110)
    _header(fig, "Weather & Climate", "Historical NASA POWER context for seasonal risk planning—not a current forecast.",
            "Field scope: all 25 fields  |  Period: 1991–2025  |  Baseline: 1991–2020")
    _kpi(fig, 0.025, "2025 temperature", f"{climate['latest_temperature_C']:.1f} °C", f"{climate['latest_temperature_anomaly_C']:+.1f} °C anomaly")
    _kpi(fig, 0.215, "2025 precipitation", f"{climate['latest_precipitation_mm']:.0f} mm", f"{climate['latest_precipitation_anomaly_pct']:+.1f}%")
    _kpi(fig, 0.405, "Temp trend", f"{climate['temperature_trend_C_per_decade']:+.2f}", "°C per decade")
    _kpi(fig, 0.595, "Baseline rain", f"{baseline_p:.0f} mm", "1991–2020 mean")
    _kpi(fig, 0.785, "Data completeness", "35 years", "annual records")

    gs = GridSpec(2, 2, figure=fig, left=0.06, right=0.97, bottom=0.08, top=0.735, hspace=0.34, wspace=0.22)
    ax_t = fig.add_subplot(gs[0, :])
    ax_t.plot(weather.year, weather.annual_mean_temperature_C, color=COLORS["red"], lw=2, marker="o", ms=3)
    ax_t.axhline(baseline_t, color=COLORS["gray"], ls="--", label="1991–2020 mean")
    ax_t.set_ylabel("Annual mean temperature (°C)")
    ax_t.set_title("Annual temperature history", loc="left", fontsize=13, weight="bold", color=COLORS["navy"])
    ax_t.legend(); ax_t.grid(alpha=0.2); ax_t.spines[["top","right"]].set_visible(False)

    ax_p = fig.add_subplot(gs[1, 0])
    colors = [COLORS["blue"] if v >= baseline_p else COLORS["gold"] for v in weather.annual_precipitation_mm]
    ax_p.bar(weather.year, weather.annual_precipitation_mm, color=colors, width=0.8)
    ax_p.axhline(baseline_p, color=COLORS["gray"], ls="--")
    ax_p.set_ylabel("Annual precipitation (mm)")
    ax_p.set_title("Annual precipitation history", loc="left", fontsize=13, weight="bold", color=COLORS["navy"])
    ax_p.grid(axis="y", alpha=0.2); ax_p.spines[["top","right"]].set_visible(False)

    ax_note = fig.add_subplot(gs[1, 1]); ax_note.axis("off")
    note = (
        "SEASONAL PLANNING CONTEXT\n\n"
        f"2025 was {climate['moisture_context']} ({climate['latest_precipitation_anomaly_pct']:+.1f}% versus the baseline).\n\n"
        f"The descriptive temperature trend is {climate['temperature_trend_C_per_decade']:+.2f} °C per decade.\n\n"
        "Use this history to discuss drought preparedness, water-storage limits, planting windows, and field-monitoring frequency.\n\n"
        "Before planting, spraying, irrigation, or harvest, check a current local forecast and verify field conditions."
    )
    ax_note.text(0, 1, note, va="top", fontsize=10, linespacing=1.55, color=COLORS["navy"],
                 bbox=dict(boxstyle="round,pad=0.9", facecolor="white", edgecolor="#d9e0e5"), wrap=True)

    path = OUT / "04_weather_climate.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def main() -> None:
    bundle = load_dashboard_bundle(REPO)
    paths = [decision_center(bundle), crop_vegetation(bundle), soil_conservation(bundle), weather_climate(bundle)]
    for path in paths:
        print(path.relative_to(REPO))


if __name__ == "__main__":
    main()
