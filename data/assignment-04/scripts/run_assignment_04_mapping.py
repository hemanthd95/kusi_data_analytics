"""Reproducible Assignment 4 SSURGO mapping pipeline.

Offline mode is intentionally checksum-gated and performs no HTTP operations.
"""
from __future__ import annotations

import argparse, hashlib, json, platform
from datetime import datetime, timezone
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from PIL import Image
import folium
from branca.colormap import linear
from shapely import transform

REPO = Path(__file__).resolve().parents[3]
A4 = REPO / "data/assignment-04"
FIELD_SOURCE = REPO / "data/assignment-02/fields_EPSG4326.geojson"
RAW = A4 / "source/ssurgo_mapunit_response.gml"
META = A4 / "source/ssurgo_request_metadata.json"
EXTERNAL = A4 / "source/field_buffer_500m_external.geojson"
EXPECTED = {
 RAW:"f7b9e32fb7f575f814739a7cefffc7fb0695b829e56f518a56f93bfddd46ab5c",
 META:"b361a28525bd10d4e4c1c65551b954ebf0a29de0f274af47d6de6610106960e8",
 EXTERNAL:"3ed7c3487e1714fc71ac641f59748557a1078a57b09e3a31eb031ddf1dc71e9f"}
CRS="EPSG:32617"; ATTRIBUTE="aws025wta"; UNITS="centimeters of water"; ACRES=0.000247105381

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def savefig(fig, stem, dpi=200):
    fig.savefig(stem.with_suffix('.png'), dpi=dpi, bbox_inches='tight', facecolor='white')
    fig.savefig(stem.with_suffix('.svg'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

def north_scale(ax):
    ax.annotate('N',(.96,.91),xycoords='axes fraction',ha='center',weight='bold',fontsize=13)
    ax.annotate('',(.96,.985),(.96,.92),xycoords='axes fraction',arrowprops=dict(facecolor='black',width=3,headwidth=10))
    x0,x1=ax.get_xlim(); y0,y1=ax.get_ylim(); length=1000
    ax.plot([x0+.06*(x1-x0),x0+.06*(x1-x0)+length],[y0+.055*(y1-y0)]*2,'k-',lw=4)
    ax.text(x0+.06*(x1-x0)+length/2,y0+.07*(y1-y0),'1 km',ha='center',fontsize=9)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--offline',action='store_true'); args=ap.parse_args()
    if not args.offline: raise SystemExit('Online acquisition is disabled for this reproducible run; use --offline.')
    for p,h in EXPECTED.items():
        if not p.is_file() or digest(p)!=h: raise RuntimeError(f'Missing or modified authoritative source: {p}')
    m=json.loads(META.read_text())
    required=(m.get('success') is True and m.get('http_status')==200 and m.get('response_byte_size')==RAW.stat().st_size==794318
              and m.get('response_sha256')==EXPECTED[RAW] and m.get('field_geometry_repairs')==3
              and m.get('parameters',{}).get('TYPENAME')=='MapunitPolyExtended')
    if not required: raise RuntimeError('Request metadata does not validate the official successful response')
    fields=gpd.read_file(FIELD_SOURCE); invalid=int((~fields.is_valid).sum())
    if len(fields)!=25 or invalid!=3: raise RuntimeError('Authoritative field geometry inventory changed')
    fields=fields.copy(); fields.geometry=fields.geometry.make_valid(); fields=fields.to_crs(CRS)
    # make_valid can return collections; retain all polygonal pieces.
    fields.geometry=fields.geometry.apply(lambda g: gpd.GeoSeries([g],crs=CRS).explode(index_parts=False).union_all())
    buffer=fields.geometry.union_all().buffer(500)
    out=A4/'output'; maps=out/'maps'; dash=out/'dashboard_assets'; inter=out/'interactive'; tables=out/'tables'
    for d in (maps,dash,inter,tables): d.mkdir(parents=True,exist_ok=True)
    bg=gpd.GeoDataFrame({'buffer_m':[500]},geometry=[buffer],crs=CRS)
    bg.to_crs(4326).to_file(out/'field_buffer_500m.geojson',driver='GeoJSON')
    ext=gpd.read_file(EXTERNAL).to_crs(CRS).geometry.union_all()
    difference=buffer.symmetric_difference(ext).area
    soil=gpd.read_file(RAW)
    if not {'mukey','musym','geometry',ATTRIBUTE}.issubset(soil.columns): raise RuntimeError('Required authentic GML schema absent')
    # The official WFS 1.1 GML encodes EPSG:4326 in latitude/longitude axis order.
    # GDAL exposes those ordinates literally, so normalize to conventional x=longitude.
    if soil.total_bounds[0] > 0:
        soil.geometry=soil.geometry.apply(lambda geom: transform(geom,lambda xy: xy[:, ::-1]))
    parsed=len(soil); soil=soil.to_crs(CRS); clipped=gpd.clip(soil,bg); clipped=clipped[~clipped.is_empty].copy()
    clipped['soil_area_m2']=clipped.area
    # Intersections include missing soil values; NaN is never converted to zero.
    inters=gpd.overlay(fields[['field_id','geometry']],clipped[['mukey','musym',ATTRIBUTE,'geometry']],how='intersection',keep_geom_type=False)
    inters=inters[inters.geom_type.isin(['Polygon','MultiPolygon'])].copy(); inters['intersection_area_m2']=inters.area
    inters['intersection_area_acres']=inters.intersection_area_m2*ACRES
    fa=fields.set_index('field_id').area
    inters['field_area_m2']=inters.field_id.map(fa); inters['percent_of_field']=100*inters.intersection_area_m2/inters.field_area_m2
    def summarize(g):
        valid=g[ATTRIBUTE].notna(); covered=g.intersection_area_m2.sum(); valued=g.loc[valid,'intersection_area_m2'].sum()
        weighted=np.average(g.loc[valid,ATTRIBUTE],weights=g.loc[valid,'intersection_area_m2']) if valued else np.nan
        return pd.Series({'field_area_m2':g.field_area_m2.iloc[0],'covered_area_m2':covered,'coverage_percent':100*covered/g.field_area_m2.iloc[0],
          'uncovered_percent':max(0,100*(g.field_area_m2.iloc[0]-covered)/g.field_area_m2.iloc[0]),'valued_coverage_percent':100*valued/g.field_area_m2.iloc[0],
          'map_unit_count':g.mukey.nunique(),'area_weighted_aws025wta':weighted})
    fs=inters.groupby('field_id').apply(summarize,include_groups=False).reset_index()
    fs['field_id']=fs.field_id.astype(str); fs.to_csv(tables/'field_soil_summary.csv',index=False)
    inters.drop(columns='geometry').to_csv(tables/'field_ssurgo_intersections.csv',index=False)
    mu=clipped.groupby(['mukey','musym'],dropna=False).agg(polygon_count=('geometry','size'),clipped_area_m2=('soil_area_m2','sum'),aws025wta=(ATTRIBUTE,'first')).reset_index()
    mu['clipped_area_acres']=mu.clipped_area_m2*ACRES; mu.to_csv(tables/'map_unit_summary.csv',index=False)
    fields=fields.merge(fs[['field_id','area_weighted_aws025wta','coverage_percent']],on='field_id',how='left')
    # 1 context
    fig,ax=plt.subplots(figsize=(12,9)); clipped.plot(ax=ax,color='#d9c89e',edgecolor='#8c6d31',lw=.5); fields.boundary.plot(ax=ax,color='#173f5f',lw=1.5); bg.boundary.plot(ax=ax,color='#d62728',ls='--');
    ax.set_title('Field Boundaries and SSURGO Context'); ax.set_axis_off(); north_scale(ax); ax.text(.01,.01,'Source: USDA-NRCS SSURGO; authoritative Assignment 2 fields',transform=ax.transAxes,fontsize=8); savefig(fig,maps/'01_field_boundaries_and_ssurgo_context')
    # 2 choropleth
    fig,ax=plt.subplots(figsize=(12,9)); clipped.plot(ATTRIBUTE,ax=ax,cmap='YlGnBu',legend=True,missing_kwds={'color':'#d9d9d9','label':'Missing'},edgecolor='white',lw=.4,legend_kwds={'label':f'Available water storage 0–25 cm ({UNITS})'}); fields.boundary.plot(ax=ax,color='black',lw=1); ax.set_title('SSURGO Available Water Storage (0–25 cm)'); ax.set_axis_off(); north_scale(ax); ax.text(.01,.01,'Missing values are shown in gray and are not treated as zero.',transform=ax.transAxes,fontsize=8); savefig(fig,maps/'02_ssurgo_attribute_choropleth')
    # 3 buffer comparison
    fig,ax=plt.subplots(figsize=(12,9)); bg.plot(ax=ax,color='#add8e6',alpha=.45,edgecolor='#006d9c'); gpd.GeoSeries([ext],crs=CRS).boundary.plot(ax=ax,color='#e6550d',ls='--'); fields.plot(ax=ax,color='#31a354',edgecolor='white'); ax.set_title('500 m Analytical Buffer — Regenerated vs External Reference'); ax.set_axis_off(); north_scale(ax); ax.text(.01,.01,f'Symmetric difference: {difference:,.3f} m² | Working CRS: EPSG:32617',transform=ax.transAxes); savefig(fig,maps/'03_buffer_operation')
    # final large panel with table
    fig=plt.figure(figsize=(16,12)); gs=fig.add_gridspec(2,2,height_ratios=[3,1.15]); ax=fig.add_subplot(gs[0,:]); clipped.plot(ATTRIBUTE,ax=ax,cmap='YlGnBu',edgecolor='white',lw=.3,missing_kwds={'color':'#ddd'}); fields.boundary.plot(ax=ax,color='black',lw=1); ax.set_axis_off(); north_scale(ax); ax.set_title('Assignment 4 — SSURGO Soil Water Storage and 25 Fields',fontsize=20,weight='bold');
    sm=ScalarMappable(Normalize(clipped[ATTRIBUTE].min(),clipped[ATTRIBUTE].max()),cmap='YlGnBu'); cb=fig.colorbar(sm,ax=ax,fraction=.025,pad=.01); cb.set_label(f'aws025wta ({UNITS})')
    ta=fig.add_subplot(gs[1,0]); ta.axis('off'); show=fs.sort_values('area_weighted_aws025wta',ascending=False)[['field_id','area_weighted_aws025wta','coverage_percent']].copy(); show.field_id=show.field_id.str[-6:]; show.columns=['Field (last 6)','AWS 0–25 cm','Coverage %']; show=show.round(2); table=ta.table(cellText=show.values,colLabels=show.columns,loc='center',cellLoc='center'); table.auto_set_font_size(False); table.set_fontsize(8); table.scale(1,1.15)
    tx=fig.add_subplot(gs[1,1]); tx.axis('off'); tx.text(0,.95,'Interpretation',weight='bold',fontsize=14); tx.text(0,.82,'Higher values indicate more water stored in the upper 25 cm.\nField values are area-weighted only across intersections with\nnon-missing SSURGO values; missing values are never zero-filled.',va='top',fontsize=11); tx.text(0,.3,'Legend: blue = higher AWS; yellow = lower AWS; gray = missing\nNorth arrow and 1 km scale shown above.\nSource: USDA-NRCS SSURGO MapunitPolyExtended\nAnalysis: EPSG:32617; retrieved externally and checksum verified.',fontsize=9)
    fig.subplots_adjust(hspace=.12); savefig(fig,maps/'04_final_assignment_panel',dpi=180)
    # dashboard
    fig,ax=plt.subplots(figsize=(12,7)); fields.plot('area_weighted_aws025wta',ax=ax,cmap='viridis',legend=True,edgecolor='white',lw=1,legend_kwds={'label':f'Area-weighted AWS ({UNITS})'}); ax.set_title('Field Soil-Water Variability',fontsize=18,weight='bold'); ax.set_axis_off(); north_scale(ax); savefig(fig,dash/'dashboard_ssurgo_field_variability_map',dpi=360)
    # interactive Leaflet, with attributes and fields
    center=fields.to_crs(4326).geometry.union_all().centroid
    fm=folium.Map([center.y,center.x],zoom_start=13,tiles='CartoDB positron')
    c=linear.YlGnBu_09.scale(float(clipped[ATTRIBUTE].min()),float(clipped[ATTRIBUTE].max())); c.caption=f'aws025wta ({UNITS})'; c.add_to(fm)
    sj=clipped.to_crs(4326)[['mukey','musym',ATTRIBUTE,'geometry']]
    folium.GeoJson(sj.to_json(),name='SSURGO',style_function=lambda f:{'fillColor':'#bdbdbd' if f['properties'][ATTRIBUTE] is None else c(f['properties'][ATTRIBUTE]),'color':'#666','weight':.5,'fillOpacity':.65},tooltip=folium.GeoJsonTooltip(['mukey','musym',ATTRIBUTE])).add_to(fm)
    folium.GeoJson(fields.to_crs(4326)[['field_id','area_weighted_aws025wta','coverage_percent','geometry']].to_json(),name='Fields',style_function=lambda f:{'fillOpacity':0,'color':'#111','weight':2},tooltip=folium.GeoJsonTooltip(['field_id','area_weighted_aws025wta','coverage_percent'])).add_to(fm); folium.LayerControl().add_to(fm); fm.save(inter/'assignment_04_interactive_map.html')
    vals=clipped[ATTRIBUTE]; wvals=fs.area_weighted_aws025wta
    quality={'generated_utc':datetime.now(timezone.utc).isoformat(),'offline':True,'network_requests':0,'source_checksums':{p.name:h for p,h in EXPECTED.items()},'source_byte_size':RAW.stat().st_size,
      'schema_columns':soil.columns.tolist(),'field_count':len(fields),'field_geometry_repairs':invalid,'parsed_polygon_features':parsed,'clipped_polygon_features':len(clipped),'unique_map_units':int(clipped.mukey.nunique()),
      'attribute':ATTRIBUTE,'definition':'Available water storage from 0–25 cm, weighted average of map-unit components','units':UNITS,'source_attribute_missing_count':int(vals.isna().sum()),'source_attribute_missing_percent':float(vals.isna().mean()*100),
      'source_attribute_stats':{k:float(v) for k,v in vals.describe().items()},'field_weighted_stats':{k:float(v) for k,v in wvals.describe().items()},'fields_multiple_units':int((fs.map_unit_count>1).sum()),
      'average_field_coverage_percent':float(fs.coverage_percent.mean()),'minimum_field_coverage_percent':float(fs.coverage_percent.min()),'buffer_symmetric_difference_m2':float(difference),
      'highest_field':fs.loc[wvals.idxmax(),['field_id','area_weighted_aws025wta']].to_dict(),'lowest_field':fs.loc[wvals.idxmin(),['field_id','area_weighted_aws025wta']].to_dict(),
      'environment':{'python':platform.python_version(),'geopandas':gpd.__version__,'pandas':pd.__version__}}
    (out/'spatial_quality_summary.json').write_text(json.dumps(quality,indent=2,default=str)+'\n')
    print(json.dumps(quality,indent=2,default=str)); print('SUCCESS: Assignment 4 offline mapping complete')

if __name__=='__main__': main()
