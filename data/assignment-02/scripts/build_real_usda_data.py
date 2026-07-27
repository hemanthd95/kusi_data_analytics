#!/usr/bin/env python3
"""Build Assignment 2 exclusively from published USDA CSB and CDL data.

This program is intended for the manually dispatched GitHub Actions workflow.
Downloads are kept in ignored directories and every publishable file is staged
until all four raster extractions have succeeded.  A failed official request
therefore cannot overwrite the reviewed Assignment 2 products.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path
from urllib.parse import urljoin

import fiona
import folium
from folium.plugins import Fullscreen, GroupedLayerControl
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS as PyprojCRS
import rasterio
from rasterio.mask import mask
import requests

ROOT = Path(__file__).resolve().parents[3]
ASSIGNMENT = ROOT / "data" / "assignment-02"
DOWNLOADS = ASSIGNMENT / "source_downloads"
RASTERS = ASSIGNMENT / "rasters"
CSB_URL = "https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/datasets/NationalCSB_2016-2023_rev23.zip"
CDL_SERVICE = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLFile"
CDL_COUNTY_CACHE = "https://nassgeodata.gmu.edu/webservice/nass_data_cache/byfips/CDL_{year}_{fips}.tif"
YEARS = (2020, 2021, 2022, 2023)
USER_AGENT = "kusi-data-analytics-assignment-02/1.0 (GitHub Actions; USDA educational analysis)"

# Names are from the USDA NASS CDL category legend. Unknown published codes are
# retained (never replaced) and clearly labelled by their numeric value.
CDL_NAMES = {
    1:"Corn",2:"Cotton",3:"Rice",4:"Sorghum",5:"Soybeans",6:"Sunflower",10:"Peanuts",
    11:"Tobacco",12:"Sweet Corn",13:"Pop or Orn Corn",14:"Mint",21:"Barley",22:"Durum Wheat",
    23:"Spring Wheat",24:"Winter Wheat",25:"Other Small Grains",26:"Dbl Crop WinWht/Soybeans",
    27:"Rye",28:"Oats",29:"Millet",30:"Speltz",31:"Canola",32:"Flaxseed",33:"Safflower",
    34:"Rape Seed",35:"Mustard",36:"Alfalfa",37:"Other Hay/Non Alfalfa",38:"Camelina",
    39:"Buckwheat",41:"Sugarbeets",42:"Dry Beans",43:"Potatoes",44:"Other Crops",45:"Sugarcane",
    46:"Sweet Potatoes",47:"Misc Vegs & Fruits",48:"Watermelons",49:"Onions",50:"Cucumbers",
    51:"Chick Peas",52:"Lentils",53:"Peas",54:"Tomatoes",55:"Caneberries",56:"Hops",
    57:"Herbs",58:"Clover/Wildflowers",59:"Sod/Grass Seed",60:"Switchgrass",61:"Fallow/Idle Cropland",
    63:"Forest",64:"Shrubland",65:"Barren",66:"Cherries",67:"Peaches",68:"Apples",69:"Grapes",
    70:"Christmas Trees",71:"Other Tree Crops",72:"Citrus",74:"Pecans",75:"Almonds",76:"Walnuts",
    77:"Pears",81:"Clouds/No Data",82:"Developed",83:"Water",87:"Wetlands",88:"Nonag/Undefined",
    92:"Aquaculture",111:"Open Water",112:"Perennial Ice/Snow",121:"Developed/Open Space",
    122:"Developed/Low Intensity",123:"Developed/Med Intensity",124:"Developed/High Intensity",
    131:"Barren",141:"Deciduous Forest",142:"Evergreen Forest",143:"Mixed Forest",152:"Shrubland",
    176:"Grassland/Pasture",190:"Woody Wetlands",195:"Herbaceous Wetlands",
}
COLORS = {1:"#f5d328",2:"#d7191c",3:"#00a8e8",5:"#267300",10:"#70a800",11:"#00af4d",
          24:"#a87000",26:"#707000",36:"#e8beff",37:"#b2df8a",61:"#b3b3b3",176:"#e8e8a6"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    return s


def download(s: requests.Session, url: str, path: Path, params=None) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with s.get(url, params=params, timeout=(30, 600), stream=True) as response:
        print(f"GET {response.url} -> HTTP {response.status_code}", flush=True)
        if not response.ok:
            body = response.text[:4000]
            raise RuntimeError(f"Official download failed: GET {response.url}; HTTP {response.status_code}; response={body!r}")
        save_stream(response, path)
        return {"requested_url": url, "final_url": response.url, "http_status": response.status_code,
                "byte_size": path.stat().st_size, "sha256": sha256(path), "accessed_utc": now()}


def valid_csb_archive(path: Path) -> bool:
    """Validate a cached archive without trusting its filename or cache key."""
    try:
        if not path.is_file() or path.stat().st_size == 0 or not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path) as archive:
            return any(".gdb/" in name.lower() or name.lower().endswith(".gdb")
                       for name in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def acquire_csb_archive(s: requests.Session, path: Path) -> dict:
    if path.exists() and valid_csb_archive(path):
        metadata = {"requested_url": CSB_URL, "final_url": CSB_URL, "http_status": None,
                    "cache_reused": True, "cache_validation": "valid ZIP containing .gdb",
                    "byte_size": path.stat().st_size, "sha256": sha256(path), "accessed_utc": now()}
        print(f"Reusing validated CSB cache: bytes={metadata['byte_size']} sha256={metadata['sha256']}")
        return metadata
    if path.exists():
        print(f"Deleting invalid cached CSB archive: {path}", flush=True)
        path.unlink()
    metadata = download(s, CSB_URL, path)
    if not valid_csb_archive(path):
        path.unlink(missing_ok=True)
        raise RuntimeError("Downloaded CSB archive is not a valid ZIP containing a .gdb")
    metadata.update({"cache_reused": False, "cache_validation": "valid ZIP containing .gdb"})
    return metadata


def find_layer(extracted: Path) -> tuple[Path, str, dict]:
    geodatabases = sorted(extracted.rglob("*.gdb"))
    if not geodatabases:
        raise RuntimeError("Official CSB archive contained no .gdb directory")
    candidates = []
    for database in geodatabases:
        for layer in fiona.listlayers(database):
            with fiona.open(database, layer=layer) as source:
                fields = {name.upper() for name in source.schema["properties"]}
                if {"CSBID", "STATEFIPS"}.issubset(fields):
                    candidates.append((database, layer, {"geometry": source.schema["geometry"],
                        "properties": dict(source.schema["properties"]), "crs": source.crs.to_string()}))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one CSB feature class with CSBID/STATEFIPS, found {[(str(x[0]),x[1]) for x in candidates]}")
    return candidates[0]


def normalize_county_fips(value, attribute_name: str) -> str:
    """Return an official SC five-digit county FIPS without name guessing."""
    cleaned = re.sub(r"\.0$", "", str(value).strip())
    if not cleaned.isdigit():
        raise RuntimeError(
            f"Selected county attribute {attribute_name!r} value {value!r} is not a FIPS code; "
            "county names are never guessed for raster acquisition"
        )
    # Numeric geodatabase fields necessarily discard leading zeroes. Restore
    # those within the three-digit county component, but reject longer or
    # otherwise ambiguous values.
    if len(cleaned) <= 3:
        normalized = "45" + cleaned.zfill(3)
    elif len(cleaned) == 5 and cleaned.startswith("45"):
        normalized = cleaned
    else:
        raise RuntimeError(f"County value {value!r} cannot be normalized to a South Carolina FIPS")
    return normalized


def select_fields(database: Path, layer: str, schema: dict) -> tuple[gpd.GeoDataFrame, dict]:
    """Read only one state through OGR, then select a compact county sample."""
    source_properties = schema["properties"]
    lookup = {column.upper(): column for column in source_properties}
    required = ["CSBID", "STATEFIPS", *(f"CDL{year}" for year in YEARS)]
    missing = [name for name in required if name not in lookup]
    if missing:
        raise RuntimeError(f"CSB feature class is missing required attributes: {missing}")

    # FileGDB attributes can expose STATEFIPS as either text or numeric. Build
    # the OGR predicate from Fiona's schema type so filtering happens inside
    # the driver, before GeoPandas receives any feature records.
    state_column = lookup["STATEFIPS"]
    field_type = str(source_properties[state_column]).lower()
    escaped_column = state_column.replace('"', '""')
    state_literal = "45" if field_type.startswith(("int", "float", "real")) else "'45'"
    state_filter = f'"{escaped_column}" = {state_literal}'
    try:
        state = gpd.read_file(database, layer=layer, engine="pyogrio", where=state_filter)
    except Exception as error:
        raise RuntimeError(
            f"OGR state-level read failed for layer {layer!r} with where={state_filter!r}; "
            "refusing to load the national feature class"
        ) from error
    if state_column not in state.columns:
        raise RuntimeError(f"Filtered OGR read did not return STATEFIPS column {state_column!r}")
    if state.empty or not state[state_column].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2).eq("45").all():
        raise RuntimeError(
            f"OGR filter {state_filter!r} returned no records or records outside STATEFIPS 45; "
            "refusing an unfiltered national read"
        )
    south_carolina_count = len(state)
    lookup = {column.upper(): column for column in state.columns}
    county_candidates = ("COUNTYFIPS", "CNTYFIPS", "COUNTY", "COUNTYNAME")
    county_key = next((name for name in county_candidates if name in lookup), None)
    if county_key is None:
        raise RuntimeError(f"CSB schema has no supported county attribute; checked {county_candidates}")
    county_column = lookup[county_key]

    state = state[state.geometry.notna() & ~state.geometry.is_empty].copy()
    state["_csbid"] = state[lookup["CSBID"]].astype(str)
    state = state[~state["_csbid"].duplicated(keep=False)]
    for year in YEARS:
        state[f"_valid_{year}"] = pd.to_numeric(state[lookup[f"CDL{year}"]], errors="coerce").fillna(0).gt(0)
    state["_all_valid"] = state[[f"_valid_{year}" for year in YEARS]].all(axis=1)
    eligible = state[state["_all_valid"] & state[county_column].notna()].copy()
    eligible["_county_sort"] = eligible[county_column].astype(str).str.strip()
    county_counts = eligible.groupby("_county_sort", sort=True).size()
    qualifying = county_counts[county_counts >= 25]
    if qualifying.empty:
        raise RuntimeError(
            f"No single South Carolina county has 25 eligible unique CSB fields using {county_column!r}; "
            "refusing to fall back to a statewide selection"
        )
    selected_county = sorted(qualifying.index)[0]
    selected_county_fips = normalize_county_fips(selected_county, county_column)
    county_eligible_count = int(qualifying.loc[selected_county])
    state = (eligible[eligible["_county_sort"] == selected_county]
             .sort_values("_csbid", kind="stable").head(25).copy())
    if len(state) != 25:
        raise RuntimeError(f"County {selected_county!r} yielded only {len(state)} eligible fields")
    output = gpd.GeoDataFrame({
        "field_id": state[lookup["CSBID"]].astype(str), "CSBID": state[lookup["CSBID"]].astype(str),
        "STATEFIPS": state[lookup["STATEFIPS"]].astype(str).str.zfill(2),
        "CSBACRES": state[lookup["CSBACRES"]] if "CSBACRES" in lookup else np.nan,
        "county": state[county_column],
        "source_attribute": state[lookup["SOURCE"]] if "SOURCE" in lookup else "",
        **{f"CDL{year}": pd.to_numeric(state[lookup[f"CDL{year}"]], errors="raise").astype(int) for year in YEARS},
        "geometry": state.geometry,
    }, crs=state.crs)
    if output.field_id.duplicated().any():
        raise RuntimeError("Selected CSBID values are not unique")
    # Reprojection is the only geometry transformation; no construction,
    # simplification, buffering, shifting, or coordinate editing occurs.
    output = output.to_crs("EPSG:4326")
    selection = {
        "national_feature_class": layer,
        "state_filter": state_filter,
        "state_filter_column": state_column,
        "south_carolina_feature_count_read": south_carolina_count,
        "national_feature_class_loaded_in_full": False,
        "county_attribute": county_column,
        "selected_county": selected_county,
        "selected_county_fips": selected_county_fips,
        "eligible_fields_in_selected_county": county_eligible_count,
        "selected_field_count": len(output),
    }
    return output, selection


def raster_url(response: requests.Response) -> str:
    if not response.ok:
        raise RuntimeError(f"CDL service failed: GET {response.url}; HTTP {response.status_code}; response={response.text[:4000]!r}")
    match = re.search(r"https?://[^<\s\"']+\.(?:tif|tiff|zip)", response.text, re.I)
    if not match:
        # Axis2 commonly returns <returnURL>...</returnURL>.
        match = re.search(r"<(?:returnURL|return)>\s*([^<]+)\s*</", response.text, re.I)
    if not match:
        raise RuntimeError(f"CDL service returned no raster URL: GET {response.url}; HTTP {response.status_code}; response={response.text[:4000]!r}")
    return html.unescape(match.group(1))


def validate_cdl_raster(path: Path) -> dict:
    """Reject empty, HTML, malformed, CRS-less, and non-USDA-Albers files."""
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("downloaded raster is empty")
    with path.open("rb") as stream:
        signature = stream.read(16).lstrip().lower()
    if signature.startswith((b"<html", b"<!doctype", b"<?xml")):
        raise ValueError("downloaded content is HTML/XML, not a GeoTIFF")
    with rasterio.open(path) as dataset:
        if dataset.crs is None:
            raise ValueError("raster has no CRS")
        if dataset.count < 1 or dataset.width <= 0 or dataset.height <= 0:
            raise ValueError("raster has invalid bands or dimensions")
        raster_crs = PyprojCRS.from_user_input(dataset.crs)
        if not raster_crs.equals(PyprojCRS.from_epsg(5070), ignore_axis_order=True):
            raise ValueError(f"raster CRS is not equivalent to USDA Albers EPSG:5070: {dataset.crs}")
        return {"byte_size": path.stat().st_size, "sha256": sha256(path),
                "raster_crs": dataset.crs.to_string(), "raster_epsg": raster_crs.to_epsg(),
                "raster_width": dataset.width, "raster_height": dataset.height,
                "raster_band_count": dataset.count}


def save_stream(response: requests.Response, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def attempt_record(method: str, request_method: str, url: str, parameters: dict, number: int) -> dict:
    return {"method": method, "http_method": request_method, "request_url": url,
            "request_parameters": parameters, "attempt_number": number,
            "attempted_utc": now(), "success": False}


def direct_county_cache(s: requests.Session, year: int, county_fips: str,
                        path: Path, attempts: list[dict]) -> dict | None:
    url = CDL_COUNTY_CACHE.format(year=year, fips=county_fips)
    record = attempt_record("direct_county_cache", "GET", url, {}, 1)
    attempts.append(record)
    try:
        with s.get(url, timeout=(30, 600), stream=True) as response:
            final_url = response.url
            record.update({"request_url": final_url, "http_status": response.status_code})
            if response.status_code != 200:
                record["error"] = f"HTTP {response.status_code}: {response.text[:1000]!r}"
                return None
            save_stream(response, path)
        raster = validate_cdl_raster(path)
        record.update({"success": True, "raster_url": final_url, **raster})
        return {"successful_method": record["method"], "final_raster_url": final_url, **raster}
    except Exception as error:
        path.unlink(missing_ok=True)
        record.update({"exception_type": type(error).__name__, "exception_message": str(error)})
        return None


def service_route(s: requests.Session, year: int, county_fips: str, path: Path,
                  attempts: list[dict], method_name: str, http_method: str,
                  parameters: dict) -> dict | None:
    retry_statuses = {429, 500, 502, 503, 504}
    delays = (0, 15, 30)
    for number, delay in enumerate(delays, 1):
        if delay:
            print(f"{method_name} retry backoff: {delay} seconds", flush=True)
            time.sleep(delay)
        record = attempt_record(method_name, http_method, CDL_SERVICE, parameters, number)
        attempts.append(record)
        service_status = None
        raster_status = None
        retry = False
        try:
            kwargs = {"params": parameters} if http_method == "GET" else {"data": parameters}
            headers = {"Content-Type": "application/x-www-form-urlencoded"} if http_method == "POST" else None
            with s.request(http_method, CDL_SERVICE, headers=headers, timeout=(30, 300), **kwargs) as response:
                service_status = response.status_code
                record.update({"request_url": response.url, "http_status": service_status})
                if service_status != 200:
                    record["error"] = f"HTTP {service_status}: {response.text[:1000]!r}"
                    retry = service_status in retry_statuses
                else:
                    generated_url = urljoin(response.url, raster_url(response))
                    record["raster_url"] = generated_url
                    with s.get(generated_url, timeout=(30, 600), stream=True) as raster_response:
                        raster_status = raster_response.status_code
                        record["raster_http_status"] = raster_status
                        if raster_status != 200:
                            record["error"] = f"Raster HTTP {raster_status}: {raster_response.text[:1000]!r}"
                            retry = raster_status in retry_statuses
                        else:
                            save_stream(raster_response, path)
                    if raster_status == 200:
                        raster = validate_cdl_raster(path)
                        record.update({"success": True, **raster})
                        return {"successful_method": method_name, "final_raster_url": generated_url, **raster}
        except (requests.ConnectionError, requests.ReadTimeout) as error:
            retry = True
            record.update({"exception_type": type(error).__name__, "exception_message": str(error)})
        except Exception as error:
            record.update({"exception_type": type(error).__name__, "exception_message": str(error)})
            retry = False
        path.unlink(missing_ok=True)
        if not retry:
            break
    return None


def acquire_cdl_raster(s: requests.Session, fields: gpd.GeoDataFrame, year: int,
                       county_fips: str) -> tuple[Path, dict]:
    path = RASTERS / f"CDL_{year}_{county_fips}.tif"
    path.unlink(missing_ok=True)
    attempts: list[dict] = []
    successful = direct_county_cache(s, year, county_fips, path, attempts)
    if successful is None:
        successful = service_route(s, year, county_fips, path, attempts,
                                   "county_fips_service_get", "GET",
                                   {"year": year, "fips": county_fips})
    if successful is None:
        successful = service_route(s, year, county_fips, path, attempts,
                                   "county_fips_service_post", "POST",
                                   {"year": year, "fips": county_fips})
    if successful is None:
        bounds = fields.to_crs("EPSG:5070").total_bounds
        successful = service_route(s, year, county_fips, path, attempts,
                                   "bounding_box_service_get", "GET",
                                   {"year": year, "bbox": ",".join(f"{value:.3f}" for value in bounds)})
    if successful is None:
        raise RuntimeError(
            f"All official CDL acquisition routes failed for year={year}, county_fips={county_fips}; "
            f"attempts={json.dumps(attempts)}; no outputs will be published"
        )
    metadata = {"year": year, "selected_county_fips": county_fips,
                "attempts": attempts, **successful}
    return path, metadata


def extract_cdl(s: requests.Session, fields: gpd.GeoDataFrame, year: int,
                county_fips: str) -> tuple[list[dict], dict]:
    raster_path, request_meta = acquire_cdl_raster(s, fields, year, county_fips)
    rows = []
    with rasterio.open(raster_path) as dataset:
        projected = fields.to_crs(dataset.crs)
        nodata = dataset.nodata
        for (_, original), (_, feature) in zip(fields.iterrows(), projected.iterrows()):
            pixels, _ = mask(dataset, [feature.geometry.__geo_interface__], crop=True, all_touched=False)
            values = pixels[0].reshape(-1)
            valid = values != 0
            if nodata is not None:
                valid &= values != nodata
            values = values[valid].astype(int)
            if not len(values):
                raise RuntimeError(f"No valid {year} CDL raster pixels for CSBID {original.field_id}")
            counts = Counter(values.tolist())
            code, dominant = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
            csb_code = int(original[f"CDL{year}"])
            rows.append({"field_id": original.field_id, "year": year, "crop_code": code,
                "crop_name": CDL_NAMES.get(code, f"USDA CDL class {code}"), "valid_pixel_count": len(values),
                "dominant_pixel_count": dominant, "dominant_pct": round(dominant * 100 / len(values), 6),
                "extraction_method": "rasterio.mask; pixel-center (all_touched=False); zero/nodata excluded",
                "csb_annual_cdl_code": csb_code, "matches_csb_annual_cdl": code == csb_code,
                "raster_source_url": request_meta["final_raster_url"],
                "raster_sha256": request_meta["sha256"]})
    return rows, request_meta


def geojson(frame: gpd.GeoDataFrame, path: Path) -> None:
    path.write_text(frame.to_json(drop_id=True) + "\n", encoding="utf-8")


def joined_products(fields: gpd.GeoDataFrame, cdl: pd.DataFrame, stage: Path) -> gpd.GeoDataFrame:
    result = fields.copy()
    for year in YEARS:
        annual = cdl[cdl.year == year].set_index("field_id")
        for source, target in (("crop_code",f"crop_code_{year}"),("crop_name",f"crop_{year}"),
                               ("dominant_pct",f"dominant_pct_{year}"),("valid_pixel_count",f"valid_pixels_{year}"),
                               ("matches_csb_annual_cdl",f"matches_csb_{year}")):
            result[target] = result.field_id.map(annual[source])
    geojson(result, stage / "fields_with_crops.geojson")
    result.drop(columns="geometry").to_csv(stage / "field_summary.csv", index=False)
    return result


def popup_html(row) -> str:
    lines = [f"<b>CSBID / field_id:</b> {html.escape(str(row.field_id))}",
             f"<b>County:</b> {html.escape(str(row.county))}", f"<b>Acreage:</b> {row.CSBACRES}"]
    lines += [f"<b>{year}:</b> {html.escape(str(row[f'crop_{year}']))} — {row[f'dominant_pct_{year}']:.2f}% ({row[f'valid_pixels_{year}']} valid pixels)" for year in YEARS]
    return "<br>".join(lines)


def make_map(fields: gpd.GeoDataFrame, stage: Path) -> None:
    bounds = fields.total_bounds
    center = [(bounds[1]+bounds[3])/2, (bounds[0]+bounds[2])/2]
    map_ = folium.Map(location=center, tiles=None, control_scale=True, prefer_canvas=True)
    folium.TileLayer("CartoDB positron", name="CartoDB Positron", overlay=False, control=True, show=True).add_to(map_)
    layers = []
    for year in YEARS:
        layer = folium.FeatureGroup(name=f"{year} crops", overlay=True, control=False, show=year == 2023)
        for _, row in fields.iterrows():
            code = int(row[f"crop_code_{year}"])
            color = COLORS.get(code, "#756bb1")
            tooltip = (f"field_id: {row.field_id}<br>selected year: {year}<br>"
                       f"crop: {html.escape(str(row[f'crop_{year}']))}<br>dominant: {row[f'dominant_pct_{year}']:.2f}%")
            folium.GeoJson(row.geometry.__geo_interface__, style_function=lambda _f, c=color: {
                "color":"#263238", "weight":1, "fillColor":c, "fillOpacity":0.72},
                tooltip=tooltip, popup=folium.Popup(popup_html(row), max_width=520)).add_to(layer)
        layer.add_to(map_); layers.append(layer)
    GroupedLayerControl(groups={"Crop year": layers}, exclusive_groups=True, collapsed=False).add_to(map_)
    Fullscreen(position="topright").add_to(map_)
    map_.fit_bounds([[bounds[1],bounds[0]],[bounds[3],bounds[2]]])
    title = """<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;background:white;padding:8px 16px;border:1px solid #777"><b>Assignment 02 — USDA CSB fields and raster CDL crops</b><br><small>Use the Crop year radio selector; 2023 is shown initially.</small></div>"""
    legend = "".join(f'<span><i style="display:inline-block;width:12px;height:12px;background:{COLORS.get(code,"#756bb1")};margin:0 4px 0 10px"></i>{name}</span>' for code,name in sorted({int(r[f"crop_code_{y}"]):r[f"crop_{y}"] for _,r in fields.iterrows() for y in YEARS}.items()))
    map_.get_root().html.add_child(folium.Element(title + f'<div style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;padding:10px;border:1px solid #777"><b>USDA CDL dominant crop</b><br>{legend}</div>'))
    map_.save(stage / "my_fields_map.html")


