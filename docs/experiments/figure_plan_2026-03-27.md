# Figures Production Plan (2026-03-27)

## Objective

Produce a publication-ready figure package for the strict-usable OpenNeuro wave,
centered on the comparison:

- `phase2_openneuro600_gsr_moe_n100_20260324`
- `phase2_openneuro_usable600_gsr_moe_n100_20260326`

## Figure Set (Target)

1. **F1: Strict-Usable Gate Summary**
   - projected keep total vs target (`670` vs `600`)
   - accepted/rejected counts (`600` / `97`)
2. **F2: Dataset Contribution Bar Plot**
   - accepted subjects by dataset (`ds000030`, `ds000243`, ...)
3. **F3: OS Performance Comparison**
   - seed-level and mean+/-std for `accuracy`, `f1_macro`
4. **F4: ETTh1 Performance Comparison**
   - seed-level and mean+/-std for `MAE`, `MSE`
5. **F5: Efficiency Comparison**
   - latency comparison per task (`OS`, `ETTh1`)
   - FLOPs parity annotation

## Frozen Inputs

- `artifacts/openneuro_usable_plan_20260326/reports/openneuro_usable_yield_table.csv`
- `artifacts/openneuro_usable_plan_20260326/reports/openneuro_usable_plan_manifest.json`
- `artifacts/phase2_openneuro_usable600_gsr_moe_n100_20260326/logs/prepare_data.json`
- `artifacts/phase2_openneuro600_gsr_moe_n100_20260324/reports/raw_metrics.csv`
- `artifacts/phase2_openneuro_usable600_gsr_moe_n100_20260326/reports/raw_metrics.csv`
- `artifacts/phase2_openneuro600_gsr_moe_n100_20260324__vs__phase2_openneuro_usable600_gsr_moe_n100_20260326/reports/followup_paired_stats.csv`

## Implementation Plan

### Stage 1. Data Lock and Consistency Check

- verify both raw metric files have `5` seeds (`42..46`) and same schema
- verify comparison manifest paths resolve
- copy frozen inputs into figure run manifest

Output:

- `artifacts/figures_openneuro_usable600_20260327/reports/figure_manifest.json`

### Stage 2. Figure Builder Script

Create one dedicated script:

- `scripts/make_openneuro_usable600_figures.py`

Responsibilities:

- load frozen inputs
- compute compact plotting table (`figure_metrics_table.csv`)
- generate all target PNGs with deterministic style (`dpi=300`)
- write one summary markdown (`figure_captions.md`)

Output directory:

- `artifacts/figures_openneuro_usable600_20260327/reports/`

### Stage 3. Plot Specs (Concrete)

- `fig_f1_gate_summary.png`:
  - bar: projected keep total / target / accepted
  - text annotation: rejection count and main rejection type (`node_mismatch`)
- `fig_f2_dataset_contribution.png`:
  - horizontal bars sorted by accepted count
- `fig_f3_os_metrics.png`:
  - paired seed-line + mean marker for `accuracy` and `f1_macro`
- `fig_f4_etth1_metrics.png`:
  - paired seed-line + mean marker for `MAE` and `MSE`
- `fig_f5_efficiency.png`:
  - latency bars (`OS`, `ETTh1`) + FLOPs equality note

### Stage 4. Quality Gate

- all figures render without overlap at both notebook and paper widths
- axis labels include units (ms, FLOPs, score)
- each figure has a one-line caption in `figure_captions.md`
- numerical values in captions match source CSV within rounding tolerance

## Execution Commands

1. comparison refresh (if inputs changed):

```bash
./.venv/bin/python scripts/compare_followup_runs.py \
  --run-a phase2_openneuro600_gsr_moe_n100_20260324 \
  --run-b phase2_openneuro_usable600_gsr_moe_n100_20260326
```

2. figure build:

```bash
./.venv/bin/python scripts/make_openneuro_usable600_figures.py \
  --run-a phase2_openneuro600_gsr_moe_n100_20260324 \
  --run-b phase2_openneuro_usable600_gsr_moe_n100_20260326 \
  --plan-manifest artifacts/openneuro_usable_plan_20260326/reports/openneuro_usable_plan_manifest.json \
  --prepare-log artifacts/phase2_openneuro_usable600_gsr_moe_n100_20260326/logs/prepare_data.json \
  --out-dir artifacts/figures_openneuro_usable600_20260327/reports
```

## Risks and Mitigations

- small-seed uncertainty (`n=5`):
  - keep seed-level overlays in F3/F4 and annotate inferential caution
- latency variability by hardware state:
  - include device/backend metadata in figure manifest
- interpretation drift between metrics:
  - keep OS and ETTh1 panels separated and avoid mixed-score ranking

## Execution Update (2026-03-27)

- implemented: `scripts/make_openneuro_usable600_figures.py`
- generated:
  - `artifacts/figures_openneuro_usable600_20260327/reports/figure_manifest.json`
  - `fig_f1_gate_summary.png`
  - `fig_f2_dataset_contribution.png`
  - `fig_f3_os_metrics.png`
  - `fig_f4_etth1_metrics.png`
  - `fig_f5_efficiency.png`
