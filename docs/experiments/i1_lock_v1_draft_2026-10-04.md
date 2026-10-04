# I1 — 사전등록 잠금 문서 **초안** (2026-10-04)

> **아직 잠금이 아니다.** 결정 38-4 ("저장소 내 잠금 문서 — v1 처럼 계획서 커밋 + 잠금 해시") 의 초안이다.
> §2 는 이미 결정된 것을 결정 번호와 함께 옮긴 것이고, §3 은 **잠금 전에 정해야 할 것** (권고 포함, 결정 아님) 이다.
> §3 이 모두 정해지면 → §4 의 잠금 JSON 을 h197 에서 만들고 → 이 문서와 함께 커밋 → 본 실행 승인 (결정 39) 순서다.
> 근거 문서: I1 계획서 초안 `docs/experiments/i1_protocol_draft_2026-10-02.md` (이하 "계획서"), 승인 대장 `docs/handoff/mobse_v3_checkpoint_2026-10-01.md` §11.

## 1. 질문과 주장 범위 (계획서 §1 그대로)

뇌 그래프 딥러닝 모델의 "ROI 정체 · 해부학적 배치를 쓴다" 는 판정이 (a) 모델 구조의 대칭성, (b) null 의 종류, (c) 재학습 변동,
(d) target 포화에 얼마나 좌우되는가. 검정 대상 C1–C5 (계획서 §1). **주장하지 않는 것**: 어느 모델이 가장 좋다 · ASD 진단 성능 · 새 모델 · 효율 우위.

## 2. 정해진 것 (잠금 대상)

| 항목 | 내용 | 근거 |
|---|---|---|
| 모델 | BNT · BQN · Han dual-pathway · BrainGB GCN (mean pooling · `--node_features degree`) + MoBSE v3 (외부 prior) | 결정 37 · 40 |
| 하이퍼파라미터 | 저장소 공식 기본값 + 저자 ABIDE 명령, **튜닝 없음**. 예외 BrainGB 구성 (결정 40). 명령은 `scripts/i1/run_fold.py` 에 고정 (`HAN_OVERRIDES` 등) | 계획서 §7 · 결정 40 |
| epoch | 저장소 기본 — BQN 200 · BNT 200 · Han 100 · BrainGB 100 | [코드] |
| 자료 | ABIDE I PCP 표준 판 (CPAC · filt_noglobal · CC200) 1,009 명, `abide.npy` sha `d81bb42063d6` · AOMIC PIOP1 (포화 양성 대조) | 결정 36 · 39 |
| AOMIC 범위 | 공개 넷 + MoBSE + 기준선 모두 | 결정 39-② |
| null | N0 일관 재배열 · N1 피험자별 순열 · N2 피험자별 spin (반구 = 중심 x 부호) · N3 피험자별 가중 · 부호 null (Rubinov–Sporns, 부호 수정판, 시계열은 원래 것) | 결정 38-1 · 41 |
| null 입력 | `scripts/i1/null_inputs.py` — seed `SeedSequence([20261003, 조건, k, 피험자+1])`, `pcorr` 제거 | 계획서 §9.2 |
| 반복 | K=5 · R=3 (BrainGB K=3 · R=2) | 결정 38-3 |
| 분할 | 층화 무작위 5-fold, 층 = label × site, 안쪽 val = train fold 의 층화 10 % — `results/i1/folds_draw0.json` | 결정 38-2 · 42 |
| site 민감도 | site 단위 분할을 민감도로 (대상 모델 · 반복 수는 §3) | 결정 38-2 |
| 실행 | 메모리 wrapper `scripts/i1/run_fold.py` — 저장소 파일 불변, 바꾼 함수 목록은 fit 마다 `summary.json` | 결정 41-1 |
| test 예측 | 네 모델 모두 안쪽 val loss (확률에서 계산한 평균 CE) 최소 epoch, 같으면 앞 epoch | 결정 42 |
| 결정성 | `use_deterministic_algorithms(True)` — BrainGB 만 끔 (OOM · CPU 불가), 그 비결정성은 D3 에 포함 | 계획서 §9.5 |
| 지표 | AUC 주 · BA (문턱 0.5) 보조 | 계획서 §7 |
| 포화 | 기준값 없음 — 기준선 성능을 반드시 함께 보고 (보고 장치) | 결정 39-① |
| 사전등록 형식 | 저장소 내 잠금 문서 + 잠금 해시 | 결정 38-4 |
| PIOP2 | 열지 않음 | 결정 27 |

## 3. 잠금 전에 정해야 할 것 (권고 — 결정 아님)

**3.1 추정량과 Δ 의 단위** — 권고: 조건 c · null 번호 k · seed r 마다 5 fold 의 test 예측을 모아 **OOF AUC** 하나를 낸다.
Δ_{c,k,r} = AUC(원판, r) − AUC(c, k, r) — 같은 seed r 끼리 짝짓는다. 조건별 요약은 k · r 평균 Δ_c.

**3.2 CI 두 종류** (계획서 §6 의 "나란히") — 권고:
- 단일 학습 CI: r=1 · k=0 한 쌍의 Δ 에 피험자 bootstrap (같은 피험자 재표집, 2,000 회, 95 % percentile).
- 재학습 포함 CI: 피험자를 재표집하고 그 안에서 (k, r) 판도 복원 재표집하는 2 단 bootstrap (2,000 회, 95 % percentile).
- 판정 문장: "조건 c 에서 Δ 의 재학습 포함 CI 가 0 을 넘는다 / 0 을 포함한다". 최소 관심 효과 (δ) 는 두지 않는다 — 진단 연구라 크기와 CI 를 그대로 보고.
- 다중성: 모델 × 자료 × 조건의 판정은 **보정 없이 기술용** 으로 두고 그 사실을 적는다 (C3 이 "단일 학습 CI 의 과신" 을 재는 연구이므로, 보정이 그 측정을 가리지 않게).

