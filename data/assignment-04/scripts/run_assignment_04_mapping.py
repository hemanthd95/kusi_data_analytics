"""Assignment 4 real-data acquisition and geospatial analysis pipeline.

The pipeline intentionally has no synthetic fallback.  It preserves a machine-readable
attempt log and raises an actionable error if USDA-NRCS Soil Data Access is unreachable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import requests

REPO = Path(__file__).resolve().parents[3]
A4 = REPO / "data" / "assignment-04"
FIELD_SOURCE = REPO / "data" / "assignment-02" / "fields_EPSG4326.geojson"
SUMMARY_SOURCE = REPO / "data" / "assignment-02" / "field_summary.csv"
ENDPOINT = "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs"
WORKING_CRS = "EPSG:32617"
BUFFER_M = 500


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_fields() -> tuple[gpd.GeoDataFrame, int]:
    """Validate the immutable Assignment 2 geometry and return a working copy."""
    if not FIELD_SOURCE.exists() or not SUMMARY_SOURCE.exists():
        raise FileNotFoundError("Required Assignment 2 field inputs are missing")
    fields = gpd.read_file(FIELD_SOURCE)
    if len(fields) != 25 or fields.field_id.nunique() != 25:
        raise ValueError("Assignment 2 layer must contain 25 features and 25 field IDs")
    if fields.crs is None or fields.crs.to_epsg() != 4326:
        raise ValueError("Assignment 2 field layer must be EPSG:4326")
    if fields.geometry.is_empty.any() or fields.geometry.isna().any():
        raise ValueError("Assignment 2 contains empty field geometry")
    if not fields.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Assignment 2 contains a non-polygon geometry")
    repaired = int((~fields.geometry.is_valid).sum())
    if repaired:
        fields.geometry = fields.geometry.make_valid()
    return fields, repaired


def request_ssurgo(bounds: list[float]) -> tuple[bytes, dict]:
    """Request official SSURGO WFS data with bounded retries and full attempt logging."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "1.1.0",
        "REQUEST": "GetFeature",
        "TYPENAME": "MapunitPolyExtended",
        "SRSNAME": "EPSG:4326",
        "OUTPUTFORMAT": "GML3",
        "MAXFEATURES": "250000",
        "BBOX": ",".join(f"{value:.10f}" for value in bounds) + ",EPSG:4326",
    }
    attempts: list[dict] = []
    headers = {"User-Agent": "kusi-data-analytics-assignment-04/1.0 (academic real-data workflow)"}
    for attempt in range(1, 4):
        record = {"attempt": attempt, "timestamp_utc": utc_now(), "endpoint": ENDPOINT,
                  "parameters": params, "timeout_seconds": 60}
        try:
            response = requests.get(ENDPOINT, params=params, headers=headers, timeout=60)
            record.update(http_status=response.status_code, byte_count=len(response.content),
                          response_sha256=hashlib.sha256(response.content).hexdigest())
            attempts.append(record)
            if response.status_code == 200 and len(response.content) > 1000 and b"FeatureCollection" in response.content:
                return response.content, {"attempts": attempts, "successful_attempt": attempt}
            record["error"] = "Response failed HTTP or GML FeatureCollection validation"
        except requests.RequestException as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            attempts.append(record)
        if attempt < 3:
            time.sleep(2 ** (attempt - 1))
    metadata = {"status": "FAILED", "endpoint": ENDPOINT, "parameters": params,
                "attempts": attempts, "finished_utc": utc_now()}
    source = A4 / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "ssurgo_request_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    raise RuntimeError(
        "Official USDA-NRCS SSURGO WFS acquisition failed after three attempts; "
        "no synthetic fallback was created. See data/assignment-04/source/ssurgo_request_metadata.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Reuse checksum-validated committed GML")
    args = parser.parse_args()
    fields, repairs = validate_fields()
    projected = fields.to_crs(WORKING_CRS)
    dissolved = projected.geometry.union_all()
    buffer_geom = dissolved.buffer(BUFFER_M)
    out = A4 / "output"
    out.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({"buffer_distance_m": [BUFFER_M], "geometry": [buffer_geom]}, crs=WORKING_CRS).to_file(
        out / "field_buffer_500m.geojson", driver="GeoJSON"
    )
    bounds = gpd.GeoSeries([buffer_geom], crs=WORKING_CRS).to_crs(4326).total_bounds.tolist()
    raw_path = A4 / "source" / "ssurgo_mapunit_response.gml"
    if args.offline:
        metadata_path = A4 / "source" / "ssurgo_request_metadata.json"
        if not raw_path.exists() or not metadata_path.exists():
            raise RuntimeError("Offline mode requires a previously validated official GML and metadata")
        metadata = json.loads(metadata_path.read_text())
        expected = metadata.get("response_sha256")
        if not expected or sha256(raw_path) != expected:
            raise RuntimeError("Stored SSURGO response checksum verification failed")
        content = raw_path.read_bytes()
    else:
        content, metadata = request_ssurgo(bounds)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)
        metadata.update(status="SUCCESS", response_sha256=sha256(raw_path), response_byte_size=len(content),
                        endpoint=ENDPOINT, buffer_bounds_epsg4326=bounds, field_source_sha256=sha256(FIELD_SOURCE),
                        geometry_repairs=repairs)
        (A4 / "source" / "ssurgo_request_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # Parsing and downstream analysis may proceed only after genuine response validation.
    raise NotImplementedError("Validated SSURGO response acquired; downstream implementation is pending")


if __name__ == "__main__":
    main()
