from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _summary_dir(study_id: str) -> Path:
    return Path("artifacts") / f"{study_id}_summary" / "reports"


def _load_sweep(study_id: str) -> pd.DataFrame:
    path = _summary_dir(study_id) / "phase2_sweep_seed42.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing sweep file: {path}")
    df = pd.read_csv(path)
    df["study_id"] = study_id
    df["phase"] = "sweep_seed42"
    return df


def _load_bal3_seed(study_id: str) -> pd.DataFrame:
    path = _summary_dir(study_id) / "phase2_top3_bal3_seed_metrics.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing bal3 seed file: {path}")
    df = pd.read_csv(path)
    df["study_id"] = study_id
    df["phase"] = "bal3_seed"
    return df


def _load_best_run(study_id: str) -> str:
    path = _summary_dir(study_id) / "phase2_top3_bal3_summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing bal3 summary file: {path}")
    df = pd.read_csv(path).sort_values(["os_accuracy_mean", "os_f1_macro_mean"], ascending=False)
    return str(df.iloc[0]["run_id"])


def _eval_file(run_id: str, seed: int) -> Path:
    seed_path = Path("artifacts") / run_id / "logs" / f"eval_seed{seed}_mobse.json"
    if seed_path.exists():
        return seed_path
    return Path("artifacts") / run_id / "logs" / "eval_mobse.json"


