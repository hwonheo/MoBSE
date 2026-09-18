#!/usr/bin/env python3
"""AOMIC Streaming ROI Extraction.

Downloads fMRIPrep BOLD + confounds per subject, extracts Schaefer ROI
timeseries, saves .npy, then deletes the NIfTI to minimize disk usage.

Usage:
    # 1-subject pilot test (PIOP2, sub-0001)
    python scripts/stream_aomic_extract.py \
        --dataset piop2 --subjects 1 --nodes 100 200

    # Full PIOP2
    python scripts/stream_aomic_extract.py \
        --dataset piop2 --subjects 0 --nodes 100 200

    # Full ID1000 rest-only
    python scripts/stream_aomic_extract.py \
        --dataset id1000 --subjects 0 --nodes 100 200 --tasks restingstate

Date: 2026-04-15
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASET_REGISTRY: Dict[str, str] = {
    "id1000": "ds003097",
    "piop1": "ds002785",
    "piop2": "ds002790",
}

S3_BASE = "s3://openneuro.org"

# fMRIPrep confound columns to use (36P-like strategy)
# Refs: Ciric et al. 2017, Parkes et al. 2018
CONFOUND_COLS_24P = [
    # 6 motion parameters
    "trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
    # temporal derivatives of motion
    "trans_x_derivative1", "trans_y_derivative1", "trans_z_derivative1",
    "rot_x_derivative1", "rot_y_derivative1", "rot_z_derivative1",
    # quadratic terms
    "trans_x_power2", "trans_y_power2", "trans_z_power2",
    "rot_x_power2", "rot_y_power2", "rot_z_power2",
    "trans_x_derivative1_power2", "trans_y_derivative1_power2",
    "trans_z_derivative1_power2",
    "rot_x_derivative1_power2", "rot_y_derivative1_power2",
    "rot_z_derivative1_power2",
]

CONFOUND_COLS_TISSUE = ["csf", "white_matter"]

CONFOUND_COLS_COMPCOR = [f"a_comp_cor_0{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SubjectResult:
    subject_id: str
    dataset: str
    task: str
    atlas_nodes: int
    n_timepoints: int
    n_nodes: int
    output_path: str
    mean_fd: Optional[float] = None
    scan_duration_sec: Optional[float] = None
    tr: Optional[float] = None
    status: str = "ok"
    error: Optional[str] = None


@dataclass
class RunManifest:
    dataset: str
    ds_id: str
    start_time: str = ""
    end_time: str = ""
    total_subjects: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def s3_sync(
    s3_path: str,
    local_path: str,
    include_patterns: List[str],
) -> bool:
    """Download files from S3 matching include patterns."""
    cmd = [
        "aws", "s3", "sync", "--no-sign-request",
        s3_path, local_path,
        "--exclude", "*",
    ]
    for pat in include_patterns:
        cmd.extend(["--include", pat])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            log.warning("s3 sync stderr: %s", result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("S3 sync timed out")
        return False


def s3_cp(s3_path: str, local_path: str) -> bool:
    """Download a single file from S3."""
    cmd = [
        "aws", "s3", "cp", "--no-sign-request",
        s3_path, local_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


# ---------------------------------------------------------------------------
# Confounds handling
# ---------------------------------------------------------------------------

def load_fmriprep_confounds(
    confounds_tsv: Path,
    strategy: str = "24p_acompcor",
) -> Optional[np.ndarray]:
    """Load and select confound columns from fMRIPrep TSV.

    Strategies:
      - 24p: 24 motion parameters (6 + derivatives + quadratic)
      - 24p_acompcor: 24p + 5 aCompCor components
      - 36p: 24p + CSF + WM + their derivatives + quadratic
    """
    df = pd.read_csv(confounds_tsv, sep="\t")

    if strategy == "24p":
        cols = CONFOUND_COLS_24P
    elif strategy == "24p_acompcor":
        cols = CONFOUND_COLS_24P + CONFOUND_COLS_COMPCOR
    elif strategy == "36p":
        cols = CONFOUND_COLS_24P + CONFOUND_COLS_TISSUE
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    # Select available columns (some may be missing)
    available = [c for c in cols if c in df.columns]
    if len(available) < len(cols) * 0.5:
        log.warning(
            "Only %d/%d confound columns found in %s",
            len(available), len(cols), confounds_tsv.name,
        )

    if not available:
        return None

    confounds = df[available].apply(pd.to_numeric, errors="coerce")
    arr = confounds.to_numpy(dtype=np.float32)
    # Replace NaN (common in first row for derivatives) with 0
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def compute_mean_fd(confounds_tsv: Path) -> Optional[float]:
    """Extract mean framewise displacement from confounds TSV."""
    df = pd.read_csv(confounds_tsv, sep="\t")
    if "framewise_displacement" not in df.columns:
        return None
    fd = pd.to_numeric(df["framewise_displacement"], errors="coerce")
    return float(fd.mean(skipna=True))


# ---------------------------------------------------------------------------
# ROI extraction
# ---------------------------------------------------------------------------

def extract_roi_timeseries(
    bold_path: Path,
    confounds: Optional[np.ndarray],
    num_nodes: int,
    tr: float = 0.75,
    high_pass: float = 0.008,
    low_pass: float = 0.1,
) -> np.ndarray:
    """Extract Schaefer ROI timeseries with confound regression.

    Returns: np.ndarray of shape [T, num_nodes]
    """
    from nilearn.datasets import fetch_atlas_schaefer_2018
    from nilearn.maskers import NiftiLabelsMasker

    atlas = fetch_atlas_schaefer_2018(n_rois=num_nodes)
    masker = NiftiLabelsMasker(
        labels_img=atlas.maps,
        standardize="zscore_sample",
        t_r=tr,
        detrend=True,
        high_pass=high_pass,
        low_pass=low_pass,
    )
    ts = masker.fit_transform(str(bold_path), confounds=confounds)
    return ts.astype(np.float32)


# ---------------------------------------------------------------------------
# Streaming processor
# ---------------------------------------------------------------------------

def discover_bold_files(
    fmriprep_dir: Path,
    subject_id: str,
    tasks: Optional[List[str]] = None,
) -> List[Dict[str, Path]]:
    """Find BOLD + confounds file pairs for a subject."""
    func_dir = fmriprep_dir / subject_id / "func"
    if not func_dir.exists():
        return []

    bold_files = sorted(func_dir.glob(
        "*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz"
    ))

    pairs = []
    for bold in bold_files:
        # Extract task name from BIDS filename
        parts = bold.name.split("_")
        task_part = [p for p in parts if p.startswith("task-")]
        if not task_part:
            continue
        task_name = task_part[0].replace("task-", "")

        if tasks and task_name not in tasks:
            continue

        # Find matching confounds TSV
        confounds_pattern = bold.name.replace(
            "space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz",
            "desc-confounds_regressors.tsv",
        )
        # Handle potential _acq- or other BIDS entities between task and space
        confounds_candidates = list(func_dir.glob(
            f"*task-{task_name}*desc-confounds_regressors.tsv"
        ))

        confounds_path = None
        if confounds_candidates:
            confounds_path = confounds_candidates[0]

        pairs.append({
            "bold": bold,
            "confounds": confounds_path,
            "task": task_name,
        })

    return pairs


def process_one_subject(
    dataset_name: str,
    ds_id: str,
    subject_id: str,
    output_root: Path,
    nodes_list: List[int],
    tasks: Optional[List[str]] = None,
    tr: float = 0.75,
    confound_strategy: str = "24p_acompcor",
    mean_fd_threshold: float = 0.5,
    min_timepoints: int = 100,
) -> List[SubjectResult]:
    """Stream-process a single subject: download → extract → cleanup."""
    results = []

    with tempfile.TemporaryDirectory(prefix=f"aomic_{subject_id}_") as tmpdir:
        tmp = Path(tmpdir)
        fmriprep_tmp = tmp / "derivatives" / "fmriprep"

        # --- Download ---
        t0 = time.time()
        s3_prefix = f"{S3_BASE}/{ds_id}/derivatives/fmriprep/{subject_id}"
        local_prefix = str(fmriprep_tmp / subject_id)

        log.info("[%s] Downloading fMRIPrep derivatives...", subject_id)
        ok = s3_sync(
            f"{S3_BASE}/{ds_id}/derivatives/fmriprep/{subject_id}",
            str(fmriprep_tmp / subject_id),
            include_patterns=[
                "func/*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz",
                "func/*space-MNI152NLin2009cAsym*desc-preproc_bold.json",
                "func/*desc-confounds_regressors.tsv",
                "func/*desc-confounds_regressors.json",
            ],
        )
        dl_sec = time.time() - t0

        if not ok:
            log.error("[%s] Download failed", subject_id)
            results.append(SubjectResult(
                subject_id=subject_id, dataset=dataset_name,
                task="all", atlas_nodes=0, n_timepoints=0, n_nodes=0,
                output_path="", status="download_failed",
                error="S3 sync failed",
            ))
            return results

        log.info("[%s] Download complete (%.1fs)", subject_id, dl_sec)

        # --- Discover BOLD files ---
        bold_pairs = discover_bold_files(fmriprep_tmp, subject_id, tasks)
        if not bold_pairs:
            log.warning("[%s] No BOLD files found after download", subject_id)
            results.append(SubjectResult(
                subject_id=subject_id, dataset=dataset_name,
                task="all", atlas_nodes=0, n_timepoints=0, n_nodes=0,
                output_path="", status="no_bold",
                error="No matching BOLD files in fMRIPrep derivatives",
            ))
            return results

        log.info("[%s] Found %d BOLD files: %s", subject_id, len(bold_pairs),
                 [p["task"] for p in bold_pairs])

        # --- Process each task × atlas ---
        for pair in bold_pairs:
            task_name = pair["task"]
            bold_path = pair["bold"]
            confounds_path = pair["confounds"]

            # QC: mean FD
            mean_fd = None
            if confounds_path and confounds_path.exists():
                mean_fd = compute_mean_fd(confounds_path)
                if mean_fd is not None and mean_fd > mean_fd_threshold:
                    log.warning(
                        "[%s/%s] mean FD=%.3f > %.2f, skipping",
                        subject_id, task_name, mean_fd, mean_fd_threshold,
                    )
                    results.append(SubjectResult(
                        subject_id=subject_id, dataset=dataset_name,
                        task=task_name, atlas_nodes=0, n_timepoints=0,
                        n_nodes=0, output_path="", mean_fd=mean_fd,
                        status="excluded_motion",
                        error=f"mean_fd={mean_fd:.3f} > {mean_fd_threshold}",
                    ))
                    continue

            # Load confounds
            confounds_arr = None
            if confounds_path and confounds_path.exists():
                confounds_arr = load_fmriprep_confounds(
                    confounds_path, strategy=confound_strategy,
                )

            for n_nodes in nodes_list:
                t1 = time.time()
                try:
                    ts = extract_roi_timeseries(
                        bold_path=bold_path,
                        confounds=confounds_arr,
                        num_nodes=n_nodes,
                        tr=tr,
                    )
                except Exception as e:
                    log.error(
                        "[%s/%s/n%d] Extraction failed: %s",
                        subject_id, task_name, n_nodes, e,
                    )
                    results.append(SubjectResult(
                        subject_id=subject_id, dataset=dataset_name,
                        task=task_name, atlas_nodes=n_nodes,
                        n_timepoints=0, n_nodes=n_nodes, output_path="",
                        mean_fd=mean_fd, status="extraction_failed",
                        error=str(e),
                    ))
                    continue

                n_tp = ts.shape[0]
                ext_sec = time.time() - t1

                # QC: minimum timepoints
                if n_tp < min_timepoints:
                    log.warning(
                        "[%s/%s/n%d] Only %d timepoints (< %d), skipping",
                        subject_id, task_name, n_nodes, n_tp, min_timepoints,
                    )
                    results.append(SubjectResult(
                        subject_id=subject_id, dataset=dataset_name,
                        task=task_name, atlas_nodes=n_nodes,
                        n_timepoints=n_tp, n_nodes=n_nodes, output_path="",
                        mean_fd=mean_fd, tr=tr, status="excluded_short",
                        error=f"timepoints={n_tp} < {min_timepoints}",
                    ))
                    continue

                # Save
                out_dir = (
                    output_root / dataset_name / "timeseries"
                    / str(n_nodes) / subject_id
                )
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{task_name}.npy"
                np.save(out_path, ts)

                log.info(
                    "[%s/%s/n%d] OK: shape=%s, FD=%.3f, %.1fs",
                    subject_id, task_name, n_nodes, ts.shape,
                    mean_fd or 0.0, ext_sec,
                )

                results.append(SubjectResult(
                    subject_id=subject_id, dataset=dataset_name,
                    task=task_name, atlas_nodes=n_nodes,
                    n_timepoints=n_tp, n_nodes=n_nodes,
                    output_path=str(out_path), mean_fd=mean_fd,
                    scan_duration_sec=n_tp * tr, tr=tr, status="ok",
                ))

        # tmpdir is auto-cleaned here (NIfTI deleted)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AOMIC streaming ROI extraction",
    )
    parser.add_argument(
        "--dataset", required=True, choices=list(DATASET_REGISTRY.keys()),
        help="AOMIC dataset name",
    )
    parser.add_argument(
        "--subjects", type=int, default=1,
        help="Number of subjects to process (0 = all)",
    )
    parser.add_argument(
        "--nodes", type=int, nargs="+", default=[100, 200],
        help="Schaefer atlas node counts",
    )
    parser.add_argument(
        "--tasks", nargs="*", default=None,
        help="Task names to extract (default: all available)",
    )
    parser.add_argument(
        "--tr", type=float, default=0.75,
        help="Repetition time in seconds (AOMIC default: 0.75)",
    )
    parser.add_argument(
        "--confound-strategy", default="24p_acompcor",
        choices=["24p", "24p_acompcor", "36p"],
        help="Confound regression strategy",
    )
    parser.add_argument(
        "--fd-threshold", type=float, default=0.5,
        help="Mean FD exclusion threshold (mm)",
    )
    parser.add_argument(
        "--min-timepoints", type=int, default=100,
        help="Minimum timepoints to include a scan",
    )
    parser.add_argument(
        "--output-root", type=str, default="data/aomic",
        help="Output root directory",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be downloaded without executing",
    )
    args = parser.parse_args()

    ds_id = DATASET_REGISTRY[args.dataset]
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # --- Download participants.tsv ---
    participants_path = output_root / args.dataset / "participants.tsv"
    if not participants_path.exists():
        log.info("Downloading participants.tsv for %s...", args.dataset)
        participants_path.parent.mkdir(parents=True, exist_ok=True)
        ok = s3_cp(
            f"{S3_BASE}/{ds_id}/participants.tsv",
            str(participants_path),
        )
        if not ok:
            log.error("Failed to download participants.tsv")
            sys.exit(1)

    # --- Get subject list ---
    participants = pd.read_csv(participants_path, sep="\t")
    all_subjects = sorted(participants.iloc[:, 0].astype(str).tolist())
    log.info("Total subjects in %s: %d", args.dataset, len(all_subjects))

    if args.subjects > 0:
        selected = all_subjects[:args.subjects]
    else:
        selected = all_subjects
    log.info("Processing %d subjects", len(selected))

    # --- Dry run ---
    if args.dry_run:
        print("\n[DRY RUN] Would process:")
        print(f"  Dataset: {args.dataset} ({ds_id})")
        print(f"  Subjects: {len(selected)} (first: {selected[0]})")
        print(f"  Atlas nodes: {args.nodes}")
        print(f"  Tasks: {args.tasks or 'all'}")
        print(f"  Confound strategy: {args.confound_strategy}")
        print(f"  FD threshold: {args.fd_threshold}")
        print(f"  Output: {output_root / args.dataset}/timeseries/{{nodes}}/{{sub}}/{{task}}.npy")
        print(f"\n  S3 source: {S3_BASE}/{ds_id}/derivatives/fmriprep/")
        print(f"  Per subject downloads:")
        print(f"    *space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz (~300-500MB)")
        print(f"    *desc-confounds_regressors.tsv (~200KB)")
        print(f"  Temp disk: ~1-2GB (auto-cleaned per subject)")
        print(f"  Final output: ~{len(selected) * len(args.nodes) * 50 / 1024:.1f}MB "
              f"({len(selected)} subs × {len(args.nodes)} atlas × ~50KB/file)")
        sys.exit(0)

    # --- Process ---
    manifest = RunManifest(
        dataset=args.dataset,
        ds_id=ds_id,
        start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        total_subjects=len(selected),
    )

    all_results = []
    for i, sub_id in enumerate(selected):
        log.info("=== [%d/%d] %s ===", i + 1, len(selected), sub_id)
        try:
            results = process_one_subject(
                dataset_name=args.dataset,
                ds_id=ds_id,
                subject_id=sub_id,
                output_root=output_root,
                nodes_list=args.nodes,
                tasks=args.tasks,
                tr=args.tr,
                confound_strategy=args.confound_strategy,
                mean_fd_threshold=args.fd_threshold,
                min_timepoints=args.min_timepoints,
            )
            all_results.extend(results)
            ok_count = sum(1 for r in results if r.status == "ok")
            fail_count = sum(1 for r in results if "failed" in r.status)
            skip_count = sum(1 for r in results if "excluded" in r.status)
            manifest.processed += (1 if ok_count > 0 else 0)
            manifest.failed += (1 if fail_count > 0 and ok_count == 0 else 0)
            manifest.skipped += (1 if skip_count > 0 and ok_count == 0 else 0)
        except Exception as e:
            log.error("[%s] Unexpected error: %s", sub_id, e)
            manifest.failed += 1
            all_results.append(SubjectResult(
                subject_id=sub_id, dataset=args.dataset,
                task="all", atlas_nodes=0, n_timepoints=0, n_nodes=0,
                output_path="", status="unexpected_error", error=str(e),
            ))

    manifest.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest.results = [asdict(r) for r in all_results]

    # --- Save manifest ---
    manifest_dir = output_root / args.dataset / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"extraction_manifest_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(manifest_path, "w") as f:
        json.dump(asdict(manifest), f, indent=2, default=str)
    log.info("Manifest saved: %s", manifest_path)

    # --- Summary ---
    ok_results = [r for r in all_results if r.status == "ok"]
    print("\n" + "=" * 60)
    print(f"  AOMIC Extraction Complete: {args.dataset}")
    print(f"  Subjects: {manifest.processed} ok / "
          f"{manifest.failed} failed / {manifest.skipped} skipped")
    print(f"  Total timeseries saved: {len(ok_results)}")
    for n in args.nodes:
        node_results = [r for r in ok_results if r.atlas_nodes == n]
        if node_results:
            tasks_found = set(r.task for r in node_results)
            print(f"    Schaefer {n}: {len(node_results)} files, "
                  f"tasks={sorted(tasks_found)}")
    print(f"  Manifest: {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
