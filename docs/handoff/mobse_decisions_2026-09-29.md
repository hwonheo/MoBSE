# MoBSE — 결정 25 (2026-09-29, 터미널 Claude Code 세션)

> **09-29 이후 현행 정본은 이 문서 + `mobse_main_oof_2026-09-28.md`.** 결정 0–22 원문·운영 규칙·마감 절차는 `mobse_redesign_g0_handoff_2026-09-17.md`, 결정 23·24 와 main OOF 실행 기록은 `mobse_main_oof_2026-09-28.md` 를 따른다. 어긋나면 이 문서가 앞선다.
> 수집 방식: 2026-09-29 09:5x KST, 선택 TUI (AskUserQuestion) 5문항. 선택지 문안은 main_oof 문서 "gate 표기 권고 1–6", midreview 3절 선택지 (가)/(나)/(다), interpretation 3절 (PIOP2·WI-08) 에서 가져왔다.
> **정본은 이 저장소 `docs/handoff/` 다.** claude.ai Project "MoBSE" 사본 동기화는 하지 않는다 —
> 선생님 지시 (2026-09-29): "claude.ai Project 에 올리는 일은 하지말고 docs/handoff 문서 갱신만.., 그리고 개발 진행은 승인".

## 결정 25 (선택 결과)

| # | 물음 | 선택 |
|---|---|---|
| 25-1 | gate evidence 표기 | **권고 1–6 전부 적용** |
| 25-2 | H2 (A−C) 방향 | **(다) WI-09 만 먼저 (PIOP2 미사용) 후 (나) 판단** |
| 25-3 | PIOP2 외부 평가 (WI-08) 착수 | **지금은 승인하지 않음** |
| 25-4 | A−S (단순 FC 기준선 100%) 처리 | **추가 분석 후 판단** |
| 25-5 | WI-09 일정 | **기록·커밋 마친 뒤 착수** |
| 25-6 | A−S 추가 분석 범위 | **새 학습 없는 진단만** |

### 25-1 정한 것 — gate 표기 (main_oof 문서 권고 1–6 그대로)
1. G3 Internal release → `cleared`
2. G2 Implementation lock → `planned` → `cleared`
3. G0 Provenance → `cleared`, `unresolved` 에서 U3·U6 제거, U10 은 G1 한계로 옮겨 적음
4. "blocked by G0" (G2·G3·G5) · "blocked by G0/G1" (G4) 표기 삭제
5. G1 Measurement lock → 검사 판정은 `fail` 2건 그대로, `status` 를 새 값 `cleared_with_limitations` 로
6. G4 (외부) · G5 (해석) 는 `planned` 유지

**정하지 않은 것**: G1 fail 2건 ([0] group_id · [6] δ 정밀도) 을 pass 로 바꾸는 것 (계획서 P4·§8 이 정한 알려진 한계로 남김).

### 25-2·25-5 정한 것 — H2 방향과 WI-09
- 현 버전에서 **null 민감도 (WI-09) 만** 수행: seed 1730–1733, C/D 120 fit, 재튜닝 없음. null 간 편차를 본 뒤 (나) (새 탐색 버전 설계) 를 다시 판단한다.
- 착수 시점: **09-28 결과의 기록 (보고서 부록 + gate evidence 새 revision) → 마감 5+1 → 커밋을 마친 뒤.** 산출물 이력이 섞이지 않게 한다.

**정하지 않은 것**: 새 탐색 버전 설계 착수, 현 버전의 설계·grid·δ·N 변경.

### 25-3 정한 것 — PIOP2
- **PIOP2 외부 평가 (WI-08) 는 지금 착수하지 않는다.** H2 방향 (25-2) 결과를 본 뒤 다시 판단한다.
- 따라서 외부 S·NG·SG 포함 여부, U17 (PIOP1–PIOP2 참가자 중복) 의 해소 판단도 **미정** — 승인 시점에 함께 정한다.
- 미구현 항목은 그대로 남는다: (9,9) external final fit 배선, PIOP2 평가 경로, `external_lock.json` 생성·검증, 시험·돌연변이, 측정·구현 잠금 새 판과 gate revision.

### 25-4·25-6 정한 것 — A−S
- A−S (A 0.877 대 S 1.000, −0.123 [−0.163, −0.083]) 의 논문·다음 단계 처리는 **추가 분석 뒤에 정한다.**
- 그 추가 분석은 **새 학습 없이 기존 산출물만 읽는 진단**으로 한정한다 (예: S 가 쓴 FC 특징의 변별력, A 의 gate PCA 10 차원이 버리는 정보량, run 별 오답 패턴). 새 fit·설계 변경은 하지 않으므로 새 exploratory version 을 열 필요가 없다.

**정하지 않은 것**: target 난이도·교란 (촬영 순서·움직임 등) 의 본격 조사 — 하려면 별도 exploratory version.

