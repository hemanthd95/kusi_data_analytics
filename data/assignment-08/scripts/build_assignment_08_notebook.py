#!/usr/bin/env python3
"""Build the Assignment 8 notebook from committed outputs."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[3]
NOTEBOOK = ROOT / "notebooks" / "08_soil_health_sustainability.ipynb"
nb = nbf.v4.new_notebook()
nb["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nb["metadata"]["language_info"] = {"name": "python", "version": "3.12"}
nb["cells"] = [
    nbf.v4.new_markdown_cell("# Assignment 8 — Soil Health and Sustainability Metrics Assessment\n\nOffline analysis of validated USDA-NRCS SSURGO and USDA NASS CDL products for 25 fields."),
    nbf.v4.new_code_cell("from pathlib import Path\nimport os\nimport json\nimport pandas as pd\nfrom IPython.display import display\nstart=Path(os.environ.get('GITHUB_WORKSPACE', Path.cwd())).resolve()\nROOT=next((p for p in [start, *start.parents] if (p/'data/assignment-08').is_dir()), None)\nif ROOT is None:\n    raise RuntimeError('Could not locate repository root')\nA8=ROOT/'data/assignment-08'\nOUT=A8/'output'\nsummary=json.loads((OUT/'soil_health_summary.json').read_text())\nsummary"),
    nbf.v4.new_markdown_cell("## Field-level soil health scorecard"),
    nbf.v4.new_code_cell("scorecard=pd.read_csv(OUT/'tables/field_soil_health_scorecard.csv', dtype={'field_id':str})\ndisplay(scorecard.head(10).round(2))\nprint('fields=',len(scorecard),' unique_ids=',scorecard.field_id.nunique())"),
    nbf.v4.new_markdown_cell("## Required sustainability metrics"),
    nbf.v4.new_code_cell("metrics=pd.read_csv(OUT/'tables/sustainability_metric_summary.csv')\ndisplay(metrics.round(2))\nprint('metric_count=',summary['sustainability_metric_count'])"),
    nbf.v4.new_markdown_cell("## NRCS map-unit context"),
    nbf.v4.new_code_cell("mapunits=pd.read_csv(OUT/'tables/soil_mapunit_sustainability_summary.csv', dtype={'mukey':str})\ndisplay(mapunits.round(2))"),
    nbf.v4.new_markdown_cell("## Dashboard visualization 1\n\n![Scorecard](../data/assignment-08/output/dashboard_assets/dashboard_soil_health_scorecard.png)"),
    nbf.v4.new_markdown_cell("## Dashboard visualization 2\n\n![Tradeoff](../data/assignment-08/output/dashboard_assets/dashboard_sustainability_tradeoff.png)"),
    nbf.v4.new_markdown_cell("## Interpretation limits\n\nThe score is relative within this 25-field set. SSURGO is mapped soil information, not field sampling. The package contains no laboratory pH, organic matter, soil carbon, biological activity, or direct sensor measurements, and none are invented."),
]
for index, cell in enumerate(nb["cells"]):
    cell["id"] = f"assignment-08-{index:02d}"
NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, NOTEBOOK)
print(f"Built {NOTEBOOK.relative_to(ROOT)}")
