# Final Project — Row Crop Intelligence Dashboard

## Status

**Complete locally and ready for independent review before publication.**

This project converts the verified outputs from Assignments 2, 3, 5, 6, 7, and 8 into an interactive, farmer-oriented decision-support dashboard. It integrates field and crop history, exploratory data-quality metrics, SSURGO soil attributes, one authentic Landsat NDVI observation, 1991–2025 NASA POWER climate history, and the relative soil-sustainability scorecard.

No field, yield, current-weather, soil-moisture, pest, nutrient, or economic observation is invented. The assignment brief's 200-field KPI and predicted-bushel examples are treated as examples: the validated repository contains **25 fields totaling 170.3 acres** and no yield observations.

## Farmer decision workflow

The dashboard is organized around the question **“Which field should I inspect first?”** A farmer or farm manager can:

1. Choose a management decision: general review, irrigation monitoring, crop scouting, soil conservation, or rotation planning.
2. Filter by dominant soil type.
3. Select a field from the ranked worklist or interactive field map.
4. Review the evidence used in the ranking.
5. Read a concise suggested follow-up and the “measure before acting” caution.

The rankings prioritize follow-up within this 25-field package. They do not prescribe irrigation rates, pesticide or fertilizer products, application timing, or conservation designs.

## Dashboard sections

- **Decision Center:** five KPI tiles, field-attention map, ranked field worklist, and dynamic advisory.
- **Crop & Vegetation:** four-year crop history, Assignment 3 acreage-confidence relationship, and authentic Assignment 5 NDVI where available.
- **Soil & Conservation:** four sustainability components, relative field ranking, mapped available-water storage, slope, and erosion-history context.
- **Weather & Climate:** 1991–2025 annual temperature and precipitation with 1991–2020 baseline context.
- **Data & Limitations:** source inventory, requirement coverage, and explicit analytical constraints.

## Final Project requirement coverage

| Requirement | Implementation |
|---|---|
| Professional Python dashboard | Bokeh server application with callbacks and linked selections |
| KPI summary tiles | Five tiles recalculated for the active soil/task view |
| Field ID filter | 25 verified field IDs |
| Soil type filter | Dominant SSURGO map-unit symbol |
| Interactive control | Management-task selector plus map/table selection |
| At least five visualizations | Eight visualizations across five sections |
| At least four previous assignments | Six assignments integrated: 2, 3, 5, 6, 7, and 8 |
| Geospatial map | Field polygons ranked by task-specific attention |
| Weather time series | Annual temperature and precipitation, 1991–2025 |
| Soil-health metrics | Water storage, slope resilience, erosion history, rotation diversity |
| Vegetation health | Authentic Landsat NDVI for one field; no extrapolation |
| EDA relationship plot | Field acreage versus mean CDL confidence |
| Dynamic narratives | Deterministic AI-assisted advisory rules tied to selected field and task |
| Main repository documentation | Root `README.md` includes technologies and run instructions |
| AI usage summary | `docs/AI_DOCS.md` |
| Demo evidence | Four committed screenshot views in `screenshots/` |

## Technologies

- Python 3.12+
- Bokeh server for the interactive dashboard
- Pandas and NumPy for integration and ranking
- GeoPandas and Shapely for field geometry
- SQLite for the portable dashboard data layer
- Matplotlib for deterministic screenshot evidence
- GitHub Actions for clean-checkout validation

## Run the dashboard

From the repository root:

```bash
python -m pip install -r data/final-project/requirements.txt
python data/final-project/scripts/build_final_project_data.py
bokeh serve data/final-project/app.py --show
```

Open the local address displayed by Bokeh, normally `http://localhost:5006/app`.

## Rebuild screenshots and verify

```bash
python data/final-project/scripts/render_dashboard_screenshots.py
python data/final-project/verify_final_project.py
```

For an automated server smoke test:

```bash
bokeh serve data/final-project/app.py --port 5010 --address 127.0.0.1 \
  --allow-websocket-origin=127.0.0.1:5010 &
python data/final-project/scripts/smoke_test_dashboard_server.py \
  --url http://127.0.0.1:5010/app
```

## Main artifacts

- `app.py` — interactive dashboard application
- `dashboard_core.py` — independently testable integration and decision logic
- `output/dashboard_data.sqlite` — portable dashboard database
- `output/tables/dashboard_field_metrics.csv` — field-level integrated metrics
- `output/tables/field_management_priorities.csv` — all five task rankings
- `output/dashboard_summary.json` — requirement and provenance summary
- `screenshots/` — four representative dashboard views
- `FINAL_PROJECT_REPORT.md` — detailed design, findings, and limitations
- `verify_final_project.py` — independent verifier

## Scientific and operational limitations

- NASA POWER is historical gridded weather context, not a current field forecast.
- SSURGO attributes are mapped estimates, not live soil-moisture or laboratory measurements.
- Landsat NDVI is available for one field on one historical date and is not copied to other fields.
- CDL dominant crop labels can contain classification and mixed-pixel error.
- No yield data are present; predicted bushels are intentionally omitted.
- Recommendations are screening priorities for field follow-up, not agronomic prescriptions.
