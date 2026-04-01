# ETTh1 Modeling Storyline Blueprint (Top-Journal Draft, 2026-03-27)

## 0) One-Sentence Hook

Can a brain-inspired sparse routing architecture keep ETTh1 forecasting quality while reducing inference cost enough to matter at scale?

This is the story focus, not "data collection was hard."

## 1) Answers to the 5 Core Questions

### Q1. What is this project really about?

This project tests a design hypothesis:

- use structured sparse routing (brain-state template idea in `mobse`, generic routing in `moe`)
- to improve the practical forecasting operating point on ETTh1 (`error + latency + FLOPs` together)
- under a dual-task regime (`OS classification + ETTh1 forecasting`) to stress routing behavior.

### Q2. What did the authors build and test?

Core implementation path:

1. ETTh1 windowing + scaling (`mobse/data/etth1.py`)
2. routing-based model families (`mobse/models/mobse.py`, `mobse/models/baselines.py`)
3. dual-task optimization with normalized task loss and best-checkpoint selection (`mobse/train.py`)
4. paired-seed benchmark comparisons and routing/efficiency figures (`docs/experiments/*`, `scripts/phase2_figures.py`)

### Q3. What is the AI/LLM/Agent relevance?

- AI/LLM relevance: sparse routing and expert selection are the same efficiency problem class as modern MoE LLM systems.
- Agent relevance: the repo already operationalizes an agentic experiment loop (collect -> train/eval -> compare -> report) that can be extended into autonomous hypothesis testing.

### Q4. How did failures shape the final theory?

Observed failure chain and fixes:

- failure A: dual-task training instability (classification signal buried by forecast loss)
  - fix: normalized multi-task loss + huber + early stopping
- failure B: "bigger graph is better" did not hold (n200 instability/cost)
  - fix: node-size sweep + top-k config balancing + paired-seed comparisons
- failure C: biologically inspired prior did not dominate every setting
  - fix: explicit baseline confrontation; operational mainline moved to `MoE n100`.

The stronger final claim is therefore:

- routing-centric sparse design is valuable,
- but "brain prior always wins" is not yet proven.

### Q5. What illustrations can support this story?

Use a 6-panel narrative figure sequence (Section 4 below) that moves from hypothesis to falsification-to-refinement, not just final scores.

## 2) ETTh1 Modeling Mechanics (Concrete Formulation)

The current code implies the following modeling equations.

Notation:

- ETTh1 input window: `X_et in R^(T x d)`
- OS input window: `X_os in R^(T x N)`
- experts: `E`
- hidden size: `H`

### 2.1 ETTh1 data construction

- standardize features with train split statistics
- build sliding windows:
  - input length `seq_len`
  - target horizon `pred_len`

Implemented in `mobse/data/etth1.py`.

### 2.2 Routing model forward (MoBSE)

For ETTh1 task:

1. temporal summary (control branch)  
   `p = mean_t(X_et[t])` (baseline) or `p = h_T` from GRU temporal encoder
2. node latent projection  
   `Z = reshape(W_et * p, N, H)`
3. routing weights  
   `g = softmax(MLP([0_N ; p]))` with top-k pruning depending on routing mode
4. expert graph mixture  
   `A = sum_e g_e * T_e`
5. graph propagation  
   `H_(l+1) = GELU(GraphLayer(H_l, A))`
6. forecast head  
   `y_hat = reshape(W_pred * mean_n(H_L[n]), pred_len, out_dim)`

Implemented in `mobse/models/mobse.py`.

### 2.3 Optimization objective

Training uses weighted normalized multi-task loss:

`L_train = w_os * (L_os / s_os) + w_et * (L_et / s_et)`

where:

- `L_os`: cross-entropy
- `L_et`: ETTh1 loss (`huber|mse|mae`, default huber)
- `s_os, s_et`: initial loss scales estimated from warmup batches

Checkpoint selection uses `selection_metric`, typically `weighted_normalized_loss`.
Implemented in `mobse/train.py`.

## 3) Logical Gaps Status (Updated 2026-03-27)

1. Brain prior -> ETTh1 gain causality
   - status: partially addressed (historical prior on/off sweeps exist), still not universal.
2. Multi-task benefit separation
   - status: closed for current scope (`10`-seed ETTh1-only vs dual-task runs completed).
