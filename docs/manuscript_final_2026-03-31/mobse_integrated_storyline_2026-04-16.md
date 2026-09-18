# MoBSE Integrated Manuscript Storyline (2026-04-16)

Phase 1 (Yeo-7/ABIDE, 2026-03-31 lock) + Phase 2 (dFC/PIOP1, 2026-04-16) 통합 논문 구조.

---

## 0. One-Line Thesis (Updated)

> MoBSE routes fMRI time-series through brain-state expert sub-networks — first validated with atlas-based (Yeo-7) templates on resting-state data, then extended to data-driven (dFC centroid) templates that reveal task-specific expert routing aligned with cognitive demand.

Phase 1의 "interpretable scaffold" 주장을 Phase 2가 **data-driven 확장 + 인지적 의미 부여**로 강화.

---

## 1. Storyline Evolution

### Phase 1 Claim (유지)
- Real rs-fMRI + Yeo-7 base + MoBSE experts → 시뮬레이션 대비 분류 우위 + 해석 가능한 라우팅
- 제약: atlas-based (Yeo-7 7개 고정 네트워크), resting-state only, binary OS

### Phase 2 Extension (신규)
- dFC centroid templates (data-driven) → atlas 의존성 제거
- Multi-task routing (6 cognitive tasks) → 인지적 부하와 라우팅의 정량적 대응
- Expert collapse 진단/수정 → MoE 학습 안정성에 대한 방법론적 기여

### 논문 내 위치: Two-stage validation narrative
1. **Stage A**: Atlas-based template이 MoBSE routing의 기본 해석 좌표를 제공함을 보임 (Phase 1)
2. **Stage B**: Data-driven template으로 전환해도 routing이 task의 인지적 특성과 일치함을 보임 (Phase 2)
3. **Bridge**: atlas → data-driven 전환이 해석 가능성을 유지하면서 유연성을 확보함

---

## 2. Updated Paper Structure

### Introduction
- Problem: rs-fMRI의 복잡성과 해석 간극 (동일)
- Position (확장): 고정 atlas scaffold (Yeo-7)뿐 아니라, data-driven brain-state templates (dFC centroids)도 MoBSE routing의 유효한 prior
- Contribution:
  1. MoBSE framework: brain-state expert routing for fMRI (Phase 1)
  2. Data-driven template bank via dFC clustering (Phase 2)
  3. Task-specific routing → cognitive demand mapping (Phase 2)
  4. Expert collapse 진단 및 differentiable masking 해결 (Phase 2, methodological)

### Methods
- **2.1 Data**
  - ABIDE control adults (n=143) + simulation (n=150) — Phase 1
  - AOMIC PIOP1 (N=216, 6 tasks, Schaefer-100) — Phase 2
  - Dataset 선택 근거: resting-state → multi-task cognitive paradigm
- **2.2 Brain-state templates**
  - 2.2.1 Atlas-based: Yeo-7 network parcellation (Phase 1)
  - 2.2.2 Data-driven: sliding-window dFC → PCA → k-means centroids (Phase 2)
    - Window length=64 TRs, stride=16, PCA→k-means (k=3)
    - Allen et al. 2014 framework 적용
- **2.3 MoBSE architecture** (통합)
  - Gate network, expert bank, graph forward (동일 framework)
  - Routing mode: soft/hard, top-k pruning
  - **Differentiable masking**: `weights * mask` (expert collapse 해결, Phase 2 기여)
  - Gate temperature scaling, entropy-based load balancing loss
- **2.4 Training protocol**
  - Phase 1: dual-task (OS + ETTh1), matched compute
  - Phase 2: OS classification (6 brain-state classes), balance loss, anti-overfitting config
- **2.5 Evaluation**
  - Classification metrics: accuracy, F1-macro
  - Routing metrics: entropy, per-task expert usage distribution
  - Compute metrics: FLOPs, latency

### Results

**R1. Atlas-based MoBSE outperforms simulation under matched compute** (Phase 1, 유지)
- ABIDE vs simulation: OS acc 1.000 vs 0.132, matched FLOPs
- Fig2, Fig3, Table 1 (기존 lock)

