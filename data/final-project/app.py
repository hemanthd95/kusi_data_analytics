#!/usr/bin/env python3
"""Bokeh server application for the Row Crop Intelligence Dashboard.

Run from the repository root:
    bokeh serve data/final-project/app.py --show
"""
from __future__ import annotations

import html
import json
import sqlite3
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from bokeh.io import curdoc
from bokeh.layouts import column, gridplot, row
from bokeh.models import (
    BasicTicker,
    ColorBar,
    ColumnDataSource,
    DataTable,
    Div,
    HoverTool,
    LinearColorMapper,
    NumberFormatter,
    RadioButtonGroup,
    Select,
    Span,
    StringFormatter,
    TabPanel,
    TableColumn,
    Tabs,
)
from bokeh.palettes import RdYlGn11, TolRainbow7
from bokeh.plotting import figure
from bokeh.transform import linear_cmap

PROJECT = Path(__file__).resolve().parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from dashboard_core import (  # noqa: E402
    TASKS,
    field_advisory,
    find_repo_root,
    priority_label,
    task_slug,
)

REPO = find_repo_root(PROJECT)
DB = PROJECT / "output" / "dashboard_data.sqlite"
GEOJSON = REPO / "data/assignment-07/output/integrated_fields.geojson"
SUMMARY = json.loads((PROJECT / "output/dashboard_summary.json").read_text(encoding="utf-8"))

if not DB.is_file():
    raise FileNotFoundError(
        "Missing dashboard_data.sqlite. Run data/final-project/scripts/build_final_project_data.py first."
    )

with sqlite3.connect(DB) as connection:
    fields = pd.read_sql_query("SELECT * FROM fields ORDER BY field_id", connection)
    weather = pd.read_sql_query("SELECT * FROM weather_annual ORDER BY year", connection)
    priorities = pd.read_sql_query(
        "SELECT * FROM task_priorities ORDER BY task, attention_score DESC, field_id", connection
    )
    sources = pd.read_sql_query("SELECT * FROM data_sources ORDER BY assignment", connection)
    climate = pd.read_sql_query("SELECT * FROM climate_context", connection).iloc[0].to_dict()

geo = gpd.read_file(GEOJSON)
geo["field_id"] = geo["field_id"].astype(str)
fields["field_id"] = fields["field_id"].astype(str)
geo = geo[["field_id", "geometry"]].merge(fields, on="field_id", validate="one_to_one")


THEME = {
    "navy": "#17324d",
    "blue": "#2f6690",
    "green": "#477a45",
    "light_green": "#edf5ea",
    "gold": "#d99b2b",
    "red": "#a23b32",
    "cream": "#fbfaf6",
    "gray": "#5f6b73",
    "light_gray": "#eef1f3",
}


def polygon_xy(geometry):
    xs: list[float] = []
    ys: list[float] = []
    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    for index, polygon in enumerate(polygons):
        if index:
            xs.append(float("nan"))
            ys.append(float("nan"))
        x, y = polygon.exterior.coords.xy
        xs.extend(list(x))
        ys.extend(list(y))
    return xs, ys


map_xs, map_ys = zip(*(polygon_xy(geometry) for geometry in geo.geometry))
geo["xs"] = list(map_xs)
geo["ys"] = list(map_ys)


def card(title: str, value: str, subtitle: str = "") -> str:
    return f"""
    <div style="background:white;border-left:6px solid {THEME['green']};padding:14px 16px;
                border-radius:8px;box-shadow:0 2px 7px rgba(0,0,0,.10);min-height:88px;">
      <div style="font-size:12px;color:{THEME['gray']};font-weight:700;text-transform:uppercase;letter-spacing:.5px;">{html.escape(title)}</div>
      <div style="font-size:28px;color:{THEME['navy']};font-weight:800;margin-top:3px;">{html.escape(value)}</div>
      <div style="font-size:12px;color:{THEME['gray']};margin-top:2px;">{html.escape(subtitle)}</div>
    </div>
    """


