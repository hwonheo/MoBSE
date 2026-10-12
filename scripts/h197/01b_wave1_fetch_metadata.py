#!/usr/bin/env python3
"""Wave 1 — AOMIC PIOP1/PIOP2 메타데이터 확보 (aws CLI 불필요, 표준 라이브러리만).

OpenNeuro 의 공개 S3 버킷을 REST API(ListObjectsV2)로 직접 조회한다.
`01_wave1_fetch_metadata.sh` 와 받는 파일 집합이 동일하며, awscli 가 없는
호스트를 위한 대안이다.

받는 것 (task ∈ {restingstate, emomatching, workingmemory}):
  <ds>/dataset_description.json, participants.tsv(.json), README, CHANGES
  <ds>/task-<task>_bold.json                      ← BIDS inheritance 대비
  <ds>/sub-*/func/*task-<task>*_bold.json
  <ds>/sub-*/func/*task-<task>*_events.tsv|.json
  <ds>/derivatives/fmriprep/sub-*/func/*task-<task>*desc-confounds_{regressors,timeseries}.tsv|.json
  <ds>/derivatives/fmriprep/sub-*/func/*task-<task>*space-MNI152NLin2009cAsym*desc-preproc_bold.json

BOLD 본체(.nii.gz)는 받지 않는다.

사용:
  python3 01b_wave1_fetch_metadata.py --dest /data/aomic_wave1 --dry-run
  python3 01b_wave1_fetch_metadata.py --dest /data/aomic_wave1
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fnmatch
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BUCKET_URL = "https://s3.amazonaws.com/openneuro.org"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
DATASETS = ["ds002785", "ds002790"]          # AOMIC PIOP1 / PIOP2
TASKS = ["restingstate", "emomatching", "workingmemory"]
SPACE = "space-MNI152NLin2009cAsym"
TIMEOUT = 60
RETRIES = 4


@dataclass(frozen=True)
class Obj:
    key: str
    size: int


def _get(url: str) -> bytes:
    last: Optional[Exception] = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET 실패 ({RETRIES}회): {url}\n  마지막 오류: {last}")


def list_prefix(prefix: str, progress: bool = True) -> List[Obj]:
    """ListObjectsV2 로 prefix 아래 전체 객체를 나열한다(페이지네이션 포함)."""
    out: List[Obj] = []
    token: Optional[str] = None
    page = 0
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        url = f"{BUCKET_URL}?{urllib.parse.urlencode(q)}"
        root = ET.fromstring(_get(url))
        for c in root.findall("s3:Contents", NS):
            k = c.findtext("s3:Key", default="", namespaces=NS)
            sz = int(c.findtext("s3:Size", default="0", namespaces=NS))
            if k:
                out.append(Obj(k, sz))
        page += 1
        if progress and page % 10 == 0:
            print(f"    … {prefix}: {page} pages, {len(out)} objects", flush=True)
        truncated = root.findtext("s3:IsTruncated", default="false",
                                  namespaces=NS) == "true"
        token = root.findtext("s3:NextContinuationToken", namespaces=NS)
        if not truncated or not token:
            break
    return out


def wanted_patterns(ds: str) -> List[str]:
    pats = [
        f"{ds}/dataset_description.json",
        f"{ds}/participants.tsv",
        f"{ds}/participants.json",
        f"{ds}/README*",
        f"{ds}/CHANGES*",
    ]
    for t in TASKS:
        pats += [
            f"{ds}/task-{t}_bold.json",
            f"{ds}/sub-*/func/*task-{t}*_bold.json",
            f"{ds}/sub-*/func/*task-{t}*_events.tsv",
            f"{ds}/sub-*/func/*task-{t}*_events.json",
            f"{ds}/derivatives/fmriprep/sub-*/func/*task-{t}*desc-confounds_regressors.tsv",
            f"{ds}/derivatives/fmriprep/sub-*/func/*task-{t}*desc-confounds_regressors.json",
            f"{ds}/derivatives/fmriprep/sub-*/func/*task-{t}*desc-confounds_timeseries.tsv",
            f"{ds}/derivatives/fmriprep/sub-*/func/*task-{t}*desc-confounds_timeseries.json",
            f"{ds}/derivatives/fmriprep/sub-*/func/*task-{t}*{SPACE}*desc-preproc_bold.json",
        ]
    pats.append(f"{ds}/derivatives/fmriprep/dataset_description.json")
    return pats


def select(objects: Iterable[Obj], patterns: List[str]) -> List[Obj]:
    """패턴에 걸리는 객체만. .nii.gz 는 어떤 경우에도 제외한다(안전장치)."""
    sel: Dict[str, Obj] = {}
    for o in objects:
        if o.key.endswith(".nii.gz") or o.key.endswith(".nii"):
            continue
        if any(fnmatch.fnmatch(o.key, p) for p in patterns):
            sel[o.key] = o
    return [sel[k] for k in sorted(sel)]


def fetch_to(url: str, dst: Path) -> int:
    """`.part` 로 받은 뒤 rename 한다.

    중간에 프로세스가 죽어도 최종 경로에는 절반짜리 파일이 남지 않는다.
    (SSH 끊김으로 foreground 프로세스가 죽는 사고에 대한 guard.)
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    data = _get(url)
    tmp.write_bytes(data)
    os.replace(tmp, dst)
    return len(data)


