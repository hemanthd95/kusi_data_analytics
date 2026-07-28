#!/usr/bin/env python3
"""Independent integrity verifier for Assignment 5."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
A5 = ROOT / "data/assignment-05"

SUCCESS_MESSAGE = (
    "SUCCESS: Assignment 5 real-data NDVI workflow complete"
)

PASS_MESSAGE = (
    "PASS: Assignment 5 verification succeeded "
    "(all checks passed)."
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_obj:
        for block in iter(
            lambda: file_obj.read(1 << 20),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(
            f"Required JSON is missing: {path.relative_to(ROOT)}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def verify_notebook(path: Path) -> tuple[int, int]:
    notebook = load_json(path)

    code_cells = [
        cell
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]

    if not code_cells:
        raise RuntimeError(
            "Notebook contains no code cells."
        )

    executed = 0
    errors = []

    for index, cell in enumerate(
        notebook.get("cells", [])
    ):
        if cell.get("cell_type") == "code":
            if cell.get("execution_count") is not None:
                executed += 1

        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                errors.append(
                    {
                        "cell": index,
                        "error": output.get("ename"),
                        "message": output.get("evalue"),
                    }
                )

    if executed != len(code_cells):
        raise RuntimeError(
            "Not every notebook code cell was executed."
        )

    if errors:
        raise RuntimeError(
            f"Notebook contains execution errors: {errors}"
        )

    return len(code_cells), executed


def main() -> int:
    try:
        required = [
            A5 / "source/source_manifest.json",
            A5 / "source/selected_scene_metadata.json",
            A5 / "source/selected_field.geojson",
            A5 / "source/raw/red.tif",
            A5 / "source/raw/nir.tif",
            A5 / "source/raw/qa_pixel.tif",
            A5 / "source/raw/qa_radsat.tif",
            A5 / "output/acquisition_provenance.json",
            A5 / "output/ndvi_summary.json",
            A5 / "output/skill_run.log",
            A5 / "output/rasters/selected_field_red_reflectance.tif",
            A5 / "output/rasters/selected_field_nir_reflectance.tif",
            A5 / "output/rasters/selected_field_qa_pixel.tif",
            A5 / "output/rasters/selected_field_qa_radsat.tif",
            A5 / "output/rasters/selected_field_ndvi.tif",
            A5 / "output/visualizations/01_selected_field_red_reflectance.png",
            A5 / "output/visualizations/02_selected_field_nir_reflectance.png",
            A5 / "output/visualizations/03_selected_field_ndvi.png",
            A5 / "output/visualizations/04_assignment_05_final_panel.png",
            A5 / "output/dashboard_assets/dashboard_selected_field_ndvi.png",
            A5 / "output/tables/ndvi_statistics.csv",
            A5 / "README.md",
            A5 / "NDVI_WALKTHROUGH.md",
            A5 / "evidence/assignment_05_evidence_summary.md",
            ROOT / "docs/project/assignment-05-tracker.md",
            ROOT / "notebooks/05_ndvi_crop_health.ipynb",
        ]

        missing = [
            path.relative_to(ROOT)
            for path in required
            if not path.is_file()
        ]

        if missing:
            raise RuntimeError(
                f"Required artifacts are missing: {missing}"
            )

        manifest = load_json(
            A5 / "source/source_manifest.json"
        )

        provenance = load_json(
            A5 / "output/acquisition_provenance.json"
        )

        summary = load_json(
            A5 / "output/ndvi_summary.json"
        )

        if manifest.get("status") != "acquired":
            raise RuntimeError(
                "Source manifest is not marked acquired."
            )

        if provenance.get("status") != "acquired":
            raise RuntimeError(
                "Acquisition provenance is not marked acquired."
            )

        if summary.get("status") != "complete":
            raise RuntimeError(
                "NDVI summary is not marked complete."
            )

        for record_name, record in (
            ("manifest", manifest),
            ("provenance", provenance),
            ("summary", summary),
        ):
            if (
                record.get("no_synthetic_fallback_used")
                is not True
            ):
                raise RuntimeError(
                    f"{record_name} does not attest "
                    "real-data-only processing."
                )

        product_id = manifest.get("product_id")

        if not product_id:
            raise RuntimeError(
                "Source manifest lacks a product ID."
            )

        if summary.get("product_id") != product_id:
            raise RuntimeError(
                "Summary product ID disagrees with manifest."
            )

        if (
            provenance.get("selected_product_id")
            != product_id
        ):
            raise RuntimeError(
                "Acquisition provenance product ID "
                "disagrees with manifest."
            )

        if manifest.get("platform") not in {
            "landsat-8",
            "landsat-9",
        }:
            raise RuntimeError(
                "Selected platform is not Landsat 8 or 9."
            )

        if (
            manifest.get("provider")
            != "Microsoft Planetary Computer"
        ):
            raise RuntimeError(
                "Unexpected acquisition provider."
            )

        required_assets = {
            "red",
            "nir",
            "qa_pixel",
            "qa_radsat",
        }

        assets = manifest.get("assets", {})

        if set(assets) != required_assets:
            raise RuntimeError(
                "Manifest asset inventory is incomplete."
            )

        for name, record in assets.items():
            path = ROOT / record["path"]

            if not path.is_file():
                raise RuntimeError(
                    f"Source asset is missing: {name}"
                )

            if sha256(path) != record["sha256"]:
                raise RuntimeError(
                    f"Source checksum mismatch: {name}"
                )

            if "sig=" in record.get(
                "source_url",
                "",
            ).lower():
                raise RuntimeError(
                    f"Temporary token was stored for {name}."
                )

        for relative_path, expected in summary[
            "output_sha256"
        ].items():
            path = ROOT / relative_path

            if not path.is_file():
                raise RuntimeError(
                    f"Analytical output is missing: {relative_path}"
                )

            if sha256(path) != expected:
                raise RuntimeError(
                    f"Analytical checksum mismatch: {relative_path}"
                )

        raster_paths = {
            "red": (
                A5
                / "output/rasters/"
                "selected_field_red_reflectance.tif"
            ),
            "nir": (
                A5
                / "output/rasters/"
                "selected_field_nir_reflectance.tif"
            ),
            "qa_pixel": (
                A5
                / "output/rasters/"
                "selected_field_qa_pixel.tif"
            ),
            "qa_radsat": (
                A5
                / "output/rasters/"
                "selected_field_qa_radsat.tif"
            ),
            "ndvi": (
                A5
                / "output/rasters/"
                "selected_field_ndvi.tif"
            ),
        }

        alignments = {}
        arrays = {}

        for name, path in raster_paths.items():
            with rasterio.open(path) as src:
                alignments[name] = (
                    str(src.crs),
                    src.width,
                    src.height,
                    tuple(src.transform),
                    tuple(src.res),
                )

                arrays[name] = src.read(
                    1,
                    masked=True,
                )

        reference = alignments["red"]

        for name, alignment in alignments.items():
            if alignment != reference:
                raise RuntimeError(
                    f"Raster alignment mismatch: {name}"
                )

        if reference[0] != "EPSG:32617":
            raise RuntimeError(
                f"Unexpected raster CRS: {reference[0]}"
            )

        if not (
            math.isclose(reference[4][0], 30.0)
            and math.isclose(reference[4][1], 30.0)
        ):
            raise RuntimeError(
                f"Unexpected raster resolution: {reference[4]}"
            )

        dimensions = summary["dimensions"]

        if (
            reference[1] != dimensions["width"]
            or reference[2] != dimensions["height"]
        ):
            raise RuntimeError(
                "Summary raster dimensions are incorrect."
            )

        ndvi = arrays["ndvi"].compressed()

        if ndvi.size == 0:
            raise RuntimeError(
                "NDVI raster has no valid pixels."
            )

        if ndvi.size != summary["valid_pixel_count"]:
            raise RuntimeError(
                "NDVI valid-pixel count disagrees with summary."
            )

        if float(np.min(ndvi)) < -1.000001:
            raise RuntimeError(
                "NDVI contains a value below -1."
            )

        if float(np.max(ndvi)) > 1.000001:
            raise RuntimeError(
                "NDVI contains a value above 1."
            )

        calculated = {
            "minimum": float(np.min(ndvi)),
            "median": float(np.median(ndvi)),
            "mean": float(np.mean(ndvi)),
            "maximum": float(np.max(ndvi)),
            "standard_deviation": float(np.std(ndvi)),
        }

        reported = summary["ndvi_statistics"]

        for name, value in calculated.items():
            if not np.isclose(
                value,
                reported[name],
                rtol=0.0,
                atol=1e-6,
            ):
                raise RuntimeError(
                    f"NDVI statistic mismatch: {name}"
                )

        reflectance = summary[
            "surface_reflectance"
        ]

        if not np.isclose(
            reflectance["scale"],
            0.0000275,
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError(
                "Incorrect surface-reflectance scale."
            )

        if not np.isclose(
            reflectance["offset"],
            -0.2,
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError(
                "Incorrect surface-reflectance offset."
            )

        image_requirements = {
            (
                A5
                / "output/visualizations/"
                "01_selected_field_red_reflectance.png"
            ): (1800, 1400),
            (
                A5
                / "output/visualizations/"
                "03_selected_field_ndvi.png"
            ): (1800, 1400),
            (
                A5
                / "output/visualizations/"
                "04_assignment_05_final_panel.png"
            ): (2400, 1800),
            (
                A5
                / "output/dashboard_assets/"
                "dashboard_selected_field_ndvi.png"
            ): (1800, 1400),
        }

        for path, minimum_size in image_requirements.items():
            with Image.open(path) as image:
                if (
                    image.width < minimum_size[0]
                    or image.height < minimum_size[1]
                ):
                    raise RuntimeError(
                        f"Image is undersized: "
                        f"{path.relative_to(ROOT)} "
                        f"({image.width}x{image.height})"
                    )

        walkthrough = (
            A5 / "NDVI_WALKTHROUGH.md"
        ).read_text(encoding="utf-8")

        required_inline_images = [
            "01_selected_field_red_reflectance.png",
            "02_selected_field_nir_reflectance.png",
            "03_selected_field_ndvi.png",
            "04_assignment_05_final_panel.png",
        ]

        for image_name in required_inline_images:
            if image_name not in walkthrough:
                raise RuntimeError(
                    f"Walkthrough does not embed {image_name}."
                )

        log_text = (
            A5 / "output/skill_run.log"
        ).read_text(encoding="utf-8")

        if SUCCESS_MESSAGE not in log_text:
            raise RuntimeError(
                "Successful-run message is absent from skill_run.log."
            )

        notebook_path = (
            ROOT / "notebooks/05_ndvi_crop_health.ipynb"
        )

        code_cells, executed_cells = verify_notebook(
            notebook_path
        )

        print("Product ID:", product_id)
        print("Platform:", manifest["platform"])
        print(
            "Acquisition:",
            manifest["acquisition_datetime"],
        )
        print(
            "Field ID:",
            manifest["field_id"],
        )
        print(
            "Valid NDVI pixels:",
            summary["valid_pixel_count"],
        )
        print(
            "NDVI range:",
            f"{calculated['minimum']:.6f}",
            "to",
            f"{calculated['maximum']:.6f}",
        )
        print(
            "Notebook code cells:",
            f"{executed_cells}/{code_cells}",
        )
        print(PASS_MESSAGE)

        return 0

    except Exception as exc:
        print(
            f"FAIL: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
