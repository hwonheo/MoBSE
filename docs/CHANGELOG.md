# Changelog

## 2026-03-13 (Roadmap Update)

### Added
- Concept-aligned execution roadmap in `README.md` with explicit Phase 1/2/3 scope.
- Phase-1 closeout checklist for the current PoC line (post-regression balanced 3-seed rerun, report refresh, efficiency profiling, reproducibility freeze).
- Phase-2 HCP-scale validation plan (`150-250` subjects first, then expanded ablations).
- Phase-3 method-extension plan (learnable template perturbation, graph mixture, oscillatory dynamics).

### Changed
- Project planning baseline is now explicitly split between public-proxy PoC completion criteria and HCP-target full-claim validation criteria.

### Fixed
- Documentation ambiguity between "implemented now" and "planned next" by separating completed Phase-1 results from remaining and future phases.

## 2026-03-13 (Phase 1)

Source summary: [`docs/experiments/experiments_note_2026-03-13.md`](experiments/experiments_note_2026-03-13.md)

### Added
- Nuisance-regression pipeline for raw fMRI to ROI extraction (CompCor-like high-variance confounds, GSR, derivative/quadratic expansion, detrend + band-pass `0.008-0.1Hz`).
- Configurable ETTh1 loss options (`huber|mse|mae`, default `huber`).
- Task-loss normalization, balanced checkpoint selection (`weighted_normalized_loss`), and early stopping in dual-task training.

### Changed
- Naming refactor from `hcp_*` to `os_*` with backward-compatible aliases.
- End-to-end CLI flow (`prepare_data`, `build_templates`, `train`, `evaluate`, `report`) and progress logging standardization.

### Fixed
- OpenNeuro indexing bottleneck by scanning `participants.tsv` first and restricting recursive traversal to selected subjects.
- Cross-run artifact contamination by prioritizing current `run_id` templates/windows before glob fallback.

### Experiment Snapshot
- HC127 balanced 3-seed comparison completed for 100-node vs 200-node.
- 100-node showed better OS classification mean performance; 200-node showed larger variance in ETTh1 metrics.
- Nuisance-regression re-check completed on `ds000030` (`openneuro_hc`) with data-quality validation artifacts saved.
