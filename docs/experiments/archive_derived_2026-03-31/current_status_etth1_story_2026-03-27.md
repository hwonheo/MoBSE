# Current Status: ETTh1 Storyline (2026-03-27)

## Overall

- branch status: ETTh1 storyline hardening implemented
- readiness audit: `19/19 ready` (`0 missing`, `0 partial`)
- controlled evidence: completed (`10` seeds x `4` regimes)
- figures: `F1~F5` generated (`PNG` + `PDF`)

## What Is Closed

1. temporal bottleneck control
   - implemented as `model.etth1_temporal_encoder: mean|gru`
2. high-power robustness requirement
   - `10`-seed paired comparisons completed
3. ETTh1-only vs dual-task separation
   - both mean and GRU regimes compared

## Key Quantitative Snapshot

- mean regime (`10`-seed means):
  - ETTh1-only: `MAE 2.262`, `MSE 8.658`
  - dual-task: `MAE 2.206`, `MSE 7.860`
- GRU regime (`10`-seed means):
  - ETTh1-only: `MAE 1.459`, `MSE 3.711`
  - dual-task: `MAE 1.417`, `MSE 3.579`
- trade-off:
  - GRU improves ETTh1 error strongly
  - latency/FLOPs increase (`~0.329ms -> ~2.58ms`, `2.96M -> 3.76M FLOPs`)

## Figure Package Status

Output directory:

- `artifacts/figures_etth1_story_20260327/reports/`

Generated panels:

- `fig_f1_hook_routing_vs_scale.(png|pdf)`
- `fig_f2_etth1_model_schematic.(png|pdf)`
- `fig_f3_temporal_bottleneck_control.(png|pdf)`
- `fig_f4_prior_boundary_map.(png|pdf)`
- `fig_f5_etth1_pareto_frontier.(png|pdf)`

## Remaining for Submission

1. final visual QA pass (font consistency, line thickness, caption length)
2. manuscript integration (main text + supplementary references to paired stats)
3. optional rerun on second hardware backend for latency robustness note
