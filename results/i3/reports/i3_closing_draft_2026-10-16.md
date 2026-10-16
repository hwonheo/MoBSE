# I3 (PIOP1 emomatching 과제 안 조건) 마감 문서 · 2 판 · 2026-10-16

> **무엇인가**: I3 본 실행과 그 뒤 진단을 한곳에 모은 **마감 문서**다. 1 판은 결정 72 의 초안이고, 2 판 (결정 74) 은
> gate 크기 맞춤 pilot (결정 73) 과 추가 대조를 더하고 §6 해석을 확정 후보로 다듬었다.
> **무엇이 아닌가**: §6 은 **확정 후보**이며 선생님 확인 전이다. 설계 변경도 아니고, 다음 방향의 결정도 아니다.
> 모든 수치는 산출물에서 다시 잰 값이며 출처를 함께 적었다. `[추정]` 은 재지 않은 값이다.
> 정본 진행 기록은 `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.31–§11.42 (결정 67–74) 이다.

## 1. 한 문단 요약

v1 과 v3 에서 주가설 H1 (A−B, 입력 의존 routing) 과 H2 (A−C, 정렬된 뇌 graph bank) 를 잰 target 은 모두 포화돼
있었다 (S 1.000 · 학습 10 명 S3 0.984). I3 는 target 을 **emomatching 과제 안의 조건 (emotion 대 control 블록)** 으로
바꿔 포화되지 않은 자리에서 다시 물었다. 활성 정보를 지우는 블록 안 z-score 입력으로 FC 만 남겼다.

- **포화 해소**: 됐다. MoBSE 칸이 0.54–0.71, S 0.666 으로 흩어졌다. 활성 기준선만 0.981 이다.
- **주가설**: 넷 모두 지지되지 않았다. 지지 방향은 mean H2 하나였으나 δ 에 못 미치고 민감도에서 사라졌다 (결정 71).
  - embedding H1 은 **반대 방향** (A−B −0.118) 이다.
  - 어떤 A 도 S 를 넘지 못했다.
- **진단 (새 학습 없음 · 결정론 재현)**: 입력 의존 gate 가 **학습 전부터 블록마다 expert 하나를 고른다.**
  - I3 에서는 그 선택이 조건과 거의 무관하다. gate 를 평균 weight 로 고정하면 정확도가 오른다.
  - v1 의 gate 도 똑같이 하나를 고르지만, 그 선택이 **과제 label 을 따라간다.** 고정하면 0.877 에서 0.730 으로 떨어진다.
- **gate 를 고쳐 보는 길 (pilot)**: 입력 크기를 맞추면 학습 전 쏠림은 사라지지만 학습 뒤 다시 쏠리고, 정확도도 오르지 않았다.
- **남는 단서 (기술값)**: routing 을 끈 embedding 모델 B 는 S 를 넘었다 (+0.047). 그 안에서 정렬 bank 는 순열 bank 보다 높았으나 (+0.036) spin · rewire 대비로는 작아지거나 0 을 포함했다.

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
| 실행 호스트 | h197 (CUDA) | **Mac (MPS)**, 산출물은 h197 로 옮김 | 결정 68 · §11.41 |

잠금 `results/i3/locks/lock.json` (lock_hash `1bc3622dcd85`, code `34b04c7c307c`, data `e141ff75dda5`), 잠금 문서 `docs/experiments/i3_lock_v1.md`.

## 3. claim–evidence 표

산출물 경로는 h197 자료 루트의 `i3/` 기준이다 (Mac 작업 사본 `data/i3/` 와 sha256 동일, §11.41).

| # | 주장 | 근거 (수치) | 산출물 |
|---|---|---|---|
| C1 | 설계상 δ 0.02 는 탐지할 수 없었다 (사전 기록) | 126 명 × 8 블록에서 P(하한>0 \| δ 0.02) 0.09–0.42, 80 % 를 넘는 δ 0.04–0.08 | `scripts/h1h2_scope/i3_gb_power.py` · handoff §11.32 |
| C2 | 조건과 시간 위치가 겹친다 (사전 기록) | 157 명 전원 c e c e c e c e. pilot: control 안 뒤 대 앞 BA 0.758, 첫 짝 제외 시 조건 BA 0.657 → 0.591 | `i3_time_check.py` · §11.32 |
| C3 | target 은 포화되지 않았다 | MoBSE 칸 0.539–0.712, S 0.666, NG 0.543. 활성 기준선 (blockz 이전 입력) 0.981 | `i3/main/20261016_1bc3622d_a1/analysis/analysis.json` (sha `20318dd9c961`) |
| C4 | 주가설 H1 · H2 는 지지되지 않았다 | §4 표. mean H2 +0.020 [+0.001, +0.039] 는 δ 미달 · 첫 짝 제외 시 [−0.001, +0.044] → "지지 안 됨" (결정 71) | 같은 파일 |
| C5 | embedding 에서는 routing 을 없앤 B 가 A 를 이긴다 | A−B −0.118 [−0.156, −0.081], 첫 짝 제외 −0.128 | 같은 파일 |
| C6 | MoBSE 의 어느 A 도 FC logistic 을 넘지 못했다 | A−S mean −0.093 [−0.130, −0.055] · embedding −0.071 [−0.109, −0.034] | 같은 파일 |
| C7 | embedding 의 큰 차이는 routing 유무에서 온다. bank 효과는 작고 null 종류에 따라 다르다 | routing 고정 embedding 4 칸 0.677–0.712 · 선택 시점 val loss 0.54–0.59, 입력 routing 칸 (A · C 3 종) 0.561–0.594 · val loss 0.67–0.68. 고정 routing 안 B−D: 순열 +0.036 [+0.012, +0.061] · spin +0.022 [0.000, +0.044] · rewire +0.014 [−0.009, +0.037] (95 %, 기술값) | `scripts/i3_diag/read_diag.py` · `i3/diag/extra_contrasts.json` (sha `ddb589989410`) |
| C8 | I3 의 입력 의존 gate 는 블록마다 expert 하나를 고르며, 그 선택은 조건과 거의 무관하다 | A embedding test entropy 중앙 0.164 (균일 1.099), label 사이 차이 최대 중앙 0.068. 재현 30/30 바이트 동일 | `i3/diag/routing_a1/` · `scripts/i3_diag/routing_summary.py` |
| C9 | 그 쏠림은 학습 전부터 있다 | 초기화 직후 val entropy 0.310–0.530. gate 입력 PCA 는 rest 기준이라 과제 블록에서 첫 성분 평균 −27.0 · 열 SD 5.3–25.9 | `scripts/i3_diag/gate_init_check.py` |
| C10 | I3 에서 gate 를 평균으로 고정하면 정확도가 오른다 | A embedding 0.594 → 0.642 (새 학습 없음, CI 미계산) | `routing_summary.py` |
| C11 | v1 의 gate 도 하나를 고르지만, 그 선택이 과제 label 을 따른다 | v1 A · C test entropy 중앙 0.102 · 0.107, label 사이 차이 0.523 · 0.520. 고정 시 run BA A 0.877 → 0.730 · C 0.893 → 0.770. 재현: 보고값과 같은 BA, 확률 차이 ≤ 3.7e-6 | h197 `i3_diag/v1_gate_20261016/v1_gate_check.json` (sha `c6cf0f1e665b`) |
| C12 | gate 입력 크기를 맞추면 학습 전 쏠림은 사라진다 (pilot) | 초기화 직후 entropy: 그대로 0.068–0.455 → rest 기준 1.080–1.095 · 과제 블록 기준 1.075–1.088 | `scripts/i3_diag/gate_scale_check.py` · §11.38 |
| C13 | 그러나 학습 뒤 다시 쏠리고 정확도도 오르지 않았다 (pilot) | pilot 31 명 5 fold · 60 fit: 학습 뒤 entropy 0.195 · 0.360 · 0.390, 정확도 0.605 · 0.573 · 0.560 (그대로 · rest · 과제). 세 입력 모두 gate 고정이 손해 | `i3/diag/gate_scale_pilot_a1/summary.json` (sha `3a17630c088e`) · §11.39 |
| C14 | routing 을 끈 embedding 모델은 FC logistic 을 넘었다 (기술값) | B−S +0.047 [+0.008, +0.085], 첫 짝 제외 +0.087 [+0.045, +0.128]. D (순열 · spin · rewire) − S 는 +0.011 · +0.025 · +0.033, 모두 0 포함 | `i3/diag/extra_contrasts.json` |

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

보조 (95 %, 사전 지정):

- A−C_spin: mean +0.021 (하한 > 0) · embedding +0.022 (0 포함)
- A−C_rewire: mean +0.034 · embedding +0.034 (둘 다 하한 > 0)
- A−NG: mean +0.030 (0 포함) · embedding +0.052 (하한 > 0)
- A−SG: 두 구조 모두 0 포함

추가 대조 (95 %, 결과를 본 뒤 정함 — 기술값, `extra_contrasts.json`):

| 대조 | 전체 | 첫 짝 제외 |
|---|---|---|
| B emb − S | +0.047 [+0.008, +0.085] | +0.087 [+0.045, +0.128] |
| D emb (순열) − S | +0.011 [−0.032, +0.055] | +0.045 [−0.001, +0.091] |
| D emb spin − S | +0.025 [−0.014, +0.063] | +0.061 [+0.019, +0.103] |
| D emb rewire − S | +0.033 [−0.010, +0.076] | +0.075 [+0.030, +0.122] |
| B − D emb (순열) | +0.036 [+0.012, +0.061] | +0.042 [+0.015, +0.071] |
| B − D emb spin | +0.022 [0.000, +0.044] | +0.026 [−0.001, +0.054] |
| B − D emb rewire | +0.014 [−0.009, +0.037] | +0.012 [−0.015, +0.037] |

실행: Mac MPS · 동시 2, 10:01:44–11:11:48 KST (70 분), fit 270 · 실패 0 · 붕괴 0.

## 5. 음성 결과

1. H1 · H2 는 포화되지 않은 target 에서도 지지되지 않았다 (C4).
2. embedding 에서 입력 routing 은 이득이 아니라 손실이었다 (C5).
3. MoBSE 의 A 는 같은 FC 입력의 logistic 보다 낮다 (C6). v1 (A−S −0.123) · v3 (−0.17 ~ −0.35) 와 같은 방향이다.
4. mean 구조는 모든 칸이 같은 약한 상태다. 선택 시점 val loss 가 0.683–0.685 이고, 블록 위치에 따라 정확도가 번갈아 오르내린다 (짝수 블록 0.65–0.72, 홀수 블록 0.40–0.49).
5. gate 입력 크기를 맞추는 수정은 pilot 에서 효과가 없었다 (C13).

## 6. 해석 (확정 후보 — 선생님 확인 전)

- **6-1. 이 설계의 H1 은 "입력 의존 routing 의 이득" 을 재지 못했다.** gate 입력 (rest 로 맞춘 PCA) 이 과제 자료에서 편향되고 스케일이 커서, 학습 전부터 gate 가 사실상 이산 선택기로 작동한다 (C8 · C9). 그래서 A−B 는 "routing 의 이득" 이 아니라 "이산 선택기를 붙인 손익" 을 잰 것이다.
- **6-2. v1 의 양의 H1 과 I3 의 음의 H1 은 같은 gate 성질로 둘 다 설명된다.** v1 에서는 이산 선택이 과제 label 과 맞아떨어져 gate 가 분류기 노릇을 했고 (고정하면 −0.147), I3 처럼 label 이 FC 의 큰 축에 실리지 않는 target 에서는 같은 선택이 잡음이 된다 (고정하면 +0.048). 이것은 사후 설명이며 두 결과의 원인으로 확인한 것은 아니다.
- **6-3. v1 의 A ≈ C (H2 불확실) 와도 들어맞는다.** gate 가 label 을 따라 graph 하나를 고른다면 그 graph 의 내용 (정렬 대 순열) 은 덜 중요하다. v1 의 C 도 A 와 같은 정도로 label 을 따른다 (0.520 대 0.523).
- **6-4. gate 입력 크기만 고쳐서는 풀리지 않았다 (pilot).** 학습 전 쏠림은 사라지지만 학습이 다시 이산 선택으로 몰고 간다 (C12 · C13). 이 구조의 입력 의존 gate 를 살리려면 입력 스케일 말고도 온도 · 정규화 · 학습 목표를 함께 바꿔야 할 수 있으며, 그 근거는 지금 없다.
- **6-5. 남는 단서는 "routing 을 끈 embedding 그래프 모델" 이다 (기술값).** 이 모델만 FC logistic 을 넘었고 (C14), 그 안에서 정렬 bank 의 이득은 순열 대비 +0.036 이나 공간 구조를 보존하는 null (spin · rewire) 대비로는 0.022 · 0.014 로 작아져 0 에 닿는다 (C7). 즉 "정렬된 뇌 배선도" 의 고유 기여는 이 자료에서 크게 잡아도 0.01–0.04 이고, null 선택에 따라 사라진다.
- **6-6. 이 결과로 MoBSE 의 원래 두 주장 (입력 의존 routing · 정렬된 뇌 graph bank 의 기여) 을 지지할 근거는 v1 · v3 · I3 어디에도 없다.** 개념의 반증이라고까지 쓰지는 않는다 — 6-1 의 측정 결함 때문이다.

## 7. 한계

1. δ 0.02 는 탐지할 수 없는 크기로 사전 기록됐다 (C1).
2. 조건 순서가 전원 같아 조건과 시간 위치가 겹친다 (C2). 첫 짝 제외는 이를 일부만 다룬다. 추가 대조에서 첫 짝을 빼면 차이가 커지는 칸이 있다 (B−S +0.047 → +0.087).
3. inner fold 0 하나로 best checkpoint 를 고르고 config 를 0 으로 고정했다. v1 의 config grid 와 다르다.
4. 진단 (C7–C13) 과 추가 대조 (C7 의 B−D · C14) 는 본 결과를 본 뒤의 탐색 분석이다. 사전등록되지 않았고 다중성 보정이 없으며, CI 가 없는 기술값이 섞여 있다 (C10 · C11 의 고정 대조).
5. v1 과 I3 의 고정 대조는 평균 weight 의 출처가 다르다 (I3 val 창 · v1 train 창, v1 outer 적합에는 val 이 없음).
6. v1 점검의 초기화 entropy 는 `torch.manual_seed(seed)` 로 만든 것이다. `train_fold` 의 seed 경로와 같은지 확인하지 않았다.
7. pilot (C12 · C13) 은 학습 18–19 명이라 main 과 학습 양상이 다르다 — pilot 의 B 는 0.520, main 의 B 는 0.712. pilot 결과를 main 에 그대로 옮길 수 없다.
8. 실행 호스트가 Mac MPS 로 v1 (h197 CUDA) 과 다르다. MPS 결정론은 확인했다.

## 8. 재현

```bash
# 본 실행 (Mac, 저장소 루트; 잠금 검증이 rc 0 일 때만 시작)
PYTHONPATH=. .venv/bin/python -B scripts/i3/run_main.py --mode main --data-root data/h1h2_scope/aomic --out-root data/i3 \
    --lock results/i3/locks/lock.json --run-id 20261016_1bc3622d_a1 --jobs 2
