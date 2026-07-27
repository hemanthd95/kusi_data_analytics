#!/usr/bin/env python3
"""Run the imported field-boundaries skill against its included sample data."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "output"
EVIDENCE = Path(__file__).resolve().parent / "evidence"
SKILL_DIR = ROOT / "skills" / "field-boundaries"
SAMPLE = SKILL_DIR / "examples" / "sample_2_fields.geojson"
UPSTREAM_COMMIT = "8133719196e6f3299585e103deb61c4510472778"
REQUIRED_SKILLS = (
    "field-boundaries",
    "ssurgo-soil",
    "nasa-power-weather",
    "cdl-cropland",
    "interactive-web-map",
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    # Import the vendored implementation itself, not a reimplementation.
    sys.path.insert(0, str(SKILL_DIR / "src"))
    import geopandas as gpd
    import matplotlib
    import shapely
    from field_boundaries import get_summary
    from render_field_map_svg import render

    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    fields = gpd.read_file(SAMPLE)
    summary = get_summary(fields)
    plot_path = render(SAMPLE, EVIDENCE / "field-boundaries-sample-map.svg")

    serializable_summary = {
        "source_sample": str(SAMPLE.relative_to(ROOT)),
        "skill": "field-boundaries",
        "skill_source": "https://github.com/borealBytes/ag-skills/tree/skills-content/field-boundaries",
        "upstream_commit": UPSTREAM_COMMIT,
        "total_fields": int(summary["total_fields"]),
        "total_area_acres": float(summary["total_area_acres"]),
        "average_field_size_acres": float(summary["avg_field_size"]),
        "crops": summary["crops"],
    }
    (OUTPUT / "field_boundaries_summary.json").write_text(
        json.dumps(serializable_summary, indent=2) + "\n", encoding="utf-8"
    )

    checks = {
        "required_skill_manifests_present": {
            name: (ROOT / "skills" / name / "SKILL.md").is_file()
            for name in REQUIRED_SKILLS
        },
        "sample_data_present": SAMPLE.is_file(),
        "sample_feature_count_is_two": len(fields) == 2,
        "summary_generated": (OUTPUT / "field_boundaries_summary.json").is_file(),
        "map_generated": plot_path.is_file() and plot_path.stat().st_size > 0,
    }
    passed = (
        all(checks["required_skill_manifests_present"].values())
        and all(value for key, value in checks.items() if key != "required_skill_manifests_present")
    )
    environment = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            "geopandas": gpd.__version__,
            "matplotlib": matplotlib.__version__,
            "shapely": shapely.__version__,
        },
        "repository_root": str(ROOT),
        "git_branch": git("branch", "--show-current"),
        "git_commit_at_run": git("rev-parse", "HEAD"),
        "skill": "field-boundaries",
        "skill_source": serializable_summary["skill_source"],
        "upstream_commit": UPSTREAM_COMMIT,
        "checks": checks,
        "status": "PASS" if passed else "FAIL",
    }
    (OUTPUT / "environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )

    print("Assignment 1: imported agricultural skill run")
    print(f"Skill: field-boundaries ({SKILL_DIR.relative_to(ROOT)}/SKILL.md)")
    print(f"Source: {serializable_summary['skill_source']}")
    print(f"Upstream commit: {UPSTREAM_COMMIT}")
    print(f"Input: {SAMPLE.relative_to(ROOT)}")
    print(f"Features loaded: {len(fields)}")
    print(f"Total area: {summary['total_area_acres']:.6f} acres")
    print("Verified skills: " + ", ".join(REQUIRED_SKILLS))
    print("Outputs: output/environment.json, output/field_boundaries_summary.json")
    print("Rendered evidence: evidence/field-boundaries-sample-map.svg")
    print(f"RESULT: {environment['status']}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
