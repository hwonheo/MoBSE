# WI-11 — 연구 결과 패키지 (재설계 v1 내부 마감) · 2026-09-29

> **무엇인가**: 재설계 v1 을 **내부 결과로 마감**하는 문서다 (선생님 결정 27, 2026-09-29). PIOP2 외부 검증은 하지 않았고 그 사유를 §7 에 적었다.
> **무엇이 아닌가**: 논문 원고가 아니다. 주장마다 원 artifact 를 잇는 표와 한계 목록이다.
> 계획서 §10 G5 필수 산출물 "claim–evidence 표, 비용·제한·재현 패키지", 다음 단계 조건 "각 주장과 원 artifact 연결" 에 대응한다.
> 모든 수치는 산출물에서 다시 잰 값이며 출처를 함께 적었다. `[추정]` 은 재지 않은 값이다.

## 1. 한 문단 요약

training-rest 에서 만든 graph bank 의 **입력 의존 routing 은 이 target 에서 뚜렷한 이득을 준다** (H1 A−B +0.155, 97.5% CI 하한 +0.095 > δ). **정렬된 뇌 배선도의 추가 가치는 확인되지 않았다** (H2 A−C −0.016 [−0.052, +0.020], 불확실). 계획서 §8 규칙에 따라 **두 기여를 함께 주장할 수 없다.** 그리고 이 target 은 FC Fisher-z 를 쓰는 단순 분류기가 126 명 252 run 을 **전부** 맞힌다 (S 1.000) — MoBSE 는 그보다 12 %p 낮다. 따라서 이 결과는 "MoBSE 가 좋다" 가 아니라 **"이 target 은 이 가설을 검정하기에 부적절했다"** 로 읽는 것이 옳다.

## 2. 자료 흐름 (Wave 1 실측 → 분석 단위)

| 단계 | 수 | 출처 |
|---|---:|---|
| Wave 1 감사 run | 1,295 | `provenance/h197_wave1/wave1_runs.jsonl` |
| PIOP1 (ds002785) 전체 subject | 216 | `participants.tsv` |
| PIOP1 적격 (세 task 전부 보유 + QC) | **157** | `derivatives_v3/cohort_piop1/subjects.jsonl` |
| pilot (기술 검증 전용, 모든 main·final fit 에서 제외) | 31 | `splits_piop1_p7/folds.json` |
| **main pool (primary 분석)** | **126** | 같은 파일, split_hash `ace5f4a4…` |
| outer test 크기 | 26 / 25 / 25 / 25 / 25 | 같은 파일 |
| PIOP2 (ds002790) 적격 — **쓰지 않음** | 189 | `derivatives_v3_piop2/cohort_piop2/subjects.jsonl` |
| primary endpoint 단위 | subject 126 · run 252 · 창 12,096 | `evaluate/evaluation.json` |

- 창은 60 초 · 표본 30 · 시작 12/72/132/192 초 (config `main.yaml`).
- 통과대역 0.008–0.2 Hz, nuisance 와 차단대역 DCT 기저를 **동시 회귀** (개정 P9·P10).
- **기존 파생 시계열은 쓰지 않았다** — 모든 run 에 0.75 s 를 적용해 두 primary target 이 2.67 배 잘못된 rate 로 필터링됐기 때문이다. 재추출본 `derivatives_v3*` 만 썼다.

## 3. claim–evidence 표

각 행의 "근거" 는 h197 data root 상대 경로이며 sha256 은 gate evidence `data_root_outputs` 에 있다.

