# I1 확장 — MoBSE 를 ABIDE 에서 공개 모델과 같은 조건으로 돌리기: 범위 확인 메모 (결정 58)

> 2026-10-13 · 설계 메모 + smoke 결과 + 잠금안 초안. **잠금 · 본 실행은 하지 않았음** (결정 58 의 범위).
> 근거: I1 보고서 2.0 의 2 장 (MoBSE 를 공개 모델과 나란히 놓을 수 없는 이유) · 결정 58 원문 (handoff §11.19).

## 1. 목표

- I1 공개 모델 (BQN · BNT · Han) 과 **같은 자료 (ABIDE 1,009 명) · 같은 fold · 같은 seed · 같은 입력 뒤섞기** 로 MoBSE (cell A, 구조 mean · embedding) 의 Δ 를 낸다.
- 그래야 "MoBSE 가 공개 모델보다 영역 정보를 덜 (또는 더) 쓰는가" 를 같은 줄에서 볼 수 있음.

## 2. 그대로 쓰는 것 (잠긴 코드는 import 만)

| 부분 | 출처 | 잠금 |
|---|---|---|
| 창 FC (Ledoit-Wolf) · Fisher-z · scaler + PCA 10 | `mobse/v2/features.py` | v1 측정 · 구현 잠금이 해시 — 고치지 않음 |
| bank (KMeans K=3 · 양수 상위 20 % · 정규화) | `mobse/v2/templates.py` | 〃 |
| cell A (brain bank + 입력 의존 routing) | `mobse/v2/models.py` `CELL_SPEC` | 〃 |
| 모델 구조 mean · embedding | `mobse/v3/models.py` `MoBSEv3` | v3 잠금이 해시 — 고치지 않음 |
| grid · batch 32 · grad clip · update 예산 5,000 | `mobse/v2/train.py` · `mobse/v3/train.py` | 〃 |
| 자료 · fold · 입력 뒤섞기 | I1 `abide.npy` · `folds_draw0.json` · `inputs/abide/<cond>_k<k>/` | I1 잠금이 해시 — 그대로 읽음 |

- 새 코드는 `scripts/i1_mobse_abide/` 에만 둠 — `scripts/i1/` 에 두면 I1 잠금의 code_hash 가 바뀜.
- v3 의 학습 함수 (`mobse/v3/fitting.train_fold`) 는 쓸 수 없음 — label 을 AOMIC task 이름에서 읽고 run 당 창 4 개를 강제함. 같은 규칙 (AdamW · CrossEntropy · batch · clip · 예산) 의 짧은 학습 루프를 새로 둠.

## 3. AOMIC 과 다른 점 — 결정 후보

| # | 문제 | 선택지 | 권고 |
|---|---|---|---|
| D1 | **상수 영역 피험자 46 명** — 30 시점 창 안에서 신호가 0 인 영역이 있는 피험자 (한 창 최대 118 영역). 잠긴 특징 함수가 그런 창을 거부함. 공개 모델은 이 46 명도 씀 | (a) MoBSE 에서 빼고, 비교는 **공개 모델 · MoBSE 모두 같은 963 명으로 다시 분석** (공개 모델은 새 학습 없이 기존 피험자별 예측을 963 명으로 좁힘) · (b) 상수 영역을 따로 처리하는 새 특징 함수 — MoBSE 특징 정의가 바뀜 | (a) |
| D2 | **n3 은 MoBSE 에 효과가 없음** — I1 의 n3 은 연결성 행렬만 바꾸고 시계열은 그대로 둠. MoBSE 는 창 시계열에서 연결성을 다시 계산함 | (a) MoBSE 는 n0 · n1 · n2 만 · (b) 시계열 단위의 새 n3 정의 — I1 공개 모델과 다른 개입이 됨 | (a) |
| D3 | 쉬는 scan 이 따로 없음 — bank · PCA 를 **학습 fold 피험자의 같은 창**으로 만듦 (진단군 구분 없이). AOMIC 은 rest 로 bank, task 로 분류 | 피할 길이 없음 — 차이로 기록 | 기록 |
| D4 | 시계열 길이 — I1 `abide.npy` 는 앞 100 시점만 남김 → 30 시점 창 3 개 (0–29 · 30–59 · 60–89) | (a) 공개 모델과 같은 입력 · (b) PCP 원 파일로 더 긴 창 — 입력이 공개 모델과 달라짐, 뒤섞기도 다시 적용 | (a) |
| D5 | 설정 — v1 · v3 는 안쪽 grid 8 개에서 고름 | (a) config 0 하나로 고정 (lr 0.001 · dropout 0.1 · wd 1e-4, v3 embedding 선택 5 fold 중 3) — 공개 모델도 튜닝 없음 · (b) grid 선택 — 비용 8 배 | (a) |
| D6 | epoch 선택 | I1 공개 모델 규칙: 안쪽 val 의 피험자 평균 cross-entropy 최소 (같으면 앞 epoch), 예산 안 전 epoch 학습 | 그대로 |
| D7 | seed · 반복 | I1 과 같음: seed 1–3 · fold 5 · 뒤섞기 k0–k4 (n0 · 원판은 k0) | 그대로 |
| D8 | v3 의 prior 뒤섞기 (순열 · spin · rewire bank) 를 ABIDE 에서도 할지 | spin 은 `cc200_coords.json` 으로 가능하나 반구 걸친 parcel 22 개 문제 | 이번엔 하지 않음 (입력 뒤섞기 비교가 목적) |

- 창 label = 피험자 진단 (ASD 0 · TC 1, I1 과 같음), 평가는 피험자별 창 확률 평균.
- 분석은 I1 `analyze.py` 와 같은 계산 (OOF AUC · Δ · 재학습 포함 CI · D3) 을 963 명에 대해 — 공개 모델 셋도 963 명으로 다시 냄. `analyze.py` 는 표본 수 1,009 를 전제하므로 963 명용 얇은 감싸개가 필요함 (`scripts/i1/` 밖).

