from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import networkx as nx
import numpy as np
import pandas as pd


def _parse_from_name(path: Path) -> tuple[int, float]:
    m = re.search(r"atlas(\d+)_sp(\d+)_template_bank\.npz$", path.name)
    if not m:
        return -1, -1.0
    return int(m.group(1)), int(m.group(2)) / 100.0


def _load_matrix(path: Path, state: str) -> np.ndarray:
    arr = np.load(path, allow_pickle=True)
    key = f"template::{state}"
    if key not in arr.files:
        raise KeyError(f"{path} missing key {key}. available={arr.files}")
    mat = np.asarray(arr[key], dtype=np.float64)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(f"{path} has non-square matrix for {key}: shape={mat.shape}")
    return mat


def _metrics_from_matrix(mat: np.ndarray) -> Dict[str, float]:
    n = int(mat.shape[0])
    np.fill_diagonal(mat, 0.0)
    w = np.asarray(mat, dtype=np.float64)
    abs_w = np.abs(w)

    upper = np.triu(abs_w, k=1)
    edge_mask = upper > 0
    m = int(edge_mask.sum())
    max_edges = n * (n - 1) // 2
    density = float(m / max_edges) if max_edges > 0 else 0.0

    strengths = abs_w.sum(axis=1)
    deg = (abs_w > 0).sum(axis=1)

    g = nx.from_numpy_array(abs_w)
    g.remove_edges_from([(u, v) for u, v, d in g.edges(data=True) if float(d.get("weight", 0.0)) <= 0.0])

    if g.number_of_edges() > 0:
        avg_clustering_w = float(nx.average_clustering(g, weight="weight"))
        avg_clustering = float(nx.average_clustering(g, weight=None))
        lcc_nodes = max(nx.connected_components(g), key=len)
        g_lcc = g.subgraph(lcc_nodes).copy()
        global_eff = float(nx.global_efficiency(g))
        lcc_ratio = float(len(lcc_nodes) / n)
        if g_lcc.number_of_edges() > 0 and g_lcc.number_of_nodes() >= 3:
            comms = list(nx.community.greedy_modularity_communities(g_lcc, weight="weight"))
            modularity = float(nx.community.modularity(g_lcc, comms, weight="weight")) if comms else 0.0
            n_comms = int(len(comms))
        else:
            modularity = 0.0
            n_comms = 0
    else:
        avg_clustering_w = 0.0
        avg_clustering = 0.0
        global_eff = 0.0
        lcc_ratio = 0.0
        modularity = 0.0
        n_comms = 0

    return {
        "num_nodes": n,
        "num_edges": m,
        "density": density,
        "mean_abs_weight": float(upper[edge_mask].mean()) if m > 0 else 0.0,
        "std_abs_weight": float(upper[edge_mask].std()) if m > 0 else 0.0,
        "mean_strength": float(strengths.mean()),
        "std_strength": float(strengths.std()),
        "mean_degree": float(deg.mean()),
        "std_degree": float(deg.std()),
        "avg_clustering": avg_clustering,
        "avg_clustering_weighted": avg_clustering_w,
        "global_efficiency": global_eff,
        "lcc_ratio": lcc_ratio,
        "modularity_lcc": modularity,
        "num_communities_lcc": n_comms,
    }


def _to_markdown(df: pd.DataFrame, out_path: Path) -> None:
    cols = [
        "template",
        "state",
        "num_nodes",
        "sparsity",
        "density",
        "mean_abs_weight",
        "mean_strength",
        "mean_degree",
        "avg_clustering_weighted",
        "global_efficiency",
        "modularity_lcc",
        "num_communities_lcc",
    ]
    view = df[cols].copy()
    for c in [
        "density",
        "mean_abs_weight",
        "mean_strength",
        "mean_degree",
        "avg_clustering_weighted",
        "global_efficiency",
        "modularity_lcc",
    ]:
        view[c] = view[c].map(lambda x: f"{x:.6f}")
    headers = list(view.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in view.iterrows():
        vals = [str(row[c]) for c in headers]
        lines.append("| " + " | ".join(vals) + " |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze graph metrics from MoBSE template_bank npz files.")
    ap.add_argument("--template-glob", required=True, help="Glob for template npz, e.g. artifacts/.../templates/atlas*_template_bank.npz")
    ap.add_argument("--state", default="rest", help="State key name (default: rest)")
    ap.add_argument("--out-dir", required=True, help="Output directory for reports")
    args = ap.parse_args()

    paths = sorted(Path(p) for p in Path().glob(args.template_glob))
    if not paths:
        raise FileNotFoundError(f"No templates matched: {args.template_glob}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, float | int | str]] = []
    for p in paths:
        nodes, sparsity = _parse_from_name(p)
        mat = _load_matrix(p, state=args.state).copy()
        metrics = _metrics_from_matrix(mat)
        rows.append(
            {
                "template": str(p),
                "template_name": p.name,
                "state": args.state,
                "num_nodes": nodes if nodes > 0 else metrics["num_nodes"],
                "sparsity": sparsity,
                **metrics,
            }
        )

    df = pd.DataFrame(rows).sort_values(["num_nodes", "sparsity", "template_name"]).reset_index(drop=True)
    csv_path = out_dir / "template_network_metrics.csv"
    json_path = out_dir / "template_network_metrics.json"
    md_path = out_dir / "template_network_metrics.md"
    manifest_path = out_dir / "template_network_metrics_manifest.json"

    df.to_csv(csv_path, index=False)
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    _to_markdown(df, md_path)

    manifest = {
        "template_glob": args.template_glob,
        "state": args.state,
        "rows": int(len(df)),
        "outputs": {
            "csv": str(csv_path),
            "json": str(json_path),
            "markdown": str(md_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
