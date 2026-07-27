# Assignment 02 real USDA data workflow

The build script is intentionally run by the manually dispatched **Build
Assignment 2 Real USDA Data** GitHub Actions workflow. The Codex network proxy
returned HTTP 403 from the official USDA NASS and GMU hosts, so the preparatory
change does not download or replace any Assignment 2 data.

## Running the workflow

1. Open **Actions** in GitHub and select **Build Assignment 2 Real USDA Data**.
2. Choose **Run workflow** from `feature/assignment-02-actions-runner`.
3. Review the download, extraction, verification, and compilation steps.
4. Download the `assignment-02-real-usda-data` artifact if a complete snapshot
   is needed. A successful run also creates or updates
   `feature/assignment-02-real-data-fix` from the latest `main`.

The job downloads the exact official `NationalCSB_2016-2023_rev23.zip`, finds
the CSB feature class by schema, deterministically selects 25 valid South
Carolina records, and requests a bounded CDL service raster for each of
2020–2023. It stages publishable products until every official request and all
100 zonal extractions succeed. Any HTTP or validation failure exits nonzero and
leaves the repository outputs untouched.

Source archives, extracted geodatabases, service rasters, caches, virtual
environments, and compiled files are ignored and explicitly removed before
the allow-listed `git add`. Metadata, checksums, derived CSV/GeoJSON, map,
evidence, scripts, and documentation remain reviewable.
