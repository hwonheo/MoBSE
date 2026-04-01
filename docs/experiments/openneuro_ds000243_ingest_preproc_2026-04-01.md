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
