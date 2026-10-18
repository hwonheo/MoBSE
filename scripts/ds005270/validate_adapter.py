"""Limited four-subject validation only; frozen images in, new candidate outputs out.

WM/CSF columns are fMRIPrep regional means, NOT asserted equivalent to AFNI
eroded-mask means. Outputs are explicitly candidates, not approved model inputs.
"""
from pathlib import Path
import argparse, csv, hashlib, json
import nibabel as nb
import numpy as np

CONDITIONS = ('ZeroBack','OneBack','TwoBack')
MOTION = ('rot_x','rot_y','rot_z','trans_x','trans_y','trans_z')

def psc(x):
    x=np.asarray(x,dtype=float)
    if not np.isfinite(x).all() or np.any(x.mean(axis=0)==0) or np.any(x.std(axis=0)==0):
        raise ValueError('Unusable signal: nonfinite, zero mean or zero variance; no imputation')
    return 100*(x/x.mean(axis=0)-1)

def build_design(motion,wm,csf):
    if motion.shape!=(266,6) or not np.isfinite(motion).all():raise ValueError('Motion rows invalid')
    mot=motion.copy();mot[:,:3]=np.rad2deg(mot[:,:3])
    derivative=np.vstack([np.zeros((1,6)),np.diff(mot,axis=0)])
    t=np.arange(266,dtype=float);t=(t-t.mean())/t.std()
    x=np.column_stack([np.ones(266),t,mot,derivative,mot**2,derivative**2,psc(wm),psc(csf)])
    if x.shape!=(266,28) or not np.isfinite(x).all() or np.linalg.matrix_rank(x)!=28:
        raise ValueError('Nuisance design invalid or rank deficient')
    return x

def get_fd(motion):
    return np.r_[0,(np.abs(np.diff(motion,axis=0))*[50,50,50,1,1,1]).sum(axis=1)]

def retain(fd,windows):
    spikes=fd>.5;flags=spikes.copy();flags[1:]|=spikes[:-1];flags[:-1]|=spikes[1:]
    kept={}
    for mode in ('main','sensitivity'):
        kept[mode]={}
        for c in CONDITIONS:
            w=windows['conditions'][c][mode];starts=w['first_volume']
            if len(starts)!=4 or any(s<0 or s+15>266 for s in starts):raise ValueError('Invalid window index')
            if not np.allclose(np.array(starts)*2,w['starts_s']):raise ValueError('Window timing mismatch')
            kept[mode][c]=[not flags[s:s+15].any() for s in starts]
    return flags,kept

def finite_variance(x):
    return bool(np.isfinite(x).all() and np.all(np.var(x,axis=0)>0))

