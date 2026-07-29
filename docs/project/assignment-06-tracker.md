# Assignment 6 tracker

- **Status:** Incomplete; fail-closed authentic-data workflow implemented.
- **Fields:** 25 Assignment 2 geometries; inputs unchanged.
- **Request point:** 34.33090814° N, 82.53604245° W, deterministic acreage-weighted centroid.
- **Source:** Official NASA POWER Daily Point API, AG/LST, 1991–2025, six required variables.
- **Blocker:** Environment HTTPS proxy returned a 403 tunnel failure on 2026-07-29.
- **Integrity:** No raw response, synthetic fallback, analytical outputs, successful notebook, or completion claim was created.
- **Continuation:** Run the five reproduction commands in `data/assignment-06/README.md` where the official endpoint is reachable.
- **Local import:** `acquire_assignment_06_power.py --import-raw /absolute/path/to/nasa_power_daily_raw.json` now validates and preserves exact authentic bytes, with the original proxy failure retained in acquisition history after success.
