#!/usr/bin/env python3
"""Deterministically build the offline Assignment 6 analysis notebook."""
from pathlib import Path
import nbformat as n
ROOT=Path(__file__).resolve().parents[3]; out=ROOT/'notebooks/06_weather_climate_trends.ipynb'
c=[]
def md(x): c.append(n.v4.new_markdown_cell(x))
def code(x): c.append(n.v4.new_code_cell(x))
md('# Assignment 6 — Real-Data Weather and Climate Trend Analysis\nAuthentic NASA POWER gridded daily estimates for the 25-field South Carolina cluster; no network access is used here.')
code("from pathlib import Path\nimport hashlib,json,pandas as pd\nfrom IPython.display import display,Image\nROOT=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'data/assignment-06').exists())\nA=ROOT/'data/assignment-06'; S=A/'source'; O=A/'output'")
md('## Source provenance and checksum validation')
code("m=json.loads((S/'source_manifest.json').read_text()); raw=S/'nasa_power_daily_raw.json'\nassert m['status']=='success' and m['no_synthetic_fallback'] and hashlib.sha256(raw.read_bytes()).hexdigest()==m['raw_response']['sha256']\ndisplay(pd.DataFrame([m['request']]))")
md('## Field and weather-point context\nThe acreage-weighted centroid is one representative point. NASA POWER is gridded and cannot resolve field-to-field meteorological differences or replace an on-site station.')
code("loc=json.loads((S/'field_location_summary.json').read_text()); dist=pd.read_csv(S/'field_to_weather_point_distances.csv',dtype={'field_id':str}); assert len(dist)==25 and dist.field_id.nunique()==25; display(loc,dist.head())")
md('## Daily structure and data quality\nFill values are missing, never interpolated. Hot (≥35 °C maximum), frost (≤0 °C minimum), dry (<1 mm), and heavy-rain (≥25 mm) flags are descriptive—not universal crop-injury thresholds.')
code("daily=pd.read_csv(O/'tables/weather_daily_1991_2025.csv',parse_dates=['date']); quality=pd.read_csv(O/'tables/weather_data_quality.csv'); assert len(daily)==12784; display(daily.head(),quality)")
md('## Aggregation rules\nTemperature and humidity/radiation are means; precipitation is accumulated. Months need ≥90% valid days. Dry spells reset at annual and April–October boundaries.')
code("monthly=pd.read_csv(O/'tables/weather_monthly_1991_2025.csv'); annual=pd.read_csv(O/'tables/weather_annual_1991_2025.csv'); warm=pd.read_csv(O/'tables/weather_warm_season_1991_2025.csv'); assert len(monthly)==420 and len(annual)==35; display(monthly.head(),annual.tail())")
md('## Seasonal climatology — baseline 1991–2020')
code("normals=pd.read_csv(O/'tables/climate_normals_1991_2020.csv'); display(normals); display(Image(filename=str(O/'dashboard_assets/dashboard_seasonal_climate.png')))")
md('## Trends and precipitation anomalies')
code("trends=pd.read_csv(O/'tables/climate_trend_statistics.csv'); anomalies=pd.read_csv(O/'tables/climate_anomalies_1991_2025.csv'); recent=pd.read_csv(O/'tables/recent_anomalies_2021_2025.csv'); display(trends,recent); display(Image(filename=str(O/'dashboard_assets/dashboard_climate_trends_anomalies.png')))")
md('## Warm-season weather-risk metrics\nApril–October is a consistent agricultural analytical window, not every crop’s exact phenology. Metrics support planning context but do not establish crop damage or causation.')
code("display(warm[['year','warm_season_hot_day_count','warm_season_longest_dry_spell_days','warm_season_precipitation_mm']].tail(10))")
md('## Independent internal validation and interpretation cautions\nTrends are local and descriptive; statistical significance is not agronomic importance or global attribution. Gridded NASA estimates are not station measurements.')
code("assert daily.date.is_unique and daily.date.is_monotonic_increasing\nassert daily.date.min()==pd.Timestamp('1991-01-01') and daily.date.max()==pd.Timestamp('2025-12-31')\nassert (daily.diurnal_temperature_range_C-(daily.t2m_max_C-daily.t2m_min_C)).abs().max()<1e-9\nassert set(recent.year)==set(range(2021,2026))\nprint('All notebook internal assertions passed.')")
nb=n.v4.new_notebook(cells=c,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3'}});n.write(nb,out);print(out)
