#!/usr/bin/env python3
"""Wave 2 사전 용량 실측 — awscli 불필요 (U26 해소). 다운로드는 하지 않는다.

`01b_wave1_fetch_metadata.py` 가 남긴 `s3_listing_cache.json` 을 재사용하면
S3 재조회 없이 즉시 계산된다. 캐시가 없으면 직접 나열한다.

사용:
  python3 03b_wave2_size_probe.py --listing-cache <dest>/s3_listing_cache.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("w1", HERE / "01b_wave1_fetch_metadata.py")
w1 = importlib.util.module_from_spec(spec)
sys.modules["w1"] = w1
spec.loader.exec_module(w1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listing-cache", type=Path, default=None)
    ap.add_argument("--datasets", nargs="*", default=w1.DATASETS)
    ap.add_argument("--out", type=Path, default=Path("wave2_size_probe.json"))
    args = ap.parse_args(argv)

    cache: Dict[str, List[List]] = {}
    if args.listing_cache and args.listing_cache.is_file():
        cache = json.loads(args.listing_cache.read_text(encoding="utf-8"))
        print(f"[cache] {args.listing_cache}")

    report: Dict[str, Dict] = {}
    grand = 0
    for ds in args.datasets:
        print(f"\n=== {ds} ===")
        if ds in cache:
            objs = [w1.Obj(k, s) for k, s in cache[ds]]
        else:
            print("  listing s3 …", flush=True)
            objs = w1.list_prefix(f"{ds}/")
        per: Dict[str, Dict[str, int]] = {}
        total = 0
        for t in w1.TASKS:
            hits = [o for o in objs
                    if f"task-{t}" in o.key and w1.SPACE in o.key
                    and o.key.endswith("desc-preproc_bold.nii.gz")
                    and "/derivatives/fmriprep/" in o.key]
            b = sum(o.size for o in hits)
            per[t] = {"files": len(hits), "bytes": b}
            total += b
            print(f"  {t:16s} files={len(hits):<5d} {w1.human(b)}")
        print(f"  {'TOTAL':16s} {w1.human(total)}")
        report[ds] = {"per_task": per, "total_bytes": total}
        grand += total

    print(f"\nGRAND TOTAL: {w1.human(grand)}")
    args.out.write_text(json.dumps(
        {"datasets": report, "grand_total_bytes": grand,
         "space": w1.SPACE, "tasks": w1.TASKS}, indent=2) + "\n", encoding="utf-8")
    print(f"report: {args.out}")
    print("\n가용 디스크에 여유 있게 들어가지 않으면 streaming 추출을 설계에 포함한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