## 이 결정으로 열린 작업 (순서)
1. 보고서 새 부록 (스레드 측정 · main OOF · primary · 보조 비교) 작성.
2. gate evidence 새 revision — 기록 부분 (`data_root_outputs` 에 09-28 산출 sha, rev72 `not_done` "명세 6" 정정) + **25-1 의 gate 표기 변경**.
3. 마감 5+1 단계 (h197, 전부 rc=0) → 커밋 (**푸시 안 함**).
4. `resource_budget.md` 에 스레드 고정 반영, 인수인계 문서에 결정 23·24·25 행 합치기, CLAUDE.md 포인터 갱신.
5. 그 뒤 WI-09 (25-5).
6. A−S 진단 (25-6) — 시점 미정, 가역.

## 결정 25 이후 진행 (2026-09-29)

선생님 승인 원문: **"개발 진행은 승인"** — 위 "이 결정으로 열린 작업" 1–3 (부록 → gate revision → 마감 5+1 → 커밋) 과 그 뒤 WI-09 를 진행한다.

| 항목 | 상태 |
|---|---|
| 보고서 부록 BT (스레드 고정)·BU (main OOF 실행)·BV (primary 결과)·BW (보조 비교)·BX (결정 25·gate 표기) | 작성 완료 |
| gate evidence **rev73** — 09-28 실행 기록 + 결정 25-1 표기 적용 + rev72 `not_done` "명세 6" 정정 | 적용 완료 |
| `reports/resource_budget.md` 9.2 (스레드 고정·main 규모 실측) | 작성 완료 |
| 인수인계 문서 (`mobse_redesign_g0_handoff_2026-09-17.md`) 에 결정 23–25 요약 행 | 추가 완료 |
| 마감 5+1 단계 (h197) → 커밋 (푸시 안 함) | 아래 기록 |
| WI-09 null 민감도 | 커밋 뒤 착수 |

### gate rev73 판정표

| Gate | status | checks |
|---|---|---|
| G0 Provenance | `cleared` | 10 (pass 10) |
| G1 Measurement lock | `cleared_with_limitations` | 8 (pass 6 · fail 2 — group_id, δ 정밀도) |
| G2 Implementation lock | `cleared` | 5 (pass 5) |
| G3 Internal release | `cleared` | 3 (pass 3) |
| G4 External release | `planned` (U17 만 남음) | 1 (pass 1) |
| G5 Interpretation | `planned` | 0 |

## 결정 26 — WI-09 구현 방식 (2026-09-29)

세션 보고 (원문 요지): WI-09 는 null seed 1730–1733 로 C/D 를 다시 학습하는데, `fit` CLI 는 null seed 를 config `bank.null_seed` 에서 읽고 `mobse/v2/config.py` 검증기가 그 값을 코드 상수 1729 로 잠가 둔다. seed 를 바꾸면 `config_hash` 가 바뀌고 `evaluate` 는 fit manifest 의 `config_hash` 가 다르면 거부한다 (`cli.py:1738`) → main 의 A·B outer 예측을 그대로 재사용할 수 없다. 선택지 (가) seed 마다 A·B 도 같이 재실행 (코드·잠금 불변) / (나) `config.py` 잠금을 풀고 별도 analysis config (측정 잠금 재생성 + gate 새 revision).

**선생님 회신 (원문): "가. 로 진행"**

**정한 것**: (가) — null seed 마다 A·B·C·D outer 60 fit 을 모두 돌린다. **총 240 fit** (계획서의 "C/D 120 fit" 은 그중 seed 에 실제로 의존하는 부분이고, A·B 120 은 `config_hash` 일치를 위한 재계산이다). `mobse/v2` 와 잠금은 바꾸지 않는다 — null seed 는 구동기가 **프로세스 안에서만** `cli.load_config` 를 감싸 덮는다 (pilot end-to-end 의 `MAX_EPOCHS` 덮기와 같은 방식, 부록 BQ.1).

**정하지 않은 것**: `mobse/v2` 수정, 측정·구현 잠금 재생성, WI-09 의 나머지 항목 (routing 고정/shuffle, nuisance/time 기준선, 비용, window·atlas·GSR·K 민감도) — 이번 범위는 **null 민감도뿐**이다 (결정 25-5).

**착수 전 확인**: A outer fit 1 건을 seed 1730 판으로 돌려 main 과 창 예측 값·checkpoint sha 가 같은지 본다. 다르면 멈추고 보고한다 (A 는 null bank 를 쓰지 않으므로 같아야 한다).

## WI-09 null 민감도 — 완료 (2026-09-29, gate rev74, 부록 BY)

- 산출 h197 `$D/null_sens/20260929_97e434a_a1/`. HEAD `97e434a`, preflight 4종 rc=0, 추적 파일 381 사본 동일.
- 착수 전 확인 통과: seed 1730 판 A outer fit 1건이 main 과 **창 예측 208개 전부 동일·checkpoint sha 동일** (다른 것은 `config_hash`·`null_seed` 기록뿐).
- 실행: outer **240 fit** 01:40:37Z → 03:03:12Z (**1 h 22 m 35 s**, 실패 0) → seed 마다 evaluate·report rc=0 → `ALL_RC=0`.
- 점검 (네 seed 공통): outer 60 · 고유 checkpoint 60 · 창 예측 12,096 · **누설 0** · 배정 밖 0 · A·B 30건 main 과 차이 0 · report g3 pass.

