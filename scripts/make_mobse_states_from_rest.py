#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np

YEO_7_STATES = ["vis", "sommot", "dorsattn", "salventattn", "limbic", "cont", "default"]


def _canonical_network_name(label: str) -> str:
    if not label:
        return ""
    parts = label.split("_")
    if len(parts) < 3:
        return ""
    raw = parts[2]
    mapping = {
        "Vis": "vis",
        "SomMot": "sommot",
        "DorsAttn": "dorsattn",
        "SalVentAttn": "salventattn",
        "Limbic": "limbic",
        "Cont": "cont",
        "Default": "default",
    }
    return mapping.get(raw, "")


def _build_yeo7_node_indices(num_nodes: int) -> Dict[str, List[int]]:
    from nilearn.datasets import fetch_atlas_schaefer_2018

    atlas = fetch_atlas_schaefer_2018(n_rois=num_nodes)
    labels = list(atlas.labels)
    if len(labels) < num_nodes + 1:
        raise RuntimeError(
            f"Schaefer label count mismatch: expected >= {num_nodes + 1}, got {len(labels)}"
        )

    state_to_nodes: Dict[str, List[int]] = {k: [] for k in YEO_7_STATES}
    for node_idx in range(num_nodes):
        raw = labels[node_idx + 1]
        text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
        state = _canonical_network_name(text)
        if state:
            state_to_nodes[state].append(node_idx)

    missing = [k for k, nodes in state_to_nodes.items() if not nodes]
    if missing:
        raise RuntimeError(f"Yeo7 node mapping failed. Missing networks: {missing}")
    return state_to_nodes


def _resolve_node_dir(root: Path, num_nodes: int) -> Path:
    node_dir = root / str(num_nodes)
    return node_dir if node_dir.exists() else root


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create Yeo-7 network states from resting-state ROI timeseries (same node shape, masked per network)."
    )
    ap.add_argument("--input-root", required=True, help="Input timeseries root")
    ap.add_argument("--output-root", required=True, help="Output timeseries root")
    ap.add_argument("--num-nodes", type=int, required=True, help="Schaefer node count (e.g. 100, 200)")
    ap.add_argument("--source-state", default="rest", help="Source state filename stem (default: rest)")
    ap.add_argument("--subjects-limit", type=int, default=0, help="0 means all subjects")
    ap.add_argument(
        "--copy-source-state",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Also copy the original source-state npy into output subject dirs",
    )
    ap.add_argument("--summary-json", default="", help="Optional summary JSON output path")
    args = ap.parse_args()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    input_node_dir = _resolve_node_dir(input_root, int(args.num_nodes))
    output_node_dir = output_root / str(int(args.num_nodes))
    output_node_dir.mkdir(parents=True, exist_ok=True)

    state_to_nodes = _build_yeo7_node_indices(num_nodes=int(args.num_nodes))

    subjects = sorted(p for p in input_node_dir.iterdir() if p.is_dir())
    if args.subjects_limit and int(args.subjects_limit) > 0:
        subjects = subjects[: int(args.subjects_limit)]

    written_subjects = 0
    skipped = 0
    for subject_dir in subjects:
        src = subject_dir / f"{args.source_state}.npy"
        if not src.exists():
            skipped += 1
            continue

        ts = np.load(src)
        if ts.ndim != 2 or ts.shape[1] != int(args.num_nodes):
            skipped += 1
            continue

        dst_subject = output_node_dir / subject_dir.name
        dst_subject.mkdir(parents=True, exist_ok=True)

        if bool(args.copy_source_state):
            np.save(dst_subject / f"{args.source_state}.npy", ts.astype(np.float32))

        for state in YEO_7_STATES:
            masked = np.zeros_like(ts, dtype=np.float32)
            idx = state_to_nodes[state]
            masked[:, idx] = ts[:, idx].astype(np.float32)
            np.save(dst_subject / f"{state}.npy", masked)

        written_subjects += 1

    summary = {
        "input_node_dir": str(input_node_dir),
        "output_node_dir": str(output_node_dir),
        "num_nodes": int(args.num_nodes),
        "source_state": str(args.source_state),
        "states": YEO_7_STATES,
        "subjects_seen": int(len(subjects)),
        "subjects_written": int(written_subjects),
        "subjects_skipped": int(skipped),
        "nodes_per_state": {k: len(v) for k, v in state_to_nodes.items()},
    }
    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["summary_json"] = str(summary_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
