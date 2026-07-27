from __future__ import annotations

from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
from shapely import wkt

try:
    from .ssurgo_soil import download_soil
except ImportError:
    from ssurgo_soil import download_soil


SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

NUMERIC_SOIL_PROPS = [
    "comppct_r",
    "hzdept_r",
    "hzdepb_r",
    "om_r",
    "ph1to1h2o_r",
    "awc_r",
    "claytotal_r",
    "sandtotal_r",
    "silttotal_r",
    "dbthirdbar_r",
    "cec7_r",
]

TEXT_SOIL_PROPS = ["mukey", "muname", "compname", "drainagecl"]


def query_mupolygons_for_field(field_wkt: str, mukey_list: Iterable[str]) -> gpd.GeoDataFrame:
    mukeys = [str(m) for m in mukey_list]
    if not mukeys:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    sql = f"""
    SELECT m.mukey, m.mupolygonkey, m.mupolygongeo.STAsText() AS wkt
    FROM mupolygon m
    WHERE m.mukey IN ({", ".join(mukeys)})
      AND m.mupolygonkey IN (
        SELECT * FROM SDA_Get_Mupolygonkey_from_intersection_with_WktWgs84('{field_wkt}')
      )
    """
    try:
        resp = requests.post(SDA_URL, data={"query": sql, "format": "JSON"}, timeout=120)
        resp.raise_for_status()
        rows = resp.json().get("Table", [])
    except Exception:
        rows = []

    records = []
    for row in rows:
        try:
            records.append(
                {
                    "mukey": str(row[0]),
                    "mupolygonkey": str(row[1]),
                    "geometry": wkt.loads(row[2]),
                }
            )
        except Exception:
            continue
    if not records:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def load_fallback_mukey_polygons(path: str | Path) -> gpd.GeoDataFrame:
    p = Path(path)
    if not p.exists():
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    gdf = gpd.read_file(p)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    gdf["mukey"] = gdf["mukey"].astype(str)
    cols = [c for c in ["mukey", "mupolygonkey", "geometry"] if c in gdf.columns]
    return gdf[cols].copy()


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna()
    if not valid.any():
        return np.nan
    vals = values[valid].astype(float)
    wts = weights[valid].astype(float)
    denom = float(wts.sum())
    if denom <= 0:
        return float(vals.mean())
    return float((vals * wts).sum() / denom)


def most_common(values: pd.Series):
    non_null = values.dropna()
    if non_null.empty:
        return np.nan
    return non_null.mode().iloc[0]


def aggregate_soil_rows_by_mukey(soil_rows: pd.DataFrame) -> pd.DataFrame:
    groups = []
    for mukey, grp in soil_rows.groupby("mukey"):
        out = {"mukey": str(mukey)}
        weights = pd.to_numeric(grp["comppct_r"], errors="coerce").fillna(1.0)
        for col in NUMERIC_SOIL_PROPS:
            vals = pd.to_numeric(grp[col], errors="coerce")
            out[col] = float(vals.max()) if col == "comppct_r" else weighted_mean(vals, weights)
        for col in ["muname", "compname", "drainagecl"]:
            out[col] = most_common(grp[col])
        groups.append(out)
    return pd.DataFrame(groups)


