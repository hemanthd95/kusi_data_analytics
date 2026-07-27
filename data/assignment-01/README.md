# Assignment 1 — Imported Agricultural Skill Evidence

## Submission

- **Repository:** [hemanthd95/kusi_data_analytics](https://github.com/hemanthd95/kusi_data_analytics)
- **Assignment branch:** [`feature/assignment-01-final`](https://github.com/hemanthd95/kusi_data_analytics/tree/feature/assignment-01-final)
- **Pull request:** [open PR / comparison to `main`](https://github.com/hemanthd95/kusi_data_analytics/compare/main...feature/assignment-01-final)
- **Imported skill run:** [`field-boundaries`](../../skills/field-boundaries/SKILL.md)
- **Skill source:** [borealBytes/ag-skills, `skills-content` branch](https://github.com/borealBytes/ag-skills/tree/skills-content/field-boundaries), imported at commit [`8133719`](https://github.com/borealBytes/ag-skills/commit/8133719196e6f3299585e103deb61c4510472778)
- **Terminal run log:** [`skill_run.log`](output/skill_run.log)
- **Environment report:** [`environment.json`](output/environment.json)
- **Starter output:** [`field_boundaries_summary.json`](output/field_boundaries_summary.json)
- **Rendered run evidence:** [`successful-skill-run.svg`](evidence/successful-skill-run.svg)
- **Generated map:** [`field-boundaries-sample-map.svg`](evidence/field-boundaries-sample-map.svg)

## Imported skills

The agricultural collection is vendored under [`skills/`](../../skills). Its
exact source revision and import details are recorded in
[`skills/UPSTREAM_SOURCE.md`](../../skills/UPSTREAM_SOURCE.md). The pre-existing
[`assignment-setup`](../../skills/assignment-setup/SKILL.md) files were retained;
they were not replaced. Confirmed imported manifests include:

- [`field-boundaries`](../../skills/field-boundaries/SKILL.md)
- [`ssurgo-soil`](../../skills/ssurgo-soil/SKILL.md)
- [`nasa-power-weather`](../../skills/nasa-power-weather/SKILL.md)
- [`cdl-cropland`](../../skills/cdl-cropland/SKILL.md)
- [`interactive-web-map`](../../skills/interactive-web-map/SKILL.md)

## Successful lightweight run

The run loads the two features in the `field-boundaries` skill's included
`sample_2_fields.geojson`, then invokes the imported implementation's
`get_summary` function. It does **not** download, synthesize,
or begin analysis of new Assignment 2 data. The resulting JSON reports two corn
fields totaling 10.113394 acres. The field map is a deterministic, text-based
SVG generated from those same GeoJSON polygon coordinates; the other SVG is a
readable rendering of the saved terminal log.

## Reproduce and verify

Create an isolated environment and install only the packages needed by this
lightweight example:

```bash
python3 -m venv .venv-assignment-01
.venv-assignment-01/bin/pip install geopandas matplotlib shapely
.venv-assignment-01/bin/python data/assignment-01/run_assignment_setup.py \
  | tee data/assignment-01/output/skill_run.log
python3 data/assignment-01/render_evidence.py
python3 data/assignment-01/render_field_map_svg.py
python3 data/assignment-01/verify_assignment_01.py
```

The run script records interpreter, OS, dependency versions, Git state, source
skill, upstream revision, and evidence checks in `environment.json`.

## Supplemental prior evidence

The earlier local `assignment-setup` run remains under
[`supplemental-assignment-setup/`](supplemental-assignment-setup/) for provenance.
It is supplemental only; the primary evidence above is from the genuinely
imported upstream `field-boundaries` skill.

## Checklist

- [x] Agricultural skills imported from the requested upstream branch
- [x] Existing Assignment 1 setup skill retained
- [x] Five named imported skill manifests verified
- [x] Imported skill completed successfully using included sample data
- [x] Terminal log, environment report, starter output, and rendered evidence saved
- [x] Repository and assignment branch/PR links recorded
