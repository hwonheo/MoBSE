# Nuisance Sensitivity Wave (2026-03-24)

## 1. Goal

Lock the current `MoE n100` operating point against preprocessing sensitivity on the public 300-subject setup.

Reference run:

- `phase2_baseline_moe_n100_20260323` (`paper_compcor_gsr`)

Additional variants launched:

- `phase2_nuis_compcor_only_moe_n100_20260324`
- `phase2_nuis_gsr_only_moe_n100_20260324`

## 2. Execution Note

This wave uses:

- same dataset target: `ds000030 + ds000243`, adult `300`
- same seeds: `42, 43, 44, 45, 46`
- same model: `MoE n100`
- same epoch budget and reporting path

Only nuisance settings change.

## 3. Results

Combined summary:

- `artifacts/nuisance_wave_20260324/reports/nuisance_benchmark_summary.csv`

Direct comparison tables:

- `artifacts/phase2_baseline_moe_n100_20260323__vs__phase2_nuis_compcor_only_moe_n100_20260324/reports/followup_paired_stats.csv`
- `artifacts/phase2_baseline_moe_n100_20260323__vs__phase2_nuis_gsr_only_moe_n100_20260324/reports/followup_paired_stats.csv`

Mean table:

### `paper_compcor_gsr`

- OS accuracy: `0.1817`
- OS F1 macro: `0.0893`
- ETTh1 MAE: `2.2099`
- ETTh1 MSE: `7.7896`
- OS latency: `0.3842 ms`
- ETTh1 latency: `0.3519 ms`

### `compcor_only`

- OS accuracy: `0.1864`
- OS F1 macro: `0.0855`
- ETTh1 MAE: `2.2217`
- ETTh1 MSE: `7.9879`
- OS latency: `0.3457 ms`
- ETTh1 latency: `0.3324 ms`

### `gsr_only`

- OS accuracy: `0.1787`
- OS F1 macro: `0.0916`
- ETTh1 MAE: `2.2035`
- ETTh1 MSE: `7.8365`
- OS latency: `0.3192 ms`
- ETTh1 latency: `0.3237 ms`

Interpretation:

- `compcor_only` is very close to the paper stack on all predictive metrics and slightly faster.
- `gsr_only` also stays very close on predictive metrics and is noticeably faster.

Paired test highlights versus `paper_compcor_gsr`:

- `compcor_only`
  - no predictive metric shows a meaningful/significant change
  - latency improves numerically, but not at conventional significance
- `gsr_only`
  - predictive metrics remain statistically similar
  - OS latency improves with `ttest p=0.0033`
  - ETTh1 latency improves with `ttest p=0.0224`

## 4. Decision

Current nuisance conclusion:

- the mainline appears robust to dropping either CompCor or GSR
- among the tested simplifications, `gsr_only` is the strongest candidate because it preserves metrics while improving latency most clearly

Practical decision:

- keep `paper_compcor_gsr` as the frozen reference stack in historical comparisons
- use `gsr_only` as the preferred next-confirmation nuisance candidate
- do not rewrite older benchmark conclusions retroactively

## 5. HCP Confirmation Constraint

The originally suggested next step was:

- `gsr_only + HCP` confirmation rerun

Current local constraint:

- `data/reference_raw/openneuro_abide152` and `data/reference_raw/openneuro_abide127` contain precomputed ROI time-series only
- raw HCP/OpenNeuro NIfTI inputs are not present alongside those HCP cohorts

Implication:

- nuisance strategy cannot be changed retroactively on the current HCP artifacts
- HCP nuisance confirmation is blocked unless raw inputs or a NIfTI manifest are provided

Operational conclusion:

- `gsr_only` is confirmed on the public 300-subject benchmark
- HCP nuisance confirmation remains a data-availability task, not a model-training task
## 6. Node Sweep Constraint

The originally planned intermediate node sweep (`128` / `150`) is currently blocked by the atlas choice.

Verified constraint:

- `nilearn.fetch_atlas_schaefer_2018(n_rois=...)` only accepts:
  - `100, 200, 300, 400, 500, 600, 700, 800, 900, 1000`

Current implication:

- `128` / `150` cannot be generated under the current Schaefer-based pipeline
- if node expansion remains necessary, the next feasible Schaefer point is `300`
- otherwise the next immediate robustness axis should stay on nuisance sensitivity
