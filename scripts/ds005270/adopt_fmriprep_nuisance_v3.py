"""Adopt and revalidate existing four-subject arrays; never rerun preprocessing."""
from pathlib import Path
import argparse,csv,hashlib,json
import numpy as np
from validate_adapter import build_design,get_fd,retain,psc,finite_variance,MOTION,CONDITIONS

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
ROOT=args.root.resolve()
REPO=Path('/Users/hwon/projects/Git/Manuscript/MoBSE')
OLD=ROOT/'ds005270_roi_adapter_validation_a1'
OUT=args.out.resolve()
if OUT.exists():raise FileExistsError(OUT)
OUT.mkdir()
policy=json.loads((REPO/'configs/ds005270/protocol_v2_qc_policy.json').read_text())
policy['rule_version']='ds005270_fmriprep_nuisance_v3_20261019'
policy['status']='approved fMRIPrep WM/CSF definition; four-subject technical validation; no full-cohort/training authorization'
policy['supersedes']='protocol_v2_qc_policy.json (preserved)'
policy['authority']='User approved Schaefer-100 retention, sub-003 primary exclusion and explicit fMRIPrep nuisance amendment with four-subject validation.'
policy['execution']['roi_extraction']=False
policy['scope']='Limited four-subject validation authorized and completed by reuse. All execution flags control subsequent execution and remain false.'
policy['roi_scope']['partial_fov_acceptance_rule']='sub-003 excluded from primary analysis by explicit decision for posterior FOV deficit; no new numeric exclusion threshold for other subjects'
policy['default_preprocessing']['downstream_adapter']='scripts/ds005270/validate_adapter.py; fMRIPrep provided white_matter and csf means explicitly adopted in v3; numerical validation reused from four subjects'
policy.pop('nuisance_intent_preserved_not_executed')
policy['nuisance']={
 'version':'fmriprep_regional_means_v1',
 'definition_change':'Replace AFNI 3dSeg eroded mask WM/CSF means with fMRIPrep 25.2.6 provided regional white_matter/csf means. No equivalence to legacy eroded masks claimed.',
 'source':'subject task-nbk desc-confounds_timeseries.tsv, white_matter and csf columns; exact file SHA and run provenance retained',
 'mask_source':'fMRIPrep generated WM/CSF regional masks from its anatomical tissue segmentation workflow; executed CITATION.md identifies FSL FAST tissue segmentation. Exact regional-mean binary masks are not exported among collected derivatives; no extra erosion or probability threshold applied here. aCompCor masks are not substituted.',
 'reproduction':'Use exact pinned fMRIPrep image/run and archived confounds TSV. Do not reconstruct regional means from standard-space probseg files using guessed thresholds.',
 'columns':['intercept','linear_trend']+list(MOTION)+[k+'_derivative1' for k in MOTION]+[k+'_power2' for k in MOTION]+[k+'_derivative1_power2' for k in MOTION]+['white_matter_PSC','csf_PSC'],
 'motion_units':'rot_x/y/z radians read from metadata, converted to degrees for nuisance; trans_x/y/z mm. FD uses radians times 50mm.',
 'derivatives':'backward differences computed directly from motion; first derivative row exactly 0 by definition',
 'sequence':'atlas ROI intersect fMRIPrep functional brain mask -> unweighted voxel mean -> run-mean PSC; separately regional WM/CSF mean -> run-mean PSC; OLS 28-column full-run design -> residual 266x100 -> fixed 15-frame windows -> features',
 'trend':'(volume_index - mean)/population SD',
 'missing':'Reject nonfinite motion/WM/CSF/ROI/design; no imputation. Reject zero-mean PSC signals or zero-variance signals. First reported FD undefined row excluded from summaries; own FD_0=0 by definition.',
 'filter':'No added smoothing, bandpass, cosine, CompCor, global signal, task regression or window z-score',
 'fit':'OLS full 266 volumes, numpy.linalg.lstsq rcond=None; require rank28, finite nonzero-variance residual; no regression censoring',
 'censor':'FD>0.5mm plus t-1,t,t+1; reject whole 15-frame windows; no removed/interpolated frames; main >=3/condition, sensitivity cannot rescue main failure',
 'offline_limitation':'Full-run preprocessing, PSC and nuisance use time points outside each window; no 30-second-acquisition claim'
}
policy['qc']['Q6_nuisance_masks']='fMRIPrep supplied WM/CSF signals must be finite, nonzero-variance and nonzero run mean; source-mask provenance retained. Historical AFNI voxel counts are not reused as fMRIPrep mask counts.'
policy['qc']['fov_action']='Individual review; sub-003 primary exclusion explicitly approved for posterior deficit. No general new numeric cutoff.'
policy['approved_primary_exclusions']={'sub-003':'posterior acquired FOV deficit; explicit user decision','sub-006':'existing Q2 motion and Q3 windows failure'}
policy['release_gate']={'ready':False,'reasons':['remaining individual ROI/anatomical quality review is not a quantitative signal pass','full-cohort/training execution not authorized'],'resolved':['Schaefer100 maintained','sub-003 primary exclusion approved','fMRIPrep WM/CSF definition approved','four-subject adapter technical validation passed']}
(OUT/'protocol_v3.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2))
manifest=json.loads((OLD/'delivery_manifest.json').read_text())
for rel,h in manifest['files'].items():assert hashlib.sha256((OLD/rel).read_bytes()).hexdigest()==h,rel
for path,h in json.loads((OLD/'source_sha256.json').read_text()).items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
decisions=json.loads((REPO/'results/ds005270/qc_adoption_v2/subject_decisions.json').read_text())
decisions['rule_version']=policy['rule_version']
for row in decisions['subjects']:
 row['rule_version']=policy['rule_version']
 if row['subject']=='sub-003':row.update(status='exclude',reasons=['user_approved_primary_exclusion_posterior_FOV_deficit'])
 row['analysis_inclusion_approved']=False
decisions['note']='sub-003/006 primary exclusion confirmed; other four technical validation does not grant final scientific inclusion'
(OUT/'subject_decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2))
valid=[]
for sub in ['sub-001','sub-002','sub-004','sub-013']:
 parent=ROOT/('ds005270_fmriprep_results' if sub=='sub-001' else 'ds005270_pilot6_results')/(sub+'-run')/sub
 cp=parent/'func'/f'{sub}_task-nbk_desc-confounds_timeseries.tsv'
 with cp.open() as h:rows=list(csv.DictReader(h,delimiter='\t'))
 assert len(rows)==266
 col=lambda k:np.array([float(r[k]) for r in rows])
 mot=np.column_stack([col(k) for k in MOTION]);x=build_design(mot,col('white_matter'),col('csf'))
 savedx=np.load(OLD/sub/'nuisance_candidate.npy');assert np.array_equal(x,savedx)
 raw=np.load(OLD/sub/'roi_raw.npy');savedz=np.load(OLD/sub/'roi_clean_candidate.npy');y=psc(raw)
 z=y-x@np.linalg.lstsq(x,y,rcond=None)[0];assert np.allclose(z,savedz,atol=1e-10,rtol=0)
 assert finite_variance(raw) and finite_variance(z) and z.shape==(266,100)
 windows=json.loads((ROOT/'ds005270_linux_plan/qc_reference'/f'{sub}_windows.json').read_text())
 _,kept=retain(get_fd(mot),windows)
 prior=json.loads((ROOT/'ds005270_pilot6_comparison'/f'{sub}_comparison.json').read_text())
 assert all(list(map(bool,kept[m][c]))==prior['windows'][m][c]['kept'] for m in kept for c in CONDITIONS)
 for c in CONDITIONS:
  for k,start in enumerate(windows['conditions'][c]['main']['first_volume']):
   if not kept['main'][c][k]:continue
   w=z[start:start+15];assert finite_variance(w)
   fc=np.arctanh(np.clip(np.corrcoef(w,rowvar=False)[np.triu_indices(100,1)],-1+1e-6,1-1e-6))
   assert [w.size,len(fc),len(w.mean(0)),len(np.r_[w.mean(0),w.std(0,ddof=1)])]==[1500,4950,100,200]
   assert np.isfinite(fc).all()
 lineage={}
 for f in [cp,*parent.glob('log/*/fmriprep.toml'),parent.parent/'logs/CITATION.md',OLD/sub/'roi_raw.npy',OLD/sub/'nuisance_candidate.npy',OLD/sub/'roi_clean_candidate.npy']:
  lineage[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 valid.append({'subject':sub,'status':'pass_technical_validation_only','rank':int(np.linalg.matrix_rank(x)),'design_exact_reproduction':True,'residual_max_abs_difference':float(np.max(np.abs(z-savedz))),'main_windows':{c:int(sum(kept['main'][c])) for c in CONDITIONS},'source_lineage_sha256':lineage})
result={'version':policy['rule_version'],'method':'existing arrays reused by explicit content hashes; no duplicate BOLD extraction','subjects':valid,'source_checks_passed':True,'new_scientific_thresholds':False,'training_executed':False,'preprocessing_rerun':False,'full_cohort_executed':False,'remaining_quality_review':True}
(OUT/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps({'validated':len(valid),'sub003':'exclude','sub006':'exclude','method':'reuse plus numerical reproduction'}))
