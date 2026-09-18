#!/usr/bin/env python3
"""Prepare dFC template bank + training windows for MoBSE training.

Takes the output of run_abide_dfc_pilot.py (or any dFC pipeline run)
and converts it to MoBSE-compatible format for training.

Usage:
    # From ABIDE dFC pilot results:
    python scripts/prepare_dfc_for_training.py \
        --dfc-dir artifacts/abide_dfc_v2_pc10_noznorm \
        --timeseries-source abide \
        --window-len 64 --stride 16 \
        --output-dir artifacts/mobse_dfc_abide

    # From pre-saved timeseries + custom dFC results:
    python scripts/prepare_dfc_for_training.py \
        --dfc-dir artifacts/my_dfc_run \
        --timeseries-dir data/timeseries/schaefer100 \
        --window-len 64 --stride 16 \
        --output-dir artifacts/mobse_dfc_schaefer
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


def load_abide_timeseries(
    n_subjects: int = 0,
    min_age: float = 18.0,
    min_timepoints: int = 150,
) -> tuple[list[np.ndarray], list[float], int]:
    """Re-load ABIDE timeseries matching the dFC pilot filters."""
    from nilearn.datasets import fetch_abide_pcp
    import pandas as pd

    data = fetch_abide_pcp(
        n_subjects=n_subjects if n_subjects > 0 else 800,
        pipeline="cpac",
        band_pass_filtering=True,
        global_signal_regression=True,
        derivatives=["rois_cc200"],
        DX_GROUP=2,
    )

    pheno = pd.DataFrame(data.phenotypic)
    site_tr = {
        "PITT": 1.5, "OLIN": 1.5, "OHSU": 2.5, "SDSU": 2.0,
        "TRINITY": 2.0, "UM_1": 2.0, "UM_2": 2.0, "USM": 2.0,
        "YALE": 2.0, "CMU": 2.0, "LEUVEN_1": 1.66, "LEUVEN_2": 1.66,
        "KKI": 2.5, "NYU": 2.0, "STANFORD": 2.0, "UCLA_1": 3.0,
        "UCLA_2": 3.0, "MAX_MUN": 3.0, "CALTECH": 2.0, "SBL": 2.2,
    }

    timeseries_list = []
    tr_list = []
    for i, ts_arr in enumerate(data.rois_cc200):
        ts = np.array(ts_arr, dtype=np.float32)
        age = float(pheno.iloc[i]["AGE_AT_SCAN"])
        site = str(pheno.iloc[i]["SITE_ID"])
        if age < min_age or ts.shape[0] < min_timepoints:
            continue
        tr_list.append(site_tr.get(site, 2.0))
        timeseries_list.append(ts)

    n_nodes = timeseries_list[0].shape[1] if timeseries_list else 200
    log.info("Loaded %d ABIDE subjects (%d nodes)", len(timeseries_list), n_nodes)
    return timeseries_list, tr_list, n_nodes


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare dFC results for MoBSE training")
    parser.add_argument("--dfc-dir", type=str, required=True,
                        help="Directory with dfc_template_bank.npz + dfc_pilot_report.json")
    parser.add_argument("--timeseries-source", type=str, default="abide",
                        choices=["abide", "directory"],
                        help="Source of timeseries data")
    parser.add_argument("--timeseries-dir", type=str, default=None,
                        help="Directory with sub-XXXX/{task}.npy (for --timeseries-source directory)")
    parser.add_argument("--task", type=str, default="restingstate",
                        help="Task name for directory source")
    parser.add_argument("--tr", type=float, default=None,
                        help="TR in seconds (required for directory source)")
    parser.add_argument("--all-tasks", action="store_true",
                        help="Use all tasks (centroid-based labeling) to increase training data")
    parser.add_argument("--tasks", type=str, nargs="*",
                        default=["restingstate", "anticipation", "emomatching",
                                 "faces", "gstroop", "workingmemory"],
                        help="Tasks to include when --all-tasks is set")
    parser.add_argument("--window-len", type=int, default=64)
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--min-age", type=float, default=18.0)
    parser.add_argument("--min-timepoints", type=int, default=150)
    args = parser.parse_args()

    t0 = time.time()
    dfc_dir = Path(args.dfc_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Load dFC results ---
    dfc_bank_path = dfc_dir / "dfc_template_bank.npz"
    # Support both naming conventions
    dfc_report_path = dfc_dir / "dfc_report.json"
    if not dfc_report_path.exists():
        dfc_report_path = dfc_dir / "dfc_pilot_report.json"

    if not dfc_bank_path.exists():
        raise FileNotFoundError(f"dFC template bank not found: {dfc_bank_path}")

    dfc_data = np.load(dfc_bank_path)
    template_bank = dfc_data["template_bank"]
    labels = dfc_data["labels"]
    subject_indices = dfc_data["subject_indices"]
    window_counts = dfc_data["window_counts"]

    k = template_bank.shape[0]
    n_nodes_effective = template_bank.shape[1]
    log.info("dFC: k=%d, nodes=%d, windows=%d", k, n_nodes_effective, len(labels))

    # Load report for config details
    with open(dfc_report_path) as f:
        report = json.load(f)
    dfc_window_sec = report["config"]["window_sec"]
    dfc_stride_sec = report["config"]["stride_sec"]

    # --- Load timeseries ---
    if args.timeseries_source == "abide":
        timeseries_list, tr_list, n_nodes_orig = load_abide_timeseries(
            min_age=args.min_age,
            min_timepoints=args.min_timepoints,
        )
        # Apply same ROI mask if nodes differ
        if n_nodes_orig != n_nodes_effective:
            log.info("Applying ROI mask: %d → %d nodes", n_nodes_orig, n_nodes_effective)
            from mobse.data.dfc import clean_zero_variance_rois
            timeseries_list, _ = clean_zero_variance_rois(timeseries_list)
    elif args.timeseries_source == "directory":
        if not args.timeseries_dir:
            raise ValueError("--timeseries-dir required for directory source")
        if not args.tr:
            raise ValueError("--tr required for directory source")
        ts_path = Path(args.timeseries_dir)
        timeseries_list = []
        # Structure: ts_dir/sub-XXXX/{task}.npy
        for subj_dir in sorted(d for d in ts_path.iterdir() if d.is_dir()):
            npy = subj_dir / f"{args.task}.npy"
            if not npy.exists():
                continue
            ts = np.load(npy)
            if ts.shape[0] >= args.min_timepoints:
                timeseries_list.append(ts.astype(np.float32))
        tr_list = [args.tr] * len(timeseries_list)
        n_nodes_orig = timeseries_list[0].shape[1] if timeseries_list else 0
        log.info("Loaded %d subjects from %s (nodes=%d)", len(timeseries_list), ts_path, n_nodes_orig)
    else:
        raise NotImplementedError(f"Unknown source: {args.timeseries_source}")

    # --- Export template bank ---
    from mobse.templates.dfc_bridge import (
        export_dfc_for_mobse,
        build_dfc_windows,
        build_dfc_windows_all_tasks,
        generate_dfc_config_yaml,
    )

    tb_path = export_dfc_for_mobse(
        template_bank, out_dir / "template_bank.npz",
        k=k, n_nodes=n_nodes_effective,
        sparsity=report["config"]["sparsity"],
        metadata={
            "silhouette": report["clustering"]["silhouette_score"],
            "source_dir": str(dfc_dir),
        },
    )

    # --- Build training windows ---
    win_path = build_dfc_windows(
        timeseries_list=timeseries_list,
        tr_list=tr_list,
        dfc_labels=labels,
        dfc_subject_indices=subject_indices,
        dfc_window_counts=window_counts,
        dfc_config_window_sec=dfc_window_sec,
        dfc_config_stride_sec=dfc_stride_sec,
        window_len=args.window_len,
        stride=args.stride,
        output_path=out_dir / f"os_windows_nodes{n_nodes_effective}.npz",
        k=k,
    )

    # --- Generate config ---
    cfg = generate_dfc_config_yaml(
        k=k, n_nodes=n_nodes_effective,
        template_bank_path=str(tb_path),
        windows_path=str(win_path),
        window_len=args.window_len,
        stride=args.stride,
        output_path=out_dir / "config_dfc.yaml",
    )

    # --- All-tasks centroid-based labeling (approach B) ---
    all_tasks_win_path = None
    if args.all_tasks:
        if not args.timeseries_dir:
            log.warning("--all-tasks requires --timeseries-dir. Falling back to rest-only windows.")
        else:
            # Use raw FC-space centroids from dFC bank
            raw_centroids = dfc_data["centroids"]  # [k, n_edges] in FC space

            # Optionally load PCA for PCA-space distance (better accuracy)
            pca_obj = None
            centroids_pca = None
            pca_pkl_path = dfc_dir / "pca_object.pkl"
            if pca_pkl_path.exists():
                import pickle
                with open(pca_pkl_path, "rb") as f:
                    pca_obj = pickle.load(f)
                centroids_pca = pca_obj.transform(raw_centroids)
                log.info("Using PCA-space distance for centroid assignment")
            else:
                log.info("PCA object not found — using FC-space distance for centroid assignment")

            all_tasks_win_path = out_dir / f"os_windows_nodes{n_nodes_effective}_alltasks.npz"
            x_at, y_at, sids_at = build_dfc_windows_all_tasks(
                timeseries_dir=args.timeseries_dir,
                tasks=args.tasks,
                centroids_fc=raw_centroids,
                k=k,
                window_len=args.window_len,
                stride=args.stride,
                output_path=all_tasks_win_path,
                fisher_z=True,  # match dFC pipeline default
                taper="cosine",
                min_timepoints=args.min_timepoints,
                roi_mask=None,  # Schaefer: no ROI cleaning needed
                pca_object=pca_obj,
                centroids_pca=centroids_pca,
            )

            # Generate all-tasks config (with anti-overfitting settings)
            generate_dfc_config_yaml(
                k=k, n_nodes=n_nodes_effective,
                template_bank_path=str(tb_path),
                windows_path=str(all_tasks_win_path),
                window_len=args.window_len,
                stride=args.stride,
                output_path=out_dir / "config_dfc_alltasks.yaml",
            )

    elapsed = time.time() - t0

    # --- Summary ---
    wdata = np.load(win_path, allow_pickle=True)
    print("\n" + "=" * 60)
    print("  MoBSE dFC Training Data Ready")
    print("=" * 60)
    print(f"  Template bank: {tb_path}")
    print(f"    k = {k}, nodes = {n_nodes_effective}")
    print(f"  Training windows (rest-only): {win_path}")
    print(f"    Total: {wdata['x'].shape[0]}")
    print(f"    Shape: {wdata['x'].shape}")
    print(f"    Label distribution: {np.bincount(wdata['y'], minlength=k)}")
    if all_tasks_win_path and all_tasks_win_path.exists():
        wdata_at = np.load(all_tasks_win_path, allow_pickle=True)
        print(f"  Training windows (all-tasks): {all_tasks_win_path}")
        print(f"    Total: {wdata_at['x'].shape[0]}")
        print(f"    Shape: {wdata_at['x'].shape}")
        print(f"    Label distribution: {np.bincount(wdata_at['y'], minlength=k)}")
    print(f"  Config: {out_dir / 'config_dfc.yaml'}")
    if all_tasks_win_path:
        print(f"  Config (all-tasks): {out_dir / 'config_dfc_alltasks.yaml'}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print("=" * 60)
    print(f"\n  To train (rest-only): python -m mobse.cli train --config {out_dir / 'config_dfc.yaml'}")
    if all_tasks_win_path:
        print(f"  To train (all-tasks): python -m mobse.cli train --config {out_dir / 'config_dfc_alltasks.yaml'}")
    print()


if __name__ == "__main__":
    main()
