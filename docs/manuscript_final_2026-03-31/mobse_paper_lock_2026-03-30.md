# MoBSE Paper Lock (2026-03-30)

## 1) Storyline Lock

**Human-"Real"-Network (very complex) -> Base (Yeo-7) -> MoBSE (Experts)**

- Real human rs-fMRI is high-variance, noisy, and heterogeneous.
- Yeo-7 provides the canonical and interpretable base coordinate.
- MoBSE experts specialize routing over that base coordinate to absorb complexity.

Final one-line claim:

> We model real human network complexity through a canonical Yeo-7 scaffold and show that MoBSE expert routing adds specialization while preserving neuroscience-level interpretability.

## 2) Result Lock (current mainline)

Data/model setting:
- ABIDE control adults: `n=143`
- Simulation fair control: `n=150`
- Matched compute/model: `nodes=200`, `experts=7`, `states=7`, `tasks=os`, matched FLOPs/latency scale

Locked headline numbers:
- OS loss: ABIDE `0.0033` vs SIM `1.9671`
- OS accuracy: ABIDE `1.0000` vs SIM `0.1324`
- OS F1-macro: ABIDE `1.0000` vs SIM `0.1072`
- OS latency(ms): ABIDE `2.4946` vs SIM `2.4907`
- OS FLOPs: ABIDE `86.38M` vs SIM `86.38M`

Reference artifacts:
- `artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports/abide_vs_simul_eval_report.md`
- `artifacts/current_canonical/abide_mobse_mainline_20260330/reports/mobse_mainline_summary.csv`

## 3) Figure Lock

Figure and table set is fixed as follows:

1. **Fig1** Framework storyline
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f1_hook_routing_vs_scale.png`
- Caption key: Real complexity -> Yeo-7 base -> MoBSE expert specialization.

2. **Fig2** OS core results (ABIDE vs fair SIM)
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f2_etth1_model_schematic.png`
- Caption key: classification gain under matched subject scale.

3. **Fig3** OS profile results (latency/FLOPs)
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f3_temporal_bottleneck_control.png`
- Caption key: compute parity context for fair interpretation.

4. **Fig4** ETTh1 core results (context panel)
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f4_prior_boundary_map.png`
- Caption key: auxiliary task context, not primary claim axis.

5. **Fig5** OS routing usage by network
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f5_etth1_pareto_frontier.png`
- Caption key: expert/network usage distribution for mechanism-level interpretation.

6. **Fig6** MoBSE mainline quality summary
- `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/fig_ett_family_mae_mse_s10.png`
- Caption key: compact quality dashboard for rebuttal/supplement.

Table lock:

1. Storyline run summary
- `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv`
- Canonical use: 10-seed rerun baseline for ETTh1-only vs dual-task, mean vs GRU

2. Storyline pairwise statistics
- `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv`
- Canonical use: paired significance and effect-size report for rerun10

3. ETT-family extension summary
- `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv`
- Canonical use: 10-seed generalization check over ETTh1/ETTh2/ETTm1/ETTm2

## 4) Paper Structure Lock

1. Introduction
- Problem: real human network complexity and interpretation gap.
- Position: Yeo-7 as canonical base for interpretable modeling.
- Contribution: MoBSE expert specialization on top of Yeo-7.

2. Methods
- Data: ABIDE control adult cohort and matched simulation control.
- Base representation: Yeo-7 network state framing.
- Model: MoBSE with expert routing.
- Protocol: matched compute setting and reporting policy.

3. Results
- R1. Main benchmark (Fig2, Fig3): OS performance with compute parity.
- R2. Mechanism interpretation (Fig5): routing usage/network-level interpretation.
- R3. Supporting context (Fig4, Fig6): auxiliary and summary panels.
- R4. ETTh1 and ETT-family rerun10 results: reproducible 10-seed story and cross-dataset extension.

4. Discussion
- Why Yeo-7 baseline is the best practical base.
- What is valid despite limitations.
- How robustness extensions (strict split, denoising sensitivity) will strengthen final claims.

5. Limitations and Future Work
- Window-level split risk.
- State-generation asymmetry across datasets.
- Cohort/acquisition heterogeneity and preprocessing dependency.
- Planned strict subject-level split and sensitivity analyses.

## 5) Discussion Lock (must remain explicit)

Mandatory limitations to state in manuscript:
- Window-level split can inflate OS classification metrics.
- ABIDE vs simulation state generation is not fully symmetric.
- Dataset heterogeneity limits direct biological equivalence.
- Preprocessing/denoising choices may shift effect sizes.

Mandatory positive claim to preserve:

> Human rs-fMRI + Yeo-7 base + MoBSE experts provides a mechanistically interpretable modeling axis that cannot be obtained from simulation-only performance comparison.

## 6) Out-of-Scope Claim Lock

Do not claim yet:
- strict clinical generalization
- biomarker-level causal interpretation
- robustness to preprocessing without explicit sensitivity runs

## 7) Execution Continuity

- Keep this lock as the single reference for figure order and section narrative.
- Any future run can update numbers, but **must not change storyline axis** unless explicitly approved.
