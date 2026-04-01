"""
Plotting and visualization utilities for generating publication-quality figures.
"""
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import seaborn as sns


def set_nature_style() -> None:
    """Apply Nature-journal style matplotlib rcParams."""
    plt.style.use("default")
    sns.set_palette("colorblind")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 7.0,
        "legend.title_fontsize": 8.0,
        "axes.linewidth": 0.5,
        "grid.linewidth": 0.5,
        "lines.linewidth": 1.0,
        "lines.markersize": 3.0,
        "patch.linewidth": 0.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.minor.width": 0.5,
        "ytick.minor.width": 0.5,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    })


def save_multi(out_path: str | Path, fig: Optional[plt.Figure] = None) -> None:
    """
    Save the current figure (or specified fig) in both .png and .pdf formats.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    if fig is None:
        plt.savefig(out_path.with_suffix(".pdf"))
        plt.savefig(out_path.with_suffix(".png"))
    else:
        fig.savefig(out_path.with_suffix(".pdf"))
        fig.savefig(out_path.with_suffix(".png"))
