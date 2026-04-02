# OpenNeuro ds000243 Ingest + Preproc Note (2026-04-01)

## Summary
- Dataset root: `/Users/hwon/Documents/Git/MoBSE/data/current_canonical/openneuro_ds000243`
- fMRIPrep derivative detected at: `derivatives/fmriprep`
- Subject range: `sub-001` to `sub-052` (52 subjects)
- Functional runs found: 90 (`*desc-preproc_bold.nii.gz`)
- Confounds found: 90 (`*desc-confounds_timeseries.tsv`)
- fMRIPrep metadata: `GeneratedBy.Version = 25.2.5`

## Preprocessing Conversion (NIfTI -> NPY Timeseries)
- Atlas/ROI scheme: Schaefer 2018 parcellation
- Generated node sets:
  - `timeseries/100` (Schaefer-100)
  - `timeseries/200` (Schaefer-200)
- Output count:
  - `timeseries/100`: 90 files (`rest.npy`)
  - `timeseries/200`: 90 files (`rest.npy`)
- Manifest:
  - `manifests/fmriprep_rest_manifest_runs.csv`
- Subject key policy:
  - run-level disambiguation with `sub-XXX_run-Y` (to avoid overwrite across multi-run subjects)

## Execution Notes
- TR auto-read from image header (sample observed: `2.5`)
- Denoising input used fMRIPrep confounds TSV per run.
- Additional re-derived CompCor/GSR during this conversion was disabled for runtime stability.
- Nilearn warning observed:
  - `confounds will be standardized using the sample std instead of the population std` (future release behavior notice, non-blocking)

## Analysis Readiness
- Current status: ready for MoBSE downstream analysis steps that consume timeseries directories.
- Ready paths:
  - `/Users/hwon/Documents/Git/MoBSE/data/current_canonical/openneuro_ds000243/timeseries/100`
  - `/Users/hwon/Documents/Git/MoBSE/data/current_canonical/openneuro_ds000243/timeseries/200`
- Recommended next immediate step:
  - point the target config `data.os.timeseries_dir` to this dataset root and run `build_templates -> train/evaluate`.

## Template Build Log (2026-04-01)
- Config:
  - `/Users/hwon/Documents/Git/MoBSE/configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml`
- Command:
  - `python -m mobse.cli build_templates --config configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml`
- Result:
  - completed successfully (`Built template banks: 4`)
  - OS windows generated (`os_windows_nodes100.npz`, 757 windows)
- Template outputs:
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/templates/atlas100_sp10_template_bank.npz`
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/templates/atlas100_sp20_template_bank.npz`
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/templates/atlas200_sp10_template_bank.npz`
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/templates/atlas200_sp20_template_bank.npz`

## Pipeline Smoke (Train/Eval) (2026-04-01)
- Train command:
  - `python -m mobse.cli train --config configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml`
- Eval command:
  - `python -m mobse.cli evaluate --config configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml`
- Key outputs:
  - checkpoint: `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/checkpoints/model_seed42_best.pt`
  - train summary: `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/logs/train_summary.json`
  - eval json: `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/logs/eval_mobse.json`
- Interpretation note:
  - this dataset slice is `rest` single-class only, so OS classification metrics (accuracy/f1) are trivially saturated and not suitable for model comparison.

## Network Analysis Report (2026-04-01)
- Script:
  - `/Users/hwon/Documents/Git/MoBSE/scripts/analyze_template_networks.py`
- Command:
  - `python scripts/analyze_template_networks.py --template-glob 'artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/templates/atlas*_template_bank.npz' --state rest --out-dir artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/reports`
