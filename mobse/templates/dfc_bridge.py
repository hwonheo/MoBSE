"""Bridge between dFC pipeline outputs and MoBSE training pipeline.

Converts dFC template bank and window labels to the format expected by
the existing MoBSE template loading, window creation, and training code.

Usage:
    from mobse.templates.dfc_bridge import (
        export_dfc_for_mobse,
        build_dfc_windows,
    )

    # After running dFC pipeline:
    result = run_dfc_pipeline(timeseries_list, tr_list, n_nodes, config)
    export_dfc_for_mobse(result, output_dir, n_nodes_original=200)

    # Build training windows:
    build_dfc_windows(
        timeseries_list, tr_list, result,
        window_len=64, stride=16, output_path="dfc_windows.npz",
    )
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


def _dfc_state_names(k: int) -> List[str]:
    """Generate state names for dFC clusters: dfc_0, dfc_1, ..."""
    return [f"dfc_{i}" for i in range(k)]


def export_dfc_for_mobse(
    template_bank: np.ndarray,
    output_path: str | Path,
    k: int,
    n_nodes: int,
    sparsity: float,
    metadata: Optional[Dict] = None,
) -> Path:
    """Save dFC template bank in MoBSE-compatible NPZ format.

    MoBSE's load_template_bank() expects keys like "template::<state_name>".
    This function converts the dFC [k, nodes, nodes] array to that format.

    Args:
        template_bank: [k, n_nodes, n_nodes] sparse adjacency matrices.
        output_path: Where to save the NPZ file.
        k: Number of dFC states.
        n_nodes: Number of ROI nodes (after cleaning).
        sparsity: Sparsity level used.
        metadata: Optional extra metadata dict.

    Returns:
        Path to the saved NPZ file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    states = _dfc_state_names(k)
    payload = {}
    for i, state in enumerate(states):
        payload[f"template::{state}"] = template_bank[i].astype(np.float32)

    meta = {
        "states": states,
        "num_nodes": n_nodes,
        "sparsity": sparsity,
        "source": "dfc_clustering",
        "k": k,
    }
    if metadata:
        meta.update(metadata)
    payload["metadata_json"] = np.array([str(meta)], dtype=object)

    np.savez_compressed(output_path, **payload)
    log.info("Exported dFC template bank: %s (k=%d, nodes=%d)", output_path, k, n_nodes)
    return output_path


