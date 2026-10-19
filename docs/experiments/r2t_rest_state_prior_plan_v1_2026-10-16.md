# R2T 탐색 계획 v1.3 — rest 상태 연결 prior 로 전처리된 task 신호의 가린 ROI 복원 (모델 단계) · 2026-10-16

> **무엇인가**: 새 **탐색** 가설의 계획서 (결정 82 · 86). 합성 자료 단계 0 만 수행됐다 (결정 83–85). **실제 자료 실행 · 학습 · 재추출 · 다운로드 · 기존 결과
> 덮어쓰기는 승인되지 않았다.** 실행 전 검토용 pilot 설계는 `docs/experiments/r2t_pilot_design_v1_2026-10-16.md` (1 페이지).
> **무엇이 아닌가**: I3 · H1 · H2 의 재해석이 아니다. 그 결과는 음성 그대로이고 (I3 마감본 · 결정 75 · 81), PIOP2 의 P1 확증은
> 보존하되 이 가설의 근거로 쓰지 않는다.
> **표기**:
> - **[측정]** — 명령으로 잰 값
> - **[추정]** — 재지 않은 값
> - **[제안]** — 사용자 결정 전의 설계 안. 확정값이 아니다
> - **[잠금 필수]** — 실행 전 잠금 문서에 고정해야 하는 값
>
> **개정 이력**: v1 → v1.1 (검토 6 건) → v1.1 마감 문구 → v1.2 (결정 85: 전처리 정보 범위 추적 · 주효과와 기전 대조 분리 · τ 선택 규칙) → **v1.3** (결정 86: 첫 목표를 모델 단계 복원 T1 로 확정 · 성공 정의 · 사전 판정 잠금 시점 · pilot 설계, §11). 이전 판 사본은 `.backup/` 에 있다.

## 0. 연구 결과와 새 제안의 구분

| 구분 | 내용 | 출처 |
|---|---|---|
| 기존 결과 (바꾸지 않음) | v1 · v3 · I3 에서 H1 · H2 지지 근거 없음. PIOP2 P1 · P2 확증 (판정 그대로), P1 이득은 블록 시계열 사용에서 오는 것으로 보이며 그래프 고유 이득 근거 없음 | handoff §11.43 · §11.48 · §11.50 |
| 물려받는 **사실** | ① PIOP 과제는 조건 순서가 전원 같아 조건과 블록 위치가 겹친다. ② blockz 는 시계열 모양을 남긴다. ③ 기존 graph bank 는 양수 상위 20 % 로 자른 인접행렬이다 (`mobse/v2/templates.py` `sparsify_positive`). ④ 기존 추출 (`mobse/v2/extract.py`) 은 run 전체로 nuisance (24 motion · aCompCor 5 · spike · DCT 대역) 를 동시 회귀하고 run 단위 ROI z-score 를 한다 | I3 마감본 §7 · §10, 코드 |
| 새 제안 (이 문서) | R2T 가설 · 설계 · 판정 규칙 · 단계 계획. **결과 없음** | — |

## 1. 질문과 가설

**질문**: training-rest 에서 얻은 상태별 연결 구조 (공분산 prior) 가, 짧고 일부 ROI 가 빠진 task 관측에서 **같은 입력을 쓰는 강한 선형
모델**보다 빠진 ROI 신호를 더 잘 예측하는가.

**첫 목표 (v1.3 확정, 결정 86)**: **전처리된 task 신호에서 일부 ROI 를 가리고 복원하는 모델 단계 예측 (T1, §2)**. 짧은 창은 모델 입력의 단위일 뿐이다.
- 주장하지 않는 것: 실제 짧은 촬영 · 부분 뇌 관측 · 실시간 복원. 기존 자료는 run 전체로 전처리됐으므로 이 범위 안에서만 쓴다.
- hidden ROI 신호가 전처리 경로에서 observed ROI 로 섞일 수 있는 지점은 §2.1 에서 따로 점검한다. 그 한계를 T2 · T3 주장이나 기존 MoBSE 주장과 섞지 않는다.

| # | 가설 | 성격 |
|---|---|---|
| **R2T-H (주)** | 관측 ROI 만으로 창마다 가중치를 정하는 K>1 상태 혼합 Gaussian prior (MIX-a) 의 조건부 예측이, 같은 정보를 받는 기준선 중 inner validation 으로 고른 최선 (BEST) 보다 가린 ROI 예측오차가 작다 | 탐색 |
| 기전 보조 1 — 비적응 혼합의 몫 | MIX-p (같은 성분 합친 단일 공분산) · MIX-f (1/K) 가 BEST 보다 낫다 (상태 추론 없이 얻는 몫. 기전은 이 대조로 정하지 않음) | 보조 (v1.2) |
| 기전 보조 2 — 적응 가중의 몫 | MIX-a 가 MIX-p · MIX-f 보다 낫다. MIX-f 는 약한 비교 대상일 수 있어 단독 근거로 쓰지 않음 | 보조 (v1.2) |
| 대조 C-sp · C-ev | 공간 인접성 (거리 공분산 · 가까운 ROI 평균) · 과제 유발 평균 (training task 평균 시간경과) 으로 설명되는지 | 해석 조건 (§5) |

시간 문맥 (창 안 앞뒤 frame) 은 대조가 아니라 **기준선 후보 (LAG-RIDGE)** 로 BEST 선택에 넣는다. 같은 정보를 쓰기 때문이다.

**신규성 점검**: dFC + MoE (dFCExpert, MoRE-Brain), covariance shrinkage, Gaussian 상태 혼합은 기존 기법이다. 더 가까운 선행연구는
**rest FC 로 task 활성을 예측하는 연구**다:
- Cole et al. 2016, Nat Neurosci, activity flow: 보지 않은 영역의 task 활성을 rest FC 로 예측했다.
- Tavor et al. 2016, Science 352:216: rest 로 개인 task 지도를 예측했다.

