# MoBSE vs Legacy dFC Experiment Template (2026-04-02)

## 1) Objective
- Goal: Verify whether MoBSE provides a better efficiency-interpretability tradeoff than legacy models under the same dFC-informed setting.
- Core claim direction:
  - MoBSE preserves or improves task performance while showing favorable network-structure control (integration/segregation balance).

## 2) Models to Compare
- MoBSE (primary)
- Legacy baselines:
  - Transformer
  - Sparse Transformer
  - MoE baseline (non-brain-template routing)

## 3) Controlled Factors
- Same dataset/split/seed set for all models.
- Same node scales: `100`, `200`
- Same sparsity settings: `0.1`, `0.2`
- Same nuisance setting per run family:
  - `fmriprep_confounds_only` (current)
  - optional robustness families: `compcor_only`, `gsr_only`, `paper_compcor_gsr`

## 4) Hypotheses
- H1 (efficiency): MoBSE achieves equal or lower compute cost (latency/FLOPs/memory) at matched performance.
- H2 (network topology control): Increasing sparsity target (`0.1 -> 0.2`) in MoBSE increases global efficiency and reduces modularity/community count in a stable direction across node scales.
- H3 (legacy contrast): Legacy models do not show equally stable topology-linked behavior under the same configuration controls.

## 5) Metrics
- Predictive:
  - OS: Accuracy, F1-macro
  - ETTh1: MAE, MSE
- Efficiency:
  - latency mean/std
  - FLOPs
  - peak memory
- Network (template-level):
  - density, mean strength, mean degree
  - global efficiency
  - weighted clustering
  - modularity (LCC), number of communities

## 6) Statistical Plan
- Seed-level paired comparison (same seed, same config, model only changed).
- Main tests:
  - paired t-test or Wilcoxon signed-rank (non-normal case)
  - effect size (Cohen's d or matched-rank effect)
- Multiple-comparison handling:
  - FDR correction for metric families.
- Report format:
  - mean ± std
  - delta (MoBSE - baseline)
  - p-value, adjusted p-value, effect size

## 7) Execution Matrix (Recommended)
- Grid:
  - models: 4
  - nodes: 2
  - sparsity: 2
  - seeds: >=10 recommended
- Minimal matrix:
  - 4 x 2 x 2 x 10 = 160 runs

## 8) Reviewer-Risk Guardrails
- dFC caveat:
  - state explicitly that FC is statistical dependency, not causal pathway.
- Denoising caveat:
  - disclose nuisance pipeline details and robustness checks.
- Single-state caveat:
  - for rest-only datasets, focus on topology profiling rather than state-separation claims.

## 9) Deliverables Checklist
- Run manifests and resolved configs
- Unified summary table (performance + efficiency + network metrics)
- Paired statistics table
- Figure set:
  - Pareto (performance vs compute)
  - Topology shift plot (`sp10` vs `sp20`)
  - Model comparison radar/heatmap

## 10) Immediate Next Actions
1. Freeze baseline config family for fair comparison.
2. Generate run plan CSV (all model/node/sparsity/seed combinations).
3. Execute training/eval matrix.
4. Aggregate metrics and run paired statistics.
5. Draft Discussion with integration-vs-segregation framing and limitation statements.
