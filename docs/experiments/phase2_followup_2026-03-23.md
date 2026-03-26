# Phase-2 Follow-up (2026-03-23)

## 1. Goal

Strengthen the previous `n100 vs n200` Phase-2 result by expanding the best-vs-best comparison from `3` seeds to `5` seeds.

Compared runs:

- `phase2_ds00_adult300_n100_best5_20260323`
- `phase2_ds00_adult300_n200_best5_20260323`

Base best-config choices reused from the previous Phase-2 result:

- `n100`: `sp10 + hard + prior`
- `n200`: `sp20 + hard + no-prior`

Seeds:

- `42, 43, 44, 45, 46`

## 2. Execution

Configs:

- `configs/2026-03-23/phase2_best5_n100.yaml`
- `configs/2026-03-23/phase2_best5_n200.yaml`

Runner:

- `scripts/run_multiseed_followup.py`

Commands:

```bash
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-23/phase2_best5_n100.yaml --no-progress
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-23/phase2_best5_n200.yaml --no-progress
./.venv/bin/python scripts/compare_followup_runs.py \
  --run-a phase2_ds00_adult300_n100_best5_20260323 \
  --run-b phase2_ds00_adult300_n200_best5_20260323
```

## 3. Output Files

### Individual run summaries

- `artifacts/phase2_ds00_adult300_n100_best5_20260323/reports/summary_table.csv`
- `artifacts/phase2_ds00_adult300_n200_best5_20260323/reports/summary_table.csv`

### Direct comparison

- `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_ds00_adult300_n200_best5_20260323/reports/followup_summary.csv`
- `artifacts/phase2_ds00_adult300_n100_best5_20260323__vs__phase2_ds00_adult300_n200_best5_20260323/reports/followup_paired_stats.csv`

## 4. Mean ± Std (5 seeds)

### OS task

- `n100` accuracy: `0.1834 ± 0.0192`
- `n200` accuracy: `0.1717 ± 0.0075`
- `n100` F1 macro: `0.1099 ± 0.0213`
- `n200` F1 macro: `0.1123 ± 0.0120`
- `n100` latency: `1.8457 ± 0.0629 ms`
- `n200` latency: `2.8183 ± 0.0883 ms`
- `n100` FLOPs: `22.9M`
- `n200` FLOPs: `92.8M`

### ETTh1 task

- `n100` MAE: `2.2244 ± 0.1077`
- `n200` MAE: `2.4116 ± 0.1740`
- `n100` MSE: `8.3799 ± 0.8825`
- `n200` MSE: `9.4503 ± 1.1989`
- `n100` latency: `1.6048 ± 0.0467 ms`
- `n200` latency: `2.4049 ± 0.0366 ms`
- `n100` FLOPs: `22.9M`
- `n200` FLOPs: `92.8M`

## 5. Paired 5-seed Comparison

### Performance

- OS accuracy: `n100 - n200 = +0.0116`, paired t-test `p=0.1904`
- OS F1 macro: `n100 - n200 = -0.0024`, paired t-test `p=0.8288`
- ETTh1 MAE: `n100 - n200 = -0.1872`, paired t-test `p=0.1461`
- ETTh1 MSE: `n100 - n200 = -1.0704`, paired t-test `p=0.2346`

### Efficiency

- OS latency: `n100 - n200 = -0.9726 ms`, paired t-test `p=0.0000647`
- ETTh1 latency: `n100 - n200 = -0.8001 ms`, paired t-test `p=0.0000106`
- FLOPs: fixed architectural gap remains (`22.9M` vs `92.8M`)

## 6. Interpretation

The `5-seed` follow-up keeps the core conclusion intact:

- `n100` remains the better efficiency point by a large margin.
- `n100` still trends better on OS accuracy and ETTh1 error.
- `n200` keeps only a very small advantage on OS F1 macro.

What changed relative to the earlier `3-seed` comparison:

- performance deltas remained directionally similar but became smaller in magnitude
- efficiency differences remained large and are now supported more strongly
- performance metrics are still not significant at this seed count, so they remain directional rather than definitive

## 7. Practical Conclusion

As of this follow-up, the strongest defensible statement is:

> For the current 300-subject public OpenNeuro setup, `n100` is the preferred operating point because it is clearly more efficient and remains competitive-to-better on the key predictive metrics.

## 8. Recommended Next Steps

1. Keep `n100` as the mainline configuration for baseline comparison work.
2. Use this `5-seed` result as the new reference point for future tradeoff claims.
3. Move next to:
   - baseline comparisons (`transformer`, `sparse_transformer`, `moe`)
   - cross-dataset generalization (`ds000030` vs `ds000243`)
   - targeted analysis of why `n200 + prior` underperforms