이 계획의 K=1 prior 는 activity flow 계열이다. 그래서 기여는 다음 둘로 한정한다:
- 짧은 창 · ROI 결손에서 **창 단위 상태 추론 (K>1)** 이 K=1 · 강한 선형 기준선을 넘는지.
- 넘는다면 어떤 조건에서 넘는지.

dFCExpert 링크 (PMC11702678) 는 2024-12 bioRxiv preprint 판으로 보인다. 최종판은 IEEE TMI 45(3) (PMC12828913, 문헌 검토 R6) [확인 필요].

**주장하지 않는 것**: 뇌 상태 · 인지기전 · 조건 인식. 신호 복원 이득은 복원 이득일 뿐이다. 조건별 차이는 블록 위치와 겹치므로 기술값으로만 적는다.

## 2. 정보 접근 범위 — 주 분석과 보조 분석

"제한 관측" 은 **test 피험자에 대해 모델 · 표준화 · 채점 분모가 쓰는 정보가 그 창의 관측 ROI 와 train-only 값뿐**이라는 뜻으로 정의한다.

**주장 수준 세 단계** (v1.2). 전처리가 run 전체를 쓴다는 이유만으로 모든 분석이 불가능하지 않고, 원 ROI 재추출만으로 누수가 다 풀리지도 않는다. 각 수준이 보장하는 것과 못 하는 것을 나눈다.

| 수준 | 보장하는 것 | 남는 것 (주장 범위 밖) | 필요한 자료 |
|---|---|---|---|
| **T1 모델 단계 가린 신호 예측** | 모델 입력 · 적합 · 표준화 · 분모에 가린 ROI 신호가 들어가지 않는다 | 관측 ROI 의 창 밖 frame (run 전체 회귀 · z-score), 영상 단위 처리 | 기존 산출 재사용 가능 (A-run) |
| **T2 신호 단계 제한 관측 (주 분석 제안)** | T1 + ROI 신호 처리 (nuisance · 크기 맞춤 · 정답 정의) 가 창 안 관측만 씀 | 영상 단위 처리 (움직임 보정 기준 영상 · 공간 변환 추정 · 보간) 는 run 전체 · 이웃 복셀을 씀 — 아래 표 | 원 ROI 평균 재추출 (승인 필요) |
| T3 엄격한 제한 관측 · 실시간 | 영상 단위까지 창 안 · 인과적 처리 | — | 원자료부터 다시 전처리 (이 계획 범위 밖, 주장하지 않음) |

**상류 단계별 정보 범위** — 출처를 셋으로 나눈다. 로컬 = Mac 사본 · 저장소 코드 (이번 승인 범위). 원격 = h197 원본 메타데이터 (10-16, **승인 범위를 넘은 조회** — 사용자 지적 뒤 중단). 문헌 = AOMIC 논문 (Snoek et al. 2021, Sci Data, PMC7979787 — 공개 웹 조회, **승인 범위를 넘은 조회**). 로컬에 없는 fMRIPrep 보고서 · 로그 · CITATION 은 **미확인**.

| 단계 | 쓰는 정보 | 가린 ROI · 창 밖 정보와의 관계 | 출처 · 확인 범위 |
|---|---|---|---|
| fMRIPrep 판 | 1.4.1 | — | 원격 (`dataset_description.json`). 로컬 사본에 없음 |
| slice timing | 원본 sidecar 에 `SliceTiming` 없음 · 문헌 "not slice-time corrected" | 적용 안 됨으로 보임 | 원격 sidecar (상위 상속 파일은 확인 못 함) + 문헌. **로컬 미확인** |
| 움직임 추정 (mcflirt) | 문헌: 1 차 보정 뒤 **평균 영상**을 기준으로 | 기준 영상이 run 전체 · 모든 복셀 (가린 ROI 포함) 에서 만들어짐 → 공간 정렬 변수에 run 전체 정보 | 문헌. 로컬 미확인 |
| 왜곡 보정 · 정합 | 문헌: fieldmap-less (ANTs) · bbregister · T1w→MNI (ANTs) | 기준 영상 기반 공간 변환 — run 전체 | 문헌 |
| 재표본 | 문헌: 변환을 합쳐 **한 번에 Lanczos 보간** | 복셀 이웃끼리 섞임 → 가린 ROI 경계 복셀 신호가 인접 관측 ROI 경계로 조금 샐 수 있음 (frame 별 · 공간적) | 문헌. 크기 미측정 |
| 공간 평활 | 문헌에 fMRIPrep 단계 평활 언급 없음 | — | 문헌 (미언급 = 미확인) |
| confounds | 로컬 확인: 열 166 개, aCompCor (Mask CSF · WM · combined, SVD 특이값 · 설명분산) · tCompCor · global_signal · cosine · FD | aCompCor 는 run 전체 SVD. 문헌: aCompCor 는 피질 밖 (eroded brain mask ∩ CSF/WM), tCompCor 는 피질 밖 상위 5 % 변동 복셀. **global_signal 은 가린 ROI 포함 전뇌** — 현 설계는 쓰지 않음 | 로컬 (confounds tsv · json 구조) + 문헌 (마스크) |
| FD | Power 식 (문헌), 이웃 frame 차이 | 창 첫 frame 의 FD 는 창 앞 frame 을 씀 | 문헌 + 로컬 열 |
| ROI 평균 · 회귀 · z-score · 재표본 | 저장소 코드 감사 (handoff §11.53 표) | 회귀 · z-score 는 run 전체, ROI 끼리는 섞지 않음 | 로컬 코드 |

- 결론 (**v1.3 확정**): **첫 목표는 T1**. 기존 PIOP1 산출 (run 전체 회귀 · z-score) 을 그대로 쓴다. T2 (W-local, E1 재추출 필요) 는 T1 결과를 본 뒤 고를 수 있는 **후속 선택지**이며 지금 계획에 들어 있지 않다. T3 는 주장하지 않는다. (v1.2 의 "T2 주 · T1 보조" 는 바뀌었다.)
- 아래 표의 열 이름도 v1.3 에 맞춰 바꿨다: 첫 목표 = A-run (T1), 후속 = W-local (T2).
- 보간에 따른 경계 누출은 크기를 모르므로, **경계 완충 민감도** (가린 ROI 와 맞닿은 관측 ROI 를 입력에서 빼는 판) 를 보조 분석으로 둔다 [제안]. 맞닿음 정의는 atlas 복셀 인접으로 [잠금 필수].

