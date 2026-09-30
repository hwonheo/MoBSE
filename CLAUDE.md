# CLAUDE.md — MoBSE Project Context

> 최종 갱신 2026-09-30 — **커밋 규약 적용**: 이력 161 개를 영문 1줄로 재작성하고 co-author 태그 제거, 무효가 된 커밋 SHA 기록 삭제 (gate 필드 7 · 문서 토큰 284) → **gate rev78**. 선생님 지시로 `origin/redesign-v1` 에 `--force-with-lease` 푸시 (원격 = 로컬, 162 커밋, co-author 0). 그 직전: **WI-11 연구 결과 패키지** 작성 (v1 내부 마감, `reports/wi11_research_package_2026-09-29.md`) → **gate rev76** (G5 check 5 건 pass) → **rev77** (승인으로 G5 `planned` → `cleared_with_limitations`), 인용 수치 독립 대조 실패 0. **결정 33** (v3 config 잠금 키: 8 칸 · 최대 수준에서 한 번 선택 · PCA 10 고정 · null M=20). v3 빌드 1·2·3·5 단계 완료. 그 직전: **결정 30·31·32**: 새 버전 축은 **T4 저표본 곡선**, 코드는 **새 모듈 `mobse/v3/`** (`mobse/v2` 불변 → v1 잠금·gate rev75 유효), 학습은 **update 예산 5,000 고정·epoch 상한 없음·best checkpoint 선택 자유**. 그 직전: **결정 29** (G-a·G-b 는 차단이 아니라 보고 장치; pilot 만·버리는 쪽으로만) 와 **G-a 선별 실행 완료** — 양성 대조 v1 target 1.000 (gate 가 작동함), 나머지 0.52–0.70 이나 pilot 31 규모라 우연과 구분 불가 (`sex` 0.536 이 민감도 경고). gate 는 rev75 그대로. 그 직전: **결정 28: 새 탐색 버전 설계 세 갈래** (축 미정 → 포화 선별 gate 우선 · ROI 구조 둘 다 병행 · null 은 M 축소 + 종류 확대) 와 설계안 초안 `docs/experiments/mobse_exploratory_v2_design_draft_2026-09-29.md`. 착수 전 확인 2건 완료 (등변성·spin). gate 는 **rev75 그대로** (v2 설계 측정은 v1 근거가 아님). 그 직전: **결정 27: 진로 (나) 확정** (현 버전 내부 마감 · PIOP2 미개방 · 새 탐색 버전 설계) + interaction 판독 철회, **A−S 진단** (결정 25-6) → **gate evidence rev75**, 부록 BZ·CA. 그 직전: WI-09 null 민감도 완료 → rev74, 부록 BY. 그 전 같은 날: 결정 25 기록, rev73 (09-28 실행 기록 + gate 표기), 부록 BT–BX, `resource_budget.md` 9.2, 커밋. claude.ai Project 사본 동기화 중단 — 정본은 저장소 `docs/handoff/`.
> 이전 갱신 2026-09-29 09:2x KST — "인수인계 — 2026-09-29" 절 추가 (Cowork 세션 → 터미널 Claude Code), 정본 포인터를 저장소 `docs/handoff/` 로 옮김 (그때 gate 는 rev72). 그 이전 (2026-09-26 23:3x, rev60–rev72 의 세부) 은 `.backup/CLAUDE_2026092*.md` 에 있다. 모든 수치는 실측값이며 출처를 함께 적음.
> 이전판(2026-09-18)은 `.backup/CLAUDE_20260925_201635.md` 에, 2026-04-17판은 `.backup/CLAUDE.md_20260918_*.md` 에 보존됨.
> **현행 상태의 정본은 이 파일이 아님** — 저장소 `docs/handoff/` 의 문서 (읽는 순서는 아래 "인수인계 — 2026-09-29" 절) 와 가장 높은 revision 의 `gate_evidence.json`. 이 파일은 저장소에 들어온 사람을 위한 방향 안내다.

## 인수인계 — 2026-09-29 (Cowork 세션 → 터미널 Claude Code)

### 먼저 읽을 것 (순서)
1. `docs/handoff/mobse_decisions_2026-09-29.md` — **결정 25 원문과 그 뒤 진행. 09-29 이후 정본.**
2. `docs/handoff/mobse_main_oof_2026-09-28.md` — 결정 23·24 원문, main OOF·보조 비교 실행 기록과 결과, gate 표기 권고.
3. `docs/handoff/mobse_h2_midreview_2026-09-29.md` — H2 (A−C) 증명 방식 중간 점검: `C(x) = A(Pᵀx)` 수치 검증, 설계 약점 5개, 선택지 (가)/(나)/(다).
4. `docs/handoff/mobse_interpretation_2026-09-29.md` — A < S 해석, H2 불확실 근거 (기존 결과·문헌), PIOP2 계획과 미구현 목록. 1절·2절의 "ROI 식별을 못 해 구조상 A≈C" 서술은 midreview 1절에서 **정정됨**.
5. `docs/experiments/mobse_exploratory_v2_design_draft_2026-09-29.md` — **새 탐색 버전 설계안 초안** (결정 28 반영). 6. `docs/handoff/mobse_redesign_g0_handoff_2026-09-17.md` — 결정 0–22 원문과 세부, 실행 절차, 마감 절차, 재발 방지 장치 (09-27 판; 머리에 결정 23–25 요약 행 추가).

- **정본은 저장소 `docs/handoff/` 다.** claude.ai Project "MoBSE" 사본 동기화는 하지 않는다 (2026-09-29 지시).
- 문서끼리 어긋나면 **날짜가 늦은 쪽**이 앞선다. 해석·점검 문서는 판단 재료이며 결정이 아니다.

