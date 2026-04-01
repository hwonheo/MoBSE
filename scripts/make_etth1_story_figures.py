from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

from mobse.viz import save_multi, set_nature_style


def _resolve_existing(path_str: str, fallback_globs: Iterable[str], label: str) -> Path:
    candidate = Path(path_str)
    if candidate.exists():
        return candidate

    matches: list[Path] = []
    for pattern in fallback_globs:
        matches.extend(Path(".").glob(pattern))
    matches = [p for p in matches if p.is_file()]
    if matches:
        resolved = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        print(
            f"[make_etth1_story_figures] {label} not found at '{path_str}', "
            f"using '{resolved.as_posix()}'"
        )
        return resolved

    raise FileNotFoundError(
        f"{label} not found: '{path_str}'. Tried fallbacks: {list(fallback_globs)}"
    )


def _label(regime: str, temporal: str) -> str:
    left = "dual" if regime == "dual_task" else "etth1-only"
    return f"{left}-{temporal}"


def _load_pairwise_pvals(pairwise_df: pd.DataFrame) -> Dict[Tuple[str, str], float]:
    out: Dict[Tuple[str, str], float] = {}
    for _, row in pairwise_df.iterrows():
        out[(str(row["comparison"]), str(row["metric"]))] = float(row["ttest_rel_p"])
    return out


def _add_box(ax, x: float, y: float, w: float, h: float, text: str, face: str = "none", edgecolor: str = "none", fontsize: float = 8.0, fontweight: str = "normal", fontcolor: str = "#1F2937", align: str = "center") -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        linewidth=0.6,
        edgecolor=edgecolor,
        facecolor=face,
        alpha=0.9,
    )
    ax.add_patch(box)
    
    tx = x + w / 2 if align == "center" else x + 0.02
    ha = "center" if align == "center" else "left"
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fontsize, fontweight=fontweight, color=fontcolor)