| 단계 | 후속 T2 — W-local (제한 관측, 지금 계획 밖) | **첫 목표 T1 — A-run (run 전체 전처리 · 모델 단계 복원)** |
|---|---|---|
| 영상 단위 전처리 (움직임 보정 · 정합 · slice timing 등, fMRIPrep 파생 BOLD) | run 전체를 씀 — **모든 칸 공통, T2 주장의 범위 밖**으로 명시. 공간 정합 목적이지만 Lanczos 보간으로 경계 복셀은 이웃과 섞일 수 있다 (위 상류 표) [로컬 보고서 미확인] | 같음 |
| ROI 평균 | 창의 관측 ROI 만 입력. 가린 ROI 의 ROI 평균은 **정답 정의에만** 씀 | 같음 |
| nuisance · 대역 | **창 안에서만**: ROI 별 평균 · 선형 추세 제거. 창 안 FD > 0.5 mm frame 이 [잠금 필수: 개수 기준] 이상이면 창 제외 (FD 는 그 frame 에서 관측 가능). 24 motion 회귀는 15 frame 에 비해 자유도가 커서 주 분석에서 뺀다 [제안]. aCompCor 는 run 전체 WM · CSF 성분이라 쓰지 않는다 | 기존 추출 그대로 — run 전체 24 motion · aCompCor 5 · spike · DCT 0.008–0.2 Hz. **창 밖 frame 과 가린 ROI 자신의 창 밖 신호를 씀** |
| 크기 맞춤 (스케일) | 창 안 **관측 ROI 의 평균 원 강도 (grand mean)** 로 모든 ROI 를 나눠 백분율로 (관측 가능). 가린 ROI 의 자기 강도 · 분산은 쓰지 않음 | run 단위 ROI z-score (가린 ROI 자신의 run 분산 사용) |
| 정답 (가린 ROI) | 같은 창 안 규칙 (평균 · 추세 제거, 관측 ROI grand mean 으로 나눔). 평균 · 추세 제거 상수는 정답 자신에서 나오며 **정답의 정의**일 뿐 모델에 주지 않는다 | run z-score 된 값 |
| NMSE 분모 | **train-only**: training 피험자 task 창에서 같은 규칙으로 만든 가린 ROI 정답의 ROI 별 분산 (fold 마다) | 같은 정의를 A-run 단위로 |
| prior · 기준선 적합 | training-rest 를 **같은 창 안 규칙**으로 처리한 15 frame 창 (training 쪽은 run 전체 처리 · resample 을 써도 누수가 아님) | 기존 rest 창 |

- T1 (첫 목표) 은 기존 산출 (I3 `full_ts` emomatching · `derivatives_v3` rest 창) 로 한다 — 재추출 없음. 가린 ROI 의 run z-score 는 **정답의 정의**에만 쓰이고 모델 입력 · 적합 · NMSE 분모 (train-only) 에는 들어가지 않는다. 관측 ROI 의 z-score 는 run 전체 (창 밖 frame) 를 쓴다 — T1 범위에서 허용, 주장에 명시.
- T2 (후속) 는 새 ROI 시계열 추출이 필요하다 (E1). 처리 규모 참고: PIOP2 189 명 추출이 h197 에서 304 s 였다 [측정]. 실행 승인 대상.

### 2.1 hidden → observed 섞임 경로 점검 (T1 에 따로 붙이는 한계)

| 경로 | 섞임 가능성 | 근거 | T1 에서의 처리 |
|---|---|---|---|
| ROI 별 회귀 · z-score | 없음 — 열마다 따로 (ROI 끼리 섞지 않음) | 로컬 코드 `mobse/v2/extract.py:346` · `:370` | 확인됨 |
| nuisance 설계 | global_signal (전뇌, 가린 ROI 포함) · tCompCor 를 **쓰지 않음**. aCompCor 는 피질 밖 WM/CSF | 로컬 코드 `extract.py:199` (설계 열) · 문헌 (마스크) | 설계 열 이름은 manifest 에 없어 코드 판본으로만 확인 → 잠금 시 code sha 기록 |
| 공간 보간 (Lanczos 한 번) · 움직임 기준 영상 | 가린 ROI 경계 복셀 신호가 인접 관측 ROI 경계로 섞일 수 있음 — 크기 모름 | 문헌 (범위 밖 조회) · 로컬 보고서 없음 | **경계 완충 민감도** (가린 ROI 와 atlas 상 맞닿은 관측 ROI 를 입력에서 뺀 판) 를 보조로. 이 민감도는 섞임이 없다는 증명이 아니다 |
| brain mask (run 단위) | 복셀 포함 여부만 — 시간 신호 섞임 아님 | 로컬 코드 `10_wi02_extract.py:94` | 한계로 표기 |

- **의미**: 섞임이 있으면 그것은 "전처리된 신호" 자체의 성질이다. T1 의 복원 수치에는 포함되며, 이를 뇌 연결의 근거로 읽지 않는다. 인접 ROI 를 많이 쓰는 방법 (거리 · 이웃 기반) 이 상대적으로 득을 볼 수 있으므로 DIST · NN-k 대조와 경계 완충 민감도를 함께 보고한다.
- 공통 금지:
  - 전체 자료로 표준화 · PCA · 공분산을 맞추는 것.
  - test 피험자 rest · task 를 추정에 쓰는 것.
  - 가린 ROI 정보를 입력에 넣는 것 (blockz 포함).