def run(root,out):
    if out.exists():raise FileExistsError('Refuse to overwrite output '+str(out))
    out.mkdir(parents=True)
    ref=root/'ds005270_linux_plan/qc_reference'
    policy=json.loads((root/'ds005270_qc_adoption/repo_additions/configs/ds005270/protocol_v2_qc_policy.json').read_text())
    atlaspath=Path('/Users/hwon/projects/Git/Manuscript/MoBSE')/policy['atlas']['file_rel']
    assert hashlib.sha256(atlaspath.read_bytes()).hexdigest()==policy['atlas']['sha256']
    ai=nb.load(atlaspath);atlas=np.asarray(ai.dataobj,dtype=int)
    assert set(np.unique(atlas))==set(range(101))
    all_summary=[];sources={}
    for sub in ('sub-001','sub-002','sub-004','sub-013'):
        parent=root/('ds005270_fmriprep_results' if sub=='sub-001' else 'ds005270_pilot6_results')/(sub+'-run')/sub
        f=parent/'func';prefix=sub+'_task-nbk'
        bp=f/(prefix+'_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz')
        mp=f/(prefix+'_space-MNI152NLin2009cAsym_res-2_desc-brain_mask.nii.gz')
        cp=f/(prefix+'_desc-confounds_timeseries.tsv');jp=cp.with_suffix('.json')
        wp=ref/(sub+'_windows.json');meta=bp.with_name(bp.name.replace('.nii.gz','.json'))
        for p in (bp,mp,cp,jp,wp,meta,atlaspath):sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        bi=nb.load(bp);mi=nb.load(mp);bmeta=json.loads(meta.read_text());cmeta=json.loads(jp.read_text())
        assert bi.shape==(*atlas.shape,266) and bi.header.get_zooms()[3]==2
        assert np.allclose(bi.affine,ai.affine) and np.allclose(mi.affine,ai.affine)
        assert bmeta['RepetitionTime']==2 and bmeta['StartTime']==0 and bmeta['SliceTimingCorrected']
        assert all(cmeta[k]['Units']==('rad' if k.startswith('rot') else 'mm') for k in MOTION)
        with cp.open() as h:rows=list(csv.DictReader(h,delimiter='\t'))
        assert len(rows)==266
        col=lambda k:np.array([float(r[k]) if r[k]!='n/a' else np.nan for r in rows])
        motion=np.column_stack([col(k) for k in MOTION]);fd=get_fd(motion)
        fd_difference=float(np.max(np.abs(fd[1:]-col('framewise_displacement')[1:])))
        assert fd_difference<1e-10
        wm,csf=col('white_matter'),col('csf');x=build_design(motion,wm,csf)
        windows=json.loads(wp.read_text());flags,kept=retain(fd,windows)
        old=json.loads((root/'ds005270_pilot6_comparison'/f'{sub}_comparison.json').read_text())
        assert all([bool(v) for v in kept[m][c]]==old['windows'][m][c]['kept'] for m in kept for c in CONDITIONS)
        mask=np.asarray(mi.dataobj)>0;data=bi.get_fdata(dtype=np.float32)
        raw=np.empty((266,100));stats=[]
        t=np.column_stack([np.ones(266),np.arange(266)])
        for roi in range(1,101):
            roi_mask=atlas==roi;use=roi_mask&mask;outside=roi_mask&~mask
            if not use.any():raise ValueError('Empty ROI; no fill')
            v=data[use].astype(float);raw[:,roi-1]=v.mean(axis=0)
            residual=v.T-t@np.linalg.lstsq(t,v.T,rcond=None)[0]
            sd=residual.std(axis=0,ddof=2);good=sd>0
            tsnr=v.mean(axis=1)[good]/sd[good]
            vout=data[outside].astype(float)
            stats.append({'roi':roi,'n_atlas':int(roi_mask.sum()),'n_mask':int(use.sum()),
              'mask_fraction':float(use.sum()/roi_mask.sum()),'raw_mean':float(raw[:,roi-1].mean()),
              'raw_sd':float(raw[:,roi-1].std()),'inmask_nonfinite_values':int((~np.isfinite(v)).sum()),
              'inmask_zero_variance_voxels':int((v.std(axis=1)==0).sum()),
              'inmask_detrended_tsnr_median':float(np.median(tsnr)) if len(tsnr) else None,
              'outside_mask_voxels':int(outside.sum()),
              'outside_mask_mean':float(vout.mean()) if vout.size else None,
              'outside_mask_zero_variance_voxels':int((vout.std(axis=1)==0).sum()) if vout.size else 0})
        y=psc(raw);beta=np.linalg.lstsq(x,y,rcond=None)[0];clean=y-x@beta
        assert finite_variance(raw) and finite_variance(clean)
        features=[]
        for c in CONDITIONS:
            for k,s in enumerate(windows['conditions'][c]['main']['first_volume']):
                if not kept['main'][c][k]:continue
                w=clean[s:s+15];assert w.shape==(15,100) and finite_variance(w)
                fc=np.corrcoef(w,rowvar=False)[np.triu_indices(100,1)]
                feature=[w.reshape(-1),np.arctanh(np.clip(fc,-1+1e-6,1-1e-6)),w.mean(0),np.r_[w.mean(0),w.std(0,ddof=1)]]
                assert [len(a) for a in feature]==[1500,4950,100,200] and all(np.isfinite(a).all() for a in feature)
                features.append({'condition':c,'index':k,'start_volume':s,'lengths':[len(a) for a in feature]})
        for j,row in enumerate(stats):row['candidate_residual_sd']=float(clean[:,j].std())
        so=out/sub;so.mkdir();np.save(so/'roi_raw.npy',raw);np.save(so/'roi_clean_candidate.npy',clean);np.save(so/'nuisance_candidate.npy',x)
        with (so/'roi_signal_review.tsv').open('w') as h:
            wr=csv.DictWriter(h,fieldnames=list(stats[0]),delimiter='\t');wr.writeheader();wr.writerows(stats)
        summary={'subject':sub,'status':'technical_candidate_validated_not_final_inclusion','shape':[266,100],
          'confound_columns':['intercept','linear_trend']+list(MOTION)+[k+'_derivative1' for k in MOTION]+[k+'_power2' for k in MOTION]+[k+'_derivative1_power2' for k in MOTION]+['white_matter_PSC','csf_PSC'],
          'nuisance_rank':int(np.linalg.matrix_rank(x)),'design_condition_number':float(np.linalg.cond(x)),
          'fd_max_difference':fd_difference,'main_windows':{c:int(sum(kept['main'][c])) for c in CONDITIONS},
          'flagged_volume_count':int(flags.sum()),'censor_in_regression':False,'removed_or_interpolated_frames':0,
          'nonsteady_columns':{k:int(col(k).sum()) for k in rows[0] if k.startswith('non_steady_state_outlier')},
          'raw_and_candidate_residual_finite_nonzero_variance':True,'feature_contract':features,
          'low_mask_roi_signal_stats':[s for s in stats if s['mask_fraction']<.9],
          'remaining_gate':'WM/CSF regional means do not establish AFNI eroded-mask equivalence; no final nuisance-source approval; no final signal quality cutoff or inclusion decision.'}
        (so/'validation.json').write_text(json.dumps(summary,indent=2));all_summary.append(summary)
        del data
        print(sub,'validated',flush=True)
    (out/'summary.json').write_text(json.dumps(all_summary,indent=2))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in sources.items())
    (out/'source_sha256.json').write_text(json.dumps(sources,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.root.resolve(),a.out.resolve())
