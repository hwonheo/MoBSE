# MoBSE 다음 방향 후보 — 원래 가설을 옮기는 대안 (2026-10-02, 검토용 초안)

> **결정이 아니다.** 선생님 요청 (2026-10-02 "신규성이 있는 아이템으로 진행해야 함. 최초 가설을 shift 하는
> 방향으로 (대안) 다른 아이디어를 더 찾아보자") 에 따라 후보를 모은 판단 재료다.
> 근거: 세 갈래 웹 문헌 조사 (2026-10-02). **조사는 대부분 초록 · 메타데이터만 확인했고, "찾지 못함" 은 검색어
> 15 개 남짓의 결과일 뿐 없다는 증명이 아니다.** 착수 전 핵심 선행은 본문을 다시 확인해야 한다.
> [P] = preprint, [J] = 동료심사 게재.

## 0. 출발점 — 지금까지 확인된 것

- 원래 가설 (컨셉 노트 2026-03-13): 뇌 연결 상태를 routing template 으로 쓰면 "정확도는 비슷하고 계산 비용은 낮다".
  재설계 (09-17) 에서 효율 주장을 범위 밖으로 뺐고, 이후 검정되지 않았다.
- v1 · v3 실측: 정렬된 뇌 bank 의 이득 (A−C) 은 지지되지 않음. A−B 는 FC 정보 경로의 효과 (NG ≈ A).
  이 target 은 FC logistic 이 학습 10 명에서도 0.98 이상.
- 이 과정에서 **방법론적 발견**이 쌓였다: ① ROI 공유 encoder + 평균 readout 은 `C(x)=A(Pᵀx)` 로 정렬 검정이
  원리적으로 퇴화 (수치 1.2e−7) ② 포화 선별 (G-a) 이 v1 target 을 pilot 31 명으로 미리 걸렀을 것 (1.000)
  ③ null 종류마다 BA 가 0.52–0.94 로 흩어짐 ④ 재학습 변동이 효과보다 커 보임 (결정 35 로 측정 중)
  ⑤ "routing 이득" 이 FC 를 이어 붙인 MLP 와 같음.

## 1. 문헌 지형 요약 (세 갈래)

**(가) 뇌 연결을 AI 구조의 사전지식으로** — 사람 connectome 은 사실상 reservoir 로만 쓰였다
(Suárez 2021 Nat Mach Intell [J] · conn2res 2024 Nat Commun [J] · Milisav 2026-06 Nat Commun [J]).
**null 이 엄격할수록 위상 이점이 줄거나 사라진다** — Dhiman 2026-04 arXiv 2604.04033 [P] (초파리, degree 보존 +
공정 초기화), Reimers 2026-09 arXiv 2609.30508 [P] (C. elegans, 무작위 null 이 자주 이김), Equifinality
2026-04 arXiv 2604.14419 [P] (일반 MoE 에서 routing 위상은 품질을 정하지 않음). 이점이 남은 경우는 조건부다
(Suárez 2021: 임계 상태에서만, Milisav 2026: **배선 비용 정규화 시에만**). 가장 가까운 MoE 연구 Brain-MoE
(arXiv 2609.10947 [P]) 는 정적 Yeo-7 이고 prior 효과 2.3 %p 이내, spin 없음, 효율 주장 없음.
→ **사람 dFC 상태 template 을 일반 ML 의 routing prior 로 쓰고 spin · rewire 로 대조한 연구는 찾지 못함.**
→ **같은 sparsity 의 null 위상과 FLOPs · 지연을 맞춰 비교한 연구도 찾지 못함.**

**(나) 뇌 그래프 딥러닝의 검증 방법론** — 노드 정체 손실은 성능 개선 문제로만 다뤄졌다 (BrainGB 2022 TMI [J],
Contrasformer 2024 CIKM [J], BrainPrompt 2025 [P] "뇌 그래프는 본래 순열 불변"). edge 를 지워도 정확도가
유지된다는 보고 (Lara-Rangel 2025 [P]). 단순 기준선 우위 계열 (Han 2026 npj Artif Intell [J], He 2020
NeuroImage [J], NeuroGraph 2023 NeurIPS D&B [J] — HCP-task 98 %). 재학습 변동은 일반 ML (Bouthillier 2021
MLSys [J]) · 분할 (Åkesson 2024 [J]) 에만 있고, CV CI 의 포함 확률 부족은 Bates 2024 JASA [J].
→ **찾지 못한 것**: ① 등변성이 null 검정을 퇴화시킨다는 정리 · 진단 ② 사람 fMRI 딥러닝 그래프 prior 의
spin/eigenstrap null 검정 ③ 구조 비교 전 포화 선별 절차 ④ 연결체 분류에서 CI 를 test 표집 · 재학습 두 몫으로
나누는 평가 ⑤ 이 다섯을 묶은 프로토콜.

**(다) 뇌 상태 routing 의 새 쓰임새** — dFC 상태 지표를 행동과 잇는 고전 연구는 많다 (Fu 2024 Mol
Psychiatry [J], N>10,000). 상태 지표 신뢰도는 짧은 scan 에서 낮다 (Netw Neurosci 2025 [J], prevalence ICC ≈ 0.5).
fMRI foundation model 의 MoE 는 모달리티 · ROI 기준 routing 이고 dFC 상태 기준은 없다 (Brain-OF [P],
BrainCSD [P] 등). edge time series (ETS) 는 과제 기술 · rs 진단에만 쓰였다 (Jones 2024 J Neurosci [J],
Siu 2026 [P]). AOMIC 은 지능 예측 · 구조-기능 결합의 replication 에 쓰였으나 dFC 상태 재현성은 없다.
→ **찾지 못한 것**: 학습된 gate 를 행동 측정값으로 쓴 연구, ETS (TR 단위) 상태로 routing 한 연구,
PIOP1→PIOP2 상태 template 재현성.

## 2. 후보

| # | 아이디어 | 원래 가설과의 관계 | 신규성 근거 | 자료 · 비용 | 주 위험 |
|---|---|---|---|---|---|
| **I1** | **뇌 그래프 prior 검증 프로토콜** — 등변성 정리 + 진단 시험, 다중 null (순열 · spin/eigenstrap · rewire), 포화 선별 gate, 재학습 변동을 넣은 CI, "FC 이어 붙인 MLP" 대조. 공개 구조 (BrainGNN · BNT · BrainGB 기준선) 에 적용해 퇴화 · 포화가 얼마나 흔한지 보인다 | "뇌 prior 가 좋다" → "**뇌 prior 가 좋은지 어떻게 시험하나**" 로 옮김 | (나) ①–⑤ 모두 공백 | 기존 자산 대부분 재사용. 공개 자료 필요 — AOMIC + ABIDE (legacy `artifacts/abide_dfc_*` 있음, 전처리 재확인 필요). 새 학습은 공개 구조 재현분 | 방법론 논문이라 받는 곳이 좁다. 공개 구조 재현에 시간이 든다 |
| **I2** | **같은 연산 예산에서 뇌 상태 topology 대 null topology** — 사람 dFC 상태 template 을 일반 ML (시계열 · 이미지) 모델의 sparse mask / MoE routing prior 로 쓰고, 같은 sparsity · FLOPs 에서 spin · degree 보존 · 무작위 위상과 비교. Milisav 2026 처럼 **배선 비용을 제약할 때만** 이점이 나오는지 본다 | **원래 효율 가설을 fMRI 밖에서 직접 검정** | (가) 공백 2 개 (상태 template routing prior · FLOPs 맞춤 null 비교) | 새 코드 (sparse 실행 경로 포함). 뇌 쪽 자료는 이미 있음 | **2026 문헌 흐름상 음성일 가능성이 높다** (Dhiman · Reimers · Equifinality). 음성이면 I1 과 같은 성격의 결과가 된다 |
| **I3** | **TR 단위 상태 (ETS) routing 으로 과제 조건 디코딩** — emomatching emotion/control, workingmemory active/passive. 60 s 창 대신 edge time series · 짧은 창으로 상태를 정의 | 포화된 "과제 정체" 대신 **포화되지 않은 within-task target** 에서 원래 MoBSE 질문을 다시 묻는다 (설계안 T2) | (다) ETS routing 공백 | 전처리 계층 재설계 (창 · 표본 · 통과대역). events 는 있음. 6 주 [추정] | 혈역학 지연 · 2 s TR 로 짧은 trial 이 섞임, ETS 잡음, "연결성" 주장의 해석 문제 (Merritt 2026) |
| **I4** | **gate 를 개인 내 측정값으로** — 창 (또는 ETS) 단위 gate 가중치를 같은 과제 안 trial 정확도 · RT 와 비교 | routing 을 성능 수단이 아니라 **측정 도구**로 | (다) 공백 | I3 의 산출을 그대로 씀. 개인 내 설계 필수 | gate 가 과제 정체만 따라가 포화, 개인 간이면 우연과 구분 불가 (G-a 와 같은 위험) |
| I5 | PIOP1 → PIOP2 상태 template 재현성 | 보조 | (다) 공백 | **PIOP2 개방 필요 (결정 27)** | 두 cohort 의 rest TR 이 0.75 · 2.0 s 로 달라 교란 |

뺀 것: "rest prior 의 저표본 학습 곡선" (방금 끝낸 T4 와 같은 축, 이미 음성).

## 3. 판단 (권고 — 결정 아님)

- **신규성 × 실행 가능성이 가장 높은 것은 I1** 이다. 공백이 다섯 군데 모두 비어 있고, 지금까지 만든 장치
  (null 3 종 · G-a · G-b · 저표본 곡선 · 변동 측정) 와 음성 결과가 그대로 근거가 된다. 일반화를 보이려면
  우리 모델 하나가 아니라 **공개 구조 2–3 개 · 공개 자료 2 개**에 적용해야 한다.
- **원래 가설에 가장 가까운 것은 I2** 다. 다만 2026 문헌이 "엄격한 null 아래서 위상 이점이 사라진다" 쪽이라
  긍정 결과를 기대하기 어렵다. 할 거라면 **사전등록 + I1 의 프로토콜로** 해서 음성이어도 쓸 수 있게 설계해야 한다.
- **긍정 결과를 노릴 실증 트랙은 I3 (+I4)** 다. 포화 문제를 정면으로 피하지만 전처리부터 새로 해야 한다.
- 조합안: **I1 을 본 트랙, I3 를 작은 탐색 트랙**으로 두면, I1 의 프로토콜이 I3 의 검증 틀이 된다.

## 4. 착수 전 확인이 필요한 것

- I1: BrainGNN · Brain Network Transformer · BrainGB 공식 구현의 라이선스 · 재현 가능성. ABIDE legacy 산출물의
  전처리 판본 (TR 적용 문제가 ABIDE 에도 있는지). eigenstrapping 도구 (부피 · 피질하 적용).
- I2: 실제 sparse 실행 경로 (PyTorch sparse / block-sparse) 와 같은 장비 지연 측정 방법. 비뇌 benchmark 선택.
- I3: 20–30 s 창 또는 ETS 에서 FC 추정 안정성, emomatching trial 간격 (약 5 s) 대비 분리 가능성 — pilot 31 명에서 먼저.
- 공통: 핵심 선행 (Brain-MoE 2609.10947 · Dhiman 2604.04033 · BrainPrompt 2504.16096 · Han 2026) 본문 확인.

## 5. I1 후보 모델의 자원 요구 (2026-10-02 조사 — 결정 36 뒤)

조사: 공식 저장소 6 개의 코드 · 설정 · 이슈 (`gh api`) 와 논문 5 편 본문. **코드는 실행하지 않았다.**
[논문] 보고값 · [계산] 기본 설정 코드에서 센 값 · [추정] 근거를 붙인 어림값 · [실측] 우리 h197 측정.

| 모델 | parameter (V=100) | fit 1 회 | 3090 Ti | 라이선스 | 재현 위험 |
|---|---:|---|---|---|---|
| MoBSE v3 | 6.6k–9.7k | 13–14 s 벽시계 (학습 6–7 s), GPU 145 MiB [실측] | 됨 | — | — |
| S3 FC logistic | 4,951 | 4 s [실측] | — | — | — |
| BNT (Kan, NeurIPS 2022) — Wayfear/BrainNetworkTransformer | 1,368,690 [계산] (V=200 3.98M = [논문] 4.0M) | [논문] ABIDE V=200 200 epoch 1.98 분 (RTX 8000) | torch 1.12.1 · cu113 — 됨 [추정] | MIT | 중간 (stratified split 에서 val/test 크기 뒤바뀜 #11 #14) |
| BQN (Yang, ICML 2025) — LYWJUN/BQN-demo | 759,934 [계산] | [논문] RTX 3090 100 epoch full batch ABIDE 11.31 s | torch 2.0 — 됨 [추정] | 없음 | 높음 (논문 AUC 79.85, 사용자 73.1–76.0) |
| BrainGB GCN · GAT (Cui, TMI 2022) — HennyJie/BrainGB | 793,906 · 1,115,746 [계산] | README 로그 ABIDE V=200 5-fold × 100 epoch 약 1 h 43 m | **cu101 고정 — 안 됨** (올려야 함) | MIT | 중간~높음 (val 없이 마지막 epoch test, 라벨 반전 지적 #28, GAT 버전 오류) |
| BrainGNN (Li, MedIA 2021) — xxlya/BrainGNN_Pytorch | 62,882 [계산] | 보고 없음. BNT 논문에서 ABCD 360 ROI OOM (48 GB) | **torch 1.7 — 안 됨** (Ampere 미지원, 이슈 #13) | 없음 | 높음 (ABIDE 사용자 0.50–0.57) |
| Han 2026 LM+GAT — LearningKeqi/RethinkingBCA | 약 19.8k [계산] | 보고 없음 | torch 1.12.1+cu116 — 됨 [추정] | 없음 | 중간 |
| Contrasformer (Xu, CIKM 2024) — AngusMonroe/Contrasformer | 341,077 [계산] | 보고 없음. step 당 비용 ∝ N_train² (코드 구조) | DGL 버전 확인 못 함 | GPL-3.0 | 중간~높음 |

- 비용은 대부분 V² 항 (BNT · BQN 의 DEC encoder `Linear(V², 32)`) 이다 — V=100 이 V=200 보다 3–4 배 싸다 [계산].
- **등변성 구분** [코드 근거]: BNT · BQN (평탄화) · BrainGB concat pooling · BrainGNN (one-hot ROI 입력) · Han (concat) 은
  기본 설정에서 ROI 순서에 **의존**한다 — 정렬 검정이 의미 있다. BrainGB 의 mean/sum pooling 과 v1 MoBSE 는 **등변**이다.
  I1 의 등변성 정리는 "등변 구성에서만 정렬 검정이 퇴화" 로 범위를 갈라야 한다.
- I1 기본 단위 예시 5 fold × (정렬 1 + null 3 × 10) × seed 3 = 465 fit [추정]: MoBSE 약 0.5 h · BNT/BQN 4–16 h ·
  BrainGB GCN 40–80 h. BrainGNN · Contrasformer 는 1 fit 실측 뒤 판단.
- h197 RAM 31 GB (사용 가능 약 8 GB, 10-02 실측) — 학습셋 전체를 매번 올리는 모델 (Contrasformer) 은 창 단위 표본에서 제약 [추정].

**ABIDE 받음 (2026-10-02 04:08Z–04:13Z, 선생님 지시 "ABIDE ASD 쪽도 h197 에 받아줘")**: h197 data root `abide_pcp/`
— PCP CPAC · filt_global · CC200, 파일 있는 1,035 명 전원 (ASD 505 · TC 530, 20 site), 385 MiB, 실패 0 · 모양 이상 0.
nilearn QC 규칙 통과는 ASD 405 · TC 468 (기록만, 선택 규칙은 I1 설계에서). 시점 수 78–316. phenotype sha256 `009f01a8…`.
Mac 판 468 개는 h197 판의 **QC 통과 TC 집합과 정확히 같고 sha256 468/468 일치**. 스크립트 `scripts/i1/fetch_abide_pcp.py`
(표준 라이브러리만, v2 venv 불변).

**받기 전 자료 현황 (10-02 실측)**: h197 data root 에는 AOMIC 만 (원본 210 GB · 추출본). Mac `~/nilearn_data/ABIDE_pcp` 는
CPAC · filt_global · CC200 시계열 **468 명 전원 정상 대조군 (DX=2)**, 20 site — ASD 대 TC 벤치마크에는 ASD 쪽을 더 받아야 한다.
`development_fmri` (151 명, Pixar 영화) 있음. `schaefer_2018` 은 FSLMNI152 공간 (2009c 판과 섞지 않는다).
