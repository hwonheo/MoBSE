#!/usr/bin/env python3
"""ABIDE CC200 dFC Pilot Test.

Downloads ABIDE PCP HC subjects via nilearn, runs the dFC pipeline,
and reports clustering metrics + template bank summary.

Usage:
    python scripts/run_abide_dfc_pilot.py --n-subjects 50 --k 5
    python scripts/run_abide_dfc_pilot.py --n-subjects 0 --k-range 3 4 5 6 7
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_abide_cc200(
    n_subjects: int = 0,
    min_age: float = 18.0,
    min_timepoints: int = 150,
    pipeline: str = "cpac",
) -> tuple[list[np.ndarray], list[float], pd.DataFrame]:
    """Load ABIDE PCP HC resting-state ROI timeseries (CC200).

    Args:
        n_subjects: Number of HC subjects (0 = all available).
        min_age: Minimum age filter.
        min_timepoints: Minimum scan length to include.
        pipeline: ABIDE preprocessing pipeline.

    Returns:
        timeseries_list: List of [T, 200] arrays.
        tr_list: Estimated TR per subject (from site defaults).
        pheno_df: Phenotypic DataFrame for included subjects.
    """
    from nilearn.datasets import fetch_abide_pcp

    log.info("Fetching ABIDE PCP (pipeline=%s, DX_GROUP=2)...", pipeline)
    fetch_n = n_subjects if n_subjects > 0 else 800  # fetch more, filter later

    data = fetch_abide_pcp(
        n_subjects=fetch_n,
        pipeline=pipeline,
        band_pass_filtering=True,
        global_signal_regression=True,
        derivatives=["rois_cc200"],
        DX_GROUP=2,
    )

    pheno = pd.DataFrame(data.phenotypic)
    log.info("Fetched %d HC subjects", len(data.rois_cc200))

    # Site-level TR estimates (from ABIDE documentation)
    # Most sites used TR ~2.0s, some exceptions
    site_tr = {
        "PITT": 1.5, "OLIN": 1.5, "OHSU": 2.5, "SDSU": 2.0,
        "TRINITY": 2.0, "UM_1": 2.0, "UM_2": 2.0, "USM": 2.0,
        "YALE": 2.0, "CMU": 2.0, "LEUVEN_1": 1.66, "LEUVEN_2": 1.66,
        "KKI": 2.5, "NYU": 2.0, "STANFORD": 2.0, "UCLA_1": 3.0,
        "UCLA_2": 3.0, "MAX_MUN": 3.0, "CALTECH": 2.0, "SBL": 2.2,
    }

    timeseries_list = []
    tr_list = []
    keep_idx = []

    for i, ts_arr in enumerate(data.rois_cc200):
        ts = np.array(ts_arr, dtype=np.float32)
        age = float(pheno.iloc[i]["AGE_AT_SCAN"])
        site = str(pheno.iloc[i]["SITE_ID"])

        # Filters
        if age < min_age:
            continue
        if ts.shape[0] < min_timepoints:
            continue

        tr = site_tr.get(site, 2.0)
        timeseries_list.append(ts)
        tr_list.append(tr)
        keep_idx.append(i)

    pheno_filtered = pheno.iloc[keep_idx].reset_index(drop=True)

    log.info(
        "After filtering (age>=%.0f, tp>=%d): %d subjects from %d sites",
        min_age, min_timepoints, len(timeseries_list),
        pheno_filtered["SITE_ID"].nunique(),
    )

    # Summary
    shapes = [ts.shape for ts in timeseries_list]
    tps = [s[0] for s in shapes]
    log.info(
        "  Timepoints: min=%d, max=%d, mean=%.0f, median=%.0f",
        min(tps), max(tps), np.mean(tps), np.median(tps),
    )

    return timeseries_list, tr_list, pheno_filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="ABIDE CC200 dFC pilot")
    parser.add_argument("--n-subjects", type=int, default=50,
                        help="Number of subjects (0=all)")
    parser.add_argument("--k", type=int, default=5,
                        help="Number of dFC states")
    parser.add_argument("--k-range", type=int, nargs="*", default=None,
                        help="Search range for optimal k")
    parser.add_argument("--window-sec", type=float, default=45.0)
    parser.add_argument("--stride-sec", type=float, default=2.0)
    parser.add_argument("--sparsity", type=float, default=0.2)
    parser.add_argument("--min-age", type=float, default=18.0)
    parser.add_argument("--min-timepoints", type=int, default=150)
    parser.add_argument("--pca-variance", type=float, default=0.95,
                        help="PCA variance retention (0=no PCA, 0.95=95%%)")
    parser.add_argument("--pca-n-components", type=int, default=None,
                        help="Fixed PCA components (overrides --pca-variance)")
    parser.add_argument("--no-subject-z-norm", action="store_true",
                        help="Disable per-subject z-normalization")
    parser.add_argument("--no-roi-clean", action="store_true",
                        help="Disable zero-variance ROI removal")
    parser.add_argument("--output-dir", type=str,
                        default="artifacts/abide_dfc_pilot")
    args = parser.parse_args()

    t0 = time.time()

    # --- Load data ---
    timeseries_list, tr_list, pheno = load_abide_cc200(
        n_subjects=args.n_subjects,
        min_age=args.min_age,
        min_timepoints=args.min_timepoints,
    )

    if not timeseries_list:
        log.error("No subjects passed filtering.")
        return

    n_nodes = timeseries_list[0].shape[1]

    # --- Run dFC pipeline ---
    from mobse.data.dfc import DFCConfig, run_dfc_pipeline

    config = DFCConfig(
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
        k=args.k,
        k_range=args.k_range,
        sparsity=args.sparsity,
        min_timepoints=args.min_timepoints,
        pca_variance=args.pca_variance,
        pca_n_components=args.pca_n_components,
        subject_z_norm=not args.no_subject_z_norm,
        drop_zero_var_rois=not args.no_roi_clean,
    )

    result = run_dfc_pipeline(
        timeseries_list=timeseries_list,
        tr_list=tr_list,
        n_nodes=n_nodes,
        config=config,
    )

    elapsed = time.time() - t0

    # --- Save outputs ---
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Template bank
    np.savez_compressed(
        out_dir / "dfc_template_bank.npz",
        template_bank=result.template_bank,
        centroids=result.centroids,
        labels=result.labels,
        subject_indices=result.subject_indices,
        window_counts=result.window_counts,
    )

    # Save PCA object for centroid-based label assignment
    if result.pca_object is not None:
        import pickle
        with open(out_dir / "pca_object.pkl", "wb") as f:
            pickle.dump(result.pca_object, f)
        log.info("Saved PCA object: %s", out_dir / "pca_object.pkl")

    # Metrics
    report = {
        "config": {
            "window_sec": config.window_sec,
            "stride_sec": config.stride_sec,
            "k": config.k,
            "sparsity": config.sparsity,
            "taper": config.taper,
            "fisher_z": config.fisher_z,
            "min_age": args.min_age,
            "min_timepoints": args.min_timepoints,
        },
        "data": {
            "n_subjects_input": args.n_subjects,
            "n_subjects_used": int(np.sum(result.window_counts > 0)),
            "n_nodes_original": n_nodes,
            "n_nodes_effective": result.template_bank.shape[1],
            "n_rois_dropped": int(n_nodes - result.template_bank.shape[1]),
            "atlas": "CC200",
            "total_windows": int(len(result.labels)),
            "subject_z_norm": config.subject_z_norm,
        },
        "clustering": result.metrics,
        "pca": result.pca_info,
        "elapsed_sec": elapsed,
    }

    if result.k_search_results:
        report["k_search"] = result.k_search_results

    with open(out_dir / "dfc_pilot_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Phenotypic
    pheno.to_csv(out_dir / "included_subjects.csv", index=False)

    # --- Print summary ---
    print("\n" + "=" * 60)
    print("  ABIDE CC200 dFC Pilot Complete")
    print("=" * 60)
    print(f"  Subjects used: {report['data']['n_subjects_used']}")
    print(f"  Total windows: {report['data']['total_windows']}")
    n_eff = result.template_bank.shape[1]
    roi_info = f" → {n_eff} after cleaning" if n_eff != n_nodes else ""
    print(f"  Atlas: CC200 ({n_nodes} nodes{roi_info})")
    if config.subject_z_norm:
        print(f"  Subject z-normalization: ON")
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
