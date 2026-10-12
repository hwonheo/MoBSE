# MoBSE

Mixture of Brain-State Experts (MoBSE) — a graph neural network that routes fMRI
time-series through dFC-derived expert sub-networks.

**The project is in redesign (v1).** The research question and evaluation target were
replaced on 2026-09-17 after a literature review and an audit of the existing
experiments. Code and results from before that date are preserved but are **not** used
as evidence for the main analysis; see [Legacy (v1)](#legacy-v1).

## Latest Status (2026-09-18)

All figures below are measured, with the producing artifact named.

- **Research question replaced.** Previously the model was trained and evaluated on dFC
  centroid pseudo-labels — a legitimate rule-approximation experiment, but not an
  independent biological validation. The primary target is now the **run identity of
  AOMIC PIOP1 `emomatching` vs `workingmemory`**, which is independent of the
  clustering. Hypotheses: H1 = gain from input-dependent routing, H2 = gain from an
  anatomically aligned brain bank; minimum effect of interest δ = 0.02 balanced
  accuracy (a design choice of this study, not a literature standard).
- **Native TR of both primary targets confirmed to be 2.0 s** (Wave 1 audit, 1,295
  runs, single-valued per task×cohort). The window design in the protocol holds without
  change.
- **BOLD acquisition complete**: 2,590 files, 209.7 GiB, 0 failures — PIOP1 and PIOP2,
  fMRIPrep derivatives in MNI152NLin2009cAsym.
- **Cohorts locked**: PIOP1 216 → **157 eligible** (pilot 31 / main 126);
  PIOP2 226 → **189 eligible** as external hold-out.
- **v2 implementation**: 16 modules, 4,114 lines. The test suite is under active
  development — as of 2026-09-18 10:30 it collects 492 tests and runs 451 pass / 26 fail
  / 17 skip locally. **All 26 failures are `ModuleNotFoundError`** (sklearn 22, scipy 2,
  torch 2): environment, not defects. Run on the analysis host for a meaningful result,
  and re-measure rather than quoting these counts.
- **Gate status** (`gate_evidence.json` revision 22): G0 Provenance
  **conditionally_cleared**; G1–G5 planned.

### ⚠️ Existing derived time-series cannot be reused

The earlier extraction applied **0.75 s to every run**, so both primary targets were
filtered at a 2.67× wrong rate. This is recorded as a failing check in gate evidence
rev 22. `data/aomic`, `data/current_canonical` and `data/legacy_*` are therefore
excluded from the main analysis. Resampling a wrongly filtered series is not a repair.

### Corrections to the 2026-04-17 status

The previous version of this section stated three things that measurement has since
contradicted. They are listed here rather than silently deleted.

| Previous claim | Measured |
| --- | --- |
| PIOP2 excluded — "short scans → insufficient dFC windows" | **Adopted as external hold-out.** emomatching 222 runs, workingmemory 224 runs, all supporting the analysis window; 189 eligible subjects |
| ds000030 selected as cross-site replication target | **Dropped** as a substitute for the primary target. PIOP2 is used as a locked cohort replication, and is deliberately *not* called cross-site (same research environment) |
| "Phase 2 dFC pipeline complete — 15,817 windows" | Those derivatives are built on the wrong TR and are unusable for the main analysis |

## Quick Start (v2)

Run on the analysis host; the pipeline requires torch, scikit-learn and scipy.

```bash
PYTHONPATH=. python -m mobse.v2.cli --help
# subcommands: validate, prepare, split, fit, evaluate, report
PYTHONPATH=. python -m pytest tests/v2 -q
```

Runtime configs are in `configs/redesign_v1/` — `main.yaml`, `pilot.yaml`,
`external.yaml`. These files **restate code constants in order to lock them**; they are
not knobs. `mobse/v2/config.py` validates each value against the corresponding module
constant and fails on mismatch, and unknown keys are rejected as typos. Every path must
be given explicitly — there is no glob fallback.

Outputs are written to `results/redesign_v1/<release_id>/` under
`provenance/ qc/ splits/ locks/ fits/ predictions/ statistics/ reports/`.
A release is never overwritten; a retry appends an attempt number.

## Scope of claims

Being the first brain-based MoE, atlas-free operation, a cognitive-load marker, and
sparse-compute superiority are **not** claims of this study. dFCExpert (IEEE TMI 45(3),
2026-03) and MoRE-Brain (NeurIPS 2025) are direct prior work. The study does not claim
to measure cognitive load ground truth, individual brain states, or causal cognitive
mechanism; sensory, motor and acquisition-order differences co-vary with task and are
stated as a limitation.

## Docs

### Current (redesign v1)

These four documents govern. Where an older note disagrees, these win.

- **Protocol v1.1** — design, hypotheses, QC and analysis rules: [docs/experiments/mobse_redesign_protocol_2026-09-17.md](docs/experiments/mobse_redesign_protocol_2026-09-17.md)
- **Work instructions v1.0** — WI-00…WI-11, module and artifact contracts: [docs/experiments/mobse_redesign_work_instructions_2026-09-17.md](docs/experiments/mobse_redesign_work_instructions_2026-09-17.md)
- **Audit of existing experiments** — what was already done and what still needs doing: [docs/experiments/mobse_existing_experiments_audit_2026-09-17.md](docs/experiments/mobse_existing_experiments_audit_2026-09-17.md)
- **Literature review** — prior work and its implications for the design: [docs/experiments/mobse_literature_review_2026-09-17.md](docs/experiments/mobse_literature_review_2026-09-17.md)
- Data acquisition plan (two waves): [docs/experiments/h197_acquisition_plan_2026-09-17.md](docs/experiments/h197_acquisition_plan_2026-09-17.md)
- Protocol figures RD1–RD4: [`docs/experiments/figures_redesign_2026-09-17/`](docs/experiments/figures_redesign_2026-09-17/)
- Changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)

