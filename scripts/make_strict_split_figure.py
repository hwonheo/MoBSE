#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from mobse.viz import save_multi, set_nature_style


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Fig7 strict split ABIDE vs simulation summary figure.")
    ap.add_argument(
        "--summary-csv",
        default="artifacts/current_canonical/strict_split_wave_20260331/reports/strict_split_summary.csv",
        help="strict split summary csv",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/current_canonical/robustness_figures_20260331_draft/reports",
        help="output directory",
    )
    ap.add_argument("--stem", default="fig_ra_strict_split_abide_vs_simul", help="output figure stem")
    args = ap.parse_args()

    summary_csv = Path(args.summary_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_stem = out_dir / args.stem

    df = pd.read_csv(summary_csv).set_index("variant")
    needed = ["abide_strict", "simul_strict"]
    for k in needed:
        if k not in df.index:
            raise ValueError(f"Missing variant in summary csv: {k}")

    set_nature_style()
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0), constrained_layout=True)
    metrics = [
        ("os_accuracy_mean", "os_accuracy_std", "Accuracy"),
        ("os_f1_macro_mean", "os_f1_macro_std", "F1-macro"),
        ("os_loss_mean", "os_loss_std", "Loss"),
        ("os_latency_ms_mean", None, "Latency (ms)"),
    ]

    for ax, (m, s, title) in zip(axes.ravel(), metrics):
        vals = [float(df.loc["abide_strict", m]), float(df.loc["simul_strict", m])]
        errs = None
        if s is not None and s in df.columns:
            errs = [float(df.loc["abide_strict", s]), float(df.loc["simul_strict", s])]
        ax.bar(["ABIDE", "Simulation"], vals, yerr=errs, capsize=3, color=["#1f77b4", "#d62728"], alpha=0.9)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)

    fig.suptitle("Fig7. Strict split ABIDE vs Simulation (s=10)", fontsize=10)
    save_multi(fig_stem, fig)
    plt.close(fig)

    manifest = {
        "summary_csv": str(summary_csv.resolve()),
        "figure_png": str(fig_stem.with_suffix(".png").resolve()),
        "figure_pdf": str(fig_stem.with_suffix(".pdf").resolve()),
        "script": str(Path(__file__).resolve()),
    }
    (out_dir / "figure_manifest_fig7.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
