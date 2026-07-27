# Assignment execution status

## Status: PDFs extracted; external source data still blocked

All machine-readable PDF text has been exported under `extracted_text/`. The
image-only PDFs can also be unpacked losslessly into local page JPEGs under
`.generated/extracted_images/`, making every supplied document readable without
adding generated binary files to Git.
The assignment analyses have **not** been fabricated: the repositories and real
datasets referenced by the requirements remain unavailable.

The preflight run on 2026-07-27 found:

1. Ubuntu package repositories returned HTTP 403 through the environment proxy,
   so `apt-get update` failed and `poppler-utils` could not be installed.
2. `pdftotext` is not installed (`command not found`, exit 127), so a checked-in,
   dependency-free extractor is used for the supplied Skia PDFs.
3. Both requested GitHub clones failed because the HTTPS CONNECT tunnel returned
   HTTP 403. No GitHub credentials were available in the environment.
4. The original assignment directory contained only PDF files; the datasets and
   skill repository content referenced by those PDFs were not present locally.

## Reproduce the prerequisite audit

Run:

```bash
./agriculturaldataanalyticsclassassignmentandproject/preflight.sh
```

The script writes `preflight.log` beside the PDFs and exits nonzero if any
prerequisite is unavailable. The log is intentionally ignored because it
contains a timestamp and environment-specific diagnostics.

## Required remediation

Before rerunning the assignment:

- permit the environment proxy to reach Ubuntu package repositories and
  `github.com`, or preinstall Poppler and place checkouts of the exact requested
  branches in `.external/`;
- if the repositories are private, provide a GitHub token with read access; or
- copy all required repositories and datasets directly into
  `agriculturaldataanalyticsclassassignmentandproject/`.

PDF extraction can be regenerated now with `./extract_all.sh`. Once the external
data checks report `READY`, analysis execution, output export, and rubric-by-
rubric verification can proceed without inventing missing inputs.
