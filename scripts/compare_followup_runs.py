from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.stats import ttest_rel, wilcoxon


METRICS = [
    ("os", "metric_accuracy"),
    ("os", "metric_f1_macro"),
    ("os", "profile_latency_ms_mean"),
    ("os", "profile_flops"),
    ("etth1", "metric_mae"),
    ("etth1", "metric_mse"),
    ("etth1", "profile_latency_ms_mean"),
    ("etth1", "profile_flops"),
]


def _load_raw(run_id: str) -> pd.DataFrame:
    path = Path("artifacts") / run_id / "reports" / "raw_metrics.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing raw metrics file: {path}")
    df = pd.read_csv(path)
    if "source" not in df.columns or "task" not in df.columns:
        raise ValueError(f"Unexpected raw metrics schema: {path}")
    df["seed"] = df["source"].str.extract(r"eval_seed(\d+)_")[0].astype(int)
    return df


def _cohen_dz(diff: np.ndarray) -> float:
    if diff.size < 2:
        return float("nan")
    denom = float(np.std(diff, ddof=1))
    if denom == 0.0:
        return float("inf") if float(np.mean(diff)) != 0.0 else 0.0
    return float(np.mean(diff) / denom)


def _summary_row(run_id: str, df: pd.DataFrame, task: str, metric: str) -> Dict[str, object]:
    sub = df[df["task"] == task][["seed", metric]].dropna().sort_values("seed")
    values = sub[metric].to_numpy(dtype=float)
    return {
        "run_id": run_id,
        "task": task,
        "metric": metric,
        "n": int(len(values)),
        "mean": float(np.mean(values)) if len(values) else float("nan"),
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else float("nan"),
    }


def _paired_row(run_a: str, df_a: pd.DataFrame, run_b: str, df_b: pd.DataFrame, task: str, metric: str) -> Dict[str, object] | None:
    sub_a = df_a[df_a["task"] == task][["seed", metric]].rename(columns={metric: "a"})
    sub_b = df_b[df_b["task"] == task][["seed", metric]].rename(columns={metric: "b"})
    merged = sub_a.merge(sub_b, on="seed", how="inner").dropna().sort_values("seed")
    if len(merged) < 2:
        return None

    diff = (merged["a"] - merged["b"]).to_numpy(dtype=float)
    t_stat, t_p = ttest_rel(merged["a"], merged["b"])
    if np.allclose(diff, 0.0):
        w_stat, w_p = 0.0, 1.0
    else:
        w_stat, w_p = wilcoxon(diff, zero_method="wilcox", correction=False, alternative="two-sided")

    return {
        "run_a": run_a,
        "run_b": run_b,
        "task": task,
        "metric": metric,
        "n_pairs": int(len(merged)),
        "mean_a": float(np.mean(merged["a"])),
        "std_a": float(np.std(merged["a"], ddof=1)),
        "mean_b": float(np.mean(merged["b"])),
        "std_b": float(np.std(merged["b"], ddof=1)),
        "mean_diff_a_minus_b": float(np.mean(diff)),
        "cohen_dz": _cohen_dz(diff),
        "ttest_rel_stat": float(t_stat),
        "ttest_rel_p": float(t_p),
        "wilcoxon_stat": float(w_stat),
        "wilcoxon_p": float(w_p),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare two follow-up multiseed runs from raw_metrics.csv")
    ap.add_argument("--run-a", required=True, help="Run id A")
    ap.add_argument("--run-b", required=True, help="Run id B")
    ap.add_argument("--out-dir", default="", help="Optional output directory")
    args = ap.parse_args()

    df_a = _load_raw(args.run_a)
    df_b = _load_raw(args.run_b)

    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts") / f"{args.run_a}__vs__{args.run_b}" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: List[Dict[str, object]] = []
    paired_rows: List[Dict[str, object]] = []
    for task, metric in METRICS:
        summary_rows.append(_summary_row(args.run_a, df_a, task, metric))
        summary_rows.append(_summary_row(args.run_b, df_b, task, metric))
        paired = _paired_row(args.run_a, df_a, args.run_b, df_b, task, metric)
        if paired is not None:
            paired_rows.append(paired)

    summary_df = pd.DataFrame(summary_rows)
    paired_df = pd.DataFrame(paired_rows)

    summary_path = out_dir / "followup_summary.csv"
    paired_path = out_dir / "followup_paired_stats.csv"
    manifest_path = out_dir / "followup_manifest.json"

    summary_df.to_csv(summary_path, index=False)
    paired_df.to_csv(paired_path, index=False)

    manifest = {
        "run_a": args.run_a,
        "run_b": args.run_b,
        "summary": str(summary_path),
        "paired_stats": str(paired_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