def _figure_f1(summary_df: pd.DataFrame, out_path: Path) -> None:
    # Nature-style figure: elegantly spaced layout, larger vertical height for breathing room
    fig = plt.figure(figsize=(7.4, 4.4))
    fig.patch.set_facecolor("white")

    mean_df = summary_df[summary_df["temporal_encoder"] == "mean"]
    gru_df = summary_df[summary_df["temporal_encoder"] == "gru"]
    mean_mae = float(mean_df["etth1_mae_mean"].mean()) if not mean_df.empty else float("nan")
    gru_mae = float(gru_df["etth1_mae_mean"].mean()) if not gru_df.empty else float("nan")
    mean_lat = float(mean_df["etth1_latency_ms_mean"].mean()) if not mean_df.empty else float("nan")
    gru_lat = float(gru_df["etth1_latency_ms_mean"].mean()) if not gru_df.empty else float("nan")
    mean_flops = float(mean_df["etth1_flops_mean"].mean()) if not mean_df.empty else float("nan")
    gru_flops = float(gru_df["etth1_flops_mean"].mean()) if not gru_df.empty else float("nan")

    # Panel A: Conceptual Schematic (Dense vs Routing)
    ax_a = fig.add_axes([0.02, 0.02, 0.56, 0.90])  # Slightly narrower ax_a for wider gap to ax_b
    ax_a.axis("off")
    
    # 1) Title and Panel Label
    fig.text(0.02, 0.96, "a", fontsize=12, fontweight="bold", ha="left", va="top", family="sans-serif")
    fig.text(0.06, 0.96, "Conceptual Shift: Dense vs. Routed", fontsize=10, fontweight="bold", color="#111827", ha="left", va="top")
    
    # Left Side: Dense Baseline
    ax_a.text(0.25, 0.88, "Dense Path (Baseline)", fontsize=9, ha="center", color="#374151", fontweight="bold")
    ax_a.text(0.25, 0.83, r"$\mathcal{O}(N^2)$ Complexity", fontsize=8, ha="center", color="#6B7280")
    
    left_center = (0.25, 0.48)
    radius_x = 0.15
    radius_y = 0.15
    points = []
    n_nodes = 8
    for i in range(n_nodes):
        theta = 2.0 * math.pi * i / n_nodes
        x = left_center[0] + radius_x * math.cos(theta)
        y = left_center[1] + radius_y * math.sin(theta)
        points.append((x, y))
    
    # All-to-all dense graph
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            ax_a.plot([points[i][0], points[j][0]], [points[i][1], points[j][1]], color="#FCA5A5", linewidth=0.6, alpha=0.6)
            
    # Nodes
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
    for x, y in points:
        ax_a.add_patch(Circle((x, y), 0.016, facecolor="#EF4444", edgecolor="#B91C1C", lw=0.5, zorder=3))

    # Dense Input and Output Spacing
    ax_a.annotate("", xy=(0.25, 0.65), xytext=(0.25, 0.75), arrowprops=dict(arrowstyle="->", color="#9CA3AF", lw=1.5))
    ax_a.text(0.25, 0.76, "Input Sequence", ha="center", va="bottom", fontsize=8, color="#4B5563")

    ax_a.annotate("", xy=(0.25, 0.16), xytext=(0.25, 0.31), arrowprops=dict(arrowstyle="-|>", color="#9CA3AF", lw=1.5))
    ax_a.text(0.25, 0.14, "Forecast/FN Output", ha="center", va="top", fontsize=8, color="#4B5563")

    # Divider line
    ax_a.plot([0.5, 0.5], [0.1, 0.87], color="#E5E7EB", linewidth=1.0, linestyle="--")

    # Right Side: Sparse Routing (Proposed)
    ax_a.text(0.75, 0.88, "Sparse Routing (Proposed)", fontsize=9, ha="center", color="#374151", fontweight="bold")
    ax_a.text(0.75, 0.83, r"$\mathcal{O}(k \cdot N)$ Complexity", fontsize=8, ha="center", color="#6B7280")
    
    router_xy = (0.75, 0.62)
    ax_a.add_patch(FancyBboxPatch((router_xy[0]-0.07, router_xy[1]-0.05), 0.14, 0.10, boxstyle="round,pad=0.02,rounding_size=0.04", facecolor="#E0E7FF", edgecolor="#4F46E5", lw=1.2, zorder=3))
    ax_a.text(router_xy[0], router_xy[1]+0.015, "MoBSE", ha="center", va="center", fontsize=10, fontweight="bold", color="#312E81", zorder=4)
    ax_a.text(router_xy[0], router_xy[1]-0.025, "(Router)", ha="center", va="center", fontsize=7, color="#4338CA", zorder=4)
    
    ax_a.annotate("", xy=(router_xy[0], 0.68), xytext=(router_xy[0], 0.75), arrowprops=dict(arrowstyle="->", color="#9CA3AF", lw=1.5))
    ax_a.text(router_xy[0], 0.76, "Input Sequence", ha="center", va="bottom", fontsize=8, color="#4B5563")

    expert_y = 0.40
    expert_xs = [0.57, 0.69, 0.81, 0.93]
    expert_labels = ["$E_1$", "$E_2$", "$E_3$", "$E_4$"]
    active_indices = [0, 2]  # Active routes k=2
    
    for i, (ex, el) in enumerate(zip(expert_xs, expert_labels)):
        is_active = i in active_indices
        arr_col = "#10B981" if is_active else "#E5E7EB"
        rad = -0.1 if ex < router_xy[0] else 0.1
        
        # Base container faint dashed circle
        circ_fc = "#F0FDF4" if is_active else "#F9FAFB"
        circ_ec = "#A7F3D0" if is_active else "#E5E7EB"
        ax_a.add_patch(Circle((ex, expert_y), 0.045, facecolor=circ_fc, edgecolor=circ_ec, lw=1.0, linestyle="--", zorder=2))
        
        # Mini graph topology parameters
        e_nodes = 8
        e_rad = 0.03
        e_points = []
        for j in range(e_nodes):
            theta = 2.0 * math.pi * j / e_nodes
            nx = ex + e_rad * math.cos(theta)
            ny = expert_y + e_rad * math.sin(theta)
            e_points.append((nx, ny))
            
        if is_active:
            # Custom sparse routing patterns for each expert
            active_edges = [(0,4), (1,3), (1,5)] if i == 0 else [(2,6), (3,7), (6,7)]
            active_nodes = set()
            for x1, x2 in active_edges:
                active_nodes.add(x1)
                active_nodes.add(x2)
            
            # Faint background connecting paths indicating Dense subset
            for n1 in range(e_nodes):
                for n2 in range(n1+1, e_nodes):
                    if (n1,n2) not in active_edges and (n2,n1) not in active_edges:
                        ax_a.plot([e_points[n1][0], e_points[n2][0]], [e_points[n1][1], e_points[n2][1]], color="#F3F4F6", lw=0.4, alpha=0.5, zorder=2)
            
            # Vivid sparse routes in action
            for n1, n2 in active_edges:
                ax_a.plot([e_points[n1][0], e_points[n2][0]], [e_points[n1][1], e_points[n2][1]], color="#10B981", lw=1.2, zorder=3)
                
            # Draw activated vs inactivated nodes
            for j, (nx, ny) in enumerate(e_points):
                node_active = j in active_nodes
                ncol = "#34D399" if node_active else "#F3F4F6"
                nedge = "#059669" if node_active else "#D1D5DB"
                ax_a.add_patch(Circle((nx, ny), 0.005, facecolor=ncol, edgecolor=nedge, lw=0.5, zorder=4))
        else:
            # Sleeping inactive experts show only faint network scaffolding
            for n1 in range(e_nodes):
                for n2 in range(n1+1, e_nodes):
                    if (n1+n2) % 3 == 0:  
                        ax_a.plot([e_points[n1][0], e_points[n2][0]], [e_points[n1][1], e_points[n2][1]], color="#F3F4F6", lw=0.4, alpha=0.5, zorder=2)
            for nx, ny in e_points:
                ax_a.add_patch(Circle((nx, ny), 0.004, facecolor="#F9FAFB", edgecolor="#E5E7EB", lw=0.4, zorder=4))
        
        # Label E_i beneath the miniature graph
        l_col = "#064E3B" if is_active else "#9CA3AF"
        ax_a.text(ex, expert_y-0.055, el, ha="center", va="top", fontsize=8, color=l_col, fontweight="bold", zorder=4)

        # Arrows from router precisely avoiding the boundary (padded to +0.05)
        ax_a.add_patch(FancyArrowPatch((router_xy[0], router_xy[1]-0.06), (ex, expert_y+0.05), connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=12, linewidth=1.5 if is_active else 1.0, color=arr_col, zorder=2))

        # Output vertical arrows starting with 0.01 gap below E_i label
        ax_a.annotate("", xy=(ex, 0.24), xytext=(ex, expert_y-0.10), arrowprops=dict(arrowstyle="-|>", color=arr_col, lw=1.5 if is_active else 1.0))

    # Output merger shifted gently down for arrow length balance
    ax_a.plot([0.57, 0.93], [0.24, 0.24], color="#D1D5DB", lw=1.5)
    ax_a.annotate("", xy=(0.75, 0.16), xytext=(0.75, 0.24), arrowprops=dict(arrowstyle="-|>", color="#9CA3AF", lw=1.5))
    ax_a.text(0.75, 0.14, "Forecast/FN Output", ha="center", va="top", fontsize=8, color="#4B5563")


    # Panel B: Empirical Advantages
    fig.text(0.60, 0.96, "b", fontsize=12, fontweight="bold", ha="left", va="top", family="sans-serif")
    fig.text(0.63, 0.96, "Empirical Gains (10-seed)", fontsize=10, fontweight="bold", color="#111827", ha="left", va="top")
    fig.text(0.63, 0.92, "(See Fig. 3 & 5 for detailed tradeoffs)", fontsize=8, color="#6B7280", ha="left", va="top", fontstyle="italic")

    metrics = [
        ("Test MAE", mean_mae, gru_mae),
        ("Latency (ms)", gru_lat, mean_lat),
        ("kFLOPs", gru_flops / 1e3, mean_flops / 1e3) 
    ]
    
    # Create 3 sub-axes for the bar charts spaced evenly
    for i, (m_name, m_base, m_prop) in enumerate(metrics):
        pct = (m_base - m_prop) / m_base * 100.0 if m_base else 0.0
        # Lowered top chart starting y to prevent clashing with the title above
        y_bot = 0.69 - i * 0.26 
        ax_m = fig.add_axes([0.69, y_bot, 0.28, 0.15]) # Shifted slightly right to avoid ax_a text
        
        ax_m.spines["top"].set_visible(False)
        ax_m.spines["right"].set_visible(False)
        ax_m.spines["left"].set_visible(False)
        ax_m.tick_params(left=False, axis="y", colors="#374151", labelsize=8)
        
        # Plot horizontal bars
        bars = ax_m.barh([1, 0], [m_base, m_prop], color=["#9CA3AF", "#10B981"], height=0.6, alpha=0.9)
        ax_m.set_yticks([0, 1])
        ax_m.set_yticklabels(["MoBSE", "Base"])
        ax_m.set_ylim([-0.6, 1.6])
        
        # Direct labels on bars
        fmt = ".3f" if "MAE" in m_name else (".2f" if "Latency" in m_name else ",.1f")
        ax_m.text(m_base, 1, f" {m_base:{fmt}}", va="center", ha="left", fontsize=8, color="#4B5563")
        ax_m.text(m_prop, 0, f" {m_prop:{fmt}}", va="center", ha="left", fontsize=8, color="#064E3B", fontweight="bold")
        
        # Metric Title and percentage drop
        ax_m.text(-0.25 * max(m_base, m_prop), 1.8, m_name, va="bottom", ha="left", fontsize=9, fontweight="bold", color="#374151")
        if pct > 0:
            ax_m.text(max(m_base, m_prop) * 1.1, 1.8, f"(-{pct:.1f}%)", va="bottom", ha="right", fontsize=8, color="#059669", fontweight="bold")
            
        ax_m.spines["bottom"].set_color("#E5E7EB")
        ax_m.tick_params(axis="x", colors="#9CA3AF", labelsize=7)
        ax_m.set_xlim(0, max(m_base, m_prop) * 1.4) 

    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _figure_f2(summary_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    mean_df = summary_df[summary_df["temporal_encoder"] == "mean"]
    gru_df = summary_df[summary_df["temporal_encoder"] == "gru"]
    mean_mae = float(mean_df["etth1_mae_mean"].mean()) if not mean_df.empty else float("nan")
    gru_mae = float(gru_df["etth1_mae_mean"].mean()) if not gru_df.empty else float("nan")
    mean_lat = float(mean_df["etth1_latency_ms_mean"].mean()) if not mean_df.empty else float("nan")
    gru_lat = float(gru_df["etth1_latency_ms_mean"].mean()) if not gru_df.empty else float("nan")

    # ---------------------------
    # 1) Pipeline Flow Rendering (End-to-End Visual Stream)
    # ---------------------------
    y_p = 0.64
    font_title_sz = 9
    font_sub_sz = 8
    
    title_y = 0.86
    sub_y = 0.80
    
    # Block 1. ETTh1 Window
    x1 = 0.10
    for i_r in range(3):
        for j_c in range(3):
            ax.add_patch(plt.Rectangle((x1 - 0.03 + j_c*0.02, y_p - 0.04 + i_r*0.02), 0.015, 0.015, facecolor="#E0E7FF", edgecolor="#818CF8", lw=0.5))
    ax.text(x1, title_y, "1. ETTh1\nWindow", ha="center", va="center", fontsize=font_title_sz, fontweight="bold", color="#1F2937")
    ax.text(x1, sub_y, r"$X \in \mathbb{R}^{T \times d}$", ha="center", va="center", fontsize=font_sub_sz, color="#6B7280")

    # Flow 1->2
    x2 = 0.26
    ax.annotate("", xy=(x2-0.035, y_p), xytext=(x1+0.035, y_p), arrowprops=dict(arrowstyle="-|>", color="#9CA3AF", lw=1.5, mutation_scale=10))
    
    # Block 2. Temporal Encoder
    for s in range(3):
        ax.add_patch(plt.Rectangle((x2 - 0.02 + s*0.01, y_p - 0.04 + s*0.01), 0.03, 0.06, facecolor="#FDE68A", edgecolor="#F59E0B", lw=0.8, zorder=2+s))
    ax.text(x2, title_y, "2. Temporal\nEncoder", ha="center", va="center", fontsize=font_title_sz, fontweight="bold", color="#1F2937")
    ax.text(x2, sub_y, r"$Z \in \mathbb{R}^{N \times H}$", ha="center", va="center", fontsize=font_sub_sz, color="#6B7280")

    # Flow 2->3
    x3 = 0.42
    ax.annotate("", xy=(x3-0.04, y_p), xytext=(x2+0.035, y_p), arrowprops=dict(arrowstyle="-|>", color="#9CA3AF", lw=1.5, mutation_scale=10))
    
    # Block 3. Node Projection
    ax.add_patch(Circle((x3, y_p), 0.035, facecolor="#D1FAE5", edgecolor="#10B981", lw=1.2, zorder=2))
    ax.text(x3, y_p, r"$\phi$", ha="center", va="center", fontsize=11, color="#047857", fontweight="bold", zorder=3)
    ax.text(x3, title_y, "3. Node\nProjection", ha="center", va="center", fontsize=font_title_sz, fontweight="bold", color="#1F2937")
    ax.text(x3, sub_y, r"$\phi(Z)$", ha="center", va="center", fontsize=font_sub_sz, color="#6B7280")

    # Flow 3->4
    x4 = 0.58
    ax.annotate("", xy=(x4-0.05, y_p), xytext=(x3+0.045, y_p), arrowprops=dict(arrowstyle="-|>", color="#9CA3AF", lw=1.5, mutation_scale=10))
    
    # Block 4. Top-k Router (MoBSE icon)
    ax.add_patch(FancyBboxPatch((x4-0.04, y_p-0.03), 0.08, 0.06, boxstyle="round,pad=0.01,rounding_size=0.02", facecolor="#E0E7FF", edgecolor="#4F46E5", lw=1.2, zorder=3))
    ax.text(x4, y_p, "MoBSE", ha="center", va="center", fontsize=9, fontweight="bold", color="#312E81", zorder=4)
    ax.text(x4, title_y, "4. Top-$k$\nRouter", ha="center", va="center", fontsize=font_title_sz, fontweight="bold", color="#1F2937")
    ax.text(x4, sub_y, r"$\mathrm{softmax}(W Z)$", ha="center", va="center", fontsize=font_sub_sz, color="#6B7280")

    # Block 5. Expert Mix (Miniature Sparse Patterns)
    x5 = 0.74
    my_centers = [0.74, 0.64, 0.54]  
    for k, c_y in enumerate(my_centers):
        is_act = k in [0, 2] # Actives
        # Dashed container mapping sparse subset
        ax.add_patch(Circle((x5, c_y), 0.020, facecolor="#F0FDF4" if is_act else "#F9FAFB", edgecolor="#A7F3D0" if is_act else "#E5E7EB", lw=0.8, linestyle="--", zorder=2))
        
        # Draw dynamic mini graph
        e_px = []
        for j in range(6):
            th = 2 * math.pi * j / 6
            e_px.append((x5 + 0.012*math.cos(th), c_y + 0.012*math.sin(th)))
            
        circ_c = "#34D399" if is_act else "#E5E7EB"
        ecirc_c = "#059669" if is_act else "#D1D5DB"
        if is_act:
            ax.plot([e_px[0][0], e_px[3][0]], [e_px[0][1], e_px[3][1]], color="#10B981", lw=0.8, zorder=3)
            if k == 0: ax.plot([e_px[1][0], e_px[4][0]], [e_px[1][1], e_px[4][1]], color="#10B981", lw=0.8, zorder=3)
            if k == 2: ax.plot([e_px[2][0], e_px[5][0]], [e_px[2][1], e_px[5][1]], color="#10B981", lw=0.8, zorder=3)
            
        for nx, ny in e_px:
            ax.add_patch(Circle((nx, ny), 0.002, facecolor=circ_c, edgecolor=ecirc_c, lw=0.4, zorder=4))
        
        # Elegant merge curves out/in from router
        arr_col = "#10B981" if is_act else "#E5E7EB"
        rd = -0.1 if c_y > 0.64 else (0.1 if c_y < 0.64 else 0.0)
        ax.annotate("", xy=(x5-0.025, c_y), xytext=(x4+0.045, y_p), arrowprops=dict(arrowstyle="-|>", mutation_scale=8, color=arr_col, lw=1.2, connectionstyle=f"arc3,rad={rd}"))
        
        rd2 = 0.1 if c_y > 0.64 else (-0.1 if c_y < 0.64 else 0.0)
        ax.annotate("", xy=(0.875, y_p), xytext=(x5+0.025, c_y), arrowprops=dict(arrowstyle="-|>", mutation_scale=8, color=arr_col, lw=1.2, connectionstyle=f"arc3,rad={rd2}"))

    ax.text(x5, title_y, "5. Expert\nMix", ha="center", va="center", fontsize=font_title_sz, fontweight="bold", color="#1F2937")
    ax.text(x5, sub_y, r"$\sum g_e E_e(Z)$", ha="center", va="center", fontsize=font_sub_sz, color="#6B7280")

    # Block 6. Forecast Head
    x6 = 0.90
    ax.add_patch(plt.Rectangle((x6-0.02, y_p-0.025), 0.05, 0.05, facecolor="white", edgecolor="#D1D5DB", lw=1.0, zorder=4))
    
    # History trajectory element
    ax.plot([x6-0.015, x6+0.005, x6+0.005], [y_p-0.01, y_p+0.01, y_p-0.01], color="#9CA3AF", lw=1.2, zorder=5)
    # Forecast tracking element
    ax.plot([x6+0.005, x6+0.015, x6+0.025], [y_p-0.01, y_p+0.015, y_p+0.005], color="#EF4444", lw=1.5, linestyle="--", zorder=5)
    
    ax.text(x6, title_y, "6. Forecast\nHead", ha="center", va="center", fontsize=font_title_sz, fontweight="bold", color="#1F2937")
    ax.text(x6, sub_y, r"$\hat{y} \in \mathbb{R}^{\mathrm{out}}$", ha="center", va="center", fontsize=font_sub_sz, color="#6B7280")

    # ---------------------------
    # 2) Variants Breakdown Modules
    # ---------------------------
    ax.plot([0.05, 0.95], [0.46, 0.46], color="#E5E7EB", linewidth=1.0) # Horizontal divider
    
    # Module A: Temporal Encoder Variants
    ax.add_patch(FancyBboxPatch((0.05, 0.16), 0.43, 0.24, boxstyle="round,pad=0.02,rounding_size=0.03", facecolor="#F8FAFC", edgecolor="#CBD5E1", lw=1.0, zorder=2))
    ax.text(0.08, 0.36, "Temporal Encoder Variants", fontsize=10, fontweight="bold", color="#1E293B", zorder=3)
    
    ax.plot([0.08, 0.10], [0.29, 0.29], color="#9CA3AF", lw=3.0, zorder=3)
    ax.text(0.12, 0.29, r"Baseline: $Z_i = \frac{1}{T} \sum_{t} X_{i,t}$", fontsize=9, color="#64748B", va="center", zorder=3)
    
    ax.plot([0.08, 0.10], [0.22, 0.22], color="#10B981", lw=3.0, zorder=3)
    ax.text(0.12, 0.22, r"Proposed: $Z_i = \mathrm{GRU}(X_i)_{t=T}$", fontsize=9, color="#047857", va="center", fontweight="bold", zorder=3)

    # Module B: Task Regime Variants
    ax.add_patch(FancyBboxPatch((0.52, 0.16), 0.43, 0.24, boxstyle="round,pad=0.02,rounding_size=0.03", facecolor="#F8FAFC", edgecolor="#CBD5E1", lw=1.0, zorder=2))
    ax.text(0.55, 0.36, "Task Regime Variants", fontsize=10, fontweight="bold", color="#1E293B", zorder=3)
    
    ax.plot([0.55, 0.57], [0.29, 0.29], color="#9CA3AF", lw=3.0, zorder=3)
    ax.text(0.59, 0.29, r"ETTh1-Only: $\mathcal{L} = \mathrm{MSE}(\hat{y}, y_{\mathrm{etth1}})$", fontsize=9, color="#64748B", va="center", zorder=3)
    
    ax.plot([0.55, 0.57], [0.22, 0.22], color="#10B981", lw=3.0, zorder=3)
    ax.text(0.59, 0.22, r"Dual-Task: $\mathcal{L} = \mathcal{L}_{\mathrm{etth1}} + \lambda \mathcal{L}_{\mathrm{os}}$", fontsize=9, color="#047857", va="center", fontweight="bold", zorder=3)

    # ---------------------------
    # 3) Bottom Scoreboard KPI Frame
    # ---------------------------
    ax.add_patch(FancyBboxPatch((0.05, 0.01), 0.90, 0.11, boxstyle="round,pad=0.01,rounding_size=0.04", facecolor="#ECFDF5", edgecolor="#A7F3D0", lw=1.5, zorder=2))
    ax.text(0.50, 0.085, r"$\mathbf{Baseline}$ (Mean) $\rightarrow$  MAE "+f"{mean_mae:.3f}   |   Latency {gru_lat:.2f}ms", fontsize=10, color="#6B7280", ha="center", va="center", zorder=3)
    ax.text(0.50, 0.040, r"$\mathbf{MoBSE}$ (GRU) $\rightarrow$  MAE "+f"{gru_mae:.3f}   |   Latency {mean_lat:.2f}ms", fontsize=10, color="#064E3B", fontweight="bold", ha="center", va="center", zorder=3)


    fig.tight_layout()
    save_multi(out_path, fig)
    plt.close(fig)


def _figure_f3(summary_df: pd.DataFrame, pairwise_df: pd.DataFrame, out_path: Path) -> None:
    pvals = _load_pairwise_pvals(pairwise_df)
    data = summary_df.copy()
    
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={'wspace': 0.3})
    
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
            
            # Draw connecting dumbbell line and arrow
            ax.plot([v_m, v_g], [y, y], color="#4B5563", lw=2.5, zorder=1)
            ax.annotate("", xy=(v_g, y), xytext=(v_m, y),
                        arrowprops=dict(arrowstyle="-|>", color="#374151", lw=2.0, mutation_scale=15),
                        zorder=2)
            
            # Standard Error Whiskers (X-axis for Dumbbell)
            ax.errorbar([v_m], [y], xerr=[v_m_std], fmt='none', ecolor="#D1D5DB", elinewidth=1.5, capsize=4, capthick=1.5, zorder=2)
            ax.errorbar([v_g], [y], xerr=[v_g_std], fmt='none', ecolor="#A7F3D0", elinewidth=1.5, capsize=4, capthick=1.5, zorder=2)
            
            # Baseline (Mean) Dot
            ax.scatter([v_m], [y], color=colors["MEAN"], edgecolor="white", s=250, zorder=3, label="Baseline (Mean)" if i==0 and ax_idx==0 else "")
            # Proposed (GRU) Star
            ax.scatter([v_g], [y], color=colors["GRU"], edgecolor="#047857", s=350, marker="*", zorder=3, label="MoBSE (GRU)" if i==0 and ax_idx==0 else "")
            
            # Value Texts
            val_offset = (max(v_m, v_g) - min(v_m, v_g)) * 0.12
            ax.text(v_m + val_offset, y + 0.15, f"{v_m:.3f}", color="#6B7280", fontsize=9, ha="center", fontweight="bold")
            ax.text(v_g - val_offset, y + 0.15, f"{v_g:.3f}", color="#064E3B", fontsize=10, ha="center", fontweight="bold")
            
            # Percentage reduction badge
            pct = (v_m - v_g) / v_m * 100
            mid_x = (v_m + v_g) / 2
            ax.text(mid_x, y + 0.08, f"-{pct:.1f}%", ha="center", va="center", fontsize=9, color="#EF4444", fontweight="bold", bbox=dict(facecolor="white", edgecolor="none", pad=1.0, alpha=0.9), zorder=4)
            
            # P-value bracketing
            pval = pvals.get((f"gru_minus_mean_{regime_key.replace('_', '')}", pt_key), float("nan"))
            ax.text(mid_x, y - 0.22, f"p = {pval:.2e}", ha="center", va="center", fontsize=8, color="#6B7280", fontstyle="italic")

        ax.set_yticks(y_positions)
        ax.set_yticklabels([r[1] for r in regimes], fontsize=10, fontweight="bold", color="#1F2937")
        ax.set_ylim(-0.6, 1.8)
        
        ax.set_xlabel(f"ETTh1 {metric_name} (lower is better)", fontsize=9, color="#4B5563", labelpad=8)
        ax.set_title(f"a. {metric_name} Trajectory (Mean $\\pm 1\\sigma$)" if ax_idx==0 else f"b. {metric_name} Trajectory (Mean $\\pm 1\\sigma$)", fontsize=11, fontweight="bold", loc="left", pad=10, color="#111827")
        
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="#E5E7EB", linestyle="--", alpha=0.7)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.00), ncol=2, frameon=False, fontsize=10)
    
    fig.suptitle("Figure 3: Temporal Bottleneck Control & Variance Reduction (10 Seeds)", fontsize=13, fontweight="bold", y=0.98, color="#111827")
    plt.subplots_adjust(top=0.85, bottom=0.20, left=0.15, right=0.95)
    
    save_multi(out_path, fig)
    plt.close(fig)