### 현재 상태 (2026-09-29 11:0x KST)
- Mac branch `redesign-v1`. 2026-09-30 에 `origin/redesign-v1` 로 푸시됨 (이력 재작성분, force-with-lease).
- **결정 23 "main OOF 착수 승인" (09-28)** → A–D main OOF 완료: h197 `$D/main_oof/20260928_1cd4054_main_a2/` (`ALL_RC=0`, WI-07 완료 기준 전부 충족). attempt 1 `…_main` 은 fit 0 으로 멈춘 판 (남겨 둠).
- **결정 24** → 보조 비교 (S 4 후보·NG·SG) 완료: `$D/main_oof/20260928_1cd4054_aux_a1/` (`ALL_RC=0`). smoke 판 `$D/main_oof/20260928_aux_smoke/`.
- 결과 (BA): A 0.877 · B 0.722 · C 0.893 · D 0.790 · S 1.000 · NG 0.889 · SG 0.810.
  - primary (97.5% CI): **H1 A−B +0.155 [+0.095, +0.214]** (하한 > δ) · **H2 A−C −0.016 [−0.052, +0.020] 불확실** → 두 기여를 함께 주장할 수 없음 (§8).
  - 보조 (95% CI): interaction +0.052 [+0.004, +0.099] — **판독 철회 (결정 27-2): 순열 하나에 기댄 값이라 "추가 기여 지지" 로 쓰지 않는다** · A−S −0.123 [−0.163, −0.083] · A−NG −0.012 [−0.052, +0.028] · A−SG +0.067 [+0.016, +0.119].
  - sha256 앞자리: `statistics.json` `f0a9847bb61c` · `comparison_statistics.json` `a62e6239fbab`.
- **gate evidence 는 rev75** — rev73 (09-28 실행 기록 + gate 표기, 부록 BT–BX) → rev74 (WI-09 null 민감도, 부록 BY) → rev75 (A−S 진단 + 결정 27, 부록 BZ·CA). gate 판정·status 는 rev73 그대로.
- 구동기는 gitignore 영역 (버전 관리 밖): Mac `.backup/slot_thr_0928/` — `main_driver.py`·`main_setup.sh`·`main_check.py`·`aux_driver.py` (v2)·`aux_driver_v1.py` (결함판)·`aux_setup.sh`·`aux_resume.sh`·`thr_{driver,setup,compare}`. h197 산출 root 에도 driver 사본이 있다.
- 스레드 고정: 프로세스당 `OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=2` + 동시 k=4. pilot 96 fit 창 예측·checkpoint 바이트 동일, fit 당 벽시계 158.9 s → 73.5 s. main inner 480 은 2 h 44 m, outer 60 은 26.4 분 (`resource_budget.md` 9.2).

### 선생님 결정 25 (2026-09-29, 선택 TUI) — 정한 것
1. **gate 표기**: 권고 1–6 전부 적용 → rev73 에 반영 완료.
2. **H2 방향**: **(다)** — 현 버전에서 WI-09 만 먼저 (PIOP2 미사용) 하고 그 뒤 (나) 판단.
3. **PIOP2 외부 평가 (WI-08)**: **지금 승인하지 않음.** 외부 S·NG·SG 포함 여부와 U17 해소 판단도 승인 시점에 함께 정한다.
4. **A−S**: 추가 분석 후 판단하되, 그 분석은 **새 학습 없는 진단**으로 한정 (기존 산출물만 읽음).
5. **WI-09 일정**: 기록·커밋을 마친 뒤 착수 — **완료** (아래 "WI-09 결과").
- 이어진 지시: "claude.ai Project 에 올리는 일은 하지말고 docs/handoff 문서 갱신만.., 그리고 개발 진행은 승인".
- **정하지 않은 것**: PIOP2 개방, G1 fail 2건 해소, 새 탐색 버전 설계 착수. main 결과를 본 뒤의 설계·grid·δ·N 변경은 새 exploratory version (계획서 §3·§4-5·§8).

### WI-09 null 민감도 결과 (2026-09-29, gate rev74·부록 BY)

- 산출 h197 `$D/null_sens/20260929_97e434a_a1/`. seed 1730–1733 × A·B·C·D outer 60 = **240 fit**, 1 h 22 m, 실패 0, `ALL_RC=0`, 누설 0. 착수 전 확인: seed 1730 판 A fit 이 main 과 창 예측·checkpoint 동일.
- **결정 26** (선생님 원문 "가. 로 진행"): null seed 를 바꾸면 `config_hash` 가 바뀌어 `evaluate` 가 main 의 A·B 를 거부하므로, seed 마다 A·B 도 함께 돌렸다 (seed 의존 C·D 120 + 맞춤용 A·B 120). `mobse/v2` 와 잠금은 불변 — null seed 는 구동기가 프로세스 안에서만 덮는다.

| null seed | C | D | H2 A−C (97.5%) | interaction (95%) |
|---|---:|---:|---|---|
| 1729 (primary) | 0.8929 | 0.7897 | −0.0159 [−0.0516, +0.0198] | +0.0516 [+0.0040, +0.0992] |
| 1730 | 0.8770 | 0.7579 | 0.0000 [−0.0238, +0.0238] | +0.0357 [−0.0079, +0.0794] |
| 1731 | 0.8770 | 0.7579 | 0.0000 [−0.0357, +0.0357] | +0.0357 [−0.0079, +0.0833] |
| 1732 | 0.8770 | 0.7222 | 0.0000 [−0.0317, +0.0317] | 0.0000 [−0.0397, +0.0437] |
| 1733 | 0.8929 | 0.7659 | −0.0159 [−0.0437, +0.0119] | +0.0278 [−0.0079, +0.0635] |