| # | 주장 | 수치 | 근거 artifact | 보고서 |
|---|---|---|---|---|
| C1 | 입력 의존 routing 은 추가 가치를 준다 (H1) | A−B **+0.1548** [+0.0952, +0.2143] (97.5%) | `main_a2/report/statistics.json` `f0a9847bb61c` | 부록 BV.2 |
| C2 | 정렬된 bank 의 추가 가치는 **확인되지 않았다** (H2) | A−C **−0.0159** [−0.0516, +0.0198] | 같은 파일 | 부록 BV.2 |
| C3 | 두 기여를 함께 주장할 수 없다 | `both_primary_lower_gt_0: false` | 같은 파일 | 부록 BV.2 |
| C4 | H2 의 불확실은 **순열 선택 탓이 아니다** | 다섯 null 판 전부 A−C ∈ [−0.016, 0.000], CI 모두 0 포함 | `null_sens/…_a1/summary/null_sensitivity.json` `5ddfee4b3883` | 부록 BY.6 |
| C5 | 보조 interaction 판독은 **철회한다** | primary 판만 하한 +0.0040 > 0; 민감도 네 판 모두 하한 ≤ 0 | 같은 파일 | 부록 BY.6 · CA.4 |
| C6 | 이 target 은 단순 FC 분류기가 완전히 가른다 | S **1.000** [1.000, 1.000]; A−S **−0.1230** [−0.1627, −0.0833] | `aux_a1/report_comparison/comparison_statistics.json` `a62e6239fbab` | 부록 BW.6 |
| C7 | 그래프 없는 fusion MLP 가 A 와 구별되지 않는다 | A−NG −0.0119 [−0.0516, +0.0278] | 같은 파일 | 부록 BW.6 |
| C8 | 여러 graph 중 고르는 것은 단일 평균 graph 보다 낫다 | A−SG +0.0675 [+0.0159, +0.1190] (하한 > 0 이나 δ 이하) | 같은 파일 | 부록 BW.6 |
| C9 | A 가 놓치는 run 은 **본래 어려운 run 이 아니다** | A 감점 30 명 전원이 S 에서 만점; A 오답 31 개 중 18 개가 margin < 0.1 | `aux_a1/diagnostic/as_diagnostic.json` `e86625d873a9` | 부록 BZ |
| C10 | 누설은 없다 | 학습 subject 가 자기 test 예측에 섞임 **0**, 배정 밖 fold 예측 **0** (main·보조·null 민감도 전부) | `main_a2/summary/completion_check.json` `1635d855f8c1` 외 | 부록 BU.5 · BW.4 · BY.5 |

**주장하지 않는 것** (근거가 없으므로): 최초 brain MoE · atlas-free · cognitive load marker · sparse-compute 우위 · 인과적 인지기전 · 외부 일반화.

## 4. 칸별 결과 (balanced accuracy, 95% CI)

| 칸 | 정의 | BA | CI |
|---|---|---:|---|
| **S** | FC Fisher-z + logistic/MLP (단순 기준선) | **1.0000** | [1.0000, 1.0000] |
| C | null bank (ROI 순열) + 입력 의존 routing | 0.8929 | [0.8532, 0.9325] |
| NG | 그래프 없는 fusion MLP | 0.8889 | [0.8452, 0.9286] |
| **A** | 정렬된 brain bank + 입력 의존 routing | **0.8770** | [0.8373, 0.9167] |
| SG | 평균 graph 하나 | 0.8095 | [0.7659, 0.8532] |
| D | null bank + 고정 routing | 0.7897 | [0.7421, 0.8333] |
| B | 정렬된 bank + 고정 routing | 0.7222 | [0.6746, 0.7698] |

## 5. 비용 (모델별 학습 parameter · 실측 벽시계)

parameter 는 `ModelConfig(n_roi=100, n_samples=30, pca_dim=10)` 에서 센 값이다 (bank 는 buffer 라 학습 parameter 가 아니다).

| 모델 | 학습 parameter | 비고 |
|---|---:|---|
| A · C | **6,469** | 구조 동일, bank 만 다르다 |
| B · D | 6,021 | fixed gate 는 logits 3 개뿐 |
| SG | 6,018 | |
| NG | 5,154 | |
| **S3** (FC logistic) | **4,951** | outer fold 3 에서 선택됨 |
| **S4** (FC + 32-hidden MLP) | **158,498** | outer fold 0·1·2·4 에서 선택됨 |