def narrative_html(field_row: pd.Series, task: str) -> str:
    advisory = field_advisory(field_row, task, climate)
    actions = "".join(f"<li>{html.escape(item)}</li>" for item in advisory["actions"])
    evidence = "".join(f"<li>{html.escape(item)}</li>" for item in advisory["evidence"])
    label_color = THEME["red"] if advisory["priority_score"] >= 50 else THEME["gold"] if advisory["priority_score"] >= 35 else THEME["green"]
    return f"""
    <div style="background:white;border-radius:10px;padding:18px 20px;border:1px solid #d9e0e5;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
        <h2 style="margin:0;color:{THEME['navy']};font-size:21px;">Field {html.escape(str(field_row['field_id']))}</h2>
        <span style="background:{label_color};color:white;padding:6px 10px;border-radius:18px;font-size:12px;font-weight:700;">
          {html.escape(advisory['priority_label'])}: {advisory['priority_score']:.1f}
        </span>
      </div>
      <p style="font-size:17px;font-weight:700;color:{THEME['navy']};margin:13px 0 8px;">{html.escape(advisory['headline'])}</p>
      <h3 style="font-size:14px;color:{THEME['green']};margin-bottom:5px;">Suggested follow-up</h3>
      <ul style="margin-top:4px;line-height:1.45;">{actions}</ul>
      <h3 style="font-size:14px;color:{THEME['blue']};margin-bottom:5px;">Why this field is ranked here</h3>
      <ul style="margin-top:4px;line-height:1.4;">{evidence}</ul>
      <div style="background:#fff5df;border-left:4px solid {THEME['gold']};padding:9px 11px;margin-top:12px;font-size:12px;">
        <b>Measure before acting:</b> {html.escape(advisory['caution'])}
      </div>
    </div>
    """


def filter_fields(soil: str) -> pd.DataFrame:
    if soil == "All soil types":
        return fields.copy()
    return fields.loc[fields["dominant_musym"] == soil].copy()


def priority_frame(task: str, soil: str) -> pd.DataFrame:
    frame = priorities.loc[priorities["task"] == task].copy()
    if soil != "All soil types":
        valid = set(fields.loc[fields["dominant_musym"] == soil, "field_id"])
        frame = frame.loc[frame["field_id"].isin(valid)]
    return frame.sort_values(["attention_score", "field_id"], ascending=[False, True]).reset_index(drop=True)


field_options = sorted(fields["field_id"].tolist())
soil_options = ["All soil types"] + sorted(fields["dominant_musym"].unique().tolist())
field_select = Select(title="Field ID", value=field_options[0], options=field_options, width=250)
soil_select = Select(title="Dominant soil type", value="All soil types", options=soil_options, width=250)
task_select = Select(title="Management decision", value=TASKS[0], options=list(TASKS), width=270)

header = Div(
    text=f"""
    <div style="background:{THEME['navy']};color:white;padding:20px 24px;border-radius:10px;">
      <div style="font-size:13px;text-transform:uppercase;letter-spacing:1.2px;color:#bcd1df;">Farmer decision-support prototype</div>
      <div style="font-size:32px;font-weight:800;margin-top:2px;">Row Crop Intelligence Dashboard</div>
      <div style="font-size:14px;margin-top:7px;color:#dce7ee;">Prioritize field checks using verified crop history, SSURGO soils, Landsat NDVI, NASA POWER climate context, and sustainability metrics.</div>
    </div>
    """,
    sizing_mode="stretch_width",
)

scope_notice = Div(
    text=(
        f"<div style='background:#eef5f8;padding:10px 14px;border-radius:7px;font-size:12px;color:{THEME['navy']};'>"
        "<b>Authentic scope:</b> 25 validated fields (170.3 acres). The assignment’s 200-field tile was an example; no additional fields or yield values were fabricated."
        "</div>"
    ),
    sizing_mode="stretch_width",
)

