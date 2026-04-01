# HCP-Accessible Validation (2026-03-23)

## 1. Scope

Stage E evaluates whether the selected public-data mainline survives transfer to the local HCP-accessible cohort.

Dataset used in this run:

- `data/reference_raw/openneuro_abide127/timeseries`
- subject count: `127`
- atlas size: `100`
- seeds: `42, 43, 44, 45, 46`

Runs:

- `phase2_openneuro_abide127_moe_n100_20260323`
- `phase2_openneuro_abide127_mobse_n100_20260323`

Comparison table:

- `artifacts/phase2_openneuro_abide127_moe_n100_20260323__vs__phase2_openneuro_abide127_mobse_n100_20260323/reports/followup_paired_stats.csv`

## 2. Mean Results

### `MoE n100`

- OS accuracy: `0.1518`
- OS F1 macro: `0.1067`
- ETTh1 MAE: `2.2388`
- ETTh1 MSE: `7.9223`
- OS latency: `0.3108 ms`
- ETTh1 latency: `0.3097 ms`
- FLOPs: `2.96M`

### `MoBSE n100`

- OS accuracy: `0.1368`
- OS F1 macro: `0.1020`
- ETTh1 MAE: `2.2412`
- ETTh1 MSE: `8.8987`
- OS latency: `1.4587 ms`
- ETTh1 latency: `1.3024 ms`
- FLOPs: `22.9M`

Interpretation:

- on this cohort, `MoE` is the stronger operating point
- OS accuracy is higher
- ET forecasting error is better or tied
- efficiency advantage remains decisive

## 3. Stage E Gate Check (`hc127` first pass)

Stage E thresholds for the public-data mainline were:

- retain the Stage C efficiency advantage direction
- OS accuracy remains within `0.02` of the public-data mainline result
- ETTh1 MAE remains within `0.20` of the public-data mainline result

Public mainline reference (`phase2_baseline_moe_n100_20260323`):

- OS accuracy: `0.1817`
- ETTh1 MAE: `2.2099`
- ETTh1 MSE: `7.7896`
- OS latency: `0.3842 ms`
- ETTh1 latency: `0.3519 ms`

HCP `MoE n100` deltas:

- OS accuracy delta: `-0.0299`
- ETTh1 MAE delta: `+0.0289`
- ETTh1 MSE delta: `+0.1328`
- OS latency delta: `-0.0735 ms`
- ETTh1 latency delta: `-0.0422 ms`

Stage E decision on `hc127`:

- `partial / not yet pass`

Reason:

- efficiency direction is preserved
- ETTh1 MAE remains well inside the target band
- but OS accuracy drops by about `0.03`, which misses the `0.02` threshold

## 4. Current Meaning After `hc127`

The project is no longer blocked on public-proxy validation:

- reproducibility is stabilized
- baseline benchmarking is done
- cross-dataset transfer passes
- HCP-accessible validation is running end-to-end

But the roadmap-level HCP claim is not yet fully locked because:

- HCP OS classification accuracy is below the current target band

## 5. Immediate Next Step After `hc127`

The next HCP recovery sequence should be:

1. rerun the same Stage E recipe on the local `data/reference_raw/openneuro_abide152/timeseries` `152-subject` cohort
2. if OS accuracy still stays low, extend epochs slightly before changing architecture
3. only after that open `128` / `150` node sweep and nuisance-sensitivity checks

## 6. Recovery Rerun on `152` Subjects

Recovery dataset:

- `data/reference_raw/openneuro_abide152/timeseries`
- subject count: `152`

Runs:

- `phase2_openneuro_abide152_moe_n100_20260323`
- `phase2_openneuro_abide152_mobse_n100_20260323`

Comparison tables:

- `artifacts/phase2_openneuro_abide152_moe_n100_20260323__vs__phase2_openneuro_abide152_mobse_n100_20260323/reports/followup_summary.csv`
- `artifacts/phase2_openneuro_abide152_moe_n100_20260323__vs__phase2_openneuro_abide152_mobse_n100_20260323/reports/followup_paired_stats.csv`

### `MoE n100` on `hcp152`

- OS accuracy: `0.1684`
- OS F1 macro: `0.1156`
- ETTh1 MAE: `2.2150`
- ETTh1 MSE: `8.1183`
- OS latency: `0.3112 ms`
- ETTh1 latency: `0.3061 ms`
- FLOPs: `2.96M`

### `MoBSE n100` on `hcp152`

- OS accuracy: `0.1684`
- OS F1 macro: `0.1153`
- ETTh1 MAE: `2.1639`
- ETTh1 MSE: `7.8315`
- OS latency: `1.4161 ms`
- ETTh1 latency: `1.2992 ms`
- FLOPs: `22.9M`

Interpretation:

- OS classification is effectively tied
- `MoBSE` has a small ET forecasting edge
- `MoE` keeps the same large efficiency advantage

Public-mainline deltas for `hcp152 MoE`:

- OS accuracy delta: `-0.0133`
- ETTh1 MAE delta: `+0.0051`
- ETTh1 MSE delta: `+0.3287`
- OS latency delta: `-0.0730 ms`
- ETTh1 latency delta: `-0.0458 ms`

## 7. Final Stage E Decision

After the `hcp152` recovery rerun:

- Stage E: `pass`

Reason:

- OS accuracy is now within the `0.02` band
- ETTh1 MAE remains well inside the `0.20` band
- efficiency direction is preserved on both HCP cohorts

## 8. Outcome

The roadmap claim is now in a stronger state:

- public-data benchmark locked
- cross-dataset transfer locked
- HCP-accessible validation recovered to the target band on `152` subjects

The next sequential work is no longer HCP rescue. It is:

1. `128` / `150` intermediate node sweep
2. nuisance sensitivity matrix
