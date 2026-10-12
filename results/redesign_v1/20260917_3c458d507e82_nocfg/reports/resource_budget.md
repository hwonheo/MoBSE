# 자원 예산 — WI-03 산출물 (2026-09-18)

지침서 WI-03 의 출력 중 하나다. 계획서 §7 은 "표는 실행 횟수 계획이고 소요시간
보장이 아니다. **pilot에서 peak memory·시간을 측정해 자원 계획을 만든다**"고
정한다. pilot fit 은 아직 구현 전이므로 **이 문서는 pilot 측정을 대신하지 않는다.**
규모를 잡기 위한 중간 문서이고, 무엇이 측정이고 무엇이 추정인지 줄마다 구분한다.

표기: **[측정]** 이 기계에서 실제로 잰 값. **[추정]** 측정에서 계산한 값.
**[미측정]** 아직 재지 않았고 이 문서로 확정하지 않는 값.

## 1. 측정 환경

**[측정]**

```
host        bmcws-h197
GPU         NVIDIA GeForce RTX 3090 Ti, 24,564 MiB, driver 570.181
CPU/RAM     12 core / 31 GiB
torch       2.10.0+cu128, CUDA 사용 가능
precision   float32, AMP 미사용
저장소      /mnt/data (md0, RAID1 [2/1] [U_]), 5.5T 중 2.5T 사용 (47%)
```

계획서 §9 의 "동일 장비/batch/precision" 요구에 따라 모든 측정은 이 한 기계,
batch 32, float32 에서 잰 값이다.

## 2. 이미 지출된 것

| 항목 | 값 | 구분 |
|---|---:|---|
| Wave 2 원본 BOLD | 2,590 파일 / **209.7 GiB** | [측정] fetch 계획 로그 |
| 창 파생물 (.npy) | 4,728 파일 / **54.7 MiB** | [측정] 파일당 12,128 B × ok run 1,182 × 4 |
| atlas | 76 KiB | [측정] |
| manifest·코호트·분할 | < 3 MiB | [측정] |

**파생물은 원본의 0.03% 다.** 디스크를 먹는 것은 오로지 원본 BOLD 다.

## 3. 추출 실측 (WI-02, 완료분)

**[측정]** 6개 조합의 실제 wall-clock:

| dataset | task | run | 소요 | run 당 |
|---|---|---:|---:|---:|
| ds002785 | emomatching | 216 | 353 s | 1.63 s |
| ds002785 | workingmemory | 216 | 500 s | 2.31 s |
| ds002785 | restingstate | 216 | 1,097 s | 5.08 s |
| ds002790 | emomatching | 226 | 322 s | 1.42 s |
| ds002790 | workingmemory | 226 | 395 s | 1.75 s |
| ds002790 | restingstate | 226 | 543 s | 2.40 s |

PIOP1 rest 가 유독 느린 것은 TR 0.75 초라 run 당 원본 frame 이 480개로 가장
많고 목표 격자로 보간까지 하기 때문이다. 전량 1회 재추출 = **약 53분**.

> `derivatives_v2/extract_ds002785_workingmemory.log` 는 1차 실행분이고
> (ok 175 / error 3), manifest 는 E14 수정 후 재실행분이다 (ok 176 / excluded 31).
> 소요시간은 run 당 비용이라 재실행에도 그대로 쓴다. 로그와 manifest 의 계수가
> 다른 이유를 여기 적어 둔다.

## 4. Fold 내부 변환 실측

**[측정]** outer train rest 창 404개(= 101 subject × 4) 기준, 반복 25회 중앙값:

| 단계 | 시간 |
|---|---:|
| FC(Ledoit–Wolf) → Fisher-z | 0.27 s |
| StandardScaler + PCA-10 | 0.54 s |
| K-means(K=3) → centroid → sparsify → normalize | 0.05 s |
| **한 fit 당 합계** | **0.86 s** |

bank 는 (outer, inner) 조합마다 한 번 적합한다. main 15개 + outer 최종 5개 +
external 관련 소수 → **[추정] 전체 변환 비용은 30초 미만**이다. 무시해도 된다.

## 5. 모델 실측

**[측정]** parameter 수와 bank 동결 여부:

| cell | routing | trainable params | bank 가 buffer 인가 |
|---|---|---:|---|
| A | dynamic | 6,469 | 예 |
| B | fixed | 6,021 | 예 |
| C | dynamic | 6,469 | 예 |
| D | fixed | 6,021 | 예 |