### Superseded (kept for provenance)

Written before the 2026-09-17 redesign. They describe the centroid pseudo-label target
and the dataset decisions that measurement has since overturned.

- Concept note: [docs/concept/MoBSE_note.md](docs/concept/MoBSE_note.md)
- Integrated manuscript storyline (2026-04-16): [docs/manuscript_final_2026-03-31/mobse_integrated_storyline_2026-04-16.md](docs/manuscript_final_2026-03-31/mobse_integrated_storyline_2026-04-16.md)
- Phase 2 expert routing experiments (2026-04-16): [docs/experiments/phase2_expert_routing_experiments_2026-04-16.md](docs/experiments/phase2_expert_routing_experiments_2026-04-16.md)
- Phase 2 strategy pivot / dataset collection / execution strategy (2026-04-15): [`docs/experiments/`](docs/experiments/)
- ds000243 ingest, preproc and network notes (2026-04-01/02): [`docs/experiments/`](docs/experiments/)
- Archived experiment set: [`docs/experiments/archive_derived_2026-03-31/`](docs/experiments/archive_derived_2026-03-31/)

## Roadmap

### Now — redesign v1

Gate order is G0 → G5; each gate is cleared by evidence written to the release
directory, not by assertion.

1. **Resolve the G1 discrepancy.** `locks/measurement_lock.json` (00:45) records a G1
   lock while gate evidence rev 22 (08:40) still lists G1 as planned with two failing
   checks. The later evidence takes precedence; a person must reconcile these.
2. Clear the two failing G1 checks — constructing `group_id` from available metadata,
   and the PIOP1/PIOP2 subject ID namespace collision.
3. Proceed through WI-04 onward. WI-04 and WI-05 may be built in parallel once the
   interface is locked, but an integration test is required before WI-07.
4. **Commit the v2 implementation.** `mobse/v2/`, `tests/v2/` and `configs/redesign_v1/`
   are currently untracked.
5. Reflect the five added modules (cohort, config, extract, labels, locks) back into the
   protocol and work instructions, which specify only ten.

### Later — method extensions

Deferred until the main analysis reaches an internal release. Carried over from the
earlier roadmap and not yet re-derived under the current design:

- Learnable template perturbation on top of fixed brain-state priors.
- Graph mixture variants with adaptive template composition.
- Oscillatory graph dynamics (phase/frequency) with efficiency–accuracy tradeoffs.

## Legacy (v1)

