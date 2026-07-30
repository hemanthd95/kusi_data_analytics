# Agricultural Data Analytics — Row Crop Intelligence

This repository contains a sequence of reproducible agricultural data assignments culminating in a farmer-oriented **Row Crop Intelligence Dashboard**.

## Final Project

The Final Project integrates verified products from Assignments 2, 3, 5, 6, 7, and 8 into an interactive Bokeh dashboard. A farm manager can filter by Field ID and dominant soil type, choose a management task, review five KPI tiles, inspect eight visualizations, and receive a transparent field-priority narrative with supporting evidence and limitations.

The authentic package contains 25 South Carolina fields totaling approximately 170.3 acres. No yield observations are present, so predicted bushels are intentionally not displayed.

### Technologies

Python, Bokeh, Pandas, NumPy, GeoPandas, Shapely, SQLite, Matplotlib, and GitHub Actions.

### Run locally

```bash
python -m pip install -r data/final-project/requirements.txt
python data/final-project/scripts/build_final_project_data.py
bokeh serve data/final-project/app.py --show
```

The detailed farmer workflow, requirement matrix, artifacts, and verification instructions are in [`data/final-project/README.md`](data/final-project/README.md).

## Data integrity

Generated products identify their source. Authentic observations are not replaced by mock or synthetic data, and unavailable yield, current-weather, live soil-moisture, and laboratory measurements are not fabricated.