A/C 와 B/D 의 448 차이는 dynamic gate(Linear32→GELU→Linear3)와 fixed gate
(logits 3개)의 차이다. **bank 는 어느 cell 에서도 parameter 가 아니다.**

**[측정]** 1 epoch 학습 시간, 반복 25회:

| 규모 | 창 수 | epoch 중앙값 범위 | 최솟–최댓값 |
|---|---:|---|---|
| inner train (67 subject) | 536 | 0.085 – 0.144 s | 0.049 – 0.174 s |
| outer train (101 subject) | 808 | 0.155 – 0.245 s | 0.075 – 0.267 s |

**cell 사이의 차이는 이 측정으로 해소되지 않는다.** 네 cell 의 최솟–최댓값
구간이 서로 크게 겹친다. outer 가 inner 보다 일관되게 느린 것(창 1.5배)만
신호로 읽고, cell 간 비교는 하지 않는다.

측정에서 읽히는 것은 **이 규모에서 계산은 커널 실행 오버헤드에 묶여 있다**는
점이다. 창 808개 / batch 32 = 26 batch 이고 모델이 6천 parameter 다. GPU 를
채우지 못한다.

**[측정]** peak GPU 메모리는 네 cell 모두 **92.8–96.5 MiB**. 24 GiB 카드에서
동시에 수십 개를 돌려도 메모리가 제약이 아니다.

**[측정]** 전체 학습창 1회 추론 0.011–0.027 s.

FLOPs 는 **NA** 다 — 계획서 §9 가 "지원되지 않는 FLOPs 는 NA" 라고 정했고,
`thop` 이 dense graph layer 의 einsum 을 세지 못한다.

## 6. 학습 예산 [추정]

계획서 §7 의 fit 표는 코드 `train.fit_budget()` 과 일치한다 (`test_train.py`
`test_fit_budget_matches_protocol_table`).

epoch 비용은 위 측정의 **상단**을 쓴다 — inner 0.15 s, outer 0.25 s.
모든 fit 이 max 50 epoch 을 다 쓴다고 본다(early stopping 을 무시한 상한).

| 비용 묶음 | fits | epoch 당 | 상한 시간 |
|---|---:|---:|---:|
| A–D main inner | 480 | 0.15 s | 1.00 h |
| A–D main outer | 60 | 0.25 s | 0.21 h |
| 추가 null 민감도 | 120 | 0.25 s | 0.42 h |
| External 최종 선택 | 96 | 0.15 s | 0.20 h |
| External 최종 fit | 12 | 0.25 s | 0.04 h |
| **합계** | **768** | | **1.87 h** |

inner 가 early stopping 으로 평균 절반에서 멈추면 **1.27 h**.

**[추정]** 이 숫자는 순수 학습 시간이다. 창 적재·checkpoint 저장·평가·로깅을
넉넉히 3–5배로 잡아도 **하루 안에 끝난다.** baseline·pilot·mechanism·그 밖의
민감도는 계획서 §7 이 "별도" 라고 했으므로 이 표에 없다.

**[추정]** checkpoint: parameter 6,469 + bank buffer 30,000 을 float32 로
약 142 KiB. primary 60 + null 120 + external 12 = 192개 → **약 27 MiB**.

**[추정]** 예측 행: window 12,096 + run 1,008 (primary), external window 1,512 +
run 1,512. JSONL 로 수 MiB.

## 7. 그래서 무엇이 제약인가

계산도 메모리도 저장공간도 제약이 아니다. **제약은 자료가 놓인 디스크다.**

```
md0 : active raid1 sda1[0]  [2/1] [U_]     ← 이중화 없음
sda : Current_Pending_Sector 1,942 / Offline_Uncorrectable 1,932
      Power_On_Hours 60,758 (6.9년), Load_Cycle_Count 690,921 (정규화 VALUE 001)
```

209.7 GiB 의 원본이 **이중화 없는 디스크 한 장** 위에 있고, 그 디스크는
1,932 섹터를 이미 읽지 못한다. 학습 예산 1.9시간은 이 사실 앞에서 부차적이다.

파생물이 54.7 MiB 밖에 안 된다는 점은 유리하게 쓸 수 있다 — **원본을 다시
받지 않고도 파생물만 옮기면 WI-04 이후 전 단계를 다른 기계에서 돌릴 수 있다.**
원본이 필요한 것은 WI-02 재추출뿐이다.