- A 0.8770 · B 0.7222 · H1 A−B +0.1548 은 다섯 판 모두 같다 (A·B 는 null 과 무관).
- **① A−C 는 다섯 판 전부 [−0.016, 0.000], CI 모두 0 포함** → H2 의 불확실은 순열 선택 탓이 아니다. **② 보조 interaction 은 primary 판에서만 하한 > 0** (민감도 네 판은 하한 ≤ 0) → 그 보조 판독은 순열 하나에 기대고 있었다. primary 판정은 바꾸지 않는다 (§8).
- **결정 27 로 (나) 확정** — 현 버전은 내부 결과로 마감, PIOP2 는 열지 않음, 새 탐색 버전 설계. 사전등록 §8 이탈이라 사유를 부록 CA.3 에 기록했다.

### 결정 27 (2026-09-29) — 진로 (나) · interaction 철회 · A−S 진단

- **(나) 로 확정**: 현 버전은 내부 결과로 마감 · **PIOP2 는 열지 않음** · 새 탐색 버전 설계. 사전등록 (§8 "내부 결과가 음성이어도 외부 검증 수행") **이탈**이며 사유 4개를 부록 CA.3 에 적었다 — 최종 보고서 (WI-11) 에 옮겨야 한다.
- **interaction 판독 철회**: primary 판만 하한 > 0, 민감도 네 판은 모두 하한 ≤ 0. "추가 기여 지지" 서술을 쓰지 않는다. `statistics.json` 수치는 그대로 (§8).
- **A−S 진단** (결정 25-6, 새 학습 없음, 부록 BZ): S 는 252 run 전부 정답. A 는 31 run 오답인데 **18 개가 margin 0.1 미만**이고 **26 개가 emomatching** 이다. A 감점 30 명 중 29 명은 **한 run 만** 틀렸고, 그 30 명은 **S 에서 전원 만점**. → 틀리는 run 이 어려운 게 아니라 A 의 경로 (FC 4,950 → gate PCA 10) 가 정보를 잃는다는 관측. 새 버전 설계 변수로 **PCA 압축 폭**을 추가.
- **정하지 않은 것**: 새 탐색 버전의 target·구조·null 설계·δ·N. PIOP2 를 영영 안 쓴다는 뜻도 아니다.

### 결정 28 (2026-09-29) — 새 탐색 버전 설계 세 갈래

설계안 초안: **`docs/experiments/mobse_exploratory_v2_design_draft_2026-09-29.md`** (읽는 순서 5번 다음).

- **축 미정** → **포화 선별 gate (G-a) 가 1 순위**. 후보 target 을 pilot 에서 걸러 본 뒤 축을 정한다. 선별 가능한 라벨은 초안 §5.1 (성별·raven·NEO·나이·과제 정확도·RT — 전부 기존 자료).
- **G-d ROI 구조: ROI embedding + ROI 별 readout 병행 비교** (칸 2 배). 두 구조가 순열 등변성을 깨는 것은 **확인 완료** — v1 현행 1.19e−07 (등변) vs embedding 5.68e−03 · readout 1.27e−03. **정정**: readout 의 값은 무작위 초기화로 잰 것이고, 구현은 0 초기화라 **학습 전에는 mean 과 같고 등변**이다 — 학습이 가중치를 움직인 뒤에 갈라진다 (`tests/v3` 가 고정).
- **G-c null: M 축소 + 종류 확대** — 순열 · **공간 보존 (spin)** · degree 보존 rewiring 을 각 M=20. spin 은 **numpy+scipy 만으로 구현 가능 확인** (거리행렬 상관 0.497 대 단순 순열 0.003, 반구 유지 1.000). 세 null × M=20 은 120 fit ≈ 0.9 h [추정] — 전면 M=100 (22 h) 보다 20 배 싸다.
- **남은 결정**: G-a 기준값 · 선별을 어디서 할지 (pilot 31 은 표본이 작다) · G-b 검정력 기준값 · M · δ·endpoint 해상도 · 후보 전부 탈락 시 대안.
- v2 설계 측정은 **gate evidence 에 넣지 않는다** — v1 release 의 근거가 아니다.

### 결정 29 · G-a 선별 실행 (2026-09-29)

- **결정 29**: G-a (포화 선별) 와 G-b (검정력) 는 **자동 차단 gate 가 아니다** — 기준값을 미리 박지 않고, "반드시 재고 반드시 보고해 결정 요청으로 올린다" 는 절차 약속만 남긴다. 선별은 **pilot 31 만** 쓰고 판정은 **버리는 쪽으로만**. 후보가 전부 탈락하면 그때 다시 정한다. **한계**: 사전등록 장치로서의 힘은 약해진다.
- **G-a 선별 실행 완료** (`$D/v2_design/20260929_ga_screen/ga_screen.json`, sha `7c6c30ac0bdd`): pilot 창 248 · FC 4,950 → logistic, subject 5-fold, C grid 최댓값.
  - **양성 대조 v1 target = 1.000** → **이 gate 가 있었으면 v1 의 target 을 막았다.**
  - 나머지 0.52–0.70 (최고: workingmemory 반응시간 0.700 · emo 정확도 0.683 · raven 0.679).
  - **그러나 우연과 구분되지 않는다** — 라벨당 25–30 명, 우연 변동 SD 약 0.09 [추정], 게다가 C 최댓값을 취한 낙관. **`sex` 가 0.536** 인 것이 민감도 경고다 (FC 로 성별은 잘 맞히는 축인데도).
  - **설계 함의**: 새 자료 없이 닿는 target 공간은 한쪽이 포화, 다른 쪽이 pilot 규모에서 구분 불가 — **가운데가 비어 있다.**
