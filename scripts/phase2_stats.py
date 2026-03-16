from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import ttest_rel, wilcoxon


METRICS = [
    "os_accuracy",
    "os_f1_macro",
    "etth1_mae",
    "etth1_mse",
    "os_latency_ms",
    "etth1_latency_ms",
    "os_flops",
]


def _summary_dir(study_id: str) -> Path:
    return Path("artifacts") / f"{study_id}_summary" / "reports"


def _load_bal3_seed_metrics(study_id: str) -> pd.DataFrame:
    path = _summary_dir(study_id) / "phase2_top3_bal3_seed_metrics.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing bal3 seed metrics: {path}")
    df = pd.read_csv(path)
    if "seed" not in df.columns:
        raise ValueError(f"Seed column not found in {path}")
    return df


def _load_bal3_summary(study_id: str) -> pd.DataFrame:
    path = _summary_dir(study_id) / "phase2_top3_bal3_summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing bal3 summary: {path}")
    return pd.read_csv(path)


def _cohen_dz(diff: np.ndarray) -> float:
    if diff.size < 2:
        return float("nan")
    denom = float(np.std(diff, ddof=1))
    if denom == 0.0:
        return float("inf") if float(np.mean(diff)) != 0.0 else 0.0
    return float(np.mean(diff) / denom)


def _holm_adjust(p_values: Iterable[float]) -> List[float]:
    p = np.asarray([float(x) for x in p_values], dtype=float)
    m = p.size
    if m == 0:
        return []
    order = np.argsort(p)
    adjusted = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        value = (m - rank) * p[idx]
        running = max(running, value)
        adjusted[idx] = min(1.0, running)
    return adjusted.tolist()


def _fdr_bh_adjust(p_values: Iterable[float]) -> List[float]:
    p = np.asarray([float(x) for x in p_values], dtype=float)
    m = p.size
    if m == 0:
        return []
    order = np.argsort(p)
    ranked = p[order]
    adjusted_ranked = np.empty(m, dtype=float)
    prev = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        value = (m / rank) * ranked[i]
        prev = min(prev, value)
        adjusted_ranked[i] = prev
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = np.clip(adjusted_ranked, 0.0, 1.0)
    return adjusted.tolist()


def _paired_rows(
    a: pd.DataFrame,
    b: pd.DataFrame,
    metric: str,
    id_a: str,
    id_b: str,
    label: str,
) -> Dict[str, object] | None:
    merged = (
        a[["seed", metric]]
        .rename(columns={metric: "a"})
        .merge(b[["seed", metric]].rename(columns={metric: "b"}), on="seed", how="inner")
        .dropna()
        .sort_values("seed")
    )
    if len(merged) < 2:
        return None

    diff = (merged["a"] - merged["b"]).to_numpy(dtype=float)
    t_stat, t_p = ttest_rel(merged["a"], merged["b"])
    if np.allclose(diff, 0.0):
        w_stat, w_p = 0.0, 1.0
    else:
        w_stat, w_p = wilcoxon(diff, zero_method="wilcox", correction=False, alternative="two-sided")

    return {
        "comparison": label,
        "study_a": id_a,
        "study_b": id_b,
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


def _apply_corrections(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["ttest_rel_p_holm"] = _holm_adjust(out["ttest_rel_p"].tolist())
    out["ttest_rel_p_fdr_bh"] = _fdr_bh_adjust(out["ttest_rel_p"].tolist())
    out["wilcoxon_p_holm"] = _holm_adjust(out["wilcoxon_p"].tolist())
    out["wilcoxon_p_fdr_bh"] = _fdr_bh_adjust(out["wilcoxon_p"].tolist())
    return out


def _pairwise_top3_tests(study_id: str) -> pd.DataFrame:
    df = _load_bal3_seed_metrics(study_id)
    rows: List[Dict[str, object]] = []
    run_ids = sorted(df["run_id"].unique().tolist())
    for run_a, run_b in itertools.combinations(run_ids, 2):
        sub_a = df[df["run_id"] == run_a]
        sub_b = df[df["run_id"] == run_b]
        for metric in METRICS:
            if metric not in df.columns:
                continue
            row = _paired_rows(
                a=sub_a,
                b=sub_b,
                metric=metric,
                id_a=study_id,
                id_b=study_id,
                label=f"{run_a}__vs__{run_b}",
            )
            if row is not None:
                rows.append(row)
    return _apply_corrections(pd.DataFrame(rows))


def _best_run(study_id: str) -> str:
    summary = _load_bal3_summary(study_id)
    summary = summary.sort_values(["os_accuracy_mean", "os_f1_macro_mean"], ascending=False).reset_index(drop=True)
    return str(summary.iloc[0]["run_id"])


def _best_vs_best_tests(study_a: str, study_b: str) -> pd.DataFrame:
    df_a = _load_bal3_seed_metrics(study_a)
    df_b = _load_bal3_seed_metrics(study_b)
    run_a = _best_run(study_a)
    run_b = _best_run(study_b)
    sub_a = df_a[df_a["run_id"] == run_a]
    sub_b = df_b[df_b["run_id"] == run_b]

    rows: List[Dict[str, object]] = []
    for metric in METRICS:
        if metric not in sub_a.columns or metric not in sub_b.columns:
            continue
        row = _paired_rows(
            a=sub_a,
            b=sub_b,
            metric=metric,
            id_a=study_a,
            id_b=study_b,
            label=f"best({run_a})__vs__best({run_b})",
        )
        if row is not None:
            rows.append(row)
    out = _apply_corrections(pd.DataFrame(rows))
    if not out.empty:
        out.insert(0, "run_a", run_a)
        out.insert(1, "run_b", run_b)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase-2 p-value/effect-size table builder")
    ap.add_argument("--study-id", required=True, help="Primary phase2 study id")
    ap.add_argument("--compare-study-id", default="", help="Optional second study id for best-vs-best test")
    ap.add_argument("--out-dir", default="", help="Output directory (default: study summary reports dir)")
    args = ap.parse_args()

    base_out = Path(args.out_dir) if args.out_dir else _summary_dir(args.study_id)
    base_out.mkdir(parents=True, exist_ok=True)

    pairwise = _pairwise_top3_tests(args.study_id)
    pairwise_path = base_out / "phase2_top3_bal3_pairwise_stats.csv"
    pairwise.to_csv(pairwise_path, index=False)

    manifest: Dict[str, str] = {"pairwise_top3_stats": str(pairwise_path)}

    if args.compare_study_id.strip():
        compare = _best_vs_best_tests(args.study_id, args.compare_study_id.strip())
        compare_path = base_out / f"phase2_best_vs_best_{args.study_id}_vs_{args.compare_study_id.strip()}.csv"
        compare.to_csv(compare_path, index=False)
        manifest["best_vs_best_stats"] = str(compare_path)

    manifest_path = base_out / "phase2_stats_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
