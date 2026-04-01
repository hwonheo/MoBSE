# ds000243 Rest Network Discussion (2026-04-01)

## Scope
- Dataset: `openneuro_ds000243` (`fMRIPrep` derivatives)
- State analyzed: `rest` only
- Template set: `atlas100/200` x `sparsity 0.1/0.2`
- Source metrics: `artifacts/current_canonical/ds000243_rest_templates_100_200_20260401/reports/template_network_metrics.csv`

## Main Observations
- Increasing target sparsity from `0.1 -> 0.2` increased:
  - edge density (`0.10 -> 0.20`, by construction)
  - global efficiency (`~0.37-0.39 -> ~0.51`)
  - mean node strength and mean degree
- Increasing target sparsity reduced:
  - modularity on LCC (`~0.47-0.49 -> ~0.32-0.33`)
  - detected community count (`5 -> 3`)

## Discussion Angles For Manuscript
- Integration vs segregation tradeoff:
  - `sp20` behaves as a more integrated graph regime (higher global efficiency).
  - `sp10` preserves stronger modular structure (higher modularity, more communities).
- Scale robustness (100 vs 200 nodes):
  - qualitative trend is consistent across parcellation scales.
  - this supports a "directionally stable" claim for sparsity-induced topology shift.
- Practical implication:
  - If the objective is communication efficiency / global routing, `sp20` is favorable.
  - If the objective is mesoscale module preservation / interpretability, `sp10` may be preferable.

## Interpretation Boundaries
- This is a single-state (`rest`) dataset slice, so results should be interpreted as topology profiling, not state discriminability evidence.
- Current conversion used `fMRIPrep confounds` with additional CompCor/GSR extraction disabled in this run; nuisance design can move absolute metric values.
- Metrics are template-level summaries (group-average FC after sparsification), not subject-level inferential stats yet.

## Recommended Next Analyses
- Subject-level uncertainty:
  - bootstrap subjects/runs and report confidence intervals for efficiency/modularity deltas.
- Threshold sensitivity:
  - extend sparsity grid (`0.05, 0.10, 0.15, 0.20, 0.30`) and inspect monotonicity / turning points.
- Node-level interpretability:
  - track hub rank stability across `(nodes, sparsity)` settings.
- Reproducibility:
  - rerun with alternative nuisance settings (`compcor_only`, `gsr_only`, `paper`) for robustness bounds.