def prepare_ssurgo_field_package(
    field_wgs84: gpd.GeoDataFrame,
    field_id_column: str = "field_id",
    max_depth_cm: int = 30,
    fallback_mukey_geojson: str | Path | None = None,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame]:
    soil = download_soil(field_wgs84, field_id_column=field_id_column, max_depth_cm=max_depth_cm)
    if soil.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), pd.DataFrame(), pd.DataFrame()

    fid = field_wgs84.iloc[0][field_id_column]
    field_soil = soil[soil[field_id_column] == fid].copy()
    if field_soil.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), pd.DataFrame(), pd.DataFrame()

    field_soil["mukey"] = field_soil["mukey"].astype(str)
    fallback = (
        load_fallback_mukey_polygons(fallback_mukey_geojson)
        if fallback_mukey_geojson is not None
        else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    )

    mukeys = set(field_soil["mukey"].tolist())
    if not fallback.empty:
        mukeys.update(fallback["mukey"].astype(str).tolist())

    sda = query_mupolygons_for_field(field_wgs84.iloc[0].geometry.wkt, sorted(mukeys))
    if sda.empty and not fallback.empty:
        polygons = fallback
    elif (
        not sda.empty
        and not fallback.empty
        and fallback["mukey"].nunique() > sda["mukey"].nunique()
    ):
        polygons = fallback
    else:
        polygons = sda

    if polygons.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), pd.DataFrame(), pd.DataFrame()

    clipped = gpd.overlay(polygons, field_wgs84, how="intersection")
    if clipped.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), pd.DataFrame(), pd.DataFrame()

    dissolved = clipped.dissolve(by="mukey", as_index=False)
    dissolved["mukey"] = dissolved["mukey"].astype(str)
    agg = aggregate_soil_rows_by_mukey(field_soil)
    dissolved = dissolved.merge(agg, on="mukey", how="left")

    utm = dissolved.to_crs(
        "EPSG:32615" if field_wgs84.geometry.iloc[0].centroid.x < -90 else "EPSG:32616"
    )
    dissolved["area_acres"] = utm.geometry.area * 0.000247105

    detail = field_soil.copy()
    detail = detail.merge(dissolved[["mukey", "area_acres"]], on="mukey", how="left")
    detail = detail.sort_values(["mukey", "hzdept_r", "comppct_r"], ascending=[True, True, False])
    return dissolved, detail, agg


def headlands_ring(field_utm: gpd.GeoDataFrame, combine_width_m: float = 9.0) -> gpd.GeoDataFrame:
    rings = []
    for geom in field_utm.geometry:
        inner = geom.buffer(-combine_width_m)
        rings.append(geom if inner.is_empty else geom.difference(inner))
    valid = [g for g in rings if not g.is_empty]
    return (
        gpd.GeoDataFrame(geometry=valid, crs=field_utm.crs)
        if valid
        else gpd.GeoDataFrame(geometry=[], crs=field_utm.crs)
    )


def classify_natural_breaks(values: pd.Series, n_classes: int = 3) -> tuple[np.ndarray, list[str]]:
    arr = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if arr.size == 0:
        return np.array([], dtype=int), []
    unique = np.sort(np.unique(arr))
    class_count = max(1, min(n_classes, unique.size))
    if class_count == 1:
        return np.zeros(arr.size, dtype=int), [f"{unique[0]:.2f}"]
    if unique.size <= class_count:
        edges = np.linspace(arr.min(), arr.max(), class_count + 1)
    else:
        gaps = np.diff(unique)
        split_idx = np.sort(np.argsort(gaps)[-(class_count - 1) :])
        mids = [(unique[i] + unique[i + 1]) / 2.0 for i in split_idx]
        edges = np.array([arr.min(), *mids, arr.max()], dtype=float)
    edges = np.unique(edges)
    if edges.size < 2:
        return np.zeros(arr.size, dtype=int), [f"{arr[0]:.2f}"]
    class_ids = pd.cut(arr, bins=edges, labels=False, include_lowest=True)
    class_ids = pd.Series(class_ids).fillna(0).astype(int).to_numpy()
    labels = [f"{edges[i]:.2f} to {edges[i + 1]:.2f}" for i in range(edges.size - 1)]
    class_ids = np.clip(class_ids, 0, max(0, len(labels) - 1))
    return class_ids, labels


def _add_basemap(
    ax, gdf_wgs84: gpd.GeoDataFrame, alpha: float = 0.5, attribution_size: int = 5
) -> gpd.GeoDataFrame:
    try:
        import contextily as ctx
    except ImportError:
        return gdf_wgs84
    gdf_wm = gdf_wgs84.to_crs(epsg=3857)
    bounds = gdf_wm.total_bounds
    xb = (bounds[2] - bounds[0]) * 0.25
    yb = (bounds[3] - bounds[1]) * 0.25
    ax.set_xlim(bounds[0] - xb, bounds[2] + xb)
    ax.set_ylim(bounds[1] - yb, bounds[3] + yb)
    ctx.add_basemap(
        ax, source=ctx.providers.Esri.WorldImagery, alpha=alpha, attribution_size=attribution_size
    )
    return gdf_wm