| null seed | C | D | **H2 A−C** (97.5% CI) | interaction (95% CI) |
|---|---:|---:|---|---|
| **1729 (primary)** | 0.8929 | 0.7897 | **−0.0159** [−0.0516, +0.0198] | +0.0516 [+0.0040, +0.0992] |
| 1730 | 0.8770 | 0.7579 | 0.0000 [−0.0238, +0.0238] | +0.0357 [−0.0079, +0.0794] |
| 1731 | 0.8770 | 0.7579 | 0.0000 [−0.0357, +0.0357] | +0.0357 [−0.0079, +0.0833] |
| 1732 | 0.8770 | 0.7222 | 0.0000 [−0.0317, +0.0317] | 0.0000 [−0.0397, +0.0437] |
| 1733 | 0.8929 | 0.7659 | −0.0159 [−0.0437, +0.0119] | +0.0278 [−0.0079, +0.0635] |

A 0.8770 · B 0.7222 · H1 A−B +0.1548 [+0.0952, +0.2143] 은 다섯 판 모두 같다 (A·B 는 null 과 무관).

**두 가지 읽을 거리 (기록 — primary 판정은 바꾸지 않음, 계획서 §8)**
1. **A−C 는 다섯 판 전부 [−0.016, 0.000] 이고 CI 가 모두 0 을 포함한다.** H2 가 불확실한 것은 하필 고른 순열 (1729) 때문이 아니다.
2. **보조 interaction 의 판독은 null 에 따라 바뀐다.** primary 판만 하한 +0.0040 > 0 이고, 민감도 네 판은 모두 하한 ≤ 0 이다 — 그 보조 판독은 순열 하나에 기대고 있었다. C 는 거의 안 움직이고 (0.8770–0.8929) D 가 더 흔들린다 (0.7222–0.7897).

**한계**: 순열 5개로는 null 분포를 만들 수 없다 (midreview 2절 약점 4). 공간 보존 null (spin)·degree 보존 rewiring 은 계획 밖이다.

### 이제 선생님 판단이 필요한 것
결정 25-2 의 (다) 는 "WI-09 결과를 본 뒤 (나) 를 판단" 이었다. WI-09 가 끝났으므로 **(나) — 현 버전을 내부 결과로 마감하고 PIOP2 는 보류한 채 새 탐색 버전을 설계할지** 를 정할 차례다. 판단 재료는 위 두 읽을 거리와 `mobse_h2_midreview_2026-09-29.md` 3절이다.

## 결정 27 — 진로 (나) 확정 · interaction 판독 철회 (2026-09-29, 선택 TUI)

| # | 물음 | 선택 |
|---|---|---|
| 27-1 | 결정 25-2 의 (다) 가 예고한 "WI-09 뒤 (나) 판단" | **(나) 로 간다** |
| 27-2 | WI-09 가 드러낸 보조 interaction 문제 | **주장에서 뺀다** |

**정한 것**: 현 버전 (재설계 v1) 은 **내부 결과로 마감**한다 · **PIOP2 는 열지 않는다** (결정 25-3 의 보류가 확정) · 새 탐색 버전을 설계한다 · 보고서·논문에서 "interaction 이 추가 기여를 지지한다" 는 서술을 쓰지 않는다.

**정하지 않은 것**: 새 탐색 버전의 내용 (target·모델 구조·null 설계·δ·N) — 설계안을 따로 올린다. PIOP2 를 영영 안 쓴다는 뜻은 아니다 (새 버전의 확증용으로 남긴다).

### 사전등록 이탈 — 사유 (부록 CA.3, 최종 보고서 WI-11 에 옮겨 적을 것)
계획서 §8 은 "내부 결과가 음성이어도 외부 검증 수행" 이라 적었다. (나) 는 그 항목을 수행하지 않으므로 이탈이며, 사유는 넷이다.
1. WI-09 가 H2 의 불확실이 순열 선택 탓이 아님을 보였다 → 같은 설계로 PIOP2 를 열면 같은 이유로 다시 불확실할 가능성이 크다 [추정].
2. PIOP2 는 한 번만 열 수 있다 — 확증력 없는 실행에 쓰면 새 설계의 확증 수단이 사라진다.
3. target 자체가 이 가설에 부적절하다는 증거가 모였다 (S 1.000 · NG ≈ A · 부록 BZ).
4. 내부 결과 (H1 지지 · H2 불확실) 는 그대로 보고한다 — 음성 결과를 숨기려는 생략이 아니다.

### interaction 철회 (27-2)
primary 판 (seed 1729) 만 하한 +0.0040 > 0 이고 민감도 네 판은 모두 하한 ≤ 0 이다. 값을 적을 때는 "순열 하나에 기댄 판독" 단서를 함께 적는다. `statistics.json` 의 수치와 그 파일이 낸 판독 문구는 그대로 둔다 (§8 — 민감도를 primary 에 역반영하지 않는다).

