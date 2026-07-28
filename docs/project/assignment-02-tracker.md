# Assignment 02 tracker

- Status: real USDA build complete at 2026-07-28T15:04:25.268559+00:00.
- Boundaries: 25 official CSBID records for STATEFIPS 45; source geometry unchanged except CRS reprojection.
- CDL: validated official county rasters for 2020–2023; direct cache preferred, county-FIPS services next, bounding-box service last; 100 raster zonal extractions.
- Join: 25 matched, 0 unmatched.
- Raster/CSB annual-code disagreements: 6; see the summary JSON for every record.
- Limitations: 30 m pixel-center extraction can differ at boundaries; the CDL service clip covers the combined selected-field bounding box.
