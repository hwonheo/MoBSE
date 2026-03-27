from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


def _load_scan(scan_csv: Path) -> Dict[str, Dict[str, object]]:
    rows: Dict[str, Dict[str, object]] = {}
    if not scan_csv.exists():
        return rows
    with scan_csv.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dataset_id = str(row.get("dataset_id", "")).strip()
            if not dataset_id:
                continue
            rows[dataset_id] = {
                "snapshot_tag": str(row.get("snapshot_tag", "")).strip(),
                "adult_count": int(row.get("adult_count") or 0),
            }
    return rows


def _recommend(raw_count: int, usable_count: int) -> str:
    if raw_count <= 0:
        return "pilot_more"
    rate = usable_count / raw_count if raw_count else 0.0
    if usable_count < 10 and rate < 0.5:
        return "drop"
    if rate < 0.5:
        return "pilot_more"
    return "keep"


def _parse_pilot_roots(text: str) -> List[Tuple[str, Path]]:
    pairs: List[Tuple[str, Path]] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"Invalid pilot spec '{token}'. Expected dataset_id:path")
        dataset_id, root = token.split(":", 1)
        dataset_id = dataset_id.strip()
        root = root.strip()
        if not dataset_id or not root:
            raise ValueError(f"Invalid pilot spec '{token}'.")
        pairs.append((dataset_id, Path(root)))
    return pairs


def _load_qc_counts(qc_csv: Path, expected_nodes: int) -> Dict[str, int]:
    if not qc_csv.exists():
        return {"raw_count": 0, "usable_count": 0}
    df = pd.read_csv(qc_csv)
    if "num_nodes_requested" in df.columns:
        df = df[df["num_nodes_requested"] == expected_nodes]
    raw_count = int(len(df))
    usable_count = int((df["status"] == "accepted").sum()) if "status" in df.columns else 0
    return {"raw_count": raw_count, "usable_count": usable_count}


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh strict-usable planning table with pilot QC evidence")
    ap.add_argument(
        "--base-table",
        default="artifacts/openneuro_usable_plan_20260324/reports/openneuro_usable_yield_table.csv",
    )
    ap.add_argument(
        "--scan-csv",
        default="artifacts/phase2_ds_scan250_20260324/reports/ds00_scan.csv",
    )
    ap.add_argument("--expected-nodes", type=int, default=100)
    ap.add_argument(
        "--pilot-roots",
        default=(
            "ds001747:data/os_strict_pilot_ds001747,"
            "ds001796:data/os_strict_pilot_ds001796,"
            "ds001386:data/os_strict_pilot_ds001386,"
            "ds001771:data/os_strict_pilot_ds001771"
        ),
        help="Comma-separated dataset_id:path pairs",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/openneuro_usable_plan_20260326/reports",
    )
    args = ap.parse_args()

    base_table = Path(args.base_table)
    scan_csv = Path(args.scan_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not base_table.exists():
        raise FileNotFoundError(f"Base table not found: {base_table}")

    df = pd.read_csv(base_table)
    scan = _load_scan(scan_csv)

    pilot_roots = _parse_pilot_roots(args.pilot_roots)
    missing_qc: Dict[str, str] = {}
    for dataset_id, root in pilot_roots:
        qc_csv = root / "timeseries" / "openneuro_qc.csv"
        counts = _load_qc_counts(qc_csv=qc_csv, expected_nodes=args.expected_nodes)
        raw_count = int(counts["raw_count"])
        usable_count = int(counts["usable_count"])
        if raw_count == 0 and not qc_csv.exists():
            missing_qc[dataset_id] = str(qc_csv)

        existing = df[df["dataset_id"] == dataset_id]
        adult_count = int(scan.get(dataset_id, {}).get("adult_count", 0))
        if adult_count <= 0 and not existing.empty:
            adult_count = int(existing.iloc[0].get("adult_count", 0))
        snapshot_tag = str(scan.get(dataset_id, {}).get("snapshot_tag", ""))
        if not snapshot_tag and not existing.empty:
            snapshot_tag = str(existing.iloc[0].get("snapshot_tag", ""))

        usable_rate = (usable_count / raw_count) if raw_count else float("nan")
        projected = int(round(adult_count * usable_rate)) if raw_count else 0
        rec = _recommend(raw_count=raw_count, usable_count=usable_count)
        row = {
            "dataset_id": dataset_id,
            "snapshot_tag": snapshot_tag,
            "adult_count": adult_count,
            "raw_count": raw_count,
            "usable_count": usable_count,
            "usable_rate": usable_rate,
            "projected_usable_strict": projected,
            "recommendation": rec,
        }

        if existing.empty:
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            idx = existing.index[0]
            for key, value in row.items():
                df.at[idx, key] = value

    df = df.sort_values(["recommendation", "projected_usable_strict", "adult_count"], ascending=[True, False, False])

    csv_path = out_dir / "openneuro_usable_yield_table.csv"
    json_path = out_dir / "openneuro_usable_yield_table.json"
    manifest_path = out_dir / "openneuro_usable_plan_manifest.json"
    df.to_csv(csv_path, index=False)
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")

    keep_df = df[df["recommendation"] == "keep"]
    manifest = {
        "base_table": str(base_table),
        "scan_csv": str(scan_csv),
        "expected_nodes": int(args.expected_nodes),
        "pilot_roots": {dataset_id: str(root) for dataset_id, root in pilot_roots},
        "missing_qc": missing_qc,
        "keep_datasets": keep_df["dataset_id"].tolist(),
        "projected_usable_keep_total": int(keep_df["projected_usable_strict"].sum()),
        "table_csv": str(csv_path),
        "table_json": str(json_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