## A−S 진단 — 완료 (결정 25-6, gate rev75, 부록 BZ)

새 학습 없이 기존 산출물만 읽었다. 산출 `$D/main_oof/20260928_1cd4054_aux_a1/diagnostic/as_diagnostic.json` (sha256 `e86625d873a9…`).

| 칸 | 두 run 다 틀림 | 한 run 틀림 | 만점 | 틀린 run | emo / wm | 틀린 run 중앙 margin |
|---|---:|---:|---:|---:|---:|---:|
| **S** | 0 | 0 | **126** | 0 | — | — |
| C | 2 | 23 | 101 | 27 | 15 / 12 | 0.101 |
| NG | 2 | 24 | 100 | — | — | — |
| **A** | 1 | 29 | 96 | 31 | **26 / 5** | **0.083** |
| SG | 2 | 44 | 80 | — | — | — |
| D | 2 | 49 | 75 | 53 | 46 / 7 | 0.145 |
| B | 4 | 62 | 60 | 70 | 63 / 7 | 0.123 |

- **A 의 오답은 얕다**: 맞힌 run 의 중앙 margin 0.342 대 틀린 run 0.083, 31 개 중 18 개가 margin 0.1 미만. 방향을 자신 있게 틀린 게 아니라 경계에서 흔들린 것이다.
- **A 에서 감점된 30 명은 S 에서 전원 만점**이다. 틀리는 run 이 본래 어려운 게 아니라, **A 의 경로가 S 가 쓰는 정보 일부를 잃는다**는 뜻이다 (FC 4,950 → gate PCA 10).
- A 감점자 30 명 중 15 명이 NG 에서도 감점 — 두 경로가 정보를 상당 부분 공유 (A−NG −0.012 와 같은 방향).
- **관측이며 인과 설명이 아니다.** PCA 차원을 바꿔 다시 학습하는 것은 새 exploratory version 이다.
- 새 버전 설계에 보탤 것: **gate 입력의 FC 압축 폭 (PCA 10) 을 설계 변수로 다룰 것.**

## 결정 28 — 새 탐색 버전 설계 세 갈래 (2026-09-29, 선택 TUI)

| # | 물음 | 선택 |
|---|---|---|
| 28-1 | 새 버전의 **축** | **축을 아직 정하지 않는다** — 포화 선별 gate (G-a) 를 먼저 만들어 후보 target 을 pilot 에서 걸러 본 뒤 정한다 |
| 28-2 | ROI 정체 구조 변경 (G-d) 의 크기 | **둘 다 병행 비교** — ROI embedding + ROI 별 readout |
| 28-3 | null 분포 (G-c) 의 규모 | **M 을 줄이고 null 종류를 늘린다** — 순열 + 공간 보존 (spin) + degree 보존 rewiring |

설계안 초안은 `docs/experiments/mobse_exploratory_v2_design_draft_2026-09-29.md` 이며, 결정 28 을 반영해 §3·§5·§6·§8 을 고쳤다.

**정하지 않은 것**: G-a 포화 기준값 · 선별을 어디서 할지 (pilot 31 의 표본 문제) · G-b 검정력 기준값 · G-c 의 M · δ 와 endpoint 해상도 · 후보가 전부 탈락했을 때의 대안.

### 착수 전 확인 두 건 — 둘 다 완료 (2026-09-29)

**① ROI 구조 변경이 순열 등변성을 깨는가** (Mac `.venv`, 저장소 코드 불변 — 덧껍데기만, 학습 전 무작위 가중치·seed 1729)

| 구조 | max │C(x) − A(Pᵀx)│ | max │C(x) − A(x)│ | 정렬을 쓸 수 있나 |
|---|---:|---:|---|
| v1 현행 (ROI 평균 readout) | 1.19e−07 | 9.73e−04 | **아니오 — 등변** (midreview 의 1.2e−07 재현) |
| + ROI embedding | 5.68e−03 | 2.36e−03 | 예 |
| + ROI 별 readout | 1.27e−03 | 1.14e−03 | 예 |

크기는 성능을 뜻하지 않는다 (학습 전 가중치) — 읽을 수 있는 것은 "0 인가 아닌가" 뿐이다.
> **정정 (2026-09-29, v3 빌드 2 단계)**: 위 `readout` 의 1.27e−03 은 **무작위 초기화**로 잰 값이다.
> 실제 구현은 `roi_readout` 을 **0 으로 초기화**했다 (두 구조가 같은 출발점에서 갈라지게 하려는 구현 선택) — 그래서
> **학습 전에는 `readout` 이 `mean` 과 완전히 같고 등변이다.** 정렬을 쓸 수 있게 되는 것은 학습이 그 가중치를 움직인 뒤다.
> `embedding` 은 작은 양수로 초기화하므로 처음부터 등변이 아니다. 두 성질 모두 `tests/v3/test_models_v3.py` 가 고정한다.
기록: `template_bank` 가 buffer 라 `state_dict` 에 들어간다 — A 의 state_dict 를 C 에 통째로 실으면 C 의 null bank 가 덮여 `C(x) = A(x)` 가 된다. 버퍼를 빼고 싣고 assert 로 확인했다.