- **다음 판단 (선생님)**: T4 저표본 곡선 / T1 새 task fetch / T2 창 재설계 / 선별을 더 큰 표본에서 다시 (결정 29-2 재개방) 중 택일.

### 결정 30·31·32 (2026-09-29) — v3 의 축과 학습 규칙

- **축 = T4 저표본 곡선** (결정 30): target 은 그대로, **학습 subject 수를 줄여 가며** A−C·A−S 를 본다.
- **코드 = 새 모듈 `mobse/v3/`** (결정 31-2). **`mobse/v2` 는 손대지 않는다** → v1 잠금 (`9b7b11cf`·`bcf1fec22676`) 과 gate rev75 가 그대로 유효하다. v3 잠금의 `code_hash` 는 `mobse/v3/*.py` + `mobse/v2/*.py` 를 함께 해시한다 (구현 선택).
- **학습 규칙 (P8-c 후보, 결정 31-1·32)**: update 예산 **5,000 을 모든 N 이 동일하게** · **epoch 상한 없음** · **best checkpoint 는 어느 epoch 에서든** (`min_epoch` 결합 해제).
  - 결정 32 가 필요했던 이유 [측정]: `fitting.py:613`·`670`, `train.py:288` 이 `min_epoch` 전에는 early stopping·best 선택을 막는다 → 학습 10 명이면 창 80 개를 **1,667 epoch 반복한 뒤에야** checkpoint 를 고르게 되어 저표본이 구조적으로 과적합된다.
- **v3 에서 바꿀 것**: 학습 규칙 · ROI embedding·ROI 별 readout (28-2) · null 세 종류 (28-3) · config 새 잠금 키 · 학습 subject 부분표집 · `configs/exploratory_v2/` · `tests/v3`.

### WI-11 · 결정 33 (2026-09-29)

- **WI-11 연구 결과 패키지** — `results/redesign_v1/.../reports/wi11_research_package_2026-09-29.md` (sha `c2e758e88205`). claim–evidence 10 행 · 비용 · 음성 결과 7 · 사전등록 이탈 사유 4 · 한계 6 · 재현 명령. **gate rev76** 에 등록하고 G5 check 5 건 pass → **rev77 에서 G5 `status` 를 `planned` → `cleared_with_limitations`** (선생님 승인 "권고 사항으로 바로 진행"). 단순 `cleared` 가 아닌 이유 셋을 `status_note` 에 적었다 — 외부 검증 없이 내린 해석 · 계획서 §8 사전등록 이탈 · H2 불확실과 interaction 판독 철회. 인용 수치 독립 대조 **실패 0**.
- **비용 실측** (보조 비교의 `not_reported` 를 닫음): A·C 6,469 · B·D 6,021 · SG 6,018 · NG 5,154 · S3 4,951 · **S4 158,498** parameter. **S4 가 A 보다 24.5 배 큰데 12 %p 이긴다** → 효율 우위 주장 불가.
- **결정 33 (v3 config 잠금 키)**: 칸 **A–D × 2 구조 = 8 칸** · config grid 선택은 **가장 큰 수준 (N=100) 에서 한 번** 후 전 수준 재사용 · gate PCA **10 고정** (grid 안 엶) · null **M = 20**. 정하지 않은 것: δ·endpoint 해상도, G-b simulation 시점, 저표본 fit 당 실제 시간 (착수 전 실측 필요).

### 작업 규칙 (선생님 지시 — 모든 세션 공통)
- 한국어·간결·쉬운 말. 수치·시각·상태는 명령으로 확인한 값만 쓰고, 확인하지 못한 것은 따로 적는다.
- 1시간 넘는 작업은 시작부터 매시 상태 보고 (① 지금 단계 ② 완료·진행 ③ 계획 ④ 다음 보고). 09-28 까지 쓰던 claude.ai 예약 작업 (시간별 슬롯) 은 비활성 — 이 세션이 직접 보고한다.
- 가역 결정은 진행하고 보고, 되돌리기 어려운 결정만 올리고 그 가지만 멈춘다.
- 결정은 원문 그대로 인용하고 범위를 넓히지 않는다 ("정한 것 / 정하지 않은 것").
- 기록·메모를 먼저 찾아본 뒤 질문한다 (대부분 이미 답이 있다).
- **커밋 규약 — 이 절이 정본이다** (팀 규칙, 출처 `~/.claude/plugins/marketplaces/bmc-plugins/README.md`:
  "커밋 규칙은 팀 규칙을 따름 — 영문 1줄, 20~25단어 이내, 작업 단위로 묶어 5건 이하, co-author 태그 미사용.")
  1. **영문 1줄.** 본문(body) 을 쓰지 않는다 — 자세한 이유는 `docs/handoff/` 와 gate evidence 에 적는다.
  2. **20~25단어 이내.**
  3. 작업 단위로 묶어 5건 이하 — **선택 사항이다** (필수 아님, 2026-09-30 선생님 확인).
  4. **co-author 태그 미사용.** `Co-Authored-By` 를 붙이지 않는다 (도구 기본값이 붙이려 해도 제거한다).
  5. Conventional Commits 접두사 (`feat(scope):`·`docs(scope):`·`chore(scope):`) 는 유지.
  6. 파일로 써서 `git commit -F` (zsh heredoc 사고). git lock 으로 막히면 `.git/*.lock` 을 to-delete 폴더로 **옮기고** (삭제 아님) 다시 시도.
  7. **푸시는 지시가 있을 때만.** 기본은 로컬 커밋까지다. (2026-09-30: 선생님 지시로 `--force-with-lease` 1 회 푸시 — 이력 재작성분 반영.)
