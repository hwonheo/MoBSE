# Methods Lock Addendum (2026-03-31)

이 문서는 본문 Methods에 바로 반영할 수 있는 실행 규칙과 분석 범위를 잠그기 위한 보조 문서다.

## 1) ETTh1 Data Source

| Item | Locked value |
|---|---|
| Dataset | ETTh1 |
| Source URL | `https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTh1.csv` |
| Local path | `data/reference_raw/ETTh1.csv` |
| Forecast target | `OT` |
| Windowing | `seq_len=96`, `pred_len=24` |

## 2) Seed / Repeat Policy

| Scope | Seeds | Status |
|---|---:|---|
| Main analysis | `42, 43, 44, 45, 46, 47, 48, 49, 50, 51` | locked |
| Exploratory extension | `42, 43, 44` | auxiliary only |

Locked interpretation:
- Main paper claims use the `10-seed` rerun line.
- The earlier `3-seed` ETTh-family extension is retained only as an exploratory check and should not be promoted to primary evidence.

## 3) Selection Metric and Early Stopping

| Run family | Task regime | Task-loss handling | Checkpoint selection | Early stopping |
|---|---|---|---|---|
| ETTh1-only | `tasks=[etth1]` | raw ETTh1 loss | `raw_loss` | patience `3`, min delta `0.0005` |
| Dual-task | `tasks=[os, etth1]` | normalized task losses enabled | `weighted_normalized_loss` | patience `3`, min delta `0.0005` |

Operational summary:
- Loss type for ETTh1 is `huber` with `delta=1.0`.
- Batch size is `32`, learning rate is `1e-3`, and gradient clipping is `1.0`.
- The dual-task branch uses task-loss normalization to keep OS and ETTh1 gradients comparable.

## 4) Main vs Exploratory Analysis Boundary

The manuscript should preserve the following separation:

1. Main analysis
- ETTh1 storyline with `10-seed` rerun results.
- Figure and table lock should use the rerun10 artifacts.
- This is the evidence base for the paper's core claims.

2. Exploratory extension
- ETTh2, ETTm1, and ETTm2 are used as generalization checks.
- The earlier `3-seed` extension is exploratory only.
- If space is limited, report the `10-seed` ETT-family rerun and omit the `3-seed` numbers from the main text.

## 5) Manuscript-ready Method Sentence

Suggested insertion:

> We used ETTh1 from the ETDataset repository (`ETT-small/ETTh1.csv`) and evaluated the primary storyline with 10-seed reruns (`42`--`51`). Exploratory generalization checks on ETTh2, ETTm1, and ETTm2 were kept separate from the main analysis and treated as auxiliary evidence only.

## 6) Hypothesis and Evidence Protocol (Added)

컨셉 노트와 본문 정합을 위해, Methods에 아래 가설-검증 프로토콜을 명시한다.

| Hypothesis | Operational test | Current status |
|---|---|---|
| H1. Statistical-prior routing | OS 성능 + 라우팅 지표(엔트로피/안정성) 동시 보고 | partially satisfied |
| H2. Complexity under matched compute | FLOPs/latency 고정 비교에서 성능 차이 확인 | satisfied |
| H3. Reproducible specialization | 동일 실험선 10-seed rerun 재현 | satisfied |
| H4. Split-robust classification | subject-level strict split에서 OS 재검증 | pending |
| H5. Preprocessing/harmonization robustness | denoising/harmonization 변화에 대한 민감도 평가 | pending |

방법론 문장(본문 삽입용):

> We frame MoBSE templates as statistical routing priors rather than causal neural pathways, and evaluate them under matched-compute constraints. We treat rerun10 reproducibility as mandatory evidence and classify strict subject-level split and preprocessing/harmonization sensitivity as required robustness tests for final claim hardening.
