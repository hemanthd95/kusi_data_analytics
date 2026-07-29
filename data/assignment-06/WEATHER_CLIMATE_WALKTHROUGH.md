# Assignment 6 weather/climate walkthrough

## Objective and requirements
Analyze authentic NASA POWER weather for 25 authoritative row-crop field locations, while preserving provenance and failing closed. Acquisition is currently incomplete because the environment's proxy denied the official endpoint; no analytical results or images are represented as complete.

## Authoritative fields and representative point
The immutable Assignment 2 GeoJSON and summary contain the 25 inputs. The acquisition script validates IDs, EPSG:4326, valid nonempty geometry, and positive acreage; projects to EPSG:32617; computes centroids; weights them by `CSBACRES`; and transforms the result to EPSG:4326. The request location is 34.33090814° N, 82.53604245° W. Distance evidence and cluster spans are committed. One gridded point represents the overall cluster, not within-cluster weather differences.

## NASA POWER request and period
The official Daily Point API request specifies AG, JSON, LST, 1991-01-01–2025-12-31, and T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, and ALLSKY_SFC_SW_DWN. Returned definitions, units, fill values, coordinates, metadata, and original bytes are required before processing.

## Missing data, aggregation, baseline, and seasonality
Fill values become missing and are never interpolated. The daily date index must contain all 12,784 days. Months remain present but analytical values are null below 90% completeness. Temperatures, humidity, and radiation are means; precipitation is accumulated. Annual and April–October windows reset dry spells at their boundaries. The climate-normal baseline is 1991–2020.

## Trends, anomalies, and warm season
The offline workflow implements annual and warm-season temperature/precipitation anomalies, baseline sample-standard-deviation z-scores, `|z| ≥ 2` flags, OLS slopes and confidence intervals, Theil–Sen slopes, and Kendall tests. Hot days (maximum ≥35 °C), frost days (minimum ≤0 °C), dry days (<1 mm), and heavy rain (≥25 mm) are transparent descriptive thresholds, not crop-loss evidence. April–October is an analytical window, not exact phenology.

## Results and agronomic relevance
No numerical climate result is reported because authentic acquisition failed. Once acquired, seasonal climatology can contextualize planting and water planning, and trends/anomalies can describe exposure history; neither establishes causality, global attribution, or crop damage. NASA POWER estimates are gridded rather than on-site observations.

## Reproduction and output inventory
Run the commands in `README.md`. On success the workflow creates nine tables, six PNG/SVG analytical figures, two dashboards, provenance, environment, summary, log, executed notebook, evidence, and verification. The finished walkthrough will embed:

- `output/visualizations/02_monthly_seasonal_climatology.png`
- `output/visualizations/03_annual_temperature_trend.png`
- `output/visualizations/04_annual_precipitation_anomalies.png`
- `output/visualizations/06_assignment_06_final_panel.png`

## Local authentic-file continuation

Use the exact external-import and offline continuation commands in `README.md`. Import validation happens before any success manifest is written and preserves the original Codex proxy failure in acquisition history. The expected independently calculated checksum is documented for a manual comparison, but authentic validation does not rely on that checksum alone.
