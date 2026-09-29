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
