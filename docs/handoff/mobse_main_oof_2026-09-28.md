# MoBSE — 결정 23·24 · main OOF 실행 기록 (2026-09-28, 대화 세션 작성)

> **이 문서가 2026-09-28 이후 현행 정본이다.** 결정 0–22 원문과 그 세부, 운영 규칙, 마감 절차, 재발 방지 장치는 `claude/mobse_redesign_g0_handoff_2026-09-17.md` (09-27 09:3x 판, 손대지 않고 보존) 를 그대로 따른다. 두 문서가 어긋나면 이 문서의 결정 23·24 와 "현행" 이 앞선다.
> 인수인계 문서를 통째로 다시 쓰지 않고 이 문서를 따로 만든 이유 (구현 선택): 약 100 KB 문서를 손으로 다시 옮기면 전사 오류 위험이 커서 (남은 작업 13). 인수인계 문서에 결정 23·24 행을 합치는 일은 남은 작업 A.
> 시각은 Mac/h197 `date` 로 잰 값. (갱신 2026-09-28 21:3x KST — 보조 비교 완료·결과 열람)

## 결정 (원문)

| # | 원문 | 상태 |
|---|---|---|
| 23 | **"main OOF 착수 승인"** (2026-09-28 15:4x KST, 대화). 직전 "그러면 바로 적용하고 실행해 주길" 은 세션이 main 승인으로 읽지 않고 pilot 스레드 고정 측정만 실행한 뒤 승인 원문을 따로 요청했다 | **완료 (15:44 → 18:55 KST, h197, `ALL_RC=0`)** |
| 24 | 19:0x 보고의 "정해 주실 것" 세 항목에 대한 회신 (2026-09-28 19:1x KST): **"1. 결과 열람 후 보고, 보고 형식은 쉬운 한국어로; 2. S 후보와 구조 비교(NG·SG): 1의 결과에 종속적일 경우 결과 확인 후 권고, 독립적이면 바로 수행; 3. gate 표기: 권고 사항을 알려주길"** | 1 완료 · 2 **독립으로 판단 → 완료 (19:07 → 21:02 KST, `ALL_RC=0`)** · 3 권고 보고 (gate 는 바꾸지 않음) |

**결정 23 정한 것**: A–D main OOF — WI-07 main inner 480 + outer 60 + select-ad 5 + evaluate + report. **정하지 않은 것**: null 민감도 (WI-09), 외부 PIOP2 (WI-08), gate `status`·"blocked by G0" 표기, 결과를 본 뒤의 설계·grid·δ·N 변경 (계획서 §3·§8 금지).

**결정 24 항목 2 판단 근거 (세션 판단, 보고)**: S 4 후보 grid·선택 규칙 (§6, P11), NG·SG 학습·선택 규칙 (결정 14), A−S·A−NG·A−SG 보조 contrast (§8 P12, main 결과 전 사전 등록) 가 모두 main 결과와 무관하게 정해져 있고, 실행 입력은 main pool 분할·main evaluate 산출물뿐이다 → "독립" 으로 보고 바로 실행. 결과가 S·NG·SG 실행 여부·방식을 바꾸는 규칙은 계획서에 없다 (grep).
**결정 24 항목 3**: 권고만 — gate evidence 는 선생님 결정 전 바꾸지 않는다.

## 선생님 지시 (운영, 원문)

- 09-28 16:5x KST: "확인하지 못한 것: azcopy 작업이 언제 끝나는지. <-- 이건 확인하지 말 것" → azcopy 종료 시점은 확인·보고하지 않는다.

## 착수 전 측정 — 스레드 고정 (pilot 기술 분할, main pool 미사용)

- 틀 Mac `.backup/slot_thr_0928/{thr_driver.py, thr_setup.sh, thr_compare.py}` (커밋 안 함), 산출 h197 `$D/pilot_threads/20260928_thr2/`. outer 0 inner fit 96, k=4, 프로세스당 `OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=2`.
- 결과: **창 예측·checkpoint·eval_loss 96/96 바이트 동일**, fit 당 벽시계 중앙 158.9 s → 73.5 s (학습 시간은 거의 같음 — 줄어든 것은 CPU 단계). 대조군은 돌리지 않음 (가역 판단).

## main OOF 실행 — 완료

