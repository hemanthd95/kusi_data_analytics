#!/usr/bin/env python3
"""Independent Assignment 6 verifier; imports no workflow implementation code."""
from pathlib import Path
import hashlib, json, re, sys
import nbformat
import numpy as np
import pandas as pd
from PIL import Image

R = Path(__file__).resolve().parents[2]
A = R / "data/assignment-06"
failures = []


def ck(ok, msg):
    if not ok:
        failures.append(msg)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


required = [
    "source/nasa_power_daily_raw.json",
    "source/source_manifest.json",
    "source/nasa_power_request.json",
    "source/nasa_power_response_metadata.json",
    "source/representative_weather_point.geojson",
    "source/field_to_weather_point_distances.csv",
    "source/field_location_summary.json",
    "output/acquisition_provenance.json",
    "output/climate_summary.json",
    "output/weather_data_quality.json",
    "output/environment.json",
    "output/skill_run.log",
    "output/tables/weather_data_quality.csv",
    "output/tables/weather_daily_1991_2025.csv",
    "output/tables/weather_monthly_1991_2025.csv",
    "output/tables/weather_annual_1991_2025.csv",
    "output/tables/weather_warm_season_1991_2025.csv",
    "output/tables/climate_normals_1991_2020.csv",
    "output/tables/climate_anomalies_1991_2025.csv",
    "output/tables/recent_anomalies_2021_2025.csv",
    "output/tables/climate_trend_statistics.csv",
    *[
        f"output/visualizations/{i:02d}_{name}.svg"
        for i, name in [
            (1, "field_cluster_and_weather_point"),
            (2, "monthly_seasonal_climatology"),
            (3, "annual_temperature_trend"),
            (4, "annual_precipitation_anomalies"),
            (5, "warm_season_weather_risks"),
            (6, "assignment_06_final_panel"),
        ]
    ],
    "WEATHER_CLIMATE_WALKTHROUGH.md",
    "README.md",
]
for item in required:
    path = A / item
    ck(path.is_file() and path.stat().st_size > 0, f"missing/empty: {item}")

