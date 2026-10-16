# R2T 탐색 계획 v1 — rest 상태 연결 prior 로 짧고 불완전한 task 관측 복원 · 2026-10-16

> **무엇인가**: 새 **탐색** 가설의 계획서 (결정 82). 승인 범위는 **계획 수립까지**다 — 실험 실행 · 학습 · 대규모 처리 · 다운로드 ·
> 기존 결과 덮어쓰기는 하지 않았고, 이 문서의 단계는 각각 별도 승인 뒤에만 실행한다.
> **무엇이 아닌가**: I3 · H1 · H2 의 재해석이 아니다. 그 결과는 음성 그대로이고 (I3 마감본 · 결정 75 · 81), PIOP2 의 P1 확증은
> 보존하되 이 가설의 근거로 쓰지 않는다. 표기: **[측정]** 은 명령으로 잰 값, **[추정]** 은 재지 않은 값, **[제안]** 은 이 계획의 설계 선택이다.

## 0. 연구 결과와 새 제안의 구분

| 구분 | 내용 | 출처 |
|---|---|---|
| 기존 결과 (바꾸지 않음) | v1 · v3 · I3 에서 H1 · H2 지지 근거 없음. PIOP2 P1 · P2 확증 (판정 그대로), P1 이득은 블록 시계열 사용에서 오는 것으로 보이며 그래프 고유 이득 근거 없음 | handoff §11.43 · §11.48 · §11.50 |
| 기존 결과에서 이 계획이 물려받는 **사실** | ① PIOP 과제는 조건 순서가 전원 같아 조건과 블록 위치가 겹친다. ② blockz 는 시계열 모양을 남긴다. ③ 기존 graph bank 는 양수 상위 20 % 로 자른 인접행렬이다 (`mobse/v2/templates.py` `sparsify_positive`) | I3 마감본 §7 · §10, 코드 |
| 새 제안 (이 문서) | R2T 가설 · 설계 · 판정 규칙 · 단계 계획. **결과 없음** | — |

## 1. 질문과 가설

**질문**: training-rest 에서 얻은 상태별 연결 구조 (공분산 prior) 가, 짧고 일부 ROI 가 빠진 task 관측에서 **같은 입력을 쓰는 강한 선형
모델**보다 빠진 ROI 신호를 더 잘 예측하는가.

| # | 가설 | 성격 |
|---|---|---|
| **R2T-H (주)** | 관측 ROI 만으로 창마다 가중치를 정하는 K>1 상태 혼합 Gaussian prior 의 조건부 예측이, 같은 training-rest · 같은 관측 신호를 받는 기준선 중 inner validation 으로 고른 최선보다 가린 ROI 예측오차가 작다 | 탐색 |
| 대조 C-reg | 이득이 있어도 **고정 가중치 (1/K) 혼합 ≈ 적응 혼합**이면 상태 추론이 아니라 regularization · 평균화 효과다 | 대조 |
| 대조 C-sp | 거리만으로 만든 공분산 · 가까운 관측 ROI 평균이 비슷하면 공간 인접성 복원이다 | 대조 |
| 대조 C-tm | 창의 앞뒤 frame 을 쓰는 lag ridge 가 따라잡으면 시간 문맥 효과다 | 대조 |
| 대조 C-ev | training 피험자의 과제 평균 시간경과 (evoked mean) 가 대부분을 설명하거나, 그것을 뺀 잔차에서 이득이 사라지면 과제 유발 평균 복원이다 | 대조 |

**신규성 점검**: dFC + MoE (dFCExpert, MoRE-Brain), covariance shrinkage, Gaussian 상태 혼합은 기존 기법이다. 더 가까운 선행연구는
**rest FC 로 task 활성을 예측하는 연구**다:
- Cole et al. 2016, Nat Neurosci, activity flow: 보지 않은 영역의 task 활성을 rest FC 로 예측했다.
- Tavor et al. 2016, Science 352:216: rest 로 개인 task 지도를 예측했다.

이 계획의 K=1 prior 는 activity flow 와 같은 계열이다. 그래서 기여는 "rest → task 예측" 자체가 아니라 다음 둘로 한정한다:
- 짧은 창 (15 frame) · ROI 결손이라는 조건에서 **창 단위 상태 추론 (K>1)** 이 K=1 · 강한 선형 기준선을 넘는지.
- 넘는다면 어떤 창 길이 · 결손 비율 · 결손 형태에서 넘는지.

