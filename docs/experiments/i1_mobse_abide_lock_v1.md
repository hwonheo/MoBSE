# I1 확장 잠금 v1 — ABIDE 에서 MoBSE 를 공개 모델과 같은 조건으로 (결정 58 · 59)

> 이 문서는 `scripts/i1_mobse_abide/build_lock.py` 가 해시하는 잠금 문서다. 잠금 뒤 바꾸면 잠금 검증이 실패한다.
> 범위 확인 메모: `docs/experiments/i1_mobse_abide_scoping_2026-10-13.md`. 결정 원문: `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.19 · §11.20.
> I1 잠금 (`ac3bad06f6ef`) 과 그 산출은 바꾸지 않는다. 이 잠금은 그 위에 MoBSE 팔 하나를 더한다.

## 1. 질문

- I1 공개 모델 (BQN · BNT · Han) 과 **같은 자료 · 같은 fold · 같은 seed · 같은 입력 뒤섞기**에서 MoBSE (cell A, 구조 mean · embedding) 의 Δ = AUC(원판) − AUC(뒤섞음) 은 어떠한가.
- 비교 단위는 I1 과 같음 — 모델마다 "자기 원판 대 자기 뒤섞음". 모델 사이에는 같은 자료 · 같은 뒤섞기의 판정 문장 ("재학습 포함 CI 가 0 을 넘는다 / 0 을 포함한다") 과 Δ 크기를 나란히 보고한다.

## 2. 결정 원문

- 결정 58 (TUI): "제안 1, 범위 확인부터 (Recommended)".
- 결정 59 (TUI): "구현 → 잠금 → 본 실행 (Recommended)" · D1 "963 명 공통 분석 (Recommended)" · D2 "MoBSE 는 n0–n2 만 (Recommended)" · D5 "config 0 고정 (Recommended)". 나머지는 범위 확인 메모의 권고안.

## 3. 자료 · 분할 · 뒤섞기

| 항목 | 내용 |
|---|---|
| 자료 | I1 `abide.npy` (ABIDE I PCP · CPAC · filt_noglobal · CC200, 1,009 명, 시계열 앞 100 시점). label ASD 0 · TC 1 |
| 분석 대상 | **963 명** — 30 시점 창 안에 상수 영역이 있는 46 명을 뺌 (잠긴 MoBSE 특징 함수가 그 창을 거부, D1). 원판에서 정하고 모든 입력에서 같은 집합인지 대조 |
| 분할 | I1 `folds_draw0.json` 그대로 (fold 5, train · val · test). 각 부분에서 46 명만 뺌 |
| 뒤섞기 | I1 본 실행의 입력 그대로: n0 k0 · n1 k0–4 · n2 k0–4 (`inputs/abide/<cond>_k<k>/abide.npy`). **n3 은 쓰지 않음** — I1 n3 은 시계열을 바꾸지 않아 MoBSE 에 효과가 없음 (D2). 보고에서 MoBSE 의 n3 칸은 "해당 없음" |
| 공개 모델 | **새 학습 없음.** I1 본 실행의 ABIDE 예측 (BQN · BNT · Han 각 255 fit) 을 963 명으로 좁혀 다시 분석 |

## 4. MoBSE 입력 · 모델 · 학습

| 항목 | 내용 |
|---|---|
| 창 | 사람당 30 시점 창 3 개 (0–29 · 30–59 · 60–89). 창 label = 피험자 label |
| 특징 · bank | 창 FC (Ledoit-Wolf) · Fisher-z → scaler + PCA 10 → KMeans K=3 bank (`mobse/v2/features.py` · `templates.py`, 고치지 않음). **학습 fold 피험자의 창만으로 fit** — ABIDE 에는 따로 쉬는 scan 이 없어, bank 를 만드는 창과 분류하는 창이 같은 자료 (AOMIC 설계와의 차이, D3) |
| 모델 | cell A (brain bank + 입력 의존 routing), `mobse/v3/models.MoBSEv3` 의 mean (등변) · embedding (순서 의존) |
| 설정 | config 0 고정 — lr 0.001 · dropout 0.1 · weight decay 1e-4 (D5). grid 를 열지 않음 (공개 모델도 튜닝 없음) |
| 학습 | AdamW · CrossEntropy (창 단위) · batch 32 · grad clip 1.0 · update 예산 5,000 (`mobse/v3/train.py`) — 예산 안 전 epoch 학습 |
| epoch 선택 | I1 공개 모델 규칙: 안쪽 val 의 피험자 평균 cross-entropy 최소 epoch (같으면 앞 epoch) 의 가중치로 test 예측 |
| 예측 | 피험자별 창 확률 평균 (test 피험자만 저장) |
| 반복 | seed 1 · 2 · 3 × fold 5 × 입력 12 판 (원판 · n0 k0 · n1 k0–4 · n2 k0–4) × 구조 2 = **360 fit**. 준비물 (PCA · bank) 은 입력 × fold 60 개를 seed · 구조가 공유 |
| seed | `random` · `numpy` · `torch` 를 seed 로 고정, cudnn deterministic. GPU 연산의 완전한 결정성은 보장하지 않음 |

## 5. 분석

- I1 `scripts/i1/analyze.py` 의 함수를 그대로 import (`scripts/i1_mobse_abide/analyze963.py`) — 963 명으로 index 를 다시 매기는 것만 다름.
- 모델 5 개 (MoBSE mean · embedding, BQN · BNT · Han) 모두 963 명. OOF AUC (주) · BA (보조) · Δ · 재학습 포함 CI · 단일 CI · 단일 CI 가 0 을 벗어난 비율 (D3).
- bootstrap 2,000 회 · seed 20261006 · 95 % percentile · 피험자 짝 재표집. **δ · 다중성 보정 없음 — 탐색적.**
- 붕괴 (fit 단위): test 예측 SD < 1e−6 또는 class 하나. 판정은 전체 단위, 붕괴 단위를 뺀 결과는 민감도.

## 6. 실패 규칙

- 실패는 **다시 돌리지 않고 센다** (I1 잠금 §8 과 같음). 중단 뒤 이어 돌리기는 끝난 작업 (`summary.json` · `prep.json` 있음) 을 건너뛰는 것만 허용.
- GPU 메모리 부족도 같은 규칙. 동시 실행 수는 운영 선택이며 잠금 대상이 아님 (기록은 남김).

## 7. 잠금 전에 본 것

- 범위 확인 smoke (`i1_mobse_abide/smoke_20261013/`, fold 0 · seed 1, 학습 fold 690 명 · val 77 명, **test 미사용**): 4 fit 전부 rc=0 · 붕괴 없음. 구동기가 출력한 **val** AUC — mean 원판 0.678 · embedding 원판 0.736 · mean n1 k0 0.661 · embedding n1 k0 0.601. 이 값으로 설계를 바꾸지 않음.
- 구동기 smoke (잠금 전, `i1_mobse_abide/driver_smoke_20261013/`, `--no-lock`, 산출에 `SMOKE_NOT_LOCKED` 표시): 원판 · n1 k0 의 fold 0 준비물 2 개 (161 s, 동시 2) 와 fit 4 개 (seed 1 × 구조 2, 88 s, 동시 4), 실패 0. 963 명 · fold 0 의 train 690 · val 77 · test 196 확인. **test 예측 파일은 생겼으나 AUC · Δ 를 계산하지 않았고**, 출력한 것은 선택 epoch · test 예측 SD (붕괴 점검) 뿐임. 분석 · 보고에 쓰지 않음.
- I1 공개 모델의 ABIDE 결과 (1,009 명) 는 이미 알려져 있음 (I1 보고서). 963 명 재분석 값은 잠금 뒤에 처음 냄.

## 8. 바꾸지 않는 것과 이탈

- 결과를 본 뒤 설계를 바꾸면 이 잠금의 새 판 (v2) 이 필요하고, 이탈로 기록한다.
- `mobse/v2` · `mobse/v3` · `scripts/i1` 은 고치지 않는다 (각 잠금이 해시). 이 잠금도 그 파일들을 해시한다.

## 9. 산출

- h197 data root 상대 `i1_mobse_abide/main/<날짜>_<lock 앞 8>_a<번호>/`: `cache/` · `abide/mobse_{mean,embedding}/<cond>/k<k>/r<seed>/f<fold>/` (`predictions.jsonl` · `summary.json` · `epochs.jsonl`) · `analysis/*.json` · `status.txt` · `fails_*.json` · `logs/` · `kept_subjects.json`.
- 저장소 쪽: 잠금 `results/i1_mobse_abide/locks/lock.json`, 결과 기록은 handoff 와 I1 보고서의 새 판.
