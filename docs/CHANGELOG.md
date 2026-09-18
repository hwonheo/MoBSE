# Changelog

## 2026-09-18 (v2 implementation + WI-02/03 execution + G0 conditionally cleared)

All figures measured; the producing artifact is named for each.

### Added
- **`mobse/v2/` — 16 modules, 4,114 lines.** The ten specified in the work instructions
  (manifests, preprocess, splits, features, templates, models, train, evaluate,
  statistics, cli) plus five not in the spec: cohort, config, extract, labels, locks.
  *The protocol and work instructions still describe only ten and need updating.*
- **`tests/v2/` — under active development.** Measured at 2026-09-18 10:30: 22 files,
  5,001 lines, 492 tests collected; local run 451 passed / 26 failed / 17 skipped. All 26
  failures are `ModuleNotFoundError` (sklearn 22, scipy 2, torch 2) — environment, not
  defects. An earlier measurement the same morning read 470 tests (439/26/7), so these
  counts move hour to hour; re-measure rather than quoting them. The analysis-host
  snapshot (11 modules, 9 test files) passed 170/170.
- **`configs/redesign_v1/`** — `main.yaml`, `pilot.yaml`, `external.yaml`. These restate
  code constants to lock them; `mobse/v2/config.py` validates each against the module
  constant and rejects unknown keys as typos.
- **WI-02 extraction outputs** — parcellated windows re-derived from source BOLD for both
  cohorts. These are the canonical time-series, replacing the earlier derivatives.
- **Schaefer-100 atlas in MNI152NLin2009cAsym**, matching the BOLD space. Distinct from
  the FSLMNI152 copy under `~/nilearn_data`; the two must not be mixed.

### Changed
- **Gate evidence advanced to revision 22** (2026-09-18T08:40Z).
  **G0 Provenance: blocked → conditionally_cleared** (2 of 10 checks still fail).
  G1–G5 planned; G1 has two failing checks (`group_id` constructible from local
  metadata, PIOP1/PIOP2 subject ID namespace).
- **Cohorts locked (WI-03)**: PIOP1 216 → 157 eligible (pilot 31 / main 126);
  PIOP2 226 → 189 eligible as external hold-out. Rule version protocol-1.1 §3.3,
  requiring all three tasks. Revision 22 promoted the re-extraction to canonical,
  raising PIOP1 eligibility 153 → 157; the existing 1,560 windows were byte-identical
  and were promoted without overwrite.
- **Wave 2 BOLD acquisition completed**: 2,590 files, 209.7 GiB, 0 failures
  (emomatching 860 / restingstate 868 / workingmemory 862; PIOP1 1,250 + PIOP2 1,340).

### Confirmed defect in prior work
- `existing extraction TR correctness` = **fail**. The earlier extraction applied 0.75 s
  to every run, so both primary targets were filtered at a 2.67× wrong rate. PIOP1
  restingstate was correct only by coincidence. **Existing derived time-series
  (`data/aomic`, `data/current_canonical`, `data/legacy_*`) cannot be reused for the
  main analysis**, and resampling them is not a repair.

### Known discrepancy
- `locks/measurement_lock.json` (00:45Z) records a G1 lock, while gate evidence rev 22
  (08:40Z) still lists G1 as planned. The later evidence takes precedence; a person must
  reconcile these.

### Repository policy
Per the team data policy — **code to GitHub, data and outputs to local storage and the
in-house storage server** — the repository now carries only the *brief* of a release.

- Kept in the repo: `gate_evidence.json`, `locks/`, `reports/` (decision and verdict
  records, ~400 KB).
- Not in the repo: `results/**/provenance/` (run-level records, ~10 MB), raw BOLD,
  parcellated time-series. These live on the analysis host and are registered as rows in
  the Notion `🗄️ Data Assets` database with their physical paths and checksums.
- The 2026-04 expert routing report (`.docx`) and its seven figures were moved to a local
  archive. **They were never committed** — no history rewrite was involved. Three
  superseded April documents still reference `figures/…` by relative path; the archive's
  README records where the files went.

### Documentation
- `README.md`, `CLAUDE.md` rewritten against measured state; 2026-04-17 versions
  preserved under `.backup/`.
- Work Logs 01–08 recorded in Notion under series `MOBSE`, with data assets linked.

## 2026-09-17 (Redesign: research question and evaluation target replaced)