# 진단 · 추가 대조
python3 scripts/i3_diag/read_diag.py data/i3/main/20261016_1bc3622d_a1
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/routing_repro.py --run data/i3/main/20261016_1bc3622d_a1 --out data/i3/diag/routing_a1 --jobs 2
python3 scripts/i3_diag/routing_summary.py data/i3/diag/routing_a1
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_init_check.py data/i3/main/20261016_1bc3622d_a1
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/extra_contrasts.py --run data/i3/main/20261016_1bc3622d_a1
# gate 크기 맞춤 (pilot 만)
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_scale_check.py --smoke data/i3/smoke/smoke_a1 --data-root data/h1h2_scope/aomic
PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_scale_pilot.py --data-root data/h1h2_scope/aomic --out data/i3/diag/gate_scale_pilot_a1 --jobs 2
# v1 점검 (h197, 그 run 의 code 사본)
PYTHONPATH=$R/code $VENV/bin/python -B scripts/i3_diag/v1_gate_check.py --root $R --out <out.json>
```

주의: 저장소 루트에 `mobse.egg-info` 가 있으면 `PYTHONPATH=.` 에서 잠금 검증이 실패한다 (§11.34). 지금은 `.backup/to-delete_20261016/` 로 옮겨 두었다. 산출물의 정본 위치는 h197 `MoBSE_dataset/i3/` 이며 경로 전체는 Notion `🗄️ Data Assets` 의 I3 행에 있다.

## 9. 정하지 않은 것

- §6 해석의 확정과 이 문서를 마감본으로 확정할지
- 다음 방향 (MoBSE 를 어디로 가져갈지), 새 탐색 버전 여부
- ② ABIDE A–D
- PIOP2
- 보고서 형식 (BMC 내부 보고서 · Notion)
- 푸시
