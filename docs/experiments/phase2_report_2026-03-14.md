# Phase-2 Report (2026-03-14, Updated)

## 1) Dataset and Scope

- Dataset source: OpenNeuro `ds000030 + ds000243`
- Filter: age `>=18`, task `rest,restingstate`
- Target: 300 subjects
- Collected:
  - n100 path: `collected_subjects=300`
  - n200 path: `collected_subjects=300`

## 2) Runs Executed

- n100 study: `phase2_ds00_adult300_n100_20260314`
- n200 study: `phase2_ds00_adult300_n200_20260314`
- Common protocol:
  - sweep(seed=42): 12 configs (sparsity 0.1/0.2/0.3 x routing soft/hard x prior on/off)
  - bal3(seed=42/43/44): top-3 configs, epochs=4

## 3) Best Config Per Node (bal3)

### n100 best

- run: `phase2_ds00_adult300_n100_20260314_top_bal3_n100_sp10_hard_prior`
- OS Accuracy: `0.1856 ± 0.0251`
- OS F1 Macro: `0.0948 ± 0.0082`
- ETTh1 MAE: `2.2183 ± 0.1366`
- ETTh1 MSE: `8.3439 ± 1.2218`
- OS latency: `2.9651 ms`
- ETTh1 latency: `2.7259 ms`
- OS FLOPs: `22,885,440`

### n200 best

- run: `phase2_ds00_adult300_n200_20260314_top_bal3_n200_sp20_hard_noprior`
- OS Accuracy: `0.1620 ± 0.0063`
- OS F1 Macro: `0.1005 ± 0.0055`
- ETTh1 MAE: `2.5623 ± 0.1564`
- ETTh1 MSE: `10.2469 ± 0.7281`
- OS latency: `7.8215 ms`
- ETTh1 latency: `6.8860 ms`
- OS FLOPs: `92,773,440`

## 4) Statistical Comparison (best n100 vs best n200, paired by seed)

- table:
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_best_vs_best_phase2_ds00_adult300_n100_20260314_vs_phase2_ds00_adult300_n200_20260314.csv`
- key points:
  - OS Accuracy: n100 higher (`+0.0236`), corrected p-value not significant (Holm on t-test: `0.7029`)
  - ETTh1 MSE: n100 lower (`-1.9030`), corrected p-value not significant (Holm on t-test: `0.7029`)
  - Latency/FLOPs: n100 markedly lower, t-test Holm-corrected p-values significant
    - OS latency: `0.0135`
    - ETTh1 latency: `0.0151`
    - OS FLOPs: `0.0000`
- interpretation note:
  - `n=3` seeds only, so performance metric p-values are low-power and should be treated as exploratory.

## 5) Additional Outputs

- pairwise p-value tables:
  - n100 top3: `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_top3_bal3_pairwise_stats.csv`
  - n200 top3: `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_top3_bal3_pairwise_stats.csv`
- figure manifest:
  - `artifacts/phase2_figures_20260314_n100_n200/phase2_figures_manifest.json`
- generated figures:
  - `phase2_tradeoff_accuracy_vs_latency.png`
  - `phase2_tradeoff_mse_vs_latency.png`
  - `phase2_tradeoff_accuracy_vs_flops.png`
  - `phase2_routing_entropy_by_nodes_task.png`
  - `phase2_routing_usage_best_runs.png`

## 6) Conclusion for the Previous "Next Steps"

- `n200` path execution: completed
- bal3 p-value table: completed
- automatic tradeoff/routing figures: completed
- validity check:
  - the proposed next steps were methodologically valid for reducing uncertainty in `100 vs 200` and are now implemented end-to-end.
