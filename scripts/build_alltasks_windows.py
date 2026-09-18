#!/usr/bin/env python3
"""Standalone script to build all-tasks training windows using centroid-based labeling.

Avoids importing the full MoBSE package (which requires torch).
Directly uses numpy + scipy for FC computation and centroid matching.

Usage:
    python scripts/build_alltasks_windows.py \
        --dfc-dir artifacts/piop1_dfc_schaefer100 \
        --timeseries-dir data/aomic/piop1/timeseries/100 \
        --output-dir artifacts/mobse_dfc_piop1_sch100 \
        --window-len 64 --stride 16 --k 3
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from scipy.signal import windows as sig_windows

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def compute_window_fc(
    segment: np.ndarray,
    fisher_z: bool = True,
    taper: str = "cosine",
) -> np.ndarray:
    """Compute FC matrix for a single window segment.

    Returns:
        [n_nodes, n_nodes] FC matrix (full symmetric).
    """
    if taper == "cosine":
        taper_w = sig_windows.tukey(segment.shape[0], alpha=0.5).astype(np.float32)
    else:
        taper_w = np.ones(segment.shape[0], dtype=np.float32)

    tapered = segment * taper_w[:, np.newaxis]
    corr = np.corrcoef(tapered, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(corr, 0.0)

    if fisher_z:
        corr = np.clip(corr, -0.999999, 0.999999)
        corr = np.arctanh(corr)

    return corr.astype(np.float32)


def assign_label_by_centroid(
    window_fc: np.ndarray,
    centroids_fc: np.ndarray,
    pca_object: object = None,
    centroids_pca: np.ndarray = None,
) -> int:
    """Assign dFC state label via nearest centroid distance."""
    n_nodes = window_fc.shape[0]
    triu_idx = np.triu_indices(n_nodes, k=1)
    fc_vec = window_fc[triu_idx].reshape(1, -1).astype(np.float32)

    if pca_object is not None and centroids_pca is not None:
        fc_pca = pca_object.transform(fc_vec)
        dists = np.linalg.norm(centroids_pca - fc_pca, axis=1)
    else:
        dists = np.linalg.norm(centroids_fc - fc_vec, axis=1)

    return int(np.argmin(dists))


def build_all_tasks_windows(
    timeseries_dir: Path,
    tasks: List[str],
    centroids_fc: np.ndarray,
    k: int,
    window_len: int = 64,
    stride: int = 16,
    fisher_z: bool = True,
    taper: str = "cosine",
    min_timepoints: int = 100,
    pca_object: object = None,
    centroids_pca: np.ndarray = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build training windows from all tasks with centroid-based labeling."""
    states = [f"dfc_{i}" for i in range(k)]

    all_windows = []
    all_labels = []
    all_subjects = []
    task_counts = {t: 0 for t in tasks}

    subject_dirs = sorted([d for d in timeseries_dir.iterdir() if d.is_dir()])
    log.info(
        "All-tasks window builder: %d subjects, %d tasks, window=%d, stride=%d",
        len(subject_dirs), len(tasks), window_len, stride,
    )

    for si, subj_dir in enumerate(subject_dirs):
        subj_id = subj_dir.name

        for task in tasks:
            npy_path = subj_dir / f"{task}.npy"
            if not npy_path.exists():
                continue

            ts = np.load(npy_path).astype(np.float32)
            if ts.shape[0] < min_timepoints:
                continue

            n_wins = 0
            for start in range(0, ts.shape[0] - window_len + 1, stride):
                segment = ts[start:start + window_len]
                fc = compute_window_fc(segment, fisher_z=fisher_z, taper=taper)
                label = assign_label_by_centroid(
                    fc, centroids_fc,
                    pca_object=pca_object,
                    centroids_pca=centroids_pca,
                )
                all_windows.append(segment)
                all_labels.append(label)
                all_subjects.append(f"{subj_id}_{task}")
                n_wins += 1

            if n_wins > 0:
                task_counts[task] += 1

        if (si + 1) % 50 == 0:
            log.info("  Processed %d/%d subjects (%d windows so far)",
                     si + 1, len(subject_dirs), len(all_windows))

    if not all_windows:
        raise RuntimeError("No valid training windows generated.")

    x = np.stack(all_windows, axis=0)
    y = np.array(all_labels, dtype=np.int64)
    subject_ids = np.array(all_subjects, dtype=object)

    label_dist = {states[i]: int(np.sum(y == i)) for i in range(k)}
    log.info("All-tasks windows: %d total", len(y))
    log.info("  Per task: %s", task_counts)
    log.info("  Label distribution: %s", label_dist)

    return x, y, subject_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Build all-tasks training windows")
    parser.add_argument("--dfc-dir", type=str, required=True)
    parser.add_argument("--timeseries-dir", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--tasks", type=str, nargs="*",
                        default=["restingstate", "anticipation", "emomatching",
                                 "faces", "gstroop", "workingmemory"])
    parser.add_argument("--window-len", type=int, default=64)
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--min-timepoints", type=int, default=100)
    args = parser.parse_args()

    t0 = time.time()
    dfc_dir = Path(args.dfc_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load dFC results
    dfc_data = np.load(dfc_dir / "dfc_template_bank.npz", allow_pickle=True)
    raw_centroids = dfc_data["centroids"]  # [k, n_edges]
    k = args.k
    n_nodes = dfc_data["template_bank"].shape[1]
    log.info("dFC: k=%d, nodes=%d, centroids=%s", k, n_nodes, raw_centroids.shape)

    # Optionally load PCA
    pca_obj = None
    centroids_pca = None
    pca_path = dfc_dir / "pca_object.pkl"
    if pca_path.exists():
        import pickle
        with open(pca_path, "rb") as f:
            pca_obj = pickle.load(f)
        centroids_pca = pca_obj.transform(raw_centroids)
        log.info("Using PCA-space distance (%d components)", centroids_pca.shape[1])
    else:
        log.info("Using FC-space distance (no PCA object found)")

    # Build windows
    x, y, subject_ids = build_all_tasks_windows(
        timeseries_dir=Path(args.timeseries_dir),
        tasks=args.tasks,
        centroids_fc=raw_centroids,
        k=k,
        window_len=args.window_len,
        stride=args.stride,
        min_timepoints=args.min_timepoints,
        pca_object=pca_obj,
        centroids_pca=centroids_pca,
    )

    # Save
    states = [f"dfc_{i}" for i in range(k)]
    win_path = out_dir / f"os_windows_nodes{n_nodes}_alltasks.npz"
    np.savez_compressed(
        win_path,
        x=x, y=y,
        subject_ids=subject_ids,
        labels=np.array(states, dtype=object),
    )

    elapsed = time.time() - t0

    # Summary
    print("\n" + "=" * 60)
    print("  All-Tasks Training Windows Ready")
    print("=" * 60)
    print(f"  Total windows: {x.shape[0]}")
    print(f"  Shape: {x.shape}")
    print(f"  Label distribution: {np.bincount(y, minlength=k)}")
    print(f"  Tasks: {args.tasks}")
    print(f"  Output: {win_path}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
