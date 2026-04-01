# ETTh1 Figure Execution Plan (Top-Journal, 2026-03-27)

## Goal

Build a 6-panel figure storyline with explicit hook -> tension -> resolution flow, using completed 10-seed evidence.

## Fixed Data Inputs

- readiness matrix:
  - `artifacts/journal_etth1_story_readiness_20260327/reports/readiness_items.csv`
- 4-run summary:
  - `artifacts/etth1_story_followup_20260327/reports/story_run_summary.csv`
- focused pairwise stats:
  - `artifacts/etth1_story_followup_20260327/reports/story_pairwise_focus.csv`
- prior-on/off historical sweep:
  - `artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv`
  - `artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_sweep_seed42.csv`

## Panel-Level Plan (Gi-Seung-Jeon-Gyeol)

### F1. Hook: Routing vs Scale

- message:
  - ETTh1 forecasting can be improved by routing design choices, not only by scaling.
- asset:
  - conceptual illustration (dense all-to-all vs routed experts)
- production:
  - generate with `imagegen` using scientific infographic style.

### F2. Model Build: ETTh1 Forward Mechanics

- message:
  - window -> routing -> expert mix -> prediction, with temporal branch switch (`mean|gru`).
- asset:
  - technical schematic diagram with 3 equation boxes.
- production:
  - conceptual diagram via `imagegen`, then final labels in vector editor.

### F3. Tension: Why Mean Pooling Was a Bottleneck

- message:
  - replacing mean pooling with temporal GRU sharply reduces ETTh1 error.
- chart inputs:
  - `story_run_summary.csv`
  - `story_pairwise_focus.csv`
- chart type:
  - paired slope plot (mean vs GRU) for MAE/MSE; side annotation for p-values.

### F4. Stress Test: Prior and Configuration Boundaries

- message:
  - brain prior is helpful in parts of configuration space, not universally dominant.
- chart inputs:
  - phase2 sweep CSVs (`n100`, `n200`)
- chart type:
  - ablation heatmap (node x sparsity x prior), with win/loss markers.

### F5. Competitive Reality: Pareto Frontier

- message:
  - ETTh1 error gain from GRU comes with measurable latency/FLOPs increase.
- chart inputs:
  - `story_run_summary.csv`
- chart type:
  - MAE vs latency and MAE vs FLOPs two-panel scatter with 4 operating points.

### F6. Resolution: Refined Claim Boundary

- message:
  - supported now: routing + temporal encoding trade-space is quantified.
  - still open: universal causal advantage of brain-template prior across domains.
- asset:
  - conceptual summary card/diagram.
- production:
  - `imagegen` concept panel with strict text constraints.

## Implementation Steps

1. lock plotting table
   - copy/verify fixed inputs into figure run manifest
2. implement figure builder
   - new script: `scripts/make_etth1_story_figures.py`
   - output dir: `artifacts/figures_etth1_story_20260327/reports/`
3. generate quantitative panels
   - F3, F4, F5 as deterministic matplotlib outputs (`dpi=300`)
4. generate conceptual panels
   - F1, F2, F6 with `imagegen` prompt template and label QA pass
5. caption + consistency gate
   - produce `figure_captions.md` and cross-check all reported values against CSVs

## imagegen Prompt Skeleton

```text
Use case: infographic-diagram
Asset type: journal figure panel
Primary request: [one-sentence panel objective]
Style: publication-grade scientific illustration, clean neutral palette
Composition: landscape, left-to-right logic flow, high print legibility
Constraints: no watermark, no decorative clutter, minimal icons, crisp labels
Text (verbatim): [panel title + 3~5 labels]
```

## Quality Gate

1. every quantitative value in captions matches source CSV within rounding tolerance
2. all axes include units (`ms`, `FLOPs`, `MAE`, `MSE`)
3. each panel has one core claim sentence and one caveat sentence
4. final figure order preserves hook -> conflict -> refinement flow