dFCExpert 링크 (PMC11702678) 는 2024-12 bioRxiv preprint 판으로 보인다. 최종판은 IEEE TMI 45(3) (PMC12828913, 문헌 검토 R6) 이고, 인용은 최종판으로 한다 [확인 필요].

**주장하지 않는 것**: 뇌 상태 · 인지기전 · 조건 인식. 신호 복원 이득은 복원 이득일 뿐이다. 조건과 블록 위치가 겹치는 PIOP 과제에서는 조건별
차이를 기술값으로만 적는다.

## 2. 모델 (1 순위 설계만)

입력은 test 창의 관측 ROI 신호 `x_O` (L frame × |O|) 이고, 출력은 같은 frame 의 가린 ROI 신호 `x_M` 이다. **가린 ROI 는 test 피험자의 그
task run 어디에서도 모델에 주지 않는다.**

| 칸 | 내용 | 정보 접근 |
|---|---|---|
| **MIX-a (주)** | training-rest 15 frame 창을 단위로 EM 한 K 성분 Gaussian 혼합 (성분마다 Ledoit-Wolf shrinkage 로 양의 정부호 공분산). test 창 가중치 = 관측 `x_O` 의 주변 우도로 계산한 사후확률 (온도 τ, §4). 예측 = 성분별 조건부 평균 `μ_M + Σ_MO Σ_OO⁻¹ (x_O − μ_O)` 의 가중합 | training-rest + `x_O` |
| MIX-f | 같은 성분, 가중치 1/K 고정 | 같음 |
| G1-LW · G1-OAS | K=1 단일 공분산 (Ledoit-Wolf · OAS) 조건부 평균 — activity flow 계열 | 같음 |
| RIDGE | training-rest frame 에서 `x_O → x_M` ridge (λ inner 선택) | 같음 |
| RRR | reduced-rank ridge (rank · λ inner 선택) | 같음 |
| LAG-RIDGE | `x_O(t−1), x_O(t), x_O(t+1)` → `x_M(t)` ridge (C-tm 대조, 창 안 frame 만) | 같음 |
| DIST | 공분산 = ROI 중심 거리의 함수 (training-rest 로 맞춤) 의 조건부 평균 · 가까운 관측 ROI k 개 평균 (C-sp 대조) | 같음 + 좌표 |
| EVOKED | training 피험자 task run 의 ROI 별 평균 시간경과 (C-ev 대조) | **training-task** (정보 접근이 다름 — 순위에 넣지 않음) |
| ORACLE-w | 가린 정답으로 혼합 가중치를 고른 상한 | 상한 진단만 — 실현 성능 아님 |

- 기존 thresholded adjacency 를 공분산으로 쓰지 않는다. GNN · gate · 학습형 router 는 이 단계에 없다.
- 모든 공분산 · 평균 · ridge 는 **그 fold 의 training 피험자 rest 만**으로 추정한다. test 피험자의 rest · task, 가린 ROI 는 추정에 들어가지 않는다.
- 추정 안정성 [측정 · 추정 구분]:
  - 현재 rest 창은 사람당 60 s × 4 = 2 s 격자 120 frame 이다 [측정: `rest_win` 30 × 100 × 4].
  - training 100 명이면 12,000 frame 으로 100 × 100 공분산 하나에 충분하다. K=4 에서도 성분당 약 3,000 frame [추정] 이다.
  - 그래도 성분마다 shrinkage 를 의무로 둔다. 조건수 · shrinkage 강도를 기록한다.
  - 15 frame test 창으로는 공분산을 **추정하지 않는다** — 창 공분산은 rank ≤ 14 다. 창은 prior 아래의 우도로만 쓴다.

## 3. 자료 · 분할 (탐색 · 타당성 평가용)

| 항목 | 값 [제안] |
|---|---|
| 개발 자료 | PIOP1 (ds002785) **main 126 명**, 기존 outer 5 fold (`folds.json`, split_hash `ace5f4a4…`) 그대로 — fold 마다 training 약 100 명 [추정]. inner 선택 (K · τ · λ · rank · shrinkage) 은 training 안 inner fold 0 |
| pilot | PIOP1 pilot 31 명 — 1 단계 판정에 넣지 않고 구현 점검 · 분산 추정 (검정력) 에만 씀 |
| task | **emomatching** (TR 2.0, 135 frame) 주. workingmemory (162 frame) 는 보조 — 재추출 필요 |
| rest | 기존 `derivatives_v3` rest 창 (2 s 격자, anti-aliasing resample) |
| PIOP2 | **확증 자료 아님** (P1 · P2 확증에 이미 씀). 1 단계가 성공일 때만 잠근 설정의 **탐색 재현**으로 한 번 |

