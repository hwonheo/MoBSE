# Baseline Benchmark Wave (2026-03-23)

## 1. Scope

Reference run:

- `phase2_ds00_adult300_n100_best5_20260323` (`MoBSE n100`, 5 seeds)

Baseline runs:

- `phase2_baseline_transformer_n100_20260323`
- `phase2_baseline_sparse_transformer_n100_20260323`
- `phase2_baseline_moe_n100_20260323`

Common setup:

- same `n100` public OpenNeuro 300-subject dataset
- same seeds: `42, 43, 44, 45, 46`
- same epoch budget and loss-selection logic

## 2. Combined Summary

Key benchmark table:

- `artifacts/benchmark_wave_20260323/reports/baseline_benchmark_summary.csv`

Direct comparison tables:

- `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_baseline_transformer_n100_20260323/reports/followup_paired_stats.csv`
- `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_baseline_sparse_transformer_n100_20260323/reports/followup_paired_stats.csv`
- `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_baseline_moe_n100_20260323/reports/followup_paired_stats.csv`

## 3. Mean Results

### MoBSE n100

- OS accuracy: `0.1834`
- OS F1 macro: `0.1099`
- ETTh1 MAE: `2.2244`
- ETTh1 MSE: `8.3799`
- OS latency: `1.8457 ms`
- ETTh1 latency: `1.6048 ms`
- FLOPs: `22.9M`

### Transformer

- OS accuracy: `0.1637`
- OS F1 macro: `0.0947`
- ETTh1 MAE: `2.1829`
- ETTh1 MSE: `8.0253`
- OS latency: `2.6217 ms`
- ETTh1 latency: `3.3308 ms`
- FLOPs: `3.48M`

### Sparse Transformer

- OS accuracy: `0.1610`
- OS F1 macro: `0.0978`
- ETTh1 MAE: `2.2667`
- ETTh1 MSE: `8.1750`
- OS latency: `3.4432 ms`
- ETTh1 latency: `4.0847 ms`
- FLOPs: `3.48M`

### MoE

- OS accuracy: `0.1817`
- OS F1 macro: `0.0893`
- ETTh1 MAE: `2.2099`
- ETTh1 MSE: `7.7896`
- OS latency: `0.3842 ms`
- ETTh1 latency: `0.3519 ms`
- FLOPs: `2.96M`

## 4. Benchmark Gate Interpretation

### Against Transformer

MoBSE is better on:

- OS accuracy
- OS F1 macro
- OS latency
- ETTh1 latency

Transformer is better on:

- ETTh1 MAE
- ETTh1 MSE
- FLOPs

Interpretation:

- MoBSE beats transformer on the OS side and is much faster on ETTh1 latency.
- Transformer has a modest edge on ET forecasting error and a much smaller architecture cost.

### Against Sparse Transformer

MoBSE is better on:

- OS accuracy
- OS F1 macro
- OS latency
- ETTh1 MAE
- ETTh1 latency

Sparse transformer is better on:

- ETTh1 MSE
- FLOPs

Interpretation:

- MoBSE clearly beats sparse transformer on most practical metrics except FLOPs and a small ETTh1 MSE edge.

### Against MoE

MoBSE is better on:

- OS F1 macro

MoE is better on:

- OS accuracy (slightly)
- ETTh1 MAE (slightly)
- ETTh1 MSE
- OS latency
- ETTh1 latency
- FLOPs

Interpretation:

- MoE is the strongest competitor in the current benchmark wave.
- The performance gap is small, but the efficiency gap is decisively in MoE's favor.

## 5. Stage C Decision

Using the previously defined Stage C criteria, the current result is:

- `MoBSE n100` **does not pass as the unique mainline winner**
- `MoE` becomes the strongest current operating-point candidate

Reason:

- the `MoE` baseline stays extremely competitive on predictive metrics
- the same model is also dramatically faster and cheaper
- therefore the benchmark wave does not support keeping `MoBSE n100` as the preferred operating point on this dataset

## 6. Updated Mainline Decision

The next sequential stage should be run with:

- **primary candidate:** `MoE n100`
- **secondary comparator:** `MoBSE n100`

This keeps the strongest current architecture as the mainline while preserving the original method as a comparator for diagnosis.

## 7. Immediate Next Step

Proceed to cross-dataset generalization with:

1. `MoE n100`
2. `MoBSE n100`

and test:

- `train on ds000030 -> test on ds000243`
- `train on ds000243 -> test on ds000030`
