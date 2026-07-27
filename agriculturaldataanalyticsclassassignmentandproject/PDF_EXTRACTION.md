# PDF extraction artifacts

## Reproduce

```bash
./agriculturaldataanalyticsclassassignmentandproject/extract_all.sh
```

No package download is required. `tools/extract_pdfs.py` reads the FlateDecode
content streams and embedded ToUnicode maps used by the supplied Skia PDFs.
`tools/extract_pdf_images.py` losslessly exports DCT/JPEG objects from PDFs whose
pages are scans rather than text.

## Results

Ten UTF-8 files are in `extracted_text/`. Six text-native documents contain
usable extracted text. Four image-oriented documents have little or no text
layer. Their 16 readable page images are generated locally under
`.generated/extracted_images/` and intentionally excluded from Git because
GitHub's branch-update workflow used for this repository rejects binary diffs:

| Document | Representation |
| --- | --- |
| Assignments 1-3 Reference Guide | UTF-8 text |
| Assignments 4-5 Reference Guide | UTF-8 text |
| Final Project dashboard assignment | UTF-8 text |
| Assignment 2 instructions | UTF-8 text |
| Assignment 3 instructions | UTF-8 text |
| Assignment 8 instructions | UTF-8 text |
| Assignment 4 instructions | 3 generated JPEG page images |
| Assignment 5 instructions | 4 generated JPEG page images |
| Assignment 6 instructions | 4 generated JPEG page images |
| Assignment 7 instructions | 5 generated JPEG page images |

Only source PDFs that were already present in the repository and text-based
artifacts are tracked. Rerunning `extract_all.sh` recreates the JPEGs when they
are needed for local review without adding binary files to a pull request.

## Input-to-requirement map

| Assignment | Required input(s) identified in the documents | Expected principal output |
| --- | --- | --- |
| 1 | Template branch and imported `ag-skills` | Setup/skill-run evidence and screenshots |
| 2 | Real boundaries, CDL for 4+ years, soil and weather data | Provenance bundle, joined field data, interactive map |
| 3 | Assignment 2 `field_summary.csv` | EDA report, three visuals, two dashboard assets |
| 4 | Real field boundary and real SSURGO polygons | Attribute choropleth, buffer evidence, final map/table panel |
| 5 | Real red and NIR imagery | Single-band image, NDVI image, inline Markdown walkthrough |
| 6 | Historical weather for field locations | Seasonal/anomaly analysis and dashboard time series |
| 7 | Field, soil and/or NDVI spatial layers | Integrated spatial/zonal-statistics analysis |
| 8 | SSURGO OM, pH, CEC, K-factor/slope, depth and drainage | Soil scores, carbon/erosion metrics, two visuals |
| 9 | Outputs from at least four prior assignments | Interactive dashboard with KPIs, filters, 5 visuals and dynamic advice |

The two Git branches and real datasets are inputs, not optional dependencies.
Until they are accessible, generated numeric analyses would be synthetic and
would violate the documents' real-data rule.
