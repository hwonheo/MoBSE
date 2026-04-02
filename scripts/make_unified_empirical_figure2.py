#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle, FancyArrowPatch

from mobse.viz import save_multi, set_nature_style


def _label(reg: str, tmp: str) -> str:
    r = "ETTh1-only" if reg == "etth1_only" else "Dual-task"
    t = "GRU" if tmp == "gru" else "Mean"
    return f"{r}\n({t})"


def _load_pairwise_pvals(df: pd.DataFrame) -> dict:
    d = {}
    for _, row in df.iterrows():
        k = (str(row["comparison"]), str(row["metric"]))
        d[k] = float(row["ttest_rel_p"])
    return d


def apply_f3_temporal(ax_schem, axes, summary_df: pd.DataFrame, pairwise_df: pd.DataFrame):
    pvals = _load_pairwise_pvals(pairwise_df)
    data = summary_df.copy()
    
    regimes = [("etth1_only", "ETTh1-only"), ("dual_task", "Dual-task")]
    colors = {"MEAN": "#9CA3AF", "GRU": "#10B981"}
    
    for ax_idx, (metric_col, metric_name, pt_key) in enumerate([
        ("etth1_mae", "MAE", "metric_mae"),
        ("etth1_mse", "MSE", "metric_mse"),
    ]):
        ax = axes[ax_idx]
        y_positions = [1.0, 0.0] 
        
        for i, (regime_key, regime_label) in enumerate(regimes):
            y = y_positions[i]
            sub = data[data["regime"] == regime_key]
            if len(sub) == 0: continue
            
            sub_m = sub[sub["temporal_encoder"] == "mean"]
            sub_g = sub[sub["temporal_encoder"] == "gru"]
            if len(sub_m) == 0 or len(sub_g) == 0: continue
            
            v_m = sub_m[metric_col + "_mean"].values[0]
            v_m_std = sub_m[metric_col + "_std"].values[0]
            v_g = sub_g[metric_col + "_mean"].values[0]
            v_g_std = sub_g[metric_col + "_std"].values[0]
            
            ax.plot([v_m, v_g], [y, y], color="#4B5563", lw=2.5, zorder=1)
            ax.annotate("", xy=(v_g, y), xytext=(v_m, y),
                        arrowprops=dict(arrowstyle="-|>", color="#374151", lw=2.0, mutation_scale=15),
                        zorder=2)
            
            ax.errorbar([v_m], [y], xerr=[v_m_std], fmt='none', ecolor="#D1D5DB", elinewidth=1.5, capsize=4, zorder=2)
            ax.errorbar([v_g], [y], xerr=[v_g_std], fmt='none', ecolor="#A7F3D0", elinewidth=1.5, capsize=4, zorder=2)
            
            ax.scatter([v_m], [y], color=colors["MEAN"], edgecolor="none", alpha=0.6, s=300, zorder=3, label="Baseline (Dense)" if i==0 and ax_idx==0 else "")
            ax.scatter([v_g], [y], color=colors["GRU"], edgecolor="none", alpha=0.7, s=450, marker="*", zorder=3, label="MoBSE (Sparse / Proposed)" if i==0 and ax_idx==0 else "")
            
            val_offset = (max(v_m, v_g) - min(v_m, v_g)) * 0.12
            ax.text(v_m + val_offset, y + 0.15, f"{v_m:.3f}", color="#6B7280", fontsize=8, ha="center", fontweight="bold")
            ax.text(v_g - val_offset, y + 0.15, f"{v_g:.3f}", color="#064E3B", fontsize=9, ha="center", fontweight="bold")
            
            pct = (v_m - v_g) / v_m * 100
            mid_x = (v_m + v_g) / 2
            ax.text(mid_x, y + 0.08, f"-{pct:.1f}%", ha="center", va="center", fontsize=8, color="#EF4444", fontweight="bold", bbox=dict(facecolor="white", edgecolor="none", pad=1.0, alpha=0.9), zorder=4)
            
            pval = pvals.get((f"gru_minus_mean_{regime_key.replace('_', '')}", pt_key), float("nan"))
            ax.text(mid_x, y - 0.22, f"p = {pval:.2e}", ha="center", va="center", fontsize=7, color="#6B7280", fontstyle="italic")

        ax.set_ylim(-0.8, 1.8)
        ax.set_xlabel(f"{metric_name}", fontsize=9, color="#4B5563", labelpad=2)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="#E5E7EB", linestyle="--", alpha=0.7)
        ax.set_yticks([])

    # Identity Space
    ax_schem.set_ylim(-0.8, 1.8)
    ax_schem.set_xlim(-0.5, 0.5)
    ax_schem.spines[:].set_visible(False)
    ax_schem.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for i, (regime_key, regime_label) in enumerate(regimes):
        y = y_positions[i]
        ax_schem.text(0, y + 0.35, regime_label, color="#111827", fontweight="bold", ha="center", fontsize=8)
        if i == 0:
            ax_schem.text(0, y, r"$X_{h1}$", ha="center", va="center", fontsize=8, color="#064E3B", bbox=dict(boxstyle="round,pad=0.2", fc="#D1FAE5", ec="#34D399"))
        else:
            ax_schem.text(0, y, r"$X_{All}$", ha="center", va="center", fontsize=8, color="#92400E", bbox=dict(boxstyle="round,pad=0.2", fc="#FEF3C7", ec="#FBBF24"))
        ax_schem.add_patch(FancyArrowPatch((0, y-0.08), (0, y-0.22), arrowstyle="-|>", mutation_scale=8, color="#6B7280"))
        ax_schem.text(0, y-0.3, "MoBSE" if i==1 else "Base", ha="center", va="center", fontsize=7, color="#374151")


