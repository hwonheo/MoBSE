#!/usr/bin/env python3
"""WI-02 run manifest → `windows.jsonl` (label 부착).

재추출과 분리한 이유가 있다. 창 레코드 스키마나 label 규칙이 바뀌어도 209 GiB 를
다시 읽을 필요가 없어야 한다. 드라이버는 창 배열과 해시를 만들고, 이 단계는 그
기록을 스키마 레코드로 옮긴다.

restingstate manifest 는 **입력으로 받지 않는다** — bank source 이고 분류 대상이
아니다 (계획서 §1). 실수로 넘기면 `labels.label_of()` 가 거부한다.

사용:
    python scripts/h197/12_build_windows_manifest.py \
        --manifest .../wi02_ds002785_emomatching.jsonl \
                   .../wi02_ds002785_workingmemory.jsonl \
        --output .../windows.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2.cohort import read_extract_manifest  # noqa: E402
from mobse.v2.labels import LabelError, build_window_records  # noqa: E402
from mobse.v2.manifests import write_jsonl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, nargs="+", required=True,
                    help="WI-02 run manifest (target task 만)")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true",
                    help="기존 파일을 덮어쓴다. 기본은 거부 (지침서 §2)")
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    per_manifest: List[Dict[str, Any]] = []

    for path in args.manifest:
        header, runs = read_extract_manifest(path)
        try:
            built = build_window_records(header, runs)
        except LabelError as exc:
            print(f"[error] {path}: {exc}", file=sys.stderr)
            return 1
        ok = sum(1 for r in runs if r.get("status") == "ok")
        per_manifest.append({
            "manifest": str(path),
            "task": header.get("task"),
            "dataset": header.get("dataset"),
            "runs_total": len(runs),
            "runs_ok": ok,
            "window_records": len(built),
        })
        records.extend(built)
        print(f"[ok] {path.name}: run {ok}/{len(runs)} → 창 {len(built)}")

    keys = [r["window_key"] for r in records]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        print(f"[FAIL] window_key 중복 {len(duplicates)}건: {duplicates[:5]}",
              file=sys.stderr)
        return 1

    result = write_jsonl(args.output, "windows", records, overwrite=args.overwrite)
    summary = {"per_manifest": per_manifest, "total_window_records": len(records),
               "output": result}
    (args.output.with_suffix(".summary.json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] 창 레코드 {len(records):,} → {args.output}")
    print(f"       sha256 {result.get('sha256', '')[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
