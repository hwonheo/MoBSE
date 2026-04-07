from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from nilearn.connectome import ConnectivityMeasure

from mobse.data.os_data import sparsify_fc


def _load_subject_timeseries(ts_root: Path, num_nodes: int, state: str, max_subjects: int) -> tuple[List[np.ndarray], List[str]]:
    node_dir = ts_root / str(num_nodes)
    if not node_dir.exists():
        raise FileNotFoundError(f"Timeseries node directory not found: {node_dir}")

    series: List[np.ndarray] = []
    subject_ids: List[str] = []
    for sub_dir in sorted(p for p in node_dir.iterdir() if p.is_dir()):
        path = sub_dir / f"{state}.npy"
        if not path.exists():
            continue
        ts = np.load(path)
        if ts.ndim != 2 or ts.shape[1] != num_nodes:
            continue
        series.append(ts.astype(np.float32))
        subject_ids.append(sub_dir.name)
        if len(series) >= max_subjects:
            break

    if not series:
        raise RuntimeError(f"No usable timeseries for state={state}, nodes={num_nodes} under {node_dir}")
    return series, subject_ids


def _build_group_matrix(ts_list: List[np.ndarray], method: str) -> np.ndarray:
    kind = method
    conn = ConnectivityMeasure(kind=kind, standardize="zscore_sample")
    mats = conn.fit_transform(ts_list)
    avg = np.mean(np.stack(mats, axis=0), axis=0)
    avg = np.nan_to_num(avg, nan=0.0, posinf=0.0, neginf=0.0)
    avg = 0.5 * (avg + avg.T)
    np.fill_diagonal(avg, 0.0)
    return avg


def _save_template_bank(path: Path, state: str, matrix: np.ndarray, metadata: Dict[str, object]) -> None:
    payload = {f"template::{state}": matrix.astype(np.float32), "metadata_json": np.array([json.dumps(metadata)], dtype=object)}
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build method-wise rs-fMRI connectivity templates for ds000243 (for MoBSE vs Legacy experiments)."
    )
    ap.add_argument(
        "--timeseries-root",
        default="data/current_canonical/openneuro_ds000243/timeseries",
        help="Root directory that contains node folders (e.g., 100/, 200/).",
    )
    ap.add_argument("--state", default="rest", help="State name to build template for.")
    ap.add_argument("--nodes", default="100,200", help="Comma-separated node sizes.")
    ap.add_argument("--methods", default="correlation,partial correlation,precision,tangent", help="Connectivity methods.")
    ap.add_argument("--sparsities", default="0.1,0.2", help="Comma-separated sparsity keep ratios.")
    ap.add_argument("--max-subjects", type=int, default=90, help="Maximum subjects/runs to include per node.")
    ap.add_argument(
        "--out-dir",
        default="artifacts/current_canonical/ds000243_connectivity_templates_20260402/templates",
        help="Output directory for template banks.",
    )
    args = ap.parse_args()

    ts_root = Path(args.timeseries_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes = [int(x.strip()) for x in args.nodes.split(",") if x.strip()]
    methods = [x.strip() for x in args.methods.split(",") if x.strip()]
    sparsities = [float(x.strip()) for x in args.sparsities.split(",") if x.strip()]

    rows: List[Dict[str, object]] = []
    for node in nodes:
        ts_list, subject_ids = _load_subject_timeseries(ts_root=ts_root, num_nodes=node, state=args.state, max_subjects=args.max_subjects)
        for method in methods:
            group = _build_group_matrix(ts_list=ts_list, method=method)
            for sp in sparsities:
                sparse = sparsify_fc(group, keep_ratio=sp)
                sp_tag = int(round(sp * 100))
                method_tag = method.replace(" ", "_")
                out_path = out_dir / f"atlas{node}_sp{sp_tag}_{method_tag}_template_bank.npz"
                meta = {
                    "dataset": "openneuro_ds000243",
                    "state": args.state,
                    "num_nodes": node,
                    "connectivity_method": method,
                    "sparsity": sp,
                    "subjects_used": len(subject_ids),
                }
                _save_template_bank(path=out_path, state=args.state, matrix=sparse, metadata=meta)
                rows.append(
                    {
                        "num_nodes": node,
                        "connectivity_method": method,
                        "sparsity": sp,
                        "subjects_used": len(subject_ids),
                        "template_path": str(out_path),
                    }
                )

    summary = pd.DataFrame(rows).sort_values(["num_nodes", "connectivity_method", "sparsity"])
    summary_path = out_dir.parent / "connectivity_template_manifest.csv"
    summary.to_csv(summary_path, index=False)
    print(summary.to_string(index=False))
    print(f"\nmanifest_csv={summary_path}")


if __name__ == "__main__":
    main()

