# Phase 2 Dataset Collection Plan & CONSORT Flow

**Date**: 2026-04-15  
**Strategy**: B (Rest-only + dFC clustering)

---

## 1. Candidate Dataset Registry

### Tier 1: Pre-extracted ROI timeseries (즉시 사용 가능)

| ID | Dataset | Source | N (total) | N (HC est.) | Rest | Derivatives | ROI format | TR (s) | Notes |
|----|---------|--------|-----------|-------------|------|-------------|------------|--------|-------|
| D1 | **ABIDE PCP** | nilearn `fetch_abide_pcp()` | 1,112 | ~573 | O | O (4 pipelines) | rois_cc200, rois_cc400 | varies | DX_GROUP=2 for HC; cpac/ccs/dparsf/niak |
| D2 | **ABIDE II** | COINS/LORIS | ~1,114 | ~593 | O | partial | varies | varies | 별도 다운로드, PCP 미포함 가능 |

### Tier 2: fMRIPrep derivatives 제공 (ROI 추출만 필요)

| ID | Dataset | OpenNeuro | N (total) | N (HC est.) | Rest | Task fMRI | fMRIPrep | TR (s) | Notes |
|----|---------|-----------|-----------|-------------|------|-----------|----------|--------|-------|
| D3 | **AOMIC-ID1000** | ds003097 | 928 | ~928 | O | O (multiple) | O | 0.75 | 일반 인구, 성인, largest single dataset |
| D4 | **AOMIC-PIOP1** | ds002785 | 216 | ~216 | O | O (6 tasks) | O | 0.75 | 대학생 |
| D5 | **AOMIC-PIOP2** | ds002790 | 226 | ~226 | O | O (6 tasks) | O | 0.75 | 대학생 |
| D6 | **ds000243** | ds000243 | 50+ | ~50 | O | X | O | varies | 기존 pilot 완료 |
| D7 | **ds000030** (UCLA LA5c) | ds000030 | 272 | ~138 | O | partial | partial | 2.0 | Phase 1에서 사용 |

#### AOMIC Task fMRI Detail

PIOP1/PIOP2에서 제공하는 task paradigms (event files 포함):

| Task | Cognitive domain | PIOP1 | PIOP2 |
|------|-----------------|-------|-------|
| restingstate | — | O | O |
| workingmemory | Working memory | O | O |
| emomatching | Emotion perception | O | O |
| faceperception | Face perception | O | O |
| gstroop | Cognitive conflict/control | O | O |
| stopsignal | Response inhibition | O | O |
| moviewatching | Naturalistic vision | O | O |

**핵심 발견**: AOMIC PIOP1+PIOP2 (N=442)는 rest + 6 task conditions를 모두 제공 → **Strategy A (task-label 기반)도 동시 검증 가능**.  
ID1000은 rest + 일부 task만 제공 (확인 필요).

### Tier 3: Raw BOLD (fMRIPrep 전처리 필요)

| ID | Dataset | OpenNeuro | N (total) | N (HC est.) | Rest | TR (s) | Notes |
|----|---------|-----------|-----------|-------------|------|--------|-------|
| D8 | **ds004564** | ds004564 | ~50 | ~50 | O | varies | BIDS resting state |
| D9 | **ds003673** | ds003673 | ~30 | ~30 | O | varies | Yale rest + pupillometry |
| D10 | **ds001168** | ds001168 | 22 | ~22 | O | varies | 7T test-retest |

### Pilot-Verified Summary (2026-04-15)

| Source | N (HC) | Atlas | Rest TP | dFC 적합성 | 즉시 사용 | Notes |
|--------|--------|-------|---------|-----------|---------|-------|
| AOMIC PIOP1 | 216 | Schaefer 100/200 | **480** (6min) | 우수 | O (스트리밍) | `acq-mb3`, TR=0.75 |
| AOMIC PIOP2 | 226 | Schaefer 100/200 | 240 (3min) | 제한적 | O (스트리밍) | `acq-seq`, TR=0.75 |
| AOMIC ID1000 | 928 | — | — | **rest 없음** | X | moviewatching only |
| ABIDE PCP (TP≥150) | ~400 | CC200 | 152-296 | 양호 | **즉시** (ndarray) | 20 sites, site별 TP 상이 |
| ABIDE PCP (TP<150) | ~68 | CC200 | 78-146 | 부적합 | 제외 권장 | OHSU 78 TP 등 |
| ds000030 | ~138 | Schaefer 100/200 | varies | 기존 Phase 1 | O | TR=2.0 |
| ds000243 | ~50 | Schaefer 100/200 | varies | pilot 완료 | O | |
| **Total usable** | **~1,030** | | | | | |