try:
    manifest = json.loads((A / "source/source_manifest.json").read_text())
    raw = A / "source/nasa_power_daily_raw.json"
    request = json.loads((A / "source/nasa_power_request.json").read_text())
    response_meta = json.loads((A / "source/nasa_power_response_metadata.json").read_text())
    provenance = json.loads((A / "output/acquisition_provenance.json").read_text())

    ck(sha(raw) == manifest["raw_response"]["sha256"], "raw checksum")
    ck(request == manifest["request"], "request metadata matches manifest")
    ck(provenance.get("status") == "success" and provenance.get("request") == request, "successful acquisition provenance schema")
    ck(provenance.get("no_synthetic_fallback") is True, "provenance synthetic fallback")
    expected_parameters = {"T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN"}
    ck(set(response_meta.get("parameters", {})) == expected_parameters, "response metadata parameters")
    ck(all(response_meta.get("parameters", {}).get(x, {}).get("units") for x in expected_parameters), "response metadata units")
    ck(any(v is not None for v in response_meta.get("fill_values", {}).values()), "response fill-value metadata")
    ck(manifest["source"] == "NASA POWER" and manifest["endpoint"] == "https://power.larc.nasa.gov/api/temporal/daily/point", "official source")
    ck(manifest["request"]["community"] == "AG" and manifest["request"]["requested_date_range"] == {"start": "1991-01-01", "end": "2025-12-31"}, "request specification")
    ck(set(manifest["request"]["parameters"]) == expected_parameters, "six parameters")
    ck(manifest["no_synthetic_fallback"] is True, "synthetic fallback")

    for path, expected_hash in manifest["authoritative_inputs"].items():
        ck(sha(R / path) == expected_hash, f"input checksum {path}")

    raw_json = json.loads(raw.read_text())
    ck("POWER" in str(raw_json.get("header", {})).upper() and "parameter" in raw_json.get("properties", {}), "authentic metadata")

    distances = pd.read_csv(A / "source/field_to_weather_point_distances.csv", dtype={"field_id": str})
    ck(len(distances) == 25 and distances.field_id.nunique() == 25, "field integrity")

    daily = pd.read_csv(A / "output/tables/weather_daily_1991_2025.csv", parse_dates=["date"])
    ck(len(daily) == 12784 and daily.date.is_unique and daily.date.is_monotonic_increasing, "daily coverage")
    ck(daily.date.iloc[0] == pd.Timestamp("1991-01-01") and daily.date.iloc[-1] == pd.Timestamp("2025-12-31"), "date endpoints")
    ck(np.allclose(daily.diurnal_temperature_range_C, daily.t2m_max_C - daily.t2m_min_C, equal_nan=True), "DTR")
    ck((daily.hot_day_ge_35C == (daily.t2m_max_C >= 35)).all(), "hot flags")
    ck((daily.dry_day_lt_1mm == (daily.precipitation_mm < 1)).all(), "dry flags")
    ck(not (daily.t2m_min_C > daily.t2m_max_C).mean() > 0.01, "temperature ordering")

    monthly = pd.read_csv(A / "output/tables/weather_monthly_1991_2025.csv")
    annual = pd.read_csv(A / "output/tables/weather_annual_1991_2025.csv")
    normals = pd.read_csv(A / "output/tables/climate_normals_1991_2020.csv")
    recent = pd.read_csv(A / "output/tables/recent_anomalies_2021_2025.csv")
    ck(len(monthly) == 420 and len(annual) == 35 and len(normals) == 12 and set(recent.year) == set(range(2021, 2026)), "aggregation counts")
    sample = daily[(daily.year == 1991) & (daily.month == 1)]
    row = monthly[(monthly.year == 1991) & (monthly.month == 1)].iloc[0]
    ck(np.isclose(row.precipitation_mm, sample.precipitation_mm.sum()), "monthly precipitation reproduction")
    ck(np.isclose(row.mean_temperature_C, sample.t2m_mean_C.mean()), "monthly temperature reproduction")

    trends = pd.read_csv(A / "output/tables/climate_trend_statistics.csv")
    required_metrics = {
        "annual_mean_temperature_C",
        "annual_precipitation_mm",
        "warm_season_mean_temperature_C",
        "warm_season_precipitation_mm",
        "hot_day_count",
        "warm_season_longest_dry_spell_days",
    }
    ck(required_metrics <= set(trends.metric), "trend metrics")
    ck(np.isfinite(trends.select_dtypes("number")).all().all(), "finite trends")
    ck(np.allclose(trends.ols_slope_per_decade, trends.ols_slope_per_year * 10), "OLS decade scaling")
    ck(np.allclose(trends.theil_sen_slope_per_decade, trends.theil_sen_slope_per_year * 10), "Theil decade scaling")

    summary = json.loads((A / "output/climate_summary.json").read_text())
    for path, expected_hash in summary["output_checksums"].items():
        ck(sha(R / path) == expected_hash, f"output checksum {path}")

    pngs = list((A / "output/visualizations").glob("*.png"))
    dashboards = list((A / "output/dashboard_assets").glob("*.png"))
    if pngs or dashboards:
        ck(len(pngs) == 6, "generated analytical PNG count")
        ck(len(dashboards) == 2, "generated dashboard PNG count")
        for path in pngs:
            width, height = Image.open(path).size
            ck(width >= 1800, f"PNG width {path.name}")
            ck(path.name != "06_assignment_06_final_panel.png" or (width >= 2400 and height >= 1800), "final panel dimensions")
        for path in dashboards:
            ck(Image.open(path).size[0] >= 1800, f"dashboard width {path.name}")

    notebook = nbformat.read(R / "notebooks/06_weather_climate_trends.ipynb", 4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    ck(code_cells and all(cell.execution_count is not None for cell in code_cells), "notebook execution")
    ck(not any(output.output_type == "error" for cell in code_cells for output in cell.outputs), "notebook errors")

    walkthrough = (A / "WEATHER_CLIMATE_WALKTHROUGH.md").read_text()
    ck(all(name in walkthrough for name in [
        "02_monthly_seasonal_climatology.svg",
        "03_annual_temperature_trend.svg",
        "04_annual_precipitation_anomalies.svg",
        "06_assignment_06_final_panel.svg",
    ]), "walkthrough figure references")
    ck("SUCCESS: Assignment 6 real-data weather and climate workflow complete" in (A / "output/skill_run.log").read_text(), "success message")

    source_code = "\n".join(path.read_text(errors="ignore") for path in (A / "scripts").glob("*.py"))
    ck(not re.search(r"np\.random|random\.", source_code), "random generation")
except Exception as exc:
    failures.append(f"{type(exc).__name__}: {exc}")

if failures:
    for failure in failures:
        print("FAIL:", failure)
    sys.exit(1)
print("PASS: Assignment 6 verification succeeded (all checks passed).")
