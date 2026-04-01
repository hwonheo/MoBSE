# OpenNeuro Extension Plan (2026-03-24)

## 1. Why This Track

HCP nuisance confirmation is currently blocked by raw-input availability.

The existing OpenNeuro collection code is already production-ready:

- `scripts/scan_openneuro_ds00.py`
- `mobse.cli prepare_data --mode openneuro`
- multi-dataset fallback with `--openneuro-datasets`
- multi-task fallback with `--openneuro-task "rest,restingstate"`

So the next efficient expansion is to extend the public-data cohort using the same code path.

## 2. Existing Scan Basis

Using the existing scan artifact:

- `artifacts/phase2_ds00_scan_20260314/reports/ds00_scan.csv`

top rest-like adult datasets were:

- `ds000030`: `272`
- `ds000243`: `120`
- `ds001461`: `79`
- `ds000208`: `76`
- `ds000245`: `45`

## 3. Next Extension Choice

Recommended next wave:

- `ds000030`
- `ds000243`
- `ds001461`

Reason:

- minimal change from the current two-dataset Phase-2 mainline
- extends the existing public-data mixture beyond the current setup
- estimated adult rest-like subjects: `272 + 120 + 79 = 471`

## 4. Mainline Extension Config

Prepared mainline extension config:

- `configs/2026-03-24/phase2_openneuro450_gsr_moe_n100.yaml`

Target:

- adults `450`
- `MoE n100 + gsr_only`
- same seed grid (`42-46`)
- same automated path: `prepare_data -> build_templates -> multiseed follow-up`

## 5. Launch Command

```bash
./.venv/bin/python scripts/run_prepare_build_followup.py \
  --config configs/2026-03-24/phase2_openneuro450_gsr_moe_n100.yaml \
  --mode openneuro \
  --subjects 450 \
  --min-age 18 \
  --openneuro-datasets "ds000030,ds000243,ds001461" \
  --openneuro-task "rest,restingstate" \
  --no-progress
```

## 6. Comparison Target

After the run completes, compare against the current public mainline:

- baseline reference:
  - `phase2_nuis_gsr_only_moe_n100_20260324`
- comparison command:

```bash
./.venv/bin/python scripts/compare_followup_runs.py \
  --run-a phase2_nuis_gsr_only_moe_n100_20260324 \
  --run-b phase2_openneuro450_gsr_moe_n100_20260324
```

Interpretation focus:

- whether predictive metrics hold under the broader three-dataset mixture
- whether latency/FLOPs remain aligned with the current `MoE n100 + gsr_only` mainline

## 7. 600-Subject Extension

After the `450` wave completed, the next feasible public mix for `600` subjects is:

- `ds000030`
- `ds000243`
- `ds001461`
- `ds000208`
- `ds000245`
- `ds000210`

Known adult rest-like estimate:

- `272 + 120 + 79 + 76 + 45 + 31 = 623`

Prepared config:

- `configs/2026-03-24/phase2_openneuro600_gsr_moe_n100.yaml`

Launch command:

```bash
./.venv/bin/python scripts/run_prepare_build_followup.py \
  --config configs/2026-03-24/phase2_openneuro600_gsr_moe_n100.yaml \
  --mode openneuro \
  --subjects 600 \
  --min-age 18 \
  --openneuro-datasets "ds000030,ds000243,ds001461,ds000208,ds000245,ds000210" \
  --openneuro-task "rest,restingstate" \
  --no-progress
```

Notes:

- repo-local OpenNeuro cache reuse is enabled, so previously downloaded `ds000030`, `ds000243`, and partial `ds001461` files are reused before any new download.
- current broad scan artifact:
  - `artifacts/phase2_ds_scan_20260324/reports/phase2_dataset_pick.json`