- 같은 피험자의 창 · 블록은 train 과 test 로 갈리지 않는다 (피험자 단위 분할).
- test 창은 **겹치지 않는** 연속 L frame (frame 0 부터) 이다. 인접 창의 자기상관은 피험자 단위 집계 · bootstrap 으로 다룬다. 창을 독립 표본으로 세지 않는다.

## 4. 사전 정의 (잠금 전 고정할 값)

| 항목 | 주 분석 [제안] | 보조 (판정에 쓰지 않음) |
|---|---|---|
| 창 길이 L | **15 frame (30 s)** | 8 · 30 · run 전체 |
| 가릴 ROI | **20 % (20 ROI), 반구 균형 (10 + 10)**, seed 고정 mask 20 벌을 모든 피험자 · 방법에 공통 | 10 % · 40 %, **Yeo-7 network 하나 통째** (Schaefer-100 7Networks 라벨 사용 — 공간 인접 누수 축소) |
| 관측 ROI | 나머지 80 | — |
| 주지표 | **가린 ROI 정규화 예측오차 NMSE** — 피험자마다 창 · mask · ROI · frame 평균 | Gaussian predictive log-likelihood (모든 방법에 training-rest 잔차 공분산을 붙여 같은 형식으로) · 창별 상관 (크기 불변) |
| 주 대조 | Δ = NMSE(기준선 최선) − NMSE(MIX-a), 피험자 단위. 기준선 최선은 G1-LW · G1-OAS · RIDGE · RRR 중 **inner validation** 으로 고름 (test 를 보지 않음) | MIX-a − MIX-f (C-reg) · − LAG-RIDGE · − DIST · EVOKED 를 뺀 잔차에서의 Δ · K 별 · τ 별 |
| K | inner 로 {2, 3, 4} 중 선택 | K 고정 판 |
| τ (혼합 가중치 온도) | inner 로 선택 — frame 자기상관 때문에 frame 독립 우도는 사후확률을 과신한다 | τ = 1 판 |
| 집계 · CI | 피험자 단위 (126 명), 피험자 bootstrap 10,000 (seed 고정), 95 % | — |
| 최소 관심 효과 δ | **NMSE 0.01** (가린 신호 분산의 1 %) — 문헌 기준이 아닌 설계 선택. pilot 의 Δ 분산으로 검정력을 잰 뒤 잠금 | — |

**단위계와 누수**:
- 현재 추출은 run 단위 ROI z-score (`mobse/v2/extract.py` `zscore_rois`) 다.
  - 관측 입력의 z-score 는 창 밖 frame 을 쓴다. 다만 모든 방법이 같은 입력을 받으므로 방법 간 차이 Δ 에는 같은 조건이다.
  - 가린 ROI 의 z-score 는 **채점용 정답에만** 쓰고 모델에는 들어가지 않는다.
  - 그래도 절대 복원 수준은 과대일 수 있다.
- **보조 단위계 [제안]**: run 평균 원 강도 기준 percent signal change 로 재추출해 같은 분석을 반복한다. 재추출은 별도 승인이 필요하다. 참고로 PIOP2 189 명 추출이 h197 에서 304 s 였다 [측정].
- nuisance 처리 (움직임 · aCompCor · spike · 대역 0.008–0.2 Hz) 는 잠긴 추출 상수 그대로 쓰며 결과를 보고 바꾸지 않는다.
- 금지: 전체 자료로 표준화 · PCA · 공분산을 맞추는 것. 가린 ROI 를 포함한 창 통계를 입력에 쓰는 것. I3 식 blockz 를 입력에 쓰는 것 (가린 ROI 의 창 평균 · 분산을 씀).

**graph 정렬 주장**: 1 순위 설계는 해부학적 정렬 특이성을 주장하지 않는다. 주장하려면 다음 비교를 보조로 넣는다:
- 정렬 공분산을 DIST (거리 의존 공분산) 와 비교한다.
- spin 회전 공분산 (`mobse/v3/templates.py` 의 spin · 좌표 재사용) 과 비교한다.
- 단순 ROI 순열은 너무 약한 null 이라 근거로 쓰지 않는다 (PIOP2 P2 의 교훈).

## 5. 판정 · 중단 규칙 (1 단계)

