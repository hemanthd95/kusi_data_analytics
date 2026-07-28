# Assignment 04 — Geospatial mapping

This assignment performs a completely offline, reproducible analysis of a genuine USDA-NRCS SSURGO `MapunitPolyExtended` response around 25 authoritative Assignment 2 fields. The source response was acquired externally after Codex's proxy blocked direct acquisition; its committed SHA-256 and successful-request metadata are independently validated before parsing. Offline mode makes zero network requests and refuses missing or modified source material.

## Reproduce

```bash
python data/assignment-04/scripts/run_assignment_04_mapping.py --offline
python data/assignment-04/scripts/build_assignment_04_notebook.py
jupyter nbconvert --execute --to notebook --inplace notebooks/04_geospatial_mapping.ipynb --ExecutePreprocessor.timeout=900
python data/assignment-04/verify_assignment_04.py
```

The pipeline repairs three invalid geometries only in memory, retaining all 25 fields, and works in EPSG:32617. It recreates the 500 m buffer, clips soil polygons, calculates intersections and coverage, and computes area-weighted `aws025wta` without zero-filling missing observations. CSV tables, static PNG/SVG maps, a Leaflet interactive map, provenance, and a machine-readable spatial-quality record are under `output/`.