- **실행 전 확인 필수 — 전처리 정보 범위**: 위 상류 표에서 로컬로 확인한 것은 confounds 구조뿐이다. fMRIPrep 판 · slice timing · 움직임 기준 · 보간은 원격 · 문헌 근거이며 보고서 · 로그는 미확인이다. 확인 전에는 T2 주장을 확정하지 않는다. FD 는 창 첫 frame 에서 창 앞 frame 을 쓴다 — 주 분석 창 제외 규칙은 창 안 둘째 frame 부터의 FD 로 정한다 [제안].
- **재추출 선택지 (실행은 각각 승인 필요)**:
  - E1 원 ROI 평균 (label ∩ brain mask 복셀 평균, 회귀 · z-score 없음) · FD · frame 시각을 rest · emomatching 에 대해 저장 — T2 에 필요. 기존 `roi_timeseries` 재사용.
  - E2 경계 침식 label (다른 label 과 맞닿은 복셀 제외) 로 E1 반복 — 보간 경계 누출 민감도 [제안, 선택].
  - E3 원자료부터 인과적 재전처리 — T3. 범위 밖, 권하지 않음.
  - 기존 산출 재사용 범위: I3 `full_ts` (emomatching) · `derivatives_v3` rest 창은 **T1 보조 분석**에만.

## 3. 모델 (1 순위 설계만)

입력은 test 창의 관측 ROI 신호 `x_O` (L × |O|) 이고, 출력은 같은 frame 의 가린 ROI 신호 `x_M` 이다. **가린 ROI 는 test 피험자의 그
task run 어디에서도 모델에 주지 않는다.**

| 칸 | 내용 | 정보 접근 |
|---|---|---|
| **MIX-a** | training-rest 15 frame 창을 단위로 EM 한 K 성분 Gaussian 혼합. 성분마다 shrinkage 공분산 (§4.4). test 창 가중치 w_k ∝ π_k · exp(τ · ℓ_k), ℓ_k = 창 관측 `x_O` 의 성분 k 주변 로그우도 (frame 합), τ 는 §4.4 규칙으로 train/inner 에서만 고름 (τ = 0 이면 π 가중 비적응 혼합). 예측 = Σ_k w_k [μ_M^k + Σ_MO^k (Σ_OO^k)⁻¹ (x_O(t) − μ_O^k)] | training-rest + 창의 `x_O` |
| MIX-f | 같은 성분, w_k = 1/K | 같음 |
| MIX-p | 같은 성분을 합친 단일 공분산 Σ̄ = Σ_k π_k Σ_k 의 조건부 평균 (같은 bank 에서 만든 비적응 기준, 기전 대조용) | 같음 |
| G1-LW · G1-OAS | K=1 공분산 (Ledoit-Wolf · OAS) 조건부 평균 — activity flow 계열 | 같음 |
| RIDGE · RRR | training-rest frame 에서 `x_O(t) → x_M(t)` ridge · reduced-rank ridge | 같음 |
| LAG-RIDGE | `[x_O(t−1), x_O(t), x_O(t+1)] → x_M(t)` ridge (창 끝은 있는 frame 만, 규칙 [잠금 필수]) | 같음 |
| DIST · NN-k | 거리 함수 공분산 (training-rest 로 맞춤) 의 조건부 평균 · 가까운 관측 ROI k 개 평균 | 같음 + ROI 좌표 |
| EVOKED | training 피험자 task 창의 ROI 별 평균 시간경과 (창 위치별) | **training-task** — 정보 접근이 달라 BEST 후보에서 뺌 |
| ORACLE-w | 정답으로 혼합 가중치를 고른 상한 | 상한 진단만 |

- BEST 후보: {G1-LW, G1-OAS, RIDGE, RRR, LAG-RIDGE}.
- 기존 thresholded adjacency 는 공분산으로 쓰지 않는다. GNN · gate · 학습형 router 는 이 단계에 없다.
- 15 frame test 창으로는 공분산을 **추정하지 않는다** (rank ≤ 14). 창은 prior 아래 우도로만 쓴다.

## 4. 사전 정의 — 실행 전 잠금 항목

### 4.1 자료 · 분할 [제안]

| 항목 | 값 |
|---|---|
| 개발 자료 | PIOP1 main 126 명, 기존 outer 5 fold (`folds.json`, split_hash `ace5f4a4…`). 피험자 단위 분할 — 같은 피험자의 창은 train · test 로 갈리지 않는다 |
| inner 선택 | outer fold 마다 training 피험자를 seed 고정 무작위로 inner train 80 % · inner val 20 % (피험자 단위) [잠금 필수: seed] |
| pilot 31 명 | 1 단계 판정에 넣지 않음. 쓰임은 별도 승인 시 정함 |
| task | emomatching (TR 2.0, 135 frame) 주. workingmemory 보조 |
| PIOP2 | 확증 자료 아님. 역할은 사용자 결정 |
| test 창 | 겹치지 않는 연속 L frame, frame 0 부터 (emomatching L = 15 이면 9 창) |

### 4.2 지표와 부호

- 정답 y_{s,w,m,r,t}: 피험자 s · 창 w · mask m · 가린 ROI r · frame t.
- **NMSE_s(방법)** = (1/N_s) Σ_{w,m,r,t} (ŷ − y)² / v_r.
  - v_r 는 그 outer fold 의 train-only 분산 (§2).
  - N_s 는 피험자 s 의 항 수.
  - 창 제외 규칙으로 빠진 창은 모든 방법에서 같이 빠진다.
- **Δ_s(A 대 B)** = NMSE_s(B) − NMSE_s(A) — 부호는 **양수면 A 가 낫다**로 통일한다. 모든 대조를 이 꼴로 적는다.
- **δ 의 단위**: NMSE 단위 (train-only 분산 대비 오차 제곱의 비율, 무차원). δ = 0.01 은 "가린 신호 train 분산의 1 % 만큼 오차 감소" [제안].
- 집계: 피험자 평균 Δ̄ (피험자당 1 값, 창 · frame 을 독립 표본으로 세지 않음).
- CI: 피험자 bootstrap 10,000 [잠금 필수: seed], 95 % percentile.
- 보조 지표: 모든 방법에 train-only 잔차 공분산을 붙인 Gaussian predictive log-likelihood, 창별 상관.

### 4.3 mask

