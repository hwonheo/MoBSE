"""Dynamic Functional Connectivity (dFC) module for MoBSE Phase 2.

Implements sliding-window FC computation and k-means clustering
to derive data-driven brain-state templates from resting-state fMRI.

Reference: Allen et al. (2014), Cerebral Cortex.

Usage:
    from mobse.data.dfc import (
        compute_sliding_window_fc,
        cluster_dfc_states,
        build_dfc_template_bank,
        run_dfc_pipeline,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DFCConfig:
    """Configuration for dFC sliding-window analysis."""

    window_sec: float = 45.0
    stride_sec: float = 2.0
    taper: str = "cosine"  # cosine | rectangular
    fisher_z: bool = True
    k: int = 5
    k_range: Optional[List[int]] = None  # for silhouette search
    n_init: int = 100
    max_iter: int = 500
    random_state: int = 42
    sparsity: float = 0.2
    min_timepoints: int = 100
    min_occupancy: float = 0.05  # minimum fraction per state
    pca_variance: float = 0.95   # PCA explained variance ratio (0 = no PCA)
    pca_n_components: Optional[int] = None  # fixed PCA components (overrides pca_variance)
    subject_z_norm: bool = True  # z-normalize FC vectors per subject before pooling
    drop_zero_var_rois: bool = True  # drop ROIs with zero variance before FC
    handle_nan_roi: bool = True  # replace NaN FC edges with 0


# ---------------------------------------------------------------------------
# Sliding-window FC
# ---------------------------------------------------------------------------

def clean_zero_variance_rois(
    timeseries_list: List[np.ndarray],
    min_std: float = 1e-6,
) -> Tuple[List[np.ndarray], np.ndarray]:
    """Drop ROIs that have zero (or near-zero) variance across all subjects.

    Some CC200 ROIs lack signal in certain subjects, producing NaN correlations.
    Removing them globally ensures consistent edge indexing across subjects.

    Args:
        timeseries_list: List of [T_i, n_nodes] arrays.
        min_std: Minimum std threshold per ROI.

    Returns:
        cleaned_list: List of [T_i, n_good_nodes] arrays.
        good_mask: Boolean mask [n_nodes] of retained ROIs.
    """
    n_nodes = timeseries_list[0].shape[1]
    # ROI is "good" only if it has sufficient variance in ALL subjects
    good_mask = np.ones(n_nodes, dtype=bool)
    for ts in timeseries_list:
        roi_std = np.std(ts, axis=0)
        good_mask &= (roi_std > min_std)

    n_dropped = int(n_nodes - good_mask.sum())
    if n_dropped > 0:
        log.info(
            "Dropped %d/%d zero-variance ROIs (%.1f%% retained)",
            n_dropped, n_nodes, good_mask.sum() / n_nodes * 100,
        )
    cleaned_list = [ts[:, good_mask] for ts in timeseries_list]
    return cleaned_list, good_mask


def _build_taper_window(length: int, taper: str = "cosine") -> np.ndarray:
    """Build a tapering window for sliding-window FC.

    Args:
        length: Window length in timepoints.
        taper: 'cosine' (Tukey-like taper) or 'rectangular'.

    Returns:
        1D array of shape [length] with taper weights.
    """
    if taper == "rectangular":
        return np.ones(length, dtype=np.float32)

    # Cosine taper (Tukey window with alpha=0.5)
    from scipy.signal import windows
    return windows.tukey(length, alpha=0.5).astype(np.float32)


def compute_sliding_window_fc(
    timeseries: np.ndarray,
    window_sec: float,
    stride_sec: float,
    tr: float,
    taper: str = "cosine",
    fisher_z: bool = True,
) -> np.ndarray:
    """Compute sliding-window functional connectivity matrices.

    Args:
        timeseries: ROI timeseries, shape [T, nodes].
        window_sec: Window width in seconds.
        stride_sec: Stride in seconds.
        tr: Repetition time in seconds.
        taper: Tapering window type ('cosine' or 'rectangular').
        fisher_z: Apply Fisher-Z transform to correlation values.

    Returns:
        FC vectors, shape [n_windows, n_edges].
        n_edges = nodes * (nodes - 1) / 2 (upper triangle).
    """
    t, n_nodes = timeseries.shape
    window_len = max(1, int(round(window_sec / tr)))
    stride_len = max(1, int(round(stride_sec / tr)))

    if t < window_len:
        raise ValueError(
            f"Timeseries too short ({t} timepoints) for window "
            f"({window_len} timepoints = {window_sec}s at TR={tr}s)"
        )

    taper_weights = _build_taper_window(window_len, taper)
    triu_idx = np.triu_indices(n_nodes, k=1)
    n_edges = len(triu_idx[0])

    starts = list(range(0, t - window_len + 1, stride_len))
    fc_vectors = np.empty((len(starts), n_edges), dtype=np.float32)

    for i, start in enumerate(starts):
        segment = timeseries[start:start + window_len].copy()

        # Apply taper
        segment *= taper_weights[:, np.newaxis]

        # Pearson correlation
        corr = np.corrcoef(segment, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
        np.fill_diagonal(corr, 0.0)

        if fisher_z:
            corr = np.clip(corr, -0.999999, 0.999999)
            corr = np.arctanh(corr)

        fc_vectors[i] = corr[triu_idx]

    return fc_vectors


def compute_all_fc_vectors(
    timeseries_list: List[np.ndarray],
    window_sec: float,
    stride_sec: float,
    tr_list: List[float],
    taper: str = "cosine",
    fisher_z: bool = True,
    min_timepoints: int = 100,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute sliding-window FC for multiple subjects.

    Args:
        timeseries_list: List of [T_i, nodes] arrays.
        tr_list: TR per subject (or single value broadcast).
        Other args: passed to compute_sliding_window_fc.

    Returns:
        all_fc: [total_windows, n_edges]
        subject_indices: [total_windows] — which subject each window belongs to.
        window_counts: [n_subjects] — number of windows per subject.
    """
    all_fc = []
    subject_indices = []
    window_counts = []

    for i, ts in enumerate(timeseries_list):
        tr = tr_list[i] if len(tr_list) > 1 else tr_list[0]

        if ts.shape[0] < min_timepoints:
            log.warning(
                "Subject %d: %d timepoints < %d, skipping",
                i, ts.shape[0], min_timepoints,
            )
            window_counts.append(0)
            continue

        try:
            fc = compute_sliding_window_fc(
                ts, window_sec=window_sec, stride_sec=stride_sec,
                tr=tr, taper=taper, fisher_z=fisher_z,
            )
        except ValueError as e:
            log.warning("Subject %d: %s, skipping", i, e)
            window_counts.append(0)
            continue

        all_fc.append(fc)
        subject_indices.extend([i] * fc.shape[0])
        window_counts.append(fc.shape[0])

    if not all_fc:
        raise RuntimeError("No valid FC windows computed from any subject.")

    all_fc_stacked = np.vstack(all_fc)
    subj_idx = np.array(subject_indices, dtype=np.int32)
    win_counts = np.array(window_counts, dtype=np.int32)

    return all_fc_stacked, subj_idx, win_counts


