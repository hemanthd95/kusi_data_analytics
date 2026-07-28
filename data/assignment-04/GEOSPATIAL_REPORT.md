# Assignment 4 Geospatial Report

## Data and provenance

The authoritative field input is `data/assignment-02/fields_EPSG4326.geojson` (25 fields). The soil source is a genuine official USDA-NRCS Soil Data Access WFS 1.1 feature collection (`MapunitPolyExtended`, 794,318 bytes). It was obtained externally because Codex's proxy blocked direct acquisition, then independently verified against SHA-256 `f7b9e32f…46ab5c`. The successful metadata records HTTP 200. The completed analysis is offline and performs zero requests.

## Methods

The GML schema contains 45 columns, including `mukey`, `musym`, `aws025wta`, and MultiPolygon geometry. WFS latitude/longitude axis order was normalized to conventional longitude/latitude. Three invalid field geometries were repaired in a temporary GeoDataFrame with `make_valid`; the source was untouched and all polygonal components and 25 IDs were retained. Areas were calculated in EPSG:32617.

The regenerated 500 m dissolved buffer had 0.000 m² symmetric difference from the external reference. Of 145 parsed polygon features, 92 intersected the buffer, representing 22 map units. Polygon-field overlay supplied square meters, acres, percent of field, uncovered percent, and area weights.

## Soil attribute and findings

The selected `aws025wta` is **available water storage from 0–25 cm, weighted average of map-unit components**, in **centimeters of water**. Among clipped polygons, 11 of 92 (11.96%) are missing; missing values remain null. The 81 observed polygon values have mean 3.123, standard deviation 0.282, median 2.990, and range 2.000–3.630 cm.

All 25 fields received a valued area-weighted result; 21 intersect multiple map units. Field results average 3.114 cm (SD 0.316), range 2.044–3.500 cm. Field `451623001001187` is highest (3.500 cm); `451623001001160` is lowest (2.044 cm). Average field polygon coverage is 100.000%, and minimum coverage is 100.000% (floating-point tolerance).

## Interpretation and limitations

Higher AWS indicates greater modeled water storage in the surface 25 cm. These are map-unit interpretations, not field sampling. Boundaries and attributes inherit SSURGO scale, generalization, component weighting, and temporal limitations. A field's weighted value excludes intersected map-unit area lacking `aws025wta`; the separate valued-coverage column makes that limitation auditable.

## Outputs

Four paired PNG/SVG analytical maps include context, choropleth, buffer comparison, and a 25-field final panel with a table. A paired dashboard map, standalone Leaflet HTML, detailed intersection/field/map-unit tables, executed notebook, and `spatial_quality_summary.json` support reuse and review.
