# Experiment History Index (2026-03-26)

## Purpose

This document is the entry point for the current experiment history.

Use it to answer three questions quickly:

1. what is the current mainline?
2. which document records which experiment wave?
3. what should be done next?

## Current Mainline

Current public-data mainline:

- `MoE n100`
- `gsr_only` nuisance setting
- OpenNeuro expansion track enabled
- strict-usable OpenNeuro collection redesign implemented

Important caveat:

- the previous `raw 600` OpenNeuro wave does **not** mean `usable 600`
- under strict exact-`100`-node QC, the observed usable count from that wave was `443`
- the strict-usable redesign gate was passed on `2026-03-26` (`projected strict-usable keep total = 670`)
- a new full run targeting `usable 600` was launched and completed:
  - `artifacts/phase2_openneuro_usable600_gsr_moe_n100_20260326/`

## Reading Order

Read the documents in this order.

1. [project_status_2026-03-23.md](./project_status_2026-03-23.md)
   - living summary of current status, completed gates, and immediate next actions
2. [benchmark_goal_2026-03-23.md](./benchmark_goal_2026-03-23.md)
   - target operating point and stage gates
3. wave-specific notes below
   - use these when you need the rationale and outputs for a specific experiment wave

## Document Map

### Foundation and Follow-up

- [phase2_followup_2026-03-23.md](./phase2_followup_2026-03-23.md)
  - `n100` vs `n200` best-config follow-up expanded to `5` seeds
- [baseline_benchmark_2026-03-23.md](./baseline_benchmark_2026-03-23.md)
  - baseline benchmark wave against `transformer`, `sparse_transformer`, and `moe`
- [etth1_storyline_top_journal_2026-03-27.md](./etth1_storyline_top_journal_2026-03-27.md)
  - ETTh1 modeling-centric top-journal narrative, logical gaps, and illustration blueprint
- [etth1_journal_readiness_audit_2026-03-27.md](./etth1_journal_readiness_audit_2026-03-27.md)
  - reproducible audit of ETTh1 journal-story evidence readiness (`ready/missing` matrix)
- [etth1_story_execution_log_2026-03-27.md](./etth1_story_execution_log_2026-03-27.md)
  - 4-run (`10` seeds each) execution record for ETTh1 story controls and pairwise findings
- [etth1_figure_execution_plan_2026-03-27.md](./etth1_figure_execution_plan_2026-03-27.md)
  - concrete panel-by-panel figure production plan for ETTh1 top-journal storyline
- [current_status_etth1_story_2026-03-27.md](./current_status_etth1_story_2026-03-27.md)
  - compact current-status checkpoint for ETTh1 storyline readiness and figure package
- [development_note_etth1_story_2026-03-27.md](./development_note_etth1_story_2026-03-27.md)
  - stage-based development note, risk boundaries, and next execution recommendations

### Generalization and Validation

- [cross_dataset_2026-03-23.md](./cross_dataset_2026-03-23.md)
  - dataset-held-out style evaluation between `ds000030` and `ds000243`
- [hcp_validation_2026-03-23.md](./hcp_validation_2026-03-23.md)
  - HCP-accessible validation and recovery rerun summary

### Preprocessing and OpenNeuro Scale-up

- [nuisance_sensitivity_2026-03-24.md](./nuisance_sensitivity_2026-03-24.md)
  - nuisance simplification study; `gsr_only` emerged as the best simplification candidate
- [openneuro_extension_2026-03-24.md](./openneuro_extension_2026-03-24.md)
  - expansion from the earlier public cohort to larger OpenNeuro mixtures
- [openneuro_usable_plan_2026-03-24.md](./openneuro_usable_plan_2026-03-24.md)
  - strict-usable redesign, exact-node QC policy, collector semantics, and pilot policy
- [strict_usable_execution_plan_2026-03-26.md](./strict_usable_execution_plan_2026-03-26.md)
  - execution plan for immediate goals (4 strict pilots -> yield refresh -> `600+` gate)
- [openneuro_usable600_wave_2026-03-27.md](./openneuro_usable600_wave_2026-03-27.md)
  - strict-usable `600` rerun outcome and paired stats vs previous `raw600` mainline
- [figure_plan_2026-03-27.md](./figure_plan_2026-03-27.md)
  - concrete figure production plan for the strict-usable wave

## What The Support Files Mean

### Config folders

- `configs/2026-03-23/`
  - follow-up, baseline, cross-dataset, and HCP validation run configs
- `configs/2026-03-24/`
  - nuisance and OpenNeuro extension configs
- `configs/2026-03-26/`
  - strict pilot configs and strict-usable `600` full-run config
