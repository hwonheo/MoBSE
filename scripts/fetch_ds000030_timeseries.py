#!/usr/bin/env python3
"""ds000030 (UCLA CNP) streaming download + Schaefer-100 timeseries extraction.

subject 단위로 다운로드 → parcellation 추출 → BOLD 삭제를 반복하여
디스크 사용량을 최소화한다.

TODO (다음 실행 전 개선):
  1. DeprecationWarning 수정: nilearn 0.14.0+ confounds standardization 변경.
     masker.fit_transform() 호출 시 반복 출력됨. warnings.filterwarnings로
     억제하거나 nilearn 업그레이드 후 standardize 파라미터 재확인.
  2. 속도 개선: masker.fit()을 1회만 호출하고 masker.transform(bold, confounds)
     반복으로 변경. 현재 fit_transform()이 매 scan마다 atlas re-fitting.
  3. 로그 가독성: 반복 DeprecationWarning 억제 (1,969 scan × 동일 경고).

Usage:
    # 1) Pilot: 5명만 테스트
    python scripts/fetch_ds000030_timeseries.py --max-subjects 5

    # 2) 전체 실행
    python scripts/fetch_ds000030_timeseries.py

    # 3) 특정 task만
    python scripts/fetch_ds000030_timeseries.py --tasks rest scap stopsignal

    # 4) 다운로드만 (BOLD 유지)
    python scripts/fetch_ds000030_timeseries.py --download-only --keep-bold

Output:
    data/ds000030/timeseries/100/{task}/sub-XXXXX.npy   (T x 100)
    data/ds000030/timeseries/100/metadata.json

Requirements:
    pip install nilearn tqdm pandas --break-system-packages
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not found. Install: pip install tqdm --break-system-packages")
    sys.exit(1)

ALL_TASKS = [
    "rest", "bart", "bht", "pamenc", "pamret",
    "scap", "stopsignal", "taskswitch",
]

# ──────────────────────────────────────────────
# 1. URL Index & Filtering
# ──────────────────────────────────────────────

def get_download_plan(
    tasks: list[str],
    max_subjects: Optional[int] = None,
) -> list[dict[str, str]]:
    """Return flat list of {sub, task, bold_url, confounds_url}, sorted by subject.

    Subject-sorted order ensures all tasks for one subject are processed
    together, so BOLD files can be deleted promptly.
    """
    from nilearn.datasets import fetch_ds000030_urls

    print("[1/3] Fetching URL index...")
    _, urls = fetch_ds000030_urls()
    print(f"  Total URLs: {len(urls):,}")

    bold_pattern = re.compile(
        r"(sub-\d+).*task-(\w+)_bold_space-MNI152NLin2009cAsym_preproc\.nii\.gz$"
    )
    conf_pattern = re.compile(
        r"(sub-\d+).*task-(\w+)_bold_confounds\.tsv$"
    )

    bold_map: dict[str, dict[str, str]] = defaultdict(dict)  # {task: {sub: url}}
    conf_map: dict[str, dict[str, str]] = defaultdict(dict)

    for u in urls:
        if "derivatives/fmriprep" not in u:
            continue
        m = bold_pattern.search(u)
        if m and m.group(2) in tasks:
            bold_map[m.group(2)][m.group(1)] = u
            continue
        m = conf_pattern.search(u)
        if m and m.group(2) in tasks:
            conf_map[m.group(2)][m.group(1)] = u

    # subject × task 조합 생성
    # 먼저 task별 subject 제한 적용
    task_subs: dict[str, list[str]] = {}
    for task in tasks:
        subs = sorted(set(bold_map[task].keys()) & set(conf_map[task].keys()))
        if max_subjects:
            subs = subs[:max_subjects]
        task_subs[task] = subs
        print(f"  task-{task}: {len(subs)} subjects")

    # flat list, subject 순서로 정렬 (같은 subject의 task를 연속 처리)
    all_subs = sorted(set(s for subs in task_subs.values() for s in subs))
    plan = []
    for sub in all_subs:
        for task in tasks:
            if sub in task_subs.get(task, []):
                plan.append({
                    "sub": sub,
                    "task": task,
                    "bold_url": bold_map[task][sub],
                    "confounds_url": conf_map[task][sub],
                })

    print(f"  Total jobs: {len(plan)}")
    return plan


# ──────────────────────────────────────────────
# 2. Download with tqdm
# ──────────────────────────────────────────────

class _TqdmDownloadHook:
    """urllib download hook for tqdm progress bar."""
    def __init__(self, pbar: tqdm):
        self.pbar = pbar

    def __call__(self, block_num: int, block_size: int, total_size: int):
        if total_size > 0 and self.pbar.total is None:
            self.pbar.total = total_size
        downloaded = block_num * block_size
        self.pbar.update(downloaded - self.pbar.n)


def download_file(url: str, dest: Path, retries: int = 3, show_progress: bool = True) -> bool:
    """Download single file with retry and progress bar."""
    if dest.exists() and dest.stat().st_size > 0:
        return True  # skip existing

    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            if show_progress and dest.name.endswith(".nii.gz"):
                with tqdm(
                    desc=f"    {dest.name[:50]}",
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    miniters=1,
                    leave=False,
                ) as pbar:
                    urllib.request.urlretrieve(url, str(dest), _TqdmDownloadHook(pbar))
            else:
                urllib.request.urlretrieve(url, str(dest))
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  ✗ Download failed: {dest.name} — {e}")
                return False
    return False


# ──────────────────────────────────────────────
# 3. Schaefer-100 Masker (lazy init)
# ──────────────────────────────────────────────

_masker_cache: dict[int, object] = {}


def get_masker(n_parcels: int = 100):
    """Get or create Schaefer masker (singleton)."""
    if n_parcels in _masker_cache:
        return _masker_cache[n_parcels]

    from nilearn.datasets import fetch_atlas_schaefer_2018
    from nilearn.maskers import NiftiLabelsMasker

    atlas = fetch_atlas_schaefer_2018(
        n_rois=n_parcels,
        yeo_networks=7,
        resolution_mm=2,
    )
    masker = NiftiLabelsMasker(
        labels_img=atlas["maps"],
        standardize="zscore_sample",
        detrend=True,
        low_pass=0.1,
        high_pass=0.01,
        t_r=2.0,  # ds000030 TR=2s
        memory="nilearn_cache",
    )
    _masker_cache[n_parcels] = masker
    return masker


# Confounds columns to regress (fMRIPrep legacy + modern names)
CONFOUND_COLS_PRIMARY = [
    "csf", "white_matter",
    "trans_x", "trans_y", "trans_z",
    "rot_x", "rot_y", "rot_z",
]
CONFOUND_COLS_LEGACY = [
    "CSF", "WhiteMatter",
    "X", "Y", "Z",
    "RotX", "RotY", "RotZ",
]


def load_confounds(conf_path: Path) -> np.ndarray:
    """Load confound regressors from fMRIPrep TSV."""
    import pandas as pd
    df = pd.read_csv(conf_path, sep="\t")

    # primary names first, fallback to legacy
    cols = [c for c in CONFOUND_COLS_PRIMARY if c in df.columns]
    if len(cols) < 6:
        cols_legacy = [c for c in CONFOUND_COLS_LEGACY if c in df.columns]
        if len(cols_legacy) > len(cols):
            cols = cols_legacy
    if not cols:
        # last resort: any motion-like columns
        cols = [c for c in df.columns if "trans" in c.lower() or "rot" in c.lower()][:6]

    return df[cols].fillna(0).values


def extract_single(
    bold_path: Path,
    conf_path: Path,
    out_path: Path,
    n_parcels: int = 100,
) -> bool:
    """Extract timeseries for a single BOLD file. Returns True on success."""
    if out_path.exists():
        return True

    try:
        masker = get_masker(n_parcels)
        confounds = load_confounds(conf_path)

        ts = masker.fit_transform(
            str(bold_path),
            confounds=confounds,
        )  # (T, n_parcels)

        if ts.shape[1] != n_parcels:
            print(f"  ⚠ got {ts.shape[1]} parcels, expected {n_parcels}")
            return False

        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(out_path, ts.astype(np.float32))
        return True

    except Exception as e:
        print(f"  ✗ Extraction failed: {e}")
        return False


# ──────────────────────────────────────────────
# 4. Streaming Pipeline
# ──────────────────────────────────────────────

def run_streaming(
    plan: list[dict[str, str]],
    raw_dir: Path,
    output_dir: Path,
    n_parcels: int = 100,
    keep_bold: bool = False,
    download_only: bool = False,
) -> dict[str, int]:
    """Download → extract → cleanup per subject-task pair.

    Returns {task: n_extracted}.
    """
    stats: Counter = Counter()
    errors: Counter = Counter()

    disk_saved = 0  # bytes freed by BOLD deletion

    print(f"\n[2/3] Streaming pipeline ({'download only' if download_only else 'download → extract → cleanup'})...")
    print(f"  keep_bold={keep_bold}")
    print()

    pbar = tqdm(plan, desc="Processing", unit="scan")

    for job in pbar:
        sub = job["sub"]
        task = job["task"]
        pbar.set_postfix_str(f"{sub} task-{task}")

        bold_path = raw_dir / task / f"{sub}_task-{task}_bold_MNI_preproc.nii.gz"
        conf_path = raw_dir / task / f"{sub}_task-{task}_confounds.tsv"
        ts_path = output_dir / task / f"{sub}.npy"

        # Skip if timeseries already exists
        if ts_path.exists() and not download_only:
            stats[task] += 1
            continue

        # Download
        ok_bold = download_file(job["bold_url"], bold_path, show_progress=True)
        ok_conf = download_file(job["confounds_url"], conf_path, show_progress=False)

        if not (ok_bold and ok_conf):
            errors[task] += 1
            continue

        if download_only:
            stats[task] += 1
            continue

        # Extract
        ok = extract_single(bold_path, conf_path, ts_path, n_parcels=n_parcels)
        if ok:
            stats[task] += 1
        else:
            errors[task] += 1

        # Cleanup: delete BOLD (keep confounds — tiny)
        if not keep_bold and bold_path.exists():
            fsize = bold_path.stat().st_size
            bold_path.unlink()
            disk_saved += fsize

    pbar.close()

    print(f"\n  Results:")
    for task in ALL_TASKS:
        if task in stats or task in errors:
            print(f"    task-{task}: {stats[task]} ok, {errors[task]} errors")
    if disk_saved > 0:
        print(f"  Disk saved by BOLD cleanup: {disk_saved / (1024**3):.1f} GB")

    return dict(stats)


# ──────────────────────────────────────────────
# 5. Metadata
# ──────────────────────────────────────────────

def save_metadata(
    output_dir: Path,
    tasks: list[str],
    stats: dict[str, int],
) -> None:
    meta = {
        "dataset": "ds000030",
        "dataset_name": "UCLA Consortium for Neuropsychiatric Phenomics LA5c",
        "parcellation": "Schaefer2018_100Parcels_7Networks",
        "n_parcels": 100,
        "tr_sec": 2.0,
        "preprocessing": "fMRIPrep (from OpenNeuro derivatives)",
        "postprocessing": {
            "standardize": "zscore_sample",
            "detrend": True,
            "bandpass": [0.01, 0.1],
            "confound_regression": "csf, white_matter, 6 motion params",
        },
        "tasks": {task: {"n_subjects": stats.get(task, 0)} for task in tasks},
        "reference": "Poldrack et al. 2016, Sci Data, doi:10.1038/sdata.2016.110",
    }

    meta_path = output_dir / "metadata.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"\n[3/3] Metadata saved: {meta_path}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ds000030 → Schaefer-100 timeseries (streaming pipeline)"
    )
    parser.add_argument(
        "--tasks", nargs="+", default=ALL_TASKS,
        help=f"Tasks to process (default: all). Options: {ALL_TASKS}",
    )
    parser.add_argument(
        "--max-subjects", type=int, default=None,
        help="Limit subjects per task (for pilot runs)",
    )
    parser.add_argument(
        "--data-dir", type=str, default="data/ds000030",
        help="Base directory for downloads and outputs",
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Download only, skip parcellation",
    )
    parser.add_argument(
        "--keep-bold", action="store_true",
        help="Keep BOLD nii.gz after extraction (default: delete to save disk)",
    )
    parser.add_argument(
        "--n-parcels", type=int, default=100,
        help="Number of Schaefer parcels (default: 100)",
    )
    args = parser.parse_args()

    base_dir = Path(args.data_dir)
    raw_dir = base_dir / "raw_fmriprep"
    output_dir = base_dir / "timeseries" / str(args.n_parcels)

    invalid_tasks = [t for t in args.tasks if t not in ALL_TASKS]
    if invalid_tasks:
        print(f"Unknown tasks: {invalid_tasks}. Valid: {ALL_TASKS}")
        sys.exit(1)

    print(f"Tasks: {args.tasks}")
    print(f"Max subjects: {args.max_subjects or 'all'}")
    print(f"Output dir: {output_dir}")
    print(f"Keep BOLD: {args.keep_bold}")
    print()

    # Plan
    plan = get_download_plan(args.tasks, args.max_subjects)

    if not plan:
        print("No jobs to process.")
        return

    # Stream
    stats = run_streaming(
        plan, raw_dir, output_dir,
        n_parcels=args.n_parcels,
        keep_bold=args.keep_bold or args.download_only,
        download_only=args.download_only,
    )

    # Metadata
    if not args.download_only:
        save_metadata(output_dir, args.tasks, stats)

    print("\nDone.")
    total = sum(stats.values())
    print(f"Total: {total} timeseries")


if __name__ == "__main__":
    main()
