#!/usr/bin/env python3
"""WI-03 — WI-02 manifest 들을 subject 단위 코호트로 접는다.

계산은 `mobse/v2/cohort.py` 가 한다. 이 스크립트는 파일을 읽고 쓰고 요약을 찍는다.

한 cohort(dataset)의 **세 task manifest 를 모두** 받아야 한다. 계획서 §3.3 의
적격 기준이 "두 target task 와 rest 가 모두 유효"이므로, rest manifest 를 빼고
돌리면 전원이 `restingstate_missing` 으로 부적격이 된다. 그래서 세 개가 다
들어왔는지 먼저 확인하고, 아니면 **실패시킨다** — 조용히 전원 부적격을 내지 않는다.

사용:
    python scripts/h197/15_build_subjects.py \
        --manifest .../wi02_ds002785_{emomatching,workingmemory,restingstate}.jsonl \
        --output-dir .../cohort_piop1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2.cohort import (  # noqa: E402
    REQUIRED_TASKS,
    CohortError,
    build_subjects,
    exclusion_records,
    read_extract_manifest,
    subjects_to_records,
    summarize,
)
from mobse.v2.manifests import ManifestError, write_jsonl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, nargs="+", required=True,
                    help=f"한 dataset 의 {len(REQUIRED_TASKS)}개 task manifest 전부")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    manifests: List[Any] = []
    tasks_seen: List[str] = []
    datasets: List[str] = []
    for path in args.manifest:
        try:
            header, runs = read_extract_manifest(path)
        except CohortError as exc:
            print(f"[error] {path}: {exc}", file=sys.stderr)
            return 1
        task = str(header.get("task") or "")
        tasks_seen.append(task)
        datasets.append(str(header.get("dataset") or ""))
        manifests.append((header, runs))
        ok = sum(1 for r in runs if r.get("status") == "ok")
        print(f"[read] {path.name}: run {len(runs)}, ok {ok}, task {task}")

    missing = [t for t in REQUIRED_TASKS if t not in tasks_seen]
    if missing:
        print(f"[error] task manifest 누락: {missing}. 계획서 §3.3 의 적격 기준은 "
              "세 task 를 모두 요구하므로, 빠진 채로 돌리면 전원이 부적격이 된다",
              file=sys.stderr)
        return 1
    if len(set(datasets)) != 1:
        print(f"[error] dataset 이 섞였다: {sorted(set(datasets))}. "
              "cohort 는 dataset 단위로 만든다", file=sys.stderr)
        return 1

    try:
        subjects = build_subjects(manifests)
    except CohortError as exc:
        print(f"[error] 코호트 구성 실패: {exc}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = subjects_to_records(subjects)
    exclusions = exclusion_records(subjects)
    report: Dict[str, Any] = summarize(subjects)

    try:
        written = write_jsonl(args.output_dir / "subjects.jsonl", "subjects",
                              records, overwrite=args.overwrite)
        report["subjects_artifact"] = written
        if exclusions:
            report["exclusions_artifact"] = write_jsonl(
                args.output_dir / "exclusions.jsonl", "exclusions", exclusions,
                overwrite=args.overwrite)
    except ManifestError as exc:
        print(f"[error] 기록 실패: {exc}", file=sys.stderr)
        return 1

    report["dataset"] = datasets[0]
    report["source_manifests"] = [str(p) for p in args.manifest]
    (args.output_dir / "cohort_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[cohort] subject {report['n_subjects']}, 적격 {report['n_eligible']}")
    for cohort, counts in report["by_cohort"].items():
        print(f"  {cohort}: {counts['eligible']}/{counts['total']}")
    print("[사유 상위]")
    for reason, count in list(report["reason_counts"].items())[:8]:
        print(f"  {count:5d}  {reason}")
    print(f"\n[done] {args.output_dir}/subjects.jsonl "
          f"({report['n_subjects']} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
