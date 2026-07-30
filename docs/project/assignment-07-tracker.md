# Assignment 7 tracker

- **Status:** Implemented on `agent/assignment-07-integrated-spatial`; clean-checkout validation pending.
- **Scope:** Integrated spatial analysis and zonal statistics for the 25 authoritative South Carolina fields.
- **Inputs:** Assignment 2 field geometry/CDL summaries, Assignment 4 SSURGO field and map-unit summaries, and Assignment 5 authentic Landsat NDVI metadata.
- **Join key:** `field_id`, validated one-to-one for field-level tables.
- **Outputs:** Integrated GeoJSON, field-level zonal-statistics table, crop-group table, soil-map-unit table, integrated PNG/SVG panel, and machine-readable summary.
- **Integrity:** Input SHA-256 checksums recorded; no network requests and no synthetic fallback.
- **Validation:** Independent verifier and GitHub Actions workflow added. The workflow regenerates outputs from a clean checkout and uploads them as an artifact.
- **Merge policy:** Draft PR only; do not merge until CI succeeds and the repository owner reviews the generated outputs.