**② spin (공간 보존 null) 을 Schaefer-100 에 쓸 수 있는가** (h197, venv)

`neuromaps`·`netneurotools` 는 없지만 **numpy + scipy 만으로 가능**하다. parcel 중심 → 반구별 무작위 회전 → `linear_sum_assignment` 일대일 배정.

| 항목 | 값 |
|---|---|
| parcel | 100 (좌 50 · 우 50, 정중선 0) |
| 회전 20 회: 거리행렬 상관 | 중앙 **0.497** (0.322–0.671), 반구 유지 **1.000** |
| 대조 — 단순 순열 20 회 | 중앙 **0.003** |

한계: 표면 (fsaverage 구면) spin 이 아니라 **부피 중심 회전** (Váša et al. 2018 계열) 이다 — 논문에 그 차이를 적어야 한다.

**예산 영향**: 세 null × M=20 을 C·D 한 지점·한 fold·한 seed 로 돌리면 120 fit ≈ 0.9 h [추정]. 기각된 "순열 하나만 M=100 전면" (3,000 fit ≈ 22 h) 보다 약 20 배 싸다.

**gate evidence 는 바꾸지 않았다** — 이 두 측정은 v1 release 의 근거가 아니라 **새 버전 설계용**이다. v1 의 gate 는 rev75 그대로다.

## 결정 29 — G-a·G-b 를 "차단" 이 아니라 "보고" 장치로 (2026-09-29, 선택 TUI)

| # | 물음 | 선택 |
|---|---|---|
| 29-1 | G-a 포화 기준값 | **기준 없이 값만 보고 판단** |
| 29-2 | 선별을 어느 자료에서 | **pilot 31 만, 버리는 쪽으로만** |
| 29-3 | G-b 검정력 기준값 | **기준 없이 결정 요청만** |
| 29-4 | 후보가 전부 탈락하면 | **그때 다시 정한다** |

**정한 것**: G-a 와 G-b 는 **자동 차단 gate 가 아니다.** 대신 두 약속이 남는다 — (i) 선별과 검정력 simulation 을 **반드시 돌린다**, (ii) 값을 **반드시 보고하고 결정 요청으로 올린다**. 선별은 pilot 31 명만 쓰고, 판정은 "명백히 포화면 버린다" 한쪽으로만 쓴다.

**정하지 않은 것**: 기준값 자체 (값을 본 뒤 그때그때 판단), 후보 전부 탈락 시 대안, G-c 의 M, δ·endpoint 해상도.

**한계 (기록)**: 기준값을 미리 박지 않으므로 사전등록 장치로서의 힘은 약해진다. 남는 것은 "반드시 재고 반드시 보고한다" 는 절차적 약속이다.

## G-a 선별 실행 — 완료 (2026-09-29, pilot 31)

산출 h197 `$D/v2_design/20260929_ga_screen/ga_screen.json` (sha256 `7c6c30ac0bdd…`). 스크립트 `.backup/slot_wi09_0929/ga_screen.py` (gitignore) — `mobse.v2` 는 읽기만 했다. pilot 창 248 · FC Fisher-z 4,950 → logistic, subject 단위 5-fold, C grid 최댓값 (낙관 쪽).

| 후보 | S BA | | 후보 | S BA |
|---|---:|---|---|---:|
| **v1 emo 대 wm (양성 대조)** | **1.000** | | workingmemory 정확도 | 0.586 |
| workingmemory 반응시간 | 0.700 | | age | 0.567 |
| emomatching 정확도 | 0.683 | | NEO_E | 0.552 |
| raven_score | 0.679 | | **sex** | **0.536** |
| NEO_O | 0.667 | | NEO_C · emo 반응시간 | 0.533 |
| BMI · NEO_A | 0.633 | | NEO_N | 0.517 |

**네 가지 읽을 거리**
1. **양성 대조가 작동한다** — v1 의 target 은 pilot 31 만으로도 1.000 이다. **G-a 가 있었으면 v1 의 target 을 막았다.**
2. 나머지는 포화가 아니다 → 결정 29-2 대로라면 버릴 후보는 v1 target 하나뿐이다.
3. **"포화가 아니다" 는 "쓸 만하다" 가 아니다.** 라벨당 25–30 명, fold 당 test 6 명 남짓. 우연 변동의 표준편차가 약 0.09 [추정] 인데 C 5 개 중 최댓값까지 취했다 — **0.70 도 우연과 뚜렷이 갈리지 않는다.**
4. **민감도 경고**: `sex` 가 0.536 이다. FC 로 성별 맞히기는 문헌에서 잘 되는 축인데 pilot 규모에서 0.536 이면, 이 선별기는 **"신호 없음" 과 "표본 부족" 을 구분하지 못한다.**