def render_ssurgo_property_map(
    field_wgs84: gpd.GeoDataFrame,
    ssurgo_wgs84: gpd.GeoDataFrame,
    property_col: str,
    output_path: str | Path,
    title: str | None = None,
    show_axis_labels: bool = False,
    basemap_alpha: float = 0.5,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 8))
    field_plot = _add_basemap(ax, field_wgs84, alpha=basemap_alpha)
    if not ssurgo_wgs84.empty and property_col in ssurgo_wgs84.columns:
        ssurgo_plot = (
            ssurgo_wgs84.to_crs(epsg=3857) if str(field_plot.crs).endswith("3857") else ssurgo_wgs84
        )
        data = ssurgo_plot.dropna(subset=[property_col]).copy()
        if not data.empty:
            class_ids, labels = classify_natural_breaks(data[property_col])
            if labels:
                data["class_id"] = class_ids
                colors = plt.cm.YlGn(np.linspace(0.35, 0.85, len(labels)))
                handles = []
                for i, label in enumerate(labels):
                    part = data[data["class_id"] == i]
                    if part.empty:
                        continue
                    part.plot(
                        ax=ax, color=colors[i], alpha=0.45, edgecolor="darkgreen", linewidth=1.0
                    )
                    handles.append(
                        Patch(facecolor=colors[i], edgecolor="darkgreen", alpha=0.45, label=label)
                    )
                if handles:
                    ax.legend(
                        handles=handles,
                        loc="lower right",
                        fontsize=7,
                        title=f"{property_col} ranges",
                    )
    field_plot.plot(ax=ax, color="none", edgecolor="darkgreen", linewidth=2.2)
    ax.set_title(title or f"{property_col} (Natural Breaks)")
    if show_axis_labels:
        ax.set_xlabel("Longitude (degrees)")
        ax.set_ylabel("Latitude (degrees)")
    else:
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_xticks([])
        ax.set_yticks([])
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def render_complete_workflow_figure(
    field_wgs84: gpd.GeoDataFrame,
    ssurgo_wgs84: gpd.GeoDataFrame,
    detail_table: pd.DataFrame,
    output_path: str | Path,
    combine_width_m: float = 9.0,
) -> None:
    utm_crs = "EPSG:32615" if field_wgs84.geometry.iloc[0].centroid.x < -90 else "EPSG:32616"
    field_utm = field_wgs84.to_crs(utm_crs)
    ring_utm = headlands_ring(field_utm, combine_width_m=combine_width_m)

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    base1 = _add_basemap(axes[0, 0], field_wgs84)
    base1.plot(ax=axes[0, 0], color="none", edgecolor="darkgreen", linewidth=2.5)
    axes[0, 0].set_title("Field Boundary (WGS84)")
    axes[0, 0].set_xlabel("Longitude (degrees)")
    axes[0, 0].set_ylabel("Latitude (degrees)")

    base2 = _add_basemap(axes[0, 1], field_wgs84)
    if not ssurgo_wgs84.empty and "compname" in ssurgo_wgs84.columns:
        ssurgo2 = (
            ssurgo_wgs84.to_crs(epsg=3857) if str(base2.crs).endswith("3857") else ssurgo_wgs84
        )
        colors = plt.cm.Set3(np.linspace(0, 1, max(1, len(ssurgo2))))
        handles = []
        for i, row in ssurgo2.iterrows():
            c = colors[i % len(colors)]
            gpd.GeoSeries([row.geometry], crs=ssurgo2.crs).plot(
                ax=axes[0, 1], color=c, alpha=0.5, edgecolor="darkgreen"
            )
            comp = row.get("compname", "Unknown")
            comp = comp if isinstance(comp, str) else "Unknown"
            handles.append(Patch(facecolor=c, edgecolor="darkgreen", alpha=0.5, label=comp))
        if handles:
            axes[0, 1].legend(handles=handles, loc="lower right", fontsize=7, title="compname")
    base2.plot(ax=axes[0, 1], color="none", edgecolor="darkgreen", linewidth=2.5)
    axes[0, 1].set_title("Field + SSURGO (WGS84)")
    axes[0, 1].set_xlabel("")
    axes[0, 1].set_ylabel("")
    axes[0, 1].set_xticks([])
    axes[0, 1].set_yticks([])

    base3 = _add_basemap(axes[1, 0], field_utm.to_crs(epsg=4326))
    field3 = field_utm.to_crs(epsg=3857) if str(base3.crs).endswith("3857") else field_utm
    ring3 = (
        ring_utm.to_crs(epsg=3857)
        if not ring_utm.empty and str(base3.crs).endswith("3857")
        else ring_utm
    )
    ssurgo3 = (
        ssurgo_wgs84.to_crs(epsg=3857)
        if not ssurgo_wgs84.empty and str(base3.crs).endswith("3857")
        else ssurgo_wgs84
    )
    if not ssurgo3.empty and "om_r" in ssurgo3.columns:
        ssurgo3.dropna(subset=["om_r"]).plot(
            ax=axes[1, 0],
            column="om_r",
            cmap="YlGn",
            alpha=0.35,
            edgecolor="darkgreen",
            legend=False,
        )
    if not ring3.empty:
        ring3.plot(ax=axes[1, 0], color="orange", alpha=0.35, edgecolor="darkorange", linewidth=1.5)
    field3.plot(ax=axes[1, 0], color="none", edgecolor="darkgreen", linewidth=2.5)
    axes[1, 0].set_title("Headlands Ring + OM Overlay (UTM)")
    axes[1, 0].set_xlabel("X (meters)")
    axes[1, 0].set_ylabel("Y (meters)")
    axes[1, 0].xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(round(x)):,}"))
    axes[1, 0].yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{int(round(y)):,}"))

    axes[1, 1].axis("off")
    cols = [
        "mukey",
        "compname",
        "comppct_r",
        "hzdept_r",
        "hzdepb_r",
        "drainagecl",
        "om_r",
        "ph1to1h2o_r",
        "awc_r",
        "claytotal_r",
        "sandtotal_r",
        "silttotal_r",
        "dbthirdbar_r",
        "cec7_r",
        "area_acres",
    ]
    if not detail_table.empty:
        table_df = detail_table[cols].copy().head(18)
        table_df["drainagecl"] = table_df["drainagecl"].apply(
            lambda s: "".join(w[0].upper() for w in str(s).split()) if pd.notna(s) else ""
        )
        table_df = table_df.rename(
            columns={
                "comppct_r": "comppct",
                "hzdept_r": "hzdept",
                "hzdepb_r": "hzdepb",
                "om_r": "om",
                "ph1to1h2o_r": "ph1to1h2o",
                "awc_r": "awc",
                "claytotal_r": "claytotal",
                "sandtotal_r": "sandtotal",
                "silttotal_r": "silttotal",
                "dbthirdbar_r": "dbthirdbar",
                "cec7_r": "cec7",
            }
        )
        table_df = table_df.replace([np.nan, "nan", "NaN", "None"], "")
        table = axes[1, 1].table(
            cellText=table_df.values, colLabels=table_df.columns, loc="center", cellLoc="center"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        table.scale(1.0, 1.2)
        mukey_idx = table_df.columns.get_loc("mukey")
        palette = ["#f8f4d8", "#e6f4ea", "#e6eef8", "#f8e8ef", "#eef8f8", "#f3e8ff"]
        mukeys = list(table_df["mukey"].astype(str).unique())
        color_map = {m: palette[i % len(palette)] for i, m in enumerate(mukeys)}
        for c in range(len(table_df.columns)):
            h = table[(0, c)]
            h.set_text_props(weight="bold", color="black")
            h.set_facecolor("#f1f3f5")
            h.set_edgecolor("#9aa1a9")
            h.set_linewidth(0.35)
        for r in range(1, len(table_df) + 1):
            m = str(table_df.iloc[r - 1, mukey_idx])
            row_color = color_map.get(m, "#ffffff")
            for c in range(len(table_df.columns)):
                cell = table[(r, c)]
                cell.set_facecolor(row_color)
                cell.set_edgecolor("#aeb6bf")
                cell.set_linewidth(0.35)
                cell.set_text_props(color="black")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
