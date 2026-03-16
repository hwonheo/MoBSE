from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def _fmt(mean: float, std: float) -> str:
    return f"{mean:.4f} ± {std:.4f}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build markdown report from Phase-2 outputs")
    ap.add_argument("--study-id", required=True, help="Phase-2 study id used in scripts/run_phase2.py")
    ap.add_argument(
        "--scan-pick",
        default="artifacts/phase2_ds00_scan_20260314/reports/phase2_dataset_pick.json",
        help="Path to dataset pick JSON",
    )
    ap.add_argument(
        "--out",
        default="docs/experiments/phase2_report_2026-03-14.md",
        help="Output markdown path",
    )
    args = ap.parse_args()

    summary_root = Path("artifacts") / f"{args.study_id}_summary" / "reports"
    top3_seed42 = pd.read_csv(summary_root / "phase2_top3_seed42.csv")
    bal3_summary = pd.read_csv(summary_root / "phase2_top3_bal3_summary.csv")
    bal3_seed = pd.read_csv(summary_root / "phase2_top3_bal3_seed_metrics.csv")
    manifest = json.loads((summary_root / "phase2_manifest.json").read_text(encoding="utf-8"))

    pick_payload = json.loads(Path(args.scan_pick).read_text(encoding="utf-8"))
    selected_datasets = pick_payload.get("datasets", [])
    estimated_subjects = pick_payload.get("estimated_subjects", 0)

    best = bal3_summary.iloc[0].to_dict()
    best_run = str(best["run_id"])
    best_seed_rows = bal3_seed[bal3_seed["run_id"] == best_run]

    lines = []
    lines.append("# Phase-2 Report (2026-03-14)")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Study ID: `{args.study_id}`")
    lines.append(f"- Dataset pick: `{', '.join(selected_datasets)}` (estimated adults: {estimated_subjects})")
    lines.append("")
    lines.append("## 1) Collection Setup")
    lines.append("")
    lines.append("- Task filter: `rest,restingstate`")
    lines.append("- Age filter: `>=18`")
    lines.append("- Phase-2 target: `>=300 subjects`")
    lines.append("")
    lines.append("## 2) Sweep Summary (seed=42)")
    lines.append("")
    lines.append(f"- Total sweep rows: {len(pd.read_csv(summary_root / 'phase2_sweep_seed42.csv'))}")
    lines.append("- Top-3 (seed=42):")
    for _, row in top3_seed42.iterrows():
        lines.append(
            f"  - `{row['run_id']}` | nodes={int(row['nodes'])}, sp={row['sparsity']}, "
            f"routing={row['routing_mode']}, prior={bool(row['template_prior'])}, score={row['score']:.4f}"
        )
    lines.append("")
    lines.append("## 3) Balanced 3-Seed Result (Top Config)")
    lines.append("")
    lines.append(f"- Best run: `{best_run}`")
    lines.append(f"- OS Accuracy: {_fmt(float(best['os_accuracy_mean']), float(best['os_accuracy_std']))}")
    lines.append(f"- OS F1 Macro: {_fmt(float(best['os_f1_macro_mean']), float(best['os_f1_macro_std']))}")
    lines.append(f"- ETTh1 MAE: {_fmt(float(best['etth1_mae_mean']), float(best['etth1_mae_std']))}")
    lines.append(f"- ETTh1 MSE: {_fmt(float(best['etth1_mse_mean']), float(best['etth1_mse_std']))}")
    lines.append(f"- OS latency mean (ms): {float(best['os_latency_ms_mean']):.4f}")
    lines.append(f"- ETTh1 latency mean (ms): {float(best['etth1_latency_ms_mean']):.4f}")
    lines.append("")
    lines.append("## 4) Reproducibility Artifacts")
    lines.append("")
    lines.append(f"- Manifest: `{summary_root / 'phase2_manifest.json'}`")
    lines.append(f"- Config directory: `{manifest['config_dir']}`")
    lines.append(f"- Seed metrics: `{summary_root / 'phase2_top3_bal3_seed_metrics.csv'}`")
    lines.append("")
    lines.append("## 5) Notes")
    lines.append("")
    lines.append("- `openneuro_hc` strict mode requires diagnosis/group columns in participants.tsv.")
    lines.append("- Multi-dataset fallback and task fallback are enabled (`--openneuro-datasets`, `--openneuro-task`).")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
