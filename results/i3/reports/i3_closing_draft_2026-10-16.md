# I3 (PIOP1 emomatching 과제 안 조건) 마감 초안 · 2026-10-16

> **무엇인가**: I3 본 실행과 그 뒤 진단을 한곳에 모은 **마감 문서 초안**이다 (결정 72). 주장마다 산출물을 잇고,
> 사전 기록한 한계와 재현 방법을 적는다.
> **무엇이 아닌가**: 마감 확정이 아니다. §6 의 해석 문장은 **초안**이며 선생님 확인 전이다. 설계 변경도 아니다.
> 모든 수치는 산출물에서 다시 잰 값이며 출처를 함께 적었다. `[추정]` 은 재지 않은 값이다.
> 정본 진행 기록은 `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.31–§11.37 (결정 67–72) 이다.

## 1. 한 문단 요약

v1 과 v3 에서 주가설 H1 (A−B, 입력 의존 routing) 과 H2 (A−C, 정렬된 뇌 graph bank) 를 잰 target 은 모두 포화돼
있었다 (S 1.000 · 학습 10 명 S3 0.984). I3 는 target 을 **emomatching 과제 안의 조건 (emotion 대 control 블록)** 으로
바꿔 포화되지 않은 자리에서 다시 물었다. 활성 정보를 지우는 블록 안 z-score 입력으로 FC 만 남겼다.

- **포화 해소**: 됐다. MoBSE 칸이 0.54–0.71, S 0.666 으로 흩어졌다. 활성 기준선만 0.981 이다.
- **주가설**: 넷 중 지지 방향은 mean H2 하나다. 그것도 δ 에 못 미치고 민감도에서 사라져 **"지지 안 됨"** 으로 적는다 (결정 71).
  - embedding H1 은 **반대 방향** (A−B −0.118) 이다.
  - 어떤 A 도 S 를 넘지 못했다.
- **진단 (새 학습 없음 · 결정론 재현)**: 입력 의존 gate 가 **학습 전부터 블록마다 expert 하나를 고른다.**
  - I3 에서는 그 선택이 조건과 거의 무관하다. gate 를 평균 weight 로 고정하면 정확도가 오른다.
  - 같은 점검을 v1 checkpoint 에 하면 v1 의 gate 도 똑같이 하나를 고르지만, 그 선택이 **과제 label 을 따라간다.**
  - v1 에서 gate 를 고정하면 정확도가 0.877 에서 0.730 으로 떨어진다.

## 2. 무엇을 바꿨나 (v1 대비)

| 축 | v1 | I3 | 근거 |
|---|---|---|---|
| target | run identity (emomatching 대 workingmemory) | **emomatching 안 블록 조건** (emotion 대 control, 사람당 8 블록 4:4) | 결정 67 · 68 |
| 입력 | 60 s 창 4 개/run | **30 s 블록 (15 frame), lag 6 s, 블록 안 ROI z-score (blockz)** | 결정 69 |
| 피험자 | main 126 | main 126 (재추출 157 명 전원 ok, pilot 31 은 기술 결정에만) | 결정 68 |
| 분할 | outer 5 · inner 3 · config grid | outer 5 · **inner fold 0 val 로 best checkpoint · config 0 고정** | 결정 69 |
| 칸 | A–D (+ S · NG · SG 보조) | **A–D × mean · embedding + NG · SG = 10 칸**, null 민감도 C · D × spin · rewire 8 칸 | 결정 69 |
| 학습 | `MIN_UPDATES 5000` · `MAX_EPOCHS 400` | update 예산 5,000 · epoch 상한 없음 · best checkpoint 자유 (v3 규칙) | 결정 31 · 32 · 69 |
| gate 입력 | training-rest PCA 10 | 같음 (그대로 둠) | — |
| 실행 호스트 | h197 (CUDA) | **Mac (MPS)** | 결정 68 |

잠금 `results/i3/locks/lock.json` (lock_hash `1bc3622dcd85`, code `34b04c7c307c`, data `e141ff75dda5`), 잠금 문서 `docs/experiments/i3_lock_v1.md`.

## 3. claim–evidence 표

| # | 주장 | 근거 (수치) | 산출물 |
|---|---|---|---|
| C1 | 설계상 δ 0.02 는 탐지할 수 없었다 (사전 기록) | 126 명 × 8 블록에서 P(하한>0 \| δ 0.02) 0.09–0.42, 80 % 를 넘는 δ 0.04–0.08 | `scripts/h1h2_scope/i3_gb_power.py` · handoff §11.32 |
| C2 | 조건과 시간 위치가 겹친다 (사전 기록) | 157 명 전원 c e c e c e c e. pilot: control 안 뒤 대 앞 BA 0.758, 첫 짝 제외 시 조건 BA 0.657 → 0.591 | `i3_time_check.py` · §11.32 |
| C3 | target 은 포화되지 않았다 | MoBSE 칸 0.539–0.712, S 0.666, NG 0.543. 활성 기준선 (blockz 이전 입력) 0.981 | `data/i3/main/20261016_1bc3622d_a1/analysis/analysis.json` (sha `20318dd9c961`) |
| C4 | 주가설 H1 · H2 는 지지되지 않았다 | §4 표. mean H2 +0.020 [+0.001, +0.039] 는 δ 미달 · 첫 짝 제외 시 [−0.001, +0.044] → "지지 안 됨" (결정 71) | 같은 파일 |
| C5 | embedding 에서는 routing 을 없앤 B 가 A 를 이긴다 | A−B −0.118 [−0.156, −0.081], 첫 짝 제외 −0.128 | 같은 파일 |
| C6 | MoBSE 의 어느 A 도 FC logistic 을 넘지 못했다 | A−S mean −0.093 [−0.130, −0.055] · embedding −0.071 [−0.109, −0.034] | 같은 파일 |
| C7 | embedding 의 차이는 bank 가 아니라 routing 유무를 따라 갈린다 | routing 고정 embedding 4 칸 (B · D 순열 · spin · rewire) 0.677–0.712 · 선택 시점 val loss 0.54–0.59. 입력 routing 칸 (A · C 3 종) 0.561–0.594 · val loss 0.67–0.68 | `scripts/i3_diag/read_diag.py` |
| C8 | I3 의 입력 의존 gate 는 블록마다 expert 하나를 고르며, 그 선택은 조건과 거의 무관하다 | A embedding test entropy 중앙 0.164 (균일 1.099), label 사이 차이 최대 중앙 0.068. 재현 30/30 바이트 동일 | `data/i3/diag/routing_a1/` · `scripts/i3_diag/routing_summary.py` |
| C9 | 그 쏠림은 학습 전부터 있다 | 초기화 직후 val entropy 0.310–0.530. gate 입력 PCA 는 rest 기준이라 과제 블록에서 첫 성분 평균 −27.0 · 열 SD 5.3–25.9 | `scripts/i3_diag/gate_init_check.py` |
| C10 | I3 에서 gate 를 평균으로 고정하면 정확도가 오른다 | A embedding 0.594 → 0.642 (새 학습 없음, CI 미계산) | `routing_summary.py` |
| C11 | v1 의 gate 도 하나를 고르지만, 그 선택이 과제 label 을 따른다 | v1 A · C test entropy 중앙 0.102 · 0.107, label 사이 차이 0.523 · 0.520. 고정 시 run BA A 0.877 → 0.730 · C 0.893 → 0.770. 재현: 보고값과 같은 BA, 확률 차이 ≤ 3.7e-6 | h197 `$D/i3_diag/v1_gate_20261016/v1_gate_check.json` (sha `c6cf0f1e665b`) |

## 4. 결과 (126 명 · 1,008 블록 · seed 3 개 평균 확률 · 피험자 bootstrap 10,000)

| 칸 | mean | embedding |
|---|---:|---:|
| A (정렬 bank · 입력 routing) | 0.572 [0.543, 0.602] | 0.594 [0.562, 0.627] |
| B (정렬 bank · 고정 routing) | 0.562 | 0.712 [0.681, 0.743] |
| C (순열 bank · 입력 routing) | 0.553 | 0.586 |
| D (순열 bank · 고정 routing) | 0.562 | 0.677 |
| C spin · rewire | 0.552 · 0.539 | 0.572 · 0.561 |
| D spin · rewire | 0.563 · 0.563 | 0.690 · 0.698 |

비교 칸: NG 0.543 · SG 0.560 · S (blockz FC logistic) 0.666 · 활성 기준선 0.981.

| 구조 | 가설 | 추정 | 97.5% CI | 첫 짝 제외 | 판정 |
|---|---|---:|---|---|---|
| mean | H1 A−B | +0.010 | [−0.015, +0.034] | +0.013 [−0.016, +0.041] | 0 포함 |
| mean | H2 A−C | +0.020 | [+0.001, +0.039] | +0.021 [−0.001, +0.044] | **지지 안 됨** (δ 미달 · 민감도 0 포함) |
| embedding | H1 A−B | −0.118 | [−0.156, −0.081] | −0.128 [−0.169, −0.089] | 상한 < 0 |
| embedding | H2 A−C | +0.008 | [−0.027, +0.042] | +0.025 [−0.012, +0.061] | 0 포함 |

보조 (95 %, 기술적):

- A−C_spin: mean +0.021 (하한 > 0) · embedding +0.022 (0 포함)
- A−C_rewire: mean +0.034 · embedding +0.034 (둘 다 하한 > 0)
- A−NG: mean +0.030 (0 포함) · embedding +0.052 (하한 > 0)
- A−SG: 두 구조 모두 0 포함

실행: Mac MPS · 동시 2, 10:01:44–11:11:48 KST (70 분), fit 270 · 실패 0 · 붕괴 0.

## 5. 음성 결과

1. H1 · H2 는 포화되지 않은 target 에서도 지지되지 않았다 (C4).
2. embedding 에서 입력 routing 은 이득이 아니라 손실이었다 (C5).
3. MoBSE 는 같은 FC 입력의 logistic 보다 낮다 (C6). v1 (A−S −0.123) · v3 (−0.17 ~ −0.35) 와 같은 방향이다.
4. mean 구조는 모든 칸이 같은 약한 상태다. 선택 시점 val loss 가 0.683–0.685 이고, 블록 위치에 따라 정확도가 번갈아 오르내린다 (짝수 블록 0.65–0.72, 홀수 블록 0.40–0.49).

## 6. 해석 초안 (미확정 — 선생님 확인 전)

- **6-1. 이 설계에서 H1 은 "입력 의존 routing 의 이득" 을 재지 못했을 수 있다.** gate 입력 (rest 로 맞춘 PCA) 이 과제 자료에서 편향되고 스케일이 커서, 학습 전부터 gate 가 사실상 이산 선택기로 작동한다.
  - v1 에서는 그 이산 선택이 과제 label 과 맞아떨어졌다. 그래서 gate 자체가 분류기 노릇을 했을 가능성이 있다 (고정하면 −0.147).
  - I3 처럼 label 이 FC 의 큰 축에 실리지 않는 target 에서는 같은 이산 선택이 잡음이 된다 (고정하면 +0.048).
- **6-2. v1 의 A ≈ C (H2 불확실) 와도 들어맞는다.** gate 가 label 을 따라 graph 하나를 고른다면 그 graph 의 내용 (정렬 대 순열) 은 덜 중요하다. v1 의 C 도 A 와 같은 정도로 label 을 따른다 (0.520 대 0.523).
- **6-3. 이 진단은 MoBSE 개념의 반증이 아니라 이 gate 구현 (입력 스케일 · 온도 · 초기화) 의 성질에 대한 관찰이다.** 바꿔 보려면 본 결과를 본 뒤의 설계 변경이므로 새 탐색 버전이 된다 (계획서 §3 · §4-5 · §8).

## 7. 한계

1. δ 0.02 는 탐지할 수 없는 크기로 사전 기록됐다 (C1).
2. 조건 순서가 전원 같아 조건과 시간 위치가 겹친다 (C2). 첫 짝 제외는 이를 일부만 다룬다.
3. inner fold 0 하나로 best checkpoint 를 고르고 config 를 0 으로 고정했다. v1 의 config grid 와 다르다.
4. 진단 (C7–C11) 은 본 결과를 본 뒤의 탐색 분석이다. 사전등록되지 않았고 CI 가 없는 기술값이 섞여 있다 (C10 · C11 의 고정 대조).
5. v1 과 I3 의 고정 대조는 평균 weight 의 출처가 다르다 (I3 val 창 · v1 train 창, v1 outer 적합에는 val 이 없음).
6. v1 점검의 초기화 entropy 는 `torch.manual_seed(seed)` 로 만든 것이다. `train_fold` 의 seed 경로와 같은지 확인하지 않았다.
7. 실행 호스트가 Mac MPS 로 v1 (h197 CUDA) 과 다르다. MPS 결정론은 확인했다.

## 8. 재현

```bash
# 본 실행 (Mac, 저장소 루트; 잠금 검증이 rc 0 일 때만 시작)
PYTHONPATH=. .venv/bin/python -B scripts/i3/run_main.py --mode main --data-root data/h1h2_scope/aomic --out-root data/i3 \
    --lock results/i3/locks/lock.json --run-id 20261016_1bc3622d_a1 --jobs 2
# 진단
python3 scripts/i3_diag/read_diag.py data/i3/main/20261016_1bc3622d_a1
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/routing_repro.py --run data/i3/main/20261016_1bc3622d_a1 --out data/i3/diag/routing_a1 --jobs 2
python3 scripts/i3_diag/routing_summary.py data/i3/diag/routing_a1
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_init_check.py data/i3/main/20261016_1bc3622d_a1
# v1 점검 (h197, 그 run 의 code 사본)
PYTHONPATH=$R/code $VENV/bin/python -B scripts/i3_diag/v1_gate_check.py --root $R --out <out.json>
```

주의: 저장소 루트에 `mobse.egg-info` 가 있으면 `PYTHONPATH=.` 에서 잠금 검증이 실패한다 (§11.34). 지금은 `.backup/to-delete_20261016/` 로 옮겨 두었다.

## 9. 정하지 않은 것

- I3 마감 확정과 §6 해석 문장의 확정
- gate 입력 표준화 등 설계 변경 (새 탐색 버전)
- ② ABIDE A–D
- PIOP2
- 보고서 형식 (BMC 내부 보고서 · Notion)
- 푸시