## 8. pilot 실측 (2026-09-18 갱신)

`fit` CLI 구현 후 pilot 31명 안에서 실제 fit 을 돌렸다 (계획서 §4-2 의 기술
검증용 분할, main pool 은 건드리지 않았다). **[측정]**

| 항목 | 값 |
|---|---|
| 학습 창 / 평가 창 | 104 / 56 (inner train 13명, val 7명) |
| 순수 학습 | 1.43 – 1.63 s (26 epoch) → **0.055 – 0.063 s/epoch** |
| **end-to-end wall clock** | **12.66 s** (torch import·자료 적재·해시 대조·FC·PCA·bank 포함) |
| peak GPU | 94,005,248 – 94,022,656 B = **89.6 MiB** |
| peak RSS (host) | **1.65 GiB** |
| early stopping | epoch 26 에서 멈춤, best epoch 21 |

**학습 밖 비용이 학습의 7–8배다.** 6절이 "3–5배로 잡아도"라고 적은 여유는
이 규모에서는 부족하다. 다만 이 비율은 학습이 1.4초일 때의 값이고, main 규모
에서는 학습 시간이 늘어 비율이 내려간다 — 고정비(약 11초)가 fit 당 한 번이므로
768 fit × 11 s ≈ **2.3 h 의 고정비**로 보는 편이 낫다. 6절의 학습 1.87 h 와
합쳐 **약 4.2 h** 가 현재 최선의 추정이다.

5절의 합성 측정과 비교하면 epoch 당 시간이 0.055–0.063 s 로, 합성 inner
(0.085–0.144 s, 536창) 보다 짧다. 창이 104개로 더 적으니 방향이 맞는다.

## 8.1 여기서 드러난 더 큰 문제 [측정]

pilot fit 의 validation balanced accuracy 가 **정확히 0.5** 였다. 원인을 추적한
결과는 보고서 부록 W 에 있고, 요지는 자원 계획에도 직접 영향을 준다.

> 계획서 §7 의 **max 50 epoch + patience 5** 예산은 이 모형이 초기 평탄면을
> 벗어나기 전에 학습을 끝낸다. batch 32 에서 평탄면 탈출에 **800 update 이상**이
> 필요한데, pilot inner 규모(104창, 4 batch/epoch)의 50 epoch 은 **200 update** 다.

main 규모에서는 inner train 536창 → 17 batch/epoch → 50 epoch = **850 update**,
outer train 808창 → 26 batch → **1,300 update** 다. 탈출 구간에 겨우 닿거나
살짝 넘는다. **충분한지는 측정되지 않았다** — 부록 W.5 가 그 측정을 명시한다.

자원 관점에서 이것이 뜻하는 바: **epoch 상한을 올려야 한다면 6절의 시간이 그
배수만큼 늘어난다.** 상한을 200 epoch 으로 올리면 학습 1.87 h → 7.5 h 이고,
고정비 2.3 h 를 더해 약 10 h 다. 여전히 하루 안이다. **계산은 이 문제의
제약이 아니다.**

## 8.2 아직 재지 않은 것 [미측정]

- **main 규모에서의 평탄면 탈출 여부.** 위 8.1. 부록 W.5 참조.
- **checkpoint I/O 를 분리한 비용.** 고정비 11초를 torch import·적재·해시·FC·
  PCA·bank 로 쪼개지 않았다.
- **다중 fit 동시 실행 시의 처리량.** GPU 메모리는 89.6 MiB 뿐이라 수십 개를
  동시에 올릴 수 있지만, 고정비가 CPU·I/O 쪽이라 병렬 이득의 상한이 다르다.
  재지 않았다.
- **해시 대조를 끄면 얼마나 빨라지는지.** `--skip-hash-verify` 가 있지만
  기본값은 대조이며, 그 비용을 따로 재지 않았다.

## 근거

| 값 | 재현 명령 |
|---|---|
| 5·6절 측정 | `python scripts/h197/21_resource_benchmark.py --out <path> --repeats 25` |
| 3절 추출 시간 | `derivatives_v2*/extract_*.log` 의 마지막 진행 줄 |
| 2절 파생물 크기 | ok run 수 × 4 창 × 12,128 B (파일 크기는 `stat`) |
| fit 수 | `mobse.v2.train.fit_budget()` — 계획서 §7 표와 시험으로 대조 |

## 9. pilot 실측 — 결정 15 값 (최소 5,000 update / 상한 400 epoch) 기준 (2026-09-25 갱신)

