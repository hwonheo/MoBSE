# Cross-Dataset Generalization (2026-03-23)

## 1. Scope

Stage C selected:

- primary candidate: `MoE n100`
- comparator: `MoBSE n100`

Stage D tests:

1. `train ds000030 -> test ds000243`
2. `train ds000243 -> test ds000030`

Implementation note:

- the OS windows artifact now stores `subject_ids`
- explicit `train_subject_prefixes` / `test_subject_prefixes` split is used
- this avoids pooled random split leakage across datasets

## 2. Run Assets

Template / window builds:

- `artifacts/phase2_cross_full_n100_20260323/`
- `artifacts/phase2_cross_ds000030_templates_n100_20260323/`
- `artifacts/phase2_cross_ds000243_templates_n100_20260323/`

Direction 1 runs:

- `phase2_cross_moe_train030_test243_20260323`
- `phase2_cross_mobse_train030_test243_20260323`

Direction 2 runs:

- `phase2_cross_moe_train243_test030_20260323`
- `phase2_cross_mobse_train243_test030_20260323`

Comparison tables:

- `artifacts/phase2_cross_moe_train030_test243_20260323__vs__phase2_cross_mobse_train030_test243_20260323/reports/followup_paired_stats.csv`
- `artifacts/phase2_cross_moe_train243_test030_20260323__vs__phase2_cross_mobse_train243_test030_20260323/reports/followup_paired_stats.csv`

## 3. Mean Results

### `train ds000030 -> test ds000243`

`MoE n100`

- OS accuracy: `0.1993`
- OS F1 macro: `0.1056`
- ETTh1 MAE: `2.2236`
- ETTh1 MSE: `7.9204`
- OS latency: `0.3528 ms`
- ETTh1 latency: `0.3281 ms`
- FLOPs: `2.96M`

`MoBSE n100`

- OS accuracy: `0.2011`
- OS F1 macro: `0.1614`
- ETTh1 MAE: `2.3138`
- ETTh1 MSE: `9.0796`
- OS latency: `1.4359 ms`
- ETTh1 latency: `1.2985 ms`
- FLOPs: `22.9M`

Interpretation:

- `MoBSE` is slightly better on OS classification metrics in this direction.
- `MoE` is clearly better on ET forecasting error and efficiency.

### `train ds000243 -> test ds000030`

`MoE n100`

- OS accuracy: `0.2004`
- OS F1 macro: `0.1076`
- ETTh1 MAE: `2.2193`
- ETTh1 MSE: `7.8936`
- OS latency: `0.3413 ms`
- ETTh1 latency: `0.3365 ms`
- FLOPs: `2.96M`

`MoBSE n100`

- OS accuracy: `0.2000`
- OS F1 macro: `0.1256`
- ETTh1 MAE: `2.5422`
- ETTh1 MSE: `10.8960`
- OS latency: `1.4277 ms`
- ETTh1 latency: `1.3032 ms`
- FLOPs: `22.9M`

Interpretation:

- OS classification is roughly tied.
- `MoE` is much better on ET forecasting error and efficiency.

## 4. Stage D Gate Check

Stage D target thresholds for the selected mainline (`MoE n100`) were:

- OS accuracy drop under dataset transfer: `<= 0.03`
- ETTh1 MAE degradation: `<= 0.20`
- ETTh1 MSE degradation: `<= 1.00`

Public-data reference (`phase2_baseline_moe_n100_20260323`):

- OS accuracy: `0.1817`
- ETTh1 MAE: `2.2099`
- ETTh1 MSE: `7.7896`

Transfer deltas for `MoE n100`:

- `ds000030 -> ds000243`
  - OS accuracy delta: `+0.0176`
  - ETTh1 MAE delta: `+0.0137`
  - ETTh1 MSE delta: `+0.1309`
- `ds000243 -> ds000030`
  - OS accuracy delta: `+0.0187`
  - ETTh1 MAE delta: `+0.0094`
  - ETTh1 MSE delta: `+0.1040`

Stage D decision:

- `pass`

Reason:

- the selected mainline does not show a harmful transfer drop
- ET forecasting degradation is small in both directions
- efficiency advantage is preserved

## 5. Outcome

After Stage D:

- keep `MoE n100` as the mainline candidate
- keep `MoBSE n100` as the diagnostic comparator
- proceed to HCP-accessible validation