→ **가장 자주 뽑힌 단순 기준선 S4 는 A 보다 parameter 가 24.5 배 많다.** MoBSE 가 작은 모델인 것은 사실이나 **이 결과로 효율 우위를 주장할 수 없다** — 정확도에서 12 %p 진다. 계획서 §1 이 효율 주장을 제외한 것과 일치한다.

| 실행 | fit | 벽시계 | 출처 |
|---|---:|---|---|
| main OOF (A–D) inner 480 + outer 60 | 540 | **3 h 11 m** | `main_a2/driver.log` |
| 보조 비교 (S·NG·SG) inner 720 + outer 43 | 763 | **1 h 55 m** | `aux_a1/driver.log` |
| WI-09 null 민감도 | 240 | **1 h 22 m** | `null_sens/…/driver.log` |
| 스레드 고정 이득 | — | fit 당 158.9 s → 73.5 s | `pilot_threads/20260928_thr2/compare.txt` |

## 6. 실패·음성 결과 (숨기지 않는다)

| 무엇 | 기록 |
|---|---|
| **H2 가 불확실하다** | 주가설 둘 중 하나가 지지되지 않았다. §8 규칙대로 비유의를 "효과 없음" 으로 바꾸지 않는다 |
| **검정력이 애초에 낮았다** | δ=0.02·N=126 에서 P(CI 하한 > 0) 0.048–0.191. main **전에** 기록돼 있었고 (gate G1 check [6]) 계획대로 수용하고 진행했다 |
| **interaction 판독 철회** | primary 판에서만 하한 > 0. 민감도 네 판은 모두 하한 ≤ 0 (부록 BY.6) |
| **target 이 포화됐다** | S 1.000. 09-29 에 만든 포화 선별 gate 를 pilot 31 에 적용하니 이 target 만으로 1.000 이 나왔다 — **그 gate 가 있었으면 막혔을 선택이다** |
| **모델이 ROI 정체를 거의 못 쓴다** | `C(x) = A(Pᵀx)` 수치 확인 (최대 차 1.19e−07) — 정렬이 성능에 들어갈 통로가 이웃 평활화 하나뿐이었다 |
| main OOF attempt 1 중단 | 코드 사본 대조를 `diff -r` 로 해서 미추적 파일 때문에 멈춤 (fit 0). 추적 파일 sha256 대조로 재실행 |
| 보조 비교 v1 구동기 결함 | S 후보 이름을 줄여 써 `fit-s` argparse 가 거부 (rc=2, fit 미실행 480 호출). smoke 로 발견, v2 로 이어 돌림 |

## 7. 외부 검증을 하지 않은 사유 (사전등록 이탈)

계획서 §8 은 "내부 결과가 음성이어도 외부 검증을 수행한다" 고 적었다. 결정 27 (2026-09-29) 은 **PIOP2 를 열지 않기로** 했고, 이는 그 항목의 이탈이다. 사유 넷을 남긴다.

1. WI-09 가 H2 의 불확실이 **순열 선택 탓이 아님**을 보였다 (C4). 같은 설계로 PIOP2 를 열면 같은 이유로 다시 불확실할 가능성이 크다 `[추정]`.
2. **PIOP2 는 한 번만 열 수 있다.** 확증력이 거의 없는 실행에 그 한 번을 쓰면 새 설계의 확증 수단이 사라진다.
3. **target 자체가 이 가설에 부적절하다는 증거가 모였다** (C6·C7·C9).
4. **내부 결과는 그대로 보고한다** — 음성 결과를 숨기려는 생략이 아니다. 이 문서 §6 이 그 기록이다.

PIOP2 의 외부 분할 (`external_folds.json`, 결정 17) 과 미구현 배선은 **그대로 둔다** — 새 탐색 버전의 확증용이다.

## 8. 한계

