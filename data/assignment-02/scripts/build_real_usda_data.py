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
import rasterio
from rasterio.mask import mask
import requests

ROOT = Path(__file__).resolve().parents[3]
ASSIGNMENT = ROOT / "data" / "assignment-02"
DOWNLOADS = ASSIGNMENT / "source_downloads"
RASTERS = ASSIGNMENT / "rasters"
CSB_URL = "https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/datasets/NationalCSB_2016-2023_rev23.zip"
CDL_SERVICE = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLFile"
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
    adapter = requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(
        total=5, connect=5, read=5, backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",)))
    s.mount("https://", adapter)
    return s


def download(s: requests.Session, url: str, path: Path, params=None) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with s.get(url, params=params, timeout=(30, 600), stream=True) as response:
        print(f"GET {response.url} -> HTTP {response.status_code}", flush=True)
        if not response.ok:
            body = response.text[:4000]
            raise RuntimeError(f"Official download failed: GET {response.url}; HTTP {response.status_code}; response={body!r}")
        with path.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)
        return {"requested_url": url, "final_url": response.url, "http_status": response.status_code,
                "byte_size": path.stat().st_size, "sha256": sha256(path), "accessed_utc": now()}


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


def select_fields(database: Path, layer: str) -> gpd.GeoDataFrame:
    all_fields = gpd.read_file(database, layer=layer, engine="pyogrio")
    lookup = {column.upper(): column for column in all_fields.columns}
    required = ["CSBID", "STATEFIPS", *(f"CDL{year}" for year in YEARS)]
    missing = [name for name in required if name not in lookup]
    if missing:
        raise RuntimeError(f"CSB feature class is missing required attributes: {missing}")
    state = all_fields[all_fields[lookup["STATEFIPS"]].astype(str).str.zfill(2) == "45"].copy()
    state = state[state.geometry.notna() & ~state.geometry.is_empty]
    for year in YEARS:
        state[f"_valid_{year}"] = pd.to_numeric(state[lookup[f"CDL{year}"]], errors="coerce").fillna(0).gt(0)
    state["_all_valid"] = state[[f"_valid_{year}" for year in YEARS]].all(axis=1)
    state["_sort_id"] = state[lookup["CSBID"]].astype(str)
    state = state.sort_values(["_all_valid", "_sort_id"], ascending=[False, True], kind="stable").head(25)
    if len(state) != 25 or not state["_all_valid"].all():
        raise RuntimeError(f"Could not select 25 SC polygons with nonzero CDL2020-CDL2023; found {int(state['_all_valid'].sum())}")
    output = gpd.GeoDataFrame({
        "field_id": state[lookup["CSBID"]].astype(str), "CSBID": state[lookup["CSBID"]].astype(str),
        "STATEFIPS": state[lookup["STATEFIPS"]].astype(str).str.zfill(2),
        "CSBACRES": state[lookup["CSBACRES"]] if "CSBACRES" in lookup else np.nan,
        "county": state[lookup.get("COUNTY", lookup.get("COUNTYNAME"))] if ("COUNTY" in lookup or "COUNTYNAME" in lookup) else "",
        "source_attribute": state[lookup["SOURCE"]] if "SOURCE" in lookup else "",
        **{f"CDL{year}": pd.to_numeric(state[lookup[f"CDL{year}"]], errors="raise").astype(int) for year in YEARS},
        "geometry": state.geometry,
    }, crs=state.crs)
    if output.field_id.duplicated().any():
        raise RuntimeError("Selected CSBID values are not unique")
    # Reprojection is the only geometry transformation; no construction,
    # simplification, buffering, shifting, or coordinate editing occurs.
    return output.to_crs("EPSG:4326")


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