**설계에 주는 말**: 새 자료 없이 닿는 target 공간은 한쪽이 포화 (과제 정체), 다른 쪽이 pilot 규모에서 우연과 구분 불가 (개인차) 다 — **가운데가 비어 있다.** 결정 29-4 가 말한 자리에 사실상 도착했다.

### 선생님 판단이 필요한 것 (다음)
가운데가 비어 있으므로 셋 중 하나를 골라야 한다: **T4 저표본 곡선** (자료 그대로, target 은 포화된 것을 쓰되 학습량을 줄여 regime 을 바꾼다) · **T1 새 task fetch** (후보 풀을 넓힌다) · **T2 창 재설계** (과제 조건 디코딩). 또는 선별을 더 큰 표본에서 다시 하는 방법 (결정 29-2 를 다시 여는 것) 이다.

## 결정 30 — 새 버전의 축은 T4 저표본 곡선 (2026-09-29, 선택 TUI)

G-a 선별이 "포화 아니면 우연과 구분 불가" 로 나온 데 대한 회신: **"T4 저표본 곡선"**.

**정한 것**: target 은 그대로 두고 **학습 subject 수를 줄여 가며 A−C (그리고 A−S) 를 본다.** 새 fetch·새 전처리 없음.
**정하지 않은 것**: N 수준, 구조 변이 (결정 28-2) 를 곡선에 어떻게 넣을지, null 분포 지점, 아래 두 갈래.

### 착수 전 확인 — 저표본에서 학습 규칙이 깨진다 [측정]

P8-b 는 `MIN_UPDATES = 5000` 과 `MAX_EPOCHS = 400` 을 함께 잠갔다. 창 8 개/명, batch 32 기준:

| 학습 subject | update/epoch | 5,000 update 에 필요한 epoch | 400 안? |
|---:|---:|---:|---|
| 10 | 3 | 1,667 | **아니오** |
| 20 | 5 | 1,000 | **아니오** |
| 30 | 8 | 625 | **아니오** |
| 40 | 10 | 500 | **아니오** |
| 50 | 13 | 385 | 예 |
| 100 | 25 | 200 | 예 |

**학습 subject 가 약 50 명 아래면 두 상수를 동시에 만족할 수 없다.** 규칙을 그대로 두면 곡선이 50–100 으로 좁아져 "저표본" 이라 부르기 어렵다. 전례: pilot e2e (부록 BQ.1) 도 31 명에서 최소 epoch 1,250 이라 감싸개가 `MAX_EPOCHS` 를 2000 으로 덮었다 — 그때는 기술 검증이었지만 **v2 본 실행은 상수를 정식으로 정해야 한다.**

### 선생님 판단 필요 (둘)
1. **저표본 하한** — 규칙 유지 (50 이상만) / `MAX_EPOCHS` 인상 / `MIN_UPDATES` 인하 / epoch 상한 없이 update 수로만.
2. **v2 코드 위치** — `mobse/v2` 를 고치면 v1 의 측정·구현 잠금이 깨진다. v1 release 재현성을 지키려면 새 모듈로 갈지, 같은 모듈을 고치고 v1 은 커밋으로 보존할지 정해야 한다.

## 결정 31·32 — v3 학습 규칙과 코드 위치 (2026-09-29, 선택 TUI)

| # | 물음 | 선택 |
|---|---|---|
| 31-1 | 저표본 하한 확보 | **epoch 상한 없이 update 수로만** |
| 31-2 | v2 코드 위치 | **새 모듈 `mobse/v3/`** |
| 32 | "update 수로만" 의 해석 (아래 확인 뒤 추가 질문) | **학습은 5,000 update, 선택은 자유** |

### 결정 32 가 필요했던 이유 [측정]

`fitting.py:613` 이 `min_epoch = min_epochs_for(...)` 로 잡고, `fitting.py:670` 과 `train.py:288` 이 **그 전에는 early stopping 도 best epoch 선택도 못 하게** 막는다. 31-1 을 글자 그대로 적용하면 학습 subject 10 명에서 창 80 개를 **1,667 epoch 반복한 뒤에야** best checkpoint 를 고를 수 있다 — 저표본 쪽이 구조적으로 과적합된 모델로 평가되어 곡선의 요점이 무너진다.

### 정해진 v3 학습 규칙 (P8-c 후보)

- **update 예산 5,000 을 모든 N 이 동일하게 받는다** — 곡선의 차이가 "학습량" 이 아니라 "자료의 양" 이 되도록.
- **epoch 상한은 없다** (update 예산이 상한 역할을 한다).
- **best checkpoint 는 어느 epoch 에서든 고를 수 있다** — `min_epoch` 결합을 푼다. early stopping 이 일찍 걸리면 학습도 일찍 끝난다.

### v3 모듈 계획