- 주 [제안]: 가린 비율 20 % (100 ROI 중 20, 반구별 10). 무작위 mask M = 20 벌을 모든 피험자 · 창 · 방법에 공통으로 쓴다 [잠금 필수: 생성 seed · M].
- 보조: 10 % · 40 % · Yeo-7 network 통째 (Schaefer-100 7Networks 라벨 tsv 있음 [측정]).

### 4.4 모델 세부 [잠금 필수 — 아래 값은 제안]

| 항목 | 제안 |
|---|---|
| τ 후보 | **{0, τ_ESS, 1}** 셋만 (v1.2, 넓은 탐색 금지). τ = 0 은 π 가중 비적응 혼합 (fallback). τ_ESS = (1 − ρ̂)/(1 + ρ̂), ρ̂ = training-rest 처리 창의 lag-1 자기상관 평균 (train-only) — AR(1) 근사 유효 표본 비율. frame 독립 우도의 과신을 줄이려는 값이며, 짧은 창 · 추세 제거로 ρ̂ 가 과소추정될 수 있다 (§4.5) |
| ridge λ 후보 | 10^{−2, −1.5, …, 4} (13 개), 입력은 train-only 평균 · SD 로 표준화 |
| RRR rank 후보 | {1, 2, 4, 8, 16} × 같은 λ 후보 |
| K 후보 | {2, 3, 4} (K=1 은 G1 칸) |
| EM 초기화 | seed 고정 무작위 초기화 10 회 (창 k-means++ 로 책임도 초기화), training 로그우도 최대 판 채택 |
| 성분 공분산 | 책임도 가중 산포행렬에 Ledoit-Wolf 식 shrinkage (가중 판 식 [잠금 필수]), 최소 고유값 하한 [잠금 필수] |
| 수렴 | 상대 로그우도 변화 < 1e-6 또는 500 회 |
| 최소 점유율 | 성분 책임도 합이 training 창의 5 % 미만이면 그 K 는 실패 |
| 실패 처리 | 미수렴 · 점유율 미달 · 수치 오류인 K 는 선택 후보에서 빠지고 기록. 모든 K 가 실패하면 그 outer fold 의 MIX 는 "실패" 로 판정표에 남기고 G1 로 대체하지 않는다 |
| inner 선택 규칙 | outer fold 마다: inner train 으로 적합 → inner val 피험자의 **training task 창** 평균 NMSE 로 선택 (train-only; 선택에 training 피험자의 task 자료를 쓴다는 점을 명시 — 모델 적합에는 쓰지 않음). 선택 대상: BEST (G1-LW · G1-OAS · RIDGE λ · RRR rank · LAG-RIDGE λ 중 하나), MIX 의 K · τ. 동률 (차이 < 1e-4 [잠금 필수]) 이면 단순한 쪽 — 작은 K · 큰 λ · 작은 rank · **작은 τ**. 선택 뒤 outer train 전체로 다시 적합해 test 에 한 번 적용. test 는 보지 않는다 |
| 선택 불확실성 | fold 별 선택값 (BEST · K · τ) 과 inner val 곡선을 모두 보고. 피험자 bootstrap CI 는 선택 변동을 포함하지 않는다 (한계로 적음) |
| fallback | τ = 0 이 선택되면 "적응 미선택" 으로 기록하고 상태 적응을 주장하지 않는다 (G-A 는 그 비적응 혼합으로 판정). MIX 적합이 실패한 fold 는 "실패" — G1 로 몰래 대체하지 않는다 |

### 4.5 추정 안정성 — 충분하다고 단정하지 않음

- 쓸 수 있는 rest 양 [측정]: 사람당 60 s × 4 창 (2 s 격자 30 frame), 즉 15 frame 창 8 개.
- training 약 100 명 [추정] 이면 frame 수는 많아 보인다. 그러나 BOLD 는 frame 사이 자기상관이 커서 **유효 표본 수는 frame 수보다 작고**, 그 크기는 재지 않았다.
- 100 × 100 공분산 · K 성분 혼합에 그 유효 표본이 충분한지는 **미정**이다.
- 실행이 승인되면 다음을 잴 계획이다:
  - training-rest 의 frame 자기상관 · 유효 표본 수.
  - 성분별 shrinkage 강도 · 조건수.
  - fold 간 성분 안정성.
- 이 값들이 불안정하면 판정 전에 보고하고 멈춘다.
- LW · OAS shrinkage 강도 공식은 frame 독립을 가정한다. 합성에서 자기상관이 커져도 강도가 거의 변하지 않았다 (handoff §11.52). frame 수를 독립 표본 수로 쓰지 않는다.
- τ_ESS 의 ρ̂ 는 15 frame 창 · 추세 제거 뒤에 재므로 아래로 치우칠 수 있다. 합성에서 확인할 수 있는 것은 "ρ 가 크면 τ_ESS 가 작아진다" 는 방향뿐이며, 실제 BOLD 의 유효 표본 수 · 적절한 강도 · τ 는 미확정이다.
  - 합성 측정 (handoff §11.54): 참 AR(1) ρ 0.5 · 0.9 에서 이론 τ 0.33 · 0.05 인데 τ_ESS 는 0.66 · 0.45 — ρ̂ 과소추정으로 τ_ESS 가 크게 나온다 (방향만 맞음). 그래서 τ 는 τ_ESS 단독이 아니라 {0, τ_ESS, 1} 중 inner 선택으로 정한다.

## 5. 판정 규칙 (1 단계)

**대조별 판정 어휘** (95 % CI, Δ 부호 통일):

| 어휘 | 조건 |
|---|---|
| 이득 | 하한 > 0 이고 점추정 ≥ δ [제안: 진행에 필요한 최소] |
| 작은 이득 | 하한 > 0 이나 점추정 < δ |
| δ 이상 이득 배제 | 상한 < δ |
| 손해 | 상한 < 0 |
| 불확실 | 그 밖. **0 을 포함하는 CI 는 동등성도, regularization 의 증거도 아니다** |

**주 gate 하나 (v1.2)** — 진행 여부는 이것만으로 정한다:

