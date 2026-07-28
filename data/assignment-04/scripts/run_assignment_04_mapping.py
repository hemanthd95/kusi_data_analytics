#!/usr/bin/env python3
"""Reproducible Assignment 4 SSURGO mapping pipeline.

Offline-only: validates the committed USDA-NRCS GML and provenance before
analysis. No network requests and no synthetic fallback data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from branca.colormap import linear
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import transform as ops_transform
from shapely.ops import unary_union

try:
    from shapely import make_valid as shapely_make_valid
except ImportError:
    shapely_make_valid = None

REPO = Path(__file__).resolve().parents[3]
A4 = REPO / "data/assignment-04"
FIELD_SOURCE = REPO / "data/assignment-02/fields_EPSG4326.geojson"
RAW = A4 / "source/ssurgo_mapunit_response.gml"
META = A4 / "source/ssurgo_request_metadata.json"
EXTERNAL = A4 / "source/field_buffer_500m_external.geojson"

OUT = A4 / "output"
MAPS = OUT / "maps"
DASH = OUT / "dashboard_assets"
INTERACTIVE = OUT / "interactive"
TABLES = OUT / "tables"

WORKING_CRS = "EPSG:32617"
GEOGRAPHIC_CRS = "EPSG:4326"
BUFFER_M = 500.0
ACRES_PER_M2 = 0.000247105381
ATTRIBUTE = "aws025wta"
ATTRIBUTE_DEFINITION = (
    "Available water storage from 0–25 cm, weighted average of map-unit components"
)
UNITS = "centimeters of water"

EXPECTED = {
    RAW: "f7b9e32fb7f575f814739a7cefffc7fb0695b829e56f518a56f93bfddd46ab5c",
    META: "b361a28525bd10d4e4c1c65551b954ebf0a29de0f274af47d6de6610106960e8",
    EXTERNAL: "3ed7c3487e1714fc71ac641f59748557a1078a57b09e3a31eb031ddf1dc71e9f",
}
EXPECTED_GML_BYTES = 794_318
EXPECTED_FIELDS = 25
EXPECTED_FIELD_REPAIRS = 3
EXPECTED_ENDPOINT = (
    "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def polygonal_only(geom):
    if geom is None or geom.is_empty:
        return geom
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if isinstance(geom, GeometryCollection):
        parts = []
        for part in geom.geoms:
            poly = polygonal_only(part)
            if isinstance(poly, Polygon):
                parts.append(poly)
            elif isinstance(poly, MultiPolygon):
                parts.extend(poly.geoms)
        return unary_union(parts) if parts else GeometryCollection()
    return GeometryCollection()


def repair_polygon(geom):
    if geom is None or geom.is_empty:
        return geom
    fixed = geom
    if not geom.is_valid:
        fixed = shapely_make_valid(geom) if shapely_make_valid else geom.buffer(0)
    return polygonal_only(fixed)


def swap_xy(geom):
    if geom is None or geom.is_empty:
        return geom

    def transform_xy(x, y, z=None):
        return (y, x) if z is None else (y, x, z)

    return ops_transform(transform_xy, geom)


def validate_sources() -> dict[str, Any]:
    checksums = {}
    for path, expected in EXPECTED.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing authoritative source: {path}")
        actual = sha256(path)
        checksums[path.name] = actual
        if actual != expected:
            raise RuntimeError(
                f"Checksum mismatch for {path.name}: {actual} != {expected}"
            )

    metadata = json.loads(META.read_text(encoding="utf-8"))
    parameters = metadata.get("parameters", {})
    tests = {
        "success": metadata.get("success") is True,
        "http_status": metadata.get("http_status") == 200,
        "response_byte_size": (
            metadata.get("response_byte_size")
            == RAW.stat().st_size
            == EXPECTED_GML_BYTES
        ),
        "response_sha256": metadata.get("response_sha256") == EXPECTED[RAW],
        "field_count": metadata.get("field_count") == EXPECTED_FIELDS,
        "field_repairs": (
            metadata.get("field_geometry_repairs") == EXPECTED_FIELD_REPAIRS
        ),
        "buffer": float(metadata.get("buffer_meters", -1)) == BUFFER_M,
        "working_crs": metadata.get("working_crs") == WORKING_CRS,
        "request_crs": metadata.get("request_crs") == GEOGRAPHIC_CRS,
        "endpoint": str(metadata.get("endpoint", "")).lower()
        == EXPECTED_ENDPOINT.lower(),
        "typename": str(parameters.get("TYPENAME", "")).lower()
        == "mapunitpolyextended",
    }
    failed = [name for name, passed in tests.items() if not passed]
    if failed:
        raise RuntimeError("Metadata validation failed: " + ", ".join(failed))

    content = RAW.read_bytes().lower()
    markers = [
        b"featurecollection",
        b"<ms:mukey>",
        b"<ms:musym>",
        b"<ms:aws025wta>",
        b"<gml:polygon",
    ]
    if any(marker not in content for marker in markers):
        raise RuntimeError("GML lacks required SSURGO schema or geometry markers")
    if b"serviceexception" in content or b"exceptionreport" in content:
        raise RuntimeError("Preserved GML contains a WFS exception")

    return {
        "metadata": metadata,
        "checksums": checksums,
        "gml_bytes": RAW.stat().st_size,
        "tests": tests,
    }


def read_fields() -> tuple[gpd.GeoDataFrame, int]:
    fields = gpd.read_file(FIELD_SOURCE)
    if "field_id" not in fields.columns:
        raise RuntimeError("Assignment 2 field source lacks field_id")
    if len(fields) != EXPECTED_FIELDS:
        raise RuntimeError(f"Expected 25 fields; found {len(fields)}")
    if fields["field_id"].astype(str).nunique() != EXPECTED_FIELDS:
        raise RuntimeError("Field IDs are not unique")
    if fields.crs is None or fields.crs.to_epsg() != 4326:
        raise RuntimeError(f"Fields must be EPSG:4326; found {fields.crs}")
    if fields.geometry.isna().any() or fields.geometry.is_empty.any():
        raise RuntimeError("Field source contains missing or empty geometry")
    if not fields.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise RuntimeError("Field source contains non-polygon geometry")

    fields = fields.copy()
    fields["field_id"] = fields["field_id"].astype(str)
    invalid = ~fields.geometry.is_valid
    repairs = int(invalid.sum())
    if repairs != EXPECTED_FIELD_REPAIRS:
        raise RuntimeError(f"Expected 3 field repairs; found {repairs}")
    fields.loc[invalid, "geometry"] = fields.loc[invalid, "geometry"].apply(
        repair_polygon
    )
    if not fields.geometry.is_valid.all():
        raise RuntimeError("Field geometries remain invalid after repair")
    if not fields.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise RuntimeError("Field repair produced non-polygon geometry")
    return fields.to_crs(WORKING_CRS), repairs


def read_soil() -> tuple[gpd.GeoDataFrame, int, bool, int]:
    soil = gpd.read_file(RAW)
    parsed = len(soil)
    if parsed == 0:
        raise RuntimeError("GML parsed with zero features")

    soil = soil.rename(
        columns={c: c.lower() for c in soil.columns if c != soil.geometry.name}
    )
    required = {"mukey", "musym", ATTRIBUTE}
    missing = sorted(required.difference(soil.columns))
    if missing:
        raise RuntimeError(f"GML lacks columns: {missing}")
    if "muname" not in soil.columns:
        soil["muname"] = pd.NA

    if soil.crs is None:
        soil = soil.set_crs(GEOGRAPHIC_CRS)
    elif soil.crs.to_epsg() != 4326:
        soil = soil.to_crs(GEOGRAPHIC_CRS)

    xmin, ymin, xmax, ymax = soil.total_bounds
    axis_swapped = (
        20 <= xmin <= 50
        and 20 <= xmax <= 50
        and -100 <= ymin <= -70
        and -100 <= ymax <= -70
    )
    if axis_swapped:
        soil = soil.copy()
        soil.geometry = soil.geometry.apply(swap_xy)
        soil = soil.set_crs(GEOGRAPHIC_CRS, allow_override=True)

    xmin, ymin, xmax, ymax = soil.total_bounds
    if not (
        -100 <= xmin <= -70
        and -100 <= xmax <= -70
        and 20 <= ymin <= 50
        and 20 <= ymax <= 50
    ):
        raise RuntimeError(f"Implausible normalized SSURGO bounds: {soil.total_bounds}")

    soil[ATTRIBUTE] = pd.to_numeric(soil[ATTRIBUTE], errors="coerce")
    for column in ("mukey", "musym", "muname"):
        soil[column] = soil[column].astype("string")

    soil = soil.to_crs(WORKING_CRS)
    invalid = ~soil.geometry.is_valid
    soil_repairs = int(invalid.sum())
    if soil_repairs:
        soil.loc[invalid, "geometry"] = soil.loc[invalid, "geometry"].apply(
            repair_polygon
        )
    soil = soil[
        soil.geometry.notna()
        & ~soil.geometry.is_empty
        & soil.geom_type.isin(["Polygon", "MultiPolygon"])
    ].copy()
    if not soil.geometry.is_valid.all():
        raise RuntimeError("SSURGO geometries remain invalid after repair")
    return soil, parsed, axis_swapped, soil_repairs


def save_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    export = gdf.copy()
    for column in export.columns:
        if column != export.geometry.name and isinstance(
            export[column].dtype, pd.StringDtype
        ):
            export[column] = export[column].astype(object)
            export.loc[export[column].isna(), column] = None
    path.parent.mkdir(parents=True, exist_ok=True)
    export.to_file(path, driver="GeoJSON")


def stats(series: pd.Series) -> dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "median": None,
            "max": None,
        }
    return {
        "count": int(values.count()),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
        "min": float(values.min()),
        "median": float(values.median()),
        "max": float(values.max()),
    }


def build_field_summary(
    fields: gpd.GeoDataFrame,
    intersections: gpd.GeoDataFrame,
) -> pd.DataFrame:
    rows = []
    for _, field in fields.iterrows():
        field_id = str(field["field_id"])
        group = intersections[intersections["field_id"] == field_id].copy()
        field_area = float(field.geometry.area)
        csb = pd.to_numeric(pd.Series([field.get("CSBACRES")]), errors="coerce").iloc[0]
        csb_acres = float(csb) if pd.notna(csb) else field_area * ACRES_PER_M2

        if group.empty:
            rows.append(
                {
                    "field_id": field_id,
                    "CSBACRES": csb_acres,
                    "field_area_m2": field_area,
                    "covered_area_m2": 0.0,
                    "coverage_percent": 0.0,
                    "ssurgo_coverage_percent": 0.0,
                    "uncovered_percent": 100.0,
                    "area_weighted_aws025wta": np.nan,
                    "weighted_selected_soil_attribute": np.nan,
                    "dominant_mukey": pd.NA,
                    "dominant_musym": pd.NA,
                    "dominant_muname": pd.NA,
                    "dominant_mapunit_percent": np.nan,
                    "mapunit_count": 0,
                    "map_unit_count": 0,
                    "ssurgo_polygon_count": 0,
                }
            )
            continue

        weights = pd.to_numeric(
            group["intersection_area_m2"], errors="coerce"
        ).fillna(0.0)
        values = pd.to_numeric(group[ATTRIBUTE], errors="coerce")
        covered = float(weights.sum())
        raw_coverage = 100.0 * covered / field_area if field_area else np.nan
        coverage = min(100.0, max(0.0, raw_coverage))
        valid = values.notna() & (weights > 0)
        weighted = (
            float(
                np.average(
                    values.loc[valid].to_numpy(float),
                    weights=weights.loc[valid].to_numpy(float),
                )
            )
            if valid.any()
            else np.nan
        )
        dominant_idx = weights.idxmax()
        dominant = group.loc[dominant_idx]
        mapunit_count = int(group["mukey"].dropna().astype(str).nunique())

        rows.append(
            {
                "field_id": field_id,
                "CSBACRES": csb_acres,
                "field_area_m2": field_area,
                "covered_area_m2": covered,
                "coverage_percent": coverage,
                "ssurgo_coverage_percent": coverage,
                "uncovered_percent": max(0.0, 100.0 - coverage),
                "area_weighted_aws025wta": weighted,
                "weighted_selected_soil_attribute": weighted,
                "dominant_mukey": dominant.get("mukey"),
                "dominant_musym": dominant.get("musym"),
                "dominant_muname": dominant.get("muname"),
                "dominant_mapunit_percent": float(
                    dominant["percent_of_field"]
                ),
                "mapunit_count": mapunit_count,
                "map_unit_count": mapunit_count,
                "ssurgo_polygon_count": int(len(group)),
            }
        )

    summary = pd.DataFrame(rows).sort_values("field_id").reset_index(drop=True)
    if len(summary) != EXPECTED_FIELDS:
        raise RuntimeError(f"Field summary has {len(summary)} rows, not 25")
    return summary


def build_mapunit_summary(
    intersections: gpd.GeoDataFrame,
    total_field_area: float,
) -> pd.DataFrame:
    rows = []
    for (mukey, musym, muname), group in intersections.groupby(
        ["mukey", "musym", "muname"], dropna=False, sort=True
    ):
        weights = pd.to_numeric(
            group["intersection_area_m2"], errors="coerce"
        ).fillna(0.0)
        values = pd.to_numeric(group[ATTRIBUTE], errors="coerce")
        valid = values.notna() & (weights > 0)
        value = (
            float(
                np.average(
                    values.loc[valid].to_numpy(float),
                    weights=weights.loc[valid].to_numpy(float),
                )
            )
            if valid.any()
            else np.nan
        )
        overlap = float(weights.sum())
        rows.append(
            {
                "mukey": mukey,
                "musym": musym,
                "muname": muname,
                ATTRIBUTE: value,
                "selected_soil_attribute": value,
                "field_overlap_area_m2": overlap,
                "field_overlap_area_acres": overlap * ACRES_PER_M2,
                "field_overlap_percent": (
                    100.0 * overlap / total_field_area
                    if total_field_area
                    else np.nan
                ),
                "number_of_fields_intersected": int(
                    group["field_id"].astype(str).nunique()
                ),
                "intersection_polygon_count": int(len(group)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["field_overlap_area_m2", "mukey"],
        ascending=[False, True],
    ).reset_index(drop=True)


def add_north_scale(ax) -> None:
    ax.annotate(
        "N",
        (0.95, 0.965),
        xycoords="axes fraction",
        ha="center",
        fontsize=12,
        fontweight="bold",
    )
    ax.annotate(
        "",
        (0.95, 0.955),
        (0.95, 0.89),
        xycoords="axes fraction",
        arrowprops={"facecolor": "black", "width": 2.5, "headwidth": 9},
    )
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    start = x0 + 0.06 * (x1 - x0)
    ypos = y0 + 0.06 * (y1 - y0)
    ax.plot([start, start + 1000], [ypos, ypos], color="black", lw=4)
    ax.text(
        start + 500,
        ypos + 0.018 * (y1 - y0),
        "1 km",
        ha="center",
        fontsize=9,
    )


def plot_numeric(
    ax,
    gdf: gpd.GeoDataFrame,
    column: str,
    cmap: str,
    label: str,
    edgecolor: str = "white",
    linewidth: float = 0.4,
) -> None:
    values = pd.to_numeric(gdf[column], errors="coerce")
    observed = values.dropna()
    if observed.empty:
        raise RuntimeError(f"No observed values available for {column}")
    vmin, vmax = float(observed.min()), float(observed.max())
    if np.isclose(vmin, vmax):
        vmax = vmin + 1e-9
    norm = Normalize(vmin=vmin, vmax=vmax)

    if values.isna().any():
        gdf[values.isna()].plot(
            ax=ax,
            color="#d9d9d9",
            edgecolor=edgecolor,
            linewidth=linewidth,
        )
    mapped = gdf[values.notna()].copy()
    mapped[column] = values.loc[values.notna()].astype(float)
    mapped.plot(
        ax=ax,
        column=column,
        cmap=cmap,
        norm=norm,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cb = ax.figure.colorbar(sm, ax=ax, fraction=0.032, pad=0.015)
    cb.set_label(label)


def savefig(fig, stem: Path, dpi: int = 200) -> dict[str, Any]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    png, svg = stem.with_suffix(".png"), stem.with_suffix(".svg")
    fig.savefig(png, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    with Image.open(png) as image:
        return {
            "png": str(png.relative_to(REPO)),
            "svg": str(svg.relative_to(REPO)),
            "width": image.width,
            "height": image.height,
        }


def create_maps(
    fields: gpd.GeoDataFrame,
    clipped: gpd.GeoDataFrame,
    buffer_gdf: gpd.GeoDataFrame,
    external_geom,
    field_summary: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    outputs = {}

    fig, ax = plt.subplots(figsize=(9, 10))
    clipped.plot(
        ax=ax,
        color="#d9c89e",
        edgecolor="#8c6d31",
        lw=0.45,
        alpha=0.72,
    )
    buffer_gdf.boundary.plot(
        ax=ax,
        color="#0072B2",
        lw=1.4,
        ls="--",
    )
    fields.boundary.plot(ax=ax, color="#173f5f", lw=1.4)
    ax.set_title("Field Boundaries and SSURGO Context", fontsize=15)
    ax.set_axis_off()
    add_north_scale(ax)
    ax.legend(
        handles=[
            Patch(
                facecolor="#d9c89e",
                edgecolor="#8c6d31",
                label="SSURGO map units",
            ),
            Line2D([0], [0], color="#173f5f", label="Field boundaries"),
            Line2D(
                [0],
                [0],
                color="#0072B2",
                ls="--",
                label="500 m buffer",
            ),
        ],
        loc="upper left",
    )
    outputs["01_field_boundaries_and_ssurgo_context"] = savefig(
        fig, MAPS / "01_field_boundaries_and_ssurgo_context"
    )

    fig, ax = plt.subplots(figsize=(10, 10))
    plot_numeric(
        ax,
        clipped,
        ATTRIBUTE,
        "YlGnBu",
        f"Available water storage 0–25 cm ({UNITS})",
    )
    fields.boundary.plot(ax=ax, color="black", lw=1.0)
    ax.set_title("SSURGO Available Water Storage (0–25 cm)", fontsize=15)
    ax.set_axis_off()
    add_north_scale(ax)
    ax.text(
        0.01,
        0.01,
        "Missing values are gray and are not treated as zero.",
        transform=ax.transAxes,
        fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "none"},
    )
    outputs["02_ssurgo_attribute_choropleth"] = savefig(
        fig, MAPS / "02_ssurgo_attribute_choropleth"
    )

    fig, ax = plt.subplots(figsize=(9, 10))
    buffer_gdf.plot(
        ax=ax,
        color="#add8e6",
        alpha=0.42,
        edgecolor="#006d9c",
        lw=1.4,
    )
    gpd.GeoSeries([external_geom], crs=WORKING_CRS).boundary.plot(
        ax=ax,
        color="#e6550d",
        lw=1.3,
        ls="--",
    )
    fields.boundary.plot(ax=ax, color="#252525", lw=1.1)
    ax.set_title("500 m Buffer Operation and Cross-Check", fontsize=15)
    ax.set_axis_off()
    add_north_scale(ax)
    ax.legend(
        handles=[
            Patch(
                facecolor="#add8e6",
                edgecolor="#006d9c",
                alpha=0.42,
                label="Regenerated buffer",
            ),
            Line2D(
                [0],
                [0],
                color="#e6550d",
                ls="--",
                label="External buffer",
            ),
            Line2D([0], [0], color="#252525", label="Fields"),
        ],
        loc="upper left",
    )
    outputs["03_buffer_operation"] = savefig(
        fig, MAPS / "03_buffer_operation"
    )

    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(
        2,
        3,
        height_ratios=[2.65, 1.35],
        width_ratios=[1.08, 1.08, 0.84],
        hspace=0.11,
        wspace=0.08,
    )
    ax = fig.add_subplot(gs[0, :])
    plot_numeric(
        ax,
        clipped,
        ATTRIBUTE,
        "YlGnBu",
        f"{ATTRIBUTE} ({UNITS})",
        linewidth=0.32,
    )
    fields.boundary.plot(ax=ax, color="black", lw=0.9)
    ax.set_title(
        "Assignment 4 — SSURGO Field Variability",
        fontsize=18,
        fontweight="bold",
    )
    ax.set_axis_off()
    add_north_scale(ax)

    ranked = field_summary.sort_values(
        "area_weighted_aws025wta",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
    ranked.insert(0, "Rank", np.arange(1, len(ranked) + 1))
    table = ranked[
        [
            "Rank",
            "field_id",
            "area_weighted_aws025wta",
            "coverage_percent",
        ]
    ].copy()
    table["area_weighted_aws025wta"] = table[
        "area_weighted_aws025wta"
    ].map(lambda x: "NA" if pd.isna(x) else f"{x:.3f}")
    table["coverage_percent"] = table["coverage_percent"].map(
        lambda x: "NA" if pd.isna(x) else f"{x:.2f}%"
    )
    table.columns = ["Rank", "Field ID", "AWS (cm)", "Coverage"]

    for axis, subset, title in (
        (fig.add_subplot(gs[1, 0]), table.iloc[:13], "Fields 1–13"),
        (fig.add_subplot(gs[1, 1]), table.iloc[13:], "Fields 14–25"),
    ):
        axis.axis("off")
        axis.set_title(title, fontsize=10, fontweight="bold", pad=3)
        tbl = axis.table(
            cellText=subset.values,
            colLabels=subset.columns,
            cellLoc="center",
            colLoc="center",
            loc="center",
            colWidths=[0.11, 0.48, 0.20, 0.21],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(6.7)
        tbl.scale(1.0, 1.18)

    text_ax = fig.add_subplot(gs[1, 2])
    text_ax.axis("off")
    valid = pd.to_numeric(
        field_summary["area_weighted_aws025wta"],
        errors="coerce",
    ).dropna()
    text_ax.text(
        0,
        0.98,
        "Interpretation\n\n"
        "Higher values indicate greater water storage in the upper 25 cm.\n\n"
        f"Field-weighted range: {valid.min():.3f}–{valid.max():.3f} cm.\n\n"
        "Gray polygons have missing SSURGO values and remain missing.\n\n"
        "Methods\n"
        "• 25 real Assignment 2 fields\n"
        "• 500 m buffer in EPSG:32617\n"
        "• Genuine USDA-NRCS MapunitPolyExtended GML\n"
        "• Area-weighted field intersections\n\n"
        "Source note\n"
        "The official response was acquired externally, preserved, and "
        "checksum-validated before offline analysis.",
        va="top",
        fontsize=9.2,
        linespacing=1.22,
        bbox={
            "boxstyle": "round,pad=0.65",
            "facecolor": "#f7f7f7",
            "edgecolor": "#9e9e9e",
        },
    )
    outputs["04_final_assignment_panel"] = savefig(
        fig, MAPS / "04_final_assignment_panel", dpi=200
    )

    dashboard_fields = fields.merge(
        field_summary[
            ["field_id", "area_weighted_aws025wta", "coverage_percent"]
        ],
        on="field_id",
        how="left",
        validate="one_to_one",
    )
    fig, ax = plt.subplots(figsize=(16, 10))
    plot_numeric(
        ax,
        dashboard_fields,
        "area_weighted_aws025wta",
        "viridis",
        f"Area-weighted AWS ({UNITS})",
        linewidth=0.9,
    )
    dashboard_fields.boundary.plot(ax=ax, color="#252525", lw=0.7)
    for _, row in dashboard_fields.iterrows():
        point = row.geometry.representative_point()
        ax.text(
            point.x,
            point.y,
            str(row["field_id"])[-4:],
            ha="center",
            va="center",
            fontsize=6.5,
        )
    ax.set_title(
        "Field-Level SSURGO Available Water Storage",
        fontsize=16,
        fontweight="bold",
    )
    ax.set_axis_off()
    add_north_scale(ax)
    outputs["dashboard_ssurgo_field_variability_map"] = savefig(
        fig,
        DASH / "dashboard_ssurgo_field_variability_map",
        dpi=200,
    )
    return outputs


def create_interactive(
    fields: gpd.GeoDataFrame,
    clipped: gpd.GeoDataFrame,
    field_summary: pd.DataFrame,
) -> Path:
    soil = clipped[
        ["mukey", "musym", "muname", ATTRIBUTE, "geometry"]
    ].to_crs(GEOGRAPHIC_CRS)
    field_web = fields.merge(
        field_summary[
            ["field_id", "area_weighted_aws025wta", "coverage_percent"]
        ],
        on="field_id",
        how="left",
        validate="one_to_one",
    ).to_crs(GEOGRAPHIC_CRS)

    bounds = field_web.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    fmap = folium.Map(
        location=center,
        zoom_start=13,
        tiles="CartoDB positron",
        control_scale=True,
    )
    observed = pd.to_numeric(soil[ATTRIBUTE], errors="coerce").dropna()
    cmap = linear.YlGnBu_09.scale(
        float(observed.min()),
        float(observed.max()),
    )
    cmap.caption = f"{ATTRIBUTE} ({UNITS})"
    cmap.add_to(fmap)

    soil_json = json.loads(soil.to_json(drop_id=True))

    def soil_style(feature):
        value = feature["properties"].get(ATTRIBUTE)
        return {
            "fillColor": "#d9d9d9" if value is None else cmap(float(value)),
            "color": "#666666",
            "weight": 0.7,
            "fillOpacity": 0.68,
        }

    folium.GeoJson(
        soil_json,
        name="SSURGO map units",
        style_function=soil_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["mukey", "musym", "muname", ATTRIBUTE],
            aliases=[
                "Map unit key:",
                "Map unit symbol:",
                "Map unit name:",
                f"{ATTRIBUTE} ({UNITS}):",
            ],
            localize=True,
            sticky=False,
        ),
    ).add_to(fmap)

    folium.GeoJson(
        json.loads(
            field_web[
                [
                    "field_id",
                    "area_weighted_aws025wta",
                    "coverage_percent",
                    "geometry",
                ]
            ].to_json(drop_id=True)
        ),
        name="Assignment 2 fields",
        style_function=lambda _: {
            "fillOpacity": 0,
            "color": "#111111",
            "weight": 2,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "field_id",
                "area_weighted_aws025wta",
                "coverage_percent",
            ],
            aliases=[
                "Field ID:",
                f"Area-weighted AWS ({UNITS}):",
                "SSURGO coverage (%):",
            ],
            localize=True,
            sticky=False,
        ),
    ).add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    path = INTERACTIVE / "assignment_04_interactive_map.html"
    fmap.save(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not args.offline:
        raise SystemExit("Use --offline. This pipeline performs no network requests.")

    for directory in (OUT, MAPS, DASH, INTERACTIVE, TABLES):
        directory.mkdir(parents=True, exist_ok=True)

    source = validate_sources()
    fields, field_repairs = read_fields()
    total_field_area = float(fields.geometry.area.sum())

    buffer_geom = fields.geometry.union_all().buffer(BUFFER_M)
    if buffer_geom.is_empty or not buffer_geom.is_valid:
        raise RuntimeError("Regenerated 500 m buffer is invalid")
    buffer_gdf = gpd.GeoDataFrame(
        {"buffer_distance_m": [BUFFER_M]},
        geometry=[buffer_geom],
        crs=WORKING_CRS,
    )
    save_geojson(
        buffer_gdf.to_crs(GEOGRAPHIC_CRS),
        OUT / "field_buffer_500m.geojson",
    )

    external = gpd.read_file(EXTERNAL)
    if external.crs is None:
        raise RuntimeError("External buffer lacks a CRS")
    external_geom = external.to_crs(WORKING_CRS).geometry.union_all()
    buffer_difference = float(
        buffer_geom.symmetric_difference(external_geom).area
    )

    soil, parsed, axis_swapped, soil_repairs = read_soil()
    save_geojson(
        soil[["mukey", "musym", "muname", ATTRIBUTE, "geometry"]].to_crs(
            GEOGRAPHIC_CRS
        ),
        OUT / "ssurgo_mapunits_raw.geojson",
    )

    clipped = gpd.clip(soil, buffer_gdf)
    clipped = clipped[
        clipped.geometry.notna()
        & ~clipped.geometry.is_empty
        & clipped.geom_type.isin(["Polygon", "MultiPolygon"])
    ].copy()
    if clipped.empty:
        raise RuntimeError("No SSURGO polygons intersect the analytical buffer")
    clipped["soil_area_m2"] = clipped.geometry.area
    save_geojson(
        clipped[
            [
                "mukey",
                "musym",
                "muname",
                ATTRIBUTE,
                "soil_area_m2",
                "geometry",
            ]
        ].to_crs(GEOGRAPHIC_CRS),
        OUT / "ssurgo_mapunits_clipped.geojson",
    )

    field_columns = ["field_id", "geometry"]
    if "CSBACRES" in fields.columns:
        field_columns.insert(1, "CSBACRES")
    intersections = gpd.overlay(
        fields[field_columns],
        clipped[["mukey", "musym", "muname", ATTRIBUTE, "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    intersections = intersections[
        intersections.geometry.notna()
        & ~intersections.geometry.is_empty
        & intersections.geom_type.isin(["Polygon", "MultiPolygon"])
    ].copy()
    if intersections.empty:
        raise RuntimeError("Field–SSURGO overlay produced zero polygons")

    invalid = ~intersections.geometry.is_valid
    if invalid.any():
        intersections.loc[invalid, "geometry"] = intersections.loc[
            invalid, "geometry"
        ].apply(repair_polygon)

    intersections["field_id"] = intersections["field_id"].astype(str)
    intersections[ATTRIBUTE] = pd.to_numeric(
        intersections[ATTRIBUTE], errors="coerce"
    )
    intersections["intersection_area_m2"] = intersections.geometry.area
    intersections = intersections[
        intersections["intersection_area_m2"] > 0
    ].copy()
    intersections["intersection_area_acres"] = (
        intersections["intersection_area_m2"] * ACRES_PER_M2
    )
    area_lookup = fields.set_index("field_id").geometry.area
    intersections["field_area_m2"] = intersections["field_id"].map(
        area_lookup
    )
    if intersections["field_area_m2"].isna().any():
        raise RuntimeError("Could not map an intersection to its field area")
    intersections["percent_of_field"] = (
        100.0
        * intersections["intersection_area_m2"]
        / intersections["field_area_m2"]
    )
    intersections["selected_soil_attribute"] = intersections[ATTRIBUTE]

    inter_columns = [
        "field_id",
        "mukey",
        "musym",
        "muname",
        ATTRIBUTE,
        "selected_soil_attribute",
        "intersection_area_m2",
        "intersection_area_acres",
        "field_area_m2",
        "percent_of_field",
        "geometry",
    ]
    save_geojson(
        intersections[inter_columns].to_crs(GEOGRAPHIC_CRS),
        OUT / "field_ssurgo_intersections.geojson",
    )

    field_summary = build_field_summary(fields, intersections)
    mapunit_summary = build_mapunit_summary(
        intersections,
        total_field_area,
    )

    intersection_table = intersections.drop(columns="geometry")
    for path in (
        OUT / "field_ssurgo_intersections.csv",
        TABLES / "field_ssurgo_intersections.csv",
    ):
        intersection_table.to_csv(path, index=False)
    for path in (
        OUT / "field_soil_summary.csv",
        TABLES / "field_soil_summary.csv",
    ):
        field_summary.to_csv(path, index=False)
    for path in (
        OUT / "ssurgo_mapunit_summary.csv",
        OUT / "map_unit_summary.csv",
        TABLES / "ssurgo_mapunit_summary.csv",
        TABLES / "map_unit_summary.csv",
    ):
        mapunit_summary.to_csv(path, index=False)

    fields_output = fields.merge(
        field_summary,
        on="field_id",
        how="left",
        validate="one_to_one",
    )
    save_geojson(
        fields_output.to_crs(GEOGRAPHIC_CRS),
        OUT / "fields_with_ssurgo_summary.geojson",
    )

    visuals = create_maps(
        fields,
        clipped,
        buffer_gdf,
        external_geom,
        field_summary,
    )
    interactive_path = create_interactive(
        fields,
        clipped,
        field_summary,
    )

    source_values = pd.to_numeric(clipped[ATTRIBUTE], errors="coerce")
    field_values = pd.to_numeric(
        field_summary["area_weighted_aws025wta"],
        errors="coerce",
    )
    valid_fields = field_summary[field_values.notna()].copy()
    highest = valid_fields.loc[
        valid_fields["area_weighted_aws025wta"].idxmax(),
        ["field_id", "area_weighted_aws025wta"],
    ].to_dict()
    lowest = valid_fields.loc[
        valid_fields["area_weighted_aws025wta"].idxmin(),
        ["field_id", "area_weighted_aws025wta"],
    ].to_dict()

    quality = {
        "generated_utc": utc_now(),
        "offline": True,
        "network_requests": 0,
        "source_checksums": source["checksums"],
        "source_byte_size": source["gml_bytes"],
        "metadata_validation": source["tests"],
        "field_source": str(FIELD_SOURCE.relative_to(REPO)),
        "field_count": len(fields),
        "field_geometry_repairs": field_repairs,
        "parsed_polygon_features": parsed,
        "clipped_polygon_features": len(clipped),
        "unique_mapunits": int(
            clipped["mukey"].dropna().astype(str).nunique()
        ),
        "soil_geometry_repairs": soil_repairs,
        "wfs_axis_order_swapped": axis_swapped,
        "attribute": ATTRIBUTE,
        "definition": ATTRIBUTE_DEFINITION,
        "units": UNITS,
        "source_attribute_missing_count": int(source_values.isna().sum()),
        "source_attribute_missing_percent": float(
            100.0 * source_values.isna().mean()
        ),
        "source_attribute_observed_count": int(source_values.notna().sum()),
        "source_attribute_stats": stats(source_values),
        "field_weighted_stats": stats(field_values),
        "fields_multiple_units": int(
            (field_summary["mapunit_count"] > 1).sum()
        ),
        "highest_field": highest,
        "lowest_field": lowest,
        "average_field_coverage_percent": float(
            field_summary["coverage_percent"].mean()
        ),
        "minimum_field_coverage_percent": float(
            field_summary["coverage_percent"].min()
        ),
        "buffer_symmetric_difference_m2": buffer_difference,
        "intersection_feature_count": len(intersections),
        "mapunit_summary_rows": len(mapunit_summary),
        "visual_outputs": visuals,
        "interactive_map": str(interactive_path.relative_to(REPO)),
        "environment": {
            "python": platform.python_version(),
            "geopandas": gpd.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "matplotlib": matplotlib.__version__,
            "folium": folium.__version__,
        },
    }

    provenance = {
        "generated_utc": utc_now(),
        "mode": "offline",
        "network_requests": 0,
        "official_endpoint": EXPECTED_ENDPOINT,
        "typename": "MapunitPolyExtended",
        "source_files": {
            str(path.relative_to(REPO)): {
                "sha256": EXPECTED[path],
                "byte_size": path.stat().st_size,
            }
            for path in EXPECTED
        },
        "metadata": source["metadata"],
        "validation": source["tests"],
        "provenance_note": (
            "The official USDA-NRCS response was acquired on the user's "
            "workstation, preserved, and checksum-validated before offline "
            "analysis. No synthetic fallback was used."
        ),
    }

    write_json(OUT / "geospatial_summary.json", quality)
    write_json(OUT / "spatial_quality_summary.json", quality)
    write_json(OUT / "acquisition_provenance.json", provenance)
    write_json(
        OUT / "environment.json",
        {
            "generated_utc": utc_now(),
            **quality["environment"],
            "working_crs": WORKING_CRS,
            "geographic_crs": GEOGRAPHIC_CRS,
        },
    )

    pd.DataFrame(
        [
            {
                "metric": key,
                "value": json.dumps(value, default=json_default),
            }
            for key, value in quality.items()
            if key not in {
                "visual_outputs",
                "environment",
                "metadata_validation",
            }
        ]
    ).to_csv(OUT / "spatial_quality_summary.csv", index=False)

    (OUT / "skill_run.log").write_text(
        "\n".join(
            [
                f"{utc_now()} START Assignment 4 offline mapping",
                "network_requests=0",
                f"source_gml_sha256={EXPECTED[RAW]}",
                f"source_gml_bytes={RAW.stat().st_size}",
                f"field_count={len(fields)}",
                f"field_geometry_repairs={field_repairs}",
                f"parsed_polygon_features={parsed}",
                f"clipped_polygon_features={len(clipped)}",
                f"unique_mapunits={quality['unique_mapunits']}",
                f"attribute={ATTRIBUTE}",
                f"attribute_units={UNITS}",
                "SUCCESS: Assignment 4 offline mapping complete",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(quality, indent=2, default=json_default))
    # Normalize generated SVG and HTML whitespace.
    cleanup_root = A4 / 'output'
    for generated_path in cleanup_root.rglob('*'):
        if (
            generated_path.is_file()
            and generated_path.suffix.lower() in {'.svg', '.html'}
        ):
            generated_lines = generated_path.read_text(
                encoding='utf-8'
            ).splitlines()
            generated_path.write_text(
                '\n'.join(
                    line.rstrip() for line in generated_lines
                ) + '\n',
                encoding='utf-8',
            )

    print("SUCCESS: Assignment 4 offline mapping complete")


if __name__ == "__main__":
    main()
