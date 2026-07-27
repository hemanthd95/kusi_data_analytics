# Assignment 1 — Setup and Skill-Run Evidence

## Submission

- **Repository:** this repository (`kusi_data_analytics`)
- **Assignment branch:** `work`
- **Skill:** [`assignment-setup`](../../skills/assignment-setup/SKILL.md)
- **Run evidence:** [`successful-skill-run.svg`](evidence/successful-skill-run.svg)
- **Environment report:** [`environment.json`](output/environment.json)
- **Starter output:** [`file_inventory.md`](output/file_inventory.md)

## Required setup references

- Template branch: <https://github.com/SuperiorByteWorks-LLC/agent-project/tree/feat/agri-skills-for-agent-project>
- Skills source: <https://github.com/borealBytes/ag-skills/tree/skills-content>

## Reproduce

```bash
python3 data/assignment-01/run_assignment_setup.py \
  | tee data/assignment-01/output/skill_run.log
python3 data/assignment-01/render_evidence.py
```

## What the generated files are

`environment.json` records the interpreter, operating system, Git revision,
selected skill, checks, and final run status. `file_inventory.md` is a starter
provenance artifact: it identifies every supplied assignment PDF by filename,
byte size, and SHA-256 checksum. The SVG is a screenshot-equivalent rendering
of the saved terminal log; it is generated from the log rather than hand-edited.

## Provenance note

The requested upstream `ag-skills` Git branch was not reachable through this
environment's proxy. The checked-in local setup skill therefore demonstrates a
successful, reproducible class-style skill run without pretending that the
external skills were imported. Replace or supplement it with the upstream skill
run when repository access is restored.

## Checklist

- [x] Assignment branch identified
- [x] Environment evidence generated
- [x] Skill executed successfully
- [x] Starter outputs inspected and explained
- [x] Run evidence image committed
- [x] Required template and skill-source links recorded

The repository has no configured Git remote, so a public branch URL cannot be
derived locally. The branch name and exact revision are captured in the
environment report for the repository owner to link after pushing.
