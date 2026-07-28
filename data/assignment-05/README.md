# Assignment 05 — Landsat NDVI and crop greenness analysis

## Status

**Complete and independently verifiable.**

This assignment uses authentic USGS Landsat Collection 2 Level-2 imagery
accessed through Microsoft Planetary Computer. No synthetic, generated,
mock, or substituted imagery was used.

## Study field

- Field ID: `451623001001257`
- Validated area: `19.141194` acres
- 2023 CDL label: `Other Hay/Non Alfalfa`
- Selection rule: largest validated Assignment 2 field, with `field_id`
  as the tie-breaker

## Landsat scene

- Product ID: `LC08_L2SP_018036_20230727_02_T1`
- Platform: `landsat-8`
- Acquisition date: `2023-07-27`
- Scene cloud cover: `1.35%`
- Collection: `landsat-c2-l2`
- Source provider: `Microsoft Planetary Computer`
- Resolution: `30 m`

The acquisition workflow evaluates a 300 m field-context buffer and ranks
authentic Landsat 8/9 candidates using valid AOI percentage, AOI cloud and
shadow percentages, scene cloud cover, proximity to July 15, and product ID.

## Processing

Surface reflectance was calculated using the scale
`2.75e-05` and offset
`-0.2` recorded in the selected STAC
raster metadata and validated against the official Landsat Collection 2
values.

Invalid pixels include QA_PIXEL bits 0–5, every nonzero QA_RADSAT pixel,
source fill, nodata, nonfinite or negative reflectance, near-zero NDVI
denominators, and pixels outside the field.

## Results

- Valid field pixels: `87`
- Valid-pixel percentage: `100.00%`
- NDVI minimum: `0.5935`
- NDVI median: `0.7700`
- NDVI mean: `0.7622`
- NDVI maximum: `0.8612`
- NDVI standard deviation: `0.0432`
- Descriptive result: `high greenness`

The result is a descriptive single-date greenness assessment. It does not,
by itself, diagnose crop health, yield, management quality, or a cause of
plant stress.

## Reproduction

```bash
source ~/.venvs/kusi-assignment5/bin/activate

python data/assignment-05/scripts/acquire_assignment_05_landsat.py
python data/assignment-05/scripts/run_assignment_05_ndvi.py --offline
python data/assignment-05/scripts/build_assignment_05_notebook.py

jupyter nbconvert \
  --execute \
  --to notebook \
  --inplace \
  notebooks/05_ndvi_crop_health.ipynb \
  --ExecutePreprocessor.timeout=900

python data/assignment-05/verify_assignment_05.py
```

## Main outputs

- `source/source_manifest.json`
- `output/ndvi_summary.json`
- `output/rasters/selected_field_red_reflectance.tif`
- `output/rasters/selected_field_nir_reflectance.tif`
- `output/rasters/selected_field_ndvi.tif`
- `output/visualizations/04_assignment_05_final_panel.png`
- `../../notebooks/05_ndvi_crop_health.ipynb`
