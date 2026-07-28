#!/usr/bin/env python3
"""Repair Assignment 4 notebook/summary key compatibility.

This utility:
1. Adds stable compatibility aliases to both Assignment 4 summary JSON files.
2. Updates the notebook builder and current notebook to use the canonical
   ``unique_mapunits`` key.
3. Scans notebook code for remaining q["..."] references that are absent from
   the current spatial-quality summary and fails before notebook execution if
   any unresolved key remains.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def find_repo() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("Run this script from inside the kusi_data_analytics repository.")


REPO = find_repo()
A4 = REPO / "data" / "assignment-04"
OUTPUT = A4 / "output"
SUMMARY_PATHS = [
    OUTPUT / "spatial_quality_summary.json",
    OUTPUT / "geospatial_summary.json",
]
BUILDER = A4 / "scripts" / "build_assignment_04_notebook.py"
NOTEBOOK = REPO / "notebooks" / "04_geospatial_mapping.ipynb"

# Canonical output key -> compatibility aliases.
ALIASES = {
    "unique_mapunits": ["unique_map_units"],
    "parsed_polygon_features": ["parsed_feature_count"],
    "clipped_polygon_features": ["clipped_feature_count"],
    "field_geometry_repairs": ["field_repairs"],
    "attribute": ["selected_attribute"],
    "units": ["attribute_units"],
    "average_field_coverage_percent": ["average_coverage_percent"],
    "minimum_field_coverage_percent": ["minimum_coverage_percent"],
    "source_attribute_missing_count": ["attribute_missing_count"],
    "source_attribute_missing_percent": ["attribute_missing_percent"],
}


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add_aliases(data: dict) -> list[str]:
    added: list[str] = []
    for canonical, aliases in ALIASES.items():
        if canonical not in data:
            continue
        for alias in aliases:
            if alias not in data:
                data[alias] = data[canonical]
                added.append(alias)
    return added


def replace_key_reference(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    updated = text.replace("unique_map_units", "unique_mapunits")
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def notebook_code(notebook_path: Path) -> str:
    notebook = load_json(notebook_path)
    chunks: list[str] = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            chunks.append("".join(source) if isinstance(source, list) else str(source))
    return "\n".join(chunks)


def referenced_summary_keys(code: str) -> set[str]:
    patterns = [
        r"""q\[\s*['"]([^'"]+)['"]\s*\]""",
        r"""q\.get\(\s*['"]([^'"]+)['"]""",
    ]
    keys: set[str] = set()
    for pattern in patterns:
        keys.update(re.findall(pattern, code))
    return keys


def main() -> None:
    summary = load_json(SUMMARY_PATHS[0])
    all_added: dict[str, list[str]] = {}

    for path in SUMMARY_PATHS:
        data = load_json(path)
        added = add_aliases(data)
        write_json(path, data)
        all_added[str(path.relative_to(REPO))] = added

    builder_changed = replace_key_reference(BUILDER)
    notebook_changed = replace_key_reference(NOTEBOOK)

    # Reload after changes and verify every direct q[...] / q.get(...) reference.
    summary = load_json(SUMMARY_PATHS[0])
    code_sources = []
    if BUILDER.is_file():
        code_sources.append(BUILDER.read_text(encoding="utf-8"))
    if NOTEBOOK.is_file():
        code_sources.append(notebook_code(NOTEBOOK))

    referenced = referenced_summary_keys("\n".join(code_sources))
    missing = sorted(key for key in referenced if key not in summary)

    print("Assignment 4 notebook compatibility repair complete.")
    for path, added in all_added.items():
        print(f"{path}: aliases added = {added or 'none'}")
    print(f"Notebook builder updated: {builder_changed}")
    print(f"Current notebook updated: {notebook_changed}")
    print(f"Referenced summary keys checked: {len(referenced)}")

    if missing:
        raise RuntimeError(
            "Unresolved summary keys remain before notebook execution: "
            + ", ".join(missing)
        )

    print("PASS: All notebook summary-key references resolve.")


if __name__ == "__main__":
    main()
