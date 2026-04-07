from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def _parse_run_meta(run_id: str, study_id: str) -> Dict[str, Any]:
    # expected: {study_id}_{model}_n{nodes}_sp{sp}_s{seed}
    suffix = run_id.replace(f"{study_id}_", "", 1)
    parts = suffix.split("_")
    seed_part = parts[-1]
    sp_part = parts[-2]
    n_part = parts[-3]
    model_arch = "_".join(parts[:-3])
    seed = int(seed_part[1:]) if seed_part.startswith("s") else -1
    sparsity = int(sp_part[2:]) / 100.0 if sp_part.startswith("sp") else float("nan")
    nodes = int(n_part[1:]) if n_part.startswith("n") else -1
    return {
        "model_arch": model_arch,
        "nodes": nodes,
        "sparsity": sparsity,
        "seed": seed,
    }


def _safe_get(d: Dict[str, Any], *keys: str, default: float = float("nan")) -> float:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    try:
        return float(cur)
    except Exception:
        return default


def collect_rows(study_id: str, artifacts_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    run_dirs = sorted((artifacts_root / "current_canonical").glob(f"{study_id}_*"))
    for run_dir in run_dirs:
        run_id = run_dir.name
        train_summary = run_dir / "logs" / "train_summary.json"
        if not train_summary.exists():
            continue
        payload = json.loads(train_summary.read_text(encoding="utf-8"))
        meta = _parse_run_meta(run_id=run_id, study_id=study_id)
        seeds = payload.get("seeds", [])
        for seed_item in seeds:
            best_epoch = int(seed_item.get("best_epoch", -1))
            history = seed_item.get("history", [])
            for h in history:
                epoch = int(h.get("epoch", -1))
                rows.append(
                    {
                        "run_id": run_id,
                        **meta,
                        "epoch": epoch,
                        "is_best_epoch": 1 if epoch == best_epoch else 0,
                        "best_epoch": best_epoch,
                        "train_etth1_loss": _safe_get(h, "train_etth1_loss"),
                        "val_etth1_loss": _safe_get(h, "val_etth1", "loss"),
                        "val_etth1_mae": _safe_get(h, "val_etth1", "mae"),
                        "val_etth1_mse": _safe_get(h, "val_etth1", "mse"),
                        "val_score": _safe_get(h, "val_score"),
                    }
                )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Build epoch-wise trend report from train_summary logs.")
    ap.add_argument("--study-id", required=True)
    ap.add_argument("--artifacts-root", default="artifacts")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    artifacts_root = repo_root / args.artifacts_root
    out_dir = Path(args.out_dir) if args.out_dir else artifacts_root / "current_canonical" / args.study_id / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = collect_rows(study_id=args.study_id, artifacts_root=artifacts_root)
    if not rows:
        raise SystemExit(f"No epoch rows found for study_id={args.study_id}")

    seed_df = pd.DataFrame(rows).sort_values(["model_arch", "nodes", "sparsity", "seed", "epoch"]) 
    seed_out = out_dir / "epoch_trend_seedwise.csv"
    seed_df.to_csv(seed_out, index=False)

    summary = (
        seed_df.groupby(["model_arch", "nodes", "sparsity", "epoch"], as_index=False)
        .agg(
            train_etth1_loss_mean=("train_etth1_loss", "mean"),
            train_etth1_loss_std=("train_etth1_loss", "std"),
            val_etth1_loss_mean=("val_etth1_loss", "mean"),
            val_etth1_loss_std=("val_etth1_loss", "std"),
            val_etth1_mae_mean=("val_etth1_mae", "mean"),
            val_etth1_mae_std=("val_etth1_mae", "std"),
            val_etth1_mse_mean=("val_etth1_mse", "mean"),
            val_etth1_mse_std=("val_etth1_mse", "std"),
            val_score_mean=("val_score", "mean"),
            val_score_std=("val_score", "std"),
            best_epoch_hits=("is_best_epoch", "sum"),
            n_seed=("seed", "nunique"),
        )
        .sort_values(["nodes", "sparsity", "model_arch", "epoch"])
    )
    summary["best_epoch_rate"] = summary["best_epoch_hits"] / summary["n_seed"].clip(lower=1)
    summary_out = out_dir / "epoch_trend_summary.csv"
    summary.to_csv(summary_out, index=False)

    best_epoch_summary = (
        seed_df[["model_arch", "nodes", "sparsity", "seed", "best_epoch"]]
        .drop_duplicates()
        .groupby(["model_arch", "nodes", "sparsity"], as_index=False)
        .agg(
            best_epoch_mean=("best_epoch", "mean"),
            best_epoch_std=("best_epoch", "std"),
            n_seed=("seed", "nunique"),
        )
        .sort_values(["nodes", "sparsity", "model_arch"])
    )
    best_epoch_out = out_dir / "best_epoch_distribution.csv"
    best_epoch_summary.to_csv(best_epoch_out, index=False)

    manifest = {
        "study_id": args.study_id,
        "rows": int(len(seed_df)),
        "outputs": {
            "seedwise": str(seed_out),
            "summary": str(summary_out),
            "best_epoch_distribution": str(best_epoch_out),
        },
    }
    (out_dir / "epoch_trend_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