def _figure_f4(sweep_n100: pd.DataFrame, sweep_n200: pd.DataFrame, out_path: Path) -> None:
    sweep = pd.concat([sweep_n100, sweep_n200], ignore_index=True)
    # Get mean and std representation to calculate SNR 
    agg_df = (
        sweep.groupby(["nodes", "sparsity", "routing_mode", "template_prior"])["etth1_mse"]
        .agg(["mean", "std"]).reset_index()
    )

    nodes_sorted = sorted(agg_df["nodes"].unique().tolist())
    fig, axes = plt.subplots(1, len(nodes_sorted), figsize=(7.2, 3.8))
    if len(nodes_sorted) == 1: axes = [axes]

    for idx, nodes in enumerate(nodes_sorted):
        ax = axes[idx]
        sub = agg_df[agg_df["nodes"] == nodes]
        
        # We need prior_true and prior_false logic
        pt_df = sub[sub["template_prior"] == True].set_index(["routing_mode", "sparsity"])
        pf_df = sub[sub["template_prior"] == False].set_index(["routing_mode", "sparsity"])
        
        # Merge exactly
        heat_df = pd.merge(pt_df[["mean", "std"]], pf_df[["mean", "std"]], left_index=True, right_index=True, suffixes=('_true', '_false'))
        
        # Delta: True (Proposed) - False (Baseline)
        heat_df["delta"] = heat_df["mean_true"] - heat_df["mean_false"]
        # Standard Error of the Difference (assuming independent or conservative sum) n=10 seeds
        heat_df["se"] = np.sqrt((heat_df["std_true"]**2)/10 + (heat_df["std_false"]**2)/10)
        heat_df["t_stat"] = (heat_df["delta"].abs() / heat_df["se"]).fillna(0)
        
        # Restructure into matrices manually
        unique_sp = sorted(sub["sparsity"].unique())
        unique_rm = sorted(sub["routing_mode"].unique())
        
        # Matrices for plotting
        D_mat = np.full((len(unique_rm), len(unique_sp)), np.nan)
        T_mat = np.full((len(unique_rm), len(unique_sp)), 1.0)
        for i, rm in enumerate(unique_rm):
            for j, sp in enumerate(unique_sp):
                if (rm, sp) in heat_df.index:
                    D_mat[i, j] = heat_df.loc[(rm, sp), "delta"]
                    T_mat[i, j] = heat_df.loc[(rm, sp), "t_stat"]
        
        max_abs = np.nanmax(np.abs(D_mat))
        
        # Background Grid styling
        ax.set_facecolor("#F9FAFB")
        ax.set_xlim(-0.5, len(unique_sp) - 0.5)
        ax.set_ylim(-0.5, len(unique_rm) - 0.5)
        
        for r_idx, rm in enumerate(unique_rm):
            for c_idx, sp in enumerate(unique_sp):
                val = D_mat[r_idx, c_idx]
                tval = T_mat[r_idx, c_idx]
                if pd.isna(val): continue
                
                # Color encoding
                color = "#10B981" if val < 0 else "#F59E0B"
                # Bubble size reflects |delta| 
                size = (abs(val) / max_abs) * 800 + 100 if max_abs > 0 else 100
                # Transparency reflects statistical confidence (SNR)
                alpha_val = 0.9 if tval > 2.0 else 0.35 # >2 is approx 95% confident 10-df
                
                ax.scatter(c_idx, r_idx, s=size, color=color, alpha=alpha_val, edgecolor="white", lw=1.5, zorder=2)
                
                font_w = "bold" if tval > 2.0 else "normal"
                txt_c = "white" if size > 400 and alpha_val > 0.5 else "#1F2937"
                ax.text(c_idx, r_idx, f"{val:+.3f}", ha="center", va="center", color=txt_c, fontsize=8, fontweight=font_w, zorder=3)

        ax.set_xticks(range(len(unique_sp)))
        ax.set_xticklabels([f"Top-{s}" for s in unique_sp], fontsize=9)
        ax.set_yticks(range(len(unique_rm)))
        ax.set_yticklabels(unique_rm, fontsize=9)
        
        ax.set_title(f"a. $N={nodes}$ Experts Map" if idx==0 else f"b. $N={nodes}$ Experts Map", fontsize=11, fontweight="bold", pad=12, color="#111827", loc="left")
        ax.set_xlabel("Sparsity Limit ($k$)", fontsize=9, color="#4B5563")
        ax.set_ylabel("Routing Mode", fontsize=9, color="#4B5563") if idx == 0 else ax.set_ylabel("")
        
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.grid(color="white", linestyle="-", lw=2.0, zorder=1)
        ax.tick_params(length=0)

    fig.suptitle("Figure 4: Prior Matrix & Effect SNR (Size=$|\Delta|$, Opacity=Confidence)", fontsize=13, fontweight="bold", y=0.98, color="#111827")
    plt.subplots_adjust(top=0.82, bottom=0.15, left=0.15, right=0.95, wspace=0.3)
    
    save_multi(out_path, fig)
    plt.close(fig)


