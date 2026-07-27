# Assignment 02 real USDA data workflow

The build script is intentionally run by the manually dispatched **Build
Assignment 2 Real USDA Data** GitHub Actions workflow. The Codex network proxy
returned HTTP 403 from the official USDA NASS and GMU hosts, so the preparatory
change does not download or replace any Assignment 2 data.

## Running the workflow

1. Open **Actions** in GitHub.
2. Select **Build Assignment 2 Real USDA Data**.
3. Click **Run workflow**.
4. Select **main**.
5. Run the workflow.
6. Review the download, extraction, verification, and compilation steps.
7. Download the `assignment-02-real-usda-data` artifact if a complete snapshot
   is needed. A successful run also creates or updates
   `feature/assignment-02-real-data-fix` from the latest `main`.

The job downloads the exact official `NationalCSB_2016-2023_rev23.zip` and
caches only that archive between workflow attempts. The builder reuses it only
after verifying that it is a nonempty ZIP containing a geodatabase; corrupt
cache entries are deleted and downloaded again. It then finds the CSB feature
class by schema and deterministically selects 25 valid South Carolina records
from one county.

For 2020–2023, acquisition prefers the official direct county cache, then tries
county-FIPS GET and form-encoded POST requests, and uses the EPSG:5070 bounding-
box service only as the final fallback. Every response must open as a nonempty,
georeferenced USDA Albers GeoTIFF before extraction. HTTP 502 failures and all
other attempts are preserved in provenance, but can never cause a synthetic
substitution. The builder stages publishable products until all 100 zonal
extractions succeed, so any acquisition or validation failure exits nonzero
and leaves the repository outputs untouched.

Source archives, extracted geodatabases, service rasters, caches, virtual
environments, and compiled files are ignored and excluded from the allow-listed
`git add`; transient rasters and compiled files are also removed. The validated
CSB ZIP remains available until job teardown so `actions/cache` can save it.
Metadata, checksums, derived CSV/GeoJSON, map, evidence, scripts, and
documentation remain reviewable.
