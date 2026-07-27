#!/usr/bin/env python3
"""Verify the required Assignment 1 imported-skill evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
required = [
    ROOT / "skills" / name / "SKILL.md"
    for name in ("field-boundaries", "ssurgo-soil", "nasa-power-weather", "cdl-cropland", "interactive-web-map")
] + [
    ROOT / "skills" / "UPSTREAM_SOURCE.md",
    HERE / "output" / "skill_run.log",
    HERE / "output" / "environment.json",
    HERE / "output" / "field_boundaries_summary.json",
    HERE / "evidence" / "successful-skill-run.svg",
    HERE / "evidence" / "field-boundaries-sample-map.svg",
]
missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file() or path.stat().st_size == 0]
environment = json.loads((HERE / "output" / "environment.json").read_text())
summary = json.loads((HERE / "output" / "field_boundaries_summary.json").read_text())
assert environment["status"] == "PASS", environment
assert summary["skill"] == "field-boundaries", summary
assert summary["total_fields"] == 2, summary
if missing:
    raise SystemExit("FAIL: missing or empty evidence: " + ", ".join(missing))
print(f"PASS: {len(required)} required skill/evidence files are present and non-empty")
print("PASS: field-boundaries run status and two-feature sample summary verified")
