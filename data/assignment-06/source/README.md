# Source provenance

The two immutable authoritative inputs are `data/assignment-02/fields_EPSG4326.geojson` and `field_summary.csv`. Their SHA-256 checksums are recorded by a successful acquisition manifest. All 25 geometries are projected to EPSG:32617, their centroids are weighted by positive `CSBACRES`, and the result is returned to EPSG:4326. One point avoids redundant requests for this compact cluster; NASA POWER is a gridded product and does not resolve field-to-field meteorology.

The intended unauthenticated (no API key) request uses the official NASA POWER daily point endpoint, `community=AG`, `format=JSON`, `time-standard=LST`, dates 19910101–20251231, and exactly six documented parameters. Successful raw bytes would be preserved without reformatting and checksummed. The environment proxy blocked acquisition on 2026-07-29, so no raw file or successful manifest exists. There is no synthetic fallback.

Generated location files describe the requested point and each field-centroid distance. `../output/acquisition_provenance.json` is the authoritative failure record.

## External raw-response import

When direct NASA access is unavailable, an authentic response downloaded elsewhere can be imported without reformatting:

```bash
python \
  data/assignment-06/scripts/acquire_assignment_06_power.py \
  --import-raw "$HOME/Downloads/nasa_power_daily_raw.json"
```

The importer requires an absolute path and validates UTF-8 JSON, NASA POWER header/geometry/parameter metadata, units, definitions, fill-value metadata, six mutually consistent parameter date indexes, exactly 12,784 unique dates, and plausible returned grid coordinates. It records external download/local import status, preserves earlier acquisition failures in `acquisition_history`, hashes and copies the exact bytes, and never synthesizes observations. Independently compare the local file checksum to `cebf64e8481161fe51c5c98745989e1b304bbf0e8526e931c06ae963114aa1fb`; the validator intentionally does not hard-code that single checksum as an acceptance condition.