1–8절은 max 50 epoch 시절 값이다. 결정 15 (계획서 P8-b) 로 최소 update 5,000 · 상한 400 epoch 이
되어 예산을 다시 잡는다. 이 절의 fit 은 **pilot 기술 분할** (`derivatives_v2/pilot_tech/splits/folds.json`,
pilot 31명, outer 0 · inner 0) 만 쓰고 main pool 을 건드리지 않는다. val 성능은 저장하지 않고 해석하지 않는다.

**[측정]** h197 bmcws · RTX 3090 Ti · torch 2.10.0+cu128 · float32 · batch 32 · config 0 · seed 42 ·
v3 창 · 결정적 실행 · 칸마다 1회 순차 실행 (2026-09-25 09:16:39Z–09:23:50Z). 코드는 시작 시점
HEAD 사본. pilot 규모 (학습 104창 = 4 update/epoch) 의 최소 epoch 1,250 은 상한 400 을
넘으므로 **측정 프로세스 안에서만** `fitting.MAX_EPOCHS` 를 덮어 정확히 1,250 epoch (5,000 update) 을 돌렸다.
평가 창 56. 해시 대조 켬 (`verify=True`).

| 칸 | s/epoch | 학습 (s) | fold 변환 (s) | 창 부호화 (s) | end-to-end (s) | peak GPU (MiB) | peak RSS (GiB) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 0.0600 | 75.0 | 7.05 | 2.47 | 86.9 | 136.3 | 1.49 |
| B | 0.0542 | 67.7 | 4.95 | 10.71 | 85.8 | 136.3 | 1.49 |
| C | 0.0339 | 42.4 | 3.06 | 4.37 | 52.2 | 136.4 | 1.49 |
| D | 0.0539 | 67.4 | 2.94 | 3.44 | 76.2 | 136.4 | 1.49 |
| NG | 0.0343 | 42.9 | 4.61 | 6.01 | 55.9 | 133.4 | 1.48 |
| SG | 0.0481 | 60.1 | 3.16 | 3.00 | 68.7 | 133.5 | 1.49 |

- import 1.22–1.24 s, 참조 적재 0.09 s. end-to-end − 학습 = 고정비 **8.6–18.1 s**.
- A 와 C 는 같은 구조 (parameter 6,469) 인데 s/epoch 가 0.060 대 0.034 다 — **칸마다 1회라 칸 사이 차이는
  잡음과 구별되지 않는다.** 칸 비교에 쓰지 않는다. 창 부호화 2.5–10.7 s 의 폭도 I/O 캐시 상태로 보이나 재지 않았다.
- peak GPU 는 136 MiB 이하 — 24 GiB 카드에서 메모리는 제약이 아니다 (GPU 0 에 다른 사용자 sglang 약 19 GB 상주).

**[추정]** 5,000/400 기준 학습 예산 (순차 1 프로세스). 식은 `.backup/slot_1815b/budget.py`.

- 하한: epoch 수 = 최소 epoch (main inner 295, outer E 295, 외부 inner 239, 외부 final E 239 — 부록 AR·결정 17 참고 계산),
  epoch 시간 = rev57 합성 main 규모 A 값 (inner 536창 0.149 s, outer 808창 0.226 s; 672·1,008창은 선형 보간·외삽).
- 상한: epoch 수 = 400, epoch 시간 = update/epoch × (pilot 실측 최대 0.0600 s ÷ 4 update) — pilot epoch 의
  평가·고정분까지 update 에 얹으므로 과대 쪽이다.

| 비용 묶음 | fits | 학습 창 | update/epoch | 하한 | 상한 |
|---|---:|---:|---:|---:|---:|
| A–D main inner | 480 | 536 | 17 | 5.86 h | 13.60 h |
| A–D main outer | 60 | 808 | 26 | 1.11 h | 2.60 h |
| 추가 null 민감도 | 120 | 808 | 26 | 2.22 h | 5.20 h |
| External 최종 선택 | 96 | 672 | 21 | 1.20 h | 3.36 h |
| External 최종 fit | 12 | 1,008 | 32 | 0.23 h | 0.64 h |
| 구조 비교 inner (NG·SG) | 240 | 536 | 17 | 2.93 h | 6.80 h |
| 구조 비교 outer (NG·SG) | 30 | 808 | 26 | 0.56 h | 1.30 h |
| **학습 합계** | **1,038** | | | **14.1 h** | **33.5 h** |