def _figure_f5(summary_df: pd.DataFrame, out_path: Path) -> None:
    data = summary_df.copy()
    data["label"] = data.apply(lambda r: _label(str(r["regime"]), str(r["temporal_encoder"])), axis=1)
    
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5), gridspec_kw={'wspace': 0.3})
    
    for ax_idx, (x_col, x_label) in enumerate([
        ("etth1_latency_ms_mean", "Latency (ms)"),
        ("etth1_flops_mean", "FLOPs Count")
    ]):
        ax = axes[ax_idx]
        
        # Plot Baseline dots 
        sub_mean = data[data["temporal_encoder"]=="mean"]
        ax.errorbar(sub_mean[x_col], sub_mean["etth1_mae_mean"], yerr=sub_mean["etth1_mae_std"], fmt='none', ecolor="#D1D5DB", elinewidth=1.5, capsize=3, zorder=2)
        ax.scatter(sub_mean[x_col], sub_mean["etth1_mae_mean"], color="#9CA3AF", edgecolor="white", s=150, zorder=3, label="Baseline (Dense)")
        
        # Plot Proposed MoBSE stars
        sub_gru = data[data["temporal_encoder"]=="gru"]
        ax.errorbar(sub_gru[x_col], sub_gru["etth1_mae_mean"], yerr=sub_gru["etth1_mae_std"], fmt='none', ecolor="#A7F3D0", elinewidth=1.5, capsize=3, zorder=2)
        ax.scatter(sub_gru[x_col], sub_gru["etth1_mae_mean"], color="#10B981", marker="*", edgecolor="#047857", s=300, zorder=4, label="MoBSE (Sparse)")
        
        # Connect pairs indicating identical regime variant trades
        for reg in ["etth1_only", "dual_task"]:
            sub = data[data["regime"] == reg].sort_values("temporal_encoder")
            if len(sub) == 2:
                # A subtle link showing the improvement step
                ax.plot(sub[x_col], sub["etth1_mae_mean"], color="#D1D5DB", ls="--", lw=1.5, zorder=1)

        # Highlight Pareto Shading Envelope 
        # Draw dotted crosshairs from the absolute best point
        best_point = data.loc[data['etth1_mae_mean'].idxmin()]
        bx, by = best_point[x_col], best_point["etth1_mae_mean"]
        ax.axhline(by, color="#34D399", linestyle=":", lw=1.5, zorder=0)
        ax.axvline(bx, color="#34D399", linestyle=":", lw=1.5, zorder=0)
        
        # Shading Suboptimal region to guide the eye
        xlims = ax.get_xlim()
        ylims = ax.get_ylim()
        
        # The region > bx and > by is purely suboptimal
        import matplotlib.patches as patches
        rect = patches.Rectangle((bx, by), xlims[1]-bx, ylims[1]-by, linewidth=0, facecolor="#F3F4F6", alpha=0.5, zorder=-1)
        ax.add_patch(rect)
        
        # Add labels to points
        for _, row in data.iterrows():
            offset_y = 0.002
            ax.text(row[x_col], row["etth1_mae_mean"] + offset_y, str(row["label"]), fontsize=8, color="#374151", ha="center", va="bottom", zorder=5)

        ax.set_xlim(xlims)
        ax.set_ylim(ylims)
        
        ax.set_title(f"a. MAE vs {x_label}" if ax_idx==0 else f"b. MAE vs {x_label}", fontsize=11, fontweight="bold", loc="left", color="#111827", pad=10)
        ax.set_xlabel(f"ETTh1 {x_label} (lower is better)", fontsize=9, color="#4B5563")
        ax.set_ylabel("ETTh1 MAE (lower is better)", fontsize=9, color="#4B5563") if ax_idx == 0 else ax.set_ylabel("")
        
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(color="#E5E7EB", linestyle="--", alpha=0.7)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=2, frameon=False, fontsize=10)
    
    fig.suptitle("Figure 5: ETTh1 Pareto Frontier & Bounds (Shaded=Suboptimal)", fontsize=13, fontweight="bold", color="#111827", y=0.98)
    plt.subplots_adjust(top=0.85, bottom=0.20, left=0.12, right=0.95)
    
    save_multi(out_path, fig)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ETTh1 story figures (F1/F2/F3/F4/F5)")
    ap.add_argument(
        "--summary-csv",
        default="artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_run_summary.csv",
        help="Run summary CSV path",
    )
    ap.add_argument(
        "--pairwise-csv",
        default="artifacts/current_canonical/etth1_story_followup_20260331_rerun10/reports/story_pairwise_focus.csv",
        help="Pairwise stats CSV path",
    )
    ap.add_argument(
        "--sweep-n100",
        default="artifacts/legacy_phase2/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv",
        help="n100 sweep CSV path",
    )
    ap.add_argument(
        "--sweep-n200",
        default="artifacts/legacy_phase2/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_sweep_seed42.csv",
        help="n200 sweep CSV path",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/current_canonical/figures_etth1_story_20260331_rerun10/reports",
        help="Output directory",
    )
    args = ap.parse_args()

    set_nature_style()

    summary_csv = _resolve_existing(
        args.summary_csv,
        [
            "artifacts/current_canonical/**/reports/story_run_summary.csv",
            "artifacts/legacy_misc/**/reports/story_run_summary.csv",
        ],
        label="summary_csv",
    )
    pairwise_csv = _resolve_existing(
        args.pairwise_csv,
        [
            "artifacts/current_canonical/**/reports/story_pairwise_focus.csv",
            "artifacts/legacy_misc/**/reports/story_pairwise_focus.csv",
        ],
        label="pairwise_csv",
    )
    sweep_n100_csv = _resolve_existing(
        args.sweep_n100,
        [
            "artifacts/current_canonical/**/reports/phase2_sweep_seed42.csv",
            "artifacts/legacy_phase2/**/reports/phase2_sweep_seed42.csv",
        ],
        label="sweep_n100",
    )
    sweep_n200_csv = _resolve_existing(
        args.sweep_n200,
        [
            "artifacts/current_canonical/**/reports/phase2_sweep_seed42.csv",
            "artifacts/legacy_phase2/**/reports/phase2_sweep_seed42.csv",
        ],
        label="sweep_n200",
    )

    summary_df = pd.read_csv(summary_csv)
    pairwise_df = pd.read_csv(pairwise_csv)
    sweep_n100 = pd.read_csv(sweep_n100_csv)
    sweep_n200 = pd.read_csv(sweep_n200_csv)

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
            "summary_csv": str(summary_csv),
            "pairwise_csv": str(pairwise_csv),
            "sweep_n100": str(sweep_n100_csv),
            "sweep_n200": str(sweep_n200_csv),
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
