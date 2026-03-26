from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def _load_summary(run_id: str) -> pd.DataFrame:
    path = Path("artifacts") / run_id / "reports" / "summary_table.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing summary table: {path}")
    return pd.read_csv(path)


def _extract_row(label: str, run_id: str) -> Dict[str, object]:
    df = _load_summary(run_id)
    os_row = df[df["task"] == "os"].iloc[0]
    et_row = df[df["task"] == "etth1"].iloc[0]
    return {
        "model": label,
        "run_id": run_id,
        "os_accuracy_mean": float(os_row["metric_accuracy_mean"]),
        "os_accuracy_std": float(os_row["metric_accuracy_std"]),
        "os_f1_macro_mean": float(os_row["metric_f1_macro_mean"]),
        "os_f1_macro_std": float(os_row["metric_f1_macro_std"]),
        "os_latency_ms": float(os_row["profile_latency_ms_mean_mean"]),
        "os_flops": float(os_row["profile_flops_mean"]),
        "etth1_mae_mean": float(et_row["metric_mae_mean"]),
        "etth1_mae_std": float(et_row["metric_mae_std"]),
        "etth1_mse_mean": float(et_row["metric_mse_mean"]),
        "etth1_mse_std": float(et_row["metric_mse_std"]),
        "etth1_latency_ms": float(et_row["profile_latency_ms_mean_mean"]),
        "etth1_flops": float(et_row["profile_flops_mean"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a combined baseline benchmark table")
    ap.add_argument("--out-dir", default="artifacts/benchmark_wave_20260323/reports")
    args = ap.parse_args()

    runs = {
        "mobse_n100": "phase2_ds00_adult300_n100_best5_20260323",
        "transformer": "phase2_baseline_transformer_n100_20260323",
        "sparse_transformer": "phase2_baseline_sparse_transformer_n100_20260323",
        "moe": "phase2_baseline_moe_n100_20260323",
    }

    rows: List[Dict[str, object]] = []
    for label, run_id in runs.items():
        rows.append(_extract_row(label, run_id))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    table = pd.DataFrame(rows)
    table_path = out_dir / "baseline_benchmark_summary.csv"
    table.to_csv(table_path, index=False)

    manifest = {"summary": str(table_path)}
    (out_dir / "baseline_benchmark_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
