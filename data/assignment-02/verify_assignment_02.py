#!/usr/bin/env python3
"""Verify that Assignment 02 products have auditable real-USDA provenance."""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
YEARS = {2020, 2021, 2022, 2023}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


fields = load_json("fields_EPSG4326.geojson")
merged = load_json("fields_with_crops.geojson")
summary = load_json("output/assignment_02_summary.json")
features = fields["features"]
properties = [feature["properties"] for feature in features]
ids = [str(item["field_id"]) for item in properties]

need(len(features) == 25, "exactly 25 official field polygons are present")
need(all(item.get("CSBID") is not None and str(item["CSBID"]) == str(item["field_id"]) for item in properties),
     "every field_id is the retained official CSBID")
need(len(ids) == len(set(ids)), "the 25 CSBID values are unique")
need(all(str(item.get("STATEFIPS", "")).zfill(2) == "45" for item in properties),
     "every field has South Carolina STATEFIPS 45")
need(not any(re.match(r"^(?:FIELD_|45-2022-CSB)", value, re.I) for value in ids),
     "no legacy locally generated field identifiers remain")
need(all(feature.get("geometry", {}).get("type") in {"Polygon", "MultiPolygon"}
         and feature["geometry"].get("coordinates") for feature in features),
     "all source geometries are nonempty polygons")
need(all(all(-180 <= point[0] <= 180 and -90 <= point[1] <= 90
             for point in (feature["geometry"]["coordinates"][0][0]
                           if feature["geometry"]["type"] == "MultiPolygon"
                           else feature["geometry"]["coordinates"][0])) for feature in features),
     "all output geometry coordinates are valid EPSG:4326 coordinates")

script = (ROOT / "scripts/build_real_usda_data.py").read_text(encoding="utf-8")
need("import requests" in script and "import rasterio" in script, "builder imports requests and rasterio")
need(not re.search(r"^\s*(CENTERS|SEQS)\s*=", script, re.M), "builder has no CENTERS or SEQS constants")
need("shapely.geometry" not in script and "Polygon(" not in script and "random." not in script,
     "builder contains no polygon construction or random geometry generation")
need("dominant * 100 / len(values)" in script and "Counter(values.tolist())" in script,
     "dominant values and percentages are computed from extracted raster pixels")

with (ROOT / "cdl_EPSG4326.csv").open(newline="", encoding="utf-8") as stream:
    rows = list(csv.DictReader(stream))
required = {"field_id", "year", "crop_code", "crop_name", "valid_pixel_count",
            "dominant_pixel_count", "dominant_pct", "extraction_method",
            "raster_source_url", "raster_sha256", "csb_annual_cdl_code",
            "matches_csb_annual_cdl"}
need(bool(rows) and required <= set(rows[0]), "CDL table contains raster extraction and comparison evidence")
need(len(rows) == 100 and {int(row["year"]) for row in rows} == YEARS,
     "CDL table has exactly 25 rows for each of 2020–2023")
need({row["field_id"] for row in rows} == set(ids), "all and only official CSBID fields have CDL rows")
need(all(int(row["valid_pixel_count"]) > 0 and 0 < int(row["dominant_pixel_count"]) <= int(row["valid_pixel_count"])
         for row in rows), "all CDL rows contain genuine positive pixel counts")
need(all(math.isclose(float(row["dominant_pct"]), int(row["dominant_pixel_count"]) * 100 /
                      int(row["valid_pixel_count"]), abs_tol=0.000001) for row in rows),
     "every dominant percentage agrees with its recorded pixel counts")
need(all(row["extraction_method"].startswith("rasterio.mask") for row in rows),
     "every row records the rasterio.mask extraction method")
need(all(row["raster_source_url"].startswith("http") and re.fullmatch(r"[0-9a-f]{64}", row["raster_sha256"])
         for row in rows), "every row identifies a real raster source and SHA-256")

source = summary.get("boundary_source", {})
need(source.get("requested_url", "").endswith("NationalCSB_2016-2023_rev23.zip")
     and source.get("http_status") == 200 and source.get("byte_size", 0) > 0
     and re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")),
     "summary records official source archive URL, HTTP status, bytes, and SHA-256")
feature_class = summary.get("feature_class", {})
schema_properties = feature_class.get("schema", {}).get("properties", {})
need(feature_class.get("layer") and "CSBID" in {name.upper() for name in schema_properties},
     "summary records actual geodatabase feature-class and schema evidence")
selection = summary.get("field_selection", {})
need(selection.get("national_feature_class") == feature_class.get("layer")
     and selection.get("state_filter")
     and selection.get("south_carolina_feature_count_read", 0) >= 25
     and selection.get("national_feature_class_loaded_in_full") is False,
     "summary proves the state-filtered read did not load the national feature class")
need(selection.get("county_attribute") and selection.get("selected_county")
     and selection.get("eligible_fields_in_selected_county", 0) >= 25
     and selection.get("selected_field_count") == 25,
     "summary records deterministic single-county field selection")
need(len(selection.get("cdl_request_bbox_epsg5070", [])) == 4
     and selection.get("cdl_request_bbox_width_m", 0) > 0
     and selection.get("cdl_request_bbox_height_m", 0) > 0,
     "summary records the compact CDL request bounds and metric dimensions")
requests = summary.get("raster_requests", [])
need(len(requests) == 4 and {int(item["year"]) for item in requests} == YEARS,
     "summary records one genuine raster request for every CDL year")
need(all(item.get("response_status") == 200 and item.get("byte_size", 0) > 0
         and item.get("request_parameters", {}).get("bbox")
         and re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) for item in requests),
     "each CDL request records parameters, success, bytes, and raster checksum")
need(summary.get("field_count") == summary.get("matched_fields") == 25
     and summary.get("unmatched_fields") == 0 and len(merged["features"]) == 25,
     "merge metadata records 25 matched fields and no unmatched records")

map_html = (ROOT / "my_fields_map.html").read_text(encoding="utf-8")
need(all(f"{year} crops" in map_html and str(year) in map_html for year in YEARS),
     "interactive HTML embeds all four actual crop-year layers")
need("grouped_layer_control" in map_html.lower() and "exclusiveGroups" in map_html,
     "interactive HTML implements exclusive GroupedLayerControl radio behavior")
need("cartodb" in map_html.lower() and "positron" in map_html.lower(), "CartoDB Positron is present")
need("tile.openstreetmap.org" not in map_html.lower(), "OpenStreetMap tile endpoint is absent")
need(all(value in map_html for value in ids), "interactive HTML embeds all selected field data")

preview = (ROOT / "evidence/my_fields_map_preview.svg").read_text(encoding="utf-8")
need(all(str(year) in preview for year in YEARS), "SVG preview contains 2020, 2021, 2022, and 2023 panels")
need((ROOT / "evidence/terminal_evidence.svg").stat().st_size > 200, "terminal evidence is nonempty")
readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
tracker = (REPO / "docs/project/assignment-02-tracker.md").read_text(encoding="utf-8").lower()
need(all(term in readme + tracker for term in ("official", "csbid", "raster", "unmatched", "limitation")),
     "README and tracker clearly document real data, results, unmatched records, and limitations")
need("generated polygon" not in readme + tracker and "synthetic" not in readme + tracker,
     "README and tracker do not retain earlier generated-data claims")

print("Assignment 02 real-USDA verification passed.")