- **커밋 SHA 를 기록의 근거로 쓰지 않는다** — 2026-09-30 이력 재작성으로 예전 SHA 는 무효다. 코드 판본의 기준은 **잠금**이다 (측정 `9b7b11cf8576…` 의 `code_hash` `804d6ee17625…`, 구현 `bcf1fec22676…`).
- **h197 의 azcopy (NFS → Azure, 선생님 작업) 가 언제 끝나는지는 확인·보고하지 않는다** (09-28 지시).
- h197 부하 진단: load 가 높아도 로컬 디스크 포화로 단정하지 않는다 — 09-28 load 약 70 은 NFS (`/mnt/NAS`) 대기였고 로컬 md1 은 한가했다. 장치별 busy % 와 NFS/로컬 구분부터 본다.
- 새 구동기는 CLI 인자 값을 코드 상수에서 가져오거나 첫 fit smoke 를 먼저 돌린다 (09-28 aux v1 이 S 후보 이름을 줄여 써 480 호출 rc=2).
- 코드 사본 대조는 `diff -r` 가 아니라 **추적 파일 sha256** (미추적 파일 때문에 main attempt 1 이 멈춤).

### 저장소에 없는 컨텍스트 (알려진 누락)
- 09-28 실행·결과: 보고서 부록·gate evidence 에 없음 (위 "결정 없이 해도 되는 것").
- 구동기 `.backup/slot_thr_0928/` 는 gitignore — 버전 관리 밖.
- Notion Work Log (`MOBSE`) 에 09-28·09-29 작업이 기록됐는지 확인하지 못함.
- Cowork 대화 원문은 저장소에 없다 — 결정 원문은 docs/handoff 문서에 인용돼 있다.

## Project
MoBSE (Mixture of Brain-State Experts): fMRI 시계열을 dFC 유래 전문가 하위망으로 라우팅하는 그래프 신경망. PI: Dr. Hwon Heo, Asan Medical Center Seoul.

## Current Phase: 재설계 v1 (Redesign v1)

2026-09-17 문헌 검토와 기존 실험 감사를 거쳐 **연구 질문과 평가 target을 교체함.**

- **질문**: training-rest에서 만든 graph bank의 해부학적 정렬과 입력 의존 routing은, 군집과 독립인 실제 task 분류에서 각각 추가 가치를 주는가.
- **주 target**: AOMIC PIOP1 `emomatching=0` / `workingmemory=1` 의 run identity. 미사용 피험자에서 평가.
- **주가설**: H1 = A−B > 0 (입력 의존 routing의 이득), H2 = A−C > 0 (정렬된 brain bank의 이득). 최소 관심 효과 δ = 0.02 balanced accuracy (이 연구의 설계 선택이지 문헌 기준이 아님).
- **보조 비교** (primary 아님, 95% 기술적 CI): S 후보 4종 (logistic 2 + 32-hidden MLP 2), 구조 비교 NG (no-graph fusion MLP)·SG (single average graph).
- **복제**: PIOP2 같은 task pair를 잠근 cohort/acquisition replication으로 사용. **cross-site라고 부르지 않음** (같은 연구 환경).

정본 문서: [프로토콜 v1.1](docs/experiments/mobse_redesign_protocol_2026-09-17.md) (본문의 "계획서", 개정 행 P1–P11·P6-a/b·P8-b 포함) · [작업 지침서 v1.0](docs/experiments/mobse_redesign_work_instructions_2026-09-17.md) · [기존 실험 감사](docs/experiments/mobse_existing_experiments_audit_2026-09-17.md) · [문헌 검토](docs/experiments/mobse_literature_review_2026-09-17.md) · 실행 보고서 `results/redesign_v1/20260917_3c458d507e82_nocfg/reports/` (부록 A–BG) · 자원 계획 같은 폴더 `resource_budget.md`

### 주장하지 않는 것
최초 brain MoE, atlas-free, cognitive load marker, sparse-compute 우위는 기본 주장이 아님. dFCExpert(IEEE TMI 45(3), 2026-03)와 MoRE-Brain(NeurIPS 2025)이 직접 선행연구임. 인지부하 정답·개별 뇌 상태·인과적 인지기전을 측정한다고 하지 않음. 합성·단일 장비 비용 측정을 효율 우위 근거로 쓰지 않음.

## 확정된 자료 사실 (Wave 1 감사, 1,295 run)

| cohort / task | runs | native TR | volumes |
|---|---:|---:|---:|
| ds002785 (PIOP1) / emomatching | 208 | **2.0** | 135 |
| ds002785 / workingmemory | 207 | **2.0** | 162 |
| ds002785 / restingstate | 210 | 0.75 | 480 |
| ds002790 (PIOP2) / emomatching | 222 | **2.0** | 135 |
| ds002790 / workingmemory | 224 | **2.0** | 160 |
| ds002790 / restingstate | 224 | 2.0 | 240 |

- 전건 분석 window 성립. TR은 조합마다 단일값이라 추정할 자리가 없음.
- **두 cohort의 rest가 서로 다른 TR을 씀** — target TR을 rest에서 유추하면 안 됨.

### ⚠️ 기존 파생 시계열은 주분석에 재사용 금지
기존 추출이 **모든 run에 0.75초를 적용**해 두 primary target이 2.67배 잘못된 rate로 필터링됨 (gate evidence `existing extraction TR correctness` = fail, rev59 에도 그대로). `data/aomic`, `data/current_canonical`, `data/legacy_*` 의 시계열은 이 사유로 주분석에서 제외됨. **잘못 필터링한 시계열을 resample하는 것은 복구가 아님.**