- **`mobse/v2` 는 손대지 않는다** → v1 의 측정 잠금 `9b7b11cf` · 구현 잠금 `bcf1fec22676` 와 gate rev75 가 그대로 유효하고, v1 release 는 언제든 재현된다.
- `mobse/v3/` 에서 바꿀 것: ① `train`·`fitting` 의 학습 규칙 (위) ② `models` 에 ROI embedding · ROI 별 readout 두 구조 (결정 28-2) ③ `templates` 에 null 세 종류 — 순열 · Váša 회전 (spin) · degree 보존 rewiring (결정 28-3) ④ `config` 에 새 잠금 키 (update 예산 · 구조 · null 종류 · M · PCA 차원 grid) ⑤ 학습 subject 부분표집 (저표본 곡선, 잠긴 seed) ⑥ `configs/exploratory_v2/` ⑦ `tests/v3`.
- **구현 선택 (표시)**: v3 는 동결된 `mobse/v2` 를 import 해 재사용하고, v3 잠금의 `code_hash` 는 **`mobse/v3/*.py` 와 `mobse/v2/*.py` 를 함께** 해시한다. v2 는 v1 release 로 동결됐으므로 이 참조는 흔들리지 않는다. 9,000 줄을 복사하지 않는 대신 의존을 잠금에 명시한다.
- v1 의 분할 (`folds.json`, split_hash `ace5f4a4…`)·pilot 경계·마감 6단계·gate revision 방식은 그대로 쓴다. **PIOP2 는 계속 열지 않는다** (결정 27).

## v3 빌드 1 단계 — 학습 규칙 모듈 (2026-09-29)

`mobse/v3/` 를 새로 만들었다. **`mobse/v2` 와 `tests/v2` 는 한 줄도 바뀌지 않았다** (`git status` 0) — v1 의 측정 잠금 `9b7b11cf` · 구현 잠금 `bcf1fec22676` · gate rev75 가 그대로 유효하다.

| 파일 | 줄 | 내용 |
|---|---:|---|
| `mobse/v3/__init__.py` | 20 | 모듈 취지와 구현 선택 (무엇을 새로 쓰고 무엇을 v2 에서 import 하는지) |
| `mobse/v3/train.py` | 212 | 학습 규칙 (P8-c 후보) |
| `tests/v3/test_train_v3.py` | 163 | 시험 22 개 |

**구현 선택 (표시)**: 크게 바뀌는 모듈만 v3 에 새로 쓰고, 바뀌지 않는 것 (grid·손실·동률 규칙·누설 검사 등) 은 동결된 `mobse.v2.train` 을 import 한다. `_median`·`_require_complete` 같은 비공개 이름도 import 한다 — 사문을 다시 쓰면 두 벌이 갈라질 위험이 더 크다고 보았다.

**새 API**
- `UPDATE_BUDGET = 5000` — v1 의 `MIN_UPDATES` 와 **같은 수지만 뜻이 다르다**: v1 은 최소치, v3 는 **예산이자 상한**.
- `epochs_for_budget(n_train)` = `ceil(예산 / update_per_epoch)` — 그 학습 집합의 epoch 상한. 고정 상한은 없다.
- `EPOCH_SANITY_CEILING = 20000` — 규칙이 아니라 방어선 (지나치게 작은 학습 집합을 잡는다).
- `select_best_epoch(...)` — `min_epoch` 결합 없이 best epoch 를 고른다 (결정 32).
- `CellFoldResult` 는 `epoch_ceiling` 을 **반드시** 받는다 (기본값 없음 — 빠뜨리면 조용히 잘못된 상한으로 통과한다).
- `select_config(...)` — 선택 규칙은 v1 과 **같고** 공통 E 의 상한만 그 학습 집합의 `epoch_ceiling` 이다.

**시험 22 개** (`tests/v3`, 전부 통과). 지키려는 것: ① 예산 산술이 v1 과 같은 수를 낸다 ② 저표본에서 v1 은 충돌하지만 v3 는 그 값이 곧 상한이다 ③ **best epoch 결합이 풀렸다** (v1 이 거부하던 이른 epoch 를 고른다) ④ 선택 규칙은 v1 과 같은 결과를 낸다 (같은 입력으로 v2·v3 를 나란히 돌려 대조).

**돌연변이 시험 6/7 검출** (`.backup/slot_wi09_0929/mut_v3train.py`, gitignore). 놓친 1 건은 "공통 E 상한을 안전 상한으로 바꿈" 인데, `CellFoldResult` 가 이미 `best_epoch ≤ epoch_ceiling` 을 강제하므로 그 중앙값의 올림도 상한을 넘을 수 없다 — **정상 경로로는 닿지 않는 방어선**이다. 지우지 않고 코드에 그 사실을 적었다 (`select_config` 주석).

**다음 (v3 빌드)**: 2 `models` 두 구조 · 3 `templates` null 세 종류 · 4 `config` 새 잠금 키 + `configs/exploratory_v2/` · 5 학습 subject 부분표집 · 6 v3 잠금·pilot e2e.

## v3 빌드 2 단계 — ROI 정체 구조 (2026-09-29)