고정비 1,038 fit × ≤18.1 s = **5.2 h** 를 더하면 순차 **약 14–39 h**. 부록 AH.3 의 "약 15 h" (외삽) 는 이 범위의 하단이다.
메모리는 fit 당 136 MiB 라 동시 실행이 가능하지만 **동시 실행 처리량은 재지 않았다** (8.2절과 같음).

**[미측정]** S 후보 fit 시간 (S1·S3 logistic, S2·S4 MLP — `fit-s` 에 timing 기록 없음), main 규모 실자료 epoch 시간
(main pool 소비 — 승인 전 금지), 동시 실행 처리량, 칸 사이 시간 차이 (반복 1회).

### 9.1 반복 측정·동시 실행 (2026-09-25 22:15 슬롯, 부록 BI)

**[측정]** 같은 조건으로 칸마다 2회 더 (순서 교대), HEAD 사본. 칸당 3회 s/epoch:
A 0.046–0.060 · B 0.054 · C 0.034–0.061 · D 0.020–0.054 · NG 0.034 · SG 0.047–0.048.
A·C·D 는 같은 인자 반복에서 최대 2.7 배 흔들린다 — 위 표의 A·C 차이는 칸 차이가 아니라 반복 사이 변동이다.
고정비 5.5–14.8 s, peak GPU ≤136.4 MiB (위 표와 같은 수준).

**[측정]** 동시 실행 (칸 A, pilot 규모): 순차 41.7 fits/h (end-to-end 중앙값 86.3 s) → k=2 54.6 fits/h (1.31 배),
k=4 93.1 fits/h (2.23 배). 학습 구간 epoch 시간은 늘지 않았고 (0.037–0.061 s), fold 변환 + 창 부호화 (CPU·I/O) 가
프로세스당 5.7–9.5 s → k=4 에서 76–79 s 로 늘었다.

**[추정]** 상한을 update 당 최대 0.0608/4 s 로 바꾸면 순차 학습 14.1–**34.0** h + 고정비 ≤5.2 h = 약 14–39 h (변화 1.3%).
main 규모 동시 실행 이득은 학습 비중이 달라 pilot 값 (2.2 배) 을 그대로 쓰지 않는다.

**[미측정]** S 후보 fit 시간, main 규모 실자료 epoch 시간 (승인 전 금지), main 규모 동시 실행, 반복 변동의 원인.

### 9.2 스레드 고정과 main 규모 실측 (2026-09-28, 부록 BT·BU)

**[측정] 스레드 고정** (pilot 기술 분할 outer 0, inner fit 96, k=4, 프로세스당
`OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=2`): 창 예측·checkpoint·eval_loss 96/96 바이트 동일.
fit 당 벽시계 중앙 158.9 s → **73.5 s** (합 14,874.1 s → 7,191.3 s, 2.07 배).
학습 자체는 오히려 조금 늘었다 (s/epoch 중앙 0.0512 → 0.0527, 학습 시간 중앙 64.4 s → 66.4 s) —
줄어든 것은 9.1 절이 지목한 **학습 밖 CPU 단계**다. 이로써 "동시 실행에서 CPU 단계가 병목" 이라는 9.1 의 관측에
대응책이 생겼다. 이후 실행은 전부 이 설정을 쓴다.

**[측정] main 규모** (126 명, 결정 23 승인 뒤 실행, k=4·스레드 2): inner 480 fit **2 h 44 m**,
outer 60 fit **26.4 분**, select-ad 5 + evaluate + report 는 각각 초 단위. 전체 06:44:36Z–09:55:10Z (약 3 h 11 m).
fit 당 벽시계는 log 표본에서 87–107 s 수준이다. 9.1 의 순차 추정 (14–39 h) 과 견주면 동시 실행 k=4 + 스레드 고정으로
main A–D 전량이 3 시간 안에 끝났다.

**[측정] 보조 비교** (S 4 후보 · NG · SG): inner 720 + select 15 + outer 43 이 10:07:18Z–12:02:00Z (약 1 h 55 m).
이로써 9.1 의 **[미측정]** 중 "S 후보 fit 시간" 과 "main 규모 실자료 epoch 시간·동시 실행" 은 실측으로 바뀌었다.

**[미측정]** main 규모에서 스레드 2 가 최적인지 (대조를 돌리지 않았다), 벽시계 감소의 단계별 분해,
NG·SG 실자료 parameter/비용 집계 (`comparison_statistics.json` `not_reported`).
