# Benchmark Goal and Stage Targets (2026-03-23)

## 1. Final Goal

The current mainline goal is:

> Establish `MoE n100` as the preferred operating point on the public-data benchmark and show that its predictive quality and efficiency survive cross-dataset transfer and HCP-accessible validation strongly enough to support the next scale-up wave.

This is the decision gate before spending more effort on:

- cross-dataset generalization
- HCP-accessible cohort validation
- method extensions

## 2. Locked Reference Point

Current public-data mainline reference (`MoE n100`, 5 seeds):

- OS accuracy: `0.1817`
- OS F1 macro: `0.0893`
- ETTh1 MAE: `2.2099`
- ETTh1 MSE: `7.7896`
- OS latency: `0.3842 ms`
- ETTh1 latency: `0.3519 ms`
- FLOPs: `2.96M`

This becomes the benchmark that later runs must be compared against.

## 3. Stage Gates

### Stage A. Reproducibility Gate

Goal:

- Make reruns trustworthy before launching broader benchmark work.

Must pass:

- full local test suite passes
- generated manifests use portable paths
- baseline configs and follow-up configs are versioned

Current status:

- pass

### Stage B. Baseline Execution Gate

Goal:

- Run the three baseline families end-to-end on the same `n100` Phase-2 dataset and seed set.

Models:

- `transformer`
- `sparse_transformer`
- `moe`

Must pass:

- all 3 models finish `train -> evaluate -> report`
- each baseline produces `raw_metrics.csv` and `summary_table.csv`
- no run changes the data source or seed set

Current status:

- pass

### Stage C. Baseline Benchmark Gate

Goal:

- Decide whether `MoBSE n100` remains the mainline architecture after direct comparison.

Absolute guardrails for the selected public mainline:

- OS accuracy `>= 0.175`
- OS F1 macro `>= 0.100`
- ETTh1 MAE `<= 2.30`
- ETTh1 MSE `<= 8.80`
- OS latency `<= 2.00 ms`
- ETTh1 latency `<= 1.80 ms`

Relative success criteria versus baselines:

- Green:
  - MoBSE is best or tied on at least 2 predictive metrics among:
    - OS accuracy
    - ETTh1 MAE
    - ETTh1 MSE
  - and remains the fastest architecture on both tasks
- Yellow:
  - MoBSE is not best on performance, but stays within:
    - `0.01` absolute OS accuracy of the best baseline
    - `0.15` MAE of the best baseline
    - `0.80` MSE of the best baseline
  - while keeping at least:
    - `25%` lower latency than the best-performing competitor
    - `50%` lower FLOPs than the best-performing competitor
- Red:
  - a baseline beats MoBSE by more than those margins and the efficiency gap is no longer substantial

Current status:

- complete
- result: `MoE n100` selected as mainline, `MoBSE n100` retained as comparator

### Stage D. Cross-Dataset Generalization Gate

Goal:

- Check that the selected mainline model is not just exploiting pooled dataset shortcuts.

Target thresholds:

- OS accuracy drop under dataset transfer: `<= 0.03` absolute
- ETTh1 MAE degradation: `<= 0.20`
- ETTh1 MSE degradation: `<= 1.00`

Current status:

- pass
- `ds000030 -> ds000243` and `ds000243 -> ds000030` both remain inside the target band for `MoE n100`

### Stage E. HCP-Scale Validation Gate

Goal:

- Move from public-proxy validation to the stronger roadmap claim.

Target thresholds:

- retain the Stage C efficiency advantage direction
- OS accuracy remains within `0.02` of the public-data mainline result
- ETTh1 MAE remains within `0.20` of the public-data mainline result

Current status:

- pass after recovery rerun
- `hc127` first pass missed the OS-accuracy band, but `hcp152` recovery moved the gap to `0.0133`

## 4. Immediate Automatic Run Plan

The next automatic recovery wave is:

1. run `128` / `150` intermediate node sweep around the current `n100` mainline
2. execute nuisance sensitivity on the locked `MoE n100` operating point
3. keep `MoBSE n100` as the comparator in the same matrix

Execution policy:

- keep seeds, device, and reporting procedure fixed
- change one axis at a time
- preserve the current public-data mainline config as the base template

## 5. Decision Rule After the Runs

After the HCP recovery wave finishes:

1. compare intermediate-node candidates against the current `MoE n100` reference
2. keep predictive deltas small while watching latency/FLOPs
3. only replace `MoE n100` if a new point is clearly better in both practical quality and efficiency