- 내부 OOF bootstrap 은 **고정된 학습 결과에 조건부**이며 training-set 변동을 완전히 반영하지 않는다 (§8).
- endpoint 해상도가 거칠다: 사람당 run 이 2 개뿐이라 subject 점수가 {0, 0.5, 1} 세 값이고 A·C 동점이 126 명 중 108 명이다.
- null 은 다섯 판뿐이다 — 분포가 아니다 (부록 BY.8).
- group_id 는 1 subject = 1 group 으로 두었다 (개정 P4). 가족·쌍둥이 식별 열이 `participants.tsv` 에 없다 (gate G1 check [0] `fail`, 알려진 한계).
- PIOP1·PIOP2 참가자 중복 여부는 공식 문서로만 판정한다 (gate G4 `unresolved` U17). AOMIC 논문은 모집 기간이 다르다고 적으나 겹치지 않는다는 문장은 없다.
- 복제 cohort (PIOP2) 는 **cross-site 가 아니다** — 같은 연구 환경이다.

## 9. 재현 방법 (실제로 돈 명령만)

호스트 h197, venv `venv-mobse-v2`, python 3.11.5 · torch 2.10.0+cu128 · CUDA 12.8.
코드 판본은 커밋 SHA 가 아니라 **잠금**으로 고정된다 — 측정 잠금 `9b7b11cf8576…` 의 `code_hash` `804d6ee17625…` 가 `mobse/v2/*.py` 를 해시하고, 구현 잠금 `bcf1fec22676…` 가 환경·config·CLI 까지 묶는다 (§10). 2026-09-30 에 팀 커밋 규약 (영문 1줄, co-author 태그 미사용) 에 맞춰 이력을 재작성했으므로 예전 커밋 SHA 는 더 이상 가리키는 대상이 없다 — 그래서 이 문서와 gate evidence 에서 커밋 SHA 기록을 지웠다. **잠금 해시는 그대로이며 재현의 기준은 그쪽이다.**

```bash
cd /mnt/data/code/MoBSE && PYTHONPATH=.
python -m mobse.v2.cli fit    --config configs/redesign_v1/main.yaml --splits <folds> --subjects <subjects> \
                              --windows <windows> --rest-manifest <rest> --task-manifests <emo> <wm> \
                              --output-dir <out> --cell {A|B|C|D|NG|SG} --outer-fold <o> --inner-fold <i> \
                              --model-seed <s> --config-id <c> --epochs <e> --device cuda
python -m mobse.v2.cli fit-s  ...      # S 후보
python -m mobse.v2.cli select-ad --config … --fit-manifest … --outer-fold <o>
python -m mobse.v2.cli select-comparator | select-s
python -m mobse.v2.cli evaluate --config … --predictions … --fit-manifest … --tasks emomatching workingmemory
python -m mobse.v2.cli report | report-comparison
```

**경로는 전부 명시해야 한다 — glob fallback 이 없다.** 구동기 (`main_driver.py`·`aux_driver.py`·`null_driver.py`) 는 `.gitignore` 영역이라 저장소에 없다; 각 산출 root 에 사본이 있고 sha256 은 gate evidence 에 있다.

## 10. 잠금과 검증

| 항목 | 값 |
|---|---|
| 측정 잠금 | `9b7b11cf8576…` (locked_at 2026-09-26T05:22:16Z) |
| 구현 잠금 | `bcf1fec22676…` |
| split_hash | `ace5f4a41446…` (불변) |
| config_hash (main) | `2a7d7d7f` |
| code_hash (`mobse/v2`) | `804d6ee17625…` |
| 마감 절차 | 6 단계 — 시험 · gate 해시 · 인용 수치 · 측정 잠금 · 창 파일 · 구현 잠금 |

마감은 매 변경마다 6 단계 전부 rc=0 일 때만 커밋한다. 2026-09-29 의 모든 커밋이 이 조건을 통과했다.

## 11. 이 문서가 답하지 못하는 것

- H2 가 불확실한 **원인** — 관측 (C9, `C(x)=A(Pᵀx)`) 은 모았으나 인과는 확정하지 않았다. 확정하려면 구조·target 을 바꿔 다시 학습해야 하고 그것은 새 exploratory version 이다.
- 단순 FC 기준선이 100% 인 이유 (target 난이도인지 다른 요인인지).
- PIOP2 에서 무엇이 나올지 — 열지 않았다.
