from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def _load_adult_counts(scan_csvs: List[Path]) -> Dict[str, Dict[str, object]]:
    rows: Dict[str, Dict[str, object]] = {}
    for scan_csv in scan_csvs:
        if not scan_csv.exists():
            continue
        with scan_csv.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dataset_id = str(row["dataset_id"]).strip()
                candidate = {
                    "snapshot_tag": str(row.get("snapshot_tag", "")).strip(),
                    "adult_count": int(row.get("adult_count") or 0),
                    "rest_like": str(row.get("rest_like", "")).strip().lower() in {"true", "1"},
                }
                current = rows.get(dataset_id)
                if current is None or int(candidate["adult_count"]) > int(current["adult_count"]):
                    rows[dataset_id] = candidate
    return rows


def _count_raw_bold(openneuro_root: Path, dataset_id: str) -> int:
    ds_root = openneuro_root / dataset_id
    if not ds_root.exists():
        return 0
    return sum(1 for _ in ds_root.rglob("*_bold.nii.gz"))


def _count_usable_subjects(timeseries_root: Path, dataset_id: str, expected_nodes: int) -> int:
    node_root = timeseries_root / str(expected_nodes)
    if not node_root.exists():
        return 0
    usable = 0
    for subject_dir in sorted(p for p in node_root.iterdir() if p.is_dir() and p.name.startswith(f"{dataset_id}_")):
        rest_file = subject_dir / "rest.npy"
        if not rest_file.exists():
            continue
        try:
            import numpy as np

            arr = np.load(rest_file, mmap_mode="r")
        except Exception:
            continue
        if arr.ndim == 2 and arr.shape[1] == expected_nodes:
            usable += 1
    return usable


def _recommend(raw_count: int, usable_count: int) -> str:
    if raw_count <= 0:
        return "pilot_more"
    rate = usable_count / raw_count if raw_count else 0.0
    if usable_count < 10 and rate < 0.5:
        return "drop"
    if rate < 0.5:
        return "pilot_more"
    return "keep"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build usable-yield planning table from OpenNeuro runs")
    ap.add_argument(
        "--scan-csvs",
        default="artifacts/phase2_ds_scan_20260324/reports/ds00_scan.csv,artifacts/phase2_ds00_scan_20260314/reports/ds00_scan.csv",
        help="Comma-separated scan CSVs; the highest adult_count per dataset is kept",
    )
    ap.add_argument("--openneuro-root", default="data/os_phase2_ds00_600_gsr_n100/openneuro")
    ap.add_argument("--timeseries-root", default="data/os_phase2_ds00_600_gsr_n100/timeseries")
    ap.add_argument("--expected-nodes", type=int, default=100)
    ap.add_argument(
        "--datasets",
        default="ds000030,ds000243,ds001461,ds000208,ds000245,ds000210,ds000172",
        help="Comma-separated dataset ids to include",
    )
    ap.add_argument("--out-dir", default="artifacts/openneuro_usable_plan_20260324/reports")
    args = ap.parse_args()

    scan_csvs = [Path(token.strip()) for token in args.scan_csvs.split(",") if token.strip()]
    openneuro_root = Path(args.openneuro_root)
    timeseries_root = Path(args.timeseries_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scan_rows = _load_adult_counts(scan_csvs)
    dataset_ids = [token.strip() for token in args.datasets.split(",") if token.strip()]

    table_rows: List[Dict[str, object]] = []
    for dataset_id in dataset_ids:
        scan = scan_rows.get(dataset_id, {})
        adult_count = int(scan.get("adult_count", 0))
        raw_count = _count_raw_bold(openneuro_root, dataset_id)
        usable_count = _count_usable_subjects(timeseries_root, dataset_id, expected_nodes=args.expected_nodes)
        usable_rate = (usable_count / raw_count) if raw_count else float("nan")
        projected_usable = int(round(adult_count * usable_rate)) if raw_count else 0
        table_rows.append(
            {
                "dataset_id": dataset_id,
                "snapshot_tag": str(scan.get("snapshot_tag", "")),
                "adult_count": adult_count,
                "raw_count": raw_count,
                "usable_count": usable_count,
                "usable_rate": usable_rate,
                "projected_usable_strict": projected_usable,
                "recommendation": _recommend(raw_count=raw_count, usable_count=usable_count),
            }
        )

    df = pd.DataFrame(table_rows)
    df = df.sort_values(["recommendation", "projected_usable_strict", "adult_count"], ascending=[True, False, False])

    csv_path = out_dir / "openneuro_usable_yield_table.csv"
    json_path = out_dir / "openneuro_usable_yield_table.json"
    manifest_path = out_dir / "openneuro_usable_plan_manifest.json"

    df.to_csv(csv_path, index=False)
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")

    keep_df = df[df["recommendation"] == "keep"]
    manifest = {
        "expected_nodes": args.expected_nodes,
        "scan_csvs": [str(p) for p in scan_csvs],
        "datasets": dataset_ids,
        "keep_datasets": keep_df["dataset_id"].tolist(),
        "projected_usable_keep_total": int(keep_df["projected_usable_strict"].sum()),
        "table_csv": str(csv_path),
        "table_json": str(json_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