kpi_divs = [Div(width=230, height=120) for _ in range(5)]

# Map and ranking sources
initial_task = TASKS[0]
initial_priority_col = f"priority_{task_slug(initial_task)}"
map_data = geo.copy()
map_data["priority"] = map_data[initial_priority_col]
map_data["alpha"] = 0.85
map_data["line_width"] = np.where(map_data["field_id"] == field_select.value, 4.0, 1.0)
map_data["line_color"] = np.where(map_data["field_id"] == field_select.value, "#111111", "#ffffff")
map_source = ColumnDataSource(map_data.drop(columns="geometry"))

mapper = LinearColorMapper(palette=list(reversed(RdYlGn11)), low=0, high=100)
map_plot = figure(
    title="Field attention map — higher score means inspect sooner",
    height=560,
    width=700,
    match_aspect=True,
    tools="pan,wheel_zoom,reset,tap,save",
    active_scroll="wheel_zoom",
    toolbar_location="above",
)
map_plot.patches(
    xs="xs",
    ys="ys",
    source=map_source,
    fill_color={"field": "priority", "transform": mapper},
    fill_alpha="alpha",
    line_color="line_color",
    line_width="line_width",
)
map_plot.add_tools(
    HoverTool(
        tooltips=[
            ("Field", "@field_id"),
            ("Crop 2023", "@crop_2023"),
            ("Soil", "@dominant_musym — @dominant_muname"),
            ("Attention", "@priority{0.0}"),
            ("Soil score", "@soil_sustainability_score{0.0}"),
            ("AWS", "@area_weighted_aws025wta{0.00} cm"),
        ]
    )
)
map_plot.add_layout(ColorBar(color_mapper=mapper, ticker=BasicTicker(), title="Attention score"), "right")
map_plot.axis.visible = False
map_plot.grid.visible = False
map_plot.background_fill_color = THEME["cream"]

rank_source = ColumnDataSource(priority_frame(initial_task, soil_select.value).head(10))
rank_columns = [
    TableColumn(field="field_short_id", title="Field", formatter=StringFormatter(text_align="center")),
    TableColumn(field="attention_score", title="Attention", formatter=NumberFormatter(format="0.0")),
    TableColumn(field="attention_level", title="Level"),
    TableColumn(field="crop_2023", title="2023 crop"),
    TableColumn(field="dominant_musym", title="Soil"),
]
rank_table = DataTable(source=rank_source, columns=rank_columns, width=670, height=310, index_position=None, selectable=True)
advisory_div = Div(width=670, height=430)

# Crop history plot
crop_source = ColumnDataSource(data={"year": ["2020", "2021", "2022", "2023"], "height": [1, 1, 1, 1], "crop": ["", "", "", ""], "color": [TolRainbow7[0]] * 4})
crop_plot = figure(
    x_range=["2020", "2021", "2022", "2023"],
    y_range=(0, 1.25),
    title="Four-year dominant crop history",
    height=330,
    width=610,
    toolbar_location=None,
)
crop_plot.vbar(x="year", top="height", width=0.76, color="color", source=crop_source)
crop_plot.text(x="year", y=0.5, text="crop", source=crop_source, angle=np.pi / 2, text_align="center", text_baseline="middle", text_font_size="10px", text_color="white")
crop_plot.yaxis.visible = False
crop_plot.grid.visible = False