3. Temporal bottleneck control
   - status: closed for current scope (`mean` vs `gru` control implemented and run).
4. Routing interpretability linkage to ETTh1 regimes
   - status: partially open (routing stats exist, regime-linked interpretability analysis still needed).
5. Statistical power
   - status: closed for current scope (`10`-seed paired stats available on main ETTh1 controls).

## 3.1 Execution Update (10-Seed Evidence)

Run summary:

- ETTh1-only + mean: `MAE 2.262`, `MSE 8.658`, `latency 0.329 ms`, `FLOPs 2,960,608`
- Dual-task + mean: `MAE 2.206`, `MSE 7.860`, `latency 0.330 ms`, `FLOPs 2,960,608`
- ETTh1-only + GRU: `MAE 1.459`, `MSE 3.711`, `latency 2.577 ms`, `FLOPs 3,759,328`
- Dual-task + GRU: `MAE 1.417`, `MSE 3.579`, `latency 2.581 ms`, `FLOPs 3,759,328`

Key paired findings:

1. dual-task(mean) vs etth1-only(mean): ETTh1 MSE improved (`p_t=0.0186`, `p_w=0.0098`)
2. GRU vs mean (both regimes): ETTh1 MAE/MSE strongly improved (`p_t < 3e-8`)
3. GRU regime imposes clear efficiency cost (latency/FLOPs increase)

## 4) Figure Storyline (Gi-Seung-Jeon-Gyeol)

### Figure 1 (Gi: Hook)

Title:
- "Routing, Not Scale: A Different Path for Time-Series Forecasting Efficiency"

Content:
- visual metaphor (dense all-to-all vs sparse routed experts)
- one inset with ETTh1 target objective (`MAE/MSE + latency`)

Type:
- illustration (not a chart)

### Figure 2 (Seung: Model Construction)

Title:
- "From ETTh1 Window to Routed Graph Forecast"

Content:
- full pipeline diagram (windowing -> projection -> gate -> expert mixture -> forecast head)
- include equations in compact side boxes

Type:
- technical schematic (diagram)

### Figure 3 (Seung: Failure Emerges)

Title:
- "Why Naive Dual-Task Training Failed"

Content:
- training dynamics showing task-loss imbalance
- before/after normalization and huber stabilization

Type:
- quantitative chart

### Figure 4 (Jeon: Hypothesis Stress Test)

Title:
- "When Brain Prior Helps, and When It Does Not"

Content:
- node x sparsity x routing x prior ablation map
- mark regions where `noprior` beats `prior`

Type:
- heatmap/ablation matrix

### Figure 5 (Jeon->Gyeol: Competitive Reality)

Title:
- "MoBSE vs Transformer Family vs MoE: ETTh1 Pareto Frontier"

Content:
- error-latency and error-FLOPs Pareto plots
- emphasize practical operating point transition to `MoE n100`

Type:
- quantitative chart

### Figure 6 (Gyeol: Refined Theory)

Title:
- "Refined Claim: Routing-Centric Efficiency Framework"

Content:
- final claim boundaries:
  - supported now
  - pending proof (brain prior universality, temporal bottleneck removal)

Type:
- conceptual summary illustration

## 5) Illustration Skill Support (imagegen)

Available skill found:

- `imagegen` (`/Users/hwon/.codex/skills/.system/imagegen/SKILL.md`)

Recommended use split:

1. use plotting scripts for quantitative figures (F3-F5)
2. use image generation for conceptual hero/schematic figures (F1, F2, F6)

Prompt template (for conceptual panels):

```text
Use case: infographic-diagram
Asset type: journal figure panel
Primary request: [panel objective in one sentence]
Style/medium: clean scientific illustration, minimal palette, publication-ready
Composition/framing: landscape, left-to-right process flow, clear labels
Constraints: no watermark, no decorative clutter, high legibility at print size
Text (verbatim): [panel title and 3-5 key labels]
```

## 6) Immediate Next Experiments (to strengthen the paper story)

1. routing interpretability deep-dive:
   - link expert usage shifts to ETTh1 error buckets and input regimes.
2. prior universality stress-test:
   - repeat prior on/off control under temporal-GRU regime and additional datasets.
3. manuscript-figure finalization:
   - lock quantitative panels (`F3/F4/F5`) and finish conceptual panels (`F1/F2/F6`).
