#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

from mobse.viz import save_multi, set_nature_style



def main() -> None:
    out = Path("artifacts/current_canonical/mobse_paper_lock_20260330/figures/Fig1_storyline_framework.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    set_nature_style()

    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.set_axis_off()

    box_style = dict(boxstyle="round,pad=0.6", ec="#2c3e50", lw=2)

    ax.text(
        0.12,
        0.60,
        "Human 'Real' Network\n(complex, noisy, heterogeneous)",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        bbox={**box_style, "fc": "#d9e8fb"},
    )

    ax.text(
        0.50,
        0.60,
        "Yeo-7 Base Template\n(canonical, interpretable scaffold)",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        bbox={**box_style, "fc": "#fef1d8"},
    )

    ax.text(
        0.86,
        0.60,
        "MoBSE Experts\n(specialized routing over base)",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        bbox={**box_style, "fc": "#f8dce6"},
    )

    arrow = dict(arrowstyle="-|>", lw=2.5, color="#2c3e50", shrinkA=8, shrinkB=8)
    ax.annotate("", xy=(0.37, 0.60), xytext=(0.23, 0.60), arrowprops=arrow)
    ax.annotate("", xy=(0.73, 0.60), xytext=(0.57, 0.60), arrowprops=arrow)

    ax.text(
        0.50,
        0.86,
        "Locked Storyline: Real Human Complexity -> Yeo-7 Canonical Base -> MoBSE Expert Specialization",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color="#1f2d3d",
    )

    ax.text(
        0.12,
        0.28,
        "Input Reality",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="#1f2d3d",
    )
    ax.text(
        0.50,
        0.28,
        "Interpretation Coordinate",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="#1f2d3d",
    )
    ax.text(
        0.86,
        0.28,
        "Modeling Mechanism",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="#1f2d3d",
    )

    fig.tight_layout(pad=3.0)
    save_multi(out, fig)
    plt.close(fig)
    print(str(out))


if __name__ == "__main__":
    main()
