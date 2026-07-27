#!/usr/bin/env python3
"""Run the Assignment 1 setup skill and emit reproducible starter outputs."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENTS = ROOT / "agriculturaldataanalyticsclassassignmentandproject"
OUTPUT = Path(__file__).resolve().parent / "output"
SKILL = ROOT / "skills" / "assignment-setup" / "SKILL.md"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(ASSIGNMENTS.glob("*.pdf"))
    checks = {
        "skill_manifest_present": SKILL.is_file(),
        "assignment_directory_present": ASSIGNMENTS.is_dir(),
        "pdf_count": len(pdfs),
        "pdfs_present": bool(pdfs),
    }
    passed = all(value for key, value in checks.items() if key != "pdf_count")
    environment = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "repository_root": str(ROOT),
        "git_branch": git("branch", "--show-current"),
        "git_commit": git("rev-parse", "HEAD"),
        "skill": "assignment-setup",
        "checks": checks,
        "status": "PASS" if passed else "FAIL",
    }
    (OUTPUT / "environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )

    rows = ["# Supplied PDF inventory", "", "| File | Bytes | SHA-256 |", "| --- | ---: | --- |"]
    for pdf in pdfs:
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        rows.append(f"| {pdf.name} | {pdf.stat().st_size} | `{digest}` |")
    (OUTPUT / "file_inventory.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    print("Assignment 1: setup and skill-run evidence")
    print(f"Skill: assignment-setup ({SKILL.relative_to(ROOT)})")
    print(f"Branch: {environment['git_branch']}")
    print(f"Python: {environment['python']}")
    print(f"Assignment PDFs inspected: {len(pdfs)}")
    print("Outputs: environment.json, file_inventory.md")
    print(f"RESULT: {environment['status']}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
