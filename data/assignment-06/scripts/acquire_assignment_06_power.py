#!/usr/bin/env python3
"""Acquire or import authentic NASA POWER daily data; fail closed on errors."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[3]
A6 = ROOT / "data/assignment-06"
SOURCE = A6 / "source"
OUTPUT = A6 / "output"
FIELDS = ROOT / "data/assignment-02/fields_EPSG4326.geojson"
SUMMARY = ROOT / "data/assignment-02/field_summary.csv"
ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = ["ALLSKY_SFC_SW_DWN", "PRECTOTCORR", "RH2M", "T2M", "T2M_MAX", "T2M_MIN"]
EXPECTED_KEYS = pd.date_range("1991-01-01", "2025-12-31", freq="D").strftime("%Y%m%d").tolist()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_fields_and_write_location() -> tuple[Point, dict]:
    fields = gpd.read_file(FIELDS)
    summary = pd.read_csv(SUMMARY, dtype={"field_id": str})
    fields["field_id"] = fields["field_id"].astype(str)
    if len(fields) != 25 or fields.field_id.nunique() != 25 or len(summary) != 25 or summary.field_id.nunique() != 25:
        raise ValueError("authoritative inputs must contain exactly 25 unique fields")
    if set(fields.field_id) != set(summary.field_id):
        raise ValueError("field summary and geometry IDs differ")
    if fields.crs is None or fields.crs.to_epsg() != 4326:
        raise ValueError("field CRS is not EPSG:4326")
    if fields.geometry.is_empty.any():
        raise ValueError("empty field geometry")
    if (~fields.geometry.is_valid).any():
        fields.geometry = fields.geometry.make_valid()
    if (~fields.geometry.is_valid).any():
        raise ValueError("field geometry cannot be deterministically repaired")
    fields = fields.merge(summary[["field_id", "crop_2023"]], on="field_id", validate="one_to_one")
    fields["CSBACRES"] = pd.to_numeric(fields.CSBACRES, errors="raise")
    if (fields.CSBACRES <= 0).any():
        raise ValueError("acreage must be positive")

    projected = fields.to_crs(32617)
    centroids = projected.geometry.centroid
    weights = projected.CSBACRES.to_numpy(float)
    point_utm = Point(np.average(centroids.x, weights=weights), np.average(centroids.y, weights=weights))
    point = gpd.GeoSeries([point_utm], crs=32617).to_crs(4326).iloc[0]
    centroid_ll = gpd.GeoSeries(centroids, crs=32617).to_crs(4326)
    distances = np.hypot(centroids.x - point_utm.x, centroids.y - point_utm.y)
    table = pd.DataFrame({
        "field_id": projected.field_id,
        "field_acres": weights,
        "field_centroid_x_utm": centroids.x,
        "field_centroid_y_utm": centroids.y,
        "field_centroid_longitude": centroid_ll.x,
        "field_centroid_latitude": centroid_ll.y,
        "distance_to_weather_point_m": distances,
        "crop_2023": projected.crop_2023,
    }).sort_values("field_id")
    table.to_csv(SOURCE / "field_to_weather_point_distances.csv", index=False)
    feature = {"type": "FeatureCollection", "name": "representative_weather_point", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}, "features": [{"type": "Feature", "properties": {"method": "CSBACRES-weighted field-centroid mean", "field_count": 25}, "geometry": {"type": "Point", "coordinates": [point.x, point.y]}}]}
    write_json(SOURCE / "representative_weather_point.geojson", feature)
    bounds = fields.total_bounds
    location = {
        "field_count": 25,
        "representative_longitude": point.x,
        "representative_latitude": point.y,
        "distance_m": {"minimum": float(distances.min()), "median": float(np.median(distances)), "mean": float(distances.mean()), "maximum": float(distances.max()), "standard_deviation": float(distances.std(ddof=0))},
        "cluster_extent": {"west": bounds[0], "south": bounds[1], "east": bounds[2], "north": bounds[3], "east_west_span_m": float(projected.total_bounds[2] - projected.total_bounds[0]), "north_south_span_m": float(projected.total_bounds[3] - projected.total_bounds[1])},
        "limitation": "One gridded series represents the overall cluster and does not resolve field-to-field meteorological differences.",
    }
    write_json(SOURCE / "field_location_summary.json", location)
    return point, location


def decode_and_validate(raw: bytes, requested_point: Point) -> tuple[dict, dict, dict]:
    if not raw or not raw.strip():
        raise ValueError("raw response is empty")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("raw response is not valid UTF-8") from exc
    prefix = text.lstrip()[:80].lower()
    if prefix.startswith(("<!doctype html", "<html", "<?xml", "<error")) or "proxy error" in prefix:
        raise ValueError("raw response appears to be HTML, XML, or a proxy-error page")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"raw response is malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("NASA POWER response root must be a JSON object")
    header = payload.get("header")
    properties = payload.get("properties")
    geometry = payload.get("geometry")
    metadata = payload.get("parameters")
    if not isinstance(header, dict) or "POWER" not in json.dumps(header).upper():
        raise ValueError("authentic NASA POWER header metadata is missing")
    if not isinstance(properties, dict) or not isinstance(properties.get("parameter"), dict):
        raise ValueError("NASA POWER properties.parameter structure is missing")
    values = properties["parameter"]
    if set(values) != set(PARAMETERS):
        raise ValueError(f"parameter mismatch: received {sorted(values)}")
    reference_keys = None
    for name in PARAMETERS:
        if not isinstance(values[name], dict):
            raise ValueError(f"{name} observations must be a date-keyed object")
        keys = list(values[name])
        if len(keys) != 12_784 or len(set(keys)) != 12_784:
            raise ValueError(f"{name} must contain exactly 12,784 unique dates")
        if keys[0] != "19910101" or keys[-1] != "20251231" or keys != EXPECTED_KEYS:
            raise ValueError(f"{name} date coverage is not exactly 19910101 through 20251231")
        if reference_keys is None:
            reference_keys = keys
        elif keys != reference_keys:
            raise ValueError(f"{name} date keys differ from the other parameters")
    if not isinstance(metadata, dict) or set(metadata) != set(PARAMETERS):
        raise ValueError("complete six-parameter NASA metadata is missing")
    for name in PARAMETERS:
        item = metadata[name]
        if not isinstance(item, dict) or not item.get("units") or not (item.get("longname") or item.get("definition")):
            raise ValueError(f"{name} metadata must include units and a definition/longname")
    fill_value = header.get("fill_value")
    parameter_fill_values = {name: metadata[name].get("fill_value", fill_value) for name in PARAMETERS}
    if all(value is None for value in parameter_fill_values.values()):
        raise ValueError("NASA fill-value metadata is missing")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        raise ValueError("NASA returned Point geometry is missing")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError("NASA returned grid coordinates are missing")
    longitude, latitude = coordinates[:2]
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValueError("NASA returned grid coordinates are invalid")
    # A grid-cell center may differ from the requested point, but must remain geographically local.
    separation_km = 111.0 * np.hypot(latitude - requested_point.y, (longitude - requested_point.x) * np.cos(np.deg2rad(requested_point.y)))
    if separation_km > 100:
        raise ValueError(f"NASA returned point is implausibly distant from request ({separation_km:.1f} km)")
    returned = {"longitude": longitude, "latitude": latitude, "requested_to_returned_distance_km": float(separation_km)}
    response_metadata = {"header": header, "parameters": metadata, "fill_values": parameter_fill_values, "geometry": geometry, "messages": payload.get("messages")}
    return payload, returned, response_metadata


def previous_failure_history() -> list[dict]:
    path = OUTPUT / "acquisition_provenance.json"
    if not path.exists():
        return []
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    history = list(previous.get("acquisition_history", [])) if isinstance(previous, dict) else []
    if isinstance(previous, dict) and previous.get("status") == "failed":
        history.append({key: previous.get(key) for key in ["timestamp_utc", "status", "endpoint", "attempted_url", "http_response_status", "response_body_excerpt", "exception_type", "error_message", "no_synthetic_fallback"]})
    return history


def finalize(raw: bytes, point: Point, location: dict, acquisition_method: str, transport: dict, imported_from: str | None = None) -> None:
    _, returned, response_metadata = decode_and_validate(raw, point)
    raw_path = SOURCE / "nasa_power_daily_raw.json"
    raw_path.write_bytes(raw)  # preserve exact bytes; never reformat the authentic response
    checksum = hashlib.sha256(raw).hexdigest()
    params = {"community": "AG", "format": "JSON", "time-standard": "LST", "start": "19910101", "end": "20251231", "parameters": ",".join(PARAMETERS), "longitude": f"{point.x:.8f}", "latitude": f"{point.y:.8f}"}
    retrieved = utc_now()
    request_record = {
        "endpoint": ENDPOINT,
        "sorted_query_parameters": dict(sorted(params.items())),
        "requested_coordinates": {"longitude": point.x, "latitude": point.y},
        "returned_grid_coordinates": {"longitude": returned["longitude"], "latitude": returned["latitude"]},
        "requested_to_returned_distance_km": returned["requested_to_returned_distance_km"],
        "requested_date_range": {"start": "1991-01-01", "end": "2025-12-31"},
        "parameters": PARAMETERS,
        "community": "AG",
        "time_standard": "LST",
        "format": "JSON",
        "retrieval_timestamp_utc": retrieved,
        "acquisition_method": acquisition_method,
        "externally_downloaded_and_locally_imported": acquisition_method == "external_raw_import",
        "imported_from": imported_from,
        "http_status": transport.get("http_status"),
        "response_content_type": transport.get("content_type", "application/json (validated local bytes)"),
        "raw_response_byte_count": len(raw),
        "raw_response_sha256": checksum,
        "no_synthetic_fallback": True,
    }
    write_json(SOURCE / "nasa_power_request.json", request_record)
    write_json(SOURCE / "nasa_power_response_metadata.json", response_metadata)
    manifest = {
        "status": "success",
        "source": "NASA POWER",
        "endpoint": ENDPOINT,
        "request": request_record,
        "request_metadata_path": "data/assignment-06/source/nasa_power_request.json",
        "response_metadata_path": "data/assignment-06/source/nasa_power_response_metadata.json",
        "authoritative_inputs": {str(FIELDS.relative_to(ROOT)): sha256(FIELDS), str(SUMMARY.relative_to(ROOT)): sha256(SUMMARY)},
        "raw_response": {"path": str(raw_path.relative_to(ROOT)), "sha256": checksum, "bytes": len(raw)},
        "acquisition_method": acquisition_method,
        "externally_downloaded_and_locally_imported": acquisition_method == "external_raw_import",
        "no_synthetic_fallback": True,
    }
    write_json(SOURCE / "source_manifest.json", manifest)
    write_json(OUTPUT / "acquisition_provenance.json", {
        "status": "success",
        "timestamp_utc": retrieved,
        "acquisition_method": acquisition_method,
        "externally_downloaded_and_locally_imported": acquisition_method == "external_raw_import",
        "imported_from": imported_from,
        "request": request_record,
        "field_location": location,
        "raw_response_sha256": checksum,
        "acquisition_history": previous_failure_history(),
        "exception": None,
        "no_synthetic_fallback": True,
    })


def acquire_network(point: Point, location: dict) -> None:
    params = {"community": "AG", "format": "JSON", "time-standard": "LST", "start": "19910101", "end": "20251231", "parameters": ",".join(PARAMETERS), "longitude": f"{point.x:.8f}", "latitude": f"{point.y:.8f}"}
    session = requests.Session()
    session.headers.update({"User-Agent": "kusi-data-analytics-assignment-06/1.1 (educational climate analysis)"})
    response = None
    for attempt in range(4):
        response = session.get(ENDPOINT, params=params, timeout=(15, 180))
        if response.status_code not in [429, 500, 502, 503, 504]:
            break
        if attempt < 3:
            time.sleep(2**attempt)
    if response is None:
        raise RuntimeError("NASA POWER request produced no response")
    if response.status_code != 200:
        raise requests.HTTPError(f"HTTP {response.status_code}; URL={response.url}; body={response.text[:500]!r}", response=response)
    if "json" not in response.headers.get("Content-Type", "").lower():
        raise ValueError(f"unexpected content type {response.headers.get('Content-Type')!r}; body={response.text[:500]!r}")
    finalize(response.content, point, location, "direct_network", {"http_status": response.status_code, "content_type": response.headers.get("Content-Type")})


def import_raw(path: Path, point: Point, location: dict) -> None:
    if not path.is_absolute():
        raise ValueError("--import-raw requires an absolute filepath")
    if not path.is_file():
        raise FileNotFoundError(f"import file does not exist: {path}")
    finalize(path.read_bytes(), point, location, "external_raw_import", {"http_status": None}, str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-raw", type=Path, help="absolute path to an externally downloaded authentic NASA POWER JSON response")
    args = parser.parse_args()
    SOURCE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    point, location = validate_fields_and_write_location()
    if args.import_raw:
        import_raw(args.import_raw, point, location)
    else:
        acquire_network(point, location)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        existing_history = previous_failure_history()
        failure = {
            "status": "failed",
            "timestamp_utc": utc_now(),
            "endpoint": ENDPOINT,
            "attempted_url": getattr(getattr(exc, "request", None), "url", None),
            "http_response_status": getattr(getattr(exc, "response", None), "status_code", None),
            "response_body_excerpt": getattr(getattr(exc, "response", None), "text", "")[:500],
            "exception_type": type(exc).__name__,
            "error_message": str(exc),
            "acquisition_history": existing_history,
            "no_synthetic_fallback": True,
        }
        write_json(OUTPUT / "acquisition_provenance.json", failure)
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("PASS: Authentic NASA POWER weather acquisition succeeded.")