| gate | 대조 | 진행 | 중단 |
|---|---|---|---|
| **G-A 주효과** | Δ(MIX-a(τ̂, K̂) 대 BEST), BEST · τ̂ · K̂ 모두 train/inner 에서만 선택 | 이득 | 손해 또는 δ 이상 이득 배제 → K>1 확장 중지 |

- "불확실" 이면 1 단계 판정도 **불확실**이다. 진행도 중단도 아니며 다음 단계는 사용자 결정이다.
- **MIX-a 가 MIX-f (또는 다른 약한 혼합) 보다 낫다는 것만으로는 진행하지 않는다.** 합성 positive control 에서 MIX-f 가 G1 보다 크게 나빴다 (handoff §11.53) — 약한 비교 대상이 될 수 있다.
- τ̂ = 0 이 선택된 fold 가 있으면 그 fold 의 G-A 는 비적응 혼합의 효과이며 "적응 미선택" 으로 표기한다.

**기전 보조 분석** (판정을 바꾸지 않고, 원인 해석을 과장하지 않는다):

| 대조 | 읽는 법 |
|---|---|
| Δ(MIX-a 대 MIX-p) | 같은 성분을 합친 단일 공분산 대비 — 적응 가중이 더하는 몫의 기술값 |
| Δ(MIX-a 대 MIX-f) | 1/K 고정 평균 대비 — MIX-f 가 약할 수 있어 부풀 수 있음. 단독으로 적응 이득 근거로 쓰지 않음 |
| Δ(MIX-f 대 BEST) · Δ(MIX-p 대 BEST) | 비적응 혼합 자체의 몫 |

- 예: MIX-p 가 BEST 보다 낫고 Δ(MIX-a 대 MIX-p) 의 상한 < δ 이면 "비적응 혼합의 개선이 있고 δ 이상의 적응 이득은 배제된다" 고만 적는다. 이는 δ 이상의 적응 이득만 배제하며, 작은 적응 효과와 기전 (평균화 · shrinkage 등) 은 미확정이다.
- 0 을 포함하면 "적응 추가 이득은 불확실" 로만 적는다.

**성공 정의 (v1.3 확정, 결정 86)**: train/inner 만으로 고른 강한 K=1 · shrinkage · ridge 기준선 (BEST) 대비 적응 혼합 MIX-a 의 개선 — 곧 G-A 의 "이득". MIX-f · MIX-p 대비 차이는 보조이며 성공 정의에 들어가지 않는다.

**사전 판정 잠금 시점 (v1.3)**:
- 잠금 = pilot (또는 본 분석) 잠금 파일 생성 — 이 계획서 · pilot 설계 · 코드 · 시험 결과 · 자료 manifest 의 해시를 묶는 시점. **실제 자료의 신호 값을 하나라도 읽기 전**이어야 한다.
- 잠금 전에는 판정 기준을 고칠 수 있다. 잠금 뒤, 또는 실제 자료 값을 본 뒤에 기준 · 후보 · 사전값을 바꾸면 그 분석은 **새 탐색 판 (v2 …)** 으로 표시한다. 같은 판의 판정으로 쓰지 않는다.
- **합성 시험의 사후 기준 변경 이력은 보존한다**: 잘못된 state bank 시험의 사전 기준 "큰 손실 없음 (< 1.05)" 이 1.088 로 실패했고, 결과를 본 뒤 "가짜 이득 없음" 으로 바꿨다 (handoff §11.54 · `tests/r2t/test_r2t_select.py` docstring). 합성 시험이라 실제 자료 판정과는 무관하나, 같은 일이 실제 자료에서 생기면 새 탐색 판으로 처리한다.

**해석 조건** (필수 gate 를 통과해도, 해당 주장을 하려면 필요):

| 주장 | 필요 조건 |
|---|---|
| "과제 유발 평균 이상의 복원" | EVOKED 를 정답 · 입력에서 뺀 잔차에서 G-A 가 이득. 아니면 이 주장을 하지 않음 |
| "공간 인접성 이상의 구조" | Δ(MIX-a 대 DIST) · Δ(MIX-a 대 NN-k) 가 이득 |
| "해부학적 정렬 특이성" | 1 순위 설계에서 주장하지 않음. 주장하려면 거리 의존 공분산 · spin 회전 공분산 대비 이득 (단순 ROI 순열 null 은 근거로 쓰지 않음). 못 미치면 주장 폐기 |

**보조 분석** (판정을 바꾸지 않음): T1 (A-run) 단위 · 경계 완충 민감도 · 창 길이 8 · 30 · run 전체 · mask 10 % · 40 % · network mask · workingmemory · K 별 · τ 별 · predictive log-likelihood · ORACLE-w 상한.

- 판정은 한 번 · 첫 목표 T1 주 분석 하나로 한다 (v1.3).

## 6. 단계 계획 · 자원 (모두 미승인)

| 단계 | 내용 | CPU/GPU · 시간 | 승인 |
|---|---|---|---|
| 0 구현 · 검증 (합성) | G1 · ridge · 누수 시험 (결정 83), 혼합 MIX-f · MIX-a (결정 84), MIX-p · τ/BEST inner 선택 · 합성 회귀시험 (결정 85) — handoff §11.52–§11.54 | CPU, 합성 수십 초 [측정] | 승인 · 수행 (합성만) |
| P pilot (T1) | 실행 전 검토용 1 페이지 설계 `r2t_pilot_design_v1_2026-10-16.md` — PIOP1 pilot 31 명 · 기존 산출 · 타당성 평가 | CPU 수 분 · RSS 1 GB 미만 [추정, 합성 측정 근거] | **미승인** (구현 · 잠금 · 실행 각각) |
| 1 판별 실험 (T1) | §4 · §5 주 분석, PIOP1 main 126 명 · 기존 산출 (재추출 없음) — pilot 뒤 별도 잠금 | CPU. 수 분–30 분 [추정], GPU 불필요 | 미승인 |
| (후속) T2 준비 | E1 원 ROI 평균 재추출, 선택 시 E2 — T1 결과 뒤 고를 수 있음 | CPU 수 분 [추정] | 미승인 · 지금 계획 밖 |
| 2 조건부 확장 | 1 이 진행일 때만: 보조 분석 · workingmemory · PIOP2 탐색 재현 (사용자 결정 시) | 1 시간 미만 [추정] | 미승인 |
| 3 독립 확증 | 잠근 설정을 새 자료에서 한 번 | 자료 결정 뒤 추정 | 미승인 (획득 · 실행 각각) |