# EDA relationship plot
eda_source = ColumnDataSource(fields)
selected_eda_source = ColumnDataSource(fields.iloc[[0]])
eda_plot = figure(
    title="Assignment 3 EDA: field acreage vs. crop-classification confidence",
    height=390,
    width=650,
    tools="pan,wheel_zoom,reset,save",
)
eda_plot.scatter("CSBACRES", "mean_dominant_pct", source=eda_source, size=9, alpha=0.55, color=THEME["blue"])
eda_plot.scatter("CSBACRES", "mean_dominant_pct", source=selected_eda_source, size=18, color=THEME["gold"], line_color=THEME["navy"], line_width=2)
eda_plot.add_tools(HoverTool(tooltips=[("Field", "@field_id"), ("Acres", "@CSBACRES{0.0}"), ("Mean confidence", "@mean_dominant_pct{0.0}%")]))
eda_plot.xaxis.axis_label = "Field area (acres)"
eda_plot.yaxis.axis_label = "Mean dominant CDL confidence (%)"

# NDVI gauge
ndvi_source = ColumnDataSource(data={"x": [], "y": []})
ndvi_plot = figure(
    title="Assignment 5 Landsat NDVI evidence",
    x_range=(0, 1),
    y_range=(0, 1),
    height=240,
    width=610,
    toolbar_location=None,
)
ndvi_plot.quad(left=0, right=0.3, bottom=0.25, top=0.75, color="#c74b50", alpha=0.85)
ndvi_plot.quad(left=0.3, right=0.6, bottom=0.25, top=0.75, color="#e0aa3e", alpha=0.85)
ndvi_plot.quad(left=0.6, right=1.0, bottom=0.25, top=0.75, color="#4c8b55", alpha=0.85)
ndvi_plot.scatter("x", "y", source=ndvi_source, size=24, color="white", line_color=THEME["navy"], line_width=4)
ndvi_plot.yaxis.visible = False
ndvi_plot.grid.visible = False
ndvi_plot.xaxis.axis_label = "NDVI"
ndvi_div = Div(width=610, height=125)

# Soil components
component_source = ColumnDataSource(data={"component": [], "score": [], "color": []})
component_plot = figure(
    y_range=[],
    x_range=(0, 100),
    title="Selected-field sustainability components",
    height=370,
    width=610,
    toolbar_location=None,
)
component_plot.hbar(y="component", right="score", height=0.58, color="color", source=component_source)
component_plot.text(x="score", y="component", text="score_label", source=component_source, x_offset=7, text_baseline="middle", text_font_size="10px")
component_plot.xaxis.axis_label = "Relative score (0–100)"
component_plot.grid.grid_line_alpha = 0.25

score_rank_source = ColumnDataSource(data={"field_short_id": [], "score": [], "color": []})
score_rank_plot = figure(
    y_range=[],
    x_range=(0, 100),
    title="Soil-sustainability score by field",
    height=560,
    width=720,
    toolbar_location=None,
)
score_rank_plot.hbar(y="field_short_id", right="score", height=0.68, color="color", source=score_rank_source)
score_rank_plot.xaxis.axis_label = "Relative sustainability score"
score_rank_plot.grid.grid_line_alpha = 0.22
soil_div = Div(width=610, height=180)

# Weather plots
weather_source = ColumnDataSource(weather)
baseline_temp = float(climate["baseline_temperature_C"])
baseline_precip = float(climate["baseline_precipitation_mm"])
temp_plot = figure(title="Annual mean temperature, 1991–2025", height=360, width=690, tools="pan,wheel_zoom,reset,save")
temp_plot.line("year", "annual_mean_temperature_C", source=weather_source, line_width=3, color=THEME["red"])
temp_plot.scatter("year", "annual_mean_temperature_C", source=weather_source, size=5, color=THEME["red"], alpha=0.7)
temp_plot.add_layout(Span(location=baseline_temp, dimension="width", line_dash="dashed", line_color=THEME["gray"], line_width=2))
temp_plot.yaxis.axis_label = "Temperature (°C)"
temp_plot.add_tools(HoverTool(tooltips=[("Year", "@year"), ("Temperature", "@annual_mean_temperature_C{0.00} °C")]))

