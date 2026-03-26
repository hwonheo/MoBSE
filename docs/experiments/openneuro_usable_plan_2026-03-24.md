# OpenNeuro Strict-Usable Plan (2026-03-24)

## 1. Goal Reset

The target is no longer raw BOLD `N`.

The target is:

- `strict usable subjects`
- exact `100-node` extraction
- image-header TR applied per subject
- rejected subjects excluded before template/window generation

## 2. Current Finding

The previous `600` raw collection does **not** equal `600` usable subjects.

Observed strict usable counts from the current `600` wave:

- `ds000030`: `218 / 268`
- `ds000243`: `115 / 120`
- `ds001461`: `49 / 79`
- `ds000208`: `5 / 76`
- `ds000245`: `45 / 45`
- `ds000210`: `11 / 12`

This means the current six-dataset mix yields only `443` observed strict-usable subjects.

## 3. Planning Artifact

Auto-generated planning table:

- `artifacts/openneuro_usable_plan_20260324/reports/openneuro_usable_yield_table.csv`
- current projected strict-usable total for initial `keep` set: `458`

This table should be treated as the source of truth for:

- keep / drop / pilot-more decisions
- projected strict-usable totals
- next collector dataset order

## 4. Dataset Policy

Initial policy under strict mode:

- `keep`:
  - `ds000030`
  - `ds000243`
  - `ds001461`
  - `ds000245`
  - `ds000210`
- `drop` or de-prioritize:
  - `ds000208`
- `pilot_more`:
  - `ds000172`
  - any new dataset without strict usable evidence

Current implication:

- the current `keep` set is still insufficient for a true `usable 600` target
- at least one or more additional pilot datasets are required before a full rerun

## 5. Collector Redesign

The collector should stop on `accepted usable subjects`, not raw downloads.

Required behavior:

1. dataset order follows projected strict-usable yield
2. collection runs in small chunks
3. each chunk performs:
   - select subjects
   - download/reuse raw files
   - extract with image-header TR
   - apply exact-node QC
   - update accepted total
4. stop when `accepted_total >= target_usable_subjects`

## 6. Next Implementation Steps

1. add a `usable_target_subjects` concept to OpenNeuro collection
2. add chunked dataset collection (`dataset_chunk_size`)
3. use strict usable yield table to seed dataset order
4. run pilot collection on `ds000172` and any newly scanned candidate
5. launch a new full run only after projected strict-usable total is credible

## 7. 2026-03-26 Update

Collector redesign is now implemented under strict mode.

- `usable_target_subjects` and `dataset_chunk_size` are wired into OpenNeuro collection
- the collector now stops on accepted usable subjects, not raw download count
- strict exact-`100`-node QC remains the acceptance gate

New evidence since the initial plan:

- `ds000172` strict pilot failed:
  - `13` QC rows
  - `0` accepted
  - all failures were `node_mismatch`
- `250`-dataset broad scan found additional raw rest-like adult candidates, but this is still a raw-count signal, not a usable-count guarantee
  - strongest new pilot candidates: `ds001747`, `ds001796`, `ds001386`, `ds001771`
  - broad-scan estimated raw adult total across the selected set: `877`

Updated implication:

- `ds000172` should move from `pilot_more` to `drop`
- the next gating step is not a full `usable 600` rerun
- the next gating step is strict usable pilot collection on the new scan candidates above