def _subject_z_normalize(
    fc_vectors: np.ndarray,
    subject_indices: np.ndarray,
) -> np.ndarray:
    """Z-normalize FC vectors per subject to remove site/scanner scale effects.

    Each subject's FC windows are independently centered and scaled,
    so cross-site variance in global FC magnitude is removed.

    Args:
        fc_vectors: [n_windows, n_edges].
        subject_indices: [n_windows] subject ID per window.

    Returns:
        Normalized FC vectors [n_windows, n_edges].
    """
    normalized = fc_vectors.copy()
    unique_subjects = np.unique(subject_indices)

    for subj in unique_subjects:
        mask = subject_indices == subj
        subj_fc = normalized[mask]
        mu = subj_fc.mean(axis=0)
        sigma = subj_fc.std(axis=0)
        sigma[sigma < 1e-8] = 1.0  # avoid division by zero
        normalized[mask] = (subj_fc - mu) / sigma

    log.info(
        "Per-subject z-normalization applied to %d subjects",
        len(unique_subjects),
    )
    return normalized


# ---------------------------------------------------------------------------
# Dimensionality reduction (Allen et al. 2014)
# ---------------------------------------------------------------------------

def reduce_fc_dimensions(
    fc_vectors: np.ndarray,
    variance_ratio: float = 0.95,
    n_components: Optional[int] = None,
    random_state: int = 42,
) -> Tuple[np.ndarray, object, Dict]:
    """PCA dimensionality reduction on FC vectors.

    Allen et al. (2014) applied PCA retaining 95% variance before k-means.
    This reduces the curse of dimensionality for high-dimensional FC vectors.

    Args:
        fc_vectors: [n_windows, n_edges].
        variance_ratio: Fraction of variance to retain (used if n_components is None).
        n_components: Fixed number of PCA components (overrides variance_ratio).
        random_state: Random seed.

    Returns:
        reduced: [n_windows, n_components].
        pca: fitted PCA object (for inverse transform).
        info: dict with n_components, explained_variance, etc.
    """
    from sklearn.decomposition import PCA

    # Handle any remaining NaN/Inf
    fc_clean = np.nan_to_num(fc_vectors, nan=0.0, posinf=0.0, neginf=0.0)

    # Fixed components or variance-based
    nc = n_components if n_components is not None else variance_ratio
    solver = "full" if n_components is None else "auto"
    pca = PCA(n_components=nc, random_state=random_state, svd_solver=solver)
    reduced = pca.fit_transform(fc_clean)

    info = {
        "n_components": int(pca.n_components_),
        "n_features_original": int(fc_vectors.shape[1]),
        "explained_variance_total": float(np.sum(pca.explained_variance_ratio_)),
        "reduction_ratio": f"{fc_vectors.shape[1]} → {pca.n_components_}",
        "mode": f"fixed={n_components}" if n_components else f"variance={variance_ratio}",
    }
    log.info(
        "PCA: %d → %d components (%.1f%% variance retained)",
        fc_vectors.shape[1], pca.n_components_,
        np.sum(pca.explained_variance_ratio_) * 100,
    )
    return reduced, pca, info


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_dfc_states(
    fc_vectors: np.ndarray,
    k: int,
    n_init: int = 100,
    max_iter: int = 500,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """Cluster FC vectors into k dynamic states via k-means.

    Args:
        fc_vectors: [n_windows, n_edges].
        k: Number of clusters.
        n_init: Number of k-means initializations.
        max_iter: Max iterations per run.
        random_state: Random seed.

    Returns:
        centroids: [k, n_edges].
        labels: [n_windows] cluster assignments.
        metrics: dict with silhouette_score, calinski_harabasz, inertia,
                 occupancy (fraction per cluster).
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import calinski_harabasz_score, silhouette_score

    log.info(
        "Clustering %d windows into %d states (n_init=%d)...",
        fc_vectors.shape[0], k, n_init,
    )

    km = KMeans(
        n_clusters=k,
        n_init=n_init,
        max_iter=max_iter,
        random_state=random_state,
    )
    labels = km.fit_predict(fc_vectors)
    centroids = km.cluster_centers_

    # Metrics
    sil = silhouette_score(fc_vectors, labels, sample_size=min(5000, len(labels)))
    ch = calinski_harabasz_score(fc_vectors, labels)
    occupancy = {
        int(c): float(np.mean(labels == c))
        for c in range(k)
    }

    metrics = {
        "k": k,
        "silhouette_score": float(sil),
        "calinski_harabasz_score": float(ch),
        "inertia": float(km.inertia_),
        "n_windows": int(len(labels)),
        "occupancy": occupancy,
    }

    log.info(
        "  k=%d  silhouette=%.4f  CH=%.1f  occupancy=%s",
        k, sil, ch,
        {c: f"{v:.1%}" for c, v in occupancy.items()},
    )

    return centroids, labels, metrics


def search_optimal_k(
    fc_vectors: np.ndarray,
    k_range: List[int],
    n_init: int = 50,
    max_iter: int = 300,
    random_state: int = 42,
) -> List[Dict]:
    """Run clustering for multiple k values and return metrics."""
    results = []
    for k in k_range:
        _, _, metrics = cluster_dfc_states(
            fc_vectors, k=k, n_init=n_init,
            max_iter=max_iter, random_state=random_state,
        )
        results.append(metrics)
    return results


# ---------------------------------------------------------------------------
# Template construction
# ---------------------------------------------------------------------------

def _vector_to_matrix(vector: np.ndarray, n_nodes: int) -> np.ndarray:
    """Reconstruct symmetric matrix from upper-triangle vector."""
    mat = np.zeros((n_nodes, n_nodes), dtype=np.float32)
    triu_idx = np.triu_indices(n_nodes, k=1)
    mat[triu_idx] = vector
    mat = mat + mat.T
    return mat


def _sparsify(matrix: np.ndarray, keep_ratio: float) -> np.ndarray:
    """Keep top keep_ratio edges by absolute value."""
    n = matrix.shape[0]
    upper_idx = np.triu_indices(n, k=1)
    scores = np.abs(matrix[upper_idx])
    keep = max(1, int(np.ceil(len(scores) * keep_ratio)))
    thresh = np.partition(scores, -keep)[-keep]

    sparse = np.zeros_like(matrix)
    mask = np.abs(matrix) >= thresh
    sparse[mask] = matrix[mask]
    sparse = np.triu(sparse, k=1)
    sparse = sparse + sparse.T
    np.fill_diagonal(sparse, 0.0)
    return sparse


def build_dfc_template_bank(
    centroids: np.ndarray,
    n_nodes: int,
    sparsity: float = 0.2,
    inverse_fisher_z: bool = True,
) -> np.ndarray:
    """Convert cluster centroids to sparse template bank.

    Args:
        centroids: [k, n_edges] from clustering.
        n_nodes: Number of ROI nodes.
        sparsity: Fraction of edges to keep.
        inverse_fisher_z: Apply tanh to undo Fisher-Z before sparsifying.

    Returns:
        template_bank: [k, n_nodes, n_nodes] sparse adjacency matrices.
    """
    k = centroids.shape[0]
    templates = np.zeros((k, n_nodes, n_nodes), dtype=np.float32)

    for i in range(k):
        mat = _vector_to_matrix(centroids[i], n_nodes)
        if inverse_fisher_z:
            mat = np.tanh(mat)
        templates[i] = _sparsify(mat, keep_ratio=sparsity)

    return templates


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------

@dataclass
class DFCResult:
    """Result container for dFC pipeline."""

    template_bank: np.ndarray       # [k, nodes, nodes]
    labels: np.ndarray              # [total_windows]
    centroids: np.ndarray           # [k, n_edges] (original FC space)
    subject_indices: np.ndarray     # [total_windows]
    window_counts: np.ndarray       # [n_subjects]
    metrics: Dict                   # clustering metrics
    config: DFCConfig               # config used
    k_search_results: Optional[List[Dict]] = None
    pca_info: Optional[Dict] = None  # PCA reduction details
    pca_object: Optional[object] = None  # fitted PCA for inverse/forward transform
    roi_mask: Optional[np.ndarray] = None  # [n_nodes_original] bool mask


def run_dfc_pipeline(
    timeseries_list: List[np.ndarray],
    tr_list: List[float],
    n_nodes: int,
    config: Optional[DFCConfig] = None,
) -> DFCResult:
    """Run the full dFC pipeline: sliding window → clustering → templates.

    Args:
        timeseries_list: List of [T_i, n_nodes] arrays.
        tr_list: TR per subject (single-element list broadcasts).
        n_nodes: Number of ROI nodes.
        config: DFC configuration (uses defaults if None).

    Returns:
        DFCResult with template bank, labels, and metrics.
    """
    if config is None:
        config = DFCConfig()

    log.info(
        "dFC pipeline: %d subjects, window=%.0fs, stride=%.0fs, k=%d",
        len(timeseries_list), config.window_sec, config.stride_sec, config.k,
    )

    # Step 0: Clean zero-variance ROIs
    effective_nodes = n_nodes
    roi_mask = None
    if config.drop_zero_var_rois:
        timeseries_list, roi_mask = clean_zero_variance_rois(timeseries_list)
        effective_nodes = int(roi_mask.sum())

    # Step 1: Compute FC vectors
    all_fc, subject_indices, window_counts = compute_all_fc_vectors(
        timeseries_list=timeseries_list,
        window_sec=config.window_sec,
        stride_sec=config.stride_sec,
        tr_list=tr_list,
        taper=config.taper,
        fisher_z=config.fisher_z,
        min_timepoints=config.min_timepoints,
    )
    log.info("Total FC windows: %d (from %d subjects with data)",
             all_fc.shape[0], int(np.sum(window_counts > 0)))

    # Step 1.5: Per-subject z-normalization (removes site/scanner scale effects)
    if config.subject_z_norm:
        all_fc = _subject_z_normalize(all_fc, subject_indices)

    # Step 2: Optional PCA dimensionality reduction (Allen et al. 2014)
    pca_obj = None
    pca_info = None
    use_pca = config.pca_n_components is not None or config.pca_variance > 0
    if use_pca:
        fc_for_clustering, pca_obj, pca_info = reduce_fc_dimensions(
            all_fc,
            variance_ratio=config.pca_variance,
            n_components=config.pca_n_components,
            random_state=config.random_state,
        )
        if roi_mask is not None:
            pca_info["n_nodes_after_roi_clean"] = effective_nodes
            pca_info["n_rois_dropped"] = int(n_nodes - effective_nodes)
    else:
        fc_for_clustering = all_fc

    # Step 3: Optional k search (on reduced space)
    k_search_results = None
    if config.k_range:
        k_search_results = search_optimal_k(
            fc_for_clustering, k_range=config.k_range,
            n_init=max(20, config.n_init // 5),
            random_state=config.random_state,
        )
        # Pick best k by silhouette
        best = max(k_search_results, key=lambda r: r["silhouette_score"])
        log.info("Best k=%d (silhouette=%.4f)", best["k"], best["silhouette_score"])
        config.k = best["k"]

    # Step 4: Final clustering (on reduced space)
    centroids_reduced, labels, metrics = cluster_dfc_states(
        fc_for_clustering, k=config.k, n_init=config.n_init,
        max_iter=config.max_iter, random_state=config.random_state,
    )

    # Map centroids back to original FC space for template construction
    if pca_obj is not None:
        centroids_fc = pca_obj.inverse_transform(centroids_reduced).astype(np.float32)
        log.info("Centroids inverse-transformed: PCA %d → FC %d dims",
                 centroids_reduced.shape[1], centroids_fc.shape[1])
    else:
        centroids_fc = centroids_reduced

    # Check occupancy
    for state, occ in metrics["occupancy"].items():
        if occ < config.min_occupancy:
            log.warning(
                "State %d occupancy %.1f%% < min %.1f%%",
                state, occ * 100, config.min_occupancy * 100,
            )

    # Step 5: Build template bank (from original-space centroids)
    template_bank = build_dfc_template_bank(
        centroids_fc, n_nodes=effective_nodes, sparsity=config.sparsity,
        inverse_fisher_z=config.fisher_z,
    )
    log.info("Template bank shape: %s, sparsity=%.0f%%",
             template_bank.shape, config.sparsity * 100)

    return DFCResult(
        template_bank=template_bank,
        labels=labels,
        centroids=centroids_fc,
        subject_indices=subject_indices,
        window_counts=window_counts,
        metrics=metrics,
        config=config,
        k_search_results=k_search_results,
        pca_info=pca_info,
        pca_object=pca_obj,
        roi_mask=roi_mask,
    )
