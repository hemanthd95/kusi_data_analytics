#!/usr/bin/env python3
"""Create authentic offline Landsat NDVI products for Assignment 5."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.mask import mask
from shapely.geometry import mapping


ROOT = Path(__file__).resolve().parents[3]
A5 = ROOT / "data/assignment-05"
SOURCE = A5 / "source"
OUTPUT = A5 / "output"

MANIFEST_PATH = SOURCE / "source_manifest.json"
SCENE_PATH = SOURCE / "selected_scene_metadata.json"
FIELD_PATH = SOURCE / "selected_field.geojson"

RASTER_DIR = OUTPUT / "rasters"
VISUAL_DIR = OUTPUT / "visualizations"
DASHBOARD_DIR = OUTPUT / "dashboard_assets"
TABLE_DIR = OUTPUT / "tables"

EXPECTED_SCALE = 0.0000275
EXPECTED_OFFSET = -0.2

FLOAT_NODATA = -9999.0
QA_NODATA = 65535

SUCCESS_MESSAGE = (
    "SUCCESS: Assignment 5 real-data NDVI workflow complete"
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
            f"Required file is missing: {path.relative_to(ROOT)}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def validate_sources(
    manifest: dict,
) -> dict[str, Path]:
    if manifest.get("status") != "acquired":
        raise RuntimeError(
            "Source manifest does not report successful acquisition."
        )

    if (
        manifest.get("no_synthetic_fallback_used")
        is not True
    ):
        raise RuntimeError(
            "Source manifest does not attest real-data-only acquisition."
        )

    required = {
        "red",
        "nir",
        "qa_pixel",
        "qa_radsat",
    }

    records = manifest.get("assets", {})
    missing = required - set(records)

    if missing:
        raise RuntimeError(
            f"Source manifest lacks assets: {sorted(missing)}"
        )

    paths: dict[str, Path] = {}

    for name in sorted(required):
        record = records[name]
        path = ROOT / record["path"]

        if not path.is_file():
            raise RuntimeError(
                f"Authentic source is missing: {path}"
            )

        expected = record.get("sha256")
        actual = sha256(path)

        if actual != expected:
            raise RuntimeError(
                f"Authentic source checksum mismatch: {name}"
            )

        paths[name] = path

    return paths


def read_scale_offset(
    scene: dict,
    asset_name: str,
) -> tuple[float, float]:
    asset = scene.get(
        "assets",
        {},
    ).get(asset_name)

    if not isinstance(asset, dict):
        raise RuntimeError(
            f"Scene metadata has no {asset_name} asset."
        )

    bands = asset.get("raster:bands")

    if (
        not isinstance(bands, list)
        or not bands
        or not isinstance(bands[0], dict)
    ):
        raise RuntimeError(
            f"{asset_name} lacks STAC raster:bands metadata."
        )

    band = bands[0]

    if "scale" not in band or "offset" not in band:
        raise RuntimeError(
            f"{asset_name} lacks scale or offset metadata."
        )

    scale = float(band["scale"])
    offset = float(band["offset"])

    if not np.isclose(
        scale,
        EXPECTED_SCALE,
        rtol=0.0,
        atol=1e-12,
    ):
        raise RuntimeError(
            f"{asset_name} scale {scale} does not match "
            f"official value {EXPECTED_SCALE}."
        )

    if not np.isclose(
        offset,
        EXPECTED_OFFSET,
        rtol=0.0,
        atol=1e-12,
    ):
        raise RuntimeError(
            f"{asset_name} offset {offset} does not match "
            f"official value {EXPECTED_OFFSET}."
        )

    return scale, offset


def crop_raster(
    path: Path,
    field: gpd.GeoDataFrame,
):
    with rasterio.open(path) as src:
        geometry = mapping(
            field.to_crs(src.crs).geometry.iloc[0]
        )

        array, transform = mask(
            src,
            [geometry],
            crop=True,
            filled=False,
        )

        profile = src.profile.copy()

        profile.update(
            count=1,
            height=array.shape[1],
            width=array.shape[2],
            transform=transform,
        )

        return {
            "array": array[0],
            "transform": transform,
            "profile": profile,
            "crs": src.crs,
            "resolution": src.res,
        }


def assert_aligned(
    reference: dict,
    candidate: dict,
    name: str,
) -> None:
    if candidate["array"].shape != reference["array"].shape:
        raise RuntimeError(
            f"{name} shape does not align with Red."
        )

    if candidate["transform"] != reference["transform"]:
        raise RuntimeError(
            f"{name} transform does not align with Red."
        )

    if candidate["crs"] != reference["crs"]:
        raise RuntimeError(
            f"{name} CRS does not align with Red."
        )

    if candidate["resolution"] != reference["resolution"]:
        raise RuntimeError(
            f"{name} resolution does not align with Red."
        )


def write_float_raster(
    path: Path,
    values: np.ndarray,
    valid: np.ndarray,
    profile: dict,
    description: str,
) -> None:
    output = np.full(
        values.shape,
        FLOAT_NODATA,
        dtype=np.float32,
    )

    output[valid] = values[valid].astype(
        np.float32
    )

    out_profile = profile.copy()

    out_profile.update(
        dtype="float32",
        nodata=FLOAT_NODATA,
        count=1,
        compress="deflate",
    )

    with rasterio.open(
        path,
        "w",
        **out_profile,
    ) as dst:
        dst.write(output, 1)
        dst.set_band_description(
            1,
            description,
        )
        dst.update_tags(
            synthetic_fallback="false",
            source_product=(
                "USGS Landsat Collection 2 Level-2"
            ),
        )


def write_qa_raster(
    path: Path,
    values: np.ndarray,
    inside: np.ndarray,
    profile: dict,
    description: str,
) -> None:
    output = np.full(
        values.shape,
        QA_NODATA,
        dtype=np.uint16,
    )

    output[inside] = values[inside].astype(
        np.uint16
    )

    out_profile = profile.copy()

    out_profile.update(
        dtype="uint16",
        nodata=QA_NODATA,
        count=1,
        compress="deflate",
    )

    with rasterio.open(
        path,
        "w",
        **out_profile,
    ) as dst:
        dst.write(output, 1)
        dst.set_band_description(
            1,
            description,
        )
        dst.update_tags(
            synthetic_fallback="false"
        )


def robust_limits(
    values: np.ndarray,
) -> tuple[float, float]:
    low, high = np.percentile(
        values,
        [2, 98],
    )

    low = float(low)
    high = float(high)

    if np.isclose(low, high):
        low = float(values.min())
        high = float(values.max())

    if np.isclose(low, high):
        high = low + 1e-6

    return low, high


def save_single_map(
    values: np.ndarray,
    valid: np.ndarray,
    title: str,
    label: str,
    output_stem: Path,
    cmap: str,
    limits: tuple[float, float] | None = None,
) -> None:
    plot_data = np.ma.array(
        values,
        mask=~valid,
    )

    if limits is None:
        vmin, vmax = robust_limits(
            values[valid]
        )
    else:
        vmin, vmax = limits

    fig, ax = plt.subplots(
        figsize=(10, 8)
    )

    image = ax.imshow(
        plot_data,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )

    ax.set_title(
        title,
        fontsize=16,
    )

    ax.set_xlabel(
        "Raster column — 30 m pixels"
    )

    ax.set_ylabel(
        "Raster row — 30 m pixels"
    )

    colorbar = fig.colorbar(
        image,
        ax=ax,
        shrink=0.82,
    )

    colorbar.set_label(label)

    fig.tight_layout()

    fig.savefig(
        output_stem.with_suffix(".png"),
        dpi=300,
        bbox_inches="tight",
    )

    fig.savefig(
        output_stem.with_suffix(".svg"),
        bbox_inches="tight",
    )

    plt.close(fig)


def descriptive_greenness(
    median: float,
) -> str:
    if median < 0.0:
        return (
            "non-vegetated or water-like "
            "spectral response"
        )

    if median < 0.2:
        return "very low greenness"

    if median < 0.4:
        return "low-to-moderate greenness"

    if median < 0.6:
        return "moderate-to-high greenness"

    return "high greenness"


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--offline",
        action="store_true",
        required=True,
    )

    parser.parse_args()

    try:
        manifest = load_json(
            MANIFEST_PATH
        )

        scene = load_json(
            SCENE_PATH
        )

        source_paths = validate_sources(
            manifest
        )

        red_scale, red_offset = (
            read_scale_offset(
                scene,
                "red",
            )
        )

        nir_scale, nir_offset = (
            read_scale_offset(
                scene,
                "nir08",
            )
        )

        if not np.isclose(
            red_scale,
            nir_scale,
        ):
            raise RuntimeError(
                "Red and NIR scale factors disagree."
            )

        if not np.isclose(
            red_offset,
            nir_offset,
        ):
            raise RuntimeError(
                "Red and NIR offsets disagree."
            )

        field = gpd.read_file(
            FIELD_PATH
        )

        if field.empty:
            raise RuntimeError(
                "Selected-field geometry is empty."
            )

        if field.crs is None:
            raise RuntimeError(
                "Selected-field geometry lacks a CRS."
            )

        red = crop_raster(
            source_paths["red"],
            field,
        )

        nir = crop_raster(
            source_paths["nir"],
            field,
        )

        qa_pixel = crop_raster(
            source_paths["qa_pixel"],
            field,
        )

        qa_radsat = crop_raster(
            source_paths["qa_radsat"],
            field,
        )

        assert_aligned(
            red,
            nir,
            "NIR",
        )

        assert_aligned(
            red,
            qa_pixel,
            "QA_PIXEL",
        )

        assert_aligned(
            red,
            qa_radsat,
            "QA_RADSAT",
        )

        red_dn = red["array"]
        nir_dn = nir["array"]
        qa_band = qa_pixel["array"]
        rad_band = qa_radsat["array"]

        red_data = red_dn.filled(
            0
        ).astype(np.float64)

        nir_data = nir_dn.filled(
            0
        ).astype(np.float64)

        qa_data = qa_band.filled(
            0
        ).astype(np.uint16)

        rad_data = rad_band.filled(
            0
        ).astype(np.uint16)

        outside = (
            np.ma.getmaskarray(red_dn)
            | np.ma.getmaskarray(nir_dn)
            | np.ma.getmaskarray(qa_band)
            | np.ma.getmaskarray(rad_band)
        )

        inside = ~outside

        field_pixel_count = int(
            inside.sum()
        )

        if field_pixel_count == 0:
            raise RuntimeError(
                "No Landsat pixels intersect the field."
            )

        bad_qa = np.zeros(
            red_data.shape,
            dtype=bool,
        )

        for bit in (
            0,
            1,
            2,
            3,
            4,
            5,
        ):
            bad_qa |= (
                ((qa_data >> bit) & 1)
                .astype(bool)
            )

        saturated = rad_data != 0

        source_fill = (
            (red_data == 0)
            | (nir_data == 0)
        )

        red_reflectance = (
            red_data * red_scale
            + red_offset
        )

        nir_reflectance = (
            nir_data * nir_scale
            + nir_offset
        )

        denominator = (
            nir_reflectance
            + red_reflectance
        )

        valid = (
            inside
            & ~bad_qa
            & ~saturated
            & ~source_fill
            & np.isfinite(red_reflectance)
            & np.isfinite(nir_reflectance)
            & (red_reflectance >= 0.0)
            & (nir_reflectance >= 0.0)
            & (np.abs(denominator) > 1e-8)
        )

        ndvi = np.full(
            red_data.shape,
            np.nan,
            dtype=np.float64,
        )

        ndvi[valid] = (
            (
                nir_reflectance[valid]
                - red_reflectance[valid]
            )
            / denominator[valid]
        )

        valid &= (
            np.isfinite(ndvi)
            & (ndvi >= -1.0)
            & (ndvi <= 1.0)
        )

        valid_pixel_count = int(
            valid.sum()
        )

        if valid_pixel_count == 0:
            raise RuntimeError(
                "No valid NDVI pixels remain "
                "after quality masking."
            )

        ndvi_values = ndvi[valid]

        valid_pixel_percent = (
            valid_pixel_count
            / field_pixel_count
            * 100.0
        )

        for directory in (
            RASTER_DIR,
            VISUAL_DIR,
            DASHBOARD_DIR,
            TABLE_DIR,
        ):
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        red_path = (
            RASTER_DIR
            / "selected_field_red_reflectance.tif"
        )

        nir_path = (
            RASTER_DIR
            / "selected_field_nir_reflectance.tif"
        )

        qa_path = (
            RASTER_DIR
            / "selected_field_qa_pixel.tif"
        )

        radsat_path = (
            RASTER_DIR
            / "selected_field_qa_radsat.tif"
        )

        ndvi_path = (
            RASTER_DIR
            / "selected_field_ndvi.tif"
        )

        write_float_raster(
            red_path,
            red_reflectance,
            valid,
            red["profile"],
            "Landsat Red surface reflectance",
        )

        write_float_raster(
            nir_path,
            nir_reflectance,
            valid,
            red["profile"],
            "Landsat NIR surface reflectance",
        )

        write_qa_raster(
            qa_path,
            qa_data,
            inside,
            qa_pixel["profile"],
            "Landsat QA_PIXEL",
        )

        write_qa_raster(
            radsat_path,
            rad_data,
            inside,
            qa_radsat["profile"],
            "Landsat QA_RADSAT",
        )

        write_float_raster(
            ndvi_path,
            ndvi,
            valid,
            red["profile"],
            "Normalized Difference Vegetation Index",
        )

        red_stem = (
            VISUAL_DIR
            / "01_selected_field_red_reflectance"
        )

        nir_stem = (
            VISUAL_DIR
            / "02_selected_field_nir_reflectance"
        )

        ndvi_stem = (
            VISUAL_DIR
            / "03_selected_field_ndvi"
        )

        final_stem = (
            VISUAL_DIR
            / "04_assignment_05_final_panel"
        )

        save_single_map(
            red_reflectance,
            valid,
            (
                "Landsat Red Surface Reflectance "
                "— Selected Field"
            ),
            "Surface reflectance",
            red_stem,
            "gray",
        )

        save_single_map(
            nir_reflectance,
            valid,
            (
                "Landsat NIR Surface Reflectance "
                "— Selected Field"
            ),
            "Surface reflectance",
            nir_stem,
            "gray",
        )

        save_single_map(
            ndvi,
            valid,
            "Landsat NDVI — Selected Field",
            "NDVI",
            ndvi_stem,
            "RdYlGn",
            (-1.0, 1.0),
        )

        fig, axes = plt.subplots(
            2,
            2,
            figsize=(14, 10),
        )

        layers = [
            (
                red_reflectance,
                "Red reflectance",
                "gray",
                None,
            ),
            (
                nir_reflectance,
                "NIR reflectance",
                "gray",
                None,
            ),
            (
                ndvi,
                "NDVI",
                "RdYlGn",
                (-1.0, 1.0),
            ),
        ]

        for ax, layer in zip(
            axes.flat[:3],
            layers,
        ):
            values, title, cmap, limits = layer

            if limits is None:
                vmin, vmax = robust_limits(
                    values[valid]
                )
            else:
                vmin, vmax = limits

            image = ax.imshow(
                np.ma.array(
                    values,
                    mask=~valid,
                ),
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest",
            )

            ax.set_title(title)
            ax.set_xlabel("Column")
            ax.set_ylabel("Row")

            fig.colorbar(
                image,
                ax=ax,
                shrink=0.78,
            )

        statistics = {
            "minimum": float(
                np.min(ndvi_values)
            ),
            "median": float(
                np.median(ndvi_values)
            ),
            "mean": float(
                np.mean(ndvi_values)
            ),
            "maximum": float(
                np.max(ndvi_values)
            ),
            "standard_deviation": float(
                np.std(ndvi_values)
            ),
        }

        axes[1, 1].axis("off")

        axes[1, 1].text(
            0.02,
            0.95,
            "\n".join(
                [
                    (
                        f"Product: "
                        f"{manifest['product_id']}"
                    ),
                    (
                        f"Date: "
                        f"{str(manifest['acquisition_datetime'])[:10]}"
                    ),
                    (
                        f"Field: "
                        f"{manifest['field_id']}"
                    ),
                    (
                        f"2023 CDL: "
                        f"{manifest['crop_2023']}"
                    ),
                    (
                        f"Valid pixels: "
                        f"{valid_pixel_count}/"
                        f"{field_pixel_count}"
                    ),
                    (
                        f"NDVI mean: "
                        f"{statistics['mean']:.4f}"
                    ),
                    (
                        f"NDVI median: "
                        f"{statistics['median']:.4f}"
                    ),
                    "",
                    (
                        "Interpretation is descriptive,"
                    ),
                    (
                        "not a causal crop-health "
                        "diagnosis."
                    ),
                ]
            ),
            va="top",
            fontsize=13,
        )

        fig.suptitle(
            (
                "Assignment 5 — Authentic "
                "Landsat NDVI Workflow"
            ),
            fontsize=18,
        )

        fig.tight_layout()

        fig.savefig(
            final_stem.with_suffix(".png"),
            dpi=300,
            bbox_inches="tight",
        )

        fig.savefig(
            final_stem.with_suffix(".svg"),
            bbox_inches="tight",
        )

        plt.close(fig)

        dashboard_path = (
            DASHBOARD_DIR
            / "dashboard_selected_field_ndvi.png"
        )

        with Image.open(
            ndvi_stem.with_suffix(".png")
        ) as image:
            image.save(
                dashboard_path
            )

        distribution_bins = [
            -1.0,
            0.0,
            0.2,
            0.4,
            0.6,
            1.0000001,
        ]

        distribution_labels = [
            "negative",
            "0.0_to_0.2",
            "0.2_to_0.4",
            "0.4_to_0.6",
            "0.6_to_1.0",
        ]

        distribution_counts, _ = (
            np.histogram(
                ndvi_values,
                bins=distribution_bins,
            )
        )

        summary = {
            "status": "complete",
            "generated_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "product_id": manifest["product_id"],
            "platform": manifest["platform"],
            "acquisition_datetime": (
                manifest["acquisition_datetime"]
            ),
            "field_id": manifest["field_id"],
            "field_acres": (
                manifest["field_acres"]
            ),
            "crop_2023": manifest["crop_2023"],
            "crs": str(red["crs"]),
            "resolution_m": [
                float(red["resolution"][0]),
                float(red["resolution"][1]),
            ],
            "dimensions": {
                "width": int(
                    red_data.shape[1]
                ),
                "height": int(
                    red_data.shape[0]
                ),
            },
            "surface_reflectance": {
                "scale": red_scale,
                "offset": red_offset,
                "metadata_source": (
                    "selected_scene_metadata.json "
                    "raster:bands"
                ),
                "official_value_validation": True,
            },
            "quality_mask": {
                "qa_pixel_rejected_bits": [
                    0,
                    1,
                    2,
                    3,
                    4,
                    5,
                ],
                "qa_radsat_rule": (
                    "Reject every nonzero value."
                ),
                "source_fill_rejected": True,
                "negative_reflectance_rejected": True,
                "near_zero_denominator_rejected": True,
            },
            "field_pixel_count": (
                field_pixel_count
            ),
            "valid_pixel_count": (
                valid_pixel_count
            ),
            "valid_pixel_percent": (
                valid_pixel_percent
            ),
            "ndvi_statistics": statistics,
            "ndvi_distribution_counts": {
                label: int(count)
                for label, count in zip(
                    distribution_labels,
                    distribution_counts,
                )
            },
            "descriptive_greenness": (
                descriptive_greenness(
                    statistics["median"]
                )
            ),
            "interpretation_caution": (
                "Single-date 30 m NDVI is "
                "descriptive and cannot by itself "
                "diagnose crop health, yield, "
                "management quality, or stress cause."
            ),
            "rasters": {
                "red": str(
                    red_path.relative_to(ROOT)
                ),
                "nir": str(
                    nir_path.relative_to(ROOT)
                ),
                "qa_pixel": str(
                    qa_path.relative_to(ROOT)
                ),
                "qa_radsat": str(
                    radsat_path.relative_to(ROOT)
                ),
                "ndvi": str(
                    ndvi_path.relative_to(ROOT)
                ),
            },
            "visualizations": {
                "red_png": (
                    "output/visualizations/"
                    "01_selected_field_red_reflectance.png"
                ),
                "nir_png": (
                    "output/visualizations/"
                    "02_selected_field_nir_reflectance.png"
                ),
                "ndvi_png": (
                    "output/visualizations/"
                    "03_selected_field_ndvi.png"
                ),
                "final_panel_png": (
                    "output/visualizations/"
                    "04_assignment_05_final_panel.png"
                ),
                "dashboard_png": (
                    "output/dashboard_assets/"
                    "dashboard_selected_field_ndvi.png"
                ),
            },
            "output_sha256": {
                str(path.relative_to(ROOT)): (
                    sha256(path)
                )
                for path in (
                    red_path,
                    nir_path,
                    qa_path,
                    radsat_path,
                    ndvi_path,
                )
            },
            "no_synthetic_fallback_used": True,
        }

        summary_path = (
            OUTPUT
            / "ndvi_summary.json"
        )

        summary_path.write_text(
            json.dumps(
                summary,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        pd.DataFrame(
            [
                {
                    "statistic": name,
                    "ndvi": value,
                }
                for name, value
                in statistics.items()
            ]
        ).to_csv(
            TABLE_DIR
            / "ndvi_statistics.csv",
            index=False,
        )

        log_lines = [
            (
                "Assignment 5 authentic "
                "Landsat NDVI run"
            ),
            (
                f"Generated UTC: "
                f"{summary['generated_utc']}"
            ),
            (
                f"Product ID: "
                f"{manifest['product_id']}"
            ),
            (
                f"Field ID: "
                f"{manifest['field_id']}"
            ),
            f"Scale: {red_scale}",
            f"Offset: {red_offset}",
            (
                f"Field pixels: "
                f"{field_pixel_count}"
            ),
            (
                f"Valid NDVI pixels: "
                f"{valid_pixel_count}"
            ),
            (
                f"Valid NDVI percent: "
                f"{valid_pixel_percent:.6f}"
            ),
            (
                f"NDVI minimum: "
                f"{statistics['minimum']:.8f}"
            ),
            (
                f"NDVI median: "
                f"{statistics['median']:.8f}"
            ),
            (
                f"NDVI mean: "
                f"{statistics['mean']:.8f}"
            ),
            (
                f"NDVI maximum: "
                f"{statistics['maximum']:.8f}"
            ),
            (
                "Synthetic fallback used: no"
            ),
            SUCCESS_MESSAGE,
        ]

        (
            OUTPUT
            / "skill_run.log"
        ).write_text(
            "\n".join(log_lines) + "\n",
            encoding="utf-8",
        )

        print(
            "PRODUCT:",
            manifest["product_id"],
        )

        print(
            "VALID NDVI PIXELS:",
            (
                f"{valid_pixel_count}/"
                f"{field_pixel_count}"
            ),
        )

        print(
            "NDVI MEAN:",
            f"{statistics['mean']:.6f}",
        )

        print(
            "NDVI MEDIAN:",
            f"{statistics['median']:.6f}",
        )

        print(
            SUCCESS_MESSAGE
        )

        return 0

    except Exception as exc:
        print(
            (
                f"FAIL: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
