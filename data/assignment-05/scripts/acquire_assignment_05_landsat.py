#!/usr/bin/env python3
"""Acquire authentic Landsat C2 L2 AOI windows from Planetary Computer."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


ROOT = Path(__file__).resolve().parents[3]
A5 = ROOT / "data/assignment-05"
SRC = A5 / "source"
OUT = A5 / "output"

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

ASSETS = {
    "red": "red",
    "nir08": "nir",
    "qa_pixel": "qa_pixel",
    "qa_radsat": "qa_radsat",
}

SEARCH_PERIOD = (
    "2023-05-01T00:00:00Z/"
    "2023-09-30T23:59:59Z"
)

CLOUD_THRESHOLD = 20
TARGET_DATE = pd.Timestamp("2023-07-15")


def sha(path: Path) -> str:
    """Return a SHA-256 checksum for a local file."""
    digest = hashlib.sha256()

    with path.open("rb") as file_obj:
        for block in iter(
            lambda: file_obj.read(1 << 20),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def remove_url_query(url: str) -> str:
    """Remove temporary SAS credentials from a URL."""
    parts = urlsplit(url)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            "",
            "",
        )
    )


def select_field():
    """Select the largest validated Assignment 2 field."""
    fields = gpd.read_file(
        ROOT / "data/assignment-02/fields_EPSG4326.geojson"
    )

    summary = pd.read_csv(
        ROOT / "data/assignment-02/field_summary.csv",
        dtype={"field_id": str},
    )

    row = (
        summary.sort_values(
            ["CSBACRES", "field_id"],
            ascending=[False, True],
        )
        .iloc[0]
    )

    selected = fields[
        fields.field_id.astype(str) == str(row.field_id)
    ].iloc[[0]]

    if selected.empty:
        raise RuntimeError(
            f"Selected field {row.field_id} was not found."
        )

    return selected, row


def read_candidate_quality(
    item,
    context: gpd.GeoDataFrame,
) -> tuple[float, float, float]:
    """Read QA assets and calculate AOI-level quality metrics."""
    required = {
        "red",
        "nir08",
        "qa_pixel",
        "qa_radsat",
    }

    missing = required - set(item.assets)

    if missing:
        raise RuntimeError(
            "Candidate is missing required assets: "
            + ", ".join(sorted(missing))
        )

    # Sign only the runtime copy. Do not save temporary
    # access credentials in repository metadata.
    signed_item = planetary_computer.sign(item)

    qa_url = signed_item.assets["qa_pixel"].href
    rad_url = signed_item.assets["qa_radsat"].href

    with rasterio.open(qa_url) as dataset:
        geometry = mapping(
            context.to_crs(dataset.crs).geometry.iloc[0]
        )

        qa_masked, _ = mask(
            dataset,
            [geometry],
            crop=True,
            filled=False,
        )

    qa_band = qa_masked[0]
    qa_data = qa_band.filled(0).astype(np.uint16)
    outside = np.ma.getmaskarray(qa_band)

    inside = ~outside
    inside_count = int(inside.sum())

    if inside_count == 0:
        raise RuntimeError(
            "Candidate QA raster contains no pixels "
            "inside the context geometry."
        )

    bad = outside.copy()

    # QA_PIXEL rejected bits:
    # 0 fill, 1 dilated cloud, 2 cirrus,
    # 3 cloud, 4 cloud shadow, 5 snow.
    for bit in (0, 1, 2, 3, 4, 5):
        bad |= ((qa_data >> bit) & 1).astype(bool)

    cloud = (
        ((qa_data >> 3) & 1).astype(bool)
        & inside
    )

    shadow = (
        ((qa_data >> 4) & 1).astype(bool)
        & inside
    )

    with rasterio.open(rad_url) as dataset:
        geometry = mapping(
            context.to_crs(dataset.crs).geometry.iloc[0]
        )

        rad_masked, _ = mask(
            dataset,
            [geometry],
            crop=True,
            filled=False,
        )

    rad_band = rad_masked[0]
    rad_data = rad_band.filled(0)
    rad_outside = np.ma.getmaskarray(rad_band)

    if rad_data.shape != qa_data.shape:
        raise RuntimeError(
            "QA_PIXEL and QA_RADSAT windows do not align."
        )

    saturated = rad_outside | (rad_data != 0)
    valid = inside & ~bad & ~saturated

    valid_pct = float(
        valid.sum() / inside_count * 100.0
    )

    cloud_pct = float(
        cloud.sum() / inside_count * 100.0
    )

    shadow_pct = float(
        shadow.sum() / inside_count * 100.0
    )

    return valid_pct, cloud_pct, shadow_pct


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--endpoint",
        default=STAC,
        help="Planetary Computer STAC API root.",
    )

    args = parser.parse_args()

    SRC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    attempts: list[dict] = []

    provenance = {
        "status": "failed",
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "endpoint": args.endpoint,
        "provider": "Microsoft Planetary Computer",
        "collection": "landsat-c2-l2",
        "attempts": attempts,
        "no_synthetic_fallback_used": True,
    }

    try:
        field, row = select_field()

        context = field.to_crs(32617).copy()
        context.geometry = context.buffer(300)
        context = context.to_crs(4326)

        geometry = mapping(
            context.geometry.iloc[0]
        )

        attempts.append(
            {
                "method": "STAC API search",
                "url": args.endpoint,
                "collection": "landsat-c2-l2",
                "search_period": SEARCH_PERIOD,
                "cloud_threshold": CLOUD_THRESHOLD,
                "platform_filter": [
                    "landsat-8",
                    "landsat-9",
                ],
            }
        )

        catalog = pystac_client.Client.open(
            args.endpoint
        )

        search = catalog.search(
            collections=["landsat-c2-l2"],
            intersects=geometry,
            datetime=SEARCH_PERIOD,
            query={
                "eo:cloud_cover": {
                    "lte": CLOUD_THRESHOLD
                }
            },
            max_items=100,
        )

        items = list(search.items())

        # Assignment 5 uses Landsat 8 or Landsat 9.
        items = [
            item
            for item in items
            if item.id.startswith(
                ("LC08_", "LC09_")
            )
        ]

        if not items:
            raise RuntimeError(
                "No authentic Landsat 8/9 candidates "
                "were returned."
            )

        candidates = []

        for item in items:
            try:
                (
                    valid_pct,
                    cloud_pct,
                    shadow_pct,
                ) = read_candidate_quality(
                    item,
                    context,
                )

                properties = item.properties

                date_string = str(
                    properties["datetime"]
                )[:10]

                date_distance = abs(
                    (
                        pd.Timestamp(date_string)
                        - TARGET_DATE
                    ).days
                )

                scene_cloud = float(
                    properties.get(
                        "eo:cloud_cover",
                        100.0,
                    )
                )

                candidates.append(
                    (
                        valid_pct,
                        cloud_pct,
                        shadow_pct,
                        scene_cloud,
                        date_distance,
                        item.id,
                        item,
                    )
                )

                attempts.append(
                    {
                        "candidate": item.id,
                        "status": "quality_read_succeeded",
                        "valid_aoi_pct": valid_pct,
                        "aoi_cloud_pct": cloud_pct,
                        "aoi_shadow_pct": shadow_pct,
                        "scene_cloud_pct": scene_cloud,
                        "target_date_distance_days": (
                            date_distance
                        ),
                    }
                )

            except Exception as exc:
                attempts.append(
                    {
                        "candidate": item.id,
                        "status": "read_failed",
                        "error_type": (
                            type(exc).__name__
                        ),
                        "error": str(exc),
                    }
                )

        if not candidates:
            raise RuntimeError(
                "Every authentic candidate AOI read "
                "failed."
            )

        candidates.sort(
            key=lambda candidate: (
                -candidate[0],
                candidate[1] + candidate[2],
                candidate[3],
                candidate[4],
                candidate[5],
            )
        )

        best = candidates[0]
        item = best[-1]

        signed_item = planetary_computer.sign(
            item
        )

        raw = SRC / "raw"
        raw.mkdir(parents=True, exist_ok=True)

        asset_records = {}

        for stac_key, output_key in ASSETS.items():
            if stac_key not in item.assets:
                raise RuntimeError(
                    f"Selected scene is missing "
                    f"required asset {stac_key}."
                )

            signed_url = (
                signed_item.assets[stac_key].href
            )

            stable_source_url = (
                item.assets[stac_key].href
            )

            destination = (
                raw / f"{output_key}.tif"
            )

            with rasterio.open(
                signed_url
            ) as dataset:
                geometry_projected = mapping(
                    context.to_crs(
                        dataset.crs
                    ).geometry.iloc[0]
                )

                array, transform = mask(
                    dataset,
                    [geometry_projected],
                    crop=True,
                )

                profile = dataset.profile.copy()

                profile.update(
                    count=array.shape[0],
                    height=array.shape[1],
                    width=array.shape[2],
                    transform=transform,
                    compress="deflate",
                )

                with rasterio.open(
                    destination,
                    "w",
                    **profile,
                ) as output:
                    output.write(array)

            asset_records[output_key] = {
                "path": str(
                    destination.relative_to(ROOT)
                ),
                "sha256": sha(destination),
                "source_url": remove_url_query(
                    stable_source_url
                ),
                "stac_asset": stac_key,
                "access_method": (
                    "Temporary Planetary Computer "
                    "signed Azure Blob URL"
                ),
            }

        selected_field_path = (
            SRC / "selected_field.geojson"
        )

        field.to_file(
            selected_field_path,
            driver="GeoJSON",
        )

        # Save unsigned STAC metadata. Temporary SAS
        # credentials are not written to the repository.
        scene_metadata = item.to_dict()

        (
            SRC / "selected_scene_metadata.json"
        ).write_text(
            json.dumps(
                scene_metadata,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        manifest = {
            "status": "acquired",
            "generated_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "product_id": item.id,
            "platform": item.properties.get(
                "platform"
            ),
            "acquisition_datetime": (
                item.properties.get("datetime")
            ),
            "scene_cloud_pct": float(
                item.properties.get(
                    "eo:cloud_cover",
                    100.0,
                )
            ),
            "field_id": str(row.field_id),
            "field_acres": float(
                row.CSBACRES
            ),
            "crop_2023": str(
                row.crop_2023
            ),
            "endpoint": args.endpoint,
            "provider": (
                "Microsoft Planetary Computer"
            ),
            "collection": "landsat-c2-l2",
            "context_buffer_m": 300,
            "assets": asset_records,
            "candidate_metrics": {
                "valid_aoi_pct": best[0],
                "aoi_cloud_pct": best[1],
                "aoi_shadow_pct": best[2],
                "scene_cloud_pct": best[3],
                "target_date_distance_days": (
                    best[4]
                ),
            },
            "qa_pixel_rejected_bits": {
                "0": "fill",
                "1": "dilated cloud",
                "2": "cirrus",
                "3": "cloud",
                "4": "cloud shadow",
                "5": "snow",
            },
            "qa_radsat_rule": (
                "Reject every nonzero QA_RADSAT "
                "pixel."
            ),
            "temporary_access_tokens_saved": False,
            "no_synthetic_fallback_used": True,
        }

        (
            SRC / "source_manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        provenance.update(
            {
                "status": "acquired",
                "completed_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "selected_product_id": item.id,
                "source_manifest": str(
                    (
                        SRC
                        / "source_manifest.json"
                    ).relative_to(ROOT)
                ),
            }
        )

        (
            OUT / "acquisition_provenance.json"
        ).write_text(
            json.dumps(
                provenance,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            "ACQUIRED:",
            item.id,
        )

        print(
            "PLATFORM:",
            item.properties.get("platform"),
        )

        print(
            "ACQUISITION DATE:",
            item.properties.get("datetime"),
        )

        print(
            "VALID AOI PERCENT:",
            f"{best[0]:.3f}",
        )

        print(
            "AOI CLOUD PERCENT:",
            f"{best[1]:.3f}",
        )

        print(
            "AOI SHADOW PERCENT:",
            f"{best[2]:.3f}",
        )

        print(
            "PASS: Authentic Landsat source "
            "acquisition succeeded."
        )

    except Exception as exc:
        provenance["status"] = "failed"
        provenance["error_type"] = (
            type(exc).__name__
        )
        provenance["error"] = str(exc)

        (
            OUT / "acquisition_provenance.json"
        ).write_text(
            json.dumps(
                provenance,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            f"FAILED CLOSED: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
