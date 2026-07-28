#!/usr/bin/env python3
"""Reproducible Assignment 3 EDA using finalized Assignment 2 outputs only."""
from __future__ import annotations
import hashlib, io, json, platform, subprocess, sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr

ROOT=Path(__file__).resolve().parents[3]
A3=ROOT/'data/assignment-03'; OUT=A3/'output'; VIS=OUT/'visualizations'; DASH=OUT/'dashboard_assets'; EVID=A3/'evidence'
SOURCE=ROOT/'data/assignment-02/field_summary.csv'; YEARS=[2020,2021,2022,2023]
GREEN='#386641'; LIGHT='#A7C957'; GOLD='#DDA15E'; BROWN='#7F5539'; RED='#BC4749'; BLUE='#457B9D'

def git_sha(): return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def boolify(s):
    if pd.api.types.is_bool_dtype(s): return s
    m={'true':True,'false':False,'1':True,'0':False}
    out=s.astype(str).str.lower().map(m); assert out.notna().all(), f'invalid booleans in {s.name}'; return out.astype(bool)
def iqr_mask(s):
    q1,q3=s.quantile([.25,.75]); i=q3-q1; return (s<q1-1.5*i)|(s>q3+1.5*i)
def load_validate():
    d=pd.read_csv(SOURCE,dtype={'field_id':str,'CSBID':str,'STATEFIPS':str})
    assert d.shape[0]==25 and d.field_id.nunique()==25 and not d.duplicated().any()
    assert d.field_id.equals(d.CSBID) and set(d.STATEFIPS)=={'45'} and (d.CSBACRES>0).all() and d.CSBACRES.notna().all()
    assert d.field_id.str.fullmatch(r'45\d{13}').all(), 'unexpected/synthetic identifiers'
    for y in YEARS:
        assert f'crop_{y}' in d and d[f'crop_{y}'].notna().all()
        assert (d[f'valid_pixels_{y}']>0).all()
        assert d[f'dominant_pct_{y}'].between(0,100).all()
        d[f'matches_csb_{y}']=boolify(d[f'matches_csb_{y}'])
    return d
def derive(d):
    p=[f'dominant_pct_{y}' for y in YEARS]; v=[f'valid_pixels_{y}' for y in YEARS]; c=[f'crop_{y}' for y in YEARS]; m=[f'matches_csb_{y}' for y in YEARS]
    x=d[['field_id','CSBID','STATEFIPS','county','CSBACRES']].copy(); a=d[p]
    x['mean_dominant_pct']=a.mean(axis=1); x['median_dominant_pct']=a.median(axis=1); x['min_dominant_pct']=a.min(axis=1); x['max_dominant_pct']=a.max(axis=1); x['dominant_pct_range']=x.max_dominant_pct-x.min_dominant_pct
    x['mean_valid_pixels']=d[v].mean(axis=1); x['crop_transition_count']=sum((d[c[i]]!=d[c[i+1]]).astype(int) for i in range(3)); x['unique_dominant_crop_count']=d[c].nunique(axis=1)
    x['raster_csb_match_rate']=d[m].mean(axis=1)*100; x['ever_raster_csb_mismatch']=~d[m].all(axis=1); x['acreage_iqr_outlier']=iqr_mask(x.CSBACRES); x['confidence_iqr_outlier']=iqr_mask(x.mean_dominant_pct)
    assert np.allclose(x.mean_dominant_pct,a.mean(axis=1)); assert x.crop_transition_count.between(0,3).all(); assert x.unique_dominant_crop_count.between(1,4).all(); assert x.raster_csb_match_rate.between(0,100).all(); assert np.allclose(x.dominant_pct_range,x.max_dominant_pct-x.min_dominant_pct)
    return x
def savefig(fig, stem, dpi=300):
    fig.savefig(stem.with_suffix('.png'),dpi=dpi,bbox_inches='tight',facecolor='white'); fig.savefig(stem.with_suffix('.svg'),bbox_inches='tight',facecolor='white'); plt.close(fig)
