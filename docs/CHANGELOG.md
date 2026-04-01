# Changelog

## 2026-04-01 (ds000243 Ingest, Template, Network Discussion)

### Added
- New ds000243 ingest/preprocessing execution note:
  - `docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md`
- New ds000243 network-interpretation discussion note:
  - `docs/experiments/openneuro_ds000243_network_discussion_2026-04-01.md`
- New template-network analysis script:
  - `scripts/analyze_template_networks.py`
- New ds000243 template/eval config:
  - `configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml`

### Changed
- README experiment links updated to archived experiment paths under:
  - `docs/experiments/archive_derived_2026-03-31/`
- README docs section extended with ds000243 note/discussion entry points.

### Data/Artifacts Produced
- Timeseries conversion outputs for Schaefer `100` and `200`:
  - `data/current_canonical/openneuro_ds000243/timeseries/{100,200}`
- Template banks:
  - `artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/templates/atlas{100,200}_sp{10,20}_template_bank.npz`
- Network metrics reports:
  - `artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/reports/template_network_metrics.{csv,json,md}`

## 2026-03-27 (ETTh1 Storyline Hardening)

### Stage 1: Readiness Closure
- Added ETTh1 readiness audit script: `scripts/audit_etth1_story_readiness.py`.
- Closed readiness gates from `17/19` to `19/19` by implementing temporal control and completing high-power seed evidence.
- Added audit documentation and closure record:
  - `docs/experiments/etth1_journal_readiness_audit_2026-03-27.md`
  - `docs/experiments/current_status_etth1_story_2026-03-27.md`

### Stage 2: Modeling Controls and Experimental Execution
- Added temporal control switch: `model.etth1_temporal_encoder: mean|gru` in:
  - `mobse/config.py`
  - `mobse/models/mobse.py`
  - `mobse/models/baselines.py`
  - `mobse/models/__init__.py`
- Added/used controlled `10`-seed configs:
  - `configs/2026-03-27/phase2_etth1_story_moe_n100_*`
- Completed four controlled run regimes (`ETTh1-only/Dual-task` x `mean/GRU`) and generated paired comparisons.

### Stage 3: Figures and Reporting
- Added ETTh1 story figure builder: `scripts/make_etth1_story_figures.py`.
- Generated ETTh1 figure package (`F1~F5`) in both `PNG` and `PDF`:
  - `artifacts/figures_etth1_story_20260327/reports/`
- Added focused run summary/pairwise tables:
  - `artifacts/etth1_story_followup_20260327/reports/story_run_summary.csv`
  - `artifacts/etth1_story_followup_20260327/reports/story_pairwise_focus.csv`

### Stage 4: Documentation Consolidation
- Added execution and figure-planning docs:
  - `docs/experiments/etth1_story_execution_log_2026-03-27.md`
  - `docs/experiments/etth1_figure_execution_plan_2026-03-27.md`
  - `docs/experiments/development_note_etth1_story_2026-03-27.md`
- Updated storyline/index docs to reflect closed gaps and current claim boundaries.

## 2026-03-14 (Phase-2 Target >=300)

### Added
- New ds00* scanner script for Phase-2 dataset discovery: `scripts/scan_openneuro_ds00.py`.
- New Phase-2 markdown report generator: `scripts/make_phase2_report.py`.
- New collection config for 300-subject n100 path: `configs/phase2_collect300_n100.yaml`.
- New Phase-2 report artifact: `docs/experiments/phase2_report_2026-03-14.md`.
- New non-expert explainer: `docs/experiments/phase2_report_2026-03-14_public.md`.
- New detailed Phase-2 execution note: `docs/experiments/experiments_note_phase2_2026-03-14.md`.

### Changed
- Phase-2 target updated from `150-250` to `>=300` in roadmap/configs.
- `scripts/run_phase2.py` now accepts CLI controls for `nodes/sparsities/routings/priors` and `bal-epochs`.