**Atlas 분리 전략**: Schaefer pool (PIOP1+PIOP2+ds000030+ds000243 ≈ 630) vs CC200 pool (ABIDE ≈ 400) 독립 분석 후 결과 비교.

#### ABIDE Site-level Scan Length Detail

| TP range | Sites | N (HC) | dFC 45s window (est.) |
|----------|-------|--------|----------------------|
| 236-296 | UM_1/2, LEUVEN_1/2, USM, CMU, STANFORD | ~145 | 7-10 |
| 176-206 | PITT, OLIN, YALE, SBL, NYU, SDSU | ~210 | 5-6 |
| 146-152 | TRINITY, CALTECH, KKI | ~56 | 3-4 |
| 116 | UCLA_1/2, MAX_MUN | ~64 | ~3 (borderline) |
| 78 | OHSU | 13 | ~1 (exclude) |

---

## 2. Priority Execution Order

### Phase 2a: AOMIC (최우선)

**이유**: 단일 collection으로 최대 ~1,370명 HC, 동일 TR (0.75s), fMRIPrep derivatives 제공, BIDS 호환.  
**추가 장점**: PIOP1/PIOP2에서 6개 task paradigm 제공 → Strategy A도 검증 가능.

```
AOMIC-ID1000 (928) + PIOP1 (216) + PIOP2 (226) = 1,370 subjects (rest)
AOMIC-PIOP1 (216) + PIOP2 (226) = 442 subjects (rest + 6 tasks)
```

작업:
1. OpenNeuro에서 fMRIPrep derivatives 선택적 다운로드 (awscli)
2. Schaefer 100/200 atlas로 `NiftiLabelsMasker` ROI 추출
3. Confounds regression (fMRIPrep confounds TSV 활용)
4. QC (motion, coverage)

#### Download Commands (awscli)

```bash
# participants.tsv 먼저 (구조 확인)
aws s3 sync --no-sign-request s3://openneuro.org/ds003097 ./data/aomic/id1000 \
  --exclude "*" --include "participants.tsv"

# Resting-state fMRIPrep BOLD (MNI space) + confounds
aws s3 sync --no-sign-request s3://openneuro.org/ds003097 ./data/aomic/id1000 \
  --exclude "*" \
  --include "derivatives/fmriprep/sub-*/func/*task-restingstate*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz" \
  --include "derivatives/fmriprep/sub-*/func/*task-restingstate*desc-confounds_regressors.tsv" \
  --include "derivatives/fmriprep/sub-*/func/*task-restingstate*desc-confounds_regressors.json"

# PIOP1 — rest + all tasks (for Strategy A validation)
aws s3 sync --no-sign-request s3://openneuro.org/ds002785 ./data/aomic/piop1 \
  --exclude "*" \
  --include "participants.tsv" \
  --include "derivatives/fmriprep/sub-*/func/*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz" \
  --include "derivatives/fmriprep/sub-*/func/*desc-confounds_regressors.tsv" \
  --include "derivatives/fmriprep/sub-*/func/*desc-confounds_regressors.json"

# PIOP2 — same as PIOP1
aws s3 sync --no-sign-request s3://openneuro.org/ds002790 ./data/aomic/piop2 \
  --exclude "*" \
  --include "participants.tsv" \
  --include "derivatives/fmriprep/sub-*/func/*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz" \
  --include "derivatives/fmriprep/sub-*/func/*desc-confounds_regressors.tsv" \
  --include "derivatives/fmriprep/sub-*/func/*desc-confounds_regressors.json"
```

**저장 공간 추정**: derivatives만 선택적 다운로드 시 ~50-100GB (전체 355GB 대비 대폭 절감).

