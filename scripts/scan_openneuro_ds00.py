from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests

from mobse.data.prepare import (
    _list_openneuro_files,
    _openneuro_graphql_query,
    _pick_column,
    _resolve_openneuro_snapshot_tag,
    _select_openneuro_bold_entries,
    _select_openneuro_subjects,
)


def _fetch_dataset_ids(api_url: str, prefix: str, limit: int) -> List[str]:
    query = """
    query($first: Int!, $after: String) {
      datasets(first: $first, after: $after) {
        edges {
          node {
            id
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """
    after = None
    out: List[str] = []
    while len(out) < limit:
        data = _openneuro_graphql_query(
            api_url=api_url,
            query=query,
            variables={"first": 100, "after": after},
        )
        conn = data["datasets"]
        for edge in conn["edges"]:
            dataset_id = str(edge["node"]["id"])
            if dataset_id.startswith(prefix):
                out.append(dataset_id)
                if len(out) >= limit:
                    break
        if not conn["pageInfo"]["hasNextPage"] or len(out) >= limit:
            break
        after = conn["pageInfo"]["endCursor"]
    return out


def _scan_dataset(
    dataset_id: str,
    api_url: str,
    min_age: int,
    task: str,
    probe_subjects: int,
) -> Dict[str, object]:
    tag = _resolve_openneuro_snapshot_tag(dataset_id=dataset_id, snapshot_tag=None, api_url=api_url)
    root_files = _list_openneuro_files(
        dataset_id=dataset_id,
        snapshot_tag=tag,
        api_url=api_url,
        progress=None,
        recursive=False,
    )
    participants_entry = next(
        (f for f in root_files if f.relative_path.lower().endswith("participants.tsv")),
        None,
    )
    if participants_entry is None:
        return {
            "dataset_id": dataset_id,
            "snapshot_tag": tag,
            "has_participants": False,
            "adult_count": 0,
            "rest_like": False,
            "error": "participants.tsv missing",
        }

    participants_text = requests.get(participants_entry.url, timeout=60).text
    df = pd.read_csv(io.StringIO(participants_text), sep="\t", dtype=str)
    age_col = _pick_column(df, ["age", "age_years", "ageinyears"])
    diagnosis_col = _pick_column(df, ["diagnosis", "group", "dx"])

    if age_col is None:
        return {
            "dataset_id": dataset_id,
            "snapshot_tag": tag,
            "has_participants": True,
            "adult_count": 0,
            "rest_like": False,
            "rows": int(len(df)),
            "has_age": False,
            "has_diagnosis": bool(diagnosis_col),
            "error": "age column missing",
        }

    selection = _select_openneuro_subjects(
        participants_tsv_text=participants_text,
        diagnosis="",
        min_age=min_age,
        n_subjects=max(probe_subjects, 1),
        strict_hc=False,
    )
    probe_ids = selection["participant_ids"][:probe_subjects]
    adult_count = len(
        pd.to_numeric(df[age_col], errors="coerce").ge(float(min_age)).fillna(False).to_numpy().nonzero()[0]
    )

    if not probe_ids:
        return {
            "dataset_id": dataset_id,
            "snapshot_tag": tag,
            "has_participants": True,
            "adult_count": 0,
            "rest_like": False,
            "rows": int(len(df)),
            "has_age": True,
            "has_diagnosis": bool(diagnosis_col),
            "error": "no adult participants",
        }

    files = _list_openneuro_files(
        dataset_id=dataset_id,
        snapshot_tag=tag,
        api_url=api_url,
        progress=None,
        recursive=True,
        allowed_subjects=probe_ids,
    )
    try:
        selected = _select_openneuro_bold_entries(
            files=files,
            participant_ids=probe_ids,
            task=task,
            n_subjects=1,
        )
        rest_like = bool(selected["entries"])
    except Exception:
        rest_like = False

    return {
        "dataset_id": dataset_id,
        "snapshot_tag": tag,
        "has_participants": True,
        "rows": int(len(df)),
        "adult_count": int(adult_count),
        "has_age": True,
        "has_diagnosis": bool(diagnosis_col),
        "rest_like": rest_like,
        "error": "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan ds00* OpenNeuro datasets for Phase-2 collection")
    ap.add_argument("--api-url", default="https://openneuro.org/crn/graphql")
    ap.add_argument("--prefix", default="ds00")
    ap.add_argument("--max-datasets", type=int, default=250)
    ap.add_argument("--min-age", type=int, default=18)
    ap.add_argument("--task", default="rest,restingstate")
    ap.add_argument("--probe-subjects", type=int, default=30)
    ap.add_argument("--target-subjects", type=int, default=300)
    ap.add_argument(
        "--out-dir",
        default="artifacts/phase2_ds00_scan/reports",
        help="Output directory for CSV/JSON summary",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset_ids = _fetch_dataset_ids(args.api_url, prefix=args.prefix, limit=args.max_datasets)
    print(f"[scan] dataset candidates: {len(dataset_ids)}")

    rows: List[Dict[str, object]] = []
    for idx, dataset_id in enumerate(dataset_ids, start=1):
        try:
            row = _scan_dataset(
                dataset_id=dataset_id,
                api_url=args.api_url,
                min_age=args.min_age,
                task=args.task,
                probe_subjects=args.probe_subjects,
            )
            rows.append(row)
            print(
                f"[scan] {idx}/{len(dataset_ids)} {dataset_id} "
                f"adult={row.get('adult_count', 0)} rest_like={row.get('rest_like', False)} "
                f"error={row.get('error', '')}"
            )
        except Exception as exc:
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "snapshot_tag": "",
                    "has_participants": False,
                    "adult_count": 0,
                    "rest_like": False,
                    "error": str(exc),
                }
            )
            print(f"[scan] {idx}/{len(dataset_ids)} {dataset_id} error={exc}")

    rows_sorted = sorted(
        rows,
        key=lambda r: (bool(r.get("rest_like")), int(r.get("adult_count", 0))),
        reverse=True,
    )

    selected: List[Dict[str, object]] = []
    total = 0
    for row in rows_sorted:
        if not row.get("rest_like"):
            continue
        adult_n = int(row.get("adult_count", 0))
        if adult_n <= 0:
            continue
        selected.append(row)
        total += adult_n
        if total >= args.target_subjects:
            break

    csv_path = out_dir / "ds00_scan.csv"
    json_path = out_dir / "ds00_scan.json"
    pick_path = out_dir / "phase2_dataset_pick.json"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset_id",
                "snapshot_tag",
                "has_participants",
                "rows",
                "adult_count",
                "has_age",
                "has_diagnosis",
                "rest_like",
                "error",
            ],
        )
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(row)

    json_path.write_text(json.dumps(rows_sorted, indent=2), encoding="utf-8")
    pick_payload = {
        "target_subjects": args.target_subjects,
        "estimated_subjects": total,
        "task": args.task,
        "min_age": args.min_age,
        "datasets": [row["dataset_id"] for row in selected],
        "selected": selected,
    }
    pick_path.write_text(json.dumps(pick_payload, indent=2), encoding="utf-8")

    print(f"[done] wrote {csv_path}")
    print(f"[done] wrote {json_path}")
    print(f"[done] wrote {pick_path}")
    print(json.dumps(pick_payload, indent=2))


if __name__ == "__main__":
    main()
