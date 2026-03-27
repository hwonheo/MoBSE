from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _load_raw(run_id: str) -> pd.DataFrame:
    path = Path("artifacts") / run_id / "reports" / "raw_metrics.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing raw metrics file: {path}")
    df = pd.read_csv(path)
    if "source" not in df.columns or "task" not in df.columns:
        raise ValueError(f"Unexpected raw metrics schema: {path}")
    df["seed"] = df["source"].str.extract(r"eval_seed(\d+)_")[0].astype(int)
    df["run_id"] = run_id
    return df


def _run_label(run_id: str) -> str:
    if "openneuro_usable600" in run_id:
        return "strict_usable600"
    if "openneuro600" in run_id:
        return "raw600"
    return re.sub(r"[^a-zA-Z0-9_]+", "_", run_id)


def _save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def _plot_f1_gate_summary(plan_manifest: Path, prepare_log: Path, out_path: Path) -> Dict[str, object]:
    if not plan_manifest.is_file() or not prepare_log.is_file():
        return {
            "path": str(out_path),
            "generated": False,
            "reason": "plan_manifest or prepare_log missing",
        }

    plan = json.loads(plan_manifest.read_text(encoding="utf-8"))
    prep = json.loads(prepare_log.read_text(encoding="utf-8"))
    projected = int(plan.get("projected_usable_keep_total", 0))
    target = int(prep.get("usable_target_subjects", prep.get("requested_subjects", 0)))
    accepted = int(prep.get("accepted_subjects", 0))
    rejected = int(prep.get("qc_summary", {}).get("rejected_total", 0))

    labels = ["projected_keep", "target", "accepted"]
    values = [projected, target, accepted]
    colors = ["#4c78a8", "#f58518", "#54a24b"]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel("subjects")
    ax.set_title("F1. Strict-Usable Gate Summary")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 2, str(value), ha="center", va="bottom")
    ax.text(
        0.98,
        0.02,
        f"rejected={rejected}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
    )
    _save_figure(fig, out_path)
    return {"path": str(out_path), "generated": True}


def _plot_f2_dataset_contribution(prepare_log: Path, out_path: Path) -> Dict[str, object]:
    if not prepare_log.is_file():
        return {"path": str(out_path), "generated": False, "reason": "prepare_log missing"}

    prep = json.loads(prepare_log.read_text(encoding="utf-8"))
    accepted_by_dataset = prep.get("qc_summary", {}).get("accepted_by_dataset", {})
    if not accepted_by_dataset:
        return {"path": str(out_path), "generated": False, "reason": "accepted_by_dataset missing"}

    df = (
        pd.DataFrame(
            [{"dataset_id": k, "accepted_count": int(v)} for k, v in accepted_by_dataset.items()]
        )
        .sort_values("accepted_count", ascending=True)
        .reset_index(drop=True)
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(df["dataset_id"], df["accepted_count"], color="#4c78a8")
    ax.set_xlabel("accepted subjects")
    ax.set_title("F2. Accepted Subjects by Dataset")
    for i, v in enumerate(df["accepted_count"].tolist()):
        ax.text(v + 1, i, str(v), va="center")
    _save_figure(fig, out_path)
    return {"path": str(out_path), "generated": True}


def _paired_metric_plot(
    ax: plt.Axes,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    task: str,
    metric: str,
    label_a: str,
    label_b: str,
    title: str,
) -> None:
    sub_a = df_a[df_a["task"] == task][["seed", metric]].rename(columns={metric: "a"})
    sub_b = df_b[df_b["task"] == task][["seed", metric]].rename(columns={metric: "b"})
    merged = sub_a.merge(sub_b, on="seed", how="inner").sort_values("seed")
    if merged.empty:
        ax.set_title(f"{title} (no data)")
        return

    for _, row in merged.iterrows():
        ax.plot([0, 1], [row["a"], row["b"]], color="#bbbbbb", linewidth=1, alpha=0.8)
        ax.scatter([0, 1], [row["a"], row["b"]], color="#666666", s=16)

    mean_a = float(merged["a"].mean())
    std_a = float(merged["a"].std(ddof=1)) if len(merged) > 1 else 0.0
    mean_b = float(merged["b"].mean())
    std_b = float(merged["b"].std(ddof=1)) if len(merged) > 1 else 0.0
    ax.errorbar([0], [mean_a], yerr=[std_a], fmt="o", color="#1f77b4", capsize=4, label=f"{label_a} mean+/-std")
    ax.errorbar([1], [mean_b], yerr=[std_b], fmt="o", color="#d62728", capsize=4, label=f"{label_b} mean+/-std")
    ax.set_xticks([0, 1], [label_a, label_b])
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)


