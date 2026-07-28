"""Independent acceptance checks for Assignment 4 outputs."""
import hashlib,json
from pathlib import Path
from PIL import Image
import pandas as pd
import nbformat

REPO=Path(__file__).resolve().parents[2]; A4=REPO/'data/assignment-04'; O=A4/'output'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
expected={'ssurgo_mapunit_response.gml':'f7b9e32fb7f575f814739a7cefffc7fb0695b829e56f518a56f93bfddd46ab5c','ssurgo_request_metadata.json':'b361a28525bd10d4e4c1c65551b954ebf0a29de0f274af47d6de6610106960e8','field_buffer_500m_external.geojson':'3ed7c3487e1714fc71ac641f59748557a1078a57b09e3a31eb031ddf1dc71e9f'}
for n,h in expected.items():
 p=A4/'source'/n; assert p.is_file() and sha(p)==h,n
q=json.loads((O/'spatial_quality_summary.json').read_text()); assert q['offline'] and q['network_requests']==0
assert q['field_count']==25 and q['field_geometry_repairs']==3 and q['parsed_polygon_features']>0 and q['clipped_polygon_features']>0
assert q['attribute']=='aws025wta' and q['unique_map_units']>1
required=['01_field_boundaries_and_ssurgo_context','02_ssurgo_attribute_choropleth','03_buffer_operation','04_final_assignment_panel']
for stem in required:
 for ext in ('png','svg'): assert (O/'maps'/f'{stem}.{ext}').stat().st_size>1000
assert Image.open(O/'maps/04_final_assignment_panel.png').size[0]>=2400 and Image.open(O/'maps/04_final_assignment_panel.png').size[1]>=1800
for ext in ('png','svg'): assert (O/'dashboard_assets'/f'dashboard_ssurgo_field_variability_map.{ext}').stat().st_size>1000
assert Image.open(O/'dashboard_assets/dashboard_ssurgo_field_variability_map.png').size[0]>=1800
html=(O/'interactive/assignment_04_interactive_map.html').read_text(); assert 'leaflet' in html.lower() and 'aws025wta' in html
fs=pd.read_csv(O/'tables/field_soil_summary.csv'); assert len(fs)==25 and fs.field_id.nunique()==25 and fs.area_weighted_aws025wta.notna().all()
nb=nbformat.read(REPO/'notebooks/04_geospatial_mapping.ipynb',as_version=4); code=[c for c in nb.cells if c.cell_type=='code']; assert code and all(c.get('execution_count') is not None for c in code)
for p in [A4/'README.md',A4/'GEOSPATIAL_REPORT.md',A4/'evidence/successful_geospatial_run.svg',A4/'evidence/assignment_04_evidence_summary.md',REPO/'docs/project/assignment-04-tracker.md']: assert p.stat().st_size>100
print('PASS: Assignment 4 verification succeeded (all checks passed).')
