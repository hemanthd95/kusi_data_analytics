# Assignment 6 — Weather and Climate Trends

**Status: incomplete (authentic acquisition blocked by the execution environment).** The implemented workflow targets the 25 authoritative South Carolina fields and fails closed: no substitute, mock, random, or synthetic observations were created.

## Planned real-data analysis

The sole weather source is the official NASA POWER Daily Point API (Agroclimatology community), for 1991-01-01–2025-12-31 in LST. The six requested variables are T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, and ALLSKY_SFC_SW_DWN. A CSBACRES-weighted centroid of projected field centroids supplies one deterministic request point. The intended baseline is 1991–2020, recent anomaly period is 2021–2025, and the fixed agricultural warm-season window is April–October.

The offline script implements daily validation, ≥90%-complete monthly aggregation, annual and warm-season summaries, climate normals, anomalies, OLS and robust trends, figures, and exactly two dashboard assets. Thresholds are descriptive and do not alone establish crop injury. NASA POWER is gridded and is not an on-site station or a means to resolve field-to-field weather.

## Acquisition limitation

The 2026-07-29 request at **34.33090814° N, 82.53604245° W** was rejected by the environment's HTTPS proxy (`403 Forbidden` tunnel failure). `output/acquisition_provenance.json` records the exact exception. Consequently, no raw response, analytical tables, figures, successful manifest, or executed completed notebook is claimed.

## Inventory

- `scripts/acquire_assignment_06_power.py`: field validation, location derivation, retry-limited authenticated-source acquisition, validation, and provenance.
- `scripts/run_assignment_06_weather_climate.py`: network-free processing and visualization.
- `scripts/build_assignment_06_notebook.py`: deterministic offline notebook builder.
- `verify_assignment_06.py`: independent, fail-closed integrity verifier.
- `source/`: representative point/distance evidence and source documentation.
- `output/`: failed acquisition provenance only until authentic acquisition succeeds.

## Import and continue locally

First independently compare the external download with the expected checksum:

```bash
sha256sum "$HOME/Downloads/nasa_power_daily_raw.json"
# Expected for the independently obtained file:
# cebf64e8481161fe51c5c98745989e1b304bbf0e8526e931c06ae963114aa1fb
```

Then validate and import its exact bytes:

```bash
python \
  data/assignment-06/scripts/acquire_assignment_06_power.py \
  --import-raw "$HOME/Downloads/nasa_power_daily_raw.json"

python \
  data/assignment-06/scripts/run_assignment_06_weather_climate.py \
  --offline

python data/assignment-06/scripts/build_assignment_06_notebook.py

jupyter nbconvert \
  --execute \
  --to notebook \
  --inplace \
  notebooks/06_weather_climate_trends.ipynb \
  --ExecutePreprocessor.timeout=900

python data/assignment-06/verify_assignment_06.py
```

The import validates UTF-8 JSON, NASA POWER metadata, parameters, units, fill metadata, coordinates, and all 12,784 consistent date keys before writing a successful manifest. Direct-network mode remains available by omitting `--import-raw`. No API key is required. Verification intentionally fails until authentic source artifacts are imported and processed.
