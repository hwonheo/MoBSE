# I1 — 연구 결과 패키지 (뇌 그래프 prior 검증 프로토콜) · 2026-10-13 초안

> **무엇인가**: I1 본 실행 (잠금 `ac3bad06f6ef`) 의 결과를 한 문서로 묶은 것이다. 주장마다 근거 산출물을 잇는 표 · 결과 표 ·
> 음성 결과 · 잠금 이탈 · 한계 · 비용 · 재현 명령을 담는다. 틀은 v1 의 WI-11 패키지 (`results/redesign_v1/…/reports/wi11_research_package_2026-09-29.md`) 를 따랐다.
> **무엇이 아닌가**: 논문 원고가 아니다. 새로 계산한 값은 없다 — 수치는 모두 `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.5 · §11.8 · §11.10 · §11.11
> 와 `docs/experiments/i1_final_statements_draft_2026-10-12.md` (C1–C5 확정 문장 · D1 학습판 · D5 표) 에서 옮겼다. 그 값들은 기록 당시 h197 분석 산출과 대조됐다.
> **형식 · 위치는 아직 정해지지 않았다** (승인 대장 29 · 30 · 34 행의 "정하지 않은 것"). 이 초안은 추천안 (연구 결과 패키지 · `results/i1/reports/`) 으로 썼다.
> `[계산]` 은 기록된 값으로 이 문서에서 셈한 값, `[추정]` 은 재지 않은 값이다.

## 1. 한 문단 요약

공개 뇌 그래프 모델 셋 (BQN · BNT · Han dual-pathway) 과 MoBSE 를 같은 절차로 돌려, "모델이 ROI 정체 · 해부학적 배치를 쓴다" 는 판정이
대칭성 · null 종류 · 재학습 변동 · 포화에 얼마나 좌우되는지 쟀다. **사전에 세운 주장 C2 (판정이 null 종류에 따라 달라진다) 는 지지되지 않았다** —
두 자료 (AOMIC 포화 · ABIDE 비포화) · 세 모델 모두 n1 · n2 · n3 에서 재학습 포함 CI 가 0 을 넘었고, null 종류가 바꾼 것은 Δ 의 크기뿐이다.
**C3 (단일 학습 CI 가 '유의' 를 자주 낸다) 는 효과가 작은 MoBSE embedding 에서만 관찰됐다.** C4 는 AOMIC 의 천장 때문에 원판 비교가 불가능했다는 점에서
성립하지만, 포화가 null 판정을 바꾸지는 않았다. C1 (등변이면 정렬 대 재배열 null 이 같은 모델) 은 정리로 성립하나 실측 대조는 AOMIC MoBSE mean 하나이고
그 Δ 의 부호가 지표 · 집계에 따라 달라진다. C5 는 네 저장소의 분할 · seed · test 선택 규칙이 모두 달랐고, 공개 모델 1,620 fit 의 최종 실패는 0 이었다.

## 2. 자료 흐름

| 자료 | 역할 | 단위 | 분할 | 출처 |
|---|---|---|---|---|
| ABIDE I PCP (CPAC · filt_noglobal · CC200) | 주 자료 (비포화) | 피험자 **1,009** (`abide.npy` sha `d81bb42063d6`) | 층화 무작위 5-fold, 층 = label × site, 안쪽 val = train 의 층화 10 % | 잠금 §3 · `results/i1/folds_draw0.json` |
| AOMIC PIOP1 | 포화 양성 대조 | v1 main 126 명 × 2 task × 창 4 = 창 1,008 → **run 252** 로 평가 | v1 outer fold 그대로 | 잠금 §3 · `results/i1/aomic_win_folds.json` |
| ABIDE site 민감도 (BQN) | 민감도 | 피험자 1,009 | site 묶음 `GroupKFold(5)` | `results/i1/folds_site.json` |
| AOMIC PIOP2 | — | **쓰지 않음** (결정 27) | — | — |

- ABIDE 표준 파일은 PCP 를 다시 받아 재구성했다 (`scripts/i1/build_abide_npy.py`): 시점 100 미만 26 명 제외 → 1,009 명, Ledoit-Wolf 상관 → arctanh.
- AOMIC 은 창이 표본이고 예측은 run 단위로 평균해 평가한다 (결정 43). label emomatching 0 · workingmemory 1.
- bootstrap 2,000 회 · seed 20261006 · 95 % percentile, 원판과 null 에 같은 피험자 재표집 (잠금 §6).

## 3. 설계 요약 (잠금 `docs/experiments/i1_lock_v1.md`)

| 항목 | 내용 |
|---|---|
| 공개 모델 | BQN (`5dc31b7`, 200 epoch) · BNT (`8a588aa`, 200) · Han (`cde613f`, 100). BrainGB 는 제외 (결정 47, §6). 튜닝 없음 |
| MoBSE | mean (등변, v1 결과 재사용 — 새 학습 없음) · embedding (순서 의존, v3 잠금 `c0c8ed77db50`, 새 fit 196) — AOMIC 만 |
| null (공개 모델, 입력 변환) | n0 모든 피험자 같은 ROI 순열 (대조) · n1 피험자별 순열 · n2 피험자별 spin (반구 안) · n3 피험자별 가중 · 부호 rewire (FC 만, 시계열은 원래 것) |
| null (MoBSE, prior 만 변환) | mean: 순열 prior (v1 null seed 1729–1733) · embedding: `prior_permutation` · `prior_spin` · `prior_rewire` (index 0–4) |
| 반복 | 공개 모델 K=5 · R=3 · fold 5 → 자료당 255 fit (orig · n0 은 k0 만). site: BQN orig + n1, 90 fit |
| test 예측 | 안쪽 val loss 최소 epoch (같으면 앞 epoch) — 세 모델 · FC-MLP 같은 규칙 |
| 지표 · 판정 | AUC 주 · BA 보조. Δ = AUC(orig, r) − AUC(c, k, r). 판정 문장 "재학습 포함 CI 가 0 을 넘는다 / 0 을 포함한다". δ 없음, **다중성 보정 없음 (기술용)** |
| 진단 | D1 등변성 · D2 null · D3 재학습 변동 · D4 기준선 (FC logistic · FC-MLP · S1) · D5 재현 마찰 |
| 실패 규칙 | 다시 돌리지 않고 센다. 붕괴 = test 예측 SD < 1e−6 또는 문턱 0.5 로 class 하나 → 표시하고 뺀 결과를 민감도로 (§8) |

## 4. claim–evidence 표 (C1–C5 확정 문장 — 결정 55 · 56, 원문 그대로)

h197 산출 root = `i1/main/20261005_ac3bad06_a2/` (data root 상대). sha256 은 앞 12 자.

| # | 확정 문장 | 근거 artifact | 기록 |
|---|---|---|---|
| C1 | "C1 은 정리로 성립하고, 실측 대조는 MoBSE mean (AOMIC) 하나뿐이다. 그 대조에서 Δ 의 부호는 지표 · 집계에 따라 달라진다 — v1 방식 (seed 앙상블 · BA 0.5) 으로는 Δ −0.016 또는 0 (CI 0 포함, null seed 다섯), I1 방식 (seed 별 AUC 15 짝) 으로는 +0.0151 [+0.0038, +0.0264]. 따라서 '실측으로 같음을 확인했다' 고 쓰지 않는다. ABIDE 에는 등변 공개 모델이 없어 (D1 학습판 최대 차 0.45–0.997) C1 의 실측 범위는 AOMIC 의 한 모델이다." | `analysis/aomic/mobse_mean.json` `15cb501a8925` · `diag/mobse_mean_20261007/` (결과 `cbe742aa636b`) · `{aomic,abide}/<모델>/orig/k0/r1/f{0,1,2}/d1.json` | §11.8 결정 52 · 최종 문장 §0 · §1 |
| C2 | "C2 는 이번 자료에서 지지되지 않았다 — 판정은 null 종류에 따라 바뀌지 않았다. 공개 모델은 두 자료 · 세 모델 모두 n1 · n2 · n3 에서 재학습 포함 CI 가 0 을 넘고, MoBSE embedding (AOMIC) 은 순열 · spin · rewire 모두 0 을 포함한다. 바뀐 것은 Δ 의 크기다 (n3 이 가장 작다: AOMIC 0.04–0.06 · ABIDE 0.13–0.18, n1 · n2 는 0.20–0.45). n3 은 FC–시계열 불일치가 있다 (잠금 §9)." | `analysis/aomic/{bqn,bnt,han,mobse_embedding}.json` · `analysis/abide/{bqn,bnt,han}.json` | §11.5 · §11.10 · 결정 51-2 · 54-2 |
| C3 | "C3 는 효과가 작은 곳에서만 관찰됐다. 효과가 큰 곳 (공개 모델 n1–n3) 에서는 단일 CI 가 짝 15/15 모두 0 을 벗어나고 재학습 포함 CI 와 결론이 같다. 대조 n0 (짝 3) 에서는 두 자료 · 세 모델 모두 단일 CI 가 0 을 벗어난 짝이 없다. 효과가 작은 MoBSE embedding (AOMIC) 에서는 재학습 포함 CI 가 0 을 포함하는데 단일 CI 가 0 을 벗어난 짝이 0.07 (spin) · 0.20 (순열) · 0.40 (rewire) 이었다 (k0/r42 의 rewire 단일 −0.025 [−0.052, −0.001] 대 재학습 포함 −0.011 [−0.022, +0.001])." | 같은 분석 json 의 D3 항목 | §11.5 · §11.10 D3 표 · 결정 51-3 · 54-2 |
| C4 | "AOMIC 에서는 기준선 (FC logistic 1.000 · FC-MLP 0.9999 · S1 0.9925) 과 공개 모델 원판 (세 모델 1.000) 이 모두 천장이라 원판 성능으로는 모델 · 구조를 가를 수 없었다 — 기준선이 이를 미리 보여 줬다. 그러나 null Δ 의 판정은 포화 (AOMIC) · 비포화 (ABIDE) 자료에서 같았다 — 포화가 null 판정을 바꾸지는 않았다. ABIDE 에서 공개 모델 원판 (0.703–0.752) 은 점추정으로 FC logistic (0.762) 보다 낮거나 비슷하다 (CI 비교 없음 — 우열 주장 없음)." | `analysis/aomic/{fc_logistic,fc_mlp,s1_logistic}.json` · `analysis/abide/` 같은 셋 | 결정 51-1 · 54-3 |
| C5 | "세 공개 모델 (BQN · BNT · Han) 은 저장소 파일을 고치지 않고 분할 · 평가 · seed 함수를 메모리에서 바꿔 끼워 돌렸다 (모델당 4–7 항목, BNT · Han 은 torch ≥ 2.0 호환 수정 포함). 네 저장소 모두 공통 5-fold 를 쓰지 않았고, test 값을 고르는 규칙이 서로 달랐으며 (val loss 최소 · val AUC 최대 · 고르지 않음 · 마지막 epoch), 셋 (BQN · BNT · BrainGB) 은 재현 가능한 seed 를 바꿀 수 없었다. BrainGB 는 저장소 설정에서 학습되지 않아 제외했다 (결정 47). 본 실행 공개 모델 1,620 fit 의 최종 프로세스 실패는 0 이나, ABIDE Han 149 fit 은 실행기 동시성이 만든 GPU OOM 으로 k=1 에서 다시 돌렸고 (실패로 세지 않음, 결정 50), 붕괴 fit 은 222 (BQN 141 · BNT 81 · Han 0) 이다." | fit 마다 `summary.json` `patches` · `status.txt` · `fails_*.json` · `diag/collapse_20261012/` (결과 `628d470f5b02`) | 최종 문장 §3 (D5 표) · 결정 56 |
| 붕괴 | "ABIDE 판정은 전체 단위로 한다 (잠금 §8). 붕괴 fit BQN 74/255 · BNT 41/255 · site 33/90 · Han 0. … BQN n3 의 상수 붕괴 5 fit 은 null AUC 를 낮춘다 (Δ 를 키우는 방향) — 뺀 민감도는 +0.134 [+0.099, +0.167] 로 0 을 넘는다. site 는 뺀 민감도를 계산할 수 없다 — 이 한계와 함께 읽는다." (전문은 최종 문장 문서 §1 "붕괴 표기") | `diag/collapse_20261012/diag_collapse.json` | §11.11 · 결정 55-1 |

## 5. 결과

### 5.1 기준선과 원판 (D4, OOF AUC)

| 자료 | FC logistic | FC-MLP | S1 | BQN 원판 | BNT 원판 | Han 원판 |
|---|---:|---:|---:|---:|---:|---:|
| AOMIC (포화) | 1.0000 | 0.9999 | 0.9925 | 1.0000 | 1.0000 | 1.0000 |
| ABIDE (비포화) | 0.7624 | 0.7337 | 0.6022 | 0.7025 | 0.7508 | 0.7521 |

- ABIDE BQN site 분할 원판 0.6634. MoBSE (AOMIC): mean 0.9561 · embedding 0.9324.
- 원판 수치는 진단의 재료다 — 모델 우열이나 ASD 진단 성능을 주장하지 않는다.

### 5.2 Δ = AUC(orig) − AUC(null), 재학습 포함 95 % CI

| 모델 | 자료 | n0 (대조) | n1 | n2 | n3 |
|---|---|---|---|---|---|
| BQN | AOMIC | +0.0000 [−0.0001, +0.0003] | +0.4034 [+0.3614, +0.4463] | +0.3721 [+0.3347, +0.4120] | +0.0495 [+0.0271, +0.0745] |
| | ABIDE | −0.0087 [−0.0316, +0.0133] | +0.2045 [+0.1711, +0.2390] | +0.2066 [+0.1746, +0.2383] | +0.1418 [+0.1133, +0.1727] |
| BNT | AOMIC | +0.0000 [−0.0000, +0.0000] | +0.4531 [+0.4258, +0.4793] | +0.3820 [+0.3439, +0.4207] | +0.0627 [+0.0412, +0.0859] |
| | ABIDE | −0.0053 [−0.0221, +0.0119] | +0.2366 [+0.2052, +0.2696] | +0.2424 [+0.2098, +0.2738] | +0.1835 [+0.1532, +0.2142] |
| Han | AOMIC | +0.0000 [−0.0000, +0.0000] | +0.2755 [+0.2284, +0.3253] | +0.2312 [+0.1887, +0.2765] | +0.0365 [+0.0177, +0.0574] |
| | ABIDE | −0.0003 [−0.0047, +0.0036] | +0.2146 [+0.1822, +0.2486] | +0.2123 [+0.1794, +0.2460] | +0.1255 [+0.0986, +0.1539] |
| BQN site | ABIDE | — | +0.1932 [+0.1565, +0.2306] | — | — |

MoBSE (AOMIC, prior 만 바꾼 null):

| 구조 | 순열 prior | spin prior | rewire prior |
|---|---|---|---|
| mean (등변) | +0.0151 [+0.0038, +0.0264] | — (v1 에 없음) | — |
| embedding | −0.0058 [−0.0186, +0.0052] | +0.0027 [−0.0077, +0.0138] | −0.0106 [−0.0222, +0.0010] |

- 단일 학습 Δ · null AUC · 원판 seed 별 AUC 는 handoff §11.5 (AOMIC) · §11.10 (ABIDE) 표에 있다.
- MoBSE mean 의 같은 예측을 v1 방식 (seed 3 개 평균 · BA 0.5) 으로 보면 Δ −0.016 또는 0 (null 5 판, CI 모두 0 포함) — 부호 차이는 지표 (AUC 대 BA) 와
  seed 앙상블 두 갈래에서 온다 (§11.8 진단, 결정 52).

### 5.3 재학습 변동 (D3) — 단일 학습 CI 가 0 을 벗어나는 비율

| 대상 | n0 | n1 · n2 · n3 | 재학습 포함 CI 의 판정과 |
|---|---|---|---|
| 공개 모델 셋 · 두 자료 | 0/3 짝 (모두) | 15/15 짝 (모두) | 같음 |
| BQN site (ABIDE, n1) | — | 15/15 | 같음 |
| MoBSE mean (순열) | — | 0.27 | 같음 (둘 다 0 을 넘음) [§11.5 표에서 읽음] |
| MoBSE embedding | — | 순열 0.20 · spin 0.07 · rewire 0.40 | **다름** — 재학습 포함 CI 는 셋 다 0 을 포함 |

- Δ 의 seed 간 SD 와 단일 CI 반폭 중앙값은 §11.5 · §11.10 D3 표. 예: ABIDE 공개 모델 n1–n3 의 seed 간 SD 0.0078–0.0228, 단일 CI 반폭 중앙 0.0307–0.0510.

### 5.4 학습 뒤 등변성 (D1) — ROI 순열 20 개에 대한 class 1 확률의 최대 차

| 모델 | AOMIC f0 · f1 · f2 | ABIDE f0 · f1 · f2 | 학습 전 (계획서 §3) |
|---|---|---|---|
| BQN | 0.983 · 0.994 · 0.997 | 0.667 · 0.975 · 0.453 | 4.9e−4 (순서 의존) |
| BNT | 0.626 · 0.689 · 0.695 | 0.603 · 0.514 · 0.744 | 1.3e−3 (순서 의존) |
| Han | 0.756 · 0.788 · 0.806 | 0.729 · 0.863 · 0.693 | 재지 않음 (구조상 순서 의존 [코드]) |

- 같은 입력 두 번의 차는 18 개 모두 0. 세 공개 모델은 학습 뒤에도 순서 의존 (0.45–0.997). ABIDE 에는 등변 대조가 없다 (BrainGB 제외).

## 6. 실패 · 음성 결과 (숨기지 않는다)

1. **C2 는 지지되지 않았다** — 사전에 세운 주장 중 가장 중심이던 것. null 종류는 판정을 바꾸지 않고 크기만 바꿨다.
2. **C3 는 좁게만 관찰됐다** — 효과가 큰 공개 모델에서는 단일 CI 와 재학습 포함 CI 가 늘 같은 결론이었다.
3. **C1 의 실측은 한 모델 · 한 자료** 이고 부호가 지표에 따라 바뀐다 — "같음을 실측으로 확인" 이라고 쓰지 않는다.
4. **BrainGB (유일한 등변 공개 모델) 는 학습되지 않아 제외했다** (결정 47) — 원판 5 fold test AUC 0.461–0.529, train AUC 도 0.55 미만,
   degree z-score 로도 같음 (0.448–0.527). 원인 후보 (1 차원 strength + mean pooling · 저장소 학습 루프) 를 가르는 측정은 하지 않았다. 잠금 전 확인이다.
5. **붕괴 fit 222 / 1,620** (AOMIC BQN 34 · BNT 40, ABIDE BQN 74 · BNT 41, site 33, Han 0). ABIDE 는 원판 단위에도 붕괴가 있고
   (BQN r1/f3 · site 3 fit — 200 epoch 상수 출력), site 는 붕괴를 뺀 민감도를 계산할 수 없다 (붕괴 없는 단위가 orig r3 하나).
6. **AOMIC 은 원판 비교에 쓸 수 없었다** — 기준선 · 원판 모두 천장. 이 자료는 포화 양성 대조로만 작동했다.
7. 계산된 곳에서는 붕괴 단위를 빼도 판정 문장이 바뀌지 않는다. 단 ABIDE BQN n1 · n2 는 뺀 뒤 1 짝뿐이라 재학습 포함 CI 가 단일 CI 와 같다.

## 7. 잠금 이탈과 운영 사건

| # | 무엇 | 잠금과의 관계 | 결과에 미친 영향 | 기록 |
|---|---|---|---|---|
| 1 | **결정 50** — ABIDE Han k=2 GPU OOM 149 fit (재시도까지 실패 79 · 한 번 실패 70) 을 k=1 로 다시 돌리고 **실패로 세지 않음**. 원문 "GPU OOM 이므로 실패로 치지 않음" | **이탈**: 잠금 §8 은 "GPU 메모리 부족도 같은 규칙이다 (다시 돌리지 않고 센다)". 잠긴 집계 규칙을 결과 (ABIDE 분석) **전에** 바꿈 | Han 255 = k=2 22 + k=1 233. 이 처리가 없었으면 완전한 단위가 32/51 (두 번 실패만 뺄 때) 또는 17/51 (전부 뺄 때) — n0 · n1 이 사라짐 | §11.6 · §11.7 |
| 2 | 결정 50-3 · 50-4 — OOM 처리를 일반 규칙으로 만들지 않음 · GPU fit 재시도는 GPU 정리 뒤 (원칙) | 잠긴 구동기는 고치지 않고 `run_jobs` 만 바꿔 끼운 래퍼 (run 폴더, 버전 관리 밖) | 교체 뒤 재시도 0 | §11.7 |
| 3 | a1 중지 — 구동 스크립트의 `PYTHONPATH=.` 로 잠금 검증의 `pip freeze` 에 `mobse==0.1.0` 이 끼어 environment 불일치, 공개 모델 단계 rc=3 | 잠금이 막은 사례 (이탈 아님) | 없음 (a1 결과 미사용, 보존) | §11.3 |
| 4 | 잠금 생성 전 `.pyc` 0 확인 누락 (h197 사본 105 개) | 절차 누락 | 없음 (해시는 `.py` 만, 재검증 rc=0) | §11.3 |
| 5 | 결정 49 — ABIDE 를 n3 뒤 AOMIC 과 병행 (동시 GPU fit 2 + 2) | 운영 방식만, 잠금 · 설계 불변 | 없음 | §11.3 |
| 6 | "ok" 를 "80 개 재실행 승인" 으로 잘못 읽음 → 되물어 정정, 사슬 중지 1 회 더 | 운영자 해석 오류 | 없음 (k=1 로 끝난 fit 0 개에서 중지) | §11.6 |

- 잠금 전에 본 결과 (smoke 의 원판 fold 0 AUC · MoBSE mean 의 I1 방식 계산 · BrainGB 10 fit) 는 잠금 문서 §9 에 적혀 있다. 그 값으로 설계를 바꾸지 않았다 (BrainGB 제외는 학습 불가 판정).
- v1 에서 넘어온 이탈 (결정 27 — PIOP2 외부 검증을 하지 않음) 은 I1 도 그대로 따른다.

## 8. 한계

1. **다중성 보정 없음** — 모델 3 × 조건 4 × 자료 2 의 CI 는 기술용이다.
2. **ABIDE 에 등변 공개 모델이 없다** — C1 의 실측 범위는 AOMIC MoBSE mean 하나.
3. **n3 은 FC 만 바꾸고 시계열은 원래 것** — 시계열을 받는 세 모델에서 FC 와 시계열이 어긋난다 (잠금 §9).
4. **CC200 은 반구를 나눠 만든 atlas 가 아니다** — 반구 걸친 parcel 22 개, n2 의 반구 판정이 그 parcel 에서 임의적.
5. **AOMIC 은 30 시점 창** — 공개 모델의 원래 쓰임 (긴 시계열) 과 다르고, 포화되어 원판 비교가 불가.
6. **MoBSE mean 에는 spin · rewire null 이 없다** (v1 에 없음, 결정 44).
7. **붕괴 fit 이 많다** (ABIDE BQN 74/255 · site 33/90) — 판정은 전체 단위로 하고 진단을 병기했다 (결정 55-1). site 의 뺀 민감도는 계산 불가.
8. **튜닝하지 않았다** — 저장소 기본 설정 · 저자 명령. 공개 모델의 원판 성능은 저자 보고값과 다를 수 있다 (대조하지 않음).
9. **fit 당 시간은 공유 GPU (sglang) · 동시 실행 아래 값** — 효율 비교에 쓰지 않는다.

## 9. 비용 (h197, RTX 3090 Ti 1 장 · 12 코어, 공유 GPU)

| 항목 | 값 | 출처 |
|---|---|---|
| fit 당 (전체 epoch smoke, ABIDE fold 0 · seed 1, 단독) | BQN 152 s · BNT 194 s · Han 517 s (BrainGB 728 s) | 잠금 §5.1 |
| ABIDE Han fit 당 (k=1, 본 실행) | 508–529 s | §11.6 · §11.10 |
| null 입력 n3 | AOMIC 5 건 12,229 s · ABIDE 5 건 44,988 s (k 당 2 h 28 m – 2 h 36 m) | `<R>/driver_{aomic,abide}.log` (10-13 확인) |
| 공개 모델 fit 단계 (예) | AOMIC BQN 255 30,757 s (k=2) · ABIDE BQN 255 59,588 s · ABIDE Han OOM 재실행 149 78,891 s · site 90 10,856 s | `driver_*.log` · §11.10 (10-13 확인) |
| 전체 벽시계 | `START` 10-05 03:15 → `ALL_DONE` 10-08 22:52 KST ≈ **91.6 h** [계산] | `<R>/status.txt` (10-13 확인) |
| 산출 크기 | a2 12,456 파일 · 15,558 MB (a1 중지판 199 파일 · 3 MB 별도) | Data Asset (10-12 실측) |

## 10. 재현 방법 (실제로 돈 진입점)

h197, 저장소 사본 루트, venv-i1. `<D>` = data root, `<R>` = `<D>/i1/main/20261005_ac3bad06_a2`.

```bash
# 잠금 검증 (구동기도 맨 앞에서 같은 검증을 하고, 실패하면 아무것도 시작하지 않는다)
python scripts/i1/build_lock.py --verify --repo-root . --data-root <D> --doc docs/experiments/i1_lock_v1.md --out results/i1/locks/i1_lock.json
# 단계 (dataset = abide | aomic; site 는 abide 만). PYTHONPATH 를 내보내지 말 것 (a1 중지 원인) — MoBSE 팔 명령에만 붙인다
python scripts/i1/run_main.py --data-root <D> --out <R> --dataset <dataset> --phase {nulls|fits|site|baselines|analyze} \
    --lock results/i1/locks/i1_lock.json --doc docs/experiments/i1_lock_v1.md [--models bqn bnt han] [--k 2]
