#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from mobse.viz import save_multi, set_nature_style


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Fig8 nuisance 3-way comparison figure.")
    ap.add_argument(
        "--summary-csv",
        default="artifacts/current_canonical/nuisance_wave_mobse_20260331/reports/nuisance_benchmark_summary.csv",
        help="nuisance summary csv",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/current_canonical/robustness_figures_20260331_draft/reports",
        help="output directory",
    )
    ap.add_argument("--stem", default="fig_rb_nuisance_threeway_core_metrics", help="output figure stem")
    args = ap.parse_args()

    summary_csv = Path(args.summary_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_stem = out_dir / args.stem

    df = pd.read_csv(summary_csv)
    order = ["paper_compcor_gsr", "compcor_only", "gsr_only"]
    idx = [v for v in order if v in set(df["variant"].astype(str))]
    df = df.set_index("variant").loc[idx].reset_index()
    label_map = {"paper_compcor_gsr": "paper", "compcor_only": "compcor", "gsr_only": "gsr"}

    set_nature_style()
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0), constrained_layout=True)
    plots = [
        ("os_accuracy_mean", "os_accuracy_std", "OS Accuracy"),
        ("os_f1_macro_mean", "os_f1_macro_std", "OS F1-macro"),
        ("etth1_mae_mean", "etth1_mae_std", "ETTh1 MAE"),
        ("etth1_mse_mean", "etth1_mse_std", "ETTh1 MSE"),
    ]

    for ax, (m, s, title) in zip(axes.ravel(), plots):
        x = [label_map.get(v, v) for v in df["variant"].astype(str)]
        vals = df[m].astype(float).to_numpy()
        errs = df[s].astype(float).to_numpy() if s in df.columns else None
        ax.bar(x, vals, yerr=errs, capsize=3, color=["#2ca02c", "#1f77b4", "#ff7f0e"], alpha=0.9)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)

    fig.suptitle("Fig8. Nuisance sensitivity (MoBSE n100, s=10)", fontsize=10)
    save_multi(fig_stem, fig)
    plt.close(fig)

    manifest = {
        "summary_csv": str(summary_csv.resolve()),
        "figure_png": str(fig_stem.with_suffix(".png").resolve()),
        "figure_pdf": str(fig_stem.with_suffix(".pdf").resolve()),
        "script": str(Path(__file__).resolve()),
    }
    (out_dir / "figure_manifest_fig8.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
