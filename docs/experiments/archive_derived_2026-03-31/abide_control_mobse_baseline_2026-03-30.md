# ABIDE Control MoBSE Baseline Note (2026-03-30)

## Scope

This note records a baseline training plan for `MoBSE` on ABIDE PCP control subjects,
with **no augmentation** and the **current default split behavior** in the codebase.

Target workflow:

1. `prepare_data --mode abide_control`
2. `build_templates`
3. `train`
4. `evaluate`

Primary config:

- `configs/2026-03-30/abide_control_cc200_mobse_base.yaml`
- run id: `abide_control_cc200_mobse_base_20260330`

## Data and Labeling Policy

- Dataset: `ABIDE PCP`
- Group: `control only` (`DX_GROUP=2`)
- Derivative: `rois_cc200`
- Pipeline: `cpac`
- Age gate: `>= 18`

State-label construction in this baseline:

- ROI nodes are partitioned into `len(data.os.states)` clusters from group FC affinity.
- For each state, only cluster-matched node channels are retained (others set to zero).
- Result is saved as per-subject state `.npy` files under
  `data/legacy_misc/os_abide_cc200_control_base/timeseries/<num_nodes>/<subject_id>/<state>.npy`.

## Split and Augmentation

### Split

Current split is unchanged (code default):

- If explicit subject prefixes are not provided,
  `create_os_dataloaders()` uses random index split via
  `split_indices(train_ratio, val_ratio, seed)`.
- In this run, we keep that default behavior.

### Augmentation

- **No augmentation** is applied.
- Rationale: establish a clean baseline before introducing any synthetic perturbation.

## Why This Baseline First

- Confirms that MoBSE can train end-to-end on real human rs-fMRI-derived ROI signals.
- Isolates architecture behavior without augmentation confounds.
- Provides reference metrics for later experiments:
  - site-aware split
  - cc200 vs cc400 comparison
  - augmentation ablation (if needed)

## Commands

```bash
# 1) prepare ABIDE control states (no augmentation path)
python -m mobse.cli prepare_data \
  --config configs/2026-03-30/abide_control_cc200_mobse_base.yaml \
  --mode abide_control \
  --subjects 80 \
  --abide-derivative rois_cc200 \
  --abide-pipeline cpac \
  --abide-partition-subjects 80 \
  --min-age 18

# 2) build templates/windows
python -m mobse.cli build_templates \
  --config configs/2026-03-30/abide_control_cc200_mobse_base.yaml

# 3) train MoBSE (OS task only in this baseline)
python -m mobse.cli train \
  --config configs/2026-03-30/abide_control_cc200_mobse_base.yaml

# 4) evaluate
python -m mobse.cli evaluate \
  --config configs/2026-03-30/abide_control_cc200_mobse_base.yaml
```

## Success Criteria

- `prepare_data.json` contains:
  - `mode = "abide_control"`
  - `subjects_collected > 0`
  - `network_partition_csv` path
- template artifacts exist:
  - `atlas200_sp20_template_bank.npz`
  - `os_windows_nodes200.npz`
- training artifact exists:
  - `checkpoints/model_seed*_best.pt`
- evaluation artifact exists:
  - `logs/eval_mobse.json`

## Execution Snapshot (2026-03-30)

Executed run:

- run id: `abide_control_cc200_mobse_base_20260330`
- config: `configs/2026-03-30/abide_control_cc200_mobse_base.yaml`

Observed outputs:

- `prepare_data`: requested `80`, collected `22` (adult control filter applied)
- `build_templates`: `atlas200_sp20_template_bank.npz` generated
- `train`: `checkpoints/model_seed42_best.pt` generated
- `evaluate` (OS task):
  - accuracy: `0.9788`
  - f1_macro: `0.9809`
  - loss: `0.1214`

Artifact references:

- `artifacts/abide_control_cc200_mobse_base_20260330/logs/prepare_data.json`
- `artifacts/abide_control_cc200_mobse_base_20260330/logs/eval_mobse.json`

## Next Step After Baseline

1. Lock this baseline as reference.
2. Add subject/site-aware split (leave-site-out style) for stronger generalization check.
3. Compare `rois_cc200` vs `rois_cc400` under the same split and training settings.