### 현행 추출 (v3)
- 통과대역 **0.008–0.2 Hz** (개정 P9, 결정 원문 "통과대역 0.2 Hz로"), 차단대역 DCT 기저를 nuisance 와 **동시 회귀** (`mobse/v2/extract.py` `BANDPASS_LOW_HZ`·상한). 산출물은 `derivatives_v3*`. `derivatives_v2*` 는 대체됨 (단 `derivatives_v2/pilot_tech/splits/folds.json` 은 pilot 측정이 씀).
- 동시 회귀 설계는 1,291 run 전수에서 rank 결손 0, 분석 run 수치적으로 안정 (보고서 부록 BG, rev59).
- pilot 31명 창 372 에서 0.2–0.25 Hz 잔여 전력 비율 중앙 약 0.004 — 필터 적용 기대값 수준, 누락 기대값 (약 0.19) 과 겹치지 않음 (보고서 부록 BH, rev60).
- pilot ok run 93 을 원 TR 로 재계산하면 저장 창과 바이트 동일 372/372, 결합 설계 잔차의 차단대역 (f<0.008·f>0.2 Hz) DCT 전력 비율 ≤3.1e-15 (nuisance 만이면 0.3–37%) (보고서 부록 BJ, rev62).

## Cohort·분할 (WI-03, 잠김)

| cohort | 전체 | 적격 | 역할 |
|---|---:|---:|---|
| ds002785 (PIOP1) | 216 | **157** | 주 (pilot 31 / main 126, outer test 26/25/25/25/25) |
| ds002790 (PIOP2) | 226 | **189** | 외부 hold-out (분할 없음) |

- 적격 규칙은 프로토콜 §3.3, 세 task 전부 보유 요구. group_id 는 1 subject = 1 group (관계 metadata 부재, 개정 P4).
- split_hash `ace5f4a4…` (불변). 외부 최종 선택용 main pool 3-fold (seed 20262000) 는 별도 `external_folds.json` (42/42/42, external_split_hash `40e50350…`, 결정 17).
- h197 경로 (data root 상대): subjects `derivatives_v3/cohort_piop1/subjects.jsonl`, 분할 `derivatives_v3/splits_piop1_p7/{folds.json, external_folds.json}`.

## Gate 현황 (gate_evidence.json revision 77 — WI-11 과 G5, 2026-09-29)

| Gate | 상태 |
|---|---|
| G0 Provenance | **cleared** (검사 10건: pass 10) |
| G1 Measurement lock | **cleared_with_limitations** (검사 8건: pass 6 · fail 2 — group_id 구성, δ=0.02 정밀도. 둘 다 계획서 P4·§8 이 정한 알려진 한계) |
| G2 Implementation lock | **cleared** (검사 5건: pass 5) |
| G3 Internal release | **cleared** (검사 3건: pass 3 — §7 fit 예산 · A–D main OOF 완료 기준 · 보조 비교 완료) |
| G4 External release | planned (검사 1건 pass. `unresolved` 는 U17 만 — **결정 27 로 이 버전에서는 외부 단계를 하지 않는다**. 그 사실을 gate 에 어떻게 적을지는 **미정 — 보고 사항**) |
| G5 Interpretation | **cleared_with_limitations** (검사 5건: pass 5 — WI-11. 한계 셋: 외부 검증 없이 내린 해석 · 계획서 §8 사전등록 이탈 · H2 불확실과 interaction 판독 철회) |

- 정본은 `results/redesign_v1/20260917_3c458d507e82_nocfg/gate_evidence.json` 이며 **revision이 올라가면 이전 판정표를 인용하지 말 것.** 순서는 revision 번호로만 봄 (`timestamp_utc` 는 거꾸로 간 적 있음).
- rev73 이 바꾼 것 (결정 25-1 = main_oof 문서 "gate 표기 권고" 1–6): G0 `conditionally_cleared`→`cleared` (U3·U6 삭제, U10 은 G1 로), G1 `in_progress`→`cleared_with_limitations` (**check 판정은 불변**), G2·G3 `planned`→`cleared`, G3 check 1→3, "blocked by G0"·"blocked by G0/G1" 표기 전부 삭제. G4·G5 `status` 는 planned 그대로. 보고서 부록 BX.
- rev73 이 더한 기록: `thread_pinning_rev73` (부록 BT) · `decision23_main_oof_rev73` (부록 BU·BV) · `decision24_aux_comparison_rev73` (부록 BW) · `decision25_gate_status_rev73` (부록 BX). 09-28 산출물은 data root 에 있어 17번 해시 검사 대상이 아니며 `data_root_outputs` 에만 적는다.
- rev72 `not_done` 의 "명세 6" 은 09-27 커밋 (마감 6단계 추가) 로 끝났다 — rev73 `decision25_gate_status_rev73.corrections` 에 정정해 적었다 (과거 revision 블록은 다시 쓰지 않는다).
- G1 의 fail 2건은 없애지 않는다: [0] group_id 는 개정 P4 (1 subject = 1 group), [6] δ=0.02 정밀도는 §8 의 "불확실 가능성 명시" 항목. main OOF 는 이 잠금으로 실행됐다.
- 측정 잠금 현행 `9b7b11cf8576…` (locked_at 2026-09-26T05:22:16Z), 구현 잠금 `bcf1fec22676…`. 잠금은 `mobse/v2/*.py` 를 해시한다 — **`mobse/v2` 를 바꾸면 잠금 재생성 + gate evidence 새 revision** (`scripts/h197/18_build_measurement_lock.py --overwrite --reason "..."`). `scripts/h197/`·`tests/v2` 만 바꾸면 잠금 재생성은 불요, gate evidence 해시만.