def _plot_f3_os_metrics(df_a: pd.DataFrame, df_b: pd.DataFrame, label_a: str, label_b: str, out_path: Path) -> Dict[str, object]:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    _paired_metric_plot(
        ax=axes[0],
        df_a=df_a,
        df_b=df_b,
        task="os",
        metric="metric_accuracy",
        label_a=label_a,
        label_b=label_b,
        title="OS Accuracy",
    )
    _paired_metric_plot(
        ax=axes[1],
        df_a=df_a,
        df_b=df_b,
        task="os",
        metric="metric_f1_macro",
        label_a=label_a,
        label_b=label_b,
        title="OS Macro-F1",
    )
    axes[1].legend(loc="best", fontsize=8)
    fig.suptitle("F3. OS Metrics (Paired Seeds)")
    _save_figure(fig, out_path)
    return {"path": str(out_path), "generated": True}


def _plot_f4_etth1_metrics(
    df_a: pd.DataFrame, df_b: pd.DataFrame, label_a: str, label_b: str, out_path: Path
) -> Dict[str, object]:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    _paired_metric_plot(
        ax=axes[0],
        df_a=df_a,
        df_b=df_b,
        task="etth1",
        metric="metric_mae",
        label_a=label_a,
        label_b=label_b,
        title="ETTh1 MAE",
    )
    _paired_metric_plot(
        ax=axes[1],
        df_a=df_a,
        df_b=df_b,
        task="etth1",
        metric="metric_mse",
        label_a=label_a,
        label_b=label_b,
        title="ETTh1 MSE",
    )
    axes[1].legend(loc="best", fontsize=8)
    fig.suptitle("F4. ETTh1 Metrics (Paired Seeds)")
    _save_figure(fig, out_path)
    return {"path": str(out_path), "generated": True}


def _plot_f5_efficiency(df_a: pd.DataFrame, df_b: pd.DataFrame, label_a: str, label_b: str, out_path: Path) -> Dict[str, object]:
    rows: List[Dict[str, object]] = []
    for run_label, df in [(label_a, df_a), (label_b, df_b)]:
        for task in ["os", "etth1"]:
            sub = df[df["task"] == task]
            rows.append(
                {
                    "run": run_label,
                    "task": task,
                    "latency_mean": float(sub["profile_latency_ms_mean"].mean()),
                    "latency_std": float(sub["profile_latency_ms_mean"].std(ddof=1)) if len(sub) > 1 else 0.0,
                    "flops_mean": float(sub["profile_flops"].mean()),
                }
            )
    eff = pd.DataFrame(rows)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    task_order = ["os", "etth1"]
    x = np.arange(len(task_order))
    width = 0.35

    a_vals = eff[eff["run"] == label_a].set_index("task").loc[task_order]
    b_vals = eff[eff["run"] == label_b].set_index("task").loc[task_order]

    axes[0].bar(x - width / 2, a_vals["latency_mean"], width, yerr=a_vals["latency_std"], capsize=4, label=label_a)
    axes[0].bar(x + width / 2, b_vals["latency_mean"], width, yerr=b_vals["latency_std"], capsize=4, label=label_b)
    axes[0].set_xticks(x, task_order)
    axes[0].set_ylabel("latency (ms)")
    axes[0].set_title("Latency")
    axes[0].legend(loc="best", fontsize=8)

    axes[1].bar(x - width / 2, a_vals["flops_mean"], width, label=label_a)
    axes[1].bar(x + width / 2, b_vals["flops_mean"], width, label=label_b)
    axes[1].set_xticks(x, task_order)
    axes[1].set_ylabel("FLOPs")
    axes[1].set_title("FLOPs")
    axes[1].legend(loc="best", fontsize=8)
    if np.allclose(a_vals["flops_mean"].to_numpy(), b_vals["flops_mean"].to_numpy()):
        axes[1].text(0.98, 0.02, "FLOPs are identical", transform=axes[1].transAxes, ha="right", va="bottom", fontsize=9)

    fig.suptitle("F5. Efficiency Comparison")
    _save_figure(fig, out_path)
    return {"path": str(out_path), "generated": True}