def assign_dfc_labels_to_windows(
    timeseries: np.ndarray,
    dfc_labels: np.ndarray,
    dfc_starts: np.ndarray,
    window_len: int,
    stride: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Assign dFC state labels to MoBSE-style training windows.

    For each MoBSE window (centered at some timepoint), find the temporally
    closest dFC window and use its cluster label. MoBSE windows that don't
    overlap with any dFC window are dropped.

    Args:
        timeseries: [T, nodes] single subject.
        dfc_labels: [n_dfc_windows] cluster assignments for this subject.
        dfc_starts: [n_dfc_windows] start timepoints of each dFC window.
        window_len: MoBSE training window length (timepoints).
        stride: MoBSE training window stride (timepoints).

    Returns:
        windows: [n_windows, window_len, nodes].
        labels: [n_windows] dFC state labels.
    """
    t = timeseries.shape[0]
    if t < window_len:
        return np.empty((0, window_len, timeseries.shape[1]), dtype=np.float32), np.empty(0, dtype=np.int64)

    windows = []
    labels = []

    # dFC window midpoints for matching
    dfc_mids = dfc_starts + (dfc_starts[1] - dfc_starts[0]) / 2 if len(dfc_starts) > 1 else dfc_starts.astype(float)

    for start in range(0, t - window_len + 1, stride):
        mid = start + window_len / 2
        # Find closest dFC window
        dists = np.abs(dfc_mids - mid)
        closest = np.argmin(dists)
        labels.append(int(dfc_labels[closest]))
        windows.append(timeseries[start:start + window_len].astype(np.float32))

    if not windows:
        return np.empty((0, window_len, timeseries.shape[1]), dtype=np.float32), np.empty(0, dtype=np.int64)

    return np.stack(windows, axis=0), np.array(labels, dtype=np.int64)


def build_dfc_windows(
    timeseries_list: List[np.ndarray],
    tr_list: List[float],
    dfc_labels: np.ndarray,
    dfc_subject_indices: np.ndarray,
    dfc_window_counts: np.ndarray,
    dfc_config_window_sec: float,
    dfc_config_stride_sec: float,
    window_len: int,
    stride: int,
    output_path: str | Path,
    k: int,
    min_timepoints: int = 100,
) -> Path:
    """Build MoBSE training windows with dFC-derived state labels.

    Takes the original timeseries and dFC clustering results,
    produces windows + labels in the same NPZ format as build_os_windows().

    Args:
        timeseries_list: List of [T_i, nodes] arrays.
        tr_list: TR per subject.
        dfc_labels: [total_dfc_windows] cluster labels from dFC pipeline.
        dfc_subject_indices: [total_dfc_windows] subject index per dFC window.
        dfc_window_counts: [n_subjects] dFC windows per subject.
        dfc_config_window_sec: dFC window width in seconds.
        dfc_config_stride_sec: dFC stride in seconds.
        window_len: MoBSE training window length (timepoints).
        stride: MoBSE training window stride (timepoints).
        output_path: Where to save the NPZ.
        k: Number of dFC states.
        min_timepoints: Minimum timepoints per subject.

    Returns:
        Path to saved NPZ.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    states = _dfc_state_names(k)
    all_windows = []
    all_labels = []
    all_subjects = []

    # Reconstruct per-subject dFC label arrays
    dfc_offset = 0
    for i, ts in enumerate(timeseries_list):
        n_dfc = int(dfc_window_counts[i])
        if n_dfc == 0 or ts.shape[0] < min_timepoints:
            dfc_offset += n_dfc
            continue

        tr = tr_list[i] if len(tr_list) > 1 else tr_list[0]
        subj_labels = dfc_labels[dfc_offset:dfc_offset + n_dfc]

        # Compute dFC window start timepoints for this subject
        dfc_window_len_tp = max(1, int(round(dfc_config_window_sec / tr)))
        dfc_stride_tp = max(1, int(round(dfc_config_stride_sec / tr)))
        dfc_starts = np.arange(0, ts.shape[0] - dfc_window_len_tp + 1, dfc_stride_tp)[:n_dfc]

        windows, labels = assign_dfc_labels_to_windows(
            ts, subj_labels, dfc_starts,
            window_len=window_len, stride=stride,
        )

        if len(windows) > 0:
            all_windows.append(windows)
            all_labels.append(labels)
            all_subjects.extend([f"sub_{i:04d}"] * len(labels))

        dfc_offset += n_dfc

    if not all_windows:
        raise RuntimeError("No valid training windows generated from dFC data.")

    x = np.concatenate(all_windows, axis=0)
    y = np.concatenate(all_labels, axis=0)
    subject_ids = np.array(all_subjects, dtype=object)

    np.savez_compressed(
        output_path,
        x=x, y=y,
        subject_ids=subject_ids,
        labels=np.array(states, dtype=object),
    )

    # Distribution summary
    label_counts = {states[i]: int(np.sum(y == i)) for i in range(k)}
    log.info(
        "dFC windows: %d total, %d subjects, distribution=%s",
        len(y), len(set(all_subjects)), label_counts,
    )
    return output_path


def assign_label_by_centroid(
    window_fc: np.ndarray,
    centroids_fc: np.ndarray,
    pca_object: Optional[object] = None,
    centroids_pca: Optional[np.ndarray] = None,
) -> int:
    """Assign a dFC state label to a single FC vector via nearest centroid.

    Supports two modes:
    1. PCA mode: project FC to PCA space, compute distance to centroids_pca.
    2. FC mode: compute distance directly in FC space (no PCA needed).

    Args:
        window_fc: [n_nodes, n_nodes] FC matrix for one window.
        centroids_fc: [k, n_edges] centroids in FC space.
        pca_object: Fitted PCA object (optional, for PCA mode).
        centroids_pca: [k, n_pca_components] centroids in PCA space (optional).

    Returns:
        Cluster index (0..k-1).
    """
    n_nodes = window_fc.shape[0]
    triu_idx = np.triu_indices(n_nodes, k=1)
    fc_vec = window_fc[triu_idx].reshape(1, -1).astype(np.float32)

    if pca_object is not None and centroids_pca is not None:
        # PCA mode: project and compare in reduced space
        fc_pca = pca_object.transform(fc_vec)
        dists = np.linalg.norm(centroids_pca - fc_pca, axis=1)
    else:
        # FC mode: direct distance in full FC space
        dists = np.linalg.norm(centroids_fc - fc_vec, axis=1)

    return int(np.argmin(dists))


def _compute_window_fc(
    segment: np.ndarray,
    fisher_z: bool = True,
    taper: str = "cosine",
) -> np.ndarray:
    """Compute FC matrix for a single window segment.

    Args:
        segment: [window_len, n_nodes] timeseries segment.
        fisher_z: Apply Fisher-Z transform.
        taper: Tapering window type.

    Returns:
        [n_nodes, n_nodes] FC matrix (full symmetric).
    """
    from scipy.signal import windows as sig_windows

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


def build_dfc_windows_all_tasks(
    timeseries_dir: str | Path,
    tasks: List[str],
    centroids_fc: np.ndarray,
    k: int,
    window_len: int = 64,
    stride: int = 16,
    output_path: Optional[str | Path] = None,
    fisher_z: bool = True,
    taper: str = "cosine",
    min_timepoints: int = 100,
    roi_mask: Optional[np.ndarray] = None,
    pca_object: Optional[object] = None,
    centroids_pca: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build training windows from ALL tasks using centroid-based label assignment.

    For each subject and each task, extract sliding windows, compute FC per
    window, find nearest dFC centroid as label. Supports both FC-space and
    PCA-space distance computation.

    This multiplies training data by utilizing all available task timeseries,
    not just resting-state.

    Args:
        timeseries_dir: Directory with sub-XXXX/{task}.npy structure.
        tasks: List of task names to include (e.g. ["restingstate", "faces", ...]).
        centroids_fc: [k, n_edges] centroids in FC space (from dfc_template_bank.npz).
        k: Number of dFC states.
        window_len: Training window length (timepoints).
        stride: Training window stride (timepoints).
        output_path: If provided, save as NPZ.
        fisher_z: Must match dFC pipeline setting.
        taper: Must match dFC pipeline setting.
        min_timepoints: Minimum scan length to include.
        roi_mask: Boolean mask [n_nodes_original] if ROI cleaning was applied.
        pca_object: Optional fitted PCA for PCA-space distance.
        centroids_pca: Optional [k, n_pca] centroids in PCA space.

    Returns:
        x: [n_windows, window_len, n_nodes] training windows.
        y: [n_windows] dFC state labels.
        subject_ids: [n_windows] subject IDs (dtype=object).
    """
    timeseries_dir = Path(timeseries_dir)
    states = _dfc_state_names(k)

    all_windows = []
    all_labels = []
    all_subjects = []
    task_counts = {t: 0 for t in tasks}

    subject_dirs = sorted([d for d in timeseries_dir.iterdir() if d.is_dir()])
    log.info(
        "All-tasks window builder: %d subjects, %d tasks, window=%d, stride=%d",
        len(subject_dirs), len(tasks), window_len, stride,
    )

    for subj_dir in subject_dirs:
        subj_id = subj_dir.name

        for task in tasks:
            npy_path = subj_dir / f"{task}.npy"
            if not npy_path.exists():
                continue

            ts = np.load(npy_path).astype(np.float32)

            # Apply ROI mask if needed (e.g., CC200 zero-variance ROI removal)
            if roi_mask is not None:
                ts = ts[:, roi_mask]

            if ts.shape[0] < min_timepoints:
                continue

            n_nodes = ts.shape[1]

            # Extract windows and assign labels
            for start in range(0, ts.shape[0] - window_len + 1, stride):
                segment = ts[start:start + window_len]
                fc = _compute_window_fc(segment, fisher_z=fisher_z, taper=taper)
                label = assign_label_by_centroid(
                    fc, centroids_fc,
                    pca_object=pca_object,
                    centroids_pca=centroids_pca,
                )

                all_windows.append(segment)
                all_labels.append(label)
                all_subjects.append(f"{subj_id}_{task}")

            task_counts[task] += 1

    if not all_windows:
        raise RuntimeError("No valid training windows generated from any task.")

    x = np.stack(all_windows, axis=0)
    y = np.array(all_labels, dtype=np.int64)
    subject_ids = np.array(all_subjects, dtype=object)

    # Distribution summary
    label_dist = {states[i]: int(np.sum(y == i)) for i in range(k)}
    log.info(
        "All-tasks windows: %d total from %d task-subject pairs",
        len(y), sum(task_counts.values()),
    )
    log.info("  Per task: %s", task_counts)
    log.info("  Label distribution: %s", label_dist)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            output_path,
            x=x, y=y,
            subject_ids=subject_ids,
            labels=np.array(states, dtype=object),
        )
        log.info("Saved all-tasks windows: %s", output_path)

    return x, y, subject_ids


def generate_dfc_config_yaml(
    k: int,
    n_nodes: int,
    template_bank_path: str,
    windows_path: str,
    window_len: int = 64,
    stride: int = 16,
    output_path: Optional[str | Path] = None,
) -> Dict:
    """Generate a MoBSE config dict for dFC-based training.

    Args:
        k: Number of dFC states.
        n_nodes: Number of ROI nodes.
        template_bank_path: Path to dFC template bank NPZ.
        windows_path: Path to dFC training windows NPZ.
        window_len: Training window length.
        stride: Training window stride.
        output_path: If provided, save as YAML.

    Returns:
        Config dict suitable for load_config().
    """
    states = _dfc_state_names(k)

    config = {
        "data": {
            "os": {
                "states": states,
                "window_len": window_len,
                "stride": stride,
                "atlas_nodes_primary": n_nodes,
            },
        },
        "template": {
            "atlas_name": "dfc",
        },
        "model": {
            "num_nodes": n_nodes,
            "num_experts": k,
            "os_num_classes": k,
            "template_bank_path": str(template_bank_path),
            "os_windows_path": str(windows_path),
        },
    }

    if output_path:
        import yaml
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.safe_dump(config, f, sort_keys=False)
        log.info("Saved dFC config: %s", output_path)

    return config