def apply_f4_prior(axes, sweep_n100, sweep_n200):
    sweep = pd.concat([sweep_n100, sweep_n200], ignore_index=True)
    agg_df = (sweep.groupby(["nodes", "sparsity", "routing_mode", "template_prior"])["etth1_mse"]
              .agg(["mean", "std"]).reset_index())
    nodes_sorted = sorted(agg_df["nodes"].unique().tolist())
    for idx, nodes in enumerate(nodes_sorted):
        ax = axes[idx]
        sub = agg_df[agg_df["nodes"] == nodes]
        pt_df = sub[sub["template_prior"] == True].set_index(["routing_mode", "sparsity"])
        pf_df = sub[sub["template_prior"] == False].set_index(["routing_mode", "sparsity"])
        heat_df = pd.merge(pt_df[["mean", "std"]], pf_df[["mean", "std"]], left_index=True, right_index=True, suffixes=('_true', '_false'))
        heat_df["delta"] = heat_df["mean_true"] - heat_df["mean_false"]
        heat_df["se"] = np.sqrt((heat_df["std_true"]**2)/10 + (heat_df["std_false"]**2)/10)
        heat_df["t_stat"] = (heat_df["delta"].abs() / heat_df["se"]).fillna(0)
        unique_sp = sorted(sub["sparsity"].unique())
        unique_rm = sorted(sub["routing_mode"].unique())
        D_mat = np.full((len(unique_rm), len(unique_sp)), np.nan)
        T_mat = np.full((len(unique_rm), len(unique_sp)), 1.0)
        for i, rm in enumerate(unique_rm):
            for j, sp in enumerate(unique_sp):
                if (rm, sp) in heat_df.index:
                    D_mat[i, j] = heat_df.loc[(rm, sp), "delta"]
                    T_mat[i, j] = heat_df.loc[(rm, sp), "t_stat"]
        max_abs = np.nanmax(np.abs(D_mat))
        ax.set_facecolor("#F9FAFB")
        ax.set_xlim(-0.5, len(unique_sp) - 0.5)
        ax.set_ylim(-0.5, len(unique_rm) - 0.5)
        for r_idx, rm in enumerate(unique_rm):
            for c_idx, sp in enumerate(unique_sp):
                val = D_mat[r_idx, c_idx]
                if pd.isna(val): continue
                tval = T_mat[r_idx, c_idx]
                color = "#10B981" if val < 0 else "#F59E0B"
                size = (abs(val) / max_abs) * 500 + 100 if max_abs > 0 else 100
                ax.scatter(c_idx, r_idx, s=size, color=color, alpha=0.85 if tval > 2.0 else 0.35, edgecolor="none", zorder=2)
                ax.text(c_idx, r_idx, f"{val:+.3f}", ha="center", va="center", color="#1F2937", fontsize=8, fontweight="bold" if tval>2.0 else "normal", zorder=3)
        ax.set_xticks(range(len(unique_sp)))
        ax.set_xticklabels([f"T-{s}" for s in unique_sp], fontsize=8)
        ax.set_yticks(range(len(unique_rm)))
        ax.set_yticklabels(unique_rm, fontsize=8)
        ax.set_title(f"Nodes = {nodes}", fontsize=9, fontweight="bold", color="#4B5563", pad=4)
        ax.set_ylabel("Mode", fontsize=8, color="#4B5563") if idx==0 else ax.set_ylabel("")
        ax.spines[:].set_visible(False)
        ax.grid(color="white", lw=2, zorder=1)


