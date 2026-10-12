#!/usr/bin/env python3
"""Wave 2 — AOMIC PIOP1/PIOP2 의 fMRIPrep preproc BOLD 확보.

Wave 1 감사에서 native TR 과 window 설계가 확정된 뒤에만 실행한다.
`01b_wave1_fetch_metadata.py` 의 S3 목록 캐시를 재사용하므로 재나열하지 않는다.

Wave 1 과 다른 점은 파일 크기다(개당 100–500 MB). 따라서 전체를 메모리에 올리지 않고
청크 단위로 `.part` 에 스트리밍한 뒤 rename 한다. 중단되어도 최종 경로에 절반짜리
파일이 남지 않으며, 재실행하면 크기가 맞는 파일만 건너뛰고 이어받는다.

받는 것 (task 는 --tasks 로 조정):
  <ds>/derivatives/fmriprep/sub-*/func/*task-<t>*space-MNI152NLin2009cAsym*desc-preproc_bold.nii.gz
  <ds>/derivatives/fmriprep/sub-*/func/*task-<t>*space-MNI152NLin2009cAsym*desc-brain_mask.nii.gz

사용:
  python3 06_wave2_fetch_bold.py --dest /data/aomic_wave2 \
      --listing-cache /data/aomic_wave1/s3_listing_cache.json --dry-run
  nohup python3 -u 06_wave2_fetch_bold.py --dest /data/aomic_wave2 \
      --listing-cache /data/aomic_wave1/s3_listing_cache.json --jobs 6 > fetch2.log 2>&1 &
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("w1", HERE / "01b_wave1_fetch_metadata.py")
w1 = importlib.util.module_from_spec(_spec)
sys.modules["w1"] = w1
_spec.loader.exec_module(w1)

BUCKET_URL = w1.BUCKET_URL
SPACE = w1.SPACE
CHUNK = 1 << 20          # 1 MiB
TIMEOUT = 300
RETRIES = 4
SUFFIXES = ("desc-preproc_bold.nii.gz", "desc-brain_mask.nii.gz")


def stream_to(url: str, dst: Path, expected: int) -> int:
    """청크 스트리밍 다운로드. `.part` → rename. 크기 불일치는 실패로 처리."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    last: Optional[Exception] = None
    for attempt in range(RETRIES):
        try:
            got = 0
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp, tmp.open("wb") as fh:
                while True:
                    buf = resp.read(CHUNK)
                    if not buf:
                        break
                    fh.write(buf)
                    got += len(buf)
            if expected and got != expected:
                raise IOError(f"size mismatch: got {got}, expected {expected}")
            os.replace(tmp, dst)
            return got
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            tmp.unlink(missing_ok=True)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"다운로드 실패 ({RETRIES}회): {url}\n  마지막 오류: {last}")


def select_bold(objects, ds: str, tasks: List[str]):
    out = []
    for o in objects:
        k = o.key
        if "/derivatives/fmriprep/" not in k or SPACE not in k:
            continue
        if not k.endswith(SUFFIXES):
            continue
        if not any(f"task-{t}" in k for t in tasks):
            continue
        out.append(o)
    return sorted(out, key=lambda o: o.key)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--listing-cache", type=Path, required=True)
    ap.add_argument("--datasets", nargs="*", default=w1.DATASETS)
    ap.add_argument("--tasks", nargs="*", default=w1.TASKS)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not args.listing_cache.is_file():
        print(f"목록 캐시 없음: {args.listing_cache}", file=sys.stderr)
        return 2
    cache = json.loads(args.listing_cache.read_text(encoding="utf-8"))
    args.dest.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Dict] = {}
    grand_files = grand_bytes = 0

    for ds in args.datasets:
        if ds not in cache:
            print(f"[warn] {ds} 캐시에 없음 — 건너뜀", file=sys.stderr)
            continue
        objs = [w1.Obj(k, s) for k, s in cache[ds]]
        sel = select_bold(objs, ds, args.tasks)
        total = sum(o.size for o in sel)
        print(f"\n=== {ds} ===")
        print(f"  selected: {len(sel)} files, {w1.human(total)}")
        report[ds] = {"selected": len(sel), "bytes": total}
        grand_files += len(sel); grand_bytes += total

        if args.dry_run:
            for o in sel[:3]:
                print(f"    e.g. {o.key}  ({w1.human(o.size)})")
            continue

        # 이전 실행이 중단되며 남은 .part 를 먼저 치운다. 최종 경로가 아니므로
        # 재개 판정에는 영향이 없지만 쌓이면 디스크를 잠식한다.
        stale = list((args.dest / ds).rglob("*.part"))
        for sp in stale:
            sp.unlink(missing_ok=True)
        if stale:
            print(f"  removed {len(stale)} stale .part file(s)")

        todo: List[Tuple] = []
        skipped = skipped_bytes = 0
        for o in sel:
            dst = w1.local_path(args.dest, ds, o.key)
            if dst.is_file() and dst.stat().st_size == o.size:
                skipped += 1; skipped_bytes += o.size
            else:
                todo.append((o, dst))
        print(f"  downloading {len(todo)} files ({w1.human(total - skipped_bytes)}), "
              f"skipping {skipped} already complete", flush=True)

        done = done_bytes = 0
        failed: List[Tuple[str, str]] = []
        lock = threading.Lock()
        t0 = time.time()

        def work(item) -> None:
            nonlocal done, done_bytes
            o, dst = item
            url = f"{BUCKET_URL}/{urllib.parse.quote(o.key)}"
            try:
                n = stream_to(url, dst, o.size)
            except Exception as exc:
                with lock:
                    failed.append((o.key, f"{type(exc).__name__}: {exc}"))
                return
            with lock:
                done += 1; done_bytes += n
                if done % 20 == 0:
                    el = time.time() - t0
                    rate = done_bytes / el if el > 0 else 0
                    left = (total - skipped_bytes - done_bytes) / rate if rate > 0 else 0
                    print(f"    … {done}/{len(todo)}  {w1.human(done_bytes)}  "
                          f"{rate/1048576:.1f} MiB/s  ETA {left/60:.0f} min", flush=True)

        if todo:
            with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
                list(ex.map(work, todo))
        print(f"  downloaded {done} ({w1.human(done_bytes)}), skipped {skipped}, "
              f"failed {len(failed)}")
        if failed:
            for k, e in failed[:10]:
                print(f"    FAIL {k}  {e}")
            report[ds]["failed"] = failed

    print(f"\nTOTAL selected: {grand_files} files, {w1.human(grand_bytes)}")
    out = args.dest / "wave2_fetch_report.json"
    out.write_text(json.dumps(
        {"bucket": BUCKET_URL, "space": SPACE, "suffixes": list(SUFFIXES),
         "tasks": args.tasks, "dry_run": args.dry_run, "datasets": report,
         "total_files": grand_files, "total_bytes": grand_bytes},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
