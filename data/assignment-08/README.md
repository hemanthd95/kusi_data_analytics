# Assignment 8 — Soil Health and Sustainability Metrics Assessment

## Status

**Complete and independently verifiable.** This assignment uses the committed USDA-NRCS SSURGO field intersections from Assignment 4 and four-year USDA NASS CDL crop histories from Assignment 2. No synthetic or substituted soil observations are used.

## Requirement coverage

The course assignment requires a soil-health analysis using NRCS data, visualizations of soil variability, at least two sustainability metrics, and a dashboard soil-health section containing one or two visualizations.

This submission provides:

- 25-field soil-health and sustainability scorecard;
- four sustainability components: near-surface available-water storage, slope resilience, mapped-eroded-area history, and crop-rotation diversity;
- two analytical visualizations showing field variability and sustainability tradeoffs;
- exactly two committed dashboard visualizations;
- an executed notebook, report, evidence summary, provenance checksums, and independent verifier.

## Scientific scope

The package does not contain laboratory pH, organic matter, soil carbon, biological activity, aggregate stability, infiltration, or direct field soil-moisture observations. The workflow does not fabricate them. The composite score is an equal-weight, relative decision-support index within this 25-field dataset and is **not an official NRCS soil-health rating**.

## Reproduce and verify

```bash
python -m pip install -r data/assignment-08/requirements.txt
python data/assignment-08/scripts/run_assignment_08_soil_health.py
python data/assignment-08/scripts/build_assignment_08_notebook.py
jupyter nbconvert --execute --to notebook --inplace notebooks/08_soil_health_sustainability.ipynb --ExecutePreprocessor.timeout=900
python data/assignment-08/scripts/normalize_assignment_08_notebook.py
python data/assignment-08/verify_assignment_08.py
```

## Main outputs

- `output/tables/field_soil_health_scorecard.csv`
- `output/tables/sustainability_metric_summary.csv`
- `output/tables/soil_mapunit_sustainability_summary.csv`
- `output/visualizations/01_field_soil_health_scorecard.png`
- `output/visualizations/02_sustainability_tradeoff.png`
- `output/dashboard_assets/dashboard_soil_health_scorecard.png`
- `output/dashboard_assets/dashboard_sustainability_tradeoff.png`
- `output/soil_health_summary.json`
- `../../notebooks/08_soil_health_sustainability.ipynb`

## Provenance fingerprint scope

The summary stores canonical SHA-256 fingerprints of the authoritative columns consumed by Assignment 8. Unrelated columns added to upstream tables do not change the fingerprint, while any analyzed value change does.
