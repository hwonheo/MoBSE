#!/usr/bin/env python3
"""ADHD-200 범위 확인 (결정 62) — 공개 S3 (fcp-indi, 로그인 없음) 에서 CPAC CC200 시계열과 표현형 파일을 받는다.

받는 것:
* ``RawDataBIDS/*_phenotypic.csv`` · ``RawDataBIDS/<site>/participants.tsv`` · ``RawDataBIDS/<site>/*bold.json``
  (사이트별 라벨 · TR).
* ``Outputs/cpac/raw_outputs/pipeline_adhd200-benchmark__freq-filter/<sub>_session_<n>/roi_timeseries/
  _scan_rest_<k>/…global0…/_bandpass_freqs_0.01.0.1/_mask_CC200/roi_CC200.1D`` — ABIDE PCP 의
  ``filt_noglobal`` · CC200 과 같은 조합 (CPAC, 대역 0.01–0.1 Hz, 전역 신호 회귀 없음).

산출 ``<out>/pheno/…`` · ``<out>/cc200/<sub>_session_<n>_rest_<k>.1D`` · ``<out>/manifest.json`` (파일별 S3 키 ·
크기 · sha256). 이미 받은 파일은 크기가 같으면 건너뛴다. 실패는 다시 시도하지 않고 manifest 에 적는다.

Usage (h197):
    python scripts/i1_adhd200/fetch.py --out /mnt/data/mp2026/MoBSE_dataset/adhd200/raw [--jobs 8]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BUCKET = "https://fcp-indi.s3.amazonaws.com"
ROOT = "data/Projects/ADHD200/"
PIPE = ROOT + "Outputs/cpac/raw_outputs/pipeline_adhd200-benchmark__freq-filter/"
CC200 = re.compile(r"^(?P<sub>[^/]+_session_\d+)/roi_timeseries/_scan_rest_(?P<k>\d+)/[^/]*/[^/]*/[^/]*/"
                   r"_compcor_ncomponents_5_selector_pc10\.linear1\.wm0\.global0\.motion1\.quadratic1\.gm0\.compcor1\.csf0/"
                   r"_bandpass_freqs_0\.01\.0\.1/_mask_CC200/roi_CC200\.1D$")


def list_keys(prefix: str, delimiter: str | None = None):
    """S3 ListObjectsV2 를 끝까지 넘기며 (key, size) 와 공통 접두사를 돌려준다."""
    keys, prefixes, token = [], [], None
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["continuation-token"] = token
        xml = urllib.request.urlopen(f"{BUCKET}/?{urllib.parse.urlencode(q)}", timeout=120).read().decode()
        keys += [(k, int(s)) for k, s in re.findall(r"<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", xml)]
        prefixes += re.findall(r"<CommonPrefixes><Prefix>([^<]+)</Prefix>", xml)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            return keys, prefixes
        token = m.group(1)


def get(key: str, size: int, dest: Path) -> dict:
    rec = {"key": key, "size": size, "path": str(dest)}
    try:
        if not (dest.exists() and dest.stat().st_size == size):
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            with urllib.request.urlopen(f"{BUCKET}/{urllib.parse.quote(key)}", timeout=300) as r, tmp.open("wb") as fh:
                fh.write(r.read())
            tmp.replace(dest)
        rec["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
        rec["ok"] = dest.stat().st_size == size
    except Exception as e:  # noqa: BLE001 — 실패는 기록만
        rec["ok"], rec["error"] = False, repr(e)
    return rec


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args(argv[1:])
    jobs = []
    keys, _ = list_keys(ROOT + "RawDataBIDS/")
    for k, s in keys:
        name = k[len(ROOT + "RawDataBIDS/"):]
        if name.endswith("_phenotypic.csv") or re.match(r"^[^/]+/(participants\.tsv|task-rest[^/]*_bold\.json)$", name):
            jobs.append((k, s, a.out / "pheno" / name))
    _, subs = list_keys(PIPE, "/")
    n_sub = len(subs)
    for sp in subs:
        sk, _ = list_keys(sp + "roi_timeseries/")
        for k, s in sk:
            m = CC200.match(k[len(PIPE):])
            if m:
                jobs.append((k, s, a.out / "cc200" / f"{m['sub']}_rest_{m['k']}.1D"))
    print(f"CPAC 피험자 폴더 {n_sub} · 받을 파일 {len(jobs)}", flush=True)
    with ThreadPoolExecutor(a.jobs) as pool:
        recs = list(pool.map(lambda j: get(*j), jobs))
    bad = [r for r in recs if not r["ok"]]
    man = {"created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bucket": BUCKET,
           "pipeline_prefix": PIPE, "n_subject_dirs": n_sub, "n_files": len(recs), "n_failed": len(bad),
           "files": recs}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"완료 {len(recs) - len(bad)} · 실패 {len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
