#!/usr/bin/env python3
"""ds000030 (UCLA CNP) derivatives 구조 탐색 스크립트.

nilearn으로 URL index를 받아 fMRIPrep derivatives 내
task BOLD 파일 존재 여부, task 종류, 피험자 수를 확인한다.

Usage:
    python scripts/probe_ds000030.py
    python scripts/probe_ds000030.py --save  # 결과를 JSON으로 저장
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from nilearn.datasets import fetch_ds000030_urls


def main(save: bool = False) -> None:
    print("[1/4] Fetching URL index from nilearn...")
    urls_path, urls = fetch_ds000030_urls()
    print(f"  Total URLs: {len(urls)}")

    # ── derivatives 필터 ──
    deriv_urls = [u for u in urls if "derivatives" in u]
    fmriprep_urls = [u for u in deriv_urls if "fmriprep" in u]
    print(f"\n[2/4] Derivatives URLs: {len(deriv_urls)}")
    print(f"  fMRIPrep URLs: {len(fmriprep_urls)}")

    # ── task BOLD 파일 ──
    task_bold = [u for u in fmriprep_urls if "task-" in u and "bold" in u.lower()]
    print(f"\n[3/4] Task BOLD files in fMRIPrep derivatives: {len(task_bold)}")

    if not task_bold:
        # fallback: raw 데이터에서 task 구조 확인
        print("\n  ⚠ fMRIPrep derivatives에 task BOLD 없음. Raw 데이터 task 확인:")
        raw_bold = [u for u in urls if "task-" in u and "bold" in u.lower()
                    and "derivatives" not in u]
        task_pattern = re.compile(r"task-(\w+)")
        raw_tasks = Counter()
        raw_subs = defaultdict(set)
        for u in raw_bold:
            m = task_pattern.search(u)
            sub_m = re.search(r"(sub-\d+)", u)
            if m:
                task_name = m.group(1)
                raw_tasks[task_name] += 1
                if sub_m:
                    raw_subs[task_name].add(sub_m.group(1))
        print(f"  Raw task BOLD files: {len(raw_bold)}")
        for task, count in sorted(raw_tasks.items()):
            print(f"    task-{task}: {count} files, {len(raw_subs[task])} subjects")
        print("\n  → fMRIPrep를 직접 돌려야 할 수 있음.")
        print("  → 또는 OpenNeuroDerivatives에서 별도 다운로드 확인 필요.")

    else:
        # task 종류별 집계
        task_pattern = re.compile(r"task-(\w+)")
        tasks = Counter()
        subjects_per_task: dict[str, set[str]] = defaultdict(set)
        spaces: set[str] = set()
        space_pattern = re.compile(r"space-(\w+)")

        for u in task_bold:
            m = task_pattern.search(u)
            sub_m = re.search(r"(sub-\d+)", u)
            sp_m = space_pattern.search(u)
            if m:
                task_name = m.group(1)
                tasks[task_name] += 1
                if sub_m:
                    subjects_per_task[task_name].add(sub_m.group(1))
            if sp_m:
                spaces.add(sp_m.group(1))

        print("\n  Task breakdown:")
        for task, count in sorted(tasks.items()):
            n_sub = len(subjects_per_task[task])
            print(f"    task-{task}: {count} files, {n_sub} subjects")
        print(f"\n  Output spaces: {sorted(spaces) if spaces else 'unknown'}")

    # ── Confounds / timeseries 확인 ──
    confounds = [u for u in fmriprep_urls if "confounds" in u.lower()]
    print(f"\n[4/4] Confounds files: {len(confounds)}")

    # ── 샘플 URL 출력 ──
    print("\n── Sample fMRIPrep URLs (first 10) ──")
    for u in fmriprep_urls[:10]:
        print(f"  {u}")

    if task_bold:
        print("\n── Sample task BOLD URLs (first 5) ──")
        for u in task_bold[:5]:
            print(f"  {u}")

    # ── 저장 ──
    if save:
        out_path = Path("artifacts/ds000030_probe_result.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = {
            "total_urls": len(urls),
            "derivatives_urls": len(deriv_urls),
            "fmriprep_urls": len(fmriprep_urls),
            "task_bold_in_fmriprep": len(task_bold),
            "confounds_files": len(confounds),
            "sample_fmriprep": fmriprep_urls[:20],
            "sample_task_bold": task_bold[:20],
        }
        out_path.write_text(json.dumps(result, indent=2))
        print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    save_flag = "--save" in sys.argv
    main(save=save_flag)
