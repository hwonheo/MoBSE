#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mobse.viz import save_multi, set_nature_style


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Fig6 ETT-family extension figure from summary CSV.")
    ap.add_argument(
        "--summary-csv",
        default="artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv",
        help="ETT-family summary csv",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports",
        help="output directory",
    )
    ap.add_argument("--stem", default="fig_ett_family_mae_mse_s10", help="output figure stem")
    args = ap.parse_args()

    summary_csv = Path(args.summary_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_stem = out_dir / args.stem

    df = pd.read_csv(summary_csv)
    if df.empty:
        raise ValueError(f"No rows in summary csv: {summary_csv}")

    order = ["ETTh1", "ETTh2", "ETTm1", "ETTm2"]
    present = [d for d in order if d in set(df["dataset"].astype(str))]
    rest = [d for d in df["dataset"].astype(str).tolist() if d not in present]
    plot_order = present + rest
    df = df.set_index("dataset").loc[plot_order].reset_index()

    set_nature_style()
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5))

    x = np.arange(len(df))
    mae = df["mae_mean"].astype(float).to_numpy()
    mae_std = df.get("mae_std", pd.Series([0.0] * len(df))).astype(float).to_numpy()
    mse = df["mse_mean"].astype(float).to_numpy()
    mse_std = df.get("mse_std", pd.Series([0.0] * len(df))).astype(float).to_numpy()

    axes[0].errorbar(x, mae, yerr=mae_std, fmt="o", color="#059669", 
                     ecolor="#A7F3D0", elinewidth=2.5, capsize=0, markersize=10, 
                     markeredgecolor="#047857", lw=1.5, zorder=3)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(df["dataset"].astype(str).tolist(), fontweight="bold", fontsize=10, color="#1F2937")
    axes[0].set_title("a. ETT-family Domain MAE", fontsize=11, fontweight="bold", loc="left", color="#111827", pad=12)
    axes[0].set_ylabel("MAE (lower is better)", fontsize=9, color="#4B5563")
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)
    axes[0].spines["left"].set_visible(False)
    axes[0].grid(axis="y", color="#E5E7EB", linestyle="--", alpha=0.7, zorder=1)
    for idx, (bx, by) in enumerate(zip(x, mae)):
        axes[0].text(bx, by + mae_std[idx] + 0.015, f"{by:.3f}", ha="center", va="bottom", fontsize=9, color="#064E3B", fontweight="bold")

    axes[1].errorbar(x, mse, yerr=mse_std, fmt="s", color="#D97706", 
                     ecolor="#FDE68A", elinewidth=2.5, capsize=0, markersize=10, 
                     markeredgecolor="#B45309", lw=1.5, zorder=3)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["dataset"].astype(str).tolist(), fontweight="bold", fontsize=10, color="#1F2937")
    axes[1].set_title("b. ETT-family Domain MSE", fontsize=11, fontweight="bold", loc="left", color="#111827", pad=12)
    axes[1].set_ylabel("MSE (lower is better)", fontsize=9, color="#4B5563")
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)
    axes[1].spines["left"].set_visible(False)
    axes[1].grid(axis="y", color="#E5E7EB", linestyle="--", alpha=0.7, zorder=1)
    for idx, (bx, by) in enumerate(zip(x, mse)):
        axes[1].text(bx, by + mse_std[idx] + 0.015, f"{by:.3f}", ha="center", va="bottom", fontsize=9, color="#92400E", fontweight="bold")

    fig.suptitle("Figure 6: ETT-family Robustness (10 Seeds)", fontsize=13, fontweight="bold", y=0.98, color="#111827")
    plt.subplots_adjust(top=0.85, bottom=0.20, left=0.15, right=0.95, wspace=0.3)
    save_multi(fig_stem, fig)
    plt.close(fig)

    manifest = {
        "summary_csv": str(summary_csv.resolve()),
        "figure_png": str(fig_stem.with_suffix(".png").resolve()),
        "figure_pdf": str(fig_stem.with_suffix(".pdf").resolve()),
        "script": str(Path(__file__).resolve()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
