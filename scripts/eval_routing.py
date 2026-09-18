#!/usr/bin/env python3
"""Downstream evaluation: routing weight analysis & brain-state interpretability.

Loads trained MoBSE checkpoint(s), runs inference on all-task windows,
and produces:
  1. Per-task routing weight distribution (which expert dominates per task?)
  2. Per-expert mean routing weight heatmap (task × expert)
  3. Routing entropy analysis (task specificity vs. uniform mixing)
  4. Mixed adjacency matrices per task (expert-weighted graph structure)
  5. Expert template visualization (top edges per expert)

Usage:
    # A+B model (all-tasks trained)
    python scripts/eval_routing.py \
        --checkpoint-dir artifacts/20260416_102453/checkpoints \
        --config artifacts/mobse_dfc_piop1_sch100/config_dfc_alltasks_antiovf.yaml \
        --timeseries-dir data/aomic/piop1/timeseries/100 \
        --output-dir artifacts/eval_routing_alltasks

    # A-only model (rest-only trained)
    python scripts/eval_routing.py \
        --checkpoint-dir artifacts/20260416_103427/checkpoints \
        --config artifacts/mobse_dfc_piop1_sch100/config_dfc_antiovf.yaml \
        --timeseries-dir data/aomic/piop1/timeseries/100 \
        --output-dir artifacts/eval_routing_restonly
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Model loading ──────────────────────────────────────────────────────

def load_model_from_checkpoint(
    ckpt_path: Path,
    config_path: Path,
    device: str = "cpu",
) -> torch.nn.Module:
    """Load trained MoBSE model from checkpoint + config."""
    from mobse.config import load_config
    from mobse.templates.builder import load_template_bank
    from mobse.models import build_model

    cfg = load_config(config_path)
    tb_path = cfg.model.template_bank_path
    states = cfg.data.os.states
    template_np = load_template_bank(tb_path, states)
    template_bank = torch.from_numpy(template_np).float()
    model = build_model(cfg, template_bank)

    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    model.to(device)

    log.info("Loaded model from %s (seed=%s)", ckpt_path, ckpt.get("seed"))
    return model, cfg


# ── Window extraction ──────────────────────────────────────────────────

def extract_task_windows(
    timeseries_dir: Path,
    tasks: List[str],
    window_len: int = 64,
    stride: int = 16,
    min_timepoints: int = 100,
    max_windows_per_task: int = 2000,
) -> Dict[str, np.ndarray]:
    """Extract windows per task. Returns {task_name: [N, window_len, nodes]}."""
    task_windows = {}

    subject_dirs = sorted([d for d in timeseries_dir.iterdir() if d.is_dir()])

    for task in tasks:
        windows = []
        for subj_dir in subject_dirs:
            npy_path = subj_dir / f"{task}.npy"
            if not npy_path.exists():
                continue
            ts = np.load(npy_path).astype(np.float32)
            if ts.shape[0] < min_timepoints:
                continue

            for start in range(0, ts.shape[0] - window_len + 1, stride):
                windows.append(ts[start:start + window_len])

            if len(windows) >= max_windows_per_task:
                break

        if windows:
            task_windows[task] = np.stack(windows[:max_windows_per_task], axis=0)
            log.info("  %s: %d windows", task, len(task_windows[task]))

    return task_windows


# ── Routing analysis ───────────────────────────────────────────────────

@torch.no_grad()
def collect_routing_weights(
    model: torch.nn.Module,
    task_windows: Dict[str, np.ndarray],
    device: str = "cpu",
    batch_size: int = 64,
) -> Dict[str, np.ndarray]:
    """Run inference and collect routing weights per task.

    Returns {task_name: [N, num_experts]}.
    """
    model.eval()
    routing_per_task = {}

    for task_name, windows in task_windows.items():
        all_routing = []
        n = windows.shape[0]

        for i in range(0, n, batch_size):
            x = torch.from_numpy(windows[i:i + batch_size]).to(device)
            out = model(x, task="os")
            all_routing.append(out["routing_weights"].cpu().numpy())

        routing_per_task[task_name] = np.concatenate(all_routing, axis=0)
        log.info("  %s: routing shape %s", task_name, routing_per_task[task_name].shape)

    return routing_per_task


def compute_routing_stats(
    routing_per_task: Dict[str, np.ndarray],
    k: int,
) -> Dict:
    """Compute summary statistics from routing weights."""
    stats = {}
    expert_names = [f"dfc_{i}" for i in range(k)]

    for task, routing in routing_per_task.items():
        mean_weights = routing.mean(axis=0)  # [k]
        std_weights = routing.std(axis=0)
        dominant_expert = int(np.argmax(mean_weights))

        # Entropy: low = specialized, high = uniform
        eps = 1e-8
        entropy = -np.sum(routing * np.log(routing + eps), axis=1).mean()
        max_entropy = np.log(k)
        normalized_entropy = entropy / max_entropy

        stats[task] = {
            "mean_weights": {expert_names[i]: float(mean_weights[i]) for i in range(k)},
            "std_weights": {expert_names[i]: float(std_weights[i]) for i in range(k)},
            "dominant_expert": expert_names[dominant_expert],
            "entropy": float(entropy),
            "normalized_entropy": float(normalized_entropy),
            "n_windows": int(routing.shape[0]),
        }

    return stats


# ── Mixed adjacency analysis ──────────────────────────────────────────

@torch.no_grad()
def compute_task_mean_adjacency(
    model: torch.nn.Module,
    routing_per_task: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    """Compute mean mixed adjacency matrix per task.

    adj_task = mean_over_samples( sum_e(routing[e] * template[e]) )
    """
    bank = model.template_bank.cpu().numpy()  # [k, nodes, nodes]
    task_adj = {}

    for task, routing in routing_per_task.items():
        # routing: [N, k], bank: [k, nodes, nodes]
        mean_routing = routing.mean(axis=0)  # [k]
        adj = np.einsum("e,enm->nm", mean_routing, bank)
        task_adj[task] = adj

    return task_adj


# ── Visualization ──────────────────────────────────────────────────────

def plot_routing_heatmap(
    stats: Dict,
    k: int,
    output_path: Path,
    title: str = "Task × Expert Routing Weights",
) -> None:
    """Heatmap: rows=tasks, cols=experts, values=mean routing weight."""
    tasks = list(stats.keys())
    expert_names = [f"dfc_{i}" for i in range(k)]
    matrix = np.zeros((len(tasks), k))

    for i, task in enumerate(tasks):
        for j in range(k):
            matrix[i, j] = stats[task]["mean_weights"][expert_names[j]]

    fig, ax = plt.subplots(figsize=(max(4, k * 1.5), max(3, len(tasks) * 0.6)))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto", vmin=0)

    ax.set_xticks(range(k))
    ax.set_xticklabels(expert_names, fontsize=9)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(tasks, fontsize=9)
    ax.set_xlabel("Expert")
    ax.set_ylabel("Task")
    ax.set_title(title, fontsize=11)

    # Annotate cells
    for i in range(len(tasks)):
        for j in range(k):
            color = "white" if matrix[i, j] > 0.5 else "black"
            ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center",
                    fontsize=9, color=color)

    plt.colorbar(im, ax=ax, label="Mean routing weight")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Saved routing heatmap: %s", output_path)


def plot_entropy_bar(
    stats: Dict,
    output_path: Path,
    title: str = "Routing Entropy by Task",
) -> None:
    """Bar chart of normalized routing entropy per task."""
    tasks = list(stats.keys())
    entropies = [stats[t]["normalized_entropy"] for t in tasks]

    fig, ax = plt.subplots(figsize=(max(4, len(tasks) * 0.8), 3.5))
    colors = plt.cm.Set2(np.linspace(0, 1, len(tasks)))
    bars = ax.bar(tasks, entropies, color=colors, edgecolor="gray", linewidth=0.5)

    ax.set_ylabel("Normalized Entropy (0=specialized, 1=uniform)")
    ax.set_title(title, fontsize=11)
    ax.set_ylim(0, 1.1)
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5, label="Uniform")

    for bar, v in zip(bars, entropies):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{v:.3f}", ha="center", fontsize=8)

    plt.xticks(rotation=30, ha="right", fontsize=9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Saved entropy chart: %s", output_path)


def plot_routing_distributions(
    routing_per_task: Dict[str, np.ndarray],
    k: int,
    output_path: Path,
    title: str = "Routing Weight Distributions",
) -> None:
    """Violin/box plots of routing weight distributions per task per expert."""
    tasks = list(routing_per_task.keys())
    n_tasks = len(tasks)
    expert_names = [f"dfc_{i}" for i in range(k)]

    fig, axes = plt.subplots(1, k, figsize=(k * 3.5, 4), sharey=True)
    if k == 1:
        axes = [axes]

    for j in range(k):
        ax = axes[j]
        data = [routing_per_task[t][:, j] for t in tasks]
        bp = ax.boxplot(data, labels=tasks, patch_artist=True, widths=0.6)
        colors = plt.cm.Set2(np.linspace(0, 1, n_tasks))
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_title(expert_names[j], fontsize=10)
        ax.set_ylabel("Routing weight" if j == 0 else "")
        ax.tick_params(axis="x", rotation=30)

    fig.suptitle(title, fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Saved routing distributions: %s", output_path)


def plot_expert_templates(
    model: torch.nn.Module,
    k: int,
    output_path: Path,
    title: str = "Expert Template Banks",
) -> None:
    """Visualize each expert's template adjacency matrix."""
    bank = model.template_bank.cpu().numpy()  # [k, nodes, nodes]

    fig, axes = plt.subplots(1, k, figsize=(k * 3.5, 3.5))
    if k == 1:
        axes = [axes]

    for i in range(k):
        ax = axes[i]
        vmax = np.max(np.abs(bank[i]))
        im = ax.imshow(bank[i], cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="equal")
        ax.set_title(f"dfc_{i}", fontsize=10)
        ax.set_xlabel("ROI")
        ax.set_ylabel("ROI" if i == 0 else "")
        plt.colorbar(im, ax=ax, fraction=0.046)

    fig.suptitle(title, fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Saved expert templates: %s", output_path)


def plot_task_mean_adjacency(
    task_adj: Dict[str, np.ndarray],
    output_path: Path,
    title: str = "Task-Specific Mixed Adjacency",
) -> None:
    """Visualize mean mixed adjacency matrix per task."""
    tasks = list(task_adj.keys())
    n = len(tasks)
    fig, axes = plt.subplots(1, n, figsize=(n * 3.5, 3.5))
    if n == 1:
        axes = [axes]

    for i, task in enumerate(tasks):
        ax = axes[i]
        adj = task_adj[task]
        vmax = np.max(np.abs(adj))
        im = ax.imshow(adj, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="equal")
        ax.set_title(task, fontsize=10)
        ax.set_xlabel("ROI")
        ax.set_ylabel("ROI" if i == 0 else "")
        plt.colorbar(im, ax=ax, fraction=0.046)

    fig.suptitle(title, fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Saved task mean adjacency: %s", output_path)


def plot_adj_difference(
    task_adj: Dict[str, np.ndarray],
    output_path: Path,
    reference_task: str = "restingstate",
    title: str = "Task − Rest Adjacency Difference",
) -> None:
    """Show how each task's mixed adjacency differs from resting state."""
    if reference_task not in task_adj:
        log.warning("Reference task '%s' not found, skipping diff plot.", reference_task)
        return

    ref = task_adj[reference_task]
    other_tasks = [t for t in task_adj if t != reference_task]
    if not other_tasks:
        return

    n = len(other_tasks)
    fig, axes = plt.subplots(1, n, figsize=(n * 3.5, 3.5))
    if n == 1:
        axes = [axes]

    for i, task in enumerate(other_tasks):
        ax = axes[i]
        diff = task_adj[task] - ref
        vmax = np.max(np.abs(diff))
        if vmax < 1e-8:
            vmax = 1.0
        im = ax.imshow(diff, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="equal")
        ax.set_title(f"{task} − {reference_task}", fontsize=9)
        ax.set_xlabel("ROI")
        ax.set_ylabel("ROI" if i == 0 else "")
        plt.colorbar(im, ax=ax, fraction=0.046)

    fig.suptitle(title, fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Saved adjacency difference: %s", output_path)


# ── Main ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MoBSE routing weight analysis")
    parser.add_argument("--checkpoint-dir", type=str, required=True,
                        help="Directory with model_seed*_best.pt files")
    parser.add_argument("--config", type=str, required=True,
                        help="Training config YAML")
    parser.add_argument("--timeseries-dir", type=str, required=True,
                        help="data/aomic/piop1/timeseries/100")
    parser.add_argument("--tasks", type=str, nargs="*",
                        default=["restingstate", "anticipation", "emomatching",
                                 "faces", "gstroop", "workingmemory"])
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--seed", type=int, default=42,
                        help="Which seed checkpoint to use (default: 42)")
    parser.add_argument("--window-len", type=int, default=64)
    parser.add_argument("--stride", type=int, default=64,
                        help="Stride for eval windows (default: 64, no overlap)")
    parser.add_argument("--max-windows-per-task", type=int, default=2000)
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load model
    ckpt_path = Path(args.checkpoint_dir) / f"model_seed{args.seed}_best.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    model, cfg = load_model_from_checkpoint(ckpt_path, args.config, args.device)
    k = cfg.model.num_experts
    log.info("Model: num_experts=%d, num_nodes=%d, hidden_dim=%d",
             k, cfg.model.num_nodes, cfg.model.hidden_dim)

    # Extract windows per task
    log.info("Extracting windows from %s...", args.timeseries_dir)
    task_windows = extract_task_windows(
        Path(args.timeseries_dir),
        tasks=args.tasks,
        window_len=args.window_len,
        stride=args.stride,
        max_windows_per_task=args.max_windows_per_task,
    )

    # Collect routing weights
    log.info("Running inference...")
    routing_per_task = collect_routing_weights(
        model, task_windows, device=args.device,
    )

    # Compute stats
    stats = compute_routing_stats(routing_per_task, k)

    # Mixed adjacency
    task_adj = compute_task_mean_adjacency(model, routing_per_task)

    # Save numerical results
    with open(out_dir / "routing_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    log.info("Saved routing_stats.json")

    # Save routing arrays for further analysis
    np.savez_compressed(
        out_dir / "routing_weights.npz",
        **{f"routing_{task}": arr for task, arr in routing_per_task.items()},
    )
    np.savez_compressed(
        out_dir / "task_adjacency.npz",
        **{f"adj_{task}": arr for task, arr in task_adj.items()},
    )

    # ── Plots ──
    plot_routing_heatmap(stats, k, out_dir / "fig_routing_heatmap.png")
    plot_entropy_bar(stats, out_dir / "fig_routing_entropy.png")
    plot_routing_distributions(routing_per_task, k, out_dir / "fig_routing_distributions.png")
    plot_expert_templates(model, k, out_dir / "fig_expert_templates.png")
    plot_task_mean_adjacency(task_adj, out_dir / "fig_task_adjacency.png")
    plot_adj_difference(task_adj, out_dir / "fig_adj_diff_vs_rest.png")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("  MoBSE Routing Analysis Complete")
    print("=" * 60)
    for task, s in stats.items():
        dom = s["dominant_expert"]
        ent = s["normalized_entropy"]
        wts = " | ".join(f"{e}: {w:.3f}" for e, w in s["mean_weights"].items())
        print(f"  {task:20s}  dominant={dom}  entropy={ent:.3f}  [{wts}]")
    print(f"\n  Output: {out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