| 판정 | 조건 |
|---|---|
| **진행** | Δ 의 95 % 하한 > 0 이고 점추정 ≥ δ, 그리고 MIX-a − MIX-f 하한 > 0 (C-reg 배제), LAG-RIDGE · DIST 대비도 하한 > 0, EVOKED 를 뺀 잔차에서 Δ 부호 유지 |
| **중단 (K>1 확장 중지)** | MIX-a 가 G1 · RIDGE · 기준선 최선보다 못함 (Δ 상한 < 0), 또는 Δ 상한 < δ (δ 이상의 이득 배제) |
| **regularization 으로 해석** | MIX-f ≈ MIX-a (차이 CI 가 0 포함) 이면서 둘 다 기준선을 넘음 — "상태 전문가" 가 아니라 평균화 · shrinkage 효과로 적는다 |
| **공간 특이성 주장 폐기** | 정렬 공분산이 DIST · spin 보다 못함 |
| **불확실** | 그 밖. "이득 없음" 이나 "동등" 이라고 쓰지 않는다 — 동등성은 사전에 정한 동등성 구간의 양쪽 한계가 모두 구간 안일 때만 |

- 판정은 한 번 · 주 분석 하나다. 보조 결과는 판정을 바꾸지 않는다.
- ORACLE-w 는 "상태 가중치를 완벽히 맞추면 얼마까지" 의 상한일 뿐이다.

## 6. 단계 계획 · 자원

| 단계 | 내용 | 자료 | CPU/GPU · 시간 | 승인 |
|---|---|---|---|---|
| 0 구현 · 검증 | 모델 · 기준선 · 분석 코드, 합성자료 시험 (참 K=3 이면 MIX 가 이기고 참 K=1 이면 못 이김), 누수 시험 (가린 ROI · test 정보가 추정 함수에 들어가지 않음을 assert), 잠금 초안 | 합성 + pilot 31 (분산 · 안정성만) | CPU, 코드 1–2 일 · 계산 수 분 [추정] | 필요 |
| **1 판별 실험 (권고 최소 실험)** | §4 주 분석 + 대조 칸 | PIOP1 main 126, emomatching, 기존 추출 | CPU 단독. 조건부 예측은 닫힌 해라 126 명 × 9 창 × 20 mask × 약 10 방법 ≈ 23 만 예측 → 수 분–30 분 [추정]. GPU 불필요 | 필요 (잠금 뒤) |
| 2 조건부 확장 | 1 이 "진행" 일 때만: 보조 단위계 재추출 · workingmemory · 창 길이 곡선 · PIOP2 탐색 재현 | PIOP1 · PIOP2 | 재추출 수 분 [측정 근거: 189 명 304 s], 분석 1 시간 미만 [추정] | 필요 |
| 3 독립 확증 | 설정을 잠근 뒤 새 자료에서 한 번 | §7 후보 | 자료 획득 · 전처리가 지배적 [추정 불가 — 자료 결정 뒤] | 자료 획득 · 실행 각각 |

참고 측정: 진단 logistic 1 회 (126 명 5 fold) 2.2 s, I3 본 실행 270 fit 70 분 (Mac MPS) [측정]. R2T 1 단계는 학습형 신경망이 없어 그보다 훨씬 작다 [추정].

## 7. 독립 검증 요건 · 후보 (조사 수준, 획득하지 않음)

**요건**:
- 같은 피험자의 rest 와 task 가 있고, 이 가설로 결과를 본 적이 없는 자료.
- TR ≤ 약 2 s, 100 명 이상 (1 단계 분산으로 다시 계산), MNI 등록 가능 (Schaefer-100 적용).
- 접근 조건을 이 연구실이 충족할 것.
- PIOP1 · PIOP2 는 둘 다 결과를 보고 설계를 바꾼 자료라 해당하지 않는다.

| 후보 | rest · task | 접근 | 주의 |
|---|---|---|---|
| HCP Young Adult (S1200) | rest + 7 task, 약 1,200 명 | Open Access Data Use Terms 수락 (ConnectomeDB) | CLAUDE.md 는 "DUA 필요 · 접근 불확실" 로 제외해 둠 → 기관 판단 필요. 다른 장비라 진짜 교차 자료 |
| Cam-CAN | rest + 영화 + 감각운동 task, 약 650 명 (18–88 세) | 온라인 자료 사용 동의 · 신청 | 나이 폭이 넓음. task 가 단순 |
| ds000030 (UCLA CNP) | rest + bart · bht · pamenc · pamret · scap · stopsignal · taskswitch (저장소 `data/ds000030/raw_fmriprep` 에 있음 [측정]) | 공개, 이미 보유 | legacy 전이 실험 (proxy label) 에 쓴 적 있음 — 이 가설의 결과는 본 적 없으나 노출 이력 표기. 환자군 포함. legacy 파생 시계열은 신뢰하지 않고 재추출 |
| MSC (ds000224) | 10 명, 사람당 rest 약 5 h · task 약 6 h | 공개 (OpenNeuro) | 집단 확증에는 작음 — **2 순위 개인화** 용 |
| AOMIC ID1000 | rest 없음 | — | 해당 없음 (기존 제외 사유) |

