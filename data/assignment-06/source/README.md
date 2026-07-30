# Source provenance

The immutable authoritative inputs are `data/assignment-02/fields_EPSG4326.geojson` and `data/assignment-02/field_summary.csv`. Their SHA-256 checksums are recorded in `source_manifest.json`. All 25 geometries are projected to EPSG:32617, their centroids are weighted by positive `CSBACRES`, and the result is transformed back to EPSG:4326. One point avoids redundant requests for this compact cluster; NASA POWER is gridded and does not resolve field-to-field meteorology.

The completed request used the official NASA POWER Daily Point endpoint with `community=AG`, `format=JSON`, `time-standard=LST`, dates 19910101–20251231, and exactly six documented parameters. The authentic raw response is preserved without reformatting in `nasa_power_daily_raw.json` and its SHA-256 checksum is recorded in `source_manifest.json`.

The direct request from the original execution environment was blocked by an HTTPS proxy on 2026-07-29. An authentic response downloaded externally was subsequently imported through the validation pathway. `../output/acquisition_provenance.json` records the successful import and retains the earlier failed request in `acquisition_history`. No synthetic fallback was used.

## Source artifacts

- `nasa_power_daily_raw.json`: exact authentic NASA POWER response bytes.
- `source_manifest.json`: source identity, request, checksums, authoritative-input hashes, and no-synthetic-fallback declaration.
- `nasa_power_request.json`: normalized request specification.
- `nasa_power_response_metadata.json`: returned parameter definitions, units, fill values, and grid coordinates.
- `representative_weather_point.geojson`: deterministic field-cluster request point.
- `field_to_weather_point_distances.csv`: distance from each field centroid to the analysis point.
- `field_location_summary.json`: cluster extent and distance summary.

## Re-importing an authentic response

```bash
python \
  data/assignment-06/scripts/acquire_assignment_06_power.py \
  --import-raw /absolute/path/to/nasa_power_daily_raw.json
```

The importer validates UTF-8 JSON, NASA POWER header, geometry, parameter metadata, units, definitions, fill-value metadata, six mutually consistent parameter date indexes, exactly 12,784 unique dates, and plausible returned grid coordinates before writing a successful manifest. It preserves the exact bytes and never synthesizes observations.
