# Assignment 03 tracker

- **Branch:** `feature/assignment-03-eda`
- **Source:** `data/assignment-02/field_summary.csv` at `e198d41ba6acf31305a603249361608376c036a0`; SHA-256 `5759d566cc88c0646b9579302a047bca6d29a43e1915a046bab3f0471e1637d8`.
- **Execution date:** 2026-07-28 UTC.
- **Files produced:** executed notebook; Markdown report; four PNG/SVG exploratory visual pairs; two PNG/SVG dashboard visual pairs; profiles, derived metrics, composition and correlation CSVs; JSON provenance/environment; log; verifier; evidence.
- **Data checks:** 25 rows, 25 unique fields, IDs equal CSBIDs, FIPS 45, no duplicates, positive acreage/pixels, bounded confidence, complete annual crop names, and boolean match flags all passed.
- **Cleaning/type normalization:** identifiers and state FIPS loaded as strings; annual match flags normalized to booleans. No observations were deleted. Blank `source_attribute` values were retained as source metadata absence.
- **Outliers:** the 1.5×IQR method flagged 5 acreage and 2 mean-confidence values. All were valid and retained.

## Actual computed findings

- Acreage mean 6.81 acres, median 4.55, range 2.64–19.14.
- Mean four-year dominant confidence averaged 68.10% across fields.
- Acreage/confidence relationship: Spearman ρ 0.147 and Pearson r 0.072 (n=25), a weak observed association.
- Overall raster/CSB match rate 94%; annual rates: 92%, 100%, 96%, and 88% for 2020–2023.
- Transition counts: 8 fields with 0, 13 with 1, and 4 with 2.
- Dashboard selections: crop composition by year and acreage versus classification confidence.
- **Limitations:** selected 25-field, one-county-FIPS sample; four years; 30 m raster and edge effects; dominant-pixel simplification; exploratory/non-causal scope; no soil, yield, or weather variables.
- **Verification:** automated verifier passed after notebook execution.
- **Pull request:** pending publication; update after PR creation.