### Fixed
- Phase-2 execution flexibility improved so large-scale collection can run with reduced node scope (`100` only) when needed for turnaround.

## 2026-03-14 (OpenNeuro Multi-Dataset Fallback)

### Added
- `prepare_data` now supports `--openneuro-datasets "dsA,dsB,..."` for sequential multi-dataset collection until target subject count is reached.
- `--openneuro-task` now accepts comma-separated task names (e.g., `rest,restingstate`) for cross-dataset task-label differences.
- Subject-key collision prevention for multi-dataset imports via `{dataset_id}_{participant_id}` directory naming.
- Unit tests for dataset-id parsing and fallback collection behavior (`tests/test_prepare_openneuro.py`).

### Changed
- Diagnosis matching in participant filtering now accepts multi-token patterns (comma/pipe separated) and handles label variants such as `CONTROL`, `HEALTHY CONTROL`, `HC`.

### Fixed
- Single-dataset hard-failure behavior replaced with skip-and-continue in multi-dataset mode, with skipped dataset reasons logged in output metadata.

## 2026-03-14 (Phase 1 Closeout Progress)

### Added
- New HC127 balanced 3-seed reruns: `phase1_nr_hc127_mps100_bal3_20260314`, `phase1_nr_hc127_mps200_bal3_20260314`.
- Cross-scale comparison bundle: `seed_metrics.csv`, `summary_mean_std.csv`, `significance_paired_ttest.csv`, `delta_200_minus_100.json` under `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/`.
- Reproducibility freeze package: `repro_manifest.json`, `replay_commands.sh`, and run-specific resolved configs under `artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/configs/`.

### Changed
- Efficiency profiling code updated to attempt MPS memory tracking (`mobse/profiling.py`) in addition to existing CUDA path.

### Fixed
- Evaluation rerun interruption due OS FD exhaustion by cleaning non-experiment background Python language-server processes before resuming seed-wise evaluation.

## 2026-03-13 (Roadmap Update)

### Added
- Concept-aligned execution roadmap in `README.md` with explicit Phase 1/2/3 scope.
- Phase-1 closeout checklist for the current PoC line (post-regression balanced 3-seed rerun, report refresh, efficiency profiling, reproducibility freeze).
- Phase-2 HCP-scale validation plan (`>=300` subjects first, then expanded ablations).
- Phase-3 method-extension plan (learnable template perturbation, graph mixture, oscillatory dynamics).

### Changed
- Project planning baseline is now explicitly split between public-proxy PoC completion criteria and HCP-target full-claim validation criteria.

### Fixed
- Documentation ambiguity between "implemented now" and "planned next" by separating completed Phase-1 results from remaining and future phases.

## 2026-03-13 (Phase 1)

Source summary: [`docs/experiments/experiments_note_2026-03-13.md`](experiments/experiments_note_2026-03-13.md)

### Added
- Nuisance-regression pipeline for raw fMRI to ROI extraction (CompCor-like high-variance confounds, GSR, derivative/quadratic expansion, detrend + band-pass `0.008-0.1Hz`).
- Configurable ETTh1 loss options (`huber|mse|mae`, default `huber`).
- Task-loss normalization, balanced checkpoint selection (`weighted_normalized_loss`), and early stopping in dual-task training.

### Changed
- Naming refactor from `hcp_*` to `os_*` with backward-compatible aliases.
- End-to-end CLI flow (`prepare_data`, `build_templates`, `train`, `evaluate`, `report`) and progress logging standardization.

### Fixed
- OpenNeuro indexing bottleneck by scanning `participants.tsv` first and restricting recursive traversal to selected subjects.
- Cross-run artifact contamination by prioritizing current `run_id` templates/windows before glob fallback.

### Experiment Snapshot
- HC127 balanced 3-seed comparison completed for 100-node vs 200-node.
- 100-node showed better OS classification mean performance; 200-node showed larger variance in ETTh1 metrics.
- Nuisance-regression re-check completed on `ds000030` (`openneuro_hc`) with data-quality validation artifacts saved.
