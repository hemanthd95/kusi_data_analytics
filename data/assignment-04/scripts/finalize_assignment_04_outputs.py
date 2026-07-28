#!/usr/bin/env python3
"""Finalize generated Assignment 4 visual outputs.

This script is intentionally independent of the mapping pipeline. It:
1. Upscales the dashboard PNG proportionally when its width is below the
   required minimum.
2. Verifies the final-panel and dashboard dimensions.
3. Synchronizes recorded image dimensions in generated JSON summaries.
4. Removes trailing whitespace from generated SVG and HTML files so
   ``git diff --check`` remains clean.

It does not alter authoritative source data or Assignment 2/3 files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


FINAL_PANEL_RELATIVE = Path(
    "data/assignment-04/output/maps/04_final_assignment_panel.png"
)
DASHBOARD_RELATIVE = Path(
    "data/assignment-04/output/dashboard_assets/"
    "dashboard_ssurgo_field_variability_map.png"
)
OUTPUT_RELATIVE = Path("data/assignment-04/output")

FINAL_PANEL_MIN_WIDTH = 2400
FINAL_PANEL_MIN_HEIGHT = 1800
DASHBOARD_MIN_WIDTH = 1800
DASHBOARD_TARGET_WIDTH = 2200

SUMMARY_FILES = (
    "geospatial_summary.json",
    "spatial_quality_summary.json",
)
DASHBOARD_KEYS = (
    "dashboard_ssurgo_field_variability_map",
    "dashboard",
)


def locate_repo(explicit_repo: Path | None) -> Path:
    if explicit_repo is not None:
        repo = explicit_repo.expanduser().resolve()
    else:
        repo = Path.cwd().resolve()

    required = repo / "data" / "assignment-04"
    if not required.is_dir():
        raise FileNotFoundError(
            "Could not locate data/assignment-04. Run this script from the "
            "repository root or pass --repo /path/to/kusi_data_analytics."
        )
    return repo


def image_dimensions(path: Path) -> tuple[int, int]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing generated image: {path}")
    with Image.open(path) as image:
        return int(image.width), int(image.height)


def ensure_dashboard_width(path: Path) -> tuple[int, int, bool]:
    """Upscale the dashboard proportionally when below the target width."""
    with Image.open(path) as source:
        source.load()
        width, height = int(source.width), int(source.height)

        if width >= DASHBOARD_MIN_WIDTH:
            return width, height, False

        target_width = max(DASHBOARD_TARGET_WIDTH, DASHBOARD_MIN_WIDTH)
        target_height = round(height * target_width / width)

        # Preserve transparency when present; otherwise use RGB.
        working = source.copy()
        if working.mode not in {"RGB", "RGBA"}:
            working = working.convert("RGBA" if "A" in working.getbands() else "RGB")

        resized = working.resize(
            (target_width, target_height),
            resample=Image.Resampling.LANCZOS,
        )

        save_kwargs: dict[str, Any] = {"optimize": True}
        dpi = source.info.get("dpi")
        if dpi:
            save_kwargs["dpi"] = dpi

        resized.save(path, format="PNG", **save_kwargs)
        return target_width, target_height, True


def strip_generated_trailing_whitespace(output_root: Path) -> list[Path]:
    changed: list[Path] = []
    for suffix in ("*.svg", "*.html"):
        for path in sorted(output_root.rglob(suffix)):
            original = path.read_text(encoding="utf-8")
            normalized = "\n".join(
                line.rstrip() for line in original.splitlines()
            ) + "\n"
            if normalized != original:
                path.write_text(normalized, encoding="utf-8")
                changed.append(path)
    return changed


def update_dashboard_dimensions_in_object(
    value: Any,
    width: int,
    height: int,
) -> bool:
    """Recursively update recognized dashboard dimension dictionaries."""
    changed = False

    if isinstance(value, dict):
        for key, child in value.items():
            if key in DASHBOARD_KEYS and isinstance(child, dict):
                if child.get("width") != width:
                    child["width"] = width
                    changed = True
                if child.get("height") != height:
                    child["height"] = height
                    changed = True

            if update_dashboard_dimensions_in_object(child, width, height):
                changed = True

    elif isinstance(value, list):
        for child in value:
            if update_dashboard_dimensions_in_object(child, width, height):
                changed = True

    return changed


def update_summary_json_files(
    output_root: Path,
    width: int,
    height: int,
) -> list[Path]:
    changed: list[Path] = []
    for filename in SUMMARY_FILES:
        path = output_root / filename
        if not path.is_file():
            continue

        content = json.loads(path.read_text(encoding="utf-8"))
        if update_dashboard_dimensions_in_object(content, width, height):
            path.write_text(
                json.dumps(content, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            changed.append(path)
    return changed


def verify_dimensions(
    final_panel: Path,
    dashboard: Path,
) -> tuple[tuple[int, int], tuple[int, int]]:
    final_dimensions = image_dimensions(final_panel)
    dashboard_dimensions = image_dimensions(dashboard)

    if final_dimensions[0] < FINAL_PANEL_MIN_WIDTH:
        raise RuntimeError(
            f"Final panel width is {final_dimensions[0]}, below "
            f"{FINAL_PANEL_MIN_WIDTH}."
        )
    if final_dimensions[1] < FINAL_PANEL_MIN_HEIGHT:
        raise RuntimeError(
            f"Final panel height is {final_dimensions[1]}, below "
            f"{FINAL_PANEL_MIN_HEIGHT}."
        )
    if dashboard_dimensions[0] < DASHBOARD_MIN_WIDTH:
        raise RuntimeError(
            f"Dashboard width is {dashboard_dimensions[0]}, below "
            f"{DASHBOARD_MIN_WIDTH}."
        )

    return final_dimensions, dashboard_dimensions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        type=Path,
        help="Path to the kusi_data_analytics repository. Defaults to cwd.",
    )
    args = parser.parse_args()

    repo = locate_repo(args.repo)
    output_root = repo / OUTPUT_RELATIVE
    final_panel = repo / FINAL_PANEL_RELATIVE
    dashboard = repo / DASHBOARD_RELATIVE

    if not output_root.is_dir():
        raise FileNotFoundError(
            "Assignment 4 output directory does not exist. Run the offline "
            "mapping pipeline before this finalizer."
        )

    dashboard_width, dashboard_height, resized = ensure_dashboard_width(dashboard)
    updated_json = update_summary_json_files(
        output_root,
        dashboard_width,
        dashboard_height,
    )
    cleaned_text = strip_generated_trailing_whitespace(output_root)
    final_dimensions, dashboard_dimensions = verify_dimensions(
        final_panel,
        dashboard,
    )

    print(
        "Dashboard action:",
        "resized proportionally" if resized else "already met minimum width",
    )
    print(
        f"Final panel: {final_dimensions[0]} x {final_dimensions[1]} "
        f"(minimum {FINAL_PANEL_MIN_WIDTH} x {FINAL_PANEL_MIN_HEIGHT})"
    )
    print(
        f"Dashboard: {dashboard_dimensions[0]} x {dashboard_dimensions[1]} "
        f"(minimum width {DASHBOARD_MIN_WIDTH})"
    )
    print(f"Updated JSON summaries: {len(updated_json)}")
    for path in updated_json:
        print(f"  {path.relative_to(repo)}")
    print(f"Whitespace-normalized SVG/HTML files: {len(cleaned_text)}")
    for path in cleaned_text:
        print(f"  {path.relative_to(repo)}")
    print("PASS: Assignment 4 generated outputs finalized successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
