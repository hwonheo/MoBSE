# ETTh1 Journal Readiness Audit (2026-03-27)

## Purpose

Before advancing the ETTh1-centered journal storyline, verify that related experiments and raw data are actually prepared, and record the verification process reproducibly.

## Audit Method

Automated audit script:

- `scripts/audit_etth1_story_readiness.py`

Executed command:

```bash
./.venv/bin/python scripts/audit_etth1_story_readiness.py
```

Generated audit artifacts:

- `artifacts/journal_etth1_story_readiness_20260327/reports/readiness_items.csv`
- `artifacts/journal_etth1_story_readiness_20260327/reports/readiness_manifest.json`

Raw ETTh1 checksum:

- `data/ETTh1.csv` sha256:
  - `f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066`

## Audit Result Snapshot

- total items checked: `19`
- `ready`: `19`
- `missing`: `0`
- `partial`: `0`

## Ready (Key Evidence)

1. Theory/modeling basis docs exist:
   - `docs/concept/MoBSE_note.md`
   - `docs/experiments/phase2_report_2026-03-14.md`
   - `docs/experiments/baseline_benchmark_2026-03-23.md`
2. ETTh1 raw data + core code exist:
   - `data/ETTh1.csv`
   - `mobse/data/etth1.py`
   - `mobse/models/mobse.py`
   - `mobse/train.py`
3. Core ablation/benchmark artifacts exist:
   - `phase2_sweep_seed42.csv` (`n100`, `n200`)
   - `phase2_best_vs_best...csv`
   - `baseline_benchmark_summary.csv`
   - `phase2_figures_manifest.json`
4. Prior on/off coverage is present in sweep artifacts (both `True` and `False` in `n100`/`n200`).
5. Loss stabilization evidence exists in before/after training logs.
6. ETTh1-only control is prepared and executed at `10` seeds.
7. Temporal bottleneck control is implemented (`mean` vs `gru`) and executed at `10` seeds.
8. High-power (`>=10` seed) ETTh1 raw-metrics evidence is now present.

## Previously Missing Items (Now Closed)

1. Temporal bottleneck control
   - implemented in model code with `etth1_temporal_encoder: mean|gru`
   - key files:
     - `mobse/config.py`
     - `mobse/models/baselines.py`
     - `mobse/models/mobse.py`
     - `mobse/models/__init__.py`
2. High-power (`>=10` seed) ETTh1 evidence
   - completed run artifacts include `10` seeds in `raw_metrics.csv`
   - representative run:
     - `phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260327`

## Executed Runs (2026-03-27)

Executed via launcher:

- `scripts/run_multiseed_followup.py`

```bash
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-27/phase2_etth1_story_moe_n100_etth1only10_20260327.yaml --no-progress
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-27/phase2_etth1_story_moe_n100_dualtask10_20260327.yaml --no-progress
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-27/phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260327.yaml --no-progress
./.venv/bin/python scripts/run_multiseed_followup.py --config configs/2026-03-27/phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260327.yaml --no-progress
```

Comparison artifacts generated:

- `artifacts/phase2_etth1_story_moe_n100_dualtask10_20260327__vs__phase2_etth1_story_moe_n100_etth1only10_20260327/reports/followup_paired_stats.csv`
- `artifacts/phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260327__vs__phase2_etth1_story_moe_n100_etth1only10_20260327/reports/followup_paired_stats.csv`
- `artifacts/phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260327__vs__phase2_etth1_story_moe_n100_dualtask10_20260327/reports/followup_paired_stats.csv`
- `artifacts/phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260327__vs__phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260327/reports/followup_paired_stats.csv`

## Journal Writing Rule (Current)

- ETTh1 storyline drafting is now supported with full readiness coverage (`19/19 ready`).
- keep claim boundaries explicit:
  - supported: high-power seed evidence for `dual-task vs etth1-only` and `mean vs gru` controls
  - still pending: causal universality of brain-template prior across broader datasets/regimes
