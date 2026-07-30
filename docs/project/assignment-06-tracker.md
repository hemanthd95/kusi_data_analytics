# Assignment 6 tracker

- **Status:** Complete.
- **Fields:** 25 authoritative Assignment 2 geometries; inputs unchanged and checksummed.
- **Request point:** 34.33090814° N, 82.53604245° W, deterministic acreage-weighted centroid.
- **Source:** Official NASA POWER Daily Point API, Agroclimatology/LST, 1991–2025, six required variables.
- **Acquisition:** Authentic response imported through the validated external-file pathway after the original execution environment blocked direct HTTPS access.
- **Integrity:** Raw-response checksum, request metadata, returned-grid metadata, authoritative-input checksums, and acquisition history are preserved. No synthetic fallback was used.
- **Outputs:** 12,784 daily rows, 420 monthly rows, 35 annual rows, warm-season summaries, 1991–2020 normals, 2021–2025 anomalies, trend statistics, quality checks, six SVG figures, reproducible PNG/dashboard assets, and an executed notebook.
- **Verification:** Independent verifier checks source integrity, analytical consistency, notebook execution, committed figures, and generated image dimensions. GitHub Actions regenerates build products from a clean checkout.