**R2. Routing interpretation on atlas-based templates** (Phase 1, 유지)
- Routing entropy: ABIDE 0.610 vs SIM 0.669
- Expert usage distribution across Yeo-7 networks
- Fig5 (기존 lock)

**R3. Data-driven dFC templates capture brain-state structure** (Phase 2, 신규)
- PIOP1 dFC clustering: k=3 centroids, cosine similarity 0.784–0.905
- Centroid-based window labeling: 15,817 windows from 6 tasks
- Fig (신규): dFC centroid heatmaps (기존 figures/fig2 활용)

**R4. Task-specific expert routing under dFC templates** (Phase 2, 핵심 신규)
- Exp C (routing_k=2, balance=1.0, temp=3.0): task-specific routing 확인
- High cognitive demand (emomatching 50.1%, workingmemory 46.4%) → dfc_2
- Low cognitive demand (rest 37.3%, anticipation 36.8%) → dfc_1
- Routing entropy = 0.693 (healthy distribution, not collapsed)
- Fig (신규): task-specific routing heatmap (기존 figures/fig5 활용)
- Table (신규): per-task routing weights (기존 Table 3 활용)

**R5. Expert collapse diagnosis and differentiable masking fix** (Phase 2, methodological)
- Collapse 현상: `scatter_(values)` → gradient disconnection → single expert dominance (87–99%)
- Fix: `weights * mask` → gradient flow 복원
- Balance loss α=1.0 with k=2: task differentiation 유지
- Balance loss α=1.0 with k=3: over-uniformity (routing entropy = log(3))
- Fig (신규): balance loss gradient diagnostic, collapse vs fixed routing comparison (figures/fig6, fig7)

**R6. Supporting context — ETTh1 and reproducibility** (Phase 1, 유지/축소)
- ETTh1 dual-task context, ETT-family extension, 10-seed reproducibility
- Fig4, Fig6, Table 2–3 (기존 lock)

**R7. Robustness** (Phase 1, 유지)
- Strict subject-level split, nuisance sensitivity
- Fig7, Fig8 (기존 lock)

### Discussion

**Why two-stage validation matters**
- Atlas-based (Phase 1): interpretability through canonical coordinates → "model reads neuroscience"
- Data-driven (Phase 2): generalizability without atlas dependency → "data writes neuroscience"
- 양방향 일관성: 두 template source 모두에서 routing이 의미 있는 분화를 보임

**Task-specific routing as cognitive demand marker**
- dfc_1 ↔ low-demand (rest, anticipation): default-mode-like state
- dfc_2 ↔ high-demand (emomatching, workingmemory): task-positive-like state
- MoBSE routing이 사전 정의 없이 cognitive load를 포착 → 해석 가능한 data-driven 모델의 가능성

**Expert collapse as a general MoE lesson**
- `scatter_(values)` gradient bug는 PyTorch MoE 구현 일반에서 발생 가능
- Differentiable masking + entropy-based balance loss → 범용 해결책

**Limitations** (확장)
- Phase 1: window-level split risk, state-generation asymmetry (유지)
- Phase 2: single-dataset (PIOP1) 제한, balance weight sensitivity, centroid 수 선택의 임의성
- 공통: preprocessing dependency, clinical generalization 미검증

### Conclusion
MoBSE는 atlas-based와 data-driven brain-state templates 모두에서 해석 가능한 expert routing을 학습하며, 특히 dFC centroid 기반 routing이 task의 인지적 부하와 일치하는 패턴을 보인다. 이는 graph neural network 기반 fMRI 모델링에서 전문가 분화가 neuroscience-level 해석 가능성을 제공할 수 있음을 시사한다.

---

## 3. Figure Plan (Updated)

### Phase 1 Figures (유지)
| Fig | Content | Source |
|-----|---------|--------|
| F1 | Framework overview | 기존 lock |
| F2 | ABIDE vs SIM OS benchmark | 기존 lock |
| F3 | Compute parity (FLOPs/latency) | 기존 lock |
| F4 | ETTh1 auxiliary panel | 기존 lock |
| F5 | Yeo-7 routing usage by network | 기존 lock |
| F6 | ETT-family extension summary | 기존 lock |