- 산출 h197 `$D/main_oof/20260928_1cd4054_main_a2/` (**구현 선택** — 저장소 release `fits/` 는 `.gitignore` 밖). attempt 1 (`…_main`) 은 코드 사본 `diff -r` 가 미추적 파일 때문에 멈춤 (fit 0, 남겨 둠) → 추적 파일 sha256 대조로 attempt 2.
- 구동기 `.backup/slot_thr_0928/main_driver.py` (sha256 `b252d579394a…`) + `main_setup.sh`. preflight: HEAD, 작업트리 깨끗, 측정 잠금 45/45, 창 파일 rc=0, 구현 잠금 38/38, gate 해시 rc=0.
- 입력 sha256 앞 16자: folds `242ba87d6101f704` · subjects `5ab1933922027dee` · windows `0750c81c0670df1f` · main.yaml `ef4b16509f2da80c`.
- 벽시계: inner 480 **2 h 44 m** (fails 0) · select-ad 5 rc=0 · outer 60 **26.4 분** · evaluate·report rc=0 · `ALLDONE` 09:55:10Z.
- **WI-07 완료 기준 전부 충족** (`.backup/slot_thr_0928/main_check.py` → `$O/summary/completion_check.json`): primary checkpoint 고유 60, window 예측 12,096 = 126×2×4×3×4, run 예측 1,008, (subject, 칸) 504 쌍 전부 24 행·outer fold 하나, 누설 0, 배정 밖 예측 0, inner best epoch 295–312.
- 선택 (기록): config o0 0 · o1 0 · o2 4 · o3 1 · o4 0; 공통 E 298 · 298 · 297 · 297 · 298.
- sha256: evaluation.json `02f6ac5e1feb…` · run_predictions.jsonl `e377a18939de…` · statistics.json `f0a9847bb61c…` · driver.log `adcd415b16c4…` · selection o0–o4 `375b58ecb3b6…`/`6c78a9abe83a…`/`59fc09a2e4fc…`/`b5421eb82b8a…`/`6adc4ee3bbe0…`.

## primary 결과 (statistics.json, 19:1x KST 열람 — 결정 24 항목 1)

N = 126 (group = subject), paired bootstrap seed 9001 · 10,000 회, 칸 간 같은 재표집. primary CI 는 97.5% (1.25–98.75 백분위, 계획서 §8), 보조는 95%.

| 비교 | 점추정 | CI | 계획서 §8 규칙에 따른 판독 (report 산출 문구) |
|---|---:|---|---|
| **H1 A−B** (입력 의존 routing) | **+0.155** | [+0.095, +0.214] (97.5%) | 하한 > δ 0.02 — 선택한 최소 효과 이상의 우월성 지지 |
| **H2 A−C** (정렬된 brain bank 대 공동 ROI-permuted null) | **−0.016** | [−0.052, +0.020] (97.5%) | CI 가 0 포함 — 불확실. 비유의를 효과 없음·동등성으로 바꾸지 않는다 |
| interaction (보조) (A−B)−(C−D) | +0.052 | [+0.004, +0.099] (95%) | 하한 > 0 이나 ≤ δ — 추가 기여는 지지, 실질적 우월성 확정 아님 |

칸별 BA (95%): A 0.877 [0.837, 0.917] · B 0.722 [0.675, 0.770] · C 0.893 [0.853, 0.933] · D 0.790 [0.742, 0.833]. `both_primary_lower_gt_0: false` → §8 에 따라 **두 기여를 함께 주장할 수 없음**. report `g3_verdict.completeness_and_consistency: pass`, `significance_is_gate: false`. caveat: 내부 OOF bootstrap 은 고정 학습 결과에 조건부 (§8).

## 보조 비교 — S 후보 4 · NG·SG (결정 24 항목 2) — 완료

- 산출 h197 `$D/main_oof/20260928_1cd4054_aux_a1/`. 구동기 `.backup/slot_thr_0928/aux_driver.py` (main 코드 사본 그대로, k=4, 스레드 2): inner (NG·SG `fit` 240 + S `fit-s` 480) → select (select-comparator 10 + select-s 5) → outer (선택 기록 `outer_plan` 의 `cli` 그대로) → report-comparison.
- **v1 결함·정정**: S 후보 이름을 "S1" 로 줄여 써서 `fit-s` argparse 가 거부 (rc=2, fit 미실행 480 호출). smoke (`$D/main_oof/20260928_aux_smoke/`) 로 발견. v1 은 NG·SG inner 240 을 끝낸 뒤 11:14:12Z 멈춤 (`run_all_v1.rc` ALL_RC=1), `aux_resume.sh` 가 v2 로 같은 root 에서 이어 돔 (11:14:16Z RESUME, 끝난 fit 건너뜀). 재발 방지: 새 구동기는 CLI 인자 값을 코드 상수에서 가져오거나 첫 fit smoke 를 먼저 돌린다.
- 벽시계: NG·SG inner 10:07–11:14Z · S inner 11:14–11:48Z · select 15 전부 rc=0 · outer 11:48–12:01:59Z · report-comparison rc=0 · `ALLDONE` 12:02:00Z · `run_all.rc` ALL_RC=0. v2 이후 fit rc≠0 **0**.
- 완료 점검: outer NG 15 · SG 15 · S 13 (MLP 4 fold × 3 seed + logistic 1). S outer 예측 2,624 행, subject 126, **학습 subject 가 test 예측에 섞임 0**, 배정 밖 fold 0, 각 S outer fit 의 fit_subjects = 그 fold train 전부. S 미수렴 제외 0 (5 fold 모두).
- 선택 (기록): S — o0 S4 (FC MLP) config 3 · o1 S4 config 4 · o2 S4 config 4 · o3 **S3 (FC logistic) C=10000** · o4 S4 config 2 (MLP outer E 295–296). NG config o0–o4 0·0·0·0·3 (E 298–304). SG config 0·0·1·0·1 (E 297–304).
- sha256: comparison_statistics.json `a62e6239fbab…` · driver.log `40f751f587cb…`.