Everything below documents the pre-redesign implementation. It still runs, and the
artifacts are preserved, but it is **not** evidence for the main analysis.

Measured inventory: 352 training summaries under `artifacts/`, 624 seed results, and 624
checkpoints inside those same run folders (626 `.pt` files exist overall). Already
performed: strict subject splits (ABIDE and simulation, 10 seeds
each), nuisance sensitivity across three conditions, prior/routing sweeps, four-way
baseline comparison, ds000030↔ds000243 transfer, and an ETTh1 temporal-encoder control.
**These counts are not 352 independent hypothesis tests** — they include re-runs, smoke
tests and exploratory tuning.

### v1 Quick Start

```bash
pip install -e .[dev,neuro,profile]
python -m mobse.cli build_templates --config configs/config.yaml
python -m mobse.cli train --config configs/config.yaml
python -m mobse.cli evaluate --config configs/config.yaml --checkpoint artifacts/<run_id>/checkpoints/model_seed42_best.pt
python -m mobse.cli report --config configs/config.yaml --eval-glob "artifacts/*/logs/eval_*.json"
```

### v1 Progress Tracking

- Each CLI command prints stage progress to console by default.
- Progress is also written to `artifacts/<run_id>/logs/progress_<command>.json`.
- Disable console progress with `--no-progress`.

### v1 Phase status (historical)

### Phase 1 Remaining (PoC v1 closeout)

- Re-run balanced 3-seed comparison (`42/43/44`) after nuisance-regression updates for both `100-node` and `200-node`.
- Refresh all paper-facing tables/figures (`report`) with updated mean/std and significance tests.
- Complete efficiency profiling in the same run matrix (FLOPs, peak memory, latency) and lock target hardware notes (MPS/CUDA).
- Freeze reproducibility package: final public config, run manifests, and artifact index for one-command replay.

### Phase 1 Status (2026-03-14)

- Completed: balanced 3-seed reruns for `100-node` and `200-node` on HC127 (`phase1_nr_hc127_mps100_bal3_20260314`, `phase1_nr_hc127_mps200_bal3_20260314`).
- Completed: comparison package with mean/std and paired significance table (`artifacts/phase1_nr_hc127_bal3_compare_20260314/reports/`).
- Completed: reproducibility freeze bundle (`repro_manifest.json`, run-specific resolved configs, `replay_commands.sh`).
- Note: MPS backend may report `peak_memory_mb=0` when backend telemetry is unavailable; latency/FLOPs are still reported.

### Phase 2 as of 2026-04-17 — superseded

