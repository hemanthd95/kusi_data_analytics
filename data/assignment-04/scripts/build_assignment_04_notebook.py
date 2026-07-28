"""Build the reproducible Assignment 4 presentation notebook."""
from pathlib import Path
import nbformat as nbf

repo=Path(__file__).resolve().parents[3]
nb=nbf.v4.new_notebook()
nb['metadata']['kernelspec']={'display_name':'Python 3','language':'python','name':'python3'}
nb['metadata']['language_info']={'name':'python','version':'3.12'}
nb['cells']=[
 nbf.v4.new_markdown_cell('# Assignment 4 — Geospatial Mapping\nExecuted, checksum-gated offline analysis of genuine USDA-NRCS SSURGO data.'),
 nbf.v4.new_code_cell("from pathlib import Path\nimport json, pandas as pd\nfrom IPython.display import display, Image\nrepo=Path.cwd().parent if Path.cwd().name=='notebooks' else Path.cwd()\nout=repo/'data/assignment-04/output'\nq=json.loads((out/'spatial_quality_summary.json').read_text())\nprint('Offline:',q['offline'],'Network requests:',q['network_requests'])\nprint('Parsed:',q['parsed_polygon_features'],'Clipped:',q['clipped_polygon_features'],'Map units:',q['unique_mapunits'])"),
 nbf.v4.new_markdown_cell('## Field-level soil summary\n`aws025wta` is available water storage from 0–25 cm, weighted across map-unit components, in centimeters of water. Missing values remain missing.'),
 nbf.v4.new_code_cell("fields=pd.read_csv(out/'tables/field_soil_summary.csv')\ndisplay(fields.round(3))\nprint(fields['area_weighted_aws025wta'].describe())"),
 nbf.v4.new_markdown_cell('## Final cartographic panel'),
 nbf.v4.new_code_cell("display(Image(filename=out/'maps/04_final_assignment_panel.png',width=1000))"),
 nbf.v4.new_markdown_cell('## Spatial quality\nThe 500 m buffer was regenerated in EPSG:32617 and compared with the independently supplied external reference.'),
 nbf.v4.new_code_cell("display(pd.Series(q).to_frame('value'))")]
nbf.write(nb,repo/'notebooks/04_geospatial_mapping.ipynb')
print('Built notebooks/04_geospatial_mapping.ipynb')
