from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch


def _label(regime: str, temporal: str) -> str:
    left = "dual" if regime == "dual_task" else "etth1-only"
    return f"{left}-{temporal}"


def _load_pairwise_pvals(pairwise_df: pd.DataFrame) -> Dict[Tuple[str, str], float]:
    out: Dict[Tuple[str, str], float] = {}
    for _, row in pairwise_df.iterrows():
        out[(str(row["comparison"]), str(row["metric"]))] = float(row["ttest_rel_p"])
    return out


def _add_box(ax, x: float, y: float, w: float, h: float, text: str, face: str = "#F3F4F6") -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.015,rounding_size=0.02",
        linewidth=1.2,
        edgecolor="#334155",
        facecolor=face,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)


def _figure_f1(summary_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.02,
        0.95,
        "F1. Hook: Routing, Not Scale",
        fontsize=16,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax.text(
        0.02,
        0.90,
        "Can we improve ETTh1 accuracy through routing design, not brute-force scaling?",
        fontsize=10,
        ha="left",
        va="top",
        color="#334155",
    )

    mean_df = summary_df[summary_df["temporal_encoder"] == "mean"]
    gru_df = summary_df[summary_df["temporal_encoder"] == "gru"]
    mean_mae = float(mean_df["etth1_mae_mean"].mean()) if not mean_df.empty else float("nan")
    gru_mae = float(gru_df["etth1_mae_mean"].mean()) if not gru_df.empty else float("nan")
    mean_lat = float(mean_df["etth1_latency_ms_mean"].mean()) if not mean_df.empty else float("nan")
    gru_lat = float(gru_df["etth1_latency_ms_mean"].mean()) if not gru_df.empty else float("nan")
    mean_flops = float(mean_df["etth1_flops_mean"].mean()) if not mean_df.empty else float("nan")
    gru_flops = float(gru_df["etth1_flops_mean"].mean()) if not gru_df.empty else float("nan")

    # Left card: dense all-to-all.
    _add_box(ax, 0.03, 0.22, 0.42, 0.60, "", face="#F8FAFC")
    ax.text(0.05, 0.79, "Dense Scaling Path", fontsize=12, fontweight="bold", ha="left", color="#0F172A")
    ax.text(0.05, 0.74, "All-to-all communication\nHigh global interaction cost", fontsize=9.5, ha="left", va="top", color="#334155")

    left_center = (0.24, 0.48)
    radius = 0.13
    points = []
    for i in range(10):
        theta = 2.0 * 3.1415926535 * i / 10.0
        x = left_center[0] + radius * float(math.cos(theta))
        y = left_center[1] + radius * float(math.sin(theta))
        points.append((x, y))
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            ax.plot(
                [points[i][0], points[j][0]],
                [points[i][1], points[j][1]],
                color="#CBD5E1",
                linewidth=0.7,
                alpha=0.45,
            )
    for x, y in points:
        ax.add_patch(Circle((x, y), 0.0105, facecolor="#2563EB", edgecolor="white", linewidth=0.9))
    _add_box(ax, 0.08, 0.26, 0.31, 0.08, r"Complexity proxy: O(N^2)", face="#EFF6FF")

    # Right card: routed experts.
    _add_box(ax, 0.52, 0.22, 0.45, 0.60, "", face="#F8FAFC")
    ax.text(0.54, 0.79, "Routing-Centric Path", fontsize=12, fontweight="bold", ha="left", color="#0F172A")
    ax.text(0.54, 0.74, "Task-dependent sparse expert usage\nLower active compute budget", fontsize=9.5, ha="left", va="top", color="#334155")

    _add_box(ax, 0.56, 0.58, 0.10, 0.08, "Input", face="#DBEAFE")
    _add_box(ax, 0.69, 0.58, 0.09, 0.08, "Gate", face="#E2E8F0")
    _add_box(ax, 0.81, 0.69, 0.13, 0.07, "Expert A", face="#DCFCE7")
    _add_box(ax, 0.81, 0.58, 0.13, 0.07, "Expert B", face="#FDE68A")
    _add_box(ax, 0.81, 0.47, 0.13, 0.07, "Expert C", face="#FECACA")
    _add_box(ax, 0.81, 0.33, 0.13, 0.08, "Forecast", face="#E9D5FF")

    ax.add_patch(FancyArrowPatch((0.66, 0.62), (0.69, 0.62), arrowstyle="->", mutation_scale=10, linewidth=1.2, color="#1E293B"))
    ax.add_patch(FancyArrowPatch((0.78, 0.62), (0.81, 0.72), arrowstyle="->", mutation_scale=10, linewidth=2.0, color="#1E293B"))
    ax.add_patch(FancyArrowPatch((0.78, 0.62), (0.81, 0.615), arrowstyle="->", mutation_scale=10, linewidth=1.6, color="#1E293B"))
    ax.add_patch(FancyArrowPatch((0.78, 0.62), (0.81, 0.505), arrowstyle="->", mutation_scale=10, linewidth=0.9, color="#1E293B"))
    ax.add_patch(FancyArrowPatch((0.94, 0.73), (0.94, 0.37), arrowstyle="->", mutation_scale=10, linewidth=1.0, color="#1E293B"))
    ax.add_patch(FancyArrowPatch((0.94, 0.62), (0.94, 0.37), arrowstyle="->", mutation_scale=10, linewidth=1.0, color="#1E293B"))
    ax.add_patch(FancyArrowPatch((0.94, 0.51), (0.94, 0.37), arrowstyle="->", mutation_scale=10, linewidth=1.0, color="#1E293B"))

    _add_box(ax, 0.54, 0.25, 0.40, 0.12, r"Complexity proxy: O(k*N) with k << N", face="#ECFDF5")

    _add_box(
        ax,
        0.03,
        0.04,
        0.94,
        0.13,
        (
            f"Observed (10-seed means): MAE {mean_mae:.3f} -> {gru_mae:.3f} (mean -> GRU), "
            f"latency {mean_lat:.3f}ms -> {gru_lat:.3f}ms, FLOPs {mean_flops:,.0f} -> {gru_flops:,.0f}"
        ),
        face="#FFFBEB",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def _figure_f2(summary_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.02, 0.95, "F2. ETTh1 Modeling Pipeline and Control Branches", fontsize=16, fontweight="bold", ha="left", va="top")

    y = 0.64
    h = 0.11
    w = 0.125
    xs = [0.03, 0.17, 0.31, 0.45, 0.59, 0.73]
    labels = [
        "ETTh1 Window\nX in R^(Txd)",
        "Temporal\nEncoder",
        "Node Projection\nZ in R^(N x H)",
        "Top-k Router\ng=softmax(MLP)",
        "Expert Mix\nA=sum g_e T_e",
        "Forecast Head\ny_hat",
    ]
    faces = ["#DBEAFE", "#E2E8F0", "#F8FAFC", "#F8FAFC", "#DCFCE7", "#E9D5FF"]
    for x, lab, face in zip(xs, labels, faces):
        _add_box(ax, x, y, w, h, lab, face=face)
    for i in range(len(xs) - 1):
        ax.add_patch(
            FancyArrowPatch(
                (xs[i] + w, y + h / 2),
                (xs[i + 1], y + h / 2),
                arrowstyle="->",
                mutation_scale=11,
                linewidth=1.3,
                color="#334155",
            )
        )

    _add_box(ax, 0.03, 0.33, 0.30, 0.12, r"Eq(1)  p = mean_t(X_t)  or  p = GRU_last(X)", face="#F8FAFC")
    _add_box(ax, 0.35, 0.33, 0.30, 0.12, r"Eq(2)  Z = reshape(Wp, N, H) | Eq(3)  A = sum g_e T_e", face="#F8FAFC")
    _add_box(ax, 0.67, 0.33, 0.30, 0.12, r"Eq(4)  y_hat = W_pred * pool(GraphOut)", face="#F8FAFC")

    mean_df = summary_df[summary_df["temporal_encoder"] == "mean"]
    gru_df = summary_df[summary_df["temporal_encoder"] == "gru"]
    mean_mae = float(mean_df["etth1_mae_mean"].mean()) if not mean_df.empty else float("nan")
    gru_mae = float(gru_df["etth1_mae_mean"].mean()) if not gru_df.empty else float("nan")
    mean_lat = float(mean_df["etth1_latency_ms_mean"].mean()) if not mean_df.empty else float("nan")
    gru_lat = float(gru_df["etth1_latency_ms_mean"].mean()) if not gru_df.empty else float("nan")

    _add_box(ax, 0.03, 0.17, 0.46, 0.11, f"Baseline branch (mean): MAE={mean_mae:.3f}, latency={mean_lat:.3f} ms", face="#EFF6FF")
    _add_box(ax, 0.51, 0.17, 0.46, 0.11, f"Control branch (GRU): MAE={gru_mae:.3f}, latency={gru_lat:.3f} ms", face="#ECFDF5")
    ax.text(
        0.03,
        0.10,
        "Control axes: temporal encoder (mean vs GRU) and task regime (ETTh1-only vs dual-task), both validated with 10-seed runs.",
        fontsize=9.8,
        ha="left",
        va="center",
        color="#334155",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def _figure_f3(summary_df: pd.DataFrame, pairwise_df: pd.DataFrame, out_path: Path) -> None:
    pvals = _load_pairwise_pvals(pairwise_df)
    data = summary_df.copy()
    data["regime_plot"] = data["regime"].map({"etth1_only": "ETTh1-only", "dual_task": "Dual-task"})
    data["temporal_plot"] = data["temporal_encoder"].str.upper()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    sns.barplot(
        data=data,
        x="regime_plot",
        y="etth1_mae_mean",
        hue="temporal_plot",
        ax=axes[0],
        palette=["#4C78A8", "#F58518"],
        errorbar=None,
    )
    sns.barplot(
        data=data,
        x="regime_plot",
        y="etth1_mse_mean",
        hue="temporal_plot",
        ax=axes[1],
        palette=["#4C78A8", "#F58518"],
        errorbar=None,
    )
    axes[0].set_title("F3a. ETTh1 MAE by Temporal Control")
    axes[0].set_ylabel("MAE (lower is better)")
    axes[0].set_xlabel("")
    axes[1].set_title("F3b. ETTh1 MSE by Temporal Control")
    axes[1].set_ylabel("MSE (lower is better)")
    axes[1].set_xlabel("")

    mae_et = pvals.get(("gru_minus_mean_etth1only", "metric_mae"), float("nan"))
    mae_dual = pvals.get(("gru_minus_mean_dualtask", "metric_mae"), float("nan"))
    mse_et = pvals.get(("gru_minus_mean_etth1only", "metric_mse"), float("nan"))
    mse_dual = pvals.get(("gru_minus_mean_dualtask", "metric_mse"), float("nan"))

    axes[0].text(
        0.02,
        0.98,
        f"p_t (ETTh1-only): {mae_et:.2e}\np_t (Dual-task): {mae_dual:.2e}",
        transform=axes[0].transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.75, edgecolor="none"),
    )
    axes[1].text(
        0.02,
        0.98,
        f"p_t (ETTh1-only): {mse_et:.2e}\np_t (Dual-task): {mse_dual:.2e}",
        transform=axes[1].transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.75, edgecolor="none"),
    )

    handles, labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles, labels, title="Temporal")
    axes[1].get_legend().remove()
    fig.suptitle("F3. Temporal Bottleneck Control (10 Seeds)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def _figure_f4(sweep_n100: pd.DataFrame, sweep_n200: pd.DataFrame, out_path: Path) -> None:
    sweep = pd.concat([sweep_n100, sweep_n200], ignore_index=True)
    grouped = (
        sweep.groupby(["nodes", "sparsity", "routing_mode", "template_prior"], as_index=False)["etth1_mse"]
        .mean()
        .reset_index(drop=True)
    )

    nodes_sorted = sorted(grouped["nodes"].unique().tolist())
    fig, axes = plt.subplots(1, len(nodes_sorted), figsize=(6.2 * len(nodes_sorted), 4.8))
    if len(nodes_sorted) == 1:
        axes = [axes]

    for idx, nodes in enumerate(nodes_sorted):
        ax = axes[idx]
        sub = grouped[grouped["nodes"] == nodes]
        pivot = (
            sub.pivot_table(
                index=["routing_mode", "sparsity"],
                columns="template_prior",
                values="etth1_mse",
                aggfunc="mean",
            )
            .rename(columns={True: "prior_true", False: "prior_false"})
            .reset_index()
        )
        if "prior_true" not in pivot.columns:
            pivot["prior_true"] = float("nan")
        if "prior_false" not in pivot.columns:
            pivot["prior_false"] = float("nan")
        pivot["delta_true_minus_false"] = pivot["prior_true"] - pivot["prior_false"]

        heat = pivot.pivot(index="routing_mode", columns="sparsity", values="delta_true_minus_false")
        sns.heatmap(
            heat,
            cmap="RdBu_r",
            center=0.0,
            annot=True,
            fmt=".3f",
            cbar=(idx == len(nodes_sorted) - 1),
            ax=ax,
        )
        ax.set_title(f"nodes={nodes}")
        ax.set_xlabel("sparsity")
        ax.set_ylabel("routing")

    fig.suptitle("F4. Prior Effect Map (ETTh1 MSE, prior_true - prior_false)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def _figure_f5(summary_df: pd.DataFrame, out_path: Path) -> None:
    data = summary_df.copy()
    data["label"] = data.apply(lambda r: _label(str(r["regime"]), str(r["temporal_encoder"])), axis=1)
    data["regime_plot"] = data["regime"].map({"etth1_only": "ETTh1-only", "dual_task": "Dual-task"})
    data["temporal_plot"] = data["temporal_encoder"].str.upper()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    sns.scatterplot(
        data=data,
        x="etth1_latency_ms_mean",
        y="etth1_mae_mean",
        hue="temporal_plot",
        style="regime_plot",
        s=140,
        ax=axes[0],
        palette=["#4C78A8", "#F58518"],
    )
    sns.scatterplot(
        data=data,
        x="etth1_flops_mean",
        y="etth1_mae_mean",
        hue="temporal_plot",
        style="regime_plot",
        s=140,
        ax=axes[1],
        palette=["#4C78A8", "#F58518"],
    )

    for _, row in data.iterrows():
        axes[0].annotate(str(row["label"]), (row["etth1_latency_ms_mean"], row["etth1_mae_mean"]), fontsize=8)
        axes[1].annotate(str(row["label"]), (row["etth1_flops_mean"], row["etth1_mae_mean"]), fontsize=8)

    for regime in ["etth1_only", "dual_task"]:
        sub = data[data["regime"] == regime].sort_values("temporal_encoder")
        if len(sub) == 2:
            axes[0].plot(sub["etth1_latency_ms_mean"], sub["etth1_mae_mean"], color="#9C755F", alpha=0.7)
            axes[1].plot(sub["etth1_flops_mean"], sub["etth1_mae_mean"], color="#9C755F", alpha=0.7)

    axes[0].set_title("F5a. MAE vs Latency")
    axes[0].set_xlabel("ETTh1 latency (ms)")
    axes[0].set_ylabel("ETTh1 MAE")
    axes[1].set_title("F5b. MAE vs FLOPs")
    axes[1].set_xlabel("ETTh1 FLOPs")
    axes[1].set_ylabel("ETTh1 MAE")

    handles, labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles, labels, title="Legend")
    axes[1].get_legend().remove()
    fig.suptitle("F5. ETTh1 Pareto Frontier (10-Seed Means)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    fig.savefig(out_path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ETTh1 story figures (F1/F2/F3/F4/F5)")
    ap.add_argument(
        "--summary-csv",
        default="artifacts/etth1_story_followup_20260327/reports/story_run_summary.csv",
        help="Run summary CSV path",
    )
    ap.add_argument(
        "--pairwise-csv",
        default="artifacts/etth1_story_followup_20260327/reports/story_pairwise_focus.csv",
        help="Pairwise stats CSV path",
    )
    ap.add_argument(
        "--sweep-n100",
        default="artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv",
        help="n100 sweep CSV path",
    )
    ap.add_argument(
        "--sweep-n200",
        default="artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_sweep_seed42.csv",
        help="n200 sweep CSV path",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/figures_etth1_story_20260327/reports",
        help="Output directory",
    )
    args = ap.parse_args()

    sns.set_theme(style="whitegrid")
    summary_df = pd.read_csv(args.summary_csv)
    pairwise_df = pd.read_csv(args.pairwise_csv)
    sweep_n100 = pd.read_csv(args.sweep_n100)
    sweep_n200 = pd.read_csv(args.sweep_n200)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    f1 = out_dir / "fig_f1_hook_routing_vs_scale.png"
    f2 = out_dir / "fig_f2_etth1_model_schematic.png"
    f3 = out_dir / "fig_f3_temporal_bottleneck_control.png"
    f4 = out_dir / "fig_f4_prior_boundary_map.png"
    f5 = out_dir / "fig_f5_etth1_pareto_frontier.png"
    captions = out_dir / "figure_captions.md"
    manifest = out_dir / "figure_manifest.json"

    _figure_f1(summary_df=summary_df, out_path=f1)
    _figure_f2(summary_df=summary_df, out_path=f2)
    _figure_f3(summary_df=summary_df, pairwise_df=pairwise_df, out_path=f3)
    _figure_f4(sweep_n100=sweep_n100, sweep_n200=sweep_n200, out_path=f4)
    _figure_f5(summary_df=summary_df, out_path=f5)

    captions.write_text(
        "\n".join(
            [
                "# ETTh1 Story Figure Captions",
                "",
                "- F1: Hook panel contrasting dense all-to-all computation vs sparse routed experts for ETTh1 forecasting.",
                "- F2: ETTh1 modeling schematic from input window to forecast head, including temporal control branch (`mean|GRU`).",
                "- F3: Temporal control (`mean` vs `GRU`) reduces ETTh1 error across both ETTh1-only and dual-task regimes (10 seeds).",
                "- F4: Prior-effect heatmap (`prior_true - prior_false` in ETTh1 MSE) shows region-dependent gains/losses, not universal dominance.",
                "- F5: Pareto view quantifies the trade-off between ETTh1 error reduction and efficiency cost (latency/FLOPs).",
            ]
        ),
        encoding="utf-8",
    )

    payload = {
        "sources": {
            "summary_csv": str(Path(args.summary_csv)),
            "pairwise_csv": str(Path(args.pairwise_csv)),
            "sweep_n100": str(Path(args.sweep_n100)),
            "sweep_n200": str(Path(args.sweep_n200)),
        },
        "figures": {
            "f1_hook_routing_vs_scale": str(f1),
            "f2_etth1_model_schematic": str(f2),
            "f3_temporal_bottleneck_control": str(f3),
            "f4_prior_boundary_map": str(f4),
            "f5_etth1_pareto_frontier": str(f5),
            "captions": str(captions),
        },
    }
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