- Outputs:
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/reports/template_network_metrics.csv`
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/reports/template_network_metrics.json`
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/reports/template_network_metrics.md`
- Quick read:
  - higher sparsity target (`sp20`) increased global efficiency (~0.51 vs ~0.37-0.39 at `sp10`)
  - modularity on LCC decreased at `sp20` (~0.32-0.33) vs `sp10` (~0.47-0.49)
  - detected community count dropped from 5 (`sp10`) to 3 (`sp20`) for both 100 and 200 nodes

## Key Interpretation (Locked)
- `sp20`에서 global efficiency가 상승(~0.51)했다.
- 대신 modularity와 community 수는 감소(5 -> 3)했다.
- 종합하면, `sp20`은 더 통합된 연결 구조로 이동하는 패턴을 보인다.

## Follow-up Plan
- 네트워크 모델 고도화 단계에서 MoBSE의 장점을 기존 Legacy 모델과 비교하는 실험을 진행한다.
- 비교 축(권장):
  - 동일 데이터/동일 split에서 `MoBSE vs legacy(Transformer/Sparse-Transformer/MoE baseline)` 비교
  - 동일 노드수(100/200), 동일 sparsity(sp10/sp20), 동일 seed 세트
  - 성능지표 + 네트워크 지표(효율성/모듈성/커뮤니티) 동시 보고

## Follow-up Execution Started (2026-04-02)
- 1차 실행 범위:
  - models: `mobse`, `transformer`, `sparse_transformer`, `moe`
  - nodes: `100`, `200`
  - sparsity: `0.1`, `0.2`
  - seeds: `42` (pilot)
- Total runs completed: `16`
- Study output root:
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_modelcomp_20260402/reports`
- Core files:
  - `model_comparison_seedwise.csv`
  - `model_comparison_summary.csv`
  - `model_comparison_summary.md`

### Pilot Readout (Performance + Efficiency)
- 성능(accuracy/f1)은 전 조건에서 `1.0`으로 포화됨 (rest 단일 클래스 특성).
- 효율성 기준에서는 MoE가 가장 낮은 latency/FLOPs를 보였고, MoBSE는 상대적으로 높은 FLOPs를 보임.
- 결론적으로 현재 파일럿은 **구조/효율 프로파일 확인 단계**로 해석해야 하며, 성능 우열 해석에는 부적합.

### Technical Note
- 비교 실행 중 발견된 baseline 초기화 버그 수정:
  - `SparseTransformerBaseline` 인자 정합(`etth1_temporal_encoder`) 반영
  - 파일: `/Users/hwon/Documents/Git/MoBSE/mobse/models/baselines.py`
- `200-node` 비교를 위해 ds000243 전용 windows 추가 생성:
  - run id: `ds000243_rest_templates_n200_windows_20260402`

## Nilearn Resting-State Suite (2026-04-02)
- 목적:
  - `ds000243`가 이미 fMRIPrep 완료 데이터라는 전제에서, resting-state 대표 분석을 Nilearn 예제 계열로 즉시 재현.
- 입력:
  - `data/current_canonical/openneuro_ds000243/derivatives/fmriprep`
- 실행 스크립트:
  - `/Users/hwon/Documents/Git/MoBSE/scripts/run_ds000243_nilearn_rest_suite.py`
- 핵심 설정:
  - 분석 대상: 6 subjects (manifest 기준)
  - seed-to-voxel seed: `(0, -52, 26)` (MNI)
  - decomposition components: 8
- 산출물 루트:
  - `/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ds000243_nilearn_rest_suite_20260402/reports`
- 대표 산출물:
  - `nilearn_rest_suite_manifest.json`
  - `nilearn_rest_suite_report.md`
  - `inverse_covariance_group_matrix.npy`
  - `inverse_covariance_connectome.png`
  - `seed_to_voxel_corr_subject0.nii.gz`
  - `compare_decomposition_{canica,dictlearning}_components.nii.gz`
  - `dictlearning_extracted_regions.nii.gz`

### Nuisance Regression Policy (Template Build vs Nilearn Suite)
- 템플릿 빌드 경로(`build_templates`)는 기존 MoBSE 설정대로 `CompCor/GSR` 기반 nuisance regression 정책을 사용.
- 이번 Nilearn suite는 fMRIPrep confounds TSV를 직접 주입해 회귀/정규화를 수행했으며, `XCP-D` 파생산물을 입력으로 사용하지 않음.
- 따라서 현재 결과 해석은 `CompCor/GSR 계열 confound regression` 관점에서 일관되게 유지됨.

### Interpretation Anchor (for Discussion)
- 기존 템플릿 네트워크 결과와 합쳐 보면, `sp20`의 효율성 상승과 모듈성/커뮤니티 축소는
  - resting-state에서 네트워크가 더 통합(integrated)된 표현으로 수렴하는 방향성과 정합적임.
- 후속 실험은 성능 포화(rest 단일 클래스) 대신
  - 연결 구조 해석력(모듈성/효율성/seed-map 일관성)과
  - 계산 효율(latency/FLOPs)에서 `MoBSE vs Legacy dFC`를 비교하는 것이 타당.