precip_plot = figure(title="Annual precipitation, 1991–2025", height=360, width=690, tools="pan,wheel_zoom,reset,save")
precip_plot.vbar(x="year", top="annual_precipitation_mm", source=weather_source, width=0.75, color=THEME["blue"], alpha=0.75)
precip_plot.add_layout(Span(location=baseline_precip, dimension="width", line_dash="dashed", line_color=THEME["gray"], line_width=2))
precip_plot.yaxis.axis_label = "Precipitation (mm)"
precip_plot.add_tools(HoverTool(tooltips=[("Year", "@year"), ("Precipitation", "@annual_precipitation_mm{0} mm"), ("Dry spell", "@longest_dry_spell_days days")]))
climate_div = Div(width=620, height=255)

# Data and limitation tables
source_table_source = ColumnDataSource(sources)
source_table = DataTable(
    source=source_table_source,
    columns=[
        TableColumn(field="assignment", title="Assignment"),
        TableColumn(field="path", title="Verified source path"),
        TableColumn(field="sha256", title="SHA-256"),
    ],
    width=1320,
    height=260,
    index_position=None,
)
limitations_div = Div(
    text="<h2 style='color:#17324d'>Use boundaries and limitations</h2>"
    + "".join(f"<div style='margin:8px 0;padding:9px 12px;background:#f2f4f5;border-left:4px solid #5f6b73;'>{html.escape(item)}</div>" for item in SUMMARY["limitations"])
    + "<h3 style='color:#477a45'>Yield status</h3><p><b>No yield or bushel prediction is shown.</b> The validated package contains no yield observations, so adding a predicted total would be unsupported.</p>",
    width=1320,
    height=430,
)

requirements = SUMMARY["requirement_matrix"]
requirements_div = Div(
    text="<h2 style='color:#17324d'>Final Project requirement coverage</h2>"
    + "<div style='display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;'>"
    + "".join(
        f"<div style='background:#edf5ea;padding:9px 12px;border-radius:6px;'><b>✓ {html.escape(key.replace('_',' ').title())}</b></div>"
        for key, value in requirements.items() if value
    )
    + "</div>",
    width=1320,
    height=300,
)

crop_palette = {
    "Grassland/Pasture": "#5b8c5a",
    "Other Hay/Non Alfalfa": "#a6b65c",
    "Winter Wheat": "#d9a441",
    "Oats": "#c9883b",
}
component_colors = [THEME["blue"], THEME["green"], THEME["gold"], "#7c5c99"]


def current_field_row() -> pd.Series:
    return fields.loc[fields["field_id"] == field_select.value].iloc[0]


def update_kpis() -> None:
    subset = filter_fields(soil_select.value)
    task = task_select.value
    priority_col = f"priority_{task_slug(task)}"
    high_count = int((subset[priority_col] >= 50).sum())
    values = [
        ("Fields in view", f"{len(subset)}", "25-field verified package"),
        ("Acreage in view", f"{subset['CSBACRES'].sum():.1f}", "acres"),
        ("Average soil score", f"{subset['soil_sustainability_score'].mean():.1f}", "relative 0–100 index"),
        ("High-attention fields", f"{high_count}", task.lower()),
        (f"{int(climate['latest_year'])} precipitation", f"{float(climate['latest_precipitation_anomaly_pct']):+.1f}%", "vs. 1991–2020 mean"),
    ]
    for div, (title, value, subtitle) in zip(kpi_divs, values):
        div.text = card(title, value, subtitle)


def update_controls_for_soil() -> None:
    subset = filter_fields(soil_select.value)
    options = sorted(subset["field_id"].tolist())
    field_select.options = options
    if field_select.value not in options:
        field_select.value = options[0]


