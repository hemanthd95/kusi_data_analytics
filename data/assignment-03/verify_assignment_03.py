#!/usr/bin/env python3
"""Fail-fast automated verification for Assignment 3."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
import nbformat,numpy as np,pandas as pd
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]; A3=ROOT/'data/assignment-03'; OUT=A3/'output'; SRC=ROOT/'data/assignment-02/field_summary.csv'; YEARS=range(2020,2024)
def need(ok,msg):
    if not ok: raise AssertionError(msg)
def main():
 s=json.loads((OUT/'eda_summary.json').read_text()); need(SRC.exists(),'input missing'); need(hashlib.sha256(SRC.read_bytes()).hexdigest()==s['source_sha256'],'source SHA mismatch'); d=pd.read_csv(SRC,dtype={'field_id':str,'CSBID':str,'STATEFIPS':str}); need(len(d)==25 and d.field_id.nunique()==25,'expected 25 unique fields'); need(d.field_id.equals(d.CSBID) and d.field_id.str.fullmatch(r'45\d{13}').all(),'invalid identifiers'); need(set(d.STATEFIPS)=={'45'},'not SC FIPS 45'); need((d.CSBACRES>0).all(),'invalid acreage')
 for y in YEARS:
  need({f'crop_{y}',f'dominant_pct_{y}',f'valid_pixels_{y}',f'matches_csb_{y}'}.issubset(d),'annual columns missing'); need((d[f'valid_pixels_{y}']>0).all(),'invalid pixels'); need(d[f'dominant_pct_{y}'].between(0,100).all(),'invalid percentage'); need(set(d[f'matches_csb_{y}'].astype(str).str.lower())<={'true','false'},'invalid boolean')
 x=pd.read_csv(OUT/'derived_field_metrics.csv'); keys=['mean_dominant_pct','median_dominant_pct','min_dominant_pct','max_dominant_pct','dominant_pct_range','mean_valid_pixels','crop_transition_count','unique_dominant_crop_count','raster_csb_match_rate','ever_raster_csb_mismatch','acreage_iqr_outlier','confidence_iqr_outlier']; need(len(x)==25 and x.field_id.nunique()==25 and set(keys)<=set(x),'derived metrics invalid'); p=d[[f'dominant_pct_{y}' for y in YEARS]]; need(np.allclose(x.mean_dominant_pct,p.mean(axis=1)) and np.allclose(x.median_dominant_pct,p.median(axis=1)),'confidence formulas wrong'); expected=sum((d[f'crop_{y}']!=d[f'crop_{y+1}']).astype(int) for y in range(2020,2023)); need(np.array_equal(x.crop_transition_count,expected),'transition formula wrong'); need(x.crop_transition_count.between(0,3).all() and x.unique_dominant_crop_count.between(1,4).all() and x.raster_csb_match_rate.between(0,100).all(),'derived ranges invalid')
 c=pd.read_csv(OUT/'correlation_matrix_spearman.csv',index_col=0); banned={'field_id','CSBID','STATEFIPS','county',*[f'CDL{y}' for y in YEARS],*[f'crop_code_{y}' for y in YEARS]}; need(not banned.intersection(c.columns),'banned correlation variables'); need(np.allclose(c,c.T,equal_nan=True) and np.allclose(np.diag(c),1),'invalid correlation matrix'); pairs=pd.read_csv(OUT/'strongest_correlations.csv'); need(not pairs.duplicated(['variable_1','variable_2']).any(),'duplicate correlation pairs')
 stems=['01_acreage_distribution','02_acreage_vs_classification_confidence','03_metric_correlation_heatmap','04_crop_composition_by_year']; report=(A3/'EDA_REPORT.md').read_text();
 for stem in stems:
  for ext in ['png','svg']: need((OUT/'visualizations'/f'{stem}.{ext}').stat().st_size>1000,f'missing visual {stem}.{ext}')
  need(f'{stem}.png' in report,f'report does not embed {stem}')
 for stem in ['dashboard_crop_composition','dashboard_field_confidence']:
  for ext in ['png','svg']: need((OUT/'dashboard_assets'/f'{stem}.{ext}').stat().st_size>1000,f'missing dashboard {stem}.{ext}')
  need(Image.open(OUT/'dashboard_assets'/f'{stem}.png').width>=1800,'dashboard too narrow')
 nb=nbformat.read(ROOT/'notebooks/03_field_eda.ipynb',as_version=4); need(any(c.cell_type=='markdown' for c in nb.cells) and any(c.cell_type=='code' for c in nb.cells),'notebook cell types'); codes=[c for c in nb.cells if c.cell_type=='code']; need(all(c.execution_count is not None for c in codes) and any(c.outputs for c in codes),'notebook not executed'); need(not any(o.get('output_type')=='error' for c in codes for o in c.get('outputs',[])),'notebook error'); need('traceback' not in json.dumps(nb).lower(),'notebook traceback')
 for sec in ['Executive summary','Provenance','Dataset description','Data quality','Descriptive statistics','Visual findings','Dashboard selections','Limitations','Data-authenticity statement']: need(re.search(rf'^## {re.escape(sec)}',report,re.M|re.I),f'missing report section {sec}')
 need('25 fields' in report and 'exploratory' in report.lower(),'report scope missing'); readme=(A3/'README.md').read_text(); tracker=(ROOT/'docs/project/assignment-03-tracker.md').read_text(); need('nbconvert' in readme and 'verify_assignment_03.py' in readme,'README reproduction missing'); need('Actual computed findings' in tracker,'tracker results missing')
 text='\n'.join([report,tracker]); unsupported=[r'(?i)\b(pH|organic matter|weather|yield)\s+(?:was|were|averaged|correlated|increased|decreased)',r'(?i)correlation\s+(?:between|with)\s+(?:pH|organic matter|weather|yield)']; need(not any(re.search(p,text) for p in unsupported),'unsupported agronomic analysis claim')
 need(s['source_git_sha'] and json.loads((OUT/'environment.json').read_text())['git_source_sha'],'provenance missing'); need((OUT/'skill_run.log').read_text().strip().endswith('RESULT: SUCCESS'),'run log not successful'); need('/home/' not in json.dumps(s)+report+readme,'absolute user path'); tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines(); need(not any('__pycache__' in p or p.endswith('.pyc') for p in tracked),'tracked cache'); print('PASS: Assignment 3 verification succeeded (all checks passed).')
if __name__=='__main__':
 try: main()
 except Exception as e: print(f'FAIL: {e}',file=sys.stderr); raise
