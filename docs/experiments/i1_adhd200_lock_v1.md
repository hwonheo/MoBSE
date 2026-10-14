# I1 확장 잠금 v1 — ADHD-200 에서 공개 모델 · MoBSE 를 같은 조건으로 (결정 62–65)

> 이 문서는 `scripts/i1_adhd200/build_lock.py` 가 해시하는 잠금 문서다. 잠금 뒤 바꾸면 잠금 검증이 실패한다.
> 잠금 생성 · 본 실행은 결정 65 로 승인됨.
> 범위 확인 메모: `docs/experiments/i1_adhd200_scoping_2026-10-14.md`. 결정 원문: `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.25–§11.28.
> I1 (`ac3bad06f6ef`) · ABIDE MoBSE (`64e75f1c9d4f`) 잠금과 그 산출은 바꾸지 않는다.

## 1. 질문

- I1 보고서 2 장 제안 3: AOMIC (천장) 대신 **천장이 아닌 두 번째 자료**에서, 공개 모델 셋과 MoBSE 두 구조의 Δ = AUC(원판) − AUC(뒤섞음) 판정이 ABIDE 와 같은가.
- 판정 문장은 I1 과 같음 — "재학습 포함 CI 가 0 을 넘는다 / 0 을 포함한다". 모델 사이 Δ 크기 · 원판 성능은 견주지 않음 (보고서 2.1 판의 이유와 같음).

## 2. 결정 원문

- 결정 62 (채팅): "제안 2 글로 정리, 제안 3 ADHD-200".
- 결정 63 (TUI): A1 "버림 (Recommended)" · A2 "빼고 100 시점 (Recommended)" · 착수 "구현 → smoke → 잠금안 (Recommended)".
- 결정 64 (TUI): "모두 188 영역 (Recommended)".
- 결정 65 (TUI): "h197 전부 · 겹치기 · 동시 2 (Recommended)".

## 3. 자료 · 분할 · 뒤섞기

| 항목 | 내용 |
|---|---|
| 원자료 | ADHD-200 Athena 판 CC200 시계열 (`ADHD200_CC200_TCs_filtfix.tar.gz`, NITRC, sha256 앞 `f86a57a660764ac7`) — 대역 0.009–0.08 Hz, 전역 신호 회귀 없음. session 1 · rest 1 의 `sfnwmrda…_cc200_TCs.1D` |
| 라벨 | 공개 S3 `participants.tsv` 의 dx — TD = 0, ADHD 세 아형 = 1. NITRC 학습판 DX 와 불일치 0 |
| 대상 | **541 명** (TD 298 · ADHD 243) — 라벨 있음 · 시점 ≥ 100 · 상수 영역 없음 · Pittsburgh · WashU (정상군만) 제외 (결정 63). 기관 6 개 (KKI 83 · NYU 216 · NeuroIMAGE 48 · Peking_1 85 · Peking_2 67 · Peking_3 42) |
| 영역 | Athena CC200 190 개에서 voxel 수가 가장 작은 2 개 (label 14 · 41) 를 뺀 **188 개** (결정 64). ABIDE 의 CC200 (200) 과 같은 지도가 아님 |
| 원판 파일 | `adhd200/i1data/abide.npy` (I1 표준 형식: `timeseires` 541×188×100 · `corr` · `pcorr` (전체 시점, Ledoit-Wolf → arctanh) · `label` · `site`), sha256 앞 `4fb37630ecba` — `scripts/i1_adhd200/build_inputs.py` |
| 좌표 | `coords.json` — 영역 중심 (voxel 평균 → affine), 반구 = x < 0 (좌 95 · 우 93). 반구를 걸친 voxel 비율 0.10 초과 29 개 · 0.25 초과 20 개 |
| 분할 | I1 `scripts/i1/make_folds.py` 그대로 — label × site 층화 5-fold, 안쪽 val 10 %, draw 0 (`folds_draw0.json`, fold 당 train 388–389 · val 44 · test 108–109) |
| 뒤섞기 | I1 `scripts/i1/null_inputs.py` 그대로 — n0 k0 · n1 · n2 · n3 각 k0–4. 시드 규칙 I1 과 같음 |

## 4. 모델 · 학습

| 팔 | 내용 |
|---|---|
| 공개 모델 | BQN · BNT · Han — I1 `scripts/i1/run_fold.py` 그대로 (저장소 commit · 설정 · 학습 길이 · 시험값 고르기 규칙 I1 과 같음). 조건 orig · n0 (k0) · n1–n3 (k0–4) × seed 1–3 × fold 5 = 모델당 **255 fit**. D1 학습판은 orig · r1 · fold 0–2 (I1 과 같음) |
| 기준선 | FC logistic · S1 (seed 1) · FC-MLP (seed 1–3), 원판만 (I1 `baselines.py`) |
| MoBSE | mean · embedding, cell A, config 0 — ABIDE MoBSE 잠금 §4 와 같음 (`scripts/i1_mobse_abide/` 를 경로만 바꿔 씀): 30 시점 창 3 개 · 학습 fold 창으로 PCA 10 + K=3 bank · update 예산 5,000 · I1 epoch 규칙. 조건 orig · n0 k0 · n1 · n2 k0–4 (n3 은 시계열을 바꾸지 않아 해당 없음) × seed 1–3 × fold 5 × 구조 2 = **360 fit** |
| 구동기 | `scripts/i1_adhd200/run_main.py` — I1 `Main` 을 상속해 입력 경로만 바꿈. 단계 nulls · fits · baselines · mobse_prep · mobse_fit · analyze |
| 실행 순서 (결정 65) | h197 한 곳에서 두 사슬을 함께 돌림 — CPU 사슬: nulls (n0–n2 → n3) → baselines → mobse_prep. GPU 사슬: n0–n2 입력이 생기면 fits (orig · n0 · n1 · n2) → n3 입력이 생기면 fits (n3) → mobse_prep 이 끝나면 mobse_fit. 둘 다 끝나면 analyze. 공개 모델 동시 2 · n3 worker 6 · MoBSE 동시 4 (운영 선택) |

## 5. 분석

- I1 `scripts/i1/analyze.py` 그대로, 541 명 전체. 모델마다 OOF AUC (주) · BA · Δ · 재학습 포함 CI · 단일 CI · 단일 CI 가 0 을 벗어난 비율.
- bootstrap 2,000 회 · seed 20261006 · 95 % percentile · 피험자 짝 재표집. **δ · 다중성 보정 없음 — 탐색적.**
- 붕괴 (fit 단위): test 예측 SD < 1e−6 또는 class 하나. 판정은 전체 단위, 붕괴 단위를 뺀 결과는 민감도.

## 6. 실패 규칙

- null 단계가 실패하면 사슬을 멈추고 보고한다 (뒤 단계가 그 입력을 씀). 학습 · 기준선 · MoBSE 의 실패는 세고 다음 단계로 간다.
- 공개 모델 · null · 기준선: I1 구동기 규칙 그대로 — 프로세스 오류는 같은 seed 로 **한 번** 다시 시도하고, 그래도 실패면 센다 (I1 결정 43 §3.3). GPU fit 은 여유 메모리 10 GB 를 기다려 시작 (I1 결정 48).
- MoBSE: 다시 돌리지 않고 셈 (ABIDE MoBSE 잠금 §6 과 같음).
- 중단 뒤 이어 돌리기는 끝난 작업 (`summary.json` · `meta.json` · `prep.json` 있음) 을 건너뛰는 것만 허용. 동시 실행 수는 운영 선택 (기록은 남김).

## 7. 잠금 전에 본 것

- 범위 확인 (190 영역, 학습 없음): 단순 기준선 FC logistic OOF AUC 674 명 0.629 · 정상군만 있는 두 기관을 뺀 541 명 0.596 (`scoping_20261014/`). 이 값으로 설계를 고르지 않음 — A1 은 기관 · 라벨 교락 때문에 정함.
- 190 영역 smoke (`smoke_20261014_190/`, 원판 · fold 0 · seed 1): BQN rc=0 · BNT rc=1 (주의 헤드) · Han rc=0 · null n0–n3 (8 명) rc=0. **BQN 로그 끝 3 줄을 봄 — 저장소가 epoch 마다 test AUC 를 찍어 그 줄에 test 값이 있었음.** 그 값으로 설계를 바꾸지 않음.
- 188 영역 smoke (`smoke_20261014_188/`, 원판 · fold 0 · seed 1, 잠금 없음): 공개 모델 셋 · 기준선 셋 · null 네 종류 (8 명) · MoBSE 구동기 (원판 · n1 k0, fold 0, seed 1, 두 구조) 전부 rc=0. 본 것은 rc · 시간 · 선택 epoch · test 예측 SD · 0.5 이상 개수 (붕괴 점검) 뿐 — **AUC · Δ 는 계산하지 않음.** 공개 모델 저장소 로그에는 test AUC 가 찍혀 있으나 열어 보지 않음.
  - 선택 epoch: BQN 17/200 · BNT 2/200 · Han 58/100 · MoBSE 네 fit 13/136.

## 8. 바꾸지 않는 것과 이탈

- `scripts/i1` · `scripts/i1_mobse_abide` · `mobse/v2` · `mobse/v3` 는 고치지 않는다 (이 잠금도 해시한다).
- 결과를 본 뒤 설계를 바꾸면 이 잠금의 새 판 (v2) 이 필요하고 이탈로 기록한다.
- I1 과 다른 점 (이탈이 아니라 자료 차이): 영역 지도 (Athena CC200 188 대 PCP CC200 200) · 전처리 파이프라인 (Athena 대 CPAC) · 기관 민감도 (BQN 기관 분할) 를 하지 않음.

## 9. 산출 · 비용

- h197 data root 상대 `adhd200/main/<날짜>_<lock 앞 8>_a<번호>/`: `inputs/adhd200/` · `adhd200/<모델>/…` · `mobse/` · `analysis/adhd200/*.json` · `driver_adhd200.log` · `fails_*.json` · `logs/`.
- 비용 [추정, smoke 1 fit 시간 × 개수, 겹치기 전]: 공개 모델 BQN 255 × 77 s · BNT 255 × 109 s · Han 255 × 186 s ≈ 26 시간 (동시 1) · **약 13 시간 (동시 2)**. n3 생성 약 1 시간. 기준선 약 10 분. MoBSE 준비 60 + 학습 360 약 2–3 시간. 분석 약 15 분. **전체 약 16–18 시간 (동시 2)**.
- 저장소 쪽: 잠금 `results/i1_adhd200/locks/lock.json`, 결과 기록은 handoff 와 I1 보고서의 새 판.
