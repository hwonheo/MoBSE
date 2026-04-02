# MoBSE PoC

Mixture of Brain-State Experts (MoBSE) proof-of-concept implementation with:

- Open-source brain-state template construction (`build_templates`)
- Dual-task training (OS-state classification + ETTh1 forecasting) (`train`)
- Performance and efficiency evaluation (`evaluate`)
- Paper-ready tables and figures (`report`)

## Quick Start

```bash
pip install -e .[dev,neuro,profile]
python -m mobse.cli prepare_data --config configs/config.yaml --mode openneuro_hc --subjects 30 --min-age 18 --diagnosis CONTROL --openneuro-datasets "ds000030,ds002790" --openneuro-task rest
python -m mobse.cli build_templates --config configs/config.yaml
python -m mobse.cli train --config configs/config.yaml
python -m mobse.cli evaluate --config configs/config.yaml --checkpoint artifacts/<run_id>/checkpoints/model_seed42_best.pt
python -m mobse.cli report --config configs/config.yaml --eval-glob "artifacts/*/logs/eval_*.json"
```

## Latest Status (2026-03-27)

- ETTh1 journal readiness audit is fully closed: `19/19 ready`.
- Temporal control ablation implemented: `model.etth1_temporal_encoder: mean|gru`.
- Controlled evidence completed with high power: `10` seeds x `4` regimes (`ETTh1-only/Dual-task` x `mean/GRU`).
- ETTh1 storyline figure package generated: `F1~F5` in `PNG` and `PDF`.
- ds000243 fMRIPrep resting-state ingest and Nilearn connectivity suite completed (6-subject pilot):
  - outputs: `artifacts/current_canonical/ds000243_nilearn_rest_suite_20260402/reports/`
  - note: dataset is already preprocessed (`derivatives/fmriprep`), and analysis used confounds-based regression (non-XCP-D path).

Primary references:

- Current status (archived): [docs/experiments/archive_derived_2026-03-31/current_status_etth1_story_2026-03-27.md](docs/experiments/archive_derived_2026-03-31/current_status_etth1_story_2026-03-27.md)
- Execution log (archived): [docs/experiments/archive_derived_2026-03-31/etth1_story_execution_log_2026-03-27.md](docs/experiments/archive_derived_2026-03-31/etth1_story_execution_log_2026-03-27.md)
- Figure execution plan (archived): [docs/experiments/archive_derived_2026-03-31/etth1_figure_execution_plan_2026-03-27.md](docs/experiments/archive_derived_2026-03-31/etth1_figure_execution_plan_2026-03-27.md)

## Docs

- Concept note: [docs/concept/MoBSE_note.md](docs/concept/MoBSE_note.md)
- Experiments archive index: [docs/experiments/archive_derived_2026-03-31/history_index_2026-03-26.md](docs/experiments/archive_derived_2026-03-31/history_index_2026-03-26.md)
- Full archived experiment set: [`docs/experiments/archive_derived_2026-03-31/`](docs/experiments/archive_derived_2026-03-31/)
- ds000243 ingest/preproc note (2026-04-01): [docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md](docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md)
- ds000243 network discussion note (2026-04-01): [docs/experiments/openneuro_ds000243_network_discussion_2026-04-01.md](docs/experiments/openneuro_ds000243_network_discussion_2026-04-01.md)
- ds000243 ingest/preproc+Nilearn log (updated 2026-04-02): [docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md](docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md)
- Changelog summary: [docs/CHANGELOG.md](docs/CHANGELOG.md)

## Progress Tracking

- Each CLI command prints stage progress to console by default.
- Progress is also written to `artifacts/<run_id>/logs/progress_<command>.json`.
- Disable console progress with `--no-progress`.

## Roadmap (Concept-Aligned)

### Phase 1 Remaining (PoC v1 closeout)

- Re-run balanced 3-seed comparison (`42/43/44`) after nuisance-regression updates for both `100-node` and `200-node`.
- Refresh all paper-facing tables/figures (`report`) with updated mean/std and significance tests.
- Complete efficiency profiling in the same run matrix (FLOPs, peak memory, latency) and lock target hardware notes (MPS/CUDA).
- Freeze reproducibility package: final public config, run manifests, and artifact index for one-command replay.

### Phase 1 Status (2026-03-14)

- Completed: balanced 3-seed reruns for `100-node` and `200-node` on HC127 (`phase1_nr_hc127_mps100_bal3_20260314`, `phase1_nr_hc127_mps200_bal3_20260314`).
- Completed: comparison package with mean/std and paired significance table (`artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/`).
- Completed: reproducibility freeze bundle (`repro_manifest.json`, run-specific resolved configs, `replay_commands.sh`).
- Note: MPS backend may report `peak_memory_mb=0` when backend telemetry is unavailable; latency/FLOPs are still reported.

### Phase 2 Plan (HCP-scale validation)

