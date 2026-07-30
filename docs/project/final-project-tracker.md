# Final Project tracker

## Objective

Build and independently verify a professional Row Crop Intelligence Dashboard that integrates at least four prior assignments and provides farmer-friendly, actionable intelligence.

## Completed locally before publication

- [x] Extracted and audited the complete Final Project brief.
- [x] Integrated Assignments 2, 3, 5, 6, 7, and 8.
- [x] Preserved the authentic 25-field scope; did not generate a fictitious 200-field package.
- [x] Built five dashboard sections and five KPI tiles.
- [x] Added Field ID, soil type, and management-task controls.
- [x] Added eight visualizations with a consistent visual theme.
- [x] Added five transparent field-priority workflows.
- [x] Added evidence-linked dynamic advisories and “measure before acting” cautions.
- [x] Omitted unsupported yield predictions.
- [x] Built CSV, JSON, and SQLite dashboard products.
- [x] Created four screenshot demo views.
- [x] Added main README, AI usage summary, report, and reflection.
- [x] Added independent verifier and Bokeh server smoke test.
- [x] Published the validated source and generated artifacts to `feature/final-project-dashboard`.
- [x] Confirmed clean-checkout analysis, deterministic regeneration, live-server testing, and committed artifact inventory in GitHub Actions.
- [x] Reconciled the committed numerical outputs and SQLite file with the clean Python 3.12 runner.
- [x] Normalized the two climate-trend outputs to 12 decimal places so different CPU/BLAS implementations cannot toggle committed artifacts.
- [x] Opened PR #20 as a narrowly scoped reproducibility correction; no automatic merge requested.

## Final review gate

The farmer-facing analysis, rankings, advisories, and screenshots are unchanged. The corrective branch contains the normalized generated artifacts, and its final normal-commit workflow run must pass without producing another artifact correction before PR #20 is ready for merge review.
