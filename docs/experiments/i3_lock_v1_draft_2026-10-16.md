# I3 잠금안 초안 v1 — PIOP1 emomatching 블록 조건에서 H1 · H2 (결정 67 · 68)

> **초안이다. 잠금이 아니다.** 결정 68 (Mac 개시) 에서 "① 본 트랙 착수 · main 126 명 재추출" 로 읽은 범위의 다음 단계로,
> 선생님께 고를 거리를 모은 것이다. 표의 "권고" 는 결정이 아니다. 근거는 범위 확인 메모
> `docs/experiments/h1h2_scoping_2026-10-16.md`. 결정 원문은 `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.31 · §11.32.
> 결과를 본 뒤의 설계 변경이므로 **새 탐색 버전 (exploratory v4)** 이다. v1 잠금 · gate rev77 · v3 잠금 · I1 잠금은 바꾸지 않는다.

## 1. 질문

- 원래 질문 그대로: training-rest 로 만든 graph bank 의 **해부학적 정렬 (H2: A−C)** 과 **입력 의존 routing (H1: A−B)** 이
  포화되지 않은 과제 target 에서 각각 추가 가치를 주는가.
- target: PIOP1 emomatching 의 블록 조건 — control 0 · emotion 1. 미사용 피험자 (outer test) 에서 평가.
- v1 과 다른 점: target (run identity → 과제 안 블록 조건), 창 (60 s 고정 4 개 → 30 s 블록 8 개), 입력 (blockz).

## 2. 자료 · 분할

| 항목 | 내용 | 근거 |
|---|---|---|
| 피험자 | PIOP1 main 126 명 (pilot 31 명은 기술 결정에만 썼고 제외) | WI-03 분할 `ace5f4a41446` |
| 분할 | v1 outer 5 fold (26/25/25/25/25) · outer 마다 inner 3 fold 그대로 | 같은 `folds.json` |
| 과제 시계열 | WI-02 와 같은 단계로 **전체 길이 재추출** (nuisance + 차단대역 DCT 동시 회귀 0.008–0.2 Hz → Schaefer-100 → ROI z-score) | `scripts/h1h2_scope/i3_extract_pilot.py` (pilot 31 에서 저장 창과 최대 차이 2.4e-7) |
| rest (bank) | `derivatives_v3` 저장 rest 60 s 창 (사람당 4 개) 그대로 | v1 bank 와 같은 입력 |

## 3. 창 · 입력

| 항목 | 권고 | 대안 | 근거 |
|---|---|---|---|
| 블록 | events 에서 같은 trial_type 연속 구간 (30 s · trial 6 개) | — | pilot 31 명 전부 8 블록 · 30 s |
| 창 | [블록 시작 + **lag**, 끝 + lag) 의 15 frame | — | TR 2 s |
| **lag** | **6 s** | 4 s · 5 s | pilot 블록 FC BA 4 s 0.55 · 6 s 0.66 (**pilot 에서 두 값을 보고 고름** — 기록) |
| **입력** | **blockz** (블록 안 ROI 별 평균 0 · 분산 1) | 원 z-score | 원 입력은 활성만으로 BA 0.95–0.98 (천장). blockz 는 활성 정보를 지워 FC 만 남김 |

## 4. 모델 · 학습

| 항목 | 권고 | 대안 | 근거 · 비용 |
|---|---|---|---|
| 칸 | A–D × {mean, embedding} + NG + SG (mean) = **10 칸** | A–D 만 (8) | v1 · v3 와 같은 칸 |
| S | blockz 창 FC (LedoitWolf → Fisher z) logistic | + 활성 logistic (원 입력) 을 **참고값**으로 보고 | 활성 참고값은 "지운 정보의 크기" 를 보여 줌 |
| bank · PCA | K=3 · PCA 10, 학습 피험자 rest 창으로 fit | — | 결정 33 (PCA 10 고정) |
| config | **config 0 고정** | grid 를 가장 큰 수준에서 한 번 (결정 33 방식) | I1 ABIDE 팔 D5 선례. grid 를 열면 fit 이 몇 배 |
| epoch 선택 | **(가) inner fold 0 의 val (34 명) 로 best checkpoint, 그 모델로 test 예측** | (나) inner 3 fold 에서 고른 epoch 를 outer 학습 100 명에 다시 학습 (fit 4 배) | (가) 는 ABIDE 팔과 같음 · 학습 66 명만 씀. (나) 는 v3 방식 |
| 학습 규칙 | update 예산 5,000 · epoch 상한 없음 · best 는 어느 epoch 에서든 | — | 결정 31 · 32 |
| seed | 42 · 43 · 44 | — | v2 `MODEL_SEEDS` |
| null (H2 의 C · D) | 주: ROI 순열 seed 1729 | + spin · rewire 각 1 (민감도) | v3 `make_null_bank` 세 종류. Schaefer 좌표가 있어 spin 가능 |

## 5. 평가 · 판정

- 블록 단위 정확도 (블록이 사람마다 4:4 라 BA 와 같음), seed 3 개의 블록 확률 평균을 0.5 로 자름.
- 주 contrast: H1 A−B · H2 A−C (구조마다). CI 는 **피험자 단위 bootstrap**, v1 규칙 97.5 % (주 contrast 2 개 Bonferroni).
- 보조 (95 %, 기술적): A−S · A−NG · A−SG · null 민감도.
- **δ**: v1 의 0.02 를 그대로 두되, 아래 G-b 결과대로 **탐지할 수 없는 크기**임을 미리 적는다 (결정 29: 차단 아님, 보고).

### G-b (학습 없음, `scripts/h1h2_scope/i3_gb_power.py`, 126 명 × 8 블록, 반복 1,000 · bootstrap 2,000)

| π (판정이 갈리는 비율) | δ 0.02 의 P(하한 > 0) | 처음 80 % 를 넘는 δ (격자 0.02 간격) |
|---|---|---|
| 0.10 | 0.15–0.42 | 0.04–0.06 |
| 0.20 | 0.14–0.21 | 0.06 |
| 0.30 | 0.12–0.13 | 0.06 |
| 0.40 | 0.09–0.12 | 0.08 |

- 범위는 사람 사이 이질성 τ 0 · 0.05 · 0.10. 보정: δ 0 에서 0.007–0.017 (이론 0.0125).
- **재학습 변동은 넣지 않았다** — 실제 검출력은 이보다 낮을 수 있다 (결정 35: v3 에서 재학습 SD ≈ bootstrap 반폭).
- 읽는 법: δ 0.02 는 이 설계로 잡을 수 없다. 잡을 수 있는 크기는 대략 0.04–0.08.

## 6. fit 수 · 비용 (Mac MPS, 직렬) [추정]

| 구성 | fit | 시간 |
|---|---:|---|
| 10 칸 × outer 5 × seed 3, epoch (가) | 150 | 약 2 h (판당 약 45 s — pilot smoke 25–42 s 에 창 수 비례) |
| + null 민감도 (spin · rewire × C · D × 2 구조 × 15) | +120 | +약 1.5 h |
| epoch (나) 를 고르면 | × 4 | 약 8 h (+민감도 6 h) |

## 7. 잠금 전에 본 것

- pilot 31 명: 블록 구조 · 기준선 (lag 4 · 6 s × 활성 · FC · fc_taskreg) · FC 안정성 · MoBSE smoke 7 판의 val 값 (6 명).
- main 126 명: **재추출 QC 만** (프레임 수 · WI-02 QC 판정 · 저장 창과의 대조). label 과 성능 값은 보지 않는다.
- G-b simulation.

## 8. 정할 것 (TUI 로 올림)

1. lag (권고 6 s) · 입력 blockz (권고)
2. 칸 10 (권고) / A–D 8
3. epoch 선택 (가) (권고) / (나)
4. null 민감도 포함 (권고: 포함, +1.5 h) / 주 null 만
5. δ 표기 — 0.02 유지 + 탐지 불가 사전 기록 (권고) / δ 를 G-b 크기로 바꿈