def make_svg(fields: gpd.GeoDataFrame, stage: Path) -> None:
    bounds = fields.total_bounds
    def points(geometry, x0, y0):
        ring = geometry.geoms[0].exterior if geometry.geom_type == "MultiPolygon" else geometry.exterior
        return " ".join(f"{x0 + (x-bounds[0])/(bounds[2]-bounds[0])*430:.1f},{y0+190-(y-bounds[1])/(bounds[3]-bounds[1])*170:.1f}" for x,y in ring.coords)
    panels=[]
    for index, year in enumerate(YEARS):
        x0=30+(index%2)*480; y0=55+(index//2)*245
        polygons="".join(f'<polygon points="{points(row.geometry,x0,y0)}" fill="{COLORS.get(int(row[f"crop_code_{year}"]),"#756bb1")}" stroke="#263238" stroke-width=".5"/>' for _,row in fields.iterrows())
        panels.append(f'<text x="{x0}" y="{y0-12}" font-size="20" font-weight="bold">{year}</text><rect x="{x0}" y="{y0}" width="430" height="190" fill="#f7f7f7" stroke="#777"/>{polygons}')
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="550"><rect width="100%" height="100%" fill="white"/><text x="30" y="30" font-family="sans-serif" font-size="22" font-weight="bold">USDA CSB fields — actual raster CDL dominant crops</text><g font-family="sans-serif">{"".join(panels)}</g></svg>'
    (stage / "evidence").mkdir(parents=True, exist_ok=True)
    (stage / "evidence/my_fields_map_preview.svg").write_text(svg, encoding="utf-8")


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True); RASTERS.mkdir(parents=True, exist_ok=True)
    s = session(); archive = DOWNLOADS / "NationalCSB_2016-2023_rev23.zip"
    archive_meta = acquire_csb_archive(s, archive)
    with tempfile.TemporaryDirectory(dir=DOWNLOADS, prefix="csb_extract_") as directory:
        with zipfile.ZipFile(archive) as zipped: zipped.extractall(directory)
        database, layer, schema = find_layer(Path(directory))
        fields, selection = select_fields(database, layer, schema)
    request_bounds = fields.to_crs("EPSG:5070").total_bounds
    selection["cdl_request_bbox_epsg5070"] = [round(float(value), 3) for value in request_bounds]
    selection["cdl_request_bbox_width_m"] = round(float(request_bounds[2] - request_bounds[0]), 3)
    selection["cdl_request_bbox_height_m"] = round(float(request_bounds[3] - request_bounds[1]), 3)
    all_rows=[]; raster_requests=[]
    for year in YEARS:
        rows, metadata = extract_cdl(s, fields, year, selection["selected_county_fips"])
        all_rows.extend(rows); raster_requests.append(metadata)
    cdl = pd.DataFrame(all_rows)
    if len(cdl) != 100: raise RuntimeError(f"Expected 100 field-year extractions, got {len(cdl)}")
    with tempfile.TemporaryDirectory(dir=ASSIGNMENT, prefix="publish_stage_") as directory:
        stage=Path(directory); (stage/"output").mkdir(); (stage/"evidence").mkdir()
        geojson(fields, stage/"fields_EPSG4326.geojson"); cdl.to_csv(stage/"cdl_EPSG4326.csv",index=False)
        joined=joined_products(fields,cdl,stage); make_map(joined,stage); make_svg(joined,stage)
        disagreements=cdl.loc[~cdl.matches_csb_annual_cdl,["field_id","year","csb_annual_cdl_code","crop_code"]].to_dict("records")
        provenance={"generated_utc":now(),"boundary_source":archive_meta,"feature_class":{"geodatabase":database.name,"layer":layer,"schema":schema},"field_selection":selection,"raster_requests":raster_requests}
        summary={**provenance,"state":"South Carolina","STATEFIPS":"45","field_count":25,"years":list(YEARS),"matched_fields":25,"unmatched_fields":0,"raster_csb_disagreement_count":len(disagreements),"raster_csb_disagreements":disagreements}
        (stage/"output/assignment_02_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
        env={"generated_utc":now(),"python":platform.python_version(),"platform":platform.platform(),
             "gdal_configuration":{"OGR_ORGANIZE_POLYGONS":os.environ.get("OGR_ORGANIZE_POLYGONS")},
             "dependencies":{d.metadata["Name"]:d.version for d in distributions() if d.metadata["Name"]}}
        (stage/"output/environment.json").write_text(json.dumps(env,indent=2)+"\n")
        log=[f"{now()} official USDA real-data build completed",f"CSB {archive_meta['final_url']} HTTP {archive_meta['http_status']} bytes={archive_meta['byte_size']} sha256={archive_meta['sha256']}",f"feature_class={layer} schema={json.dumps(schema,sort_keys=True)}"]
        log += [f"CDL {r['year']} county_fips={r['selected_county_fips']} method={r['successful_method']} raster={r['final_raster_url']} bytes={r['byte_size']} sha256={r['sha256']} attempts={json.dumps(r['attempts'])}" for r in raster_requests]
        log += ["fields=25 field_year_rows=100 unmatched=0",f"raster_vs_csb_disagreements={len(disagreements)} details={json.dumps(disagreements)}"]
        (stage/"output/skill_run.log").write_text("\n".join(log)+"\n")
        terminal="<svg xmlns='http://www.w3.org/2000/svg' width='1100' height='260'><rect width='100%' height='100%' fill='#111827'/><g fill='#d1fae5' font-family='monospace' font-size='14'>"+"".join(f"<text x='20' y='{25+i*22}'>{html.escape(line[:140])}</text>" for i,line in enumerate(log[:10]))+"</g></svg>"
        (stage/"evidence/terminal_evidence.svg").write_text(terminal)
        readme=f"""# Assignment 02 — Official USDA real-data build

These products contain 25 genuine South Carolina (`STATEFIPS=45`) polygons selected deterministically by `CSBID` from USDA NASS National Crop Sequence Boundaries 2016–2023 rev. 23. Geometry is retained from the source and reprojected only to EPSG:4326.

The four annual classifications are dominant nonzero pixels extracted with `rasterio.mask` from validated official county CDL GeoTIFFs. Direct county cache files are preferred, county-FIPS GET and POST service calls are secondary, and the bounding-box service is only the final fallback. HTTP 502 and other failed attempts are logged and can never trigger synthetic substitution. The CSB annual attributes are retained only for comparison. There are **{len(disagreements)}** raster/CSB code disagreements (listed in `output/assignment_02_summary.json`), **0** unmatched fields, and 100 field-year rows. Percentages depend on pixel-center inclusion at the 30 m raster resolution and small or edge fields can legitimately differ from the CSB annual attribute.

Source archive: `{archive_meta['final_url']}` ({archive_meta['byte_size']} bytes; SHA-256 `{archive_meta['sha256']}`; accessed {archive_meta['accessed_utc']}). Exact raster requests, redirects, sizes, checksums, schema, and disagreement records are in `output/assignment_02_summary.json`.
"""
        (stage/"README.md").write_text(readme)
        tracker=f"""# Assignment 02 tracker

- Status: real USDA build complete at {now()}.
- Boundaries: 25 official CSBID records for STATEFIPS 45; source geometry unchanged except CRS reprojection.
- CDL: validated official county rasters for 2020–2023; direct cache preferred, county-FIPS services next, bounding-box service last; 100 raster zonal extractions.
- Join: 25 matched, 0 unmatched.
- Raster/CSB annual-code disagreements: {len(disagreements)}; see the summary JSON for every record.
- Limitations: 30 m pixel-center extraction can differ at boundaries; the CDL service clip covers the combined selected-field bounding box.
"""
        (stage/"assignment-02-tracker.md").write_text(tracker)
        publish=["fields_EPSG4326.geojson","cdl_EPSG4326.csv","fields_with_crops.geojson","field_summary.csv","my_fields_map.html","README.md","evidence/my_fields_map_preview.svg","evidence/terminal_evidence.svg","output/environment.json","output/skill_run.log","output/assignment_02_summary.json"]
        for relative in publish:
            destination=ASSIGNMENT/relative; destination.parent.mkdir(parents=True,exist_ok=True); os.replace(stage/relative,destination)
        shutil.copy2(stage/"assignment-02-tracker.md",ROOT/"docs/project/assignment-02-tracker.md")
    print("Published 25 official fields and 100 genuine raster extractions.")


if __name__ == "__main__":
    try: main()
    except Exception as error:
        print(f"FATAL: {error}",file=sys.stderr,flush=True)
        raise
