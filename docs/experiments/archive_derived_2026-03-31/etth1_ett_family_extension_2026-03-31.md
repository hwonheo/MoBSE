# ETTh1 and ETT-Family Extension Log (2026-03-31)

## 1) Goal

- ETTh1 핵심 그림(F1-F5)을 현재 정리된 아티팩트 경로 기준으로 재생성
- ETTh1 재검증 + 추가 시계열(ETTh2/ETTm1/ETTm2) 테스트 실행
- 논문 본문에 넣을 수 있도록 실험 조건(시드/반복)과 수치 요약 고정

## 2) Data Source

- ETTh1 source CSV:
  - `https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTh1.csv`
- 추가 테스트 CSV:
  - `https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTh2.csv`
  - `https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTm1.csv`
  - `https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTm2.csv`

로컬 저장 경로:
- `data/reference_raw/ETTh1.csv`
- `data/reference_raw/ETT-small/ETTh2.csv`
- `data/reference_raw/ETT-small/ETTm1.csv`
- `data/reference_raw/ETT-small/ETTm2.csv`

## 3) Experimental Conditions (Explicit)

- Model: `moe` (`num_nodes=100`, `num_experts=5`, `routing_k=2`)
- Task: `tasks=[etth1]` (단일 시계열 예측)
- Training:
  - `epochs=4`
  - `batch_size=32`
  - `learning_rate=1e-3`
  - `loss=huber`
- Seeds (repeats): `3`회 (`[42, 43, 44]`)
- Device: `mps`

실행 config:
- `configs/2026-03-31/etth1_moe_n100_etth1only_s3_20260331.yaml`
- `configs/2026-03-31/etth2_moe_n100_etth1only_s3_20260331.yaml`
- `configs/2026-03-31/ettm1_moe_n100_etth1only_s3_20260331.yaml`
- `configs/2026-03-31/ettm2_moe_n100_etth1only_s3_20260331.yaml`

## 4) Generated Figures

ETTh1 storyline figures (F1-F5):
- `artifacts/current_canonical/figures_etth1_story_20260331/reports/fig_f1_hook_routing_vs_scale.png`
- `artifacts/current_canonical/figures_etth1_story_20260331/reports/fig_f2_etth1_model_schematic.png`
- `artifacts/current_canonical/figures_etth1_story_20260331/reports/fig_f3_temporal_bottleneck_control.png`
- `artifacts/current_canonical/figures_etth1_story_20260331/reports/fig_f4_prior_boundary_map.png`
- `artifacts/current_canonical/figures_etth1_story_20260331/reports/fig_f5_etth1_pareto_frontier.png`

ETT-family extension figure:
- `artifacts/current_canonical/ett_family_extension_20260331/reports/fig_ett_family_mae_mse_s3.png`

## 5) Key Results (s=3)

요약 파일:
- `artifacts/current_canonical/ett_family_extension_20260331/reports/ett_family_summary_s3.csv`

| Dataset | MAE mean | MAE std | MSE mean | MSE std | Latency mean (ms) | FLOPs |
|---|---:|---:|---:|---:|---:|---:|
| ETTh1 | 2.1744 | 0.0462 | 8.1966 | 0.3323 | 0.3248 | 2,960,608 |
| ETTh2 | 5.3991 | 0.0709 | 47.6898 | 2.0062 | 0.3433 | 2,960,608 |
| ETTm1 | 1.3060 | 0.0264 | 3.1910 | 0.1064 | 0.3338 | 2,960,608 |
| ETTm2 | 4.1037 | 0.0624 | 27.0113 | 0.2970 | 0.3345 | 2,960,608 |

## 6) Manuscript Insert Note

- 본문 Methods에는 ETTh1 원본 소스 URL(ETDataset GitHub raw)과 실험 반복 조건(`seeds=[42,43,44]`, `repeats=3`)을 명시.
- 본문 Results에는 ETTh1 핵심 패널(F1-F5)과 함께 ETT-family 확장 결과를 "generalization check (small-scale, s=3)"로 별도 단락에 분리 기재.
- 10-seed 주분석(기존 ETTh1 storyline)과 3-seed 확장분석(ETT-family)을 구분해 기술.