def local_path(dest: Path, ds: str, key: str) -> Path:
    """S3 key 를 셸 스크립트판과 같은 로컬 레이아웃으로 사상한다."""
    rest = key[len(ds) + 1:]
    if rest.startswith("derivatives/fmriprep/"):
        return dest / ds / "fmriprep" / rest[len("derivatives/fmriprep/"):]
    return dest / ds / "raw" / rest


def human(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} GiB"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true", help="목록·용량만, 다운로드 없음")
    ap.add_argument("--datasets", nargs="*", default=DATASETS)
    ap.add_argument("--listing-cache", type=Path, default=None,
                    help="객체 목록 캐시 JSON (재실행·Wave 2 용량 산정에 재사용)")
    ap.add_argument("--jobs", type=int, default=8,
                    help="동시 다운로드 수 (기본 8). 1 이면 순차.")
    args = ap.parse_args(argv)

    args.dest.mkdir(parents=True, exist_ok=True)
    cache: Dict[str, List[List]] = {}
    cache_path = args.listing_cache or (args.dest / "s3_listing_cache.json")
    if cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            print(f"[cache] {cache_path} 재사용 ({len(cache)} datasets)")
        except Exception:
            cache = {}

    grand_n = grand_bytes = 0
    report: Dict[str, Dict] = {}

    for ds in args.datasets:
        print(f"\n=== {ds} ===", flush=True)
        if ds in cache:
            objs = [Obj(k, s) for k, s in cache[ds]]
            print(f"  listing: {len(objs)} objects (cached)")
        else:
            print("  listing s3 …", flush=True)
            objs = list_prefix(f"{ds}/")
            cache[ds] = [[o.key, o.size] for o in objs]
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  listing: {len(objs)} objects")

        sel = select(objs, wanted_patterns(ds))
        total = sum(o.size for o in sel)
        print(f"  selected: {len(sel)} files, {human(total)}")

        by_kind: Dict[str, int] = {}
        for o in sel:
            if "desc-confounds" in o.key:
                k = "confounds"
            elif o.key.endswith("_events.tsv") or o.key.endswith("_events.json"):
                k = "events"
            elif "desc-preproc_bold.json" in o.key:
                k = "deriv_sidecar"
            elif o.key.endswith("_bold.json"):
                k = "raw_sidecar"
            else:
                k = "dataset_level"
            by_kind[k] = by_kind.get(k, 0) + 1
        for k in sorted(by_kind):
            print(f"    {k:16s} {by_kind[k]}")
        report[ds] = {"listed": len(objs), "selected": len(sel),
                      "bytes": total, "by_kind": by_kind}
        grand_n += len(sel)
        grand_bytes += total

        if args.dry_run:
            for o in sel[:5]:
                print(f"    e.g. {o.key}")
            continue

        todo = []
        skipped = 0
        for o in sel:
            dst = local_path(args.dest, ds, o.key)
            # 크기가 정확히 맞는 파일만 완료로 본다. 중단된 잔여물은 크기가
            # 다르므로 자동으로 다시 받는다.
            if dst.is_file() and dst.stat().st_size == o.size:
                skipped += 1
            else:
                todo.append((o, dst))

        done = 0
        failed: List[Tuple[str, str]] = []
        lock = threading.Lock()

        def work(item: Tuple[Obj, Path]) -> None:
            nonlocal done
            o, dst = item
            url = f"{BUCKET_URL}/{urllib.parse.quote(o.key)}"
            try:
                fetch_to(url, dst)
            except Exception as exc:
                with lock:
                    failed.append((o.key, f"{type(exc).__name__}: {exc}"))
                return
            with lock:
                done += 1
                if done % 200 == 0:
                    print(f"    … {done}/{len(todo)} new (skip {skipped})", flush=True)

        if todo:
            jobs = max(1, args.jobs)
            print(f"  downloading {len(todo)} files with {jobs} job(s), "
                  f"skipping {skipped} already complete", flush=True)
            if jobs == 1:
                for item in todo:
                    work(item)
            else:
                with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
                    list(ex.map(work, todo))
        print(f"  downloaded {done}, skipped {skipped}, failed {len(failed)}")
        if failed:
            for k, e in failed[:10]:
                print(f"    FAIL {k}  {e}")
            report.setdefault(ds, {})["failed"] = failed

    print(f"\nTOTAL selected: {grand_n} files, {human(grand_bytes)}")
    summary = args.dest / "wave1_fetch_report.json"
    summary.write_text(json.dumps(
        {"bucket": BUCKET_URL, "tasks": TASKS, "dry_run": args.dry_run,
         "datasets": report,
         "total_files": grand_n, "total_bytes": grand_bytes},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report: {summary}")
    if not args.dry_run:
        print(f"다음: python3 02_wave1_audit.py --root {args.dest} "
              f"--out {args.dest}/wave1_audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