### Added
- **Literature review** (`docs/experiments/mobse_literature_review_2026-09-17.md`) — 11
  works (R1–R10, D1). dFCExpert (IEEE TMI 45(3), 2026-03) and MoRE-Brain (NeurIPS 2025)
  identified as direct prior work.
- **Audit of existing experiments** (`..._existing_experiments_audit_2026-09-17.md`) —
  352 training summaries, 624 seed results, 624 checkpoints inventoried. This corrected
  an earlier judgment that validation was missing: strict subject splits, nuisance
  sensitivity, prior/routing sweeps, baseline comparison and cross-dataset transfer had
  all already been run. The counts are **not** 352 independent hypothesis tests.
- **Protocol v1.1** (`..._redesign_protocol_2026-09-17.md`) and **work instructions
  v1.0** (`..._redesign_work_instructions_2026-09-17.md`).
- **Two-wave acquisition plan** (`h197_acquisition_plan_2026-09-17.md`) — metadata first,
  BOLD only after the native TR is known.
- Protocol figures RD1–RD4 (`docs/experiments/figures_redesign_2026-09-17/`).

### Changed
- **Primary target replaced.** From dFC centroid pseudo-labels to the run identity of
  PIOP1 `emomatching` vs `workingmemory` — independent of the clustering. Hypotheses
  H1 (input-dependent routing) and H2 (aligned brain bank) pre-specified with a minimum
  effect of interest δ = 0.02 balanced accuracy.
- **Priority claims withdrawn.** First brain-state MoE, atlas-free operation, cognitive
  load marker and sparse-compute superiority are no longer claims of this study.
- **Simple baselines made mandatory** — mean-only, FC+linear and FC+MLP controls.
- **PIOP2 reinstated.** Wave 1 measured emomatching 222 runs and workingmemory 224 runs,
  all supporting the analysis window, superseding the 2026-04-17 exclusion for "short
  scans". It is used as a locked cohort replication and is deliberately **not** called
  cross-site, since it shares the research environment.
- **ds000030 demoted.** No longer a substitute target for cross-site replication.

### Key result
- **Native TR of both primary targets confirmed to be 2.0 s**, single-valued across
  1,295 audited runs (emomatching 135 volumes, workingmemory 162). The window design
  holds without change. The two cohorts' resting-state scans use *different* TRs
  (PIOP1 0.75 s, PIOP2 2.0 s), which is why the target TR could not be inferred.

## 2026-04-17 (Manuscript Integration + Cross-Site Validation Pipeline)

> **Superseded.** The dataset decisions below were overturned by measurement on
> 2026-09-17 — PIOP2 was reinstated as the external hold-out and ds000030 was dropped as
> a cross-site target. Retained as written for provenance.

### Added
- **Integrated manuscript storyline**: `docs/manuscript_final_2026-03-31/mobse_integrated_storyline_2026-04-16.md`
  - Two-stage validation narrative: Phase 1 (atlas-based Yeo-7/ABIDE) + Phase 2 (data-driven dFC/PIOP1).
  - Updated paper structure (R1–R7), figure plan (F1–F14), table plan (T1–T6).
  - Submission strategy analysis: single unified paper recommended.
  - Remaining gaps prioritized (P1–P3) with dataset exclusion rationale.
- **ds000030 (UCLA CNP) cross-site validation pipeline**:
  - `scripts/probe_ds000030.py` — URL index probe: 8 tasks confirmed (rest, bart, bht, pamenc, pamret, scap, stopsignal, taskswitch), N=207–262 per task, MNI152NLin2009cAsym fMRIPrep derivatives.
  - `scripts/fetch_ds000030_timeseries.py` — streaming download + Schaefer-100 extraction pipeline. Subject-level: download → parcellation → BOLD delete (disk-efficient). tqdm progress. Supports `--max-subjects`, `--tasks`, `--keep-bold`, `--download-only`.
  - `artifacts/ds000030_probe_result.json` — probe output.

### Changed
- Gap table updated: PIOP2/HCP/ID1000 excluded with documented rationale.
  - PIOP2: 2-day download, short scan time → insufficient dFC windows.
  - HCP: DUA approval required, data access uncertain.
  - AOMIC-ID1000: no resting-state scan → no low-demand routing anchor.
- ds000030 promoted to P1 cross-site replication target (nilearn selective download, different site/scanner).
- ABIDE dFC replication added as P1 for Phase 1↔2 bridge.

