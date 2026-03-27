# ETTh1 Story Execution Log (2026-03-27)

## Scope

Close the ETTh1 journal-story open gaps by:

1. implementing temporal bottleneck control (`mean` vs `gru`)
2. completing high-power (`10` seed) controlled runs
3. recording pairwise comparisons for manuscript use

## Code Changes

- temporal encoder config added:
  - `mobse/config.py`
- temporal control implementation:
  - `mobse/models/baselines.py` (`TransformerBaseline`, `SparseTransformerBaseline`, `StandardMoE`)
  - `mobse/models/mobse.py` (`MoBSEModel`)
- model build wiring:
  - `mobse/models/__init__.py`

New model option:

- `model.etth1_temporal_encoder: mean | gru`

## Run Matrix (All Completed, 10 Seeds Each)

1. `phase2_etth1_story_moe_n100_etth1only10_20260327`
2. `phase2_etth1_story_moe_n100_dualtask10_20260327`
3. `phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260327`
4. `phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260327`

Seed set:

- `42..51` (10 seeds)

## Core Results Snapshot

Source:

- `artifacts/etth1_story_followup_20260327/reports/story_run_summary.csv`
- `artifacts/etth1_story_followup_20260327/reports/story_pairwise_focus.csv`

### ETTh1 Means (MAE / MSE / latency ms / FLOPs)

1. ETTh1-only + mean: `2.262 / 8.658 / 0.329 / 2,960,608`
2. Dual-task + mean: `2.206 / 7.860 / 0.330 / 2,960,608`
3. ETTh1-only + GRU: `1.459 / 3.711 / 2.577 / 3,759,328`
4. Dual-task + GRU: `1.417 / 3.579 / 2.581 / 3,759,328`

### Focused Pairwise Findings

1. Dual-task vs ETTh1-only (mean, 10 paired seeds)
   - ETTh1 MSE improved: `-0.798` (`p_t=0.0186`, `p_w=0.0098`)
   - ETTh1 MAE trend improved but not significant: `-0.056` (`p_t=0.2368`)
2. GRU vs mean (ETTh1-only, 10 paired seeds)
   - ETTh1 MAE/MSE strongly improved: `-0.804 / -4.947` (both `p_t < 3e-8`)
   - latency and FLOPs increased substantially: `+2.248 ms`, `+798,720 FLOPs`
3. GRU vs mean (dual-task, 10 paired seeds)
   - ETTh1 MAE/MSE strongly improved: `-0.789 / -4.280` (both `p_t < 3e-8`)
   - latency and FLOPs increased similarly
4. Dual-task vs ETTh1-only (GRU, 10 paired seeds)
   - ETTh1 deltas small and non-significant (`MAE p_t=0.2887`, `MSE p_t=0.3687`)

## Readiness Closure

Re-audit result:

- `artifacts/journal_etth1_story_readiness_20260327/reports/readiness_manifest.json`
- status: `ready=19`, `missing=0`, `partial=0`

## Manuscript-Use Interpretation

1. Temporal bottleneck hypothesis is empirically supported:
   - removing pure mean pooling (`gru`) sharply improves ETTh1 error.
2. Efficiency trade-off is explicit and quantifiable:
   - accuracy gains come with higher latency/FLOPs.
3. Dual-task benefit depends on temporal encoder regime:
   - mean regime: meaningful MSE gain
   - GRU regime: ETTh1 gains saturate; dual-task ETTh1 advantage becomes small