def extract_cdl(s: requests.Session, fields: gpd.GeoDataFrame, year: int) -> tuple[list[dict], dict]:
    bounds = fields.to_crs("EPSG:5070").total_bounds
    params = {"year": year, "bbox": ",".join(f"{value:.3f}" for value in bounds)}
    response = s.get(CDL_SERVICE, params=params, timeout=(30, 300))
    print(f"GET {response.url} -> HTTP {response.status_code}", flush=True)
    url = raster_url(response)
    raster_path = RASTERS / f"CDL_{year}_selected_fields.tif"
    raster_meta = download(s, urljoin(response.url, url), raster_path)
    request_meta = {"year": year, "service_url": CDL_SERVICE, "request_url": response.url,
                    "request_parameters": params, "response_status": response.status_code, **raster_meta}
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
                "raster_source_url": raster_meta["final_url"], "raster_sha256": raster_meta["sha256"]})
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
    archive_meta = download(s, CSB_URL, archive)
    with tempfile.TemporaryDirectory(dir=DOWNLOADS, prefix="csb_extract_") as directory:
        with zipfile.ZipFile(archive) as zipped: zipped.extractall(directory)
        database, layer, schema = find_layer(Path(directory))
        fields = select_fields(database, layer)
    all_rows=[]; raster_requests=[]
    for year in YEARS:
        rows, metadata = extract_cdl(s, fields, year); all_rows.extend(rows); raster_requests.append(metadata)
    cdl = pd.DataFrame(all_rows)
    if len(cdl) != 100: raise RuntimeError(f"Expected 100 field-year extractions, got {len(cdl)}")
    with tempfile.TemporaryDirectory(dir=ASSIGNMENT, prefix="publish_stage_") as directory:
        stage=Path(directory); (stage/"output").mkdir(); (stage/"evidence").mkdir()
        geojson(fields, stage/"fields_EPSG4326.geojson"); cdl.to_csv(stage/"cdl_EPSG4326.csv",index=False)
        joined=joined_products(fields,cdl,stage); make_map(joined,stage); make_svg(joined,stage)
        disagreements=cdl.loc[~cdl.matches_csb_annual_cdl,["field_id","year","csb_annual_cdl_code","crop_code"]].to_dict("records")
        provenance={"generated_utc":now(),"boundary_source":archive_meta,"feature_class":{"geodatabase":database.name,"layer":layer,"schema":schema},"raster_requests":raster_requests}
        summary={**provenance,"state":"South Carolina","STATEFIPS":"45","field_count":25,"years":list(YEARS),"matched_fields":25,"unmatched_fields":0,"raster_csb_disagreement_count":len(disagreements),"raster_csb_disagreements":disagreements}
        (stage/"output/assignment_02_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
        env={"generated_utc":now(),"python":platform.python_version(),"platform":platform.platform(),"dependencies":{d.metadata["Name"]:d.version for d in distributions() if d.metadata["Name"]}}
        (stage/"output/environment.json").write_text(json.dumps(env,indent=2)+"\n")
        log=[f"{now()} official USDA real-data build completed",f"CSB {archive_meta['final_url']} HTTP {archive_meta['http_status']} bytes={archive_meta['byte_size']} sha256={archive_meta['sha256']}",f"feature_class={layer} schema={json.dumps(schema,sort_keys=True)}"]
        log += [f"CDL {r['year']} request={r['request_url']} HTTP={r['response_status']} raster={r['final_url']} bytes={r['byte_size']} sha256={r['sha256']}" for r in raster_requests]
        log += ["fields=25 field_year_rows=100 unmatched=0",f"raster_vs_csb_disagreements={len(disagreements)} details={json.dumps(disagreements)}"]
        (stage/"output/skill_run.log").write_text("\n".join(log)+"\n")
        terminal="<svg xmlns='http://www.w3.org/2000/svg' width='1100' height='260'><rect width='100%' height='100%' fill='#111827'/><g fill='#d1fae5' font-family='monospace' font-size='14'>"+"".join(f"<text x='20' y='{25+i*22}'>{html.escape(line[:140])}</text>" for i,line in enumerate(log[:10]))+"</g></svg>"
        (stage/"evidence/terminal_evidence.svg").write_text(terminal)
        readme=f"""# Assignment 02 — Official USDA real-data build

These products contain 25 genuine South Carolina (`STATEFIPS=45`) polygons selected deterministically by `CSBID` from USDA NASS National Crop Sequence Boundaries 2016–2023 rev. 23. Geometry is retained from the source and reprojected only to EPSG:4326.

The four annual classifications are dominant nonzero pixels extracted with `rasterio.mask` from official CDL service clips. The CSB annual attributes are retained for comparison. There are **{len(disagreements)}** raster/CSB code disagreements (listed in `output/assignment_02_summary.json`), **0** unmatched fields, and 100 field-year rows. Percentages depend on pixel-center inclusion at the 30 m raster resolution and small or edge fields can legitimately differ from the CSB annual attribute.

Source archive: `{archive_meta['final_url']}` ({archive_meta['byte_size']} bytes; SHA-256 `{archive_meta['sha256']}`; accessed {archive_meta['accessed_utc']}). Exact raster requests, redirects, sizes, checksums, schema, and disagreement records are in `output/assignment_02_summary.json`.
"""
        (stage/"README.md").write_text(readme)
        tracker=f"""# Assignment 02 tracker

- Status: real USDA build complete at {now()}.
- Boundaries: 25 official CSBID records for STATEFIPS 45; source geometry unchanged except CRS reprojection.
- CDL: official clipped rasters for 2020–2023; 100 raster zonal extractions.
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
