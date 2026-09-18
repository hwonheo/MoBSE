# Phase 2 Execution Strategy (Revised)

**Date**: 2026-04-15 (updated with AOMIC task fMRI availability)  
**Approach**: Strategy B (primary) + Strategy A validation  
**Companion docs**:
- [Strategy Pivot](phase2_strategy_pivot_2026-04-15.md)
- [Dataset Collection Plan](phase2_dataset_collection_2026-04-15.md)
- [dFC Clustering Optimization](phase2_dfc_clustering_optimization_2026-04-15.md) — PCA sweep results, recommended config

---

## 0. Executive Summary

Phase 1에서는 task label 기반 brain-state template으로 MoBSE PoC를 검증.  
Phase 2에서는 두 갈래로 진행:

- **Primary (Strategy B)**: resting-state dFC clustering으로 data-driven brain-state를 추출, 대규모 (>1,000 HC) 데이터에서 scalability 검증.
- **Validation (Strategy A)**: AOMIC PIOP1+PIOP2 (N=442)의 task-based fMRI를 활용, Phase 1의 task-label 기반 접근을 독립 데이터에서 재검증.

**핵심**: 두 전략이 동일 AOMIC 데이터에서 비교 가능 → "data-driven states vs task-defined states" 직접 대조.

### Revised Strategy Matrix

| | Strategy B (dFC) | Strategy A (task-label) |
|-|------------------|------------------------|
| **Data** | AOMIC 전체 (1,370) + ABIDE (573) rest-only | AOMIC PIOP1+PIOP2 (442) rest + 6 tasks |
| **Template** | Sliding window FC → k-means centroids | Task별 FC averaging (Phase 1 방식) |
| **Classification** | dFC state prediction (data-driven labels) | Task-condition prediction (ground-truth labels) |
| **Strength** | 대규모 N, 사전 label 불필요 | 해석 가능한 ground-truth, Phase 1과 직접 비교 |
| **논문 기여** | Main result: scalability + efficiency | Supplementary: cross-validation of PoC findings |

---

## 1. dFC Clustering Pipeline Design

### 1.1 Method (Allen et al., 2014 기반)

```
Per subject:
  BOLD [T, nodes] (Schaefer 100 or 200)
      │
      ▼
  Sliding window FC
  (tapered cosine window, width=w, stride=s)
      │
      ▼
  Fisher-Z transform
      │
      ▼
  Vectorize upper triangle → feature vector [n_edges]
      │
      ▼
  Stack all windows from all subjects
      │
      ▼
  k-means clustering (k = num_experts)
      │
      ├─→ Cluster centroids → reshape → [k, nodes, nodes] → sparsify → template bank
      └─→ Per-window cluster labels → classification target
```

### 1.2 Key Parameters

| Parameter | Default | Range to explore | Notes |
|-----------|---------|-----------------|-------|
| `dfc_window_sec` | 45 | 30, 45, 60 | 초 기반, TR에 따라 timepoints 자동 산출 |
| `dfc_stride_sec` | 2 | 1, 2, 3 | |
| `dfc_taper` | cosine | cosine, rectangular | Allen: tapered cosine 권장 |
| `dfc_k` | 5 | 3, 4, 5, 6, 7 | silhouette score로 최적 k 탐색 |
| `dfc_n_init` | 100 | | k-means 반복 |
| `dfc_fisher_z` | true | | |
| `sparsity` | 0.2 | 0.1, 0.2, 0.3 | template sparsification |

### 1.3 Implementation Plan

**새 모듈**: `mobse/data/dfc.py`

```python
def compute_sliding_window_fc(
    timeseries: np.ndarray,      # [T, nodes]
    window_sec: float,
    stride_sec: float,
    tr: float,
    taper: str = "cosine",
    fisher_z: bool = True,
) -> np.ndarray:
    """Returns [n_windows, n_edges] matrix of vectorized FC."""

def cluster_dfc_states(
    all_fc_vectors: np.ndarray,  # [total_windows, n_edges]
    k: int,
    n_init: int = 100,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Returns (centroids, labels, metrics)."""

def build_dfc_templates(
    centroids: np.ndarray,       # [k, n_edges]
    num_nodes: int,
    sparsity: float,
) -> np.ndarray:
    """Reshape centroids → [k, nodes, nodes], sparsify, return template bank."""
```

**기존 코드 수정**:
- `config.py`: `DFCConfig` dataclass 추가
- `templates/builder.py`: dFC path 분기 추가
- `os_data.py`: dFC label 기반 window 생성 지원
- `cli.py`: `build_templates --mode dfc` 옵션

---

## 2. Revised Architecture Flow

### Phase 1 (기존)
```
task label → FC averaging per state → template bank
                                          ↓
Input → Gating → Template selection → Graph MP → Output
                                          ↑
                              OS-state classification (task labels)
```

### Phase 2 (신규)
```
resting-state → sliding window FC → k-means → template bank
                                                    ↓
Input → Gating → Template selection → Graph MP → Output
                                                    ↑
                                    dFC-state classification (cluster labels)
```

**변경 최소화**: template bank과 classification label의 출처만 바뀌고, model architecture 자체는 동일.

---

## 3. Experimental Design

### 3.1 Main Experiment Matrix

