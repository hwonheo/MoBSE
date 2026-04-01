# Commit Bundle Plan (2026-04-01)

Large mixed worktree is split into smaller, reviewable bundles below.

## Bundle A: Core OS Refactor + Config Migration
- Scope:
  - `mobse/cli.py`
  - `mobse/config.py`
  - `mobse/data/__init__.py`
  - `mobse/data/prepare.py`
  - `mobse/data/os_data.py` (new)
  - `mobse/data/hcp.py` (delete)
  - `mobse/templates/builder.py`
  - `mobse/viz.py` (new)
  - config updates under:
    - `configs/2026-03-13/`
    - `configs/2026-03-23/`
    - `configs/2026-03-24/`
    - `configs/2026-03-26/`
    - `configs/2026-03-27/`
    - `configs/2026-03-30/`
    - `configs/2026-03-31/`
    - `configs/config.yaml`
    - `configs/phase2*.yaml`
- Suggested commit message:
  - `refactor(data): migrate hcp->os pipeline and align configs`

## Bundle B: Experiment Docs Archive Reorganization
- Scope:
  - deletes under `docs/experiments/*.md` (moved originals)
  - adds under `docs/experiments/archive_derived_2026-03-31/`
  - manuscript docs under `docs/manuscript_final_2026-03-31/`
- Suggested commit message:
  - `docs(experiments): archive derived notes and manuscript package`

## Bundle C: Reporting/Figure Tooling Expansion
- Scope:
  - new/updated scripts:
    - `scripts/make_abide_pcp_manifest.py`
    - `scripts/make_abide_vs_simul_report.py`
    - `scripts/make_ett_family_extension_figure.py`
    - `scripts/make_etth1_story_figures.py`
    - `scripts/make_mobse_mainline_summary.py`
    - `scripts/make_mobse_states_from_rest.py`
    - `scripts/make_mobse_storyline_figure.py`
    - `scripts/make_nuisance_threeway_figure.py`
    - `scripts/make_openneuro_usable600_figures.py`
    - `scripts/make_openneuro_usable_yield_table.py`
    - `scripts/make_strict_split_figure.py`
    - `scripts/phase2_figures.py`
    - `scripts/refresh_strict_usable_plan.py`
    - `scripts/audit_etth1_story_readiness.py`
- Suggested commit message:
  - `feat(reporting): add figure/report generators for robustness and storyline`

## Bundle D: ds000243 Ingest + Network Analysis (2026-04-01)
- Scope:
  - `configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml`
  - `scripts/analyze_template_networks.py`
  - `docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md`
  - `docs/experiments/openneuro_ds000243_network_discussion_2026-04-01.md`
  - `README.md`
  - `docs/CHANGELOG.md`
- Suggested commit message:
  - `feat(openneuro): add ds000243 rest template workflow and network discussion`

## Staging Pattern (bundle-by-bundle)
```bash
# check current staged set
git diff --cached --name-status

# stage one bundle only (example: Bundle D)
git add \
  configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml \
  scripts/analyze_template_networks.py \
  docs/experiments/openneuro_ds000243_ingest_preproc_2026-04-01.md \
  docs/experiments/openneuro_ds000243_network_discussion_2026-04-01.md \
  README.md \
  docs/CHANGELOG.md

# verify staged scope before commit
git diff --cached --name-status
```