def apply_f5_pareto_slope(axes, summary_df: pd.DataFrame):
     data = summary_df.copy()
     regimes = [("etth1_only", "h1-Only"), ("dual_task", "Dual-Task")]
     for ax_idx, (x_col, x_label) in enumerate([("etth1_latency_ms_mean", "Latency (ms)"), ("etth1_flops_mean", "FLOPs")]):
         ax = axes[ax_idx]
         x_pos = [0, 1]
         for i, (regime_key, regime_label) in enumerate(regimes):
             sub = data[data["regime"] == regime_key]
             m_row = sub[sub["temporal_encoder"] == "mean"]
             g_row = sub[sub["temporal_encoder"] == "gru"]
             if m_row.empty or g_row.empty: continue
             x_m, y_m = m_row[x_col].values[0], m_row["etth1_mae_mean"].values[0]
             x_g, y_g = g_row[x_col].values[0], g_row["etth1_mae_mean"].values[0]
             y_m_std, y_g_std = m_row["etth1_mae_std"].values[0], g_row["etth1_mae_std"].values[0]
             xc = x_pos[i]
             ax.errorbar(xc - 0.12, y_m, yerr=y_m_std, fmt='none', ecolor="#D1D5DB", elinewidth=1.5, zorder=2)
             ax.scatter(xc - 0.12, y_m, color="#9CA3AF", alpha=0.6, s=200, edgecolor="none", zorder=3)
             ax.errorbar(xc + 0.12, y_g, yerr=y_g_std, fmt='none', ecolor="#A7F3D0", elinewidth=1.5, zorder=2)
             ax.scatter(xc + 0.12, y_g, color="#10B981", marker="*", alpha=0.7, s=400, edgecolor="none", zorder=4)
             ax.plot([xc-0.12, xc+0.12], [y_m, y_g], color="#4B5563", lw=1.2, ls="--", zorder=1)
             impr = (y_m - y_g) / y_m * 100
             ax.text(xc, (y_m+y_g)/2, f"Gain: +{impr:.1f}%", ha="center", fontsize=8, color="#EF4444", fontweight="bold", bbox=dict(facecolor="white", edgecolor="none", pad=0.5, alpha=0.9))
             ax.text(xc-0.12, y_m+0.05, f"{y_m:.3f}", ha="center", va="bottom", fontsize=7, color="#6B7280")
             ax.text(xc+0.12, y_g-0.08, f"{y_g:.3f}", ha="center", va="top", fontsize=8, color="#064E3B", fontweight="bold")
             ax.text(xc, min(y_m, y_g) - 0.25, f"{x_g:.2f} ms" if "latency" in x_col else f"{x_g/1e6:.1f}M", ha="center", fontsize=8, color="#4B5563", fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="#F3F4F6", ec="#D1D5DB"))
         ax.set_xticks(x_pos)
         ax.set_xticklabels([r[1] for r in regimes], fontweight="bold")
         ax.set_ylabel("MAE", fontsize=9, color="#4B5563") if ax_idx==0 else ax.set_ylabel("")
         ax.set_xlim(-0.5, 1.5)
         ax.spines["top"].set_visible(False)
         ax.spines["right"].set_visible(False)
         ax.grid(axis="y", color="#E5E7EB", ls="--")


