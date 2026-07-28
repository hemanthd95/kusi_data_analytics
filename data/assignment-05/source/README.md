# Assignment 5 authentic Landsat sources

This directory contains authentic USGS Landsat Collection 2 Level-2 data
accessed through Microsoft Planetary Computer.

## Selected product

- Product ID: `LC08_L2SP_018036_20230727_02_T1`
- Platform: `landsat-8`
- Acquisition: `2023-07-27T16:05:59.161620Z`
- Field ID: `451623001001257`
- Context buffer: `300` m

## Files

- `raw/red.tif`: clipped Landsat Red `SR_B4`
- `raw/nir.tif`: clipped Landsat NIR `SR_B5`
- `raw/qa_pixel.tif`: clipped `QA_PIXEL`
- `raw/qa_radsat.tif`: clipped `QA_RADSAT`
- `selected_field.geojson`: authoritative Assignment 2 field
- `selected_scene_metadata.json`: unsigned STAC item metadata
- `source_manifest.json`: source paths, stable URLs, checksums, and provenance

Temporary Planetary Computer access tokens are not stored. No synthetic
fallback was used.
