#!/usr/bin/env python3
"""Dependency-light structural and consistency checks for Assignment 02."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def need(ok,msg):
 if not ok: raise AssertionError(msg)
 print(f'PASS: {msg}')
fields=json.loads((ROOT/'fields_EPSG4326.geojson').read_text()); merged=json.loads((ROOT/'fields_with_crops.geojson').read_text())
features=fields['features']; ids=[f['properties']['field_id'] for f in features]
need(20<=len(features)<=30,'20-30 fields are present')
need(all(f.get('geometry',{}).get('type') in ('Polygon','MultiPolygon') and f['geometry'].get('coordinates') for f in features),'all geometries are nonempty polygons')
need(all(len(f['geometry']['coordinates'][0])>=4 and f['geometry']['coordinates'][0][0]==f['geometry']['coordinates'][0][-1] for f in features),'polygon rings are structurally valid and closed')
crs=json.dumps(fields.get('crs',{})).upper(); need('4326' in crs,'CRS is EPSG:4326')
need(len(ids)==len(set(ids)),'field_id values are unique')
with (ROOT/'cdl_EPSG4326.csv').open(newline='') as fh: rows=list(csv.DictReader(fh))
required={'field_id','year','crop_code','crop_name','dominant_pct'}
need(required<=set(rows[0]),'CDL contains required columns')
need({int(r['year']) for r in rows}=={2020,2021,2022,2023},'CDL contains exactly 2020-2023')
need(len(rows)==len(features)*4,'CDL has four records per field')
need({r['field_id'] for r in rows}==set(ids),'all fields have CDL matches')
summary=json.loads((ROOT/'output/assignment_02_summary.json').read_text())
need(summary['expected_merge_fields']==len(features)==summary['actual_merge_fields']==summary['matched_fields'],'documented merge counts are internally consistent')
need(summary['unmatched_fields']==0 and len(merged['features'])==len(features),'merged output has 25 matches and no unmatched fields')
need((ROOT/'my_fields_map.html').stat().st_size>1000,'interactive HTML exists and is nonempty')
need((ROOT/'README.md').exists() and (ROOT.parents[1]/'docs/project/assignment-02-tracker.md').exists(),'README and tracker exist')
need((ROOT/'evidence/my_fields_map_preview.svg').exists() and (ROOT/'evidence/terminal_evidence.svg').exists(),'SVG map and terminal evidence exist')
need('source' in features[0]['properties'] and 'boundary_source' in summary and 'cdl_source' in summary,'provenance information exists')
print('Assignment 02 verification passed.')