Recorded as written. Three of these statements were later contradicted by measurement;
see [Corrections](#corrections-to-the-2026-04-17-status).

- **Template method**: dFC sliding window → k-means clustering (Allen et al. 2014) for data-driven brain-state experts. *Retained in the redesign, but the clusters are no longer the evaluation target.*
- **Primary data**: AOMIC PIOP1 (N=216, 6 tasks, complete). *The derived time-series were built on a wrong TR and are unusable.*
- ~~**Cross-site replication**: UCLA CNP ds000030~~ — dropped as a target substitute.
- **Expert collapse fixed**: differentiable masking in routing, entropy-based balance loss, gate temperature scaling. *Still valid as an implementation fix.*
- **Current best**: Exp C (routing_k=2, balance_loss_weight=1.0, gate_temperature=3.0). *Measured against centroid pseudo-labels, so it does not carry over as evidence.*
- ~~**Excluded datasets**: PIOP2 (short scans)~~ — PIOP2 is now the external hold-out with 189 eligible subjects. HCP (DUA) and AOMIC-ID1000 (no rest) remain excluded.

## Data Layout (v1)

### OS timeseries input

`build_templates` supports both node-scoped and legacy flat layouts.

Preferred (node-scoped) layout:

```text
<data.os.timeseries_dir>/
  100/
    sub-0001/
      rest.npy
      wm.npy
      motor.npy
      language.npy
      attention.npy
    sub-0002/
      ...
  200/
    sub-0001/
      ...
```

Legacy flat layout (still accepted):

```text
<data.os.timeseries_dir>/
  sub-0001/
    rest.npy
    ...
```

Each file is a 2D array shaped `[time, nodes]`.

`build_templates` resolves `<timeseries_dir>/<num_nodes>/` first, and falls back to
`<timeseries_dir>/` if the node directory does not exist.

If you have raw NIfTI files, set `data.os.nifti_manifest` (CSV with `subject_id,state,nifti_path[,confounds_path]`) and `build_templates` will parcellate with Schaefer atlas automatically.

If you want to use preprocessed ABIDE PCP images (without running local fMRIPrep), generate a manifest first:

```bash
./.venv/bin/python scripts/make_abide_pcp_manifest.py \
  --out-manifest data/abide_pcp_manifest_rest.csv \
  --data-dir data/_nilearn_cache \
  --pipeline cpac \
  --min-age 18 \
  --dx-group 2 \
  --n-subjects 300
```

Then set `data.os.nifti_manifest` to that CSV and run `build_templates`.

### One-command data preparation

- `prepare_data --mode openneuro_hc`: downloads ETTh1 and OpenNeuro dataset, applies strict HC filtering (requires diagnosis/group and age columns; defaults to `CONTROL`, `>=18`), then converts selected BOLD scans to OS-like ROI time-series.
- `prepare_data --mode openneuro`: downloads ETTh1 and OpenNeuro dataset without strict HC requirement (auto-discovers files from OpenNeuro GraphQL API). Use `--openneuro-dataset` or `--openneuro-datasets "dsA,dsB,..."`, plus `--openneuro-snapshot`, `--openneuro-task` (comma-separated allowed, e.g. `rest,restingstate`) to target/fallback across public fMRI datasets.
- `prepare_data --mode abide_control`: downloads ABIDE PCP control subjects (`DX_GROUP=2`) with `rois_cc200` or `rois_cc400`, then builds network-state variants by partitioning ROI nodes into `len(data.os.states)` clusters from group functional connectivity.
- `prepare_data --mode public_proxy`: downloads ETTh1 and nilearn development fMRI proxy dataset, then converts into OS-like per-state ROI time-series.
- `prepare_data --mode synthetic`: downloads ETTh1 and generates synthetic OS-like ROI time-series.

### Nuisance Regression (Raw fMRI -> ROI time-series)

Default config applies a paper-style denoising stack before ROI extraction:

- CompCor-like high-variance confounds (`nuisance_compcor_components`)
- Global signal regression (GSR)
- Derivative + quadratic expansion of confounds
- Temporal detrend + band-pass (`0.008-0.1Hz` by default)

Related config keys are under `data.os.nuisance_*`.

### ETTh1 input

Set `data.etth1.csv_path` to the ETTh1 CSV path.

## Outputs (v1)

All runs are written under `artifacts/<run_id>/`:

- `templates/`: serialized brain-state template bank
- `checkpoints/`: trained models
- `logs/`: metrics and profiling JSON files
- `reports/`: summary tables and publication-ready figures

## Key Ablation Switches (v1)

- `model.use_template_prior=true|false`: use fixed OS brain templates vs learned random expert graphs.
- `model.routing_mode=soft|hard`: routing policy.
- `model.routing_k=2|3`: top-k expert selection (k=num_experts disables pruning).
- `train.balance_loss_weight=0.0`: entropy-based MoE load balancing loss weight.
- `model.gate_temperature=1.0`: softmax temperature for routing logits.
- `model.arch=mobse|transformer|sparse_transformer|moe`: baseline family.
- `model.etth1_temporal_encoder=mean|gru`: ETTh1 temporal summary branch (`mean` baseline vs `GRU` control).

## Loss Stabilization (v1, dual-task)

- `train.etth1_loss_type`: `huber` (default), `mse`, or `mae`.
- `train.normalize_task_losses=true`: normalizes per-task losses by initial loss scale to avoid one task dominating.
- `train.selection_metric=weighted_normalized_loss`: uses balanced validation score for checkpoint selection.
- `train.early_stopping_patience`: stops when balanced validation score no longer improves.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

- **Hwon Heo**
- 📧 <heohwon@gmail.com>
- [<img src="https://orcid.org/sites/default/files/images/orcid_16x16.png" alt="ORCID"> ORCID 0000-0002-6103-4680](https://orcid.org/0000-0002-6103-4680)