def _write_captions(out_path: Path, label_a: str, label_b: str) -> None:
    text = "\n".join(
        [
            "# Figure Captions",
            "",
            f"- **F1 (`fig_f1_gate_summary.png`)**: Strict-usable gate summary (projected keep, target, accepted).",
            f"- **F2 (`fig_f2_dataset_contribution.png`)**: Accepted subject contributions by dataset.",
            f"- **F3 (`fig_f3_os_metrics.png`)**: Paired-seed OS accuracy and macro-F1 (`{label_a}` vs `{label_b}`).",
            f"- **F4 (`fig_f4_etth1_metrics.png`)**: Paired-seed ETTh1 MAE and MSE (`{label_a}` vs `{label_b}`).",
            f"- **F5 (`fig_f5_efficiency.png`)**: Latency and FLOPs comparison (`{label_a}` vs `{label_b}`).",
            "",
        ]
    )
    out_path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate strict-usable OpenNeuro figure package")
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--plan-manifest", default="")
    ap.add_argument("--prepare-log", default="")
    ap.add_argument("--out-dir", default="artifacts/figures_openneuro_usable600_20260327/reports")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_manifest_path = Path(args.plan_manifest) if args.plan_manifest else Path("__missing_plan_manifest__")
    prepare_log_path = Path(args.prepare_log) if args.prepare_log else Path("__missing_prepare_log__")

    df_a = _load_raw(args.run_a)
    df_b = _load_raw(args.run_b)
    label_a = _run_label(args.run_a)
    label_b = _run_label(args.run_b)

    metric_table = pd.concat([df_a, df_b], ignore_index=True)
    metric_table_path = out_dir / "figure_metrics_table.csv"
    metric_table.to_csv(metric_table_path, index=False)

    figure_results: List[Dict[str, object]] = []
    figure_results.append(
        _plot_f1_gate_summary(
            plan_manifest=plan_manifest_path,
            prepare_log=prepare_log_path,
            out_path=out_dir / "fig_f1_gate_summary.png",
        )
    )
    figure_results.append(_plot_f2_dataset_contribution(prepare_log=prepare_log_path, out_path=out_dir / "fig_f2_dataset_contribution.png"))
    figure_results.append(_plot_f3_os_metrics(df_a=df_a, df_b=df_b, label_a=label_a, label_b=label_b, out_path=out_dir / "fig_f3_os_metrics.png"))
    figure_results.append(
        _plot_f4_etth1_metrics(df_a=df_a, df_b=df_b, label_a=label_a, label_b=label_b, out_path=out_dir / "fig_f4_etth1_metrics.png")
    )
    figure_results.append(_plot_f5_efficiency(df_a=df_a, df_b=df_b, label_a=label_a, label_b=label_b, out_path=out_dir / "fig_f5_efficiency.png"))

    captions_path = out_dir / "figure_captions.md"
    _write_captions(captions_path, label_a=label_a, label_b=label_b)

    manifest = {
        "run_a": args.run_a,
        "run_b": args.run_b,
        "label_a": label_a,
        "label_b": label_b,
        "plan_manifest": args.plan_manifest,
        "prepare_log": args.prepare_log,
        "figure_metrics_table": str(metric_table_path),
        "captions": str(captions_path),
        "figures": figure_results,
    }
    manifest_path = out_dir / "figure_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