## 8. 2 · 3 순위 (지금 실행 계획 없음)

- **2 순위 개인화** (1 단계가 "진행" 이고 사용자 결정이 있을 때만): label 없는 test 피험자 rest 로 작은 adapter (예: 집단 prior 쪽으로 shrink 한 개인 공분산 · 개인 혼합 가중치) 를 정하고, 본인 rest · 타인 rest · 집단 rest 를 비교한다.
  - 먼저 확인할 것: 정확한 paired rest–task 가용성. PIOP 적격은 세 task 모두를 요구하므로 사람마다 rest 가 있다 [측정: 적격 규칙]. 같은 세션인지는 [확인 필요].
  - 공정한 test-time calibration 범위: test 피험자 rest 는 모든 기준선에도 똑같이 준다.
- **3 순위 미래 예측 혼합**: 작은 선형 예측기들의 out-of-fold 오류가 서로 보완적인지 먼저 확인한다. 보완적일 때만 과거 frame 만으로 가중치를 정해 미래를 예측하는 혼합을 시험한다. oracle 선택은 상한 진단만.

## 9. 재사용 · 새로 만들 것

| 재사용 | 위치 |
|---|---|
| 추출 · nuisance · 대역 상수 · run z-score | `mobse/v2/extract.py`, `scripts/piop2_confirm/extract.py` (dataset 인자) |
| rest 창 (2 s 격자) | `mobse/v2/preprocess.py`, `derivatives_v3` · I3 `rest_win` |
| task 전체 시계열 · events | I3 `full_ts` (emomatching), `scripts/i3/core.py` 읽기 함수 |
| 분할 · cohort | `folds.json` (outer 5), `subjects.jsonl` |
| ROI 좌표 · spin | `mobse/v3/templates.py` `roi_centroids` · spin null |
| 피험자 bootstrap · 잠금 · 결정론 | `scripts/piop2_confirm/p2.py` `analyze` · `build_lock.py` 양식 |

새로 만들 것: `scripts/r2t/` (혼합 EM · shrinkage · 조건부 예측 · 기준선 · 분석), `tests/r2t/` (합성 · 누수 시험), 잠금 문서. 쓰지 않는 것: graph bank (`sparsify_positive`) · GNN · gate.

## 10. 사용자 결정 사항

1. 1 단계 (구현 · 합성 시험 · pilot 분산) 착수 여부.
2. 주 단위계: 기존 run z-score (권고 — 추가 처리 없음, Δ 는 방법 간 같은 조건) 와 PSC 재추출 중 무엇을 주로 할지.
3. δ = NMSE 0.01 과 주 mask (반구 균형 무작위 20 % 대 network 통째).
4. PIOP2 의 역할: 2 단계 탐색 재현 / 쓰지 않음.
5. 독립 자료 후보 중 접근 조사를 진행할 것 (HCP 의 DUA 판단 포함).

## 출처

- dFCExpert 최종판 (문헌 검토 R6): https://pmc.ncbi.nlm.nih.gov/articles/PMC12828913/ · 제시 링크 https://pmc.ncbi.nlm.nih.gov/articles/PMC11702678/ (preprint 판으로 보임 [확인 필요])
- MoRE-Brain: https://arxiv.org/abs/2505.15946 · AOMIC: https://www.nature.com/articles/s41597-021-00870-6
- Cole et al. 2016 activity flow: https://pmc.ncbi.nlm.nih.gov/articles/PMC5127712 · Tavor et al. 2016: https://ora.ox.ac.uk/objects/uuid:55087530-0595-463c-86a3-c54a4117b42b
- MSC: https://openfmri.org/dataset/ds000224/ · Cam-CAN: https://camcan-archive.mrc-cbu.cam.ac.uk/ · HCP 이용 조건: https://www.humanconnectome.org/study/hcp-young-adult/document/wu-minn-hcp-consortium-open-access-data-use-terms