### Phase 2b: ABIDE (보강)

**이유**: nilearn으로 즉시 접근 가능, pre-extracted ROI timeseries 제공.

```
ABIDE PCP HC (573) → CC200 ROI timeseries 직접 사용
```

작업:
1. `fetch_abide_pcp(DX_GROUP=2, pipeline='cpac')` → rois_cc200 다운로드
2. CC200 → Schaefer 100/200 매핑 (or CC200을 독립 atlas로 별도 실험)
3. QC (age ≥ 18 필터, quality-checked sites)

### Phase 2c: 기존 datasets (이미 완료/부분 완료)

```
ds000030 (138 HC, Phase 1) + ds000243 (50, pilot) = ~188
```

---

## 3. CONSORT Flow Diagram

```
┌─────────────────────────────────────────────────┐
│  IDENTIFICATION                                  │
│                                                  │
│  Datasets screened: OpenNeuro + ABIDE + nilearn  │
│  Total subjects identified: ~2,500+              │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │  EXCLUSION (Dataset-level)  │
        ├─────────────────────────────┤
        │ • No resting-state fMRI     │
        │ • No usable derivatives     │
        │ • Non-BIDS / inaccessible   │
        └──────────────┬──────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  ELIGIBILITY (Subject-level screening)           │
│                                                  │
│  Candidate HC subjects: ~2,233                   │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │  EXCLUSION (Subject-level)  │
        ├─────────────────────────────┤
        │ • Age < 18                  │
        │ • Non-HC diagnosis          │
        │ • Scan duration < 5 min     │
        │ • Excessive motion          │
        │   (mean FD > 0.5mm)         │
        │ • ROI coverage < 90%        │
        │ • fMRIPrep QC failure       │
        └──────────────┬──────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  INCLUSION                                       │
│                                                  │
│  Final HC pool: N = ??? (target: max)            │
│                                                  │
│  ┌─ AOMIC:  ~1,370 (est. after QC: ~1,100+)     │
│  ├─ ABIDE:  ~573   (est. after QC: ~400+)       │
│  ├─ ds000030: ~138  (est. after QC: ~127)        │
│  └─ ds000243: ~50   (est. after QC: ~40)         │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  PROCESSING                                      │
│                                                  │
│  1. Confounds regression                         │
│     (fMRIPrep confounds or custom pipeline)      │
│  2. Schaefer 100 / 200 ROI extraction            │
│  3. QC metrics export                            │
│     (FD, tSNR, coverage per subject)             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  dFC TEMPLATE CONSTRUCTION                       │
│                                                  │
│  1. Sliding window FC (w=30-60s, stride=1-2 TR) │
│  2. Fisher-Z → vectorize upper triangle          │
│  3. k-means clustering (k = 4-6)                │
│  4. Cluster centroids → expert templates         │
│  5. Per-window cluster labels → OS task labels   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  ANALYSIS                                        │
│                                                  │
│  • Template bank: k templates × {100,200} nodes  │
│  • MoBSE training: dFC-state classification      │
│    + ETTh1 forecasting (dual-task)               │
│  • Ablation matrix: atlas, sparsity, routing,    │
│    template-prior, k                             │
└─────────────────────────────────────────────────┘
```

---

## 4. TR Heterogeneity Management

| Dataset | TR (s) | 해결 방안 |
|---------|--------|----------|
| AOMIC (all) | 0.75 | 기준 TR |
| ds000030 | 2.0 | window_sec 기반 통일 or 별도 분석 |
| ds000243 | varies | NIfTI 헤더 자동 감지 |
| ABIDE | 1.0-3.0 | site별 상이, window_sec 기반 통일 |

**권장**: `window_sec = 45` (초 기반) → `window_len = int(window_sec / tr)` per subject.

---

## 5. Immediate Next Steps

1. AOMIC-ID1000 (ds003097) fMRIPrep derivatives 구조 확인 및 pilot 다운로드
2. Schaefer ROI extraction pipeline 테스트 (기존 ds000243 코드 재활용)
3. dFC sliding window + k-means clustering 모듈 구현
4. CONSORT flow 각 단계의 실제 N 채우기
5. 전체 Phase 2 실행 계획 수립