def visuals(d,x,comp,corr):
    sns.set_theme(style='whitegrid',font_scale=1.0)
    q1,med,q3=x.CSBACRES.quantile([.25,.5,.75]); fig,ax=plt.subplots(figsize=(10,6)); ax.hist(x.CSBACRES,bins='auto',color=GREEN,edgecolor='white',alpha=.88)
    for val,label,col in [(q1,'Q1',GOLD),(med,'Median',RED),(q3,'Q3',GOLD)]: ax.axvline(val,color=col,ls='--',lw=2,label=f'{label}: {val:.1f} acres')
    o=x[x.acreage_iqr_outlier]; ax.scatter(o.CSBACRES,np.full(len(o),.25),marker='D',s=75,color=RED,label=f'IQR outlier (n={len(o)})',zorder=5); ax.set(title='Acreage Distribution in the 25-Field Assignment 2 Sample',xlabel='Field acreage (acres)',ylabel='Number of fields'); ax.legend(); fig.text(.5,.01,'Sample: 25 selected fields; not representative of all South Carolina fields.',ha='center'); fig.tight_layout(rect=[0,.04,1,1]); savefig(fig,VIS/'01_acreage_distribution')
    def scatter_fig(size,title,subtitle=False):
        fig,ax=plt.subplots(figsize=size); pal=sns.color_palette('viridis',4)
        for mismatch,marker,edge in [(False,'o','white'),(True,'X',RED)]:
            z=x[x.ever_raster_csb_mismatch==mismatch]; sc=ax.scatter(z.CSBACRES,z.mean_dominant_pct,c=z.crop_transition_count,cmap='viridis',vmin=0,vmax=3,marker=marker,s=110 if mismatch else 80,edgecolors=edge,linewidths=1.4,label='Ever mismatch' if mismatch else 'All four years match')
        cb=fig.colorbar(sc,ax=ax,ticks=[0,1,2,3]); cb.set_label('Adjacent-year crop transitions (0–3)'); ax.set(title=title,xlabel='Field acreage (acres)',ylabel='Mean dominant CDL pixels (%)'); ax.legend(loc='lower right'); ax.text(.01,.02,'Each point is one field; outlined X = ≥1 raster/CSB mismatch',transform=ax.transAxes,fontsize=9); fig.tight_layout(); return fig
    savefig(scatter_fig((10,6),'Field Acreage vs. Four-Year Classification Confidence'),VIS/'02_acreage_vs_classification_confidence')
    fig,ax=plt.subplots(figsize=(9,7)); sns.heatmap(corr,annot=True,fmt='.2f',cmap='vlag',center=0,vmin=-1,vmax=1,square=True,linewidths=.5,ax=ax,cbar_kws={'label':'Spearman ρ'}); ax.set_title('Exploratory Spearman Correlations (25 Fields)'); fig.tight_layout(); savefig(fig,VIS/'03_metric_correlation_heatmap')
    pivot=comp.pivot(index='year',columns='crop',values='field_count').fillna(0); colors=sns.color_palette('colorblind',len(pivot.columns)); fig,ax=plt.subplots(figsize=(11,6)); pivot.plot(kind='bar',stacked=True,color=colors,ax=ax,width=.72); ax.set(title='Dominant Crop Composition by Year (25 Fields per Year)',xlabel='Year',ylabel='Field count'); ax.tick_params(axis='x',rotation=0); ax.legend(title='Raster-derived dominant crop',bbox_to_anchor=(1.02,1),loc='upper left'); fig.tight_layout(); savefig(fig,VIS/'04_crop_composition_by_year')
    fig,ax=plt.subplots(figsize=(12,6.75)); (pivot/25*100).plot(kind='bar',stacked=True,color=colors,ax=ax,width=.66); ax.set(title='Dominant CDL Crop Composition, 2020–2023',xlabel='Year',ylabel='Share of 25 fields (%)',ylim=(0,100)); ax.tick_params(axis='x',rotation=0); ax.legend(title='Dominant crop class',bbox_to_anchor=(1.01,1),loc='upper left',frameon=False); ax.text(.01,-.14,'Each bar represents exactly 25 selected Assignment 2 fields; classes are not interpolated.',transform=ax.transAxes); fig.tight_layout(); savefig(fig,DASH/'dashboard_crop_composition')
    savefig(scatter_fig((12,6.75),'Field Acreage and Classification Confidence | 2020–2023'),DASH/'dashboard_field_confidence')