def update_map_and_rank() -> None:
    task = task_select.value
    col = f"priority_{task_slug(task)}"
    data = geo.copy()
    data["priority"] = data[col]
    active_soil = soil_select.value
    data["alpha"] = np.where(
        (active_soil == "All soil types") | (data["dominant_musym"] == active_soil), 0.88, 0.12
    )
    data["line_width"] = np.where(data["field_id"] == field_select.value, 4.0, 1.0)
    data["line_color"] = np.where(data["field_id"] == field_select.value, "#111111", "#ffffff")
    map_source.data = ColumnDataSource.from_df(data.drop(columns="geometry"))
    map_plot.title.text = f"Field attention map — {task}"

    ranked = priority_frame(task, active_soil).head(10)
    rank_source.data = ColumnDataSource.from_df(ranked)


def update_selected_field() -> None:
    selected = current_field_row()
    advisory_div.text = narrative_html(selected, task_select.value)

    # Crop history
    crops = [selected[f"crop_{year}"] for year in range(2020, 2024)]
    crop_source.data = {
        "year": [str(year) for year in range(2020, 2024)],
        "height": [1] * 4,
        "crop": crops,
        "color": [crop_palette.get(crop, THEME["gray"]) for crop in crops],
    }
    crop_plot.title.text = f"Field {selected['field_short_id']} — four-year dominant crop history"

    selected_eda_source.data = ColumnDataSource.from_df(fields.loc[fields["field_id"] == selected["field_id"]])

    # NDVI
    ndvi_value = selected.get("ndvi_mean")
    if pd.notna(ndvi_value):
        ndvi_source.data = {"x": [float(ndvi_value)], "y": [0.5]}
        ndvi_div.text = (
            f"<div style='background:#edf5ea;padding:12px;border-radius:7px;'><b>Historical Landsat observation:</b> "
            f"NDVI {float(ndvi_value):.3f} on {html.escape(str(selected['ndvi_date']))}. The available scene indicated high greenness, "
            "but it is a single 30 m historical observation and cannot diagnose current stress.</div>"
        )
    else:
        ndvi_source.data = {"x": [], "y": []}
        ndvi_div.text = (
            "<div style='background:#f2f4f5;padding:12px;border-radius:7px;'><b>No field-specific NDVI is available for this field.</b> "
            "Assignment 5 contains authentic Landsat evidence for one demonstration field only; values are not extrapolated.</div>"
        )

    components = ["Water storage", "Slope resilience", "Erosion history", "Rotation diversity"]
    scores = [
        float(selected["water_storage_score"]),
        float(selected["slope_resilience_score"]),
        float(selected["erosion_history_score"]),
        float(selected["rotation_diversity_score"]),
    ]
    component_source.data = {
        "component": components,
        "score": scores,
        "score_label": [f"{score:.1f}" for score in scores],
        "color": component_colors,
    }
    component_plot.y_range.factors = list(reversed(components))
    weakest_index = int(np.argmin(scores))
    soil_div.text = (
        f"<div style='background:white;padding:14px;border-radius:8px;border:1px solid #d9e0e5;'>"
        f"<b>Selected soil:</b> {html.escape(str(selected['dominant_musym']))} — {html.escape(str(selected['dominant_muname']))}<br>"
        f"<b>Weakest relative component:</b> {html.escape(components[weakest_index])} ({scores[weakest_index]:.1f}/100).<br>"
        f"<b>Mapped AWS:</b> {float(selected['area_weighted_aws025wta']):.2f} cm in the 0–25 cm layer; "
        f"<b>weighted slope midpoint:</b> {float(selected['area_weighted_slope_midpoint_pct']):.1f}%."
        "</div>"
    )

    # Update score rank
    subset = filter_fields(soil_select.value).sort_values("soil_sustainability_score", ascending=True)
    score_rank_source.data = {
        "field_short_id": subset["field_short_id"].tolist(),
        "score": subset["soil_sustainability_score"].tolist(),
        "color": [THEME["gold"] if fid == selected["field_id"] else THEME["green"] for fid in subset["field_id"]],
    }
    score_rank_plot.y_range.factors = subset["field_short_id"].tolist()