## 실행 호스트와 경로

- **정본 저장소는 Mac** `/Users/hwon/projects/Git/Manuscript/MoBSE` (branch `redesign-v1`) — 편집·커밋은 Mac. **푸시는 지시가 있을 때만** (커밋 규약 7).
- **실행 호스트는 h197** (`ssh -o BatchMode=yes h197`). 사본 `/mnt/data/code/MoBSE`, venv `/mnt/data/mp2026/MoBSE_dataset/venv-mobse-v2`. 최종 판정(마감)은 h197.
- Mac → h197 동기화: `cd /Users/hwon/projects/Git/Manuscript && rsync -a --exclude=/data/ --exclude=/artifacts/ --exclude=/nilearn_cache/ --exclude=__pycache__/ --exclude='*.pyc' MoBSE/ h197:/mnt/data/code/MoBSE/` — **`--delete` 금지, `__pycache__`·`*.pyc` 제외 필수** (2026-09-24 stale pyc 사고).
- data root: `h197:/mnt/data/mp2026/MoBSE_dataset`
  - `aomic_wave1/` — 메타데이터 (sidecar·confounds·events)
  - `aomic_wave2/` — BOLD 본체
  - `derivatives_v3/`, `derivatives_v3_piop2/` — v3 추출 파섬 창·manifest·코호트·분할 (**정본**)
  - `atlas_2009c/` — Schaefer-100 MNI152NLin2009cAsym (ROI 순서 규정)
- Mac `.venv` (python 3.11, torch 2.10) 에서도 v2 시험이 돈다 — **`.venv/bin/python` 을 직접 부를 것** (activate 후 `python` 은 torch 없는 다른 python 으로 풀림).
- 물리 경로 전체는 Notion `🗄️ Data Assets` 에 등록됨 (시리즈 `MOBSE`).

> **아틀라스 주의**: `~/nilearn_data/schaefer_2018` 은 FSLMNI152 공간이고 h197 `atlas_2009c` 는 MNI152NLin2009cAsym 공간임. **섞어 쓰면 안 됨.**

## v2 구현 현황 (2026-09-25 20:1x KST 실측, HEAD)

- `mobse/v2/` 파일 18개 · 8,984줄 — manifests · preprocess · splits · features · templates · models · train · fitting · baselines · evaluate · statistics · cli · cohort · config · extract · labels · locks (+ `__init__`)
- `tests/v2/` 시험 파일 40개 · 12,244줄 · **1,166 시험 수집** (Mac collect-only). **수치가 슬롯마다 바뀌니 인용하지 말고 다시 잴 것.** 마감 결과는 인수인계 문서 "현행".
- CLI 하위 명령 11개 (`mobse/v2/cli.py` `SUBCOMMANDS`): `validate`·`prepare`·`split`·`fit`(A–D + NG·SG)·`fit-s`·`select-ad`·`select-comparator`·`select-s`·`evaluate`·`report`·`report-comparison`
- 학습 규칙 (P8-b, 결정 15): `train.MIN_UPDATES = 5000`, `MAX_EPOCHS = 400`, early stopping 은 최소치 이후에만, inner 평가는 best checkpoint. `INNER_SEED = 42`, `MODEL_SEEDS = (42, 43, 44)` (fit·선택 CLI 가 잠긴 seed 밖을 거부). A–D 모델 구조는 변경 보류.
- `configs/redesign_v1/` — `main.yaml` · `pilot.yaml` · `external.yaml`. **config는 코드 상수를 다시 적어 잠그는 문서임.** 값을 바꿔 동작을 바꾸는 용도가 아니며, `mobse/v2/config.py` 검증기가 상수와 대조해 어긋나면 실패시킴. 미지의 키는 오타로 보고 거부함. 잠긴 키 39개 ↔ 소비 함수 대응표는 `tests/v2/test_config_consumption.py`.

### v2 실행
```bash
PYTHONPATH=. python -m mobse.v2.cli <하위 명령> --help
PYTHONPATH=. python -m pytest tests/v2 -q
```
**경로는 전부 명시해야 함 — glob fallback 없음.** fit 이웃 파일(`fit_report.json`·`window_predictions.jsonl` 등)과 `external_folds.json` 만 고정 이름으로 옆에서 읽는다.

### 마감 5단계 (h197, 매 변경마다 전부 rc=0 일 때만 커밋) + 6단계 구현 잠금 검증 (결정 21 명세 6, 09-27)
```bash
cd /mnt/data/code/MoBSE; R=results/redesign_v1/20260917_3c458d507e82_nocfg; D=/mnt/data/mp2026/MoBSE_dataset
PYTHONPATH=. python -m pytest tests/v2 -q
python scripts/h197/17_verify_gate_hashes.py $R
python scripts/h197/22_crosscheck_reported_numbers.py $R
python scripts/h197/19_verify_measurement_lock.py --data-root $D --repo-root . --release $R
python scripts/h197/25_verify_window_files.py --data-root $D --lock $R/locks/measurement_lock.json
python -B scripts/h197/27_build_implementation_lock.py --verify --data-root $D --repo-root . --release $R   # 6: h197 에서만 의미, rc≠0 이면 구현 잠금 새 판 필요
```