`mobse/v3/models.py` (147 줄) · `tests/v3/test_models_v3.py` (시험 15 개). 누적 `tests/v3` 37 개 전부 통과. **`mobse/v2` 는 여전히 불변.**

- `ROI_STRUCTURES = ("mean", "embedding", "readout")` — `mean` 은 v1 과 같은 동작으로 남긴 대조군이다.
- 구조 부품 (encoder · gate · graph layer · `ModelConfig`) 은 동결된 v2 를 그대로 import 한다. 새로 쓴 것은 `MoBSEv3` 한 클래스뿐이다.
- **구현 선택 (표시)**: `roi_readout` 을 **0 으로 초기화**한다 → 학습 전에는 `readout` 이 `mean` 과 완전히 같다. 두 구조가 같은 출발점에서 갈라지게 하려는 선택이며, 그 결과 **초기 등변성 측정은 0 이 나온다** (설계 기록의 1.27e−03 정정 — 위 결정 28 절).
- `embedding` 은 `ROI_EMBEDDING_INIT_STD = 0.1` 로 초기화하므로 처음부터 등변이 아니다.

**시험이 고정하는 것**: ① `mean` 은 등변이고 **같은 가중치면 v2 와 수치가 같다** ② `embedding` 은 처음부터 등변성을 깬다 ③ `readout` 은 **초기엔 `mean` 과 같고**, 가중치가 움직이면 깬다 ④ bank 는 buffer 라 optimizer parameter 가 아니다 ⑤ **bank 가 `state_dict` 에 들어간다는 사실 자체** — 09-29 설계 측정에서 A 의 state 를 C 에 통째로 실어 null bank 가 덮인 사고를 되풀이하지 않기 위한 회귀 시험 ⑥ parameter 증가량이 새 구조 몫과 정확히 같다.

**돌연변이 8/8 검출** (`.backup/slot_wi09_0929/mut_v3models.py`, gitignore).

## v3 빌드 3 단계 — null 세 종류 (2026-09-29)

`mobse/v3/templates.py` (약 240 줄) · `tests/v3/test_templates_v3.py` (시험 24 개). 누적 `tests/v3` **61 개** 전부 통과. **`mobse/v2` 불변.**

| kind | 무엇을 보존하나 | 무엇을 깨나 |
|---|---|---|
| `permutation` (v1 과 같음) | spectrum · weight 분포 · bank 간 관계 | 해부학 배치 · 공간 인접 · 반구 |
| `spin` (Váša 회전 + 일대일 배정) | **공간 인접 · 반구** · spectrum · weight 분포 | 해부학 배치 |
| `rewire` (degree 보존 double-edge swap) | 각 node 의 **연결 수** · weight 다중집합 | 연결 상대 · node strength |

**읽는 법**: A 가 `permutation` 만 이기고 `spin` 을 못 이기면, 모델이 쓰는 것은 해부학 배치가 아니라 공간 통계라는 뜻이다.

**구현 선택 (표시)**
- `rewire` 는 정규화된 template 을 직접 섞지 않는다. bank 를 만든 길을 **되밟는다**: `raw_centroids` → `sparsify_positive(density)` → rewire → `normalize_with_self_loop`. 정규화된 행렬을 섞으면 `D^(−1/2)(A+I)D^(−1/2)` 관계가 깨진다. 되밟은 edge 수가 bank 기록과 다르면 멈춘다.
- `rewire` 는 template 마다 seed 를 `seed + k` 로 갈라 재현 가능하게 한다. `permutation`·`spin` 은 v1 처럼 **모든 template 에 같은 순열**을 준다.
- 정중선 (x = 0) parcel 이 있으면 `roi_centroids` 가 멈춘다 — 반구 안 회전을 정의할 수 없기 때문이다.

**실제 아틀라스 확인 (h197, Schaefer-100 MNI152NLin2009cAsym)**: parcel 100 (좌 50 · 우 50). seed 1730–1749 의 spin 20 개에서 거리행렬 상관 **중앙 0.485** (0.316–0.657), 단순 순열은 **0.007**, 반구 유지 전부 1.0.

**돌연변이 13/14 검출** (`.backup/slot_wi09_0929/mut_v3templates.py`). 초기 12/14 에서 둘을 처리했다.
- **진짜 구멍 1 건**: "rewire 를 정규화된 template 에서 수행" 이 통과했다. 정규화는 off-diagonal 의 **자리**를 바꾸지 않아 degree 검사로는 잡히지 않고 **값만 틀려진다**. 교환을 항등으로 바꾸면 원래 bank 가 그대로 나와야 한다는 시험을 더해 막았다.
- 남은 1 건은 `vasa_permutation` 의 치환 검사인데, `linear_sum_assignment` 가 정의상 일대일 배정을 돌려주므로 **정상 경로로는 닿지 않는다**. 코드에 그 사실과 남겨 두는 이유 (반구 분할이 잘못되면 여기서 걸린다) 를 적었다.

**다음**: 4 `config` 새 잠금 키 + `configs/exploratory_v2/` · 5 학습 subject 부분표집 · 6 v3 잠금·pilot e2e.
