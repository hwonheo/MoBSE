# Submission Package Index (2026-03-31)

## Purpose

This file is the final submission-facing index for the MoBSE paper package.

- It records the final QC command for `yeo7` residue checks.
- It maps manuscript numbers to the canonical CSV tables used for the final draft.
- It lists the exact deliverable paths for the manuscript, figures, tables, and logs.

## 1) Final QC Checklist

### 1.1 `yeo7` residue check

Run:

```bash
rg -n "yeo7|YEO7|Yeo7" /Users/hwon/Documents/Git/MoBSE -S
```

Result placeholder:

- [ ] No active file paths, artifact names, or manuscript labels contain `yeo7`.
- [ ] Any remaining textual mentions are only historical/contextual references, not live naming.
- [ ] If a live residue appears, rename it before submission.

Current note for final pass:

- Historical script/doc references may still mention `Yeo7` in explanatory text.
- Final submission should keep the package naming and deliverables `MoBSE`-only.

### 1.2 Path sanity check

Run:

```bash
find /Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical -maxdepth 2 -type d | sort
```

Expected:

- Canonical story and figure directories exist under `artifacts/current_canonical`.
- No submission-facing path should reference old `yeo7` artifact names.

## 2) Number-to-CSV Mapping

Use these mappings when locking the manuscript text.

### 2.1 Main storyline tables

| Manuscript item | Canonical CSV |
|---|---|
| Storyline run summary | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv) |
| Storyline pairwise stats | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv) |
| ETT-family summary, 10 seeds | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv) |

### 2.2 Figure mapping

| Manuscript figure | Canonical path |
|---|---|
| Fig. 1 | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f1_hook_routing_vs_scale.png](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f1_hook_routing_vs_scale.png) |
| Fig. 2 | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f2_etth1_model_schematic.png](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f2_etth1_model_schematic.png) |
| Fig. 3 | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f3_temporal_bottleneck_control.png](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f3_temporal_bottleneck_control.png) |
| Fig. 4 | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f4_prior_boundary_map.png](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f4_prior_boundary_map.png) |
| Fig. 5 | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f5_etth1_pareto_frontier.png](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/fig_f5_etth1_pareto_frontier.png) |
| ETT-family extension figure | [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/fig_ett_family_mae_mse_s10.png](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/fig_ett_family_mae_mse_s10.png) |

## 3) Final Deliverables

### 3.1 Manuscript drafts

- [Abstract draft](/Users/hwon/Documents/Git/MoBSE/docs/experiments/mobse_abstract_kor_draft_2026-03-30.md)
- [Introduction literature analysis](/Users/hwon/Documents/Git/MoBSE/docs/experiments/mobse_intro_literature_doi_analysis_2026-03-30.md)
- [Results draft](/Users/hwon/Documents/Git/MoBSE/docs/experiments/mobse_results_draft_2026-03-31.md)
- [Discussion draft / lock](/Users/hwon/Documents/Git/MoBSE/docs/experiments/mobse_mainline_discussion_2026-03-30.md)
- [Paper lock](/Users/hwon/Documents/Git/MoBSE/docs/experiments/mobse_paper_lock_2026-03-30.md)

### 3.2 Submission figures

- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/mobse_paper_lock_20260330/figures/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/mobse_paper_lock_20260330/figures/)

### 3.3 Submission tables and stats

- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/abide_mobse_mainline_20260330/reports/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/abide_mobse_mainline_20260330/reports/)

### 3.4 Logs and reproducibility artifacts

- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_etth1only10_20260331_rerun/logs/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_etth1only10_20260331_rerun/logs/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_dualtask10_20260331_rerun/logs/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_dualtask10_20260331_rerun/logs/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260331_rerun/logs/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_etth1only10_temporalgru_20260331_rerun/logs/)
- [/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260331_rerun/logs/](/Users/hwon/Documents/Git/MoBSE/artifacts/current_canonical/phase2_etth1_story_moe_n100_dualtask10_temporalgru_20260331_rerun/logs/)

## 4) Final Submission Rule

- Manuscript text must cite only `rerun10` as the primary evidence line.
- `s=3` outputs remain exploratory and should not be used as headline results.
- Any leftover `yeo7` label must be removed from submission-facing filenames and manuscript prose unless it is part of an unavoidable historical note.

