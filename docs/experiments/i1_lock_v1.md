# I1 — 사전등록 잠금 문서 v1

> 결정 38-4 의 잠금 문서다. 이 문서의 sha256 은 잠금 JSON (`results/i1/locks/i1_lock.json`) 에 들어가고, 본 실행 구동기
> (`scripts/i1/run_main.py`) 는 잠금 검증이 통과해야 돈다. 근거: 계획서 초안 `docs/experiments/i1_protocol_draft_2026-10-02.md`,
> 잠금 초안 `docs/experiments/i1_lock_v1_draft_2026-10-04.md`, 결정 36–44 (원문은 `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §10.11–§11).
> 본 실행은 이 잠금 뒤 **다시 승인받는다** (결정 39).

## 1. 질문과 범위

뇌 그래프 딥러닝 모델의 "ROI 정체 · 해부학적 배치를 쓴다" 는 판정이 (a) 구조의 대칭성, (b) null 의 종류, (c) 재학습 변동, (d) target 포화에
얼마나 좌우되는가. 검정 대상 C1–C5 (계획서 §1). **주장하지 않는 것**: 어느 모델이 가장 좋다 · ASD 진단 성능 · 새 모델 · 효율 우위.

## 2. 모델과 설정

| 모델 | 저장소 (commit) | 설정 | epoch | 등변성 (D1 학습 전 실측) |
|---|---|---|---:|---|
| BNT | BrainNetworkTransformer `8a588aa` | README ABIDE 명령 (`model=bnt preprocess=mixup datasz=100p`) | 200 | 순서 의존 |
| BQN | BQN-demo `5dc31b7` | 기본 인자 | 200 | 순서 의존 |
| Han dual-pathway | RethinkingBCA `cde613f` | 저자 ABIDE 명령 (`run_fold.py` `HAN_OVERRIDES`) | 100 | 순서 의존 [코드] |
| BrainGB GCN | BrainGB `f042694` | `--pooling mean --node_features degree --gcn_mp_type edge_node_concate --hidden_dim 256` (결정 40) | 100 | **등변** |
| MoBSE mean | v1 `mobse/v2` (측정 잠금 `9b7b11cf`) | v1 main 그대로 (결정 44) | v1 | 등변 |
| MoBSE embedding | v3 (`c0c8ed77db50`) | v3 본 실행의 구조별 선택 | v3 | 순서 의존 |

- 튜닝하지 않는다. 예외는 BrainGB 의 특성 (결정 40 — 공식 기본 `adj` 는 FC 행이라 등변이 아니다).
- 실행은 메모리 wrapper `scripts/i1/run_fold.py` — 저장소 파일은 고치지 않고 (잠금이 clone 의 `git status` 를 확인한다) 분할 · 평가 함수만
  바꿔 끼운다. 바꾼 목록은 fit 마다 `summary.json` `patches`.
- 결정성: `torch.use_deterministic_algorithms(True)`. **BrainGB 만 끈다** (결정적 PyG scatter 가 OOM, 저장소 mixup 이 `.cuda()` 고정이라
  CPU 불가) — BrainGB 는 같은 seed 재실행도 값이 다르고, 그 변동은 D3 에 포함된다.

## 3. 자료 · 분할

| 자료 | 역할 | 표본 | 분할 |
|---|---|---|---|
| ABIDE I PCP (CPAC · filt_noglobal · CC200) | 주 자료 | 1,009 명 (`abide.npy` sha `d81bb42063d6`) | 층화 무작위 5-fold, 층 = label × site, 안쪽 val = train 의 층화 10 % (`folds_draw0.json`) |
| AOMIC PIOP1 | 포화 양성 대조 | v1 main 126 명 × 2 task × 창 4 = 창 1,008 (30 시점 × Schaefer-100) | **v1 outer fold 그대로**, 안쪽 val = train 피험자 10 % (`aomic_win/folds.json`) |
| ABIDE site 민감도 | 민감도 | 1,009 명 | site 묶음 `GroupKFold(5)` (`folds_site.json`) |

- AOMIC: 창이 표본, 예측은 run 단위로 평균해 평가 (결정 43). label emomatching 0 · workingmemory 1.
- fold 는 R 반복에서 다시 뽑지 않는다 (결정 43). PIOP2 는 열지 않는다 (결정 27).

## 4. 조건 (null)

공개 모델 (입력 변환, `scripts/i1/null_inputs.py`, seed `SeedSequence([20261003, 조건, k, 피험자+1])`):

| 조건 | 정의 |
|---|---|
| orig | 원판 |
| n0 | 모든 피험자에 같은 무작위 ROI 순열 (대조) |
| n1 | 피험자별 무작위 순열 |
| n2 | 피험자별 spin — 반구 안 회전 + 일대일 배정 (Váša 2018), 반구 = 중심 x 부호 (결정 41) |
| n3 | 피험자별 가중 · 부호 null (Rubinov–Sporns 2011, bctpy 부호 버그를 고친 사본), 시계열은 원래 것 (결정 41) |

MoBSE (외부 prior 형): 입력은 그대로 두고 prior 그래프만 바꾼다 — mean 은 순열 prior (v1 null seed 1729–1733),
embedding 은 v3 의 `permutation` · `spin` · `rewire` (index 0–4). 이름은 `prior_*` 로 공개 모델의 n1–n3 과 구분한다.

## 5. 반복 규모

| 대상 | K (null 수) | R (seed) | fold | 비고 |
|---|---:|---:|---:|---|
| BNT · BQN · Han | 5 | 3 | 5 | orig · n0 은 k0 만 → (1+1+3×5)×3×5 = 255 fit / 자료 |
| BrainGB | 3 | 2 | 5 | (1+1+3×3)×2×5 = 110 fit / 자료 |
| MoBSE mean | 5 (순열만) | 3 | 5 | 새 학습 없음 (v1 결과) |
| MoBSE embedding | 5 × 3 종 | 3 | 5 | 새 fit 196 (나머지는 v3 본 실행 재사용) |
| 기준선 | — | FC logistic · S1 1 (결정적), FC-MLP 3 | 5 | 원판만 |
| site 민감도 | n1 5 | 3 | 5 | BQN, orig + n1 |

### 5.1 비용 [실측 1 fit × 계획 fit 수, 순차]

전체 epoch smoke (2026-10-04, ABIDE fold 0 · seed 1, h197 RTX 3090 Ti, sglang 이 쉬는 동안): BQN 152 s · BNT 194 s · Han 517 s · BrainGB 728 s.
ABIDE 순차 합 = 255×152 + 255×194 + 255×517 + 110×728 s ≈ **83 h** (10.8 + 13.7 + 36.6 + 22.2) [계산] — 계획서 §5 의 54–57 h 보다 크다
(Han · BrainGB 가 사전 점검보다 길다: 전체 epoch · val 평가 추가). 동시 2–3 개면 약 30–45 h [추정]. AOMIC (창 30 시점 · ROI 100) 은 더 짧다 [추정, 미측정].
n3 입력 생성 약 17 h (CPU, 8 병렬) [추정]. GPU 를 sglang 과 함께 써서 그 작업이 활성일 때는 OOM 재시도 · 대기가 생긴다.

## 6. 지표 · 추정량 · CI (결정 42 · 43)

- test 예측 = 안쪽 val loss (확률의 평균 CE) 최소 epoch, 같으면 앞 epoch. 네 공개 모델 · 기준선 FC-MLP 모두 같은 규칙.
- 단위 (조건, k, r) 마다 5 fold 의 test 예측을 모은 OOF. 지표 AUC 주 · BA (문턱 0.5) 보조.
- Δ_{c,k,r} = AUC(orig, r) − AUC(c, k, r), 같은 seed 짝.
- CI (2,000 회, 95 % percentile, 원판 · null 에 같은 피험자 재표집): **단일 학습 CI** (가장 작은 r · k=0 짝) 와 **재학습 포함 CI**
  (피험자 재표집 + (k, r) 짝 복원 재표집의 평균 Δ) 를 나란히. 모든 짝의 단일 CI 가 0 을 벗어나는 비율 (C3).
- 판정 문장: "조건 c 에서 Δ 의 재학습 포함 CI 가 0 을 넘는다 / 0 을 포함한다". δ 없음. 다중성 보정 없이 기술용 (그 사실을 적는다).
- 포화: 기준값 없이 기준선 성능을 반드시 함께 보고 (결정 39).
- 계산: `scripts/i1/analyze.py` (bootstrap seed 20261006).

## 7. 진단 D1–D5

- **D1 등변성**: orig · r=1 · fold 0–2 의 학습 끝 (마지막 epoch) 모델로, test 앞 8 명 · ROI 순열 20 개 (seed 1729) 의 class 1 확률 최대 차
  (`run_fold.py --d1`, 순열은 크기 V 인 모든 축에). 등변이면 부동소수 수준. 학습 전 값 (계획서 §3 표) 과 함께 보고.
- **D2 null**: §4 · §6.
- **D3 재학습 변동**: Δ 의 seed 간 SD, 단일 CI 반폭 중앙값, 단일 CI 가 0 을 벗어나는 비율.
- **D4 포화 · 기준선**: FC logistic (v1 S3 와 같은 fit 함수, C 는 안쪽 val log loss) · FC-MLP (고정 설정) · S1 을 같은 fold 로.
- **D5 재현 마찰**: 모델별 호환 수정 · 바꿔 끼운 함수 · 저장소 동작 (계획서 §9.1–§9.5) 과 실패를 표로.

## 8. 실패 판

다시 돌리지 않고 센다. 붕괴 = test 예측 표준편차 < 1e−6 또는 예측 class 하나 — 붕괴 fit 이 있는 단위를 표시하고, 뺀 결과를 민감도로.
프로세스 오류 (rc ≠ 0) 는 같은 seed 로 한 번 재시도 (구동기), 다시 실패하면 실패로 기록. GPU 메모리 부족도 같은 규칙이다
(h197 GPU 는 다른 작업 (sglang) 과 함께 쓴다 — 그 작업이 GPU 18.7 GB 를 쓰는 동안 Han · BrainGB 는 OOM, 2026-10-04 실측).

## 9. 알려진 한계 (잠금 시점)

- CC200 은 반구를 나눠 만든 atlas 가 아니다 — 반구 걸친 parcel 22 개 (25 % 초과), n2 의 반구 판정이 그 parcel 에서 임의적.
- n3 에서 시계열을 받는 모델 (BNT · BQN · Han) 은 FC 와 시계열이 어긋난다.
- BrainGB 비결정성. BrainGB 는 저장소 그대로 둘째 epoch 부터 eval 모드로 학습한다.
- AOMIC 은 30 시점 창 — 공개 모델의 원래 쓰임 (긴 시계열) 과 다르다.
- MoBSE mean 은 spin · rewire 가 없다 (v1 에 없음, 결정 44).
- **잠금 전에 본 결과**: 분석 파이프라인 smoke 로 MoBSE mean 팔 (기존 v1 결과) 을 I1 방식으로 계산했다 (잠금 초안 §7.1). 그 값으로 설계를 바꾸지 않았다.
- **잠금 전에 본 결과 (2)**: 전체 epoch smoke 의 원판 fold 0 · seed 1 test AUC — BQN 0.676 · BNT 0.757 · Han 0.751 · **BrainGB (degree) 0.461**.
  BrainGB degree 판이 이 한 fold 에서 우연 수준 아래다 (선택 epoch 93/100). 한 fold · 한 seed 라 판단 근거로 약하다.
- **잠금 전에 본 결과 (3)** (결정 45): BrainGB degree 판 원판 fold 1–4 · seed 1 (h197 `i1/braingb_check/20261004/`, rc 전부 0, fit 당 705–714 s).
  null 은 돌리지 않았다 (Δ 를 보지 않음).

  | fold | 선택 epoch | test AUC | test BA | 마지막 epoch AUC | train AUC 범위 (100 epoch) |
  |---|---:|---:|---:|---:|---|
  | 0 | 93 | 0.461 | 0.466 | 0.568 | 47.6–54.1 |
  | 1 | 93 | 0.486 | 0.500 | 0.483 | 48.9–53.3 |
  | 2 | 55 | 0.467 | 0.483 | 0.469 | 48.2–54.0 |
  | 3 | 2 | 0.523 | 0.527 | 0.515 | 47.6–54.7 |
  | 4 | 50 | 0.529 | 0.500 | 0.499 | 47.0–53.4 |

  다섯 fold 의 test AUC 는 0.461–0.529 (평균 0.493 [계산]) 이고, **학습 자료에서도 train AUC 가 55 를 넘지 않는다**. loss 는 0.0443 → 0.0439 로 거의 움직이지 않는다.
  → 과적합이 아니라 **학습이 되지 않는 판**이다. 같은 fold 0 에서 BQN · BNT · Han 은 0.68–0.76.
  원인 후보 [코드 · 측정, 검증 안 함]: ① 노드 특성이 1 차원 strength (FC 행 가중합, 평균 53.6 · SD 28.9 · 범위 −79–202, 정규화 없음) 라
  첫 GCN 층 출력이 노드마다 "스칼라 × 같은 벡터" 꼴이고 mean pooling 뒤에는 strength 분포 요약값만 남는다 (ROI 정체를 볼 수 없음 — 등변의 대가)
  ② 정규화 없는 큰 입력에 lr 1e−4 · 100 epoch (저장소 기본값) 이라 최적화도 덜 됐을 수 있다 [추정].

## 10. 잠금 뒤 바꾸면

설계 · 모델 · 지표 · 반복 규모 변경은 새 잠금판 (v2) 과 사유 기록이 필요하다. 버그 수정은 잠금 재생성 + 사유를 이 문서 끝에 덧붙인다.