### Phase 2 Figures (신규)
| Fig | Content | Source |
|-----|---------|--------|
| F7 | dFC centroid template bank (k=3) | figures/fig5_template_bank.png |
| F8 | Training curves — Exp C vs baseline | figures/fig1_training_curves.png |
| F9 | Task-specific routing heatmap (Exp C) | figures/fig3_task_routing_expc.png |
| F10 | Routing entropy: collapsed vs fixed vs over-uniform | figures/fig4_routing_entropy.png |
| F11 | Template similarity & routing heatmaps | figures/fig2_routing_heatmaps.png, fig6_template_similarity.png |
| F12 | Summary panel (Exp A–D comparison) | figures/fig7_summary_panel.png |

### Phase 1 Figures (robustness, 유지)
| Fig | Content | Source |
|-----|---------|--------|
| F13 | Strict subject-level split | 기존 F7 lock |
| F14 | Nuisance sensitivity | 기존 F8 lock |

### Tables
| Table | Content | Status |
|-------|---------|--------|
| T1 | ABIDE vs SIM main metrics | 기존 lock |
| T2 | ETTh1 storyline 4-run summary (10-seed) | 기존 lock |
| T3 | ETT-family extension (10-seed) | 기존 lock |
| T4 | Phase 2 experimental conditions (Exp A–E) | 신규 (from Report Table 1) |
| T5 | Phase 2 performance comparison | 신규 (from Report Table 2) |
| T6 | Task-specific routing weights (Exp C) | 신규 (from Report Table 3) |

---

## 4. Phase 1 → Phase 2 Bridging Logic

### Q: Atlas-based (Yeo-7)에서 data-driven (dFC)으로 전환하는 논리적 근거?

**Answer in manuscript**:
1. Phase 1에서 atlas-based template이 MoBSE의 해석 가능한 routing을 가능하게 함을 보였다.
2. 그러나 Yeo-7은 resting-state 기반 고정 분류 → task-evoked 상태를 직접 반영하지 못하는 한계.
3. dFC clustering은 task-specific temporal dynamics을 포착 → template이 관찰된 뇌 상태 변화를 직접 반영.
4. Phase 2 결과가 Phase 1 주장을 data-driven으로 **확장**하고 **강화**함:
   - atlas → data-driven 전환에도 routing의 해석 가능성이 유지됨
   - multi-task setting에서 routing이 cognitive demand와 일치함
   - 이는 Phase 1의 "MoBSE routing은 뇌의 기능적 구조를 반영한다"는 주장의 더 강한 증거

### Q: Phase 1과 Phase 2 데이터셋이 다른 이유?

**Answer in manuscript**:
- Phase 1 (ABIDE): resting-state, 대규모 공개 데이터, binary OS benchmark에 적합
- Phase 2 (AOMIC PIOP1): multi-task cognitive paradigm (6 tasks), task-specific routing 검증에 적합
- 두 데이터셋이 complementary: resting-state에서의 baseline 성능 + task-evoked에서의 routing 해석
- 향후: ABIDE에서 Yeo-7 vs dFC 직접 비교, AOMIC-ID1000 (N=928) 독립 코호트 replication

### Q: Expert collapse는 Phase 1에서도 존재했나?

**Answer in manuscript**:
- Phase 1에서는 `routing_k = num_experts (=7)`로 pruning 없이 운영 → collapse 경로가 다름
- Phase 2에서 top-k pruning (k < num_experts) 도입 시 collapse 발생
- Differentiable masking fix는 top-k routing을 사용하는 모든 MoE에 일반 적용 가능
- 이는 method section의 독립 기여: "Stabilizing MoE routing via differentiable top-k masking"

---

## 5. Submission Strategy Options

