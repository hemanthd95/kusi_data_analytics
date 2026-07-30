# Assignment 7 — Integrated Spatial Analysis and Zonal Statistics

## Status

**Complete with committed, reproducible outputs.** Assignment 7 integrates the previously validated products from Assignments 2, 4, and 5. It does not download, invent, interpolate, or substitute new observations.

## Objective

Create one field-level analytical dataset that combines:

- authoritative Assignment 2 field geometry and USDA NASS CDL crop summaries;
- Assignment 4 USDA-NRCS SSURGO field-level soil zonal statistics and map-unit intersections; and
- Assignment 5 authentic Landsat NDVI metadata for the selected demonstration field.

The central join key is `field_id`. All joins are validated as one-to-one at the field-summary level, and the final integrated output retains exactly 25 fields.

## Integrated zonal statistics

For each field, the workflow preserves the 2023 dominant CDL class and confidence, the area-weighted SSURGO available-water-storage value for 0–25 cm (`aws025wta`), dominant soil map unit, soil-map-unit count, and SSURGO coverage. It also assigns a transparent descriptive soil-water class and a combined crop–soil zone label.

Two additional zonal summaries are produced:

1. **Crop-group statistics:** field count, total acres, acreage-weighted soil available-water storage, and mean 2023 dominant-crop percentage by CDL class.
2. **Soil-map-unit statistics:** number of fields intersected, intersection count, total overlap acres, and mean `aws025wta` by SSURGO map unit.

Assignment 5 NDVI is attached only to its authentic selected field. The authentic mean is read from `ndvi_statistics.mean` and is not extrapolated to the other 24 fields.

## Inputs

- `../assignment-02/fields_with_crops.geojson`
- `../assignment-02/field_summary.csv`
- `../assignment-04/output/field_soil_summary.csv`
- `../assignment-04/output/field_ssurgo_intersections.csv`
- `../assignment-05/output/ndvi_summary.json`

The workflow records SHA-256 checksums for all five inputs in `output/assignment_07_summary.json`.

## Committed outputs

- `output/integrated_fields.geojson`
- `output/tables/integrated_field_zonal_statistics.csv`
- `output/tables/crop_group_zonal_statistics.csv`
- `output/tables/soil_mapunit_zonal_statistics.csv`
- `output/visualizations/assignment_07_integrated_spatial_panel.png`
- `output/visualizations/assignment_07_integrated_spatial_panel.svg`
- `output/assignment_07_summary.json`

These seven files are committed for direct inspection. GitHub Actions also regenerates and validates them from a clean checkout and uploads a downloadable workflow artifact.

## Reproduce and verify

From the repository root:

```bash
python -m pip install -r data/assignment-07/requirements.txt
python data/assignment-07/scripts/run_assignment_07_integrated_spatial.py
python data/assignment-07/scripts/correct_assignment_07_ndvi.py
python data/assignment-07/verify_assignment_07.py
python data/assignment-07/verify_assignment_07_ndvi.py
```

## Interpretation limits

- CDL labels are raster-derived dominant classes and may include mixed pixels or classification error.
- SSURGO represents mapped soil components, not direct field measurements.
- The Landsat NDVI evidence covers one selected field and one acquisition date.
- The combined results are descriptive. They do not establish causal relationships among crop class, soil properties, vegetation condition, management, or yield.
