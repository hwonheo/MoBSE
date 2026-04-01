# OpenNeuro Strict-Usable 600 Wave Summary (2026-03-27)

## Scope

This note summarizes the strict-usable `600` rerun and its direct paired comparison
against the previous `raw 600` OpenNeuro mainline.

Compared runs:

- `phase2_openneuro600_gsr_moe_n100_20260324` (previous mainline)
- `phase2_openneuro_usable600_gsr_moe_n100_20260326` (strict-usable rerun)

Comparison outputs:

- `artifacts/phase2_openneuro600_gsr_moe_n100_20260324__vs__phase2_openneuro_usable600_gsr_moe_n100_20260326/reports/followup_summary.csv`
- `artifacts/phase2_openneuro600_gsr_moe_n100_20260324__vs__phase2_openneuro_usable600_gsr_moe_n100_20260326/reports/followup_paired_stats.csv`

## Data Gate and Execution Status

- strict-usable plan refresh projected `670` keep-subjects (`>= 600` gate passed)
- strict-usable full run accepted exactly `600` subjects
- run artifacts are complete (checkpoints, eval logs, summary table, plots)

Key provenance files:

- `artifacts/openneuro_usable_plan_20260326/reports/openneuro_usable_plan_manifest.json`
- `artifacts/phase2_openneuro_usable600_gsr_moe_n100_20260326/logs/prepare_data.json`
- `artifacts/phase2_openneuro_usable600_gsr_moe_n100_20260326/reports/summary_table.csv`

## Paired 5-Seed Comparison (A - B)

`A = 2026-03-24 raw600`, `B = 2026-03-26 strict-usable600`

| Task | Metric | Mean A | Mean B | A-B | t-test p | Wilcoxon p | Direction |
|---|---:|---:|---:|---:|---:|---:|---|
| OS | accuracy | 0.1931 | 0.2012 | -0.0081 | 0.2141 | 0.3125 | B slightly better |
| OS | f1_macro | 0.1078 | 0.0857 | 0.0222 | 0.1924 | 0.1875 | A slightly better |
| OS | latency_ms_mean | 0.2963 | 0.3192 | -0.0230 | 0.0683 | 0.0625 | A faster (borderline) |
| ETTh1 | MAE | 2.1297 | 2.2250 | -0.0953 | 0.0830 | 0.0625 | A better (lower) |
| ETTh1 | MSE | 7.6890 | 8.0870 | -0.3980 | 0.3718 | 0.4375 | A slightly better |
| OS/ETTh1 | FLOPs | 2960608 | 2960608 | 0.0000 | N/A | 1.0000 | same |

## Interpretation

- No primary metric crossed conventional significance (`p < 0.05`) under `n=5` seeds.
- strict-usable rerun (`B`) showed higher OS accuracy but lower OS macro-F1.
- the earlier run (`A`) remained better on latency and ETTh1 error metrics, with latency/MAE close to borderline significance.
- practical takeaway: strict-usable curation stabilized target-count reproducibility (`accepted=600`), but performance superiority is not yet established.

## Immediate Follow-up

1. Increase seeds from `5` to `10` for the same pair to raise statistical power.
2. Keep the strict-usable dataset policy and verify if latency/ETTh1 gaps persist.
3. Build figure package from this comparison using `figure_plan_2026-03-27.md`.