# MoBSE 팔 (AOMIC 만, venv-mobse-v2 · v3 잠금 환경)
PYTHONPATH=. python scripts/i1/mobse_arm.py {collect-mean|plan-embedding|run-embedding|collect-embedding} …
# 분석 (구동기 analyze 단계가 모델마다 부른다)
python scripts/i1/analyze.py --root <dataset root> --model <model> --out <json> [--n-boot 2000]
```

- 실제 실행은 run 폴더의 사슬 스크립트 (`orchestrate.sh` · `switch.sh` · `chain_*.sh` · `gpu_clean_retry.py` · `run_*_gc.py`) 가 위 진입점을 불렀다 —
  저장소 밖 (scripts/i1 에 두면 잠금이 바뀜) 이며 h197 run 폴더에 보존돼 있다.
- 공개 모델 저장소는 commit 고정 clone 을 쓰고 파일을 고치지 않는다 (잠금이 clone 의 `git status` 를 확인). 바꿔 끼운 함수는 fit 마다 `summary.json` `patches`.

## 11. 잠금과 검증

| 항목 | 값 |
|---|---|
| I1 잠금 | `results/i1/locks/i1_lock.json` — lock_hash `ac3bad06f6ef` · code_hash `a5738888b83c` · data_hash `b50b69aa8c4c` · v1 묶음 `08385bf94c3f` |
| 잠금 문서 | `docs/experiments/i1_lock_v1.md` (sha `e418cbf78562`) |
| 함께 쓴 잠금 | v1 측정 `9b7b11cf8576` (MoBSE mean) · v3 `c0c8ed77db50` (MoBSE embedding) |
| 분석 산출 (sha256 앞 12) | AOMIC: `bqn` `28b175dce707` · `bnt` `374944e55ec0` · `han` `89a07cf9c85e` · `mobse_mean` `15cb501a8925` · `mobse_embedding` `6cef00596fea` · `fc_logistic` `715a440d66ad` · `fc_mlp` `290cfc3c7923` · `s1_logistic` `de4a051690d9` |
| | ABIDE: `bqn` `993c1e990e87` · `bnt` `79d130c26bfd` · `han` `ecd9ee51b747` · `fc_logistic` `af82d07fe32e` · `fc_mlp` `883d12adaea3` · `s1_logistic` `f06187567f8c` · site `bqn` `4fa4f5ca95f8` |
| 진단 (새 학습 없음) | `diag/mobse_mean_20261007/` (스크립트 `bda494c7515e` → 결과 `cbe742aa636b`) · `diag/collapse_20261012/` (`b9e84ab9c810` → `628d470f5b02`) |
| 실행 상태 | 전 단계 rc=0 · `fails_*.json` 전부 빈 목록 · ABIDE `logs/` 1,702 개에 Traceback · OOM 0 (k=2 OOM 로그는 `han_oom_k2_20261007/` 에 따로) · `incomplete_units` 전부 0 |

- **이 문서 자체의 인용 대조는 아직 하지 않았다** — v1 의 `28_verify_wi11_citations.py` 처럼 h197 분석 산출과 이 문서의 수치를 기계적으로 대조하는 단계가 남아 있다.

## 12. 이 문서가 답하지 못하는 것 · 정하지 않은 것

- 보고서의 최종 형식 · 위치 (이 초안은 추천안).
- 붕괴 fit 이 왜 생겼는가 (원인 미측정 — 모양만 진단했다), BrainGB 가 왜 학습되지 않았는가 (두 원인 후보를 가르지 않았다).
- 공개 모델의 원판 성능이 저자 보고값과 같은가 (대조하지 않았다).
- 결과를 본 뒤의 설계 변경 (잠금 §10 — 새 잠금판 필요), PIOP2 개방, I3 (TR 단위 상태 routing) 착수.