**3.3 실패 판 처리** — 권고: 다시 돌리지 않고 **그대로 센다** (계획서 §3 D3 "빼지 않고 센다"). 붕괴 판정 = test 예측의 표준편차 < 1e−6 또는
한 class 로만 예측 (BA = 0.5 이고 예측 class 1 비율 0 또는 1). 붕괴 수를 모델 · 조건마다 보고하고, 붕괴 판을 뺀 결과를 민감도로 함께 낸다.
프로세스 오류 (rc ≠ 0) 는 같은 seed 로 한 번 재시도, 다시 실패하면 실패로 기록.

**3.4 R 반복에서 fold 재추첨** — 권고: **하지 않는다** (draw 0 고정, seed 만 바꿈). 원판과 null 의 짝이 같은 fold 를 쓰고,
D3 가 재는 것을 "학습 변동" 으로 좁힌다. fold 변동은 site 민감도와 함께 한계로 적는다.

**3.5 site 민감도** — 권고: 대상 BQN 한 모델 (가장 쌈), leave-site-out 이 아니라 **site 묶음 5-fold** (`GroupKFold`, site 20 개), 원판 + N1 만, R=3.

**3.6 AOMIC 입력** — 아직 만들지 않았다. **v3 추출물에는 run 전체 시계열이 없고 창만 있다** [측정]: run 마다 `win-0…3`, 창 하나 30 시점 × 100 ROI
(`derivatives_v3/sub-*/…_task-{emomatching,workingmemory}_acq-seq_win-*.npy`). 선택지:
- (가) **창 = 표본** (T=30, FC 는 창마다), 예측은 run 단위로 평균해 run 수준에서 평가 — v1 · v3 와 같은 단위 (A−S · S 1.000 이 이 단위의 값). 권고.
- (나) 같은 추출 코드 (`mobse/v2/extract.py`) 로 run 전체 시계열을 새 derivative 로 다시 뽑고 두 task 를 같은 길이로 자른다 — 공개 모델의 원래 쓰임 (긴 시계열 FC) 에 가깝지만 새 추출물이 생긴다.
- 공통: 대상 = main 126 명 (pilot 31 은 쓰지 않음), **fold 는 피험자 단위로 묶는다** (한 피험자의 run · 창이 train 과 test 로 갈라지지 않게), 좌표 = Schaefer-100 2009c.
  FC 는 ABIDE 와 같은 방식 (nilearn 상관 → arctanh, 대각 0).

**3.7 MoBSE 팔** — 권고: v3 잠금 (`c0c8ed77db50`) 의 모듈과 config 를 그대로 쓰고, 칸은 **A (mean, 등변 대표)** 와 embedding 1 칸,
null 은 v3 의 세 종류 (순열 · spin · rewire) 를 K=5 · R=3. 자료는 AOMIC 만 (ABIDE 는 MoBSE 의 rest template bank 가 없다).

**3.8 기준선** (D4) — 아직 코드가 없다. 권고: S3 와 같은 정의의 FC logistic (상삼각 · 표준화 · C grid 는 안쪽 val 로 선택) · FC-MLP (은닉 32) ·
시계열 평균 S1, 같은 fold · R=3. 원판 입력만 (null 은 기준선에 의미가 없다 — 기준선은 피험자별 순열에 영향을 받는 정도를 따로 재지 않는다).

**3.9 D1 학습판** — 권고: 원판 · r=1 · fold 0–2 의 **마지막 epoch checkpoint** 3 개, 순열 20 개 (seed 1729). wrapper 가 마지막 epoch 상태를
저장해야 한다 (아직 없음 — BNT 만 저장소가 `model.pt` 를 남긴다).

**3.10 n3 생성 비용** — 약 17 h (8 병렬) [추정]. 권고: 그대로 (본 실행과 겹쳐 CPU 에서 미리 돌린다). 가속은 하지 않는다 (구현을 바꾸면 smoke 를 다시 해야 한다).

## 4. 잠금 JSON (만들 것)

`results/i1/locks/i1_lock.json` — h197 에서 만든다. 담는 것:
- `code`: `scripts/i1/*.py` 의 sha256 (경로순) 과 code_hash, `mobse/v3/templates.py` 의 sha256 (spin 을 import 하므로)
- `data`: 표준 `abide.npy` · `abide.json` · `folds_draw0.json` · `cc200_coords.json` · CC200 atlas 의 sha256, AOMIC 입력 (§3.6 뒤)
- `repos`: `i1/repos_commits.txt` 의 저장소별 commit (BrainGNN · Contrasformer 는 대상 밖이지만 적혀 있는 그대로)
- `environment`: venv-i1 `pip freeze` sha256 (`i1/venv_i1_freeze.txt` 와 대조), torch · CUDA · GPU
- `document`: 이 문서 (잠금판) 의 sha256
- `lock_hash`: 위 전부의 해시. 검증 (`--verify`) 은 마감 단계에 넣지 않고 I1 실행 구동기가 fit 전에 부른다 [구현 선택 — 제안].

## 5. 잠금 뒤 바꾸면

잠금 뒤의 설계 · 모델 · 지표 변경은 새 판 (v2 잠금) 과 사유 기록이 필요하다 (v1 의 §8 이탈 기록과 같은 방식). 버그 수정은 잠금 재생성 + 사유.