def _extract_routing_rows(study_id: str, bal3_seed: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for _, row in bal3_seed.iterrows():
        run_id = str(row["run_id"])
        seed = int(row["seed"])
        path = _eval_file(run_id, seed)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task in ["os", "etth1"]:
            metrics = (payload.get(task) or {}).get("metrics", {})
            usage = metrics.get("routing_usage", [])
            rows.append(
                {
                    "study_id": study_id,
                    "run_id": run_id,
                    "seed": seed,
                    "nodes": int(row["nodes"]),
                    "task": task,
                    "routing_entropy": metrics.get("routing_entropy", float("nan")),
                    "routing_stability": metrics.get("routing_stability", float("nan")),
                    "routing_usage": usage if isinstance(usage, list) else [],
                }
            )
    return pd.DataFrame(rows)


def _scatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    out: Path,
    title: str,
) -> None:
    if df.empty or x not in df.columns or y not in df.columns:
        return
    plt.figure(figsize=(8, 5))
    sns.scatterplot(
        data=df,
        x=x,
        y=y,
        hue="nodes",
        style="template_prior",
        s=90,
        alpha=0.9,
    )
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def _routing_entropy_plot(df: pd.DataFrame, out: Path) -> None:
    if df.empty or "routing_entropy" not in df.columns:
        return
    plt.figure(figsize=(8, 5))
    sns.boxplot(data=df, x="nodes", y="routing_entropy", hue="task")
    plt.title("Routing Entropy by Node Size and Task")
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def _routing_usage_best_plot(df: pd.DataFrame, best_runs: Dict[str, str], out: Path) -> None:
    rows: List[Dict[str, object]] = []
    if df.empty:
        return
    for study_id, run_id in best_runs.items():
        sub = df[(df["study_id"] == study_id) & (df["run_id"] == run_id)]
        for task in ["os", "etth1"]:
            task_sub = sub[sub["task"] == task]
            if task_sub.empty:
                continue
            usage_lists = [u for u in task_sub["routing_usage"].tolist() if isinstance(u, list) and len(u) > 0]
            if not usage_lists:
                continue
            max_len = max(len(u) for u in usage_lists)
            aligned = []
            for usage in usage_lists:
                if len(usage) < max_len:
                    usage = usage + [0.0] * (max_len - len(usage))
                aligned.append(usage)
            mean_usage = pd.DataFrame(aligned).mean(axis=0).tolist()
            for expert_idx, usage_value in enumerate(mean_usage):
                rows.append(
                    {
                        "study_id": study_id,
                        "run_id": run_id,
                        "task": task,
                        "expert": f"E{expert_idx}",
                        "usage": float(usage_value),
                    }
                )

    usage_df = pd.DataFrame(rows)
    if usage_df.empty:
        return

    plt.figure(figsize=(10, 5))
    usage_df["series"] = usage_df["study_id"] + "_" + usage_df["task"]
    sns.barplot(data=usage_df, x="expert", y="usage", hue="series")
    plt.title("Best-Run Expert Usage Distribution")
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Phase-2 figures (tradeoff + routing)")
    ap.add_argument(
        "--study-ids",
        required=True,
        help="Comma-separated study ids, e.g. phase2_n100,phase2_n200",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/phase2_figures_20260314",
        help="Output directory for figures and manifest",
    )
    args = ap.parse_args()

    sns.set_theme(style="whitegrid")
    study_ids = [token.strip() for token in args.study_ids.split(",") if token.strip()]
    if not study_ids:
        raise ValueError("No study ids provided.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sweep_frames: List[pd.DataFrame] = []
    bal3_seed_frames: List[pd.DataFrame] = []
    routing_frames: List[pd.DataFrame] = []
    best_runs: Dict[str, str] = {}

    for study_id in study_ids:
        sweep = _load_sweep(study_id)
        bal3_seed = _load_bal3_seed(study_id)
        routing = _extract_routing_rows(study_id, bal3_seed)
        best_runs[study_id] = _load_best_run(study_id)

        sweep_frames.append(sweep)
        bal3_seed_frames.append(bal3_seed)
        routing_frames.append(routing)

    all_sweep = pd.concat(sweep_frames, ignore_index=True) if sweep_frames else pd.DataFrame()
    all_bal3 = pd.concat(bal3_seed_frames, ignore_index=True) if bal3_seed_frames else pd.DataFrame()
    all_routing = pd.concat(routing_frames, ignore_index=True) if routing_frames else pd.DataFrame()

    path_acc_lat = out_dir / "phase2_tradeoff_accuracy_vs_latency.png"
    path_mse_lat = out_dir / "phase2_tradeoff_mse_vs_latency.png"
    path_acc_flops = out_dir / "phase2_tradeoff_accuracy_vs_flops.png"
    path_routing_entropy = out_dir / "phase2_routing_entropy_by_nodes_task.png"
    path_routing_usage = out_dir / "phase2_routing_usage_best_runs.png"

    _scatter(
        df=all_bal3,
        x="os_latency_ms",
        y="os_accuracy",
        out=path_acc_lat,
        title="OS Accuracy vs OS Latency (bal3 seeds)",
    )
    _scatter(
        df=all_bal3,
        x="etth1_latency_ms",
        y="etth1_mse",
        out=path_mse_lat,
        title="ETTh1 MSE vs ETTh1 Latency (bal3 seeds)",
    )
    _scatter(
        df=all_bal3,
        x="os_flops",
        y="os_accuracy",
        out=path_acc_flops,
        title="OS Accuracy vs FLOPs (bal3 seeds)",
    )
    _routing_entropy_plot(all_routing, path_routing_entropy)
    _routing_usage_best_plot(all_routing, best_runs=best_runs, out=path_routing_usage)

    manifest = {
        "study_ids": study_ids,
        "sources": {
            "sweep_rows": int(len(all_sweep)),
            "bal3_seed_rows": int(len(all_bal3)),
            "routing_rows": int(len(all_routing)),
        },
        "best_runs": best_runs,
        "figures": {
            "accuracy_vs_latency": str(path_acc_lat),
            "mse_vs_latency": str(path_mse_lat),
            "accuracy_vs_flops": str(path_acc_flops),
            "routing_entropy": str(path_routing_entropy),
            "routing_usage_best": str(path_routing_usage),
        },
    }
    manifest_path = out_dir / "phase2_figures_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
