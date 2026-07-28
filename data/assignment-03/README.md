# Assignment 03 — Exploratory data analysis

This directory is the reproducible EDA submission for the 25 real USDA-derived row-crop fields finalized in Assignment 2. The sole authoritative analysis table is `data/assignment-02/field_summary.csv` (SHA-256 `5759d566cc88c0646b9579302a047bca6d29a43e1915a046bab3f0471e1637d8`, source Git commit `e198d41ba6acf31305a603249361608376c036a0`). Supporting Assignment 2 provenance is read but no field data is replaced.

## Reproduce

Run from the repository root:

```bash
python -m pip install -r data/assignment-03/requirements.txt
python data/assignment-03/scripts/run_assignment_03_eda.py
python data/assignment-03/scripts/build_assignment_03_notebook.py
jupyter nbconvert --execute --to notebook --inplace notebooks/03_field_eda.ipynb --ExecutePreprocessor.timeout=600
python data/assignment-03/verify_assignment_03.py
python -m compileall -q data/assignment-03
git diff --check
```

## Inventory

- `EDA_REPORT.md`: interpreted professional report with four inline visuals.
- `scripts/`: reusable validation, derivation, plotting, and notebook-building code.
- `output/`: data-quality profiles, derived metrics, crop composition, correlations, provenance, environment, and run log.
- `output/visualizations/`: four exploratory figures in 300-DPI PNG and SVG.
- `output/dashboard_assets/`: `dashboard_crop_composition.*` and `dashboard_field_confidence.*`, with PNGs at least 1,800 pixels wide.
- `evidence/`: human-reviewable pass artifact and linked evidence summary.
- `../../notebooks/03_field_eda.ipynb`: executed notebook with inline output.

## Limitations

These 25 fields come from one selected South Carolina county FIPS and cover only 2020–2023. CDL uses 30 m pixels; dominant-class summaries suppress within-field variation and field edges may affect small polygons. Results are exploratory, not causal. Soil, yield, and weather variables are absent.
