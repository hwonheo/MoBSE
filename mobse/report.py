from __future__ import annotations

import glob
import os
import tempfile
from pathlib import Path
from typing import Dict, List

_MPLCONFIGDIR = Path(tempfile.gettempdir()) / "mobse-mpl"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))

import matplotlib
import pandas as pd
import seaborn as sns
from scipy.stats import ttest_ind

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mobse.artifacts import ArtifactPaths
from mobse.config import ExperimentConfig
from mobse.progress import ProgressReporter
from mobse.utils import dump_json, load_json


def _collect_eval_files(eval_glob: str) -> List[Path]:
    files = [Path(p) for p in glob.glob(eval_glob)]
    if not files:
        raise FileNotFoundError(f"No evaluation files found for glob: {eval_glob}")
    return sorted(files)


def _flatten_eval(payload: Dict[str, object], source: Path) -> List[Dict[str, object]]:
    rows = []
    arch = payload.get("arch", "unknown")
    run_id = payload.get("run_id", source.parts[-3] if len(source.parts) >= 3 else "unknown")

    task_blocks: List[tuple[str, Dict[str, object]]] = []
    if "os" in payload:
        task_blocks.append(("os", payload["os"]))
    elif "hcp" in payload:
        task_blocks.append(("os", payload["hcp"]))
    if "etth1" in payload:
        task_blocks.append(("etth1", payload["etth1"]))

    for task, block in task_blocks:
        metrics = block["metrics"]
        profile = block["profile"]
        row = {
            "source": str(source),
            "run_id": run_id,
            "arch": arch,
            "task": task,
            **{f"metric_{k}": v for k, v in metrics.items()},
            **{f"profile_{k}": v for k, v in profile.items()},
        }
        rows.append(row)
    return rows


def _ttest_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = [
        "metric_accuracy",
        "metric_f1_macro",
        "metric_mae",
        "metric_mse",
        "profile_flops",
        "profile_latency_ms_mean",
    ]

    mobse_df = df[df["arch"] == "mobse"]
    others = [a for a in df["arch"].unique().tolist() if a != "mobse"]

    for metric in metrics:
        if metric not in df.columns:
            continue
        for arch in others:
            other_df = df[df["arch"] == arch]
            x = mobse_df[metric].dropna()
            y = other_df[metric].dropna()
            if len(x) < 2 or len(y) < 2:
                continue
            stat, p = ttest_ind(x, y, equal_var=False)
            rows.append(
                {
                    "metric": metric,
                    "compare": f"mobse_vs_{arch}",
                    "t_stat": float(stat),
                    "p_value": float(p),
                }
            )
    return pd.DataFrame(rows)


def _plot_metric(df: pd.DataFrame, metric_col: str, out_path: Path) -> None:
    if metric_col not in df.columns:
        return
    plt.figure(figsize=(8, 4))
    sns.barplot(data=df, x="arch", y=metric_col, hue="task", errorbar="sd")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def run_report(
    cfg: ExperimentConfig,
    paths: ArtifactPaths,
    eval_glob: str,
    progress: ProgressReporter | None = None,
) -> Dict[str, str]:
    files = _collect_eval_files(eval_glob)
    if progress:
        progress.update(stage="report:load", message=f"files={len(files)}")

    rows = []
    for idx, file in enumerate(files, start=1):
        payload = load_json(file)
        rows.extend(_flatten_eval(payload, source=file))
        if progress:
            progress.update(stage="report:parse", current=idx, total=len(files), message=file.name)

    df = pd.DataFrame(rows)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    summary = (
        df.groupby(["arch", "task"], as_index=False)[numeric_cols]
        .agg(["mean", "std"])
        .reset_index(drop=False)
    )
    summary.columns = ["_".join([c for c in col if c]) for col in summary.columns.to_flat_index()]

    summary_path = paths.reports / "summary_table.csv"
    raw_path = paths.reports / "raw_metrics.csv"
    ttest_path = paths.reports / "significance_tests.csv"

    df.to_csv(raw_path, index=False)
    summary.to_csv(summary_path, index=False)

    ttest_df = _ttest_table(df)
    if not ttest_df.empty:
        ttest_df.to_csv(ttest_path, index=False)

    _plot_metric(df, "metric_accuracy", paths.reports / "plot_accuracy.png")
    _plot_metric(df, "metric_f1_macro", paths.reports / "plot_f1_macro.png")
    _plot_metric(df, "metric_mse", paths.reports / "plot_mse.png")
    _plot_metric(df, "profile_flops", paths.reports / "plot_flops.png")

    manifest = {
        "raw_metrics": str(raw_path),
        "summary_table": str(summary_path),
        "significance_tests": str(ttest_path) if ttest_path.exists() else "",
    }
    dump_json(manifest, paths.reports / "report_manifest.json")
    if progress:
        progress.update(stage="report:done", message=f"saved={paths.reports / 'report_manifest.json'}")
    return manifest
