# Strict-Usable Execution Plan (2026-03-26)

## Scope

This plan operationalizes the three immediate goals from the history index:

1. run strict-usable pilots for `ds001747`, `ds001796`, `ds001386`, `ds001771`
2. refresh the usable-yield table with pilot evidence
3. launch full rerun only if projected strict-usable total is credibly `600+`

Reference:
- `docs/experiments/history_index_2026-03-26.md`
- `docs/experiments/openneuro_usable_plan_2026-03-24.md`

## Priority

- `P0`: strict pilot execution on the 4 candidate datasets (parallel)
- `P1`: usable-yield table refresh using observed strict QC outputs
- `P2`: decision gate for full rerun (`projected strict-usable >= 600`)

## Parallel Agent Plan

Ownership is split by dataset to avoid write conflicts.

1. Agent A: `ds001747`
2. Agent B: `ds001796`
3. Agent C: `ds001386`
4. Agent D: `ds001771`

Each agent runs:
- `prepare_data --mode openneuro`
- strict exact-`100`-node QC enabled
- image-header TR enabled
- single-dataset pilot only

Expected per-agent outputs:
- `data/os_strict_pilot_<dataset>/timeseries/openneuro_qc.csv`
- `data/os_strict_pilot_<dataset>/timeseries/openneuro_qc.json`
- `artifacts/strict_pilot_<dataset>_20260326/logs/prepare_data.json`

## Sequential Workflow

### Stage 1. Pilot Execution (Parallel)

- Start all 4 pilots concurrently.
- Record per-dataset:
  - selected/processed subject count
  - accepted count
  - rejection breakdown (`node_mismatch`, etc.)

### Stage 2. Yield Table Refresh

- Merge current base evidence with new pilot QC.
- Update:
  - `artifacts/openneuro_usable_plan_20260324/reports/openneuro_usable_yield_table.csv`
  - companion JSON/manifest if needed.

### Stage 3. Decision Gate

- If projected strict-usable total `< 600`: keep pilot/scan loop.
- If projected strict-usable total `>= 600`: approve new full rerun launch.

## Reporting Cadence

- Report at each stage transition.
- During Stage 1, report rolling pilot status by dataset (running/completed/failed).
- At Stage 2 end, report updated projected total and keep/drop/pilot recommendations.
- At Stage 3 end, report final go/no-go decision and next command set.

## Execution Update (Kickoff)

### 2026-03-26 Live Start

- Stage 1 is now running with `25-subject strict pilot` per dataset.
- Active datasets:
  - `ds001747`
  - `ds001796`
  - `ds001386`
  - `ds001771`
- Active run ids:
  - `strict_pilot_ds001747_20260326`
  - `strict_pilot_ds001796_20260326`
  - `strict_pilot_ds001386_20260326`
  - `strict_pilot_ds001771_20260326`
- Execution mode:
  - parallel sessions managed directly from the main thread
  - one process per dataset (duplicate-process collisions removed)