### artifact 계약
`results/redesign_v1/<release_id>/` 아래 `provenance/ qc/ splits/ locks/ fits/ predictions/ statistics/ reports/`.
`release_id` = `YYYYMMDD_<short-code-hash>_<config-hash-prefix>`. **같은 release 결과를 덮어쓰지 않으며** 실패 재시도는 attempt 번호를 덧붙임. 데이터·run 단위 provenance 는 커밋하지 않음.

## 고정 운영 규칙
- main OOF 는 **결정 23 (2026-09-28) 으로 실행 완료**, 보조 비교는 결정 24 로 완료. **null 민감도 (WI-09) 는 결정 25-2·25-5 로 승인** (기록·커밋 뒤 착수). **외부 선택/최종 fit·PIOP2 평가 (WI-08) 는 결정 27 로 현 버전에서 하지 않음** — 새 탐색 버전의 확증용으로 남긴다. 다시 열려면 선생님 원문 승인이 필요하다. 결정 17 (외부 분할) 도 외부 실행 승인이 아님.
- 공용 저장소(NAS, bmc-storage 등)에 쓰지 않음. `/tmp` 에 정본 산출물을 두지 않음.
- 돌연변이 시험은 bytecode 없이 (`python -B` + `PYTHONDONTWRITEBYTECODE=1`), 돌연변이 뒤·rsync 전·잠금 재생성 전에 `find mobse scripts tests -name '*.pyc'` 0 확인.
- 커밋 메시지는 위 **커밋 규약** 절을 따른다 (영문 1줄·20~25단어·co-author 없음; 5건 이하는 선택). 여기에 다시 적지 않는다.

## Code Conventions
- Python 3.9+, type hints, Google-style docstrings, snake_case
- `PYTHONPATH=.` 로 스크립트 실행
- **편집 전 백업**: `cp file .backup/file_$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S).ext`
- 과거 산출물을 새 경로로 복사해 새 결과처럼 보고하지 않음
- main 성능 접근 뒤의 설계 변경은 새 exploratory version으로 분리

## 기록 체계
- 재설계 진행 상태·선생님 결정 원문: 저장소 `docs/handoff/` 가 **정본**이다. claude.ai Project "MoBSE" 사본 동기화는 하지 않는다 (2026-09-29 지시). 새 결정은 `docs/handoff/` 문서에 원문으로 적는다.
- 작업 기록은 Notion `📓 Work Logs` 시리즈 **`MOBSE`** 에 남김 (`/bmc-records:bmc-work-log`). 물리 경로는 `🗄️ Data Assets` 에만 기재하고 Work Log 본문에는 쓰지 않음 (리포 상대 경로는 예외).

## Legacy (v1) — 참고용

재설계 이전 코드와 산출물은 보존되어 있으나 **주분석 근거로 쓰지 않음.**

- 기존 실험 자산: 학습 요약 352개, seed result 624개, checkpoint 624개 (`artifacts/`)
- 이미 수행된 것: strict subject split(ABIDE·simulation 각 10 seed), nuisance 민감도 3조건, prior/routing sweep, baseline 4종 비교, ds000030↔ds000243 전이, ETTh1 temporal encoder 통제
- **이 수치는 독립 가설 검증 352건을 뜻하지 않음** — 재실행·smoke test·탐색 튜닝 포함

### v1 구현 세부 (해당 코드 수정 시에만)
- `load_template_bank(path, states)` 는 인자 2개 필요
- YAML은 `0.001` 형식 사용 (`1e-3` 은 safe_load가 문자열로 파싱)
- `use_amp: True` 는 CUDA에서만 활성 (CPU는 graceful fallback)
- `_canonical_task()` 가 `"hcp"` → `"os"` 매핑
- `routing_k` 기본 2, `routing_mode` 기본 `"soft"`
- expert collapse 수정: `_routing_weights()` 의 `scatter_(values)` → `weights * mask`

## Next Steps
정본은 `docs/handoff/mobse_decisions_2026-09-29.md` "결정 25 이후 진행" 과 위 인수인계 절. 2026-09-29 기준 요지:
1. **설계안 남은 결정 (초안 §8)** — G-a 포화 기준값 · 선별 장소 · G-b 검정력 기준값 · G-c 의 M · δ·endpoint 해상도 · 후보 전부 탈락 시 대안. 그 뒤 **G-a 선별을 실제로 돌려** 축을 정한다 (결정 28-1).
2. **현 버전 마감 문서 (WI-11 연구 결과 패키지)** — claim–evidence 표, dataset flow, 핵심 2 contrasts 와 S 결과, 음성 결과, **사전등록 이탈 사유 (부록 CA.3)** 포함.
3. **PIOP2 는 열지 않음** (결정 27). `external_folds.json` (결정 17) 과 미구현 배선은 그대로 둔다 — 새 버전의 확증용으로 남긴다.
4. 결정 불요 후보: h197 정리 (삭제는 선생님 확인 뒤 — `pilot_e2e/20260926_1515c/`·`impl_lock/20260926_2215d/`·`main_oof/`·`null_sens/` 는 지우지 않음).

## Excluded Datasets (and why)
- **HCP**: DUA 필요, 데이터 접근 불확실
- **AOMIC-ID1000 (ds003097)**: resting-state 없음 → low-demand routing anchor 없음
- **ds000030 (UCLA CNP)**: 주 target의 대체 후보로 쓰지 않음. 과거 cross-site 전이 실험의 입력이었고 데이터는 `data/ds000030/` 에 남아 있음

> **PIOP2는 더 이상 제외 대상이 아님.** 2026-04-17판은 "짧은 스캔 → dFC 창 부족"을 이유로 제외했으나, Wave 1 실측 결과 emomatching 222 run · workingmemory 224 run이 전건 분석 window를 만족했고 적격 189명으로 **외부 hold-out에 채택됨.**