def main():
    for p in [OUT,VIS,DASH,EVID]: p.mkdir(parents=True,exist_ok=True)
    log=[]; now=datetime.now(timezone.utc).isoformat(); sha=sha256(SOURCE); source_git=git_sha(); log.append(f'{now} START source={SOURCE.relative_to(ROOT)}')
    d=load_validate(); x=derive(d); log+=['PASS input validation','PASS derived metric assertions']
    x.to_csv(OUT/'derived_field_metrics.csv',index=False)
    d.describe(include='all').transpose().to_csv(OUT/'descriptive_statistics.csv')
    pd.DataFrame({'column':d.columns,'dtype':d.dtypes.astype(str),'non_null':d.notna().sum().values,'unique':d.nunique(dropna=False).values}).to_csv(OUT/'data_types.csv',index=False)
    pd.DataFrame({'column':d.columns,'missing_count':d.isna().sum().values,'missing_pct':d.isna().mean().mul(100).values,'unique_count':d.nunique(dropna=False).values}).to_csv(OUT/'data_quality_summary.csv',index=False)
    b=io.StringIO(); d.info(buf=b); (OUT/'dataframe_info.txt').write_text(b.getvalue()+f'\nDuplicate rows: {d.duplicated().sum()}\n\nMissing values:\n{d.isna().sum().to_string()}\n\nUnique values:\n{d.nunique(dropna=False).to_string()}\n',encoding='utf-8')
    rows=[]
    for y in YEARS:
        vc=d[f'crop_{y}'].value_counts()
        rows += [{'year':y,'crop':crop,'field_count':int(n),'field_pct':n/25*100} for crop,n in vc.items()]
    comp=pd.DataFrame(rows).sort_values(['year','crop']); comp.to_csv(OUT/'crop_composition_by_year.csv',index=False)
    cols=['CSBACRES','mean_dominant_pct','min_dominant_pct','dominant_pct_range','crop_transition_count','unique_dominant_crop_count','raster_csb_match_rate']; corr=x[cols].corr(method='spearman'); corr.to_csv(OUT/'correlation_matrix_spearman.csv')
    pairs=pd.DataFrame([{'variable_1':cols[i],'variable_2':cols[j],'spearman_rho':corr.iloc[i,j],'absolute_rho':abs(corr.iloc[i,j])} for i in range(len(cols)) for j in range(i+1,len(cols))]).sort_values('absolute_rho',ascending=False); pairs.to_csv(OUT/'strongest_correlations.csv',index=False)
    sp=spearmanr(x.CSBACRES,x.mean_dominant_pct); pe=pearsonr(x.CSBACRES,x.mean_dominant_pct); visuals(d,x,comp,corr); log.append('PASS generated 4 exploratory figures and 2 dashboard figures')
    match_by={str(y):float(d[f'matches_csb_{y}'].mean()*100) for y in YEARS}; transitions={str(int(k)):int(v) for k,v in x.crop_transition_count.value_counts().sort_index().items()}
    summary={'source_file':'data/assignment-02/field_summary.csv','supporting_sources':['data/assignment-02/output/assignment_02_summary.json','data/assignment-02/cdl_EPSG4326.csv','data/assignment-02/fields_EPSG4326.geojson'],'source_sha256':sha,'source_git_sha':source_git,'generated_utc':now,'input_row_count':25,'input_column_count':int(d.shape[1]),'unique_field_count':25,'years_analyzed':YEARS,'numeric_columns_analyzed':cols,'categorical_columns_analyzed':[f'crop_{y}' for y in YEARS],'missing_value_counts':{k:int(v) for k,v in d.isna().sum().items()},'duplicate_count':0,'acreage_outlier_count':int(x.acreage_iqr_outlier.sum()),'confidence_outlier_count':int(x.confidence_iqr_outlier.sum()),'raster_csb_match_rate_overall':float(d[[f'matches_csb_{y}' for y in YEARS]].to_numpy().mean()*100),'raster_csb_match_rate_by_year':match_by,'crop_transition_counts':transitions,'crop_composition_by_year':{str(y):{k:int(v) for k,v in d[f'crop_{y}'].value_counts().items()} for y in YEARS},'visual_2_correlations':{'sample_size':25,'spearman_rho':float(sp.statistic),'spearman_p_value':float(sp.pvalue),'pearson_r':float(pe.statistic),'pearson_p_value':float(pe.pvalue)},'strongest_spearman_correlations':pairs.head(5).to_dict('records'),'output_file_inventory':['descriptive_statistics.csv','data_types.csv','data_quality_summary.csv','derived_field_metrics.csv','crop_composition_by_year.csv','correlation_matrix_spearman.csv','strongest_correlations.csv'],'dashboard_asset_inventory':['dashboard_crop_composition.png','dashboard_crop_composition.svg','dashboard_field_confidence.png','dashboard_field_confidence.svg'],'notebook_execution_status':'pending until nbconvert execution','no_synthetic_data_declaration':True}
    (OUT/'eda_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    packages=['pandas','numpy','matplotlib','seaborn','scipy','jupyter','nbformat','nbconvert']; env={'python':platform.python_version(),'operating_system':platform.platform(),'git_source_sha':source_git,**{p:version(p) for p in packages}}; (OUT/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
    log.append('RESULT: SUCCESS'); (OUT/'skill_run.log').write_text('\n'.join(log)+'\n')
    print(json.dumps({'rows':25,'columns':d.shape[1],'sha256':sha,'acreage_outliers':int(x.acreage_iqr_outlier.sum()),'confidence_outliers':int(x.confidence_iqr_outlier.sum()),'spearman':sp.statistic,'pearson':pe.statistic,'overall_match_pct':summary['raster_csb_match_rate_overall']},indent=2))
if __name__=='__main__': main()
