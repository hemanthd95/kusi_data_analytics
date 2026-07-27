#!/usr/bin/env python3
"""Render the included two-field GeoJSON as a deterministic, text-only SVG."""

from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "skills" / "field-boundaries" / "examples" / "sample_2_fields.geojson"
OUTPUT = Path(__file__).resolve().parent / "evidence" / "field-boundaries-sample-map.svg"


def polygon_points(ring: list[list[float]], x: float, y: float, width: float, height: float) -> str:
    """Fit one longitude/latitude ring into a panel while retaining its shape."""
    longitudes = [point[0] for point in ring]
    latitudes = [point[1] for point in ring]
    min_lon, max_lon = min(longitudes), max(longitudes)
    min_lat, max_lat = min(latitudes), max(latitudes)
    lon_span, lat_span = max_lon - min_lon, max_lat - min_lat
    scale = min(width / lon_span, height / lat_span)
    used_width, used_height = lon_span * scale, lat_span * scale
    offset_x = x + (width - used_width) / 2
    offset_y = y + (height - used_height) / 2
    return " ".join(
        f"{offset_x + (lon - min_lon) * scale:.3f},{offset_y + (max_lat - lat) * scale:.3f}"
        for lon, lat in ring
    )


def render(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    """Render every sample polygon in a labeled panel and return the output path."""
    source_bytes = source.read_bytes()
    features = json.loads(source_bytes)["features"]
    if len(features) != 2:
        raise ValueError(f"Expected two sample features, found {len(features)}")

    panels = []
    for index, feature in enumerate(features):
        properties = feature["properties"]
        ring = feature["geometry"]["coordinates"][0]
        panel_x = 70 + index * 560
        points = polygon_points(ring, panel_x + 35, 160, 430, 340)
        panels.append(
            f'''<g id="field-{escape(properties["field_id"])}">
  <rect x="{panel_x}" y="120" width="500" height="470" rx="12" class="panel"/>
  <polygon points="{points}" class="field"/>
  <text x="{panel_x + 250}" y="545" text-anchor="middle" class="label">Field {escape(properties["field_id"])}</text>
  <text x="{panel_x + 250}" y="572" text-anchor="middle" class="detail">{escape(properties["crop_name"])} — {properties["area_acres"]:.6f} acres</text>
</g>'''
        )

    digest = hashlib.sha256(source_bytes).hexdigest()
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680">
<title>Two field boundaries from the imported field-boundaries sample</title>
<desc>Reproducibly rendered from {SOURCE.relative_to(ROOT)}; SHA-256 {digest}</desc>
<rect width="1200" height="680" fill="#f5f8f3"/>
<text x="600" y="55" text-anchor="middle" class="title">Imported field-boundaries skill — included sample polygons</text>
<text x="600" y="88" text-anchor="middle" class="subtitle">Two USDA NASS sample fields; each panel is fitted independently for visibility</text>
<style>
.title {{ font: bold 26px sans-serif; fill: #183a25; }}
.subtitle, .detail {{ font: 16px sans-serif; fill: #4a6251; }}
.panel {{ fill: #fff; stroke: #b9c8bc; stroke-width: 2; }}
.field {{ fill: #78b76b; stroke: #245c32; stroke-width: 3; }}
.label {{ font: bold 17px monospace; fill: #183a25; }}
</style>
{''.join(panels)}
<text x="600" y="640" text-anchor="middle" class="detail">Source SHA-256: {digest}</text>
</svg>
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(f"wrote {render().relative_to(ROOT)}")