| Factor | Levels | |
|--------|--------|-|
| Atlas | 100, 200 | 2 |
| dfc_k | 4, 5, 6 | 3 |
| Sparsity | 0.1, 0.2 | 2 |
| Routing | soft, hard | 2 |
| Template prior | on, off | 2 |
| Seeds | 42, 43, 44 | 3 |

Total: 2 × 3 × 2 × 2 × 2 × 3 = **144 runs**

### 3.2 Ablation Priority (단계적 실행)

**Stage A (Core)**: atlas{100} × k{5} × sp{0.2} × routing{soft} × prior{on/off} × 3 seeds = 6 runs  
→ template prior 효과 확인

**Stage B (k Sensitivity)**: atlas{100} × k{3,4,5,6,7} × sp{0.2} × routing{soft} × prior{on} × 3 seeds = 15 runs  
→ 최적 k 탐색

**Stage C (Full)**: 전체 matrix 실행

**Stage D (Strategy A Validation)**: AOMIC PIOP1+PIOP2 (N=442) task-label 기반  
- Task states: restingstate, workingmemory, emomatching, faceperception, gstroop, stopsignal (6-7 states)
- atlas{100} × sp{0.2} × routing{soft} × prior{on/off} × 3 seeds = 6 runs
- Phase 1 방식과 동일한 task-label FC averaging → template bank
- **비교 포인트**: 동일 PIOP subjects에서 Strategy A vs B 직접 대조

### 3.3 Evaluation Metrics

| Category | Metric | Notes |
|----------|--------|-------|
| dFC quality | Silhouette score, Calinski-Harabasz | k selection validation |
| dFC quality | State occupancy rate | 각 state에 충분한 window가 할당되는지 |
| Classification | Accuracy, F1-macro | dFC state prediction |
| Forecasting | MAE, MSE (ETTh1) | dual-task 유지 |
| Efficiency | FLOPs, memory, latency | Phase 1과 비교 |
| Routing | Expert utilization entropy | routing collapse 감시 |

---

## 4. Data Pipeline Overview

```
[Phase 2a]  AOMIC download (ds003097 + ds002785 + ds002790)
                │
                ▼
[Phase 2a]  fMRIPrep confounds extraction + Schaefer ROI masking
                │
                ▼
[Phase 2a]  QC filtering (FD, scan length, coverage)
                │
                ▼
[Phase 2a]  ROI timeseries [T, nodes] .npy per subject ──────┐
                                                               │
[Phase 2b]  ABIDE PCP download (rois_cc200) ──── CC200→Schaefer mapping ─┤
                                                               │
[Phase 2c]  ds000030 + ds000243 (기존) ───────────────────────┤
                                                               │
                                                               ▼
[Shared]    dFC sliding window → k-means clustering
                │
                ├─→ Template bank [k, nodes, nodes]
                └─→ Window labels [total_windows]
                        │
                        ▼
[Shared]    Train/Val/Test split (subject-level)
                │
                ▼
[Shared]    MoBSE training (dFC classification + ETTh1)
                │
                ▼
[Shared]    Evaluation + Reporting
```

---

## 5. Timeline Estimate

| Phase | Task | Duration | Dependency |
|-------|------|----------|------------|
| 2a-1 | AOMIC pilot download (10 subjects) | 1 day | — |
| 2a-2 | ROI extraction pipeline test | 2 days | 2a-1 |
| 2a-3 | dFC module implementation (`mobse/data/dfc.py`) | 3 days | — |
| 2a-4 | dFC pilot (10 subjects, k=5) | 1 day | 2a-2, 2a-3 |
| 2a-5 | AOMIC full download + processing | 1-2 weeks | 2a-4 validated |
| 2b | ABIDE integration | 1 week | 2a-3 |
| 2c | Stage A core experiments | 2-3 days | 2a-5 or 2b |
| 2d | Stage B k-sensitivity | 3-5 days | 2c |
| 2e | Stage C full matrix | 1-2 weeks | 2d |
| 2f | Stage D (Strategy A validation on PIOP) | 3-5 days | 2a-5 |
| 2g | Strategy A vs B 비교 분석 | 2-3 days | 2e, 2f |
| 2h | Reporting + figures | 1 week | 2g |

**Total estimated: 6-8 weeks**

---

## 6. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| AOMIC download 크기/시간 | 높음 | pilot 10명 먼저, derivatives만 선택적 다운로드 |
| dFC states가 trivial (1 dominant state) | 높음 | k selection 시 occupancy rate 검증, min 10% per state |
| TR heterogeneity across datasets | 중간 | window_sec 기반 통일, dataset을 covariate로 |
| CC200 → Schaefer 매핑 information loss | 중간 | ABIDE는 보강용, AOMIC이 주력 |
| Routing collapse at scale | 중간 | expert utilization entropy 모니터링, load balancing loss |

---

## 7. Success Criteria

1. **dFC template quality**: Silhouette ≥ 0.1, 모든 state occupancy ≥ 10%
2. **Scale-up**: N ≥ 500 HC에서 Phase 1 PoC 트렌드 재현 (template prior > no prior)
3. **Classification**: dFC state prediction accuracy > chance level (1/k) by ≥ 20%p
4. **Efficiency**: MoBSE FLOPs < dense transformer baseline by ≥ 30%
5. **Reproducibility**: 3-seed variance within acceptable range (CV < 10% for main metrics)