### Documentation
- `CLAUDE.md` updated: ds000030 paths, cross-site validation section, excluded datasets, next steps refreshed to 2026-04-17.
- `README.md` updated: latest status 2026-04-17, integrated storyline link, Phase 2 plan refreshed with dataset selection decisions.
- `docs/CHANGELOG.md`: this entry.

## 2026-04-16 (Expert Routing Anti-Collapse + dFC All-Tasks Pipeline)

### Critical Fix
- **Expert collapse resolved**: replaced `scatter_(values)` with differentiable masking (`weights * mask`) in `_routing_weights()` — gradient now flows from balance loss through routing to gate parameters.
  - `mobse/models/mobse.py`: both `soft` and `hard` routing modes fixed.

### Added
- Entropy-based MoE load balancing loss (`_load_balance_loss()`) in `mobse/train.py`.
- `balance_loss_weight` (TrainConfig) and `gate_temperature` (ModelConfig) in `mobse/config.py`.
- Gate temperature scaling in `mobse/models/mobse.py` `_routing_weights()`.
- `gate_temperature` wiring in `mobse/models/__init__.py` `build_model()`.
- `pca_object` field in `DFCResult` dataclass (`mobse/data/dfc.py`), PCA pickle saving in `scripts/run_piop1_dfc.py`.
- Centroid-based label assignment for all-task windows: `assign_label_by_centroid()` and `build_dfc_windows_all_tasks()` in `mobse/templates/dfc_bridge.py`.
- New scripts:
  - `scripts/build_alltasks_windows.py` — standalone all-tasks window generation (no torch).
  - `scripts/eval_routing.py` — routing weight analysis & brain-state interpretability visualization.
  - `scripts/debug_balance_grad.py` — gradient flow diagnostic for balance loss.
- New configs:
  - `config_dfc_alltasks_balanced_C.yaml` (k=2, balance=1.0, temp=3.0) — **best configuration**.
  - `config_dfc_alltasks_balanced_D.yaml` (k=3, balance=1.0, temp=3.0).
  - `config_dfc_alltasks_balanced_E.yaml` (k=3, balance=0.1, temp=3.0) — pending.
- Publication-quality report: `MoBSE_Expert_Routing_Report.docx` with 7 figures, 3 tables.
- Figures directory: `figures/fig1–fig7` (300 DPI PNG).

### Changed
- `scripts/prepare_dfc_for_training.py`: added `--all-tasks` flag and `--tasks` argument for all-tasks pipeline.
- Training loop in `mobse/train.py`: captures routing weights, adds balance loss when `balance_loss_weight > 0`.

### Key Results
- Exp C (routing_k=2): task-specific routing confirmed — emomatching/workingmemory route to dfc_2 (50%/46%), rest/anticipation to dfc_1 (37%).
- Exp D (routing_k=3): perfectly uniform routing (entropy=log(3)) — balance loss too strong, no task differentiation.
- All-tasks data augmentation: 5,670 → 15,817 windows from 6 PIOP1 tasks.

### Documentation
- New experiment note: `docs/experiments/phase2_expert_routing_experiments_2026-04-16.md`.
- `CLAUDE.md` created for project context.
- README updated: latest status, Phase 2 plan, new config keys.

## 2026-04-02 (ds000243 Resting-State Nilearn Suite + Docs Consolidation)

### Added
- New end-to-end resting-state Nilearn suite runner:
  - `scripts/run_ds000243_nilearn_rest_suite.py`
- New ds000243 resting-state suite artifacts:
  - `artifacts/current_canonical/ds000243_nilearn_rest_suite_20260402/reports/nilearn_rest_suite_manifest.json`
  - `artifacts/current_canonical/ds000243_nilearn_rest_suite_20260402/reports/nilearn_rest_suite_report.md`
  - plus generated connectivity/decomposition/seed/region outputs under the same report directory.

### Changed
- Fixed Nilearn probabilistic-atlas extraction step by explicitly wiring `t_r` in `NiftiMapsMasker`.
- Updated `SparseTransformerBaseline` argument compatibility for model-comparison runs:
  - `mobse/models/baselines.py`
- Extended ds000243 experiment log with:
  - fMRIPrep-complete input declaration,
  - nuisance-regression policy note (`CompCor/GSR` lineage vs non-XCP-D path),
  - discussion anchor for integrated-network interpretation.

### Documentation
- README latest-status/docs entry refreshed to include ds000243 Nilearn rest-suite outputs and current interpretation scope.

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
