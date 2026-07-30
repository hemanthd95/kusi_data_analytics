#!/usr/bin/env python3
"""Deterministic Assignment 8 visualizations."""
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.rcParams["svg.hashsalt"] = "assignment-08-soil-health"


def save_figure(fig: plt.Figure, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), dpi=200, bbox_inches="tight",
                metadata={"Software": "Assignment 8 reproducible workflow"})
    svg = stem.with_suffix(".svg")
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None, "Creator": "Assignment 8 reproducible workflow"})
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")


def build_visuals(scorecard: pd.DataFrame, figures: Path, dashboard: Path) -> list[Path]:
    ordered = scorecard.sort_values("soil_sustainability_score", ascending=False).reset_index(drop=True)
    columns = ["water_storage_score", "slope_resilience_score", "erosion_history_score",
               "rotation_diversity_score", "soil_sustainability_score"]
    labels = ["Water\nstorage", "Slope\nresilience", "Erosion\nhistory", "Rotation\ndiversity", "Composite\nscore"]
    matrix = ordered[columns].to_numpy(float)
    fig, ax = plt.subplots(figsize=(12, 15))
    image = ax.imshow(matrix, aspect="auto", vmin=0, vmax=100, cmap="RdYlGn")
    ax.set_xticks(range(len(labels)), labels=labels)
    ax.set_yticks(range(len(ordered)), labels=ordered["field_id"].str[-6:])
    ax.set_ylabel("Field ID (last six digits)")
    ax.set_title("Assignment 8 Soil Health and Sustainability Scorecard\nRelative scores within the 25-field study set")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(col, row, f"{matrix[row, col]:.0f}", ha="center", va="center", fontsize=7)
    bar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    bar.set_label("Relative score (0–100)")
    fig.text(.5, .015, "Inputs: USDA-NRCS SSURGO available-water storage and map-unit slope descriptions; USDA NASS CDL crop history. Not an official NRCS rating.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .035, 1, .97))
    score_stem = figures / "01_field_soil_health_scorecard"
    save_figure(fig, score_stem)
    plt.close(fig)
    dashboard.mkdir(parents=True, exist_ok=True)
    shutil.copy2(score_stem.with_suffix(".png"), dashboard / "dashboard_soil_health_scorecard.png")

    fig, ax = plt.subplots(figsize=(13, 9))
    scatter = ax.scatter(scorecard["area_weighted_aws025wta"], scorecard["area_weighted_slope_midpoint_pct"],
                         c=scorecard["soil_sustainability_score"], s=50 + 24 * scorecard["CSBACRES"],
                         cmap="viridis", vmin=0, vmax=100, alpha=.82, edgecolors="black", linewidths=.6)
    ax.axvline(scorecard["area_weighted_aws025wta"].median(), linestyle="--", linewidth=1)
    ax.axhline(scorecard["area_weighted_slope_midpoint_pct"].median(), linestyle="--", linewidth=1)
    ax.set_xlabel("Area-weighted available water storage, 0–25 cm (cm)")
    ax.set_ylabel("Area-weighted NRCS slope-range midpoint (%)")
    ax.set_title("Water-storage and erosion-exposure tradeoff across fields")
    for _, row in scorecard.nsmallest(4, "soil_sustainability_score").iterrows():
        ax.annotate(str(row["field_id"])[-6:], (row["area_weighted_aws025wta"], row["area_weighted_slope_midpoint_pct"]), xytext=(5, 5), textcoords="offset points", fontsize=8)
    fig.colorbar(scatter, ax=ax).set_label("Composite relative sustainability score")
    fig.text(.5, .02, "Bubble area reflects field acreage; labels identify the four lowest composite scores for conservation review.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .045, 1, 1))
    trade_stem = figures / "02_sustainability_tradeoff"
    save_figure(fig, trade_stem)
    plt.close(fig)
    shutil.copy2(trade_stem.with_suffix(".png"), dashboard / "dashboard_sustainability_tradeoff.png")
    return [score_stem.with_suffix(".png"), trade_stem.with_suffix(".png")]
