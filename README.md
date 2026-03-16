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

## Docs

- Concept note: [docs/concept/MoBSE_note.md](docs/concept/MoBSE_note.md)
- Experiments note (2026-03-13): [docs/experiments/experiments_note_2026-03-13.md](docs/experiments/experiments_note_2026-03-13.md)
- Phase-2 detailed note (2026-03-14): [docs/experiments/experiments_note_phase2_2026-03-14.md](docs/experiments/experiments_note_phase2_2026-03-14.md)
- Phase-2 report (2026-03-14): [docs/experiments/phase2_report_2026-03-14.md](docs/experiments/phase2_report_2026-03-14.md)
- Phase-2 public guide (easy version): [docs/experiments/phase2_report_2026-03-14_public.md](docs/experiments/phase2_report_2026-03-14_public.md)
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

`build_templates` expects preprocessed time-series files by default:

```text
<data.os.timeseries_dir>/
  sub-0001/
    rest.npy
    wm.npy
    motor.npy
    language.npy
    attention.npy
  sub-0002/
    ...
```

Each file is a 2D array shaped `[time, nodes]`.

If you have raw NIfTI files, set `data.os.nifti_manifest` (CSV with `subject_id,state,nifti_path[,confounds_path]`) and `build_templates` will parcellate with Schaefer atlas automatically.

### One-command data preparation

- `prepare_data --mode openneuro_hc`: downloads ETTh1 and OpenNeuro dataset, applies strict HC filtering (requires diagnosis/group and age columns; defaults to `CONTROL`, `>=18`), then converts selected BOLD scans to OS-like ROI time-series.
- `prepare_data --mode openneuro`: downloads ETTh1 and OpenNeuro dataset without strict HC requirement (auto-discovers files from OpenNeuro GraphQL API). Use `--openneuro-dataset` or `--openneuro-datasets "dsA,dsB,..."`, plus `--openneuro-snapshot`, `--openneuro-task` (comma-separated allowed, e.g. `rest,restingstate`) to target/fallback across public fMRI datasets.
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