def apply_f6_ett_delta(axes, ett_df: pd.DataFrame):
     df = ett_df.copy()
     order = ["ETTh1", "ETTh2", "ETTm1", "ETTm2"]
     df = df.set_index("dataset").reindex(order).reset_index()
     x = np.arange(len(df))
     metrics = [("mae_mean", "mae_std", "#10B981"), ("mse_mean", "mse_std", "#F59E0B")]
     for ax_idx, (m_col, s_col, col) in enumerate(metrics):
         ax = axes[ax_idx]
         y, ystd = df[m_col].values, df[s_col].values
         ax.axhline(0, color="#6B7280", lw=2, zorder=1)
         ax.errorbar(x, y, yerr=ystd, fmt="none", ecolor="#D1D5DB", capsize=0, zorder=2)
         ax.scatter(x, y, s=250, color=col, alpha=0.7, edgecolor="none", zorder=3)
         ax.set_xticks(x)
         ax.set_xticklabels(df["dataset"], fontweight="bold", fontsize=9)
         ax.set_ylabel(m_col.split("_")[0].upper(), fontsize=9)
         ymax = y.max()
         ax.set_ylim(-ymax*0.2, ymax*1.3)
         # Increased left margin to avoid Y-axis proximity
         ax.set_xlim(-1.2, 4.2)
         ax.grid(axis="y", ls="--", alpha=0.5)
         ax.spines["bottom"].set_visible(False)
         ax.spines["top"].set_visible(False)
         ax.spines["right"].set_visible(False)
         for idx, val in enumerate(y):
             ax.text(idx, val + ystd[idx] + (ymax*0.05), f"{val:.3f}", ha="center", fontsize=8, fontweight="bold")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-csv", default="artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv")
    ap.add_argument("--pairwise-csv", default="artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv")
    ap.add_argument("--sweep-n100", default="artifacts/legacy_phase2/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv")
    ap.add_argument("--sweep-n200", default="artifacts/legacy_phase2/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_sweep_seed42.csv")
    ap.add_argument("--ett-csv", default="artifacts/current_canonical/ett_family_extension_20260331_rerun10/reports/ett_family_summary_s10.csv")
    ap.add_argument("--out-dir", default="docs/manuscript_final_2026-03-31/figures")
    args = ap.parse_args()

    set_nature_style()
    sum_df, pair_df = pd.read_csv(args.summary_csv), pd.read_csv(args.pairwise_csv)
    s100, s200, ett = pd.read_csv(args.sweep_n100), pd.read_csv(args.sweep_n200), pd.read_csv(args.ett_csv)

    fig = plt.figure(figsize=(7.2, 9.0))
    # Unified 5-column grid across 4 rows
    gs = fig.add_gridspec(4, 5, hspace=0.8, wspace=0.35)
    
    # Map subplots to the unified grid
    ax_a_schem = fig.add_subplot(gs[0, 0])
    ax_a_mae, ax_a_mse = fig.add_subplot(gs[0, 1:3]), fig.add_subplot(gs[0, 3:5])
    ax_b = [fig.add_subplot(gs[1, 1:3]), fig.add_subplot(gs[1, 3:5])]
    ax_c = [fig.add_subplot(gs[2, 1:3]), fig.add_subplot(gs[2, 3:5])]
    ax_d = [fig.add_subplot(gs[3, 1:3]), fig.add_subplot(gs[3, 3:5])]

    apply_f3_temporal(ax_a_schem, [ax_a_mae, ax_a_mse], sum_df, pair_df)
    apply_f4_prior(ax_b, s100, s200)
    apply_f5_pareto_slope(ax_c, sum_df)
    apply_f6_ett_delta(ax_d, ett)

    # Standardized Title Positioning for perfect alignment
    title_x = -0.42 # Alignment target relative to each left-side data spine
    ax_a_mae.text(title_x, 1.25, "a. Temporal Trajectories", transform=ax_a_mae.transAxes, fontsize=11, fontweight="bold")
    ax_b[0].text(title_x, 1.20, "b. Sub-Expert Sparsity boundaries", transform=ax_b[0].transAxes, fontsize=11, fontweight="bold")
    ax_c[0].text(title_x, 1.25, "c. Performance-Efficiency Tradeoffs", transform=ax_c[0].transAxes, fontsize=11, fontweight="bold")
    ax_d[0].text(title_x, 1.25, "d. Multi-dataset Error Distributions", transform=ax_d[0].transAxes, fontsize=11, fontweight="bold")

    handles, labels = ax_a_mae.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=2, frameon=True, fontsize=10, facecolor="#F9FAFB")

    plt.subplots_adjust(top=0.92, bottom=0.08, left=0.12, right=0.96)
    f2_path = Path(args.out_dir) / "fig_f2_unified_empirical_panel.png"
    save_multi(f2_path, fig)
    plt.close(fig)
    print(f"Final aligned Figure 2 (Unified Grid) saved to {f2_path}")

if __name__ == "__main__":
    main()