### 보조 비교 결과 (comparison_statistics.json, 21:2x KST 열람 — 전부 보조·95% 기술적 CI·primary 아님)

| 비교 | 점추정 | 95% CI | report 판독 |
|---|---:|---|---|
| **A−S** (MoBSE 대 최선 단순 기준선) | **−0.123** | [−0.163, −0.083] | 상한 < 0 — 반대 방향 (S 가 더 높음) |
| A−NG (그래프 없는 fusion MLP) | −0.012 | [−0.052, +0.028] | CI 가 0 포함 — 불확실 |
| A−SG (평균 그래프 하나) | +0.067 | [+0.016, +0.119] | 하한 > 0 이나 ≤ δ — 추가 기여 지지, 실질적 우월성 확정 아님 |

칸별 BA (95%): **S 1.000 [1.000, 1.000]** (126 명 전원 두 run 모두 정답) · NG 0.889 [0.845, 0.929] · SG 0.810 [0.766, 0.853].
- 읽는 법 (기록): 이 target (emomatching 대 workingmemory run identity) 은 FC Fisher-z 를 쓰는 단순 분류기 (S3·S4) 가 완벽히 가른다. MoBSE A 는 그보다 12 %p 낮다. 계획서 §8 은 A−S 를 보조로 두었으므로 primary 판정은 바뀌지 않는다. 결과를 본 뒤 설계·grid 를 바꾸면 새 exploratory version (§3).
- 누설 점검은 코드 (`_load_s_outer`) + 세션의 독립 재집계 두 번 다 0.

## gate 표기 권고 (결정 24 항목 3 — 권고만, 적용은 선생님 결정 뒤)

1. **G3 Internal release**: 계획서 §10 조건 "완전성과 정합성 통과; 유의성 불요" — A–D (WI-07 완료 기준 전부, report g3 5 검사) 와 보조 비교 (outer 43 fit·누설 0·report-comparison rc=0) 모두 충족 → **`cleared` 권고** (보조 비교까지 끝났으므로 조건 충족).
2. **G2 Implementation lock**: check 5/5 pass, 오늘 preflight 에서 구현 잠금 38/38 재확인, main 이 그 잠금 코드로 실행됨 → **`planned` → `cleared`** 권고.
3. **G0 Provenance**: check 10/10 pass. `unresolved` 의 U3·U6 은 낡은 표기, U10 은 계획서 P4 가 처리한 알려진 한계 → **`cleared`**, U3·U6 제거, U10 은 G1 한계로 옮겨 적기 권고.
4. **"blocked by G0"** (G2·G3·G5), **"blocked by G0/G1"** (G4): G0 를 올리면 **삭제** 권고.
5. **G1 Measurement lock**: fail 2 ([0] group_id·[6] δ 정밀도) 는 계획서 P4·§8 이 정한 알려진 한계 → 판정은 `fail` 그대로, status **`cleared_with_limitations`** (새 값) 권고 — 대안 `in_progress` 유지.
6. G4 (외부)·G5 (해석) 는 `planned` 그대로.

## 남은 작업

- A. 기록: 보고서 새 부록 (스레드 측정 + main OOF + primary 결과 + 보조 비교) + gate evidence 새 revision (`data_root_outputs`, rev72 `not_done` "명세 6" 정정, 선생님이 고른 gate 표기) → 마감 5+1 단계 (fit 없음 — 지금 가능) → 커밋 (푸시 안 함) → 인수인계 문서에 결정 23·24 행 합치기 + CLAUDE.md 포인터 갱신.
- B. 선생님 결정 대기: gate 표기 (권고 1–6), A−S 결과 (단순 기준선 100%) 를 논문·다음 단계에서 어떻게 다룰지, null 민감도 (WI-09)·외부 PIOP2 (WI-08) 일정.
- C. 스레드 고정을 자원 계획 (`resource_budget.md` 9.2 후보) 에 반영. NG·SG 실자료 parameter/비용 집계 (`not_reported`).
- 1시간 보고 예약은 보조 비교 완료로 끝냄.

## 확인하지 못한 것

- main 규모에서 스레드 2 가 최적인지.
- H2 가 불확실하게 나온 이유, 단순 FC 기준선이 100% 인 이유 (target 자체가 FC 로 쉽게 갈리는지, 다른 요인이 있는지) — 추가 분석은 계획 밖이라 하지 않음.
