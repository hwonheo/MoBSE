# Phase 2: Expert Routing Anti-Collapse Experiments (2026-04-16)

## Overview

Phase 2 dFC-based MoBSE 학습에서 발견된 **expert collapse** (dfc_1이 87–99% routing weight 독점) 문제의 진단과 해결.

## Problem Statement

AOMIC PIOP1 (N=216, Schaefer-100) all-tasks 학습 후 eval_routing 분석에서 모든 task에 대해 dfc_1 expert가 87–99% routing weight를 차지. emomatching에서 가장 심각 (dfc_1=99.2%, dfc_0=0.5%, dfc_2=0.3%).

## Attempted Fixes (FAILED — identical training curves)

| Attempt | Config | Result |
|---------|--------|--------|
| Switch Transformer balance loss (α=0.1) | `balance_loss_weight: 0.1` | train_os IDENTICAL |
| Balance loss α=1.0 | `balance_loss_weight: 1.0` | train_os IDENTICAL |
| Entropy-based balance loss + gate_temp=3.0 | `balance_loss_weight: 1.0, gate_temperature: 3.0` | train_os IDENTICAL |

모든 시도에서 training metrics가 소수점 4자리까지 동일 → **balance loss gradient가 gate에 전달되지 않음**.

## Root Cause Diagnosis

### Hypothesis A: Template similarity (REJECTED)
- Template 간 cosine similarity: 0.784–0.905
- Relative Frobenius distance: 44–63%
- **결론**: Template은 충분히 다르다. Routing이 변해도 adjacency matrix가 유의미하게 달라짐.

### Hypothesis B: Gradient flow bug (CONFIRMED)
`_routing_weights()`의 top-k pruning 코드:
```python
# BUG: scatter_(values) on fresh zeros tensor
pruned = torch.zeros_like(weights)
pruned.scatter_(1, topi, topv)
```
`torch.zeros_like(weights)`는 gradient graph에 연결되지 않은 leaf tensor. `scatter_`가 값을 복사하지만 full model training context에서 balance loss → routing → gate gradient가 사실상 zero.

### Fix: Differentiable Masking
```python
# FIX: multiply weights by binary mask → gradient flows through weights
mask = torch.zeros_like(weights)
mask.scatter_(1, topi, 1.0)
pruned = weights * mask
```

**Diagnostic 확인** (debug_balance_grad.py):
- Balance loss grad on gate bias: **3.8–17× CE loss grad** (충분히 강한 signal)
- Gate parameter에 nonzero gradient 확인

## Experiments

### Exp C: Differentiable masking + balance loss (routing_k=2)
- Config: `config_dfc_alltasks_balanced_C.yaml`
- `routing_k=2, balance_loss_weight=1.0, gate_temperature=3.0`
- Artifacts: `artifacts/20260416_134500/`

### Exp D: No pruning + balance loss (routing_k=3)
- Config: `config_dfc_alltasks_balanced_D.yaml`
- `routing_k=3, balance_loss_weight=1.0, gate_temperature=3.0`
- Artifacts: `artifacts/20260416_141348/`

## Results

### Performance (test set, mean across seeds 42/43/44)

| Experiment | Test Loss | Accuracy | F1-macro | Routing Entropy |
|------------|-----------|----------|----------|-----------------|
| A+B baseline (no balance) | 0.870 | 0.583 | 0.473 | 0.276 (collapsed) |
| A-only (rest) | 0.866 | 0.589 | 0.474 | 0.693 |
| **Exp C (k=2, bal=1.0)** | **0.868** | **0.589** | **0.453** | **0.693** |
| Exp D (k=3, bal=1.0) | 0.866 | 0.587 | 0.455 | 1.099 (uniform) |

### Task-Specific Routing (Exp C — best configuration)

| Task | dfc_0 | dfc_1 | dfc_2 | Dominant | Cognitive Load |
|------|-------|-------|-------|----------|----------------|
| restingstate | 0.320 | **0.373** | 0.307 | dfc_1 | Low |
| anticipation | 0.318 | **0.368** | 0.314 | dfc_1 | Low |
| faces | 0.306 | **0.360** | 0.334 | dfc_1 | Medium |
| gstroop | 0.295 | 0.345 | **0.361** | dfc_2 | Medium |
| emomatching | 0.273 | 0.226 | **0.501** | dfc_2 | High |
| workingmemory | 0.263 | 0.273 | **0.464** | dfc_2 | High |

**Brain-state interpretation**: dfc_1 = low-demand state, dfc_2 = high cognitive-demand state. Routing이 task의 인지적 부하와 일치.

### Exp D Problem
- 모든 task에서 routing = [0.333, 0.333, 0.334] (perfectly uniform)
- routing_entropy = 1.099 = log(3) = maximum
- balance_loss_weight=1.0이 CE loss를 완전 압도 → task-specific differentiation 소실

## Key Files Modified

| File | Change |
|------|--------|
| `mobse/models/mobse.py` | `scatter_(values)` → `weights * mask` (differentiable masking) |
| `mobse/train.py` | `_load_balance_loss()` entropy-based implementation |
| `mobse/config.py` | `balance_loss_weight`, `gate_temperature` fields |
| `mobse/models/__init__.py` | `gate_temperature` wiring in `build_model()` |

## New Scripts

| Script | Purpose |
|--------|---------|
| `scripts/debug_balance_grad.py` | Gradient flow diagnostic (balance loss → gate params) |
| `scripts/eval_routing.py` | Routing weight analysis & brain-state interpretability |
| `scripts/build_alltasks_windows.py` | Standalone all-tasks window generation (no torch dependency) |

## New Configs

| Config | Description |
|--------|-------------|
| `config_dfc_alltasks_balanced_C.yaml` | k=2, balance=1.0, temp=3.0 (best) |
| `config_dfc_alltasks_balanced_D.yaml` | k=3, balance=1.0, temp=3.0 (over-uniform) |
| `config_dfc_alltasks_balanced_E.yaml` | k=3, balance=0.1, temp=3.0 (pending) |

## Figures & Report
- Publication-quality report: `MoBSE_Expert_Routing_Report.docx`
- Figures (300 DPI): `figures/fig1_training_curves.png` ... `fig7_summary_panel.png`

## Next Steps

1. **Exp E**: routing_k=3, balance_loss_weight=0.1 → sweet spot between collapse and uniformity
2. **Hyperparameter sweep**: α ∈ {0.01, 0.05, 0.1, 0.5} × routing_k ∈ {2, 3}
3. **Multi-dataset validation**: PIOP2, ABIDE, OpenNeuro pooling
4. **Learnable templates**: `use_template_prior=False` vs fixed centroids
5. **Brain-state interpretability**: map expert templates to known resting-state networks (DMN, FPN, DAN)