참고 측정: 진단 logistic 1 회 (126 명 5 fold) 2.2 s, I3 본 실행 270 fit 70 분 (Mac MPS) [측정]. 1 단계에는 학습형 신경망이 없다.

## 7. 독립 검증 요건 · 후보 (조사 수준, 획득하지 않음)

**요건**:
- 같은 피험자의 rest 와 task 가 있고, 이 가설로 결과를 본 적이 없는 자료.
- TR ≤ 약 2 s, 표본 수는 1 단계 분산으로 다시 계산, MNI 등록 가능, 접근 조건 충족.
- PIOP1 · PIOP2 는 둘 다 결과를 보고 설계를 바꾼 자료라 해당하지 않는다.

| 후보 | rest · task | 접근 | 주의 |
|---|---|---|---|
| HCP Young Adult (S1200) | rest + 7 task, 약 1,200 명 | Open Access Data Use Terms 수락 (ConnectomeDB) | CLAUDE.md 는 "DUA 필요 · 접근 불확실" 로 제외해 둠 → 기관 판단 필요. 다른 장비 |
| Cam-CAN | rest + 영화 + 감각운동 task, 약 650 명 | 온라인 자료 사용 동의 · 신청 | 나이 폭 18–88, task 단순 |
| ds000030 (UCLA CNP) | rest + bart · bht · pamenc · pamret · scap · stopsignal · taskswitch (저장소 `data/ds000030/raw_fmriprep` [측정]) | 공개, 보유 | legacy 전이 실험에 쓴 노출 이력. 환자군 포함. legacy 파생 시계열은 신뢰하지 않음 |
| MSC (ds000224) | 10 명, 사람당 rest 약 5 h · task 약 6 h | 공개 | 집단 확증에는 작음 — 2 순위 개인화 후보 |
| AOMIC ID1000 | rest 없음 | — | 해당 없음 |

## 8. 2 · 3 순위 (실행 계획 없음)

- **2 순위 개인화**: label 없는 test 피험자 rest 로 작은 adapter (집단 prior 쪽으로 shrink 한 개인 공분산 · 개인 혼합 가중치) 를 정하고, 본인 · 타인 · 집단 rest 를 비교한다.
  - 먼저 확인할 것: paired rest–task 가용성. PIOP 적격 규칙상 사람마다 rest 가 있다 [측정: 적격 규칙]. 같은 세션 여부는 [확인 필요].
  - test-time calibration 범위: test 피험자 rest 는 모든 기준선에도 똑같이 준다.
- **3 순위 미래 예측 혼합**: 작은 선형 예측기들의 out-of-fold 오류가 서로 보완적인지 먼저 확인하고, 보완적일 때만 과거 frame 만으로 가중치를 정한다. oracle 선택은 상한 진단만.
- 처음부터 세 방향을 함께 실행하지 않는다.

## 9. 재사용 · 새로 만들 것

| 재사용 | 위치 |
|---|---|
| 원 BOLD · confounds · events 경로, ROI 평균 (atlas 2009c) | `scripts/h197/10_wi02_extract.py`, `scripts/piop2_confirm/extract.py` |
| A-run 산출 (보조) | I3 `full_ts`, `derivatives_v3` rest 창 |
| 분할 · cohort | `folds.json`, `subjects.jsonl` |
| ROI 좌표 · spin | `mobse/v3/templates.py` `roi_centroids` · spin null |
| 피험자 bootstrap · 잠금 · 결정론 양식 | `scripts/piop2_confirm/p2.py` `analyze` · `build_lock.py` |

- 새로 만들 것: T1 경로 (기존 z-score 산출을 그대로 입력 · 혼합 적합에 쓰는 처리 — 현 `mix.windows_full` 은 W-local 처리 전용이라 T1 용 경로가 따로 필요), 자료 적재 · 구동기 · 잠금, `tests/r2t/` 보강. (후속 T2 선택 시) W-local 추출.
- 쓰지 않는 것: graph bank (`sparsify_positive`) · GNN · gate · blockz.

## 10. 사용자 검토 사항 (모두 미정 — 추천과 이유)

