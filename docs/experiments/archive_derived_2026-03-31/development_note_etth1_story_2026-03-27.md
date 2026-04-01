# Development Note: ETTh1 Storyline Hardening (2026-03-27)

## Objective

Convert ETTh1 storyline from draft-level narrative to submission-ready evidence package by closing open controls, producing reproducible figure assets, and documenting traceable decisions.

## Stage Breakdown

### Stage 1. Evidence Readiness Audit

Actions:

- added automated audit script:
  - `scripts/audit_etth1_story_readiness.py`
- verified raw data, theory docs, model code, artifact coverage

Outcome:

- readiness advanced to `19/19 ready`

### Stage 2. Modeling Control Implementation + 10-Seed Runs

Actions:

- added temporal control switch:
  - `model.etth1_temporal_encoder: mean|gru`
- wired control across model builders and baselines
- executed four `10`-seed runs:
  - ETTh1-only + mean
  - Dual-task + mean
  - ETTh1-only + GRU
  - Dual-task + GRU

Outcome:

- temporal bottleneck and high-power statistical requirements closed for current scope

### Stage 3. Comparison Tables + Figure Production

Actions:

- generated focused comparison tables:
  - `artifacts/etth1_story_followup_20260327/reports/story_run_summary.csv`
  - `artifacts/etth1_story_followup_20260327/reports/story_pairwise_focus.csv`
- implemented figure builder:
  - `scripts/make_etth1_story_figures.py`
- generated full ETTh1 storyline panels:
  - `F1~F5` in both `PNG` and `PDF`

Outcome:

- paper-facing quantitative/diagram assets reproducibly generated from fixed inputs

### Stage 4. Documentation Consolidation

Actions:

- updated storyline and readiness docs
- added status summary and figure execution plan

Outcome:

- traceable writing bundle prepared for manuscript integration

## Main Risks and Boundaries

1. brain-template prior universality remains open
2. latency figures are backend-sensitive; device metadata should be disclosed in manuscript
3. conceptual panels are improved but still need final journal template alignment during manuscript layout

## Recommended Next Execution

1. lock final panel typography against target journal template
2. add supplementary table mapping each claim sentence to source artifact path
3. create final “submission freeze” manifest (`config + run_ids + figure checksums`)
