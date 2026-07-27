# Assignment 02 — First Data Download and Exploration

## Decision and result

The **southeast** course region was selected because it is the closest available region to South Carolina and is most relevant to southeastern row-crop agriculture. The submitted single-state sample contains **25 South Carolina fields (FIPS 45)** and **3,875.13 acres**. Keeping one state avoids accidentally applying the wrong state raster during CDL extraction.

The requested USDA NASS CDL years are **2020, 2021, 2022, and 2023**. Corn, soybeans, cotton, and winter wheat occur in the four-year history; the 2023 map includes corn, soybeans, and cotton. These are real-data products sourced from USDA NASS Crop Sequence Boundaries (CSB) and annual CDL. The CSB source field identifier is retained as `field_id` and is the only join key. The long CDL table has 100 rows (25 fields × 4 years); the GeoJSON has one feature per field and wide `crop_2020` through `crop_2023` attributes.

## Quality and merge audit

| Check | Result |
|---|---:|
| Boundary features | 25 |
| Valid polygon features | 25 |
| CRS | EPSG:4326 |
| Total acreage | 3,875.13 |
| Duplicate boundary `field_id` | 0 |
| Expected merged features | 25 |
| Actual merged features | 25 |
| Fields with CDL matches | 25 |
| Fields without CDL matches | 0 |

The crop types by year are: 2020 and 2021—corn, cotton, soybeans, and winter wheat; 2022—corn, cotton, and soybeans; 2023—corn, cotton, and soybeans. A major visual pattern is the intermingling of corn and soybean fields, with cotton recurring throughout the sample. Winter wheat appears earlier in some rotations but is not dominant in 2023. The surprisingly diverse four-year sequences suggest that a simple corn–soy rotation does not describe every southeastern field. Remaining questions include how double crops influence the dominant class, whether confidence differs near boundaries, and how results change under an all-touched pixel rule.

## Provenance and method

* **Boundaries:** USDA NASS, *Crop Sequence Boundaries 2022*, accessed 2026-07-27: <https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/>. The installed `field-boundaries` skill informed selection and output conventions. The exact selected coordinates and IDs are preserved by `scripts/download_and_process.py`.
* **Crop history:** USDA NASS, *Cropland Data Layer*, South Carolina FIPS **45**, years 2020–2023, accessed 2026-07-27. State raster URL pattern: `https://nassgeodata.gmu.edu/nass_data_cache/byfips/CDL_{year}_45.tif`.
* **Processing:** Following the installed `cdl-cropland` skill, boundaries are interpreted in EPSG:4326, projected to each state raster CRS, raster cells are counted by category within each polygon, and the most frequent code and its percent are recorded. Large source TIFFs are intentionally untracked. The map follows the installed `interactive-web-map` skill and colors by dominant 2023 crop.
* **Download record:** URLs, access date, state FIPS, years, counts, merge audit, and method also appear in `output/assignment_02_summary.json` and `output/skill_run.log`.

## Reproduce

```bash
uv venv data/assignment-02/.venv --python 3.12
uv pip install --python data/assignment-02/.venv/bin/python -r data/assignment-02/requirements.txt
data/assignment-02/.venv/bin/python data/assignment-02/scripts/download_and_process.py
python3 data/assignment-02/verify_assignment_02.py
python3 -m compileall -q data/assignment-02
git diff --check
```

Python and resolved package versions are in `output/environment.json`. Downloaded state TIFFs, if retained for a new run, belong in the ignored `rasters/` directory and must not be committed.

## Submitted files

| File | Description |
|---|---|
| `fields_EPSG4326.geojson` | 25 boundaries with stable IDs, acres, state, region, initial crop label, and provenance. |
| `cdl_EPSG4326.csv` | Long-format 100-row annual dominant CDL result. |
| `fields_with_crops.geojson` | One feature per field with four wide crop attributes. |
| `field_summary.csv` | Geometry-free wide field summary. |
| `my_fields_map.html` | Standalone Leaflet document with all polygons, legend, pan/zoom, and crop-history popups (base tiles need a connection). |
| `evidence/my_fields_map_preview.svg` | Text-based preview generated from the actual merged polygons and 2023 categories. |
| `evidence/terminal_evidence.svg` | Text-based rendering of saved run facts. |
| `scripts/download_and_process.py` | Exact deterministic production script. |
| `verify_assignment_02.py` | Automated submission verifier. |
| `requirements.txt` | Reproducible direct dependencies. |
| `output/environment.json` | Python/platform and complete resolved dependency versions. |
| `output/skill_run.log` | Preserved human-readable run evidence. |
| `output/assignment_02_summary.json` | Machine-readable provenance, counts, crops, and merge audit. |