### Option A: Single unified paper
- Title: "Mixture of Brain-State Experts: Interpretable Expert Routing from Atlas-Based to Data-Driven Brain Templates"
- 장점: Phase 1+2 모두 하나의 coherent narrative
- 단점: 분량이 많고, 두 데이터셋/방법이 혼재
- 적합 저널: NeuroImage, Human Brain Mapping

### Option B: Phase 1 paper + Phase 2 follow-up
- Paper 1: Atlas-based MoBSE (Phase 1 lock 그대로 제출)
- Paper 2: dFC extension + expert collapse fix (Phase 2 단독)
- 장점: 각각 focused, 출판 속도 빠름
- 단점: Phase 2 단독으로는 Phase 1 컨텍스트 필요

### Option C: Phase 1 paper with Phase 2 as "extended results"
- Main: Phase 1 (R1–R3, R6–R7) → core claim
- Extended: Phase 2 (R4–R5) → "Extended Validation" section or supplementary
- 장점: main claim이 간결하고, Phase 2가 보강 증거
- 단점: Phase 2의 task-specific routing이 supplementary로 밀릴 수 있음

### 권장: Option A (single paper)
- Task-specific routing (Phase 2)이 논문의 가장 강력한 결과이므로 main text에 포함해야 함
- Phase 1의 atlas-based validation이 Phase 2의 data-driven 결과를 정당화하는 논리적 기반
- Expert collapse fix는 Methods의 독립 subsection으로 충분

---

## 6. Remaining Gaps for Submission

| Priority | Gap | Action needed |
|----------|-----|---------------|
| **P1** | Balance weight sensitivity | α sweep: {0.01, 0.05, 0.1, 0.5} × k ∈ {2,3} |
| **P1** | PIOP1 internal validation | Subject-level 5-fold CV 또는 train/test split (60/40) |
| **P1** | ABIDE dFC replication | 기존 Phase 1 데이터에서 dFC centroid → routing 검증 (Phase 1↔2 bridge) |
| **P1** | UCLA CNP (ds000030) cross-site replication | nilearn selective download → task BOLD derivatives 확인 → dFC → routing. 다른 site(UCLA), rest+6 tasks, N~272 |
| **P2** | Phase 1–2 직접 비교 | ABIDE에서 Yeo-7 vs dFC template 비교 (동일 데이터) |
| **P2** | Brain-state network mapping | dFC centroids → DMN/FPN/DAN spatial overlap 정량화 |
| **P3** | Learnable templates | `use_template_prior=False` 비교 |

**UCLA CNP 다운로드 전 확인 필요**:
```python
from nilearn.datasets import fetch_ds000030_urls
urls_path, urls = fetch_ds000030_urls()
deriv_urls = [u for u in urls if 'derivatives' in u and 'fmriprep' in u]
# task BOLD가 fMRIPrep derivatives에 포함되는지 확인
task_bolds = [u for u in deriv_urls if 'task-' in u and '_bold' in u]
```

**제외된 데이터셋**:
- PIOP2 (ds002790): 다운로드 2일, 스캔 시간 짧아 dFC window 수 부족, 같은 코호트 wave라 독립 검증 가치 낮음
- HCP: DUA 승인 필요, data access 불확실
- AOMIC-ID1000 (ds003097): rest scan 없음 → cognitive demand gradient의 low-demand anchor 부재

---

## 7. Key Claims Summary (submission-ready)

1. **MoBSE routes fMRI through brain-state experts that outperform simulation controls under matched compute.** (Phase 1, R1)
2. **Expert routing produces neuroscience-interpretable patterns on canonical atlas coordinates.** (Phase 1, R2)
3. **Data-driven dFC centroid templates eliminate atlas dependency while maintaining routing interpretability.** (Phase 2, R3)
4. **Task-specific routing aligns with cognitive demand: high-load tasks preferentially route to distinct expert sub-networks.** (Phase 2, R4 — strongest new result)
5. **Differentiable top-k masking resolves expert collapse in MoE routing.** (Phase 2, R5 — methodological contribution)
6. **Results replicate across 10-seed runs and robustness checks.** (Phase 1, R6–R7)
