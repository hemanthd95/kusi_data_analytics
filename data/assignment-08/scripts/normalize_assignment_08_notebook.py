#!/usr/bin/env python3
"""Normalize non-analytical notebook metadata after execution.

Execution counts and cell outputs are retained. Random/timestamp metadata is
removed so clean-checkout execution can be compared byte-for-byte.
"""
from pathlib import Path
import nbformat

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "notebooks" / "08_soil_health_sustainability.ipynb"

notebook = nbformat.read(PATH, as_version=4)
for index, cell in enumerate(notebook.cells):
    cell["id"] = f"assignment-08-{index:02d}"
    cell.metadata.pop("execution", None)
notebook.metadata.pop("widgets", None)
nbformat.write(notebook, PATH)
print(f"Normalized {PATH.relative_to(ROOT)}")
