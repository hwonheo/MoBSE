# MoBSE Baseline TODO (2026-03-30)

## Scope Lock

- Mainline baseline: **MoBSE human network modeling with Yeo-7 base template**.
- Primary dataset axis: **ABIDE control (adult, min-age=18)**.
- Comparison axis: simulation/public-proxy is secondary and always matched to MoBSE mainline settings.

## Baseline Spec (must keep fixed unless explicitly changed)

- nodes: `200`
- states/classes: `7` (`vis,sommot,dorsattn,salventattn,limbic,cont,default`)
- experts: `7`
- train task: `os` only
- epochs: `5` (early stopping allowed)
- split seed: `42` (+ follow-up multi-seed)

Reference configs:
- `configs/2026-03-30/abide_control_cc200_mobse_adult150.yaml`
- `configs/2026-03-30/simul_public_proxy150_mobse_fair.yaml`

## Done (as of 2026-03-30)

1. ABIDE adult control run completed (`n=143`):
   - `artifacts/current_canonical/abide_control_cc200_mobse_adult150_20260330/`
2. Fair simulation run completed (`n=150`, matched compute/model settings):
   - `artifacts/current_canonical/simul_public_proxy150_mobse_fair_20260330/`
3. ABIDE vs fair simulation comparison report/figures generated:
   - `artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports/`
4. Figure style aligned with bsNet-like theme in comparison script:
   - `scripts/make_abide_vs_simul_report.py`

## P0 TODO (immediate)

1. [x] Add **Discussion limitations** section directly into comparison report markdown.
- Output: `artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports/abide_vs_simul_eval_report.md`
- Content requirement: split leakage risk, state-generation bias, cohort/site heterogeneity, preprocessing caveat.
  - Done: discussion + figure list updated in report.

2. [x] Create **paper-ready summary table** (MoBSE mainline only).
- Output: `artifacts/current_canonical/abide_mobse_mainline_20260330/reports/mobse_mainline_summary.csv`
- Columns: run_id, n_subjects, os_loss, os_acc, os_f1, routing_entropy, routing_stability, latency_ms, flops.
  - Done: summary csv + markdown + manifest generated.

3. [x] Produce **one-page narrative brief** for manuscript section draft.
- Output: `docs/experiments/mobse_mainline_discussion_2026-03-30.md`
- Must include: why MoBSE mainline (Yeo-7 base) is valid, what limitation is acknowledged, what claim is still valid.
  - Done: narrative brief added.

4. [x] Lock manuscript storyline/figure/result/discussion package.
- Output: `docs/experiments/mobse_paper_lock_2026-03-30.md`
- Figure lock dir: `artifacts/current_canonical/mobse_paper_lock_20260330/figures/`
- Manifest: `artifacts/current_canonical/mobse_paper_lock_20260330/reports/paper_lock_manifest.json`

## P1 TODO (next wave)

1. Multi-seed reproducibility on MoBSE ABIDE mainline (`seed=42,43,44`).
- New run-id prefix: `abide_control_cc200_mobse_adult150_bal3_20260330`
- Output: mean±std summary + paired stats csv.

2. Atlas robustness check (`cc200` vs `cc400`) with same MoBSE interpretation frame (Yeo-7 base).
- Goal: check direction consistency, not absolute metric maximization.

3. Subject-level split rerun (prevent window-level leakage).
- Implement explicit subject-prefix split usage in dataloader path.
- Re-evaluate headline metrics under strict split.

## P2 TODO (paper hardening)

1. Confound strategy sensitivity (none vs compcor/gsr variants) on MoBSE mainline.
2. Cross-dataset transfer sanity check (train/test dataset split where available).
3. Figure package finalization (main + supplementary mapping).

## Execution Checklist (operator)

1. Freeze config and run IDs before new run.
2. Save `prepare/train/eval/report` logs under one artifact namespace.
3. Regenerate comparison report after every new baseline run.
4. Update `docs/experiments/history_index_2026-03-26.md` with new outputs.

## Quick Commands

```bash
# fair baseline compare regeneration
.venv/bin/python scripts/make_abide_vs_simul_report.py \
  --abide-eval artifacts/current_canonical/abide_control_cc200_mobse_adult150_20260330/logs/eval_mobse.json \
  --abide-prepare artifacts/current_canonical/abide_control_cc200_mobse_adult150_20260330/logs/prepare_data.json \
  --sim-eval artifacts/current_canonical/simul_public_proxy150_mobse_fair_20260330/logs/eval_mobse.json \
  --sim-prepare artifacts/current_canonical/simul_public_proxy150_mobse_fair_20260330/logs/prepare_data.json \
  --out-dir artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports
```

```bash
# fair simulation rerun (if needed)
.venv/bin/python -m mobse.cli prepare_data --config configs/2026-03-30/simul_public_proxy150_mobse_fair.yaml --mode public_proxy --subjects 150
.venv/bin/python -m mobse.cli build_templates --config configs/2026-03-30/simul_public_proxy150_mobse_fair.yaml
.venv/bin/python -m mobse.cli train --config configs/2026-03-30/simul_public_proxy150_mobse_fair.yaml
.venv/bin/python -m mobse.cli evaluate --config configs/2026-03-30/simul_public_proxy150_mobse_fair.yaml --checkpoint artifacts/current_canonical/simul_public_proxy150_mobse_fair_20260330/checkpoints/model_seed42_best.pt
```

## Definition of Done (for this TODO file)

- P0-1, P0-2, P0-3 outputs exist and are committed in project history.
- MoBSE mainline narrative is consistent across report, figure caption, and discussion text.
- No new claim is added without matching artifact path.