- Move from open-source proxy data to HCP-accessible cohort (target `>=300` subjects first).
- Re-run core ablations on HCP-scale data: atlas `100/200`, sparsity `10/20/30%`, routing `soft/hard`, template-prior on/off.
- Confirm whether PoC trends persist under stricter cohort control and larger sample size.

### Phase 3 Plan (Method extensions)

- Introduce learnable template perturbation on top of fixed brain-state priors.
- Expand to graph mixture variants with adaptive template composition.
- Prototype oscillatory graph dynamics (`phase/frequency`) and evaluate efficiency-accuracy tradeoffs.

## Data Layout

### OS timeseries input

`build_templates` supports both node-scoped and legacy flat layouts.

Preferred (node-scoped) layout:

```text
<data.os.timeseries_dir>/
  100/
    sub-0001/
      rest.npy
      wm.npy
      motor.npy
      language.npy
      attention.npy
    sub-0002/
      ...
  200/
    sub-0001/
      ...
```

Legacy flat layout (still accepted):

```text
<data.os.timeseries_dir>/
  sub-0001/
    rest.npy
    ...
```

Each file is a 2D array shaped `[time, nodes]`.

`build_templates` resolves `<timeseries_dir>/<num_nodes>/` first, and falls back to
`<timeseries_dir>/` if the node directory does not exist.

If you have raw NIfTI files, set `data.os.nifti_manifest` (CSV with `subject_id,state,nifti_path[,confounds_path]`) and `build_templates` will parcellate with Schaefer atlas automatically.

If you want to use preprocessed ABIDE PCP images (without running local fMRIPrep), generate a manifest first:

```bash
./.venv/bin/python scripts/make_abide_pcp_manifest.py \
  --out-manifest data/abide_pcp_manifest_rest.csv \
  --data-dir data/_nilearn_cache \
  --pipeline cpac \
  --min-age 18 \
  --dx-group 2 \
  --n-subjects 300
```

Then set `data.os.nifti_manifest` to that CSV and run `build_templates`.

### One-command data preparation

- `prepare_data --mode openneuro_hc`: downloads ETTh1 and OpenNeuro dataset, applies strict HC filtering (requires diagnosis/group and age columns; defaults to `CONTROL`, `>=18`), then converts selected BOLD scans to OS-like ROI time-series.
- `prepare_data --mode openneuro`: downloads ETTh1 and OpenNeuro dataset without strict HC requirement (auto-discovers files from OpenNeuro GraphQL API). Use `--openneuro-dataset` or `--openneuro-datasets "dsA,dsB,..."`, plus `--openneuro-snapshot`, `--openneuro-task` (comma-separated allowed, e.g. `rest,restingstate`) to target/fallback across public fMRI datasets.
- `prepare_data --mode abide_control`: downloads ABIDE PCP control subjects (`DX_GROUP=2`) with `rois_cc200` or `rois_cc400`, then builds network-state variants by partitioning ROI nodes into `len(data.os.states)` clusters from group functional connectivity.
- `prepare_data --mode public_proxy`: downloads ETTh1 and nilearn development fMRI proxy dataset, then converts into OS-like per-state ROI time-series.
- `prepare_data --mode synthetic`: downloads ETTh1 and generates synthetic OS-like ROI time-series.

### Nuisance Regression (Raw fMRI -> ROI time-series)

Default config applies a paper-style denoising stack before ROI extraction:

- CompCor-like high-variance confounds (`nuisance_compcor_components`)
- Global signal regression (GSR)
- Derivative + quadratic expansion of confounds
- Temporal detrend + band-pass (`0.008-0.1Hz` by default)

Related config keys are under `data.os.nuisance_*`.

### ETTh1 input

Set `data.etth1.csv_path` to the ETTh1 CSV path.

## Outputs

All runs are written under `artifacts/<run_id>/`:

- `templates/`: serialized brain-state template bank
- `checkpoints/`: trained models
- `logs/`: metrics and profiling JSON files
- `reports/`: summary tables and publication-ready figures

## Key Ablation Switches

- `model.use_template_prior=true|false`: use fixed OS brain templates vs learned random expert graphs.
- `model.routing_mode=soft|hard`: routing policy.
- `model.arch=mobse|transformer|sparse_transformer|moe`: baseline family.
- `model.etth1_temporal_encoder=mean|gru`: ETTh1 temporal summary branch (`mean` baseline vs `GRU` control).

## Loss Stabilization (Dual-task)

- `train.etth1_loss_type`: `huber` (default), `mse`, or `mae`.
- `train.normalize_task_losses=true`: normalizes per-task losses by initial loss scale to avoid one task dominating.
- `train.selection_metric=weighted_normalized_loss`: uses balanced validation score for checkpoint selection.
- `train.early_stopping_patience`: stops when balanced validation score no longer improves.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

- **Hwon Heo**
- 📧 <heohwon@gmail.com>
- [<img src="https://orcid.org/sites/default/files/images/orcid_16x16.png" alt="ORCID"> ORCID 0000-0002-6103-4680](https://orcid.org/0000-0002-6103-4680)
