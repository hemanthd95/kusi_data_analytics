# Assignment 6 weather/climate walkthrough

## Objective

Analyze authentic NASA POWER weather for the 25 authoritative field locations while preserving provenance, validating the source independently, and avoiding synthetic fallback data.

## Representative weather point

The Assignment 2 field geometries are validated, projected to EPSG:32617, reduced to field centroids, and weighted by `CSBACRES`. The resulting request location is 34.33090814° N, 82.53604245° W. The farthest field centroid is approximately 2.20 km from the representative point. One NASA POWER grid series represents the cluster and does not resolve field-to-field weather differences.

## Source and period

The official NASA POWER Daily Point API request uses the Agroclimatology community, JSON output, LST, 1991-01-01 through 2025-12-31, and six variables: T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, and ALLSKY_SFC_SW_DWN. The raw response, request metadata, returned-grid metadata, checksums, and acquisition history are preserved.

## Data handling

Fill values are converted to missing values and are not interpolated. The complete daily index contains 12,784 dates. Monthly periods require at least 90% complete weather days. Temperature, humidity, and radiation are averaged; precipitation is accumulated. Annual and April–October summaries reset dry-spell calculations at period boundaries.

## Climate analysis

The workflow produces 1991–2020 monthly climate normals, annual and warm-season anomalies, 2021–2025 recent-anomaly tables, baseline z-scores, and `|z| ≥ 2` notable-year flags. Trend statistics include OLS slopes and confidence intervals, Theil–Sen robust slopes, and Kendall rank tests.

Descriptive agricultural-weather indicators include hot days with maximum temperature ≥35 °C, frost days with minimum temperature ≤0 °C, dry days with precipitation <1 mm, heavy-rain days with precipitation ≥25 mm, and warm-season dry-spell duration. These thresholds describe exposure and do not independently prove crop damage.

## Key results

The 1991–2020 baseline annual mean temperature is approximately 16.08 °C and baseline annual precipitation is approximately 1,290.7 mm. The complete analysis contains 12,784 daily records, 420 monthly records, and 35 annual records. Recent-year values, anomalies, notable years, and statistical trend estimates are available in `output/tables/` and `output/climate_summary.json`.

NASA POWER values are gridded estimates rather than on-site measurements. Local descriptive trends do not establish causation or global climate attribution.

## Figures and dashboard assets

Six SVG figures are committed for direct review:

- `output/visualizations/01_field_cluster_and_weather_point.svg`
- `output/visualizations/02_monthly_seasonal_climatology.svg`
- `output/visualizations/03_annual_temperature_trend.svg`
- `output/visualizations/04_annual_precipitation_anomalies.svg`
- `output/visualizations/05_warm_season_weather_risks.svg`
- `output/visualizations/06_assignment_06_final_panel.svg`

The analysis script reproducibly generates matching PNG figures and exactly two dashboard PNG assets. PNG products are intentionally ignored by Git because they are deterministic build outputs; GitHub Actions regenerates and validates them from a clean checkout.

## Reproduction

Run the commands in `README.md`. Verification independently checks source checksums, request metadata, daily coverage, aggregation arithmetic, trend scaling, notebook execution, committed SVGs, and generated PNG dimensions when those build products are present.
