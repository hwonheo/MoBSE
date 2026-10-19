# ds005270 scripts and execution state

Current scientific definitions are in `configs/ds005270/protocol_v3_qc_policy.json`.
The four completed pilot inclusions are approved with limitations. New pilot
preprocessing, QC computation, and training are **on hold**; see
`configs/ds005270/pilot_expansion_on_hold.json`. Copying scripts does not authorize execution.

- `00_reference.py`, `01_prepare_inputs.py`, `02_afni_subject.sh`,
  `03_extract_qc.py`, `04_pilot_summary.py`, `run_pilot.sh`, `build_lock.py`,
  `common.py`, and `no_snapshot_bin/` preserve the historical local AFNI pilot.
  They use `protocol_v1.json`, historical masks and coverage exclusions. Do not
  use them as the current fMRIPrep v3 runner or rerun the six completed subjects.
- `validate_adapter.py` preserves the four-subject candidate validation workflow
  and exposes tested nuisance/FD/window helpers. Its main workflow uses existing
  local evidence paths; it is not a generic cohort runner.
- `adopt_fmriprep_nuisance_v3.py` reproduces the initial v3 adoption snapshot from
  preserved arrays in a new output directory. Its output predates final inclusion
  approval and must not replace the current policy or final decisions.
- `apply_qc_policy_v2.py` preserves the earlier review-only classifier.
  `apply_qc_policy_v3.py` reproduces current scoped pilot approvals while retaining
  failure/hold decisions for missing evidence, motion, windows and FOV.

The historical v1 locks and source hash manifests remain outside the current
commit selection where they contain run-level provenance. Original artifacts
remain on disk. Scientific input definitions and completed evidence were not
rewritten to make old snapshots appear current.