| # | 항목 | 추천 [제안] | 이유 · 근거 | 대안 |
|---|---|---|---|---|
| 1 | 창 길이 L | 15 frame (30 s) | PIOP 블록 하나의 길이이고 I3 와 같아 비교가 쉽다. 100 ROI 에 비해 창 공분산이 rank 결손이라 창 단위 상태 추론이 prior 에 기대야 하는 조건이 된다 (T1 에서 창은 **모델 입력 단위**이지 짧은 촬영이 아님). emomatching 에서 겹치지 않는 9 창이 나온다. **문헌 기준 아님** | 8 · 30 · run 전체를 주로 |
| 2 | 가린 비율 | 20 % (반구 균형) | 창마다 가린 ROI 20 개로 오차 평균이 안정되면서 관측 80 개로 조건부 예측이 잘 정의된다. 10 · 40 % 보조의 가운데. **문헌 기준 아님** | network 통째 (공간 누수 최소, mask 다양성 7 개뿐) |
| 3 | δ | NMSE 0.01 (train 분산의 1 %) | 0 이 아닌 가장 작은 실익을 정하려는 설계 선택. **근거 문헌 없음**. 실행이 승인되면 분산 추정 뒤 검정력을 보고 다시 묻는다 | 기준선 NMSE 대비 상대 감소 (예 2 %) |
| 4 | 주장 수준 · 단위계 | **확정 (결정 86)**: 첫 목표 T1 (A-run, 기존 산출). T2 는 후속 선택지 · T3 주장 안 함 | — | — |
| 5 | (T2 전용) 창 안 nuisance | 창 안 평균 · 선형 추세 + FD 창 제외 — T1 에는 해당 없음 (기존 run 단위 처리) | 15 frame 에 24 motion 회귀는 자유도가 모자라다 [추정] | 창 안 6 motion 회귀 |
| 6 | §4.4 의 후보 집합 · 규칙 | 표의 제안값 | 일반적 범위에서 고른 값이며 결과를 보고 고른 것 아님 | 사용자 지정 |
| 7 | PIOP2 역할 | 2 단계 탐색 재현 (1 단계 진행 시만) | 독립 확증이 아니므로 재현 확인 정도로만 | 쓰지 않음 |
| 8 | 독립 자료 접근 조사 | HCP · Cam-CAN 접근 조건 조사 (획득 없음) | 표본 · 과제 폭이 크다 | ds000030 우선 (보유, 노출 이력) |
| 9 | inner 선택에 training 피험자 task 창 사용 | 사용 (§4.4) | 잘못된 state bank · 과신을 train 쪽에서 걸러낼 수 있다 (합성 회귀시험). 모델 적합에는 쓰지 않음 | rest 만으로 선택 (task 미사용, bank 오류를 못 거름) |
| 10 | 경계 완충 민감도 (T1 보조) · E2 (T2 전용) | 경계 완충은 T1 보조로 둠, E2 는 T2 선택 시에만 | 보간 경계 섞임의 크기를 모른다 (§2.1) | 생략 |

## 11. 변경 이력 (검토 반영)

1. 주 분석의 입력 · 크기 맞춤 · 가린 ROI 스케일 · NMSE 분모를 train-only 또는 창 관측 정보로 다시 정의 (W-local). run 전체 z-score · PSC 는 보조 A-run 으로 격하. 영상 단위 전처리 · nuisance · 대역이 쓰는 정보 범위를 표로 명시 (§2).
2. 0 포함 CI 는 불확실로만 판정. 고정 혼합 이득 (MIX-f 대 BEST) 과 상태 적응 추가 이득 (MIX-a 대 MIX-f) 을 따로 판정 (§1 · §5).
3. Δ = NMSE(비교 대상) − NMSE(대상) 로 부호 통일 (양수 = 대상이 나음), δ 를 NMSE 단위로 명시. 필수 gate (G-A · G-S) · 해석 조건 · 보조 분석을 구분 (§4.2 · §5).
4. mask seed · NMSE 식 · τ · λ · rank · K 후보, EM 초기화 · 최소 점유율 · 수렴 · 실패 처리, inner 선택 규칙을 적고 잠금 필수로 표시 (§4).
5. frame 수로 표본 충분을 단정한 문장을 지우고, 자기상관 · 유효 표본 수 미정을 명시 (§4.5).
6. L = 15 · 20 % · δ 0.01 의 근거를 적고 제안으로 표시, 불확실한 선택을 사용자 검토 사항으로 (§10).
7. (마감 문구 수정) 고정 혼합 이득 · 적응 이득 판정에서 이득의 원인을 평균화 · shrinkage 로 단정하던 문장을 좁힘 — 적응 이득 상한 < δ 는 δ 이상의 적응 이득만 배제하고, 작은 적응 효과와 기전은 미확정 (§1 · §5). 전처리 정보 범위를 실행 전 확인 필수 항목으로 표시 (§2).
8. (v1.2, 결정 85) 주장 수준 T1 · T2 · T3 와 상류 단계별 정보 범위 표 (출처를 로컬 · 원격 · 문헌으로 구분, 보고서 · 로그 미확인), 재추출 선택지 E1–E3 · 기존 산출 재사용 범위, 경계 완충 민감도 (§2).
9. (v1.2) 주 gate 를 G-A 하나로 — BEST · K · τ 를 train/inner 에서만 고른 MIX-a 대 BEST. G-S (MIX-a 대 MIX-f) 를 없애고 MIX-p 를 더해 기전 보조로 격하 (§1 · §3 · §5).
10. (v1.2) τ 후보 {0, τ_ESS, 1}, inner 선택 규칙 · 동률 · 선택 불확실성 · fallback (τ = 0 = 적응 미선택, 적합 실패는 실패), 유효 표본 · 자기상관 한계 (§4.4 · §4.5).
11. (v1.3, 결정 86) 첫 목표를 T1 모델 단계 복원으로 확정 (v1.2 의 "T2 주 · T1 보조" 를 바꿈), 실제 짧은 촬영 · 부분 뇌 관측 · 실시간 주장 제외, hidden → observed 섞임 경로 점검 §2.1, 성공 정의 (G-A) · 사전 판정 잠금 시점 · 결과 뒤 변경은 새 탐색 판 · 합성 사후 기준 변경 이력 보존 (§5), pilot 설계 문서 연결 (§6).

## 출처

- dFCExpert 최종판 (문헌 검토 R6): https://pmc.ncbi.nlm.nih.gov/articles/PMC12828913/ · 제시 링크 https://pmc.ncbi.nlm.nih.gov/articles/PMC11702678/ (preprint 판으로 보임 [확인 필요])
- MoRE-Brain: https://arxiv.org/abs/2505.15946 · AOMIC: https://www.nature.com/articles/s41597-021-00870-6 (전처리 서술은 PMC 판 https://pmc.ncbi.nlm.nih.gov/articles/PMC7979787/ 에서 읽음 — 승인 범위를 넘은 조회)
- Cole et al. 2016 activity flow: https://pmc.ncbi.nlm.nih.gov/articles/PMC5127712 · Tavor et al. 2016: https://ora.ox.ac.uk/objects/uuid:55087530-0595-463c-86a3-c54a4117b42b
- MSC: https://openfmri.org/dataset/ds000224/ · Cam-CAN: https://camcan-archive.mrc-cbu.cam.ac.uk/ · HCP 이용 조건: https://www.humanconnectome.org/study/hcp-young-adult/document/wu-minn-hcp-consortium-open-access-data-use-terms