## 4. smoke 결과 (h197, fold 0 · seed 1, cell A)

- 구동기 `scripts/i1_mobse_abide/smoke.py`. 산출 h197 data root 상대 `i1_mobse_abide/smoke_20261013/` (4 fit, 전부 rc=0).
- 입력: 원판 `abide.npy` (sha `d81bb42063d6`) · n1 k0 (`inputs/abide/n1_k0/abide.npy`, sha `31cba566d5d8`). 학습 690 명 (창 2,070) · val 77 명 — 상수 영역 피험자는 fold 0 의 train 36 · val 4 명이 빠짐.
- **test 피험자는 읽지 않음.** Δ 는 계산하지 않음.

| fit | rc | epoch (선택 / 예산) | val 예측 SD | 붕괴 | bank 군집 크기 | 특징 s | PCA · bank s | 학습 s | 합계 s | GPU 최대 |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| mean · 원판 | 0 | 52 / 77 | 0.147 | 없음 | 215 · 1,161 · 694 | 36 | 116 | 50 | 221 | 580 MB |
| embedding · 원판 | 0 | 39 / 77 | 0.150 | 없음 | 215 · 1,161 · 694 | 35 | 195 | 47 | 283 | 580 MB |
| mean · n1 k0 | 0 | 38 / 77 | 0.121 | 없음 | 695 · 1,156 · 219 | 17 | 314 | 33 | 371 | 580 MB |
| embedding · n1 k0 | 0 | 51 / 77 | 0.126 | 없음 | 695 · 1,156 · 219 | 20 | 240 | 40 | 303 | 580 MB |

- **학습 됨**: 넷 다 val AUC 0.5 초과, 선택 epoch 이 중간 (38–52), 붕괴 없음. BrainGB 같은 학습 불가는 없음.
- **잠금 전에 본 값 (기록)**: 구동기가 fold 0 · seed 1 의 **val** AUC 를 출력함 — mean 원판 0.678 · embedding 원판 0.736 · mean n1 0.661 · embedding n1 0.601. val 은 학습 fold 안의 epoch 선택용이며 test 가 아님. 이 값으로 설계를 바꾸지 않음 (잠금 문서에 옮겨 적을 것).
- PCA · bank 시간이 116–314 s 로 흔들림 — 공유 CPU (sglang 상주) 영향으로 봄 [추정]. 이 단계는 seed · 구조와 무관하므로 본 실행에서는 (뒤섞기 판, fold) 마다 한 번만 만들고 공유함.

## 5. 비용 추정

| 항목 | 수 | 단가 (smoke) | 합 [추정] |
|---|---:|---|---|
| 특징 + PCA · bank | 입력 12 판 (원판 · n0 k0 · n1 k0–4 · n2 k0–4) × fold 5 = 60 | 2.5–5.5 분 (CPU) | 순차 2.5–5.5 시간, 3–4 개 병렬이면 약 1–2 시간 |
| 학습 | 60 × seed 3 × 구조 2 = 360 | 33–50 초 (GPU 580 MB) | 순차 3.3–5 시간, GPU 동시 4 개면 약 1–1.5 시간 |
| 분석 | MoBSE 2 · 공개 모델 3 을 963 명으로 | 분 단위 | — |
| **합계** | | | **약 3–7 시간** (I1 공개 모델 본 실행 91.6 시간 대비 작음) |

- 병렬 실행의 실제 속도는 재지 않음 — 본 실행 첫 단계에서 잼.

## 6. 잠금안 초안

- **새 잠금** `results/i1_mobse_abide/locks/lock.json` + 잠금 문서 `docs/experiments/i1_mobse_abide_lock_v1.md` (I1 잠금과 별개, I1 잠금은 불변).
  - code: `scripts/i1_mobse_abide/*.py` + import 하는 `mobse/v2/{features,templates,models,train}.py` · `mobse/v3/{models,train}.py`.
  - data: `abide.npy` · `folds_draw0.json` · I1 run 의 `inputs/abide/{n0_k0, n1_k0–4, n2_k0–4}/abide.npy` 의 sha256, `cc200_coords.json` 은 쓰지 않음.
  - environment: venv-mobse-v2 의 pip freeze (I1 a1 사고 재발 방지 — `PYTHONPATH` 를 구동기 안에서만 씀).
- 설계 (권고안): D1 (a) 963 명 공통 · D2 (a) n0–n2 · D3 기록 · D4 (a) 100 시점 · D5 (a) config 0 · D6 I1 규칙 · D7 I1 과 같음 · D8 하지 않음.
- 산출 배치: I1 과 같은 `<out>/abide/mobse_{mean,embedding}/<cond>/k<k>/r<seed>/f<fold>/predictions.jsonl` (피험자 index · label · p1).
- 분석: I1 `analyze.py` 와 같은 계산을 963 명에 — **공개 모델 셋도 같은 963 명으로 다시 냄** (새 학습 없음). 판정 문장 · bootstrap 2,000 · seed 20261006 · 다중성 보정 없음 (탐색적) 은 I1 과 같음.
- 남은 구현 (잠금 전): 본 구동기 (PCA · bank 공유 캐시 · 동시 실행 · 실패 기록), 963 명 분석 감싸개, 잠금 생성 · 검증 스크립트, 시험 몇 개 (test 피험자가 PCA · bank · epoch 선택에 들어가지 않음, 산출 배치).
- 실행 순서: 구현 → 구동기 smoke (fit 1–2) → 잠금 생성 → 본 실행 → 분석 → 보고서 2.x 에 "같은 조건 비교" 장 추가.
