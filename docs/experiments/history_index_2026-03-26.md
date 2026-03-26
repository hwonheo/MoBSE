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

## What The Support Files Mean

### Config folders

- `configs/2026-03-23/`
  - follow-up, baseline, cross-dataset, and HCP validation run configs
- `configs/2026-03-24/`
  - nuisance and OpenNeuro extension configs
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

## Latest Hard Findings

- `MoE n100` is the strongest current public-data operating point.
- `gsr_only` kept predictive behavior close to baseline while improving latency.
- the earlier six-dataset OpenNeuro `raw 600` wave yielded only `443` strict-usable subjects.
- strict keep set projected usable total is currently `458`.
- `ds000172` strict pilot failed with `0 / 13 accepted`.
- broad scan found raw rest-like adult candidates such as `ds001747`, `ds001796`, `ds001386`, and `ds001771`, but they still need strict usable pilot evidence.

## Next Actions

1. run strict usable pilots for `ds001747`, `ds001796`, `ds001386`, and `ds001771`
2. refresh the usable-yield table with those pilot results
3. launch a full rerun only after projected strict-usable total reaches a credible `600+`
