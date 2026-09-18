# Phase 2 Strategy Pivot: HCP → OpenNeuro Rest-only + dFC Clustering

**Date**: 2026-04-15  
**Decision owner**: Dr. Hwon Heo

---

## 1. Background & Motivation

Phase 1 (PoC v1) validated the MoBSE architecture using OpenNeuro ds000030 (HC127) with 5 task-defined brain states (`rest`, `wm`, `motor`, `language`, `attention`). Phase 2 was originally planned as HCP-scale validation (≥300 subjects).

**Pivot reason**: HCP data availability issue → OpenNeuro multi-dataset pooling으로 전환.

---

## 2. Key Architectural Analysis

### 2.1 What MoBSE Actually Requires

MoBSE의 핵심은 **서로 다른 brain connectivity state**를 expert template으로 사용하는 것. 코드 레벨에서:

- `build_state_templates()`: state별 FC matrix를 group averaging → sparse template
- `num_experts` = `len(states)` — expert 수가 state 수에 직결
- `os_num_classes` = `len(states)` — classification head도 state 수에 연동
- Input format: `[time, nodes]` shape의 ROI timeseries (`.npy`)

### 2.2 Scan Time Constraints

- 유일한 hard constraint: `window_len ≥ 64` timepoints (default)
- TR 이질성 문제: dataset마다 TR이 다름 (0.72s ~ 2.5s) → 동일 window_len이 실제 시간으로 다름
- 권장: window_len을 시간 기반으로 전환하거나, TR normalization 검토 필요

### 2.3 Rest-only vs Multi-task

| 구분 | Phase 1 (현재) | Phase 2 Option A | Phase 2 Option B (선택) |
|------|-------------|-----------------|----------------------|
| State 정의 | task label (rest/wm/motor/...) | task label | dFC clustering |
| Template 구성 | task별 FC averaging | task별 FC averaging | sliding window → k-means |
| 필요 데이터 | rest + task fMRI | rest + task fMRI | **resting-state only** |
| 데이터 가용성 | 제한적 | 매우 제한적 | **풍부** |
| 이론적 근거 | Shine et al. 2016 | 동일 | Allen et al. 2014 |

**선택: Strategy B (Rest-only + dFC clustering)**

---

## 3. Strategy B: dFC Clustering 기반 Template 생성

### 3.1 Method

1. Resting-state BOLD → ROI timeseries (Schaefer 100/200)
2. Sliding window FC computation (window ~30-60s, stride ~1-2 TR)
3. Fisher-Z transform → vectorize upper triangle
4. k-means clustering (k = num_experts, e.g., 4-6)
5. Cluster centroids → brain-state templates
6. Per-window cluster assignment → classification labels

### 3.2 Advantages

- Allen et al. (2014)의 well-established method → reviewer acceptance 높음
- Resting-state만 필요 → OpenNeuro/ABIDE에서 대량 수집 가능
- "Dynamic brain states" 가설과 더 직접적으로 연결
- task label 의존성 제거 → cross-dataset heterogeneity 감소

### 3.3 Implementation Changes Required

- `build_state_templates()` 대체/확장: dFC sliding window + clustering pipeline
- `states` config: task label list → `num_dfc_states: int` (data-driven)
- Classification task 재정의: task label prediction → dFC state prediction
- Window-level label: cluster assignment로 자동 생성

---

## 4. Data Requirements

### 4.1 필요한 데이터 형태

**Preprocessed ROI timeseries** — 아래 중 하나면 충분:

- `.npy` / `.csv` / `.tsv` / `.1D` 형태의 `[time, nodes]` matrix
- fMRIPrep derivatives에서 confounds regression 후 atlas-based extraction 완료된 것
- 또는 raw BOLD + confounds TSV (자체 nuisance regression pipeline 사용)

**Raw NIfTI 불필요** — pre-extracted ROI timeseries derivatives만 있으면 됨.

### 4.2 Dataset Sources

| Source | 예상 HC 수 | 데이터 형태 | 비고 |
|--------|----------|-----------|------|
| ABIDE PCP (nilearn) | ~578 | pre-extracted ROI (CC200/CC400) | 즉시 사용 가능, Schaefer 재매핑 필요 |
| OpenNeuro multi-dataset | 300-400 | raw NIfTI + fMRIPrep derivatives 혼재 | dataset별 확인 필요 |
| nilearn development fMRI | ~100 | preprocessed | 소아(7-9세) — 별도 관리 |

### 4.3 CONSORT Flow 설계 포인트

```
Identified datasets (OpenNeuro + ABIDE + nilearn)
    │
    ├─ Excluded: no resting-state
    ├─ Excluded: no derivatives / insufficient preprocessing
    ├─ Excluded: pediatric-only (age < 18)
    │
    ▼
Eligible datasets
    │
    ├─ Excluded: < N timepoints (scan too short)
    ├─ Excluded: excessive motion (FD > threshold)
    ├─ Excluded: ROI coverage < threshold
    │
    ▼
Included subjects
    │
    ├─ Schaefer 100 extraction
    ├─ Schaefer 200 extraction
    │
    ▼
dFC sliding window → k-means clustering
    │
    ▼
Template bank + window labels
```

---

## 5. Open Questions

1. **k (number of dFC states)**: 고정 (e.g., 5) vs data-driven (silhouette/elbow)?
2. **ABIDE CC200 → Schaefer 매핑**: 직접 사용 vs NIfTI 재추출?
3. **TR normalization**: 리샘플링 vs 시간 기반 window_len?
4. **QC threshold**: motion (FD), scan duration minimum?
5. **Dual-task framing**: ETTh1 forecasting은 유지? dFC state classification으로 OS task 대체?

---

## 6. References

- Allen, E. A. et al. (2014). *Tracking whole-brain connectivity dynamics in the resting state.* Cerebral Cortex.
- Shine, J. M. et al. (2016). *The dynamics of functional brain networks.* Neuron.
- Damaraju, E. et al. (2014). *Dynamic functional connectivity analysis reveals transient states of dysconnectivity in schizophrenia.* NeuroImage: Clinical.
