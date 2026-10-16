# I3 잠금 v1 — PIOP1 emomatching 블록 조건에서 H1 · H2 (exploratory v4, 결정 67 · 68 · 69)

> 이 문서는 `scripts/i3/build_lock.py` 가 해시하는 잠금 문서다. 잠금 뒤 바꾸면 잠금 검증이 실패한다.
> 초안 · 근거: `docs/experiments/i3_lock_v1_draft_2026-10-16.md`, 범위 확인 메모 `docs/experiments/h1h2_scoping_2026-10-16.md`.
> 결정 원문: `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.31 – §11.33.
> 결과를 본 뒤의 설계 변경이므로 **새 탐색 버전**이다. v1 측정 · 구현 잠금, gate rev77, v3 잠금, I1 잠금은 바꾸지 않는다.

## 1. 질문

- training-rest 로 만든 graph bank 의 **해부학적 정렬 (H2: A − C)** 과 **입력 의존 routing (H1: A − B)** 이 포화되지 않은 과제
  target 에서 각각 추가 가치를 주는가.
- target: PIOP1 emomatching 의 블록 조건 (control 0 · emotion 1), 미사용 피험자 (outer test) 에서 평가.

## 2. 결정 원문

- 결정 67 (TUI): "① 과 ② 둘 다" (범위 확인). 결정 68 (채팅): "일단 여기 mac에서 개시." (Mac 호스트; ① 착수 · main 재추출은 해석).
- 결정 69 (TUI): "8 블록 + 첫 짝 제외 민감도 (Recommended)" · "10 칸 · (가) (Recommended)" · "순열 + spin·rewire 민감도 (Recommended)" ·
  "0.02 유지 + 구현·잠금 (Recommended)". 이어진 지시 "백그라운드 처리시 tmux 사용".
- **본 실행은 이 잠금 뒤 다시 승인을 받는다** (결정 69 "본 실행은 다시 물음").

## 3. 자료 · 분할

| 항목 | 내용 |
|---|---|
| 피험자 | PIOP1 main 126 명. pilot 31 명은 기술 결정 (lag · 입력 · smoke) 에만 썼고 분석에서 뺀다 |
| 분할 | WI-03 `folds.json` (split_hash `ace5f4a41446`) outer 5 fold (26/25/25/25/25). outer 마다 **inner fold 0** 의 train (66 명 안팎) 으로 학습, val (34 명 안팎) 으로 best checkpoint, outer test 로 예측 |
| 과제 시계열 | WI-02 와 같은 단계로 전체 길이 재추출 (`scripts/h1h2_scope/i3_extract_pilot.py`). 157 명 전부 ok · WI-02 QC 통과 157 · 프레임 135 · `derivatives_v3` 저장 창과 최대 차이 4.8e-7 |
| rest (bank) | `derivatives_v3` rest 60 s 창 (사람당 4 개) |
| 실행 위치 | Mac (`.venv`, torch MPS), 자료 `data/h1h2_scope/aomic/` (gitignore) — 파일마다 sha256 을 잠금이 담음 |

## 4. 창 · 입력

| 항목 | 내용 |
|---|---|
| 블록 | events 의 같은 trial_type 연속 구간. 사람마다 8 개 · 30 s · c e c e c e c e (157 명 전부 같은 구조 — 아니면 멈춤) |
| 창 | [블록 시작 + **6 s**, 끝 + 6 s) 의 **15 frame** (아니면 멈춤) |
| 입력 | **blockz** — 블록 안 ROI 별 평균 0 · 분산 1 (상수 ROI 가 있으면 멈춤) |
| PCA gate 특징 | blockz 창의 shrinkage 상관 (LedoitWolf) → Fisher z → 학습 피험자 rest 로 fit 한 scaler + PCA 10 |

## 5. 모델 · 학습

| 항목 | 내용 |
|---|---|
| 칸 (주 10) | A · B · C · D × {mean, embedding} (`MoBSEv3`), NG · SG (`mobse.v2` 비교 모델) |
| 칸 (null 민감도 8) | C · D × {mean, embedding} × {spin, rewire} |
| bank | K=3, 학습 피험자 rest 창, `bank_seed(outer, 0)` |
| null | 주: ROI 순열 seed 1729. 민감도: spin (Schaefer-100 parcel 중심 · 반구 유지, seed 1729) · degree 보존 rewire (seed 1729 + k) — `mobse.v3.templates.make_null_bank` |
| S | blockz 창 FC (위 Fisher z 4,950) → StandardScaler → logistic C=1, 같은 학습 피험자 |
| 참고값 | 활성 logistic — **원 입력** 블록 평균 (100) → logistic C=1. blockz 가 지운 정보의 크기를 보이는 참고값이며 비교 칸이 아님 |
| config | 0 고정 (`mobse.v2.train.build_grid`) |
| 학습 | batch 32 · grad clip 1 · AdamW · update 예산 5,000 (epoch 상한 없음) · best = val 블록 평균 cross-entropy 최소 (같으면 앞 epoch) |
| seed | 42 · 43 · 44 |
| fit 수 | (10 + 8) 칸 × 5 outer × 3 seed = **270** |

## 6. 평가 · 판정 (`scripts/i3/analyze.py`)

- 칸마다 seed 3 개의 블록 확률 평균 → 0.5 로 자름 → 블록 정확도 (사람마다 4:4 라 BA 와 같음). 126 명 × 8 = 1,008 블록.
- CI 는 **피험자 단위 bootstrap** 10,000 회 (seed 20261016), 모든 칸에 같은 재표집 (짝지은 비교), percentile.
- **주 contrast (97.5 %)**: 구조마다 H1 = A − B, H2 = A − C.
- **민감도 (97.5 %)**: 첫 짝 (블록 0 · 1) 을 뺀 6 블록으로 주 contrast 를 다시.
- **보조 (95 %, 기술적)**: 구조마다 A − S · A − NG · A − SG · A − C_spin · A − C_rewire.
- 판정 표기: 하한 > δ · 하한 > 0 · CI 0 포함 · 상한 < 0. **δ = 0.02**.
- **δ 0.02 는 이 설계로 탐지할 수 없다** (G-b, 학습 없음, `scripts/h1h2_scope/i3_gb_power.py`): 126 명 × 8 블록에서 δ 0.02 의 P(하한 > 0)
  0.09–0.42, 처음 80 % 를 넘는 δ 는 0.04–0.08 (π 0.1–0.4). 재학습 변동은 넣지 않았다. "하한 > δ" 가 나오지 않는 것은 예상된 결과다.
- 붕괴 표기: test 또는 val 확률 SD < 1e-3 인 fit 수. 판정은 전체 fit 으로 하고 붕괴 수를 함께 적는다 (I1 결정 55-1 과 같은 방식).

## 7. 알려진 위험

- **조건과 시간 위치가 겹친다** — 157 명 전원이 c e c e c e c e. pilot 에서 control 안 뒤쪽 대 앞쪽 BA 0.758, 첫 짝을 빼면 조건 구분
  BA 0.657 → 0.591. 모든 칸이 같은 입력을 받으므로 칸 사이 차이에는 같은 방식으로 작용하나, 절대 정확도는 시간 위치 신호를 포함할 수
  있다 → 첫 짝 제외 민감도로 함께 보고.
- **신호가 약하다** — pilot blockz FC logistic BA 0.66. pilot smoke 에서 train AUC 0.93–1.00 (과적합).
- **MPS 결정론** — smoke (pilot) 에서 A_mean · NG (seed 42) 를 단독으로 다시 돌린 결과, 2 개 동시 실행 원판과 test 예측 · epoch 별
  val loss 가 **바이트 동일** (최대 차이 0, 선택 epoch 113 · 9 같음). 다른 칸 · 다른 장비에서의 동일성은 재지 않았다.
- 학습은 inner fold 0 의 train 만 쓴다 — outer train 100 명 중 34 명은 epoch 선택에만 쓰인다.

## 8. 잠금 전에 본 것

- pilot 31 명: 블록 구조 · 기준선 (lag 4 · 6 s × 활성 · FC) · FC 안정성 · 시간 위치 점검 · MoBSE smoke (범위 확인 7 판 · 구동기 smoke 18 판) 의 val · test 값.
- main 126 명: 재추출 QC 만 (프레임 수 · WI-02 QC · 저장 창 대조 · 블록 구조). **label 과 성능 값은 보지 않았다.**
- G-b simulation.

## 9. 실패 규칙 · 산출

- 잠금 검증 (`build_lock.py --verify`) 이 rc 0 이 아니면 구동기가 아무것도 시작하지 않는다.
- prep 실패 · fit 실패는 `fails_<phase>.json` 에 모으고 그 단계에서 멈춘다 (rc 1). 이어 하기는 같은 run-id 로 다시 띄워 `summary.json`
  이 없는 fit 만 돈다. run_config 가 다르면 멈춘다.
- 산출: `data/i3/main/<YYYYMMDD>_<lock8>_a<n>/` — `run_config.json` · `status.log` · `prep/` · `fits/<칸>/outer<k>/seed<s>/` ·
  `s/` · `analysis/analysis.json`. 같은 run 을 덮어쓰지 않으며 재시도는 attempt 번호를 올린다.
- 실행은 tmux 세션 (`i3main`), 로그 `driver.out` 끝에 rc.
