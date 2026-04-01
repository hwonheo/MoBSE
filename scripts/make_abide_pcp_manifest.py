#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


def _pick_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lookup = {str(c).strip().lower(): str(c) for c in df.columns}
    for c in candidates:
        key = str(c).strip().lower()
        if key in lookup:
            return lookup[key]
    return None


def _extract_file_id(nifti_path: str) -> str:
    name = Path(nifti_path).name
    marker = "_func_preproc"
    idx = name.find(marker)
    if idx <= 0:
        return Path(nifti_path).stem
    return name[:idx]


def _parse_int_set(raw: str) -> set[int]:
    out: set[int] = set()
    for token in str(raw).replace(";", ",").split(","):
        tok = token.strip()
        if not tok:
            continue
        out.add(int(tok))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch ABIDE PCP (preprocessed) and emit nifti_manifest CSV for build_templates"
    )
    ap.add_argument("--out-manifest", required=True, help="Output CSV path")
    ap.add_argument("--data-dir", default="data/cache/_nilearn_cache", help="nilearn cache/data dir")
    ap.add_argument("--pipeline", default="cpac", choices=["cpac", "ccs", "dparsf", "niak"])
    ap.add_argument(
        "--n-subjects",
        type=int,
        default=300,
        help="Number of subjects to fetch from ABIDE PCP before local age/diagnosis filtering",
    )
    ap.add_argument("--min-age", type=float, default=18.0)
    ap.add_argument(
        "--dx-group",
        default="2",
        help="Comma-separated DX_GROUP values to keep (ABIDE convention: 2=control, 1=autism). Empty disables filter.",
    )
    ap.add_argument("--state", default="rest", help="State label to write into manifest rows")
    ap.add_argument(
        "--quality-checked",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use ABIDE PCP quality_checked filter (default: true)",
    )
    ap.add_argument(
        "--band-pass-filtering",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Match ABIDE PCP preprocessed branch with band-pass filtering",
    )
    ap.add_argument(
        "--global-signal-regression",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Match ABIDE PCP preprocessed branch with GSR",
    )
    ap.add_argument("--summary-json", default="", help="Optional summary JSON output path")
    args = ap.parse_args()
    if int(args.n_subjects) <= 0:
        raise ValueError("--n-subjects must be >= 1 to avoid accidental full-dataset download.")

    try:
        from nilearn.datasets import fetch_abide_pcp
    except ImportError as exc:  # pragma: no cover
        raise ImportError("nilearn is required. Install with `pip install .[neuro]`.") from exc

    bunch = fetch_abide_pcp(
        data_dir=args.data_dir,
        n_subjects=int(args.n_subjects),
        pipeline=args.pipeline,
        band_pass_filtering=bool(args.band_pass_filtering),
        global_signal_regression=bool(args.global_signal_regression),
        derivatives=["func_preproc"],
        quality_checked=bool(args.quality_checked),
        verbose=1,
    )

    func_paths = list(getattr(bunch, "func_preproc", []))
    pheno = pd.DataFrame(getattr(bunch, "phenotypic", pd.DataFrame())).reset_index(drop=True)
    if len(func_paths) == 0:
        raise RuntimeError("No func_preproc files fetched from ABIDE PCP.")
    if len(pheno) == 0:
        raise RuntimeError("ABIDE phenotypic table is empty.")

    file_ids = [_extract_file_id(p) for p in func_paths]
    records = pd.DataFrame(
        {
            "file_id": file_ids,
            "nifti_path": [str(Path(p).resolve()) for p in func_paths],
        }
    )

    file_col = _pick_column(pheno, ["FILE_ID", "file_id"])
    if file_col is not None:
        merged = records.merge(pheno, left_on="file_id", right_on=file_col, how="left")
    elif len(pheno) == len(records):
        merged = pd.concat([records, pheno], axis=1)
    else:
        raise RuntimeError("Could not align ABIDE phenotypic rows with func_preproc files.")

    age_col = _pick_column(merged, ["AGE_AT_SCAN", "age", "age_years", "ageinyears"])
    if age_col is not None and args.min_age > 0:
        age = pd.to_numeric(merged[age_col], errors="coerce")
        merged = merged.loc[age.ge(float(args.min_age)).fillna(False)].copy()

    dx_col = _pick_column(merged, ["DX_GROUP", "dx_group", "group", "diagnosis", "dx"])
    dx_filter_raw = str(args.dx_group).strip()
    if dx_filter_raw and dx_col is not None:
        wanted = _parse_int_set(dx_filter_raw)
        dx = pd.to_numeric(merged[dx_col], errors="coerce")
        merged = merged.loc[dx.isin(wanted)].copy()

    if args.n_subjects and args.n_subjects > 0:
        merged = merged.head(int(args.n_subjects)).copy()

    if merged.empty:
        raise RuntimeError("No ABIDE subjects left after filtering.")

    merged["subject_id"] = merged["file_id"].map(lambda x: f"abide_{x}")
    merged["state"] = str(args.state).strip().lower()
    merged["confounds_path"] = ""

    out_manifest = Path(args.out_manifest)
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    out_cols = ["subject_id", "state", "nifti_path", "confounds_path"]
    merged[out_cols].to_csv(out_manifest, index=False)

    summary = {
        "manifest_csv": str(out_manifest),
        "rows": int(len(merged)),
        "pipeline": args.pipeline,
        "quality_checked": bool(args.quality_checked),
        "band_pass_filtering": bool(args.band_pass_filtering),
        "global_signal_regression": bool(args.global_signal_regression),
        "min_age": float(args.min_age),
        "dx_group": dx_filter_raw,
        "state": str(args.state).strip().lower(),
    }
    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["summary_json"] = str(summary_path)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
