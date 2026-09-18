#!/usr/bin/env python3
"""PIOP1 Schaefer dFC Pipeline.

Runs dFC clustering on PIOP1 resting-state timeseries (Schaefer 100/200).

Usage:
    python scripts/run_piop1_dfc.py --nodes 100 --k-range 3 4 5 6 7
    python scripts/run_piop1_dfc.py --nodes 200 --k-range 3 4 5 6 7
    python scripts/run_piop1_dfc.py --nodes 100 --k 3  # fixed k
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_piop_timeseries(
    ts_dir: Path,
    task: str = "restingstate",
    min_timepoints: int = 100,
) -> tuple[list[np.ndarray], list[str]]:
    """Load extracted PIOP timeseries from .npy files.

    Args:
        ts_dir: Directory with sub-XXXX_task-{task}.npy files.
        task: Task name to filter.
        min_timepoints: Minimum scan length.

    Returns:
        timeseries_list: List of [T, nodes] arrays.
        subject_ids: List of subject IDs.
    """
    # Structure: ts_dir/sub-XXXX/{task}.npy (stream_aomic_extract output)
    subject_dirs = sorted([d for d in ts_dir.iterdir() if d.is_dir()])
    if not subject_dirs:
        # Fallback: flat files like sub-XXXX_task-{task}.npy
        subject_dirs = []
        files = sorted(ts_dir.glob(f"*_task-{task}.npy"))
        if not files:
            files = sorted(ts_dir.glob("*.npy"))
        for f in files:
            ts = np.load(f)
            if ts.shape[0] >= min_timepoints:
                timeseries_list.append(ts.astype(np.float32))
                subject_ids.append(f.stem.split("_")[0])
        return timeseries_list, subject_ids

    timeseries_list = []
    subject_ids = []

    for subj_dir in subject_dirs:
        npy_path = subj_dir / f"{task}.npy"
        if not npy_path.exists():
            log.warning("Skipping %s: no %s.npy", subj_dir.name, task)
            continue
        ts = np.load(npy_path)
        if ts.shape[0] < min_timepoints:
            log.warning("Skipping %s: %d timepoints < %d", subj_dir.name, ts.shape[0], min_timepoints)
            continue
        timeseries_list.append(ts.astype(np.float32))
        subject_ids.append(subj_dir.name)

    n_total = len(subject_dirs) if subject_dirs else len(timeseries_list)
    log.info(
        "Loaded %d/%d subjects from %s (task=%s)",
        len(timeseries_list), n_total, ts_dir, task,
    )
    if timeseries_list:
        shapes = [ts.shape for ts in timeseries_list]
        tps = [s[0] for s in shapes]
        log.info(
            "  Timepoints: min=%d, max=%d, mean=%.0f, nodes=%d",
            min(tps), max(tps), np.mean(tps), shapes[0][1],
        )
    return timeseries_list, subject_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="PIOP1 Schaefer dFC pipeline")
    parser.add_argument("--nodes", type=int, default=100, choices=[100, 200])
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--k-range", type=int, nargs="*", default=None)
    parser.add_argument("--pca-n-components", type=int, default=10)
    parser.add_argument("--window-sec", type=float, default=45.0)
    parser.add_argument("--stride-sec", type=float, default=2.0)
    parser.add_argument("--sparsity", type=float, default=0.2)
    parser.add_argument("--min-timepoints", type=int, default=100)
    parser.add_argument("--ts-dir", type=str, default=None,
                        help="Override timeseries directory")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    t0 = time.time()

    # --- Locate timeseries ---
    if args.ts_dir:
        ts_dir = Path(args.ts_dir)
    else:
        ts_dir = Path(f"data/aomic/piop1/timeseries/{args.nodes}")

    if not ts_dir.exists():
        raise FileNotFoundError(f"Timeseries directory not found: {ts_dir}")

    timeseries_list, subject_ids = load_piop_timeseries(
        ts_dir, task="restingstate", min_timepoints=args.min_timepoints,
    )

    if not timeseries_list:
        log.error("No subjects passed filtering.")
        return

    n_nodes = timeseries_list[0].shape[1]
    tr = 0.75  # PIOP1 TR

    # --- Run dFC ---
    from mobse.data.dfc import DFCConfig, run_dfc_pipeline

    config = DFCConfig(
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
        k=args.k,
        k_range=args.k_range,
        pca_n_components=args.pca_n_components,
        subject_z_norm=False,
        drop_zero_var_rois=True,
        sparsity=args.sparsity,
        n_init=100,
        max_iter=500,
        min_timepoints=args.min_timepoints,
    )

    result = run_dfc_pipeline(
        timeseries_list=timeseries_list,
        tr_list=[tr],
        n_nodes=n_nodes,
        config=config,
    )

    elapsed = time.time() - t0

    # --- Save outputs ---
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = Path(f"artifacts/piop1_dfc_schaefer{args.nodes}")
    out_dir.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        out_dir / "dfc_template_bank.npz",
        template_bank=result.template_bank,
        centroids=result.centroids,
        labels=result.labels,
        subject_indices=result.subject_indices,
        window_counts=result.window_counts,
    )

    # Save PCA object for centroid-based label assignment (all-tasks mode)
    if result.pca_object is not None:
        import pickle
        with open(out_dir / "pca_object.pkl", "wb") as f:
            pickle.dump(result.pca_object, f)
        log.info("Saved PCA object: %s", out_dir / "pca_object.pkl")

    report = {
        "config": {
            "window_sec": config.window_sec,
            "stride_sec": config.stride_sec,
            "k": config.k,
            "sparsity": config.sparsity,
            "taper": config.taper,
            "fisher_z": config.fisher_z,
            "pca_n_components": config.pca_n_components,
            "subject_z_norm": config.subject_z_norm,
            "drop_zero_var_rois": config.drop_zero_var_rois,
        },
        "data": {
            "dataset": "AOMIC-PIOP1",
            "atlas": f"Schaefer {args.nodes}",
            "n_subjects_input": len(timeseries_list),
            "n_subjects_used": int(np.sum(result.window_counts > 0)),
            "n_nodes_original": n_nodes,
            "n_nodes_effective": result.template_bank.shape[1],
            "tr": tr,
            "total_windows": int(len(result.labels)),
        },
        "clustering": result.metrics,
        "pca": result.pca_info,
        "elapsed_sec": elapsed,
    }
    if result.k_search_results:
        report["k_search"] = result.k_search_results

    with open(out_dir / "dfc_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Save subject list
    with open(out_dir / "subject_ids.json", "w") as f:
        json.dump(subject_ids, f)

    # --- Summary ---
    n_eff = result.template_bank.shape[1]
    roi_info = f" → {n_eff} after cleaning" if n_eff != n_nodes else ""
    print("\n" + "=" * 60)
    print("  PIOP1 Schaefer dFC Complete")
    print("=" * 60)
    print(f"  Subjects used: {report['data']['n_subjects_used']}")
    print(f"  Total windows: {report['data']['total_windows']}")
    print(f"  Atlas: Schaefer {args.nodes} ({n_nodes} nodes{roi_info})")
    print(f"  TR: {tr}s")
    if result.pca_info:
        print(f"  PCA: {result.pca_info['reduction_ratio']} "
              f"({result.pca_info['explained_variance_total']:.1%} variance)")
    print(f"  k = {result.metrics['k']}")
    print(f"  Silhouette: {result.metrics['silhouette_score']:.4f}")
    print(f"  Calinski-Harabasz: {result.metrics['calinski_harabasz_score']:.1f}")
    print(f"  Occupancy: {result.metrics['occupancy']}")
    print(f"  Template bank: {result.template_bank.shape}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Output: {out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
