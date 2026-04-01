# ETTh1 Full-Line Rerun (10 seeds, 2026-03-31)

## Scope

- 목적: 기존 ETTh1 storyline과 추가 ETT-family 확장을 `10-seed` 기준으로 재실행
- 이유: `3-seed`는 본문 근거로 약하므로, 본문/그림 반영은 `10-seed rerun`을 기준으로 고정

## Executed Configs

Storyline 4-run (all seeds=`[42..51]`):
- `configs/2026-03-31/phase2_etth1_story_moe_n100_etth1only10_20260331_rerun.yaml`
- `configs/2026-03-31/phase2_etth1_story_moe_n100_dualtask10_20260331_rerun.yaml`
- `configs/2026-03-31/phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260331_rerun.yaml`
- `configs/2026-03-31/phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260331_rerun.yaml`

ETT-family extension 3-run (all seeds=`[42..51]`):
- `configs/2026-03-31/etth2_moe_n100_etth1only_s10_20260331_rerun.yaml`
- `configs/2026-03-31/ettm1_moe_n100_etth1only_s10_20260331_rerun.yaml`
- `configs/2026-03-31/ettm2_moe_n100_etth1only_s10_20260331_rerun.yaml`

## Main Outputs

Storyline summary/statistics:
- `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv`
- `artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv`

Storyline figures (rerun10):
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f1_hook_routing_vs_scale.png`
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f2_etth1_model_schematic.png`
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f3_temporal_bottleneck_control.png`
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f4_prior_boundary_map.png`
- `artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f5_etth1_pareto_frontier.png`

ETT-family summary (rerun10):
- `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv`
- `artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/fig_ett_family_mae_mse_s10.png`

## ETT-family Key Numbers (s=10)

| Dataset | MAE mean | MAE std | MSE mean | MSE std | Latency mean (ms) | FLOPs |
|---|---:|---:|---:|---:|---:|---:|
| ETTh1 | 2.2621 | 0.0816 | 8.6578 | 0.6706 | 0.3232 | 2,960,608 |
| ETTh2 | 5.4920 | 0.2946 | 49.2933 | 4.8958 | 0.3179 | 2,960,608 |
| ETTm1 | 1.3126 | 0.0321 | 3.1803 | 0.1143 | 0.3191 | 2,960,608 |
| ETTm2 | 4.1289 | 0.0762 | 27.1469 | 0.4090 | 0.3252 | 2,960,608 |

## Manuscript Guidance

- Results 본문은 `s=10 rerun` 수치를 주분석으로 사용.
- 이전 `s=3` 확장 결과는 부록/예비 결과로만 유지.
- ETTh1 소스는 ETDataset raw URL을 Methods에 명시:
  - `https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTh1.csv`