- `configs/2026-03-13/`
  - archived resolved/source configs used to restore reproducibility bundles

### Scripts

- `scripts/run_multiseed_followup.py`
  - shared multiseed launcher for follow-up and comparison waves
- `scripts/compare_followup_runs.py`
  - paired summary/statistics generator between two completed runs
- `scripts/make_baseline_benchmark.py`
  - benchmark summary builder for baseline comparisons
- `scripts/run_prepare_build_followup.py`
  - chained `prepare_data -> build_templates -> train/evaluate/report` launcher
- `scripts/make_nuisance_benchmark.py`
  - nuisance sensitivity summary builder
- `scripts/make_openneuro_usable_yield_table.py`
  - strict-usable planning table generator from observed yield data
- `scripts/refresh_strict_usable_plan.py`
  - refreshes strict-usable plan table by merging base table with new pilot QC outputs
- `scripts/make_openneuro_usable600_figures.py`
  - builds strict-usable wave figure package (`F1~F5`) and figure manifest/captions
- `scripts/audit_etth1_story_readiness.py`
  - readiness audit for ETTh1 story evidence (`ready/partial/missing`)
- `scripts/make_etth1_story_figures.py`
  - builds ETTh1 quantitative story panels (`F3/F4/F5`) and figure manifest/captions

## Latest Hard Findings

- `MoE n100` is the strongest current public-data operating point.
- `gsr_only` kept predictive behavior close to baseline while improving latency.
- the earlier six-dataset OpenNeuro `raw 600` wave yielded only `443` strict-usable subjects.
- strict pilot + refresh pass raised projected strict-usable keep total to `670`.
- `ds000172` strict pilot failed with `0 / 13 accepted` and remains excluded.
- strict pilot outcomes:
  - `ds001747` -> drop candidate (`2 / 25` accepted)
  - `ds001796` -> keep candidate (`25 / 25` accepted)
  - `ds001386` -> keep candidate (`17 / 25` accepted)
  - `ds001771` -> keep candidate (`21 / 25` accepted)
  - `ds000258` -> keep candidate (`24 / 25` accepted)
- ETTh1 story readiness audit reached full closure: `19/19 ready`.
- ETTh1 temporal control (`mean` vs `gru`) at `10` seeds shows large ETTh1 error reduction with clear latency/FLOPs increase.

## Current Status Check (2026-03-27)

- strict pilot wave completed for:
  - `ds001747`, `ds001796`, `ds001386`, `ds001771`, `ds000258`
- usable-yield refresh completed:
  - `artifacts/openneuro_usable_plan_20260326/reports/openneuro_usable_plan_manifest.json`
  - `projected_usable_keep_total = 670`
- full strict-usable run completed:
  - run id: `phase2_openneuro_usable600_gsr_moe_n100_20260326`
  - `prepare_data` accepted subjects: `600`
  - 5-seed checkpoints/reports generated
- local baseline health check:
  - `./.venv/bin/python -m pytest -q` -> `24 passed, 3 warnings`
- figure package generated:
  - `artifacts/figures_openneuro_usable600_20260327/reports/figure_manifest.json`

## Updated TODO (2026-03-27)

- [x] run strict usable pilots for `ds001747`, `ds001796`, `ds001386`, and `ds001771`
- [x] refresh the usable-yield table with pilot evidence
- [x] launch full rerun after projected strict-usable total reaches `600+`
- [x] write a wave summary note for `phase2_openneuro_usable600_gsr_moe_n100_20260326` in `docs/experiments/`
- [x] run formal comparison against prior mainline (`phase2_openneuro600_gsr_moe_n100_20260324`) and record paired stats
- [x] update README `Data Layout` to match current timeseries structure (`<timeseries_dir>/<num_nodes>/<subject>/...`)
- [x] write a concrete figure-production plan document
- [x] implement figure builder script (`scripts/make_openneuro_usable600_figures.py`) and generate figure package
- [x] implement ETTh1 temporal bottleneck control (`model.etth1_temporal_encoder: mean|gru`)
- [x] complete ETTh1 high-power controlled runs (`10` seeds x 4 regimes)
- [x] generate ETTh1 comparison artifacts and pairwise stats tables
- [x] generate ETTh1 quantitative figure package (`scripts/make_etth1_story_figures.py`)
- [ ] review/refine figure styling and caption wording for final manuscript/presentation target
- [ ] produce conceptual panels (`F1/F2/F6`) with final journal-grade label/typography pass
- [ ] clean/stage current WIP changes (`configs/2026-03-26`, strict-plan scripts/docs) into a reproducible commit set