def update_climate() -> None:
    climate_div.text = f"""
    <div style="background:white;border-radius:9px;border:1px solid #d9e0e5;padding:16px 18px;">
      <h2 style="margin:0 0 8px;color:{THEME['navy']};">Climate planning context</h2>
      <p><b>{int(climate['latest_year'])}</b> was {html.escape(str(climate['moisture_context']))}: annual precipitation was
      <b>{float(climate['latest_precipitation_anomaly_pct']):+.1f}%</b> relative to the 1991–2020 mean.</p>
      <p>The descriptive 1991–2025 temperature trend is <b>{float(climate['temperature_trend_C_per_decade']):+.2f} °C/decade</b>.
      Use this history for seasonal risk planning, not as a current forecast.</p>
      <div style="background:#fff5df;border-left:4px solid {THEME['gold']};padding:9px 11px;">
      Check a current local forecast and in-field soil moisture before planting, spraying, irrigation, or harvest decisions.</div>
    </div>
    """


def refresh_all() -> None:
    update_kpis()
    update_map_and_rank()
    update_selected_field()
    update_climate()


def on_soil_change(attr, old, new):
    update_controls_for_soil()
    refresh_all()


def on_field_change(attr, old, new):
    update_map_and_rank()
    update_selected_field()


def on_task_change(attr, old, new):
    update_kpis()
    update_map_and_rank()
    update_selected_field()


def on_map_selection(attr, old, new):
    if new:
        index = new[0]
        selected_id = str(map_source.data["field_id"][index])
        if selected_id in field_select.options:
            field_select.value = selected_id


def on_table_selection(attr, old, new):
    if new:
        index = new[0]
        selected_id = str(rank_source.data["field_id"][index])
        if selected_id in field_select.options:
            field_select.value = selected_id


soil_select.on_change("value", on_soil_change)
field_select.on_change("value", on_field_change)
task_select.on_change("value", on_task_change)
map_source.selected.on_change("indices", on_map_selection)
rank_source.selected.on_change("indices", on_table_selection)

controls = row(field_select, soil_select, task_select, sizing_mode="stretch_width")
kpis = row(*kpi_divs, sizing_mode="stretch_width")

# Tab layouts
decision_tab = TabPanel(
    title="Decision Center",
    child=column(
        Div(text="<h2 style='color:#17324d;margin:5px 0'>Which field should I inspect first?</h2><p style='color:#5f6b73'>Choose a management task. The map and ranking recalculate relative attention using verified field evidence.</p>"),
        row(map_plot, column(advisory_div, Div(text="<h3 style='color:#17324d'>Top fields in the current view</h3>"), rank_table)),
    ),
)

crop_tab = TabPanel(
    title="Crop & Vegetation",
    child=column(
        Div(text="<h2 style='color:#17324d;margin:5px 0'>Crop history, classification confidence, and available NDVI</h2>"),
        row(crop_plot, eda_plot),
        row(ndvi_plot, ndvi_div),
    ),
)

soil_tab = TabPanel(
    title="Soil & Conservation",
    child=column(
        Div(text="<h2 style='color:#17324d;margin:5px 0'>Relative soil and conservation priorities</h2>"),
        row(column(component_plot, soil_div), score_rank_plot),
    ),
)

weather_tab = TabPanel(
    title="Weather & Climate",
    child=column(
        Div(text="<h2 style='color:#17324d;margin:5px 0'>Historical weather context for seasonal planning</h2>"),
        row(temp_plot, precip_plot),
        climate_div,
    ),
)

data_tab = TabPanel(
    title="Data & Limitations",
    child=column(requirements_div, source_table, limitations_div),
)

tabs = Tabs(tabs=[decision_tab, crop_tab, soil_tab, weather_tab, data_tab], width=1420)

root_layout = column(header, scope_notice, controls, kpis, tabs, sizing_mode="stretch_width")
curdoc().add_root(root_layout)
curdoc().title = "Row Crop Intelligence Dashboard"
curdoc().theme = "light_minimal"
refresh_all()
