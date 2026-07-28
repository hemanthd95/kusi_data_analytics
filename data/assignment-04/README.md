# Assignment 04 — Geospatial mapping

This worktree contains the real-data acquisition stage for Assignment 4. The official
USDA-NRCS Soil Data Access WFS was unreachable from the execution environment after
three bounded attempts, so the workflow stopped as required instead of fabricating soil
polygons or properties. The preserved attempt metadata is in
`source/ssurgo_request_metadata.json`.

## Intended reproduction workflow

```bash
python -m pip install -r data/assignment-04/requirements.txt
python data/assignment-04/scripts/run_assignment_04_mapping.py
python data/assignment-04/scripts/build_assignment_04_notebook.py
jupyter nbconvert --execute --to notebook --inplace notebooks/04_geospatial_mapping.ipynb --ExecutePreprocessor.timeout=900
python data/assignment-04/verify_assignment_04.py
python -m compileall -q data/assignment-04
git diff --check
```

The online pipeline call requires access to the official USDA endpoint. Offline mode
(`--offline`) is accepted only after a genuine response and its checksum have been
preserved; it refuses missing or mismatched content. Notebook creation, verification,
and map generation cannot truthfully complete until acquisition succeeds.
