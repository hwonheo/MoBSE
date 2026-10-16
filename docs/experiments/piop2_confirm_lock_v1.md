# PIOP2 확증 잠금 문서 v1 · 2026-10-16

> **무엇인가**: I3 (PIOP1) 에서 결과를 본 뒤 얻은 단서 두 가지를 **아직 쓰지 않은 PIOP2 에서 한 번만** 확증하는 실행의 잠금 문서다
> (결정 77 방향 D · 결정 78 설계값). 이 문서 · 코드 · 자료 · 환경은 `scripts/piop2_confirm/build_lock.py` 가 하나의 lock_hash 로 묶는다.
> **본 실행 전까지 PIOP2 의 성능 값은 아무것도 보지 않았다** — 본 것은 events (블록 구조) · 적격 목록 · 추출 QC 뿐이다.
> 초안 `docs/experiments/piop2_confirm_lock_draft_2026-10-16.md` 를 대체한다.

## 1. 확증할 주장과 판정 규칙

| # | 주장 | 대조 |
|---|---|---|
| P1 | routing 을 고정한 embedding MoBSE (B emb) 의 블록 정확도가 같은 FC 입력의 logistic (S) 보다 높다 | B_embedding − S_fc_logistic |
| P2 | 그 모델 안에서 정렬된 뇌 graph bank 가 순열 null bank 보다 높다 | B_embedding − D_embedding (순열) |

- **판정**: 두 주장을 Bonferroni 로 묶은 **97.5 % 피험자 단위 bootstrap percentile CI** (seed 20261016, 10,000 회). **하한 > 0 이면 "확증", 아니면 "확증 못 함"**. "확증 못 함" 은 "기여 없음" 이 아니다.
- **주 판정은 8 블록 전체.** 첫 짝 (블록 0 · 1) 을 뺀 판은 민감도로 함께 보고하며 판정을 바꾸지 않는다.
- **P2 의 null 민감도**: B − D emb spin · B − D emb rewire 를 같은 방식으로 보고하되 판정에 쓰지 않는다. **순열 null 은 약한 null 이다** — 공간 구조 (spin) · 차수 (rewire) 를 보존하지 않으므로 P2 가 확증돼도 "공간 구조를 넘어선 정렬의 기여" 라고 쓰지 않는다.
- δ 0.02 는 참고 표기만 한다.

## 2. 자료 · 분할

| 항목 | 값 |
|---|---|
| 학습 · val | PIOP1 (ds002785) 157 명 — I3 재추출 (결정 68) 전체 길이 시계열. seed 20261017 무작위로 **val 31 · 학습 126** |
| 평가 | **PIOP2 (ds002790) 적격 189 명 전원** (`derivatives_v3_piop2/cohort_piop2/subjects.jsonl`, 세 과제 모두 요구) |
| PIOP2 추출 | `scripts/piop2_confirm/extract.py` (I3 추출과 같은 단계, dataset 인자만 다름), h197, 10-16 15:17–15:22 KST, **189/189 ok · WI-02 QC 189 통과 · 프레임 135**. 같은 스크립트로 PIOP1 두 명을 뽑으면 I3 (Mac) 추출과 시계열 최대 차 2.4e-7, 시각 동일 |
| 블록 | 222 run 전부 `control emotion` × 4 · 30 s × 8 (PIOP1 과 같음). lag 6 s · 15 frame · 블록 안 ROI z-score |
| bank · null | 학습 126 명의 rest 창 (I3 와 같은 PIOP1 rest 창) 으로 K=3 bank, null seed 1729 (순열 · spin · rewire). PIOP2 rest 는 쓰지 않음 |

## 3. 모델 · 학습

- 칸: **B emb · D emb (순열 · spin · rewire)** — I3 의 `core.fit_one` 그대로 (config 0, update 예산 5,000, epoch 상한 없음, val loss 최소 epoch 의 checkpoint). seed 42 · 43 · 44 의 test 확률을 평균해 0.5 로 자름.
- **S** (blockz FC logistic, C=1) · 활성 참고값 — I3 의 `core.fit_s` 그대로.
- **결정론**: fit 마다 `mobse.v2.fitting.apply_determinism` (deterministic algorithms · cuDNN deterministic · `CUBLAS_WORKSPACE_CONFIG=:4096:8`) 을 켜고 상태를 `determinism.json` 에 남김. 이 설정 없이는 같은 seed 재실행이 확률 최대 0.41 · 선택 epoch 116 대 111 로 갈렸고 (smoke_a1), 설정 뒤에는 B emb · D emb spin 재실행이 예측 · epoch 기록 모두 바이트 동일 (smoke_a2).
- 실행 호스트 h197 (CUDA, torch 2.10.0+cu128), tmux, 동시 2. I3 (Mac MPS) 와 수치 환경이 다르다.

## 4. smoke (PIOP1 만, PIOP2 를 읽지 않음)

- `smoke_a2` (가짜 분할: 학습 100 · val 31 · test 26, seed 42): prep · fit 4 · S · 분석 모두 rc 0, `ALL_DONE`. fit 55–72 s (동시 2). 값은 판정에 쓰지 않는다.

## 5. 미리 적는 한계

1. PIOP2 를 한 번 쓰면 다시 hold-out 으로 쓸 수 없다. 같은 연구 환경이라 cross-site 가 아니다.
2. 조건과 시간 위치가 PIOP2 에서도 겹친다 — P1 이 "조건" 이 아니라 "시간 위치" 를 더 잘 잡는 모델일 가능성을 배제하지 못한다.
3. 검정력 (`scripts/piop2_confirm/power.py`, 학습 없음): P(97.5 % 하한>0) — P1 0.74 (θ = I3 점추정) · 0.21 (절반), P2 0.92 · 0.35. I3 점추정은 결과를 보고 고른 값이라 실제 효과는 더 작을 가능성이 크다.
4. 학습 자료는 PIOP1 의 I3 재추출 (Mac), 평가 자료는 PIOP2 의 h197 추출이다 — 같은 코드이나 호스트 간 부동소수 차이 (약 2e-7) 가 있다.
5. 학습은 한 번 (outer 하나, seed 3) 이라 재학습 변동은 seed 평균으로만 줄어든다.

## 6. 산출

h197 `MoBSE_dataset/piop2_confirm/main/<run_id>/` — `run_config.json` · `split.json` · `prep/` · `fits/` · `s/` · `analysis/analysis.json` · `status.log`.
