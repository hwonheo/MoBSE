#!/usr/bin/env python3
"""ABIDE I Preprocessed Connectomes Project (PCP) ROI 시계열을 받는다 — I1 공개 자료 축 (결정 36).

받는 판: **CPAC · filt_global (band-pass + 전역 신호 회귀) · CC200 (200 ROI)**. Mac `~/nilearn_data/ABIDE_pcp`
에 있던 판 (정상 대조군 468 명) 과 같은 판이며, ASD 와 TC 를 모두 받아 한 판으로 맞춘다.

출처: `s3://fcp-indi/data/Projects/ABIDE_Initiative` (공개 버킷, HTTPS). 표준 라이브러리만 쓴다 —
v2 venv 에 아무것도 설치하지 않기 위해서다 (구현 잠금이 그 환경을 기록한다).

품질 기준은 **고르지 않고 기록만** 한다. ``nilearn_qc_pass`` 는 nilearn ``fetch_abide_pcp(quality_checked=True)``
가 쓰는 규칙 (qc_rater_1 · qc_anat_rater_2 · qc_func_rater_2 · qc_anat_rater_3 · qc_func_rater_3 중 'fail'
이 하나도 없음) 을 그대로 옮긴 표시다. 어느 규칙으로 고를지는 I1 설계에서 정한다.

산출: ``<out>/phenotype/…csv`` · ``<out>/cpac/filt_global/rois_cc200/*.1D`` · ``manifest.jsonl`` · ``summary.json``.
이미 받은 파일은 sha256 을 다시 재고 건너뛴다. 덮어쓰지 않는다.

Usage (h197):
    python3 scripts/i1/fetch_abide_pcp.py --out /mnt/data/mp2026/MoBSE_dataset/abide_pcp
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://s3.amazonaws.com/fcp-indi/data/Projects/ABIDE_Initiative"
PHENO = "Phenotypic_V1_0b_preprocessed1.csv"
PIPELINE, STRATEGY, DERIV = "cpac", "filt_global", "rois_cc200"
QC_COLS = ("qc_rater_1", "qc_anat_rater_2", "qc_func_rater_2", "qc_anat_rater_3", "qc_func_rater_3")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url: str, dest: Path, tries: int = 4) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, tmp.open("wb") as fh:
                fh.write(r.read())
            tmp.rename(dest)
            return
        except Exception as exc:                       # noqa: BLE001 — 재시도 뒤 다시 던진다
            if i == tries - 1:
                raise RuntimeError(f"{url}: {exc}") from exc
            time.sleep(2 * (i + 1))


def shape_of(path: Path) -> tuple:
    rows = [l.split() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")]
    return len(rows), (len(rows[0]) if rows else 0)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv[1:])
    out = args.out
    (out / "phenotype").mkdir(parents=True, exist_ok=True)
    roi_dir = out / PIPELINE / STRATEGY / DERIV
    roi_dir.mkdir(parents=True, exist_ok=True)
    log = (out / "fetch.log").open("a", encoding="utf-8")

    def say(msg):
        line = f"{now()} {msg}"
        print(line, flush=True)
        log.write(line + "\n"); log.flush()

    ph_path = out / "phenotype" / PHENO
    if not ph_path.exists():
        fetch(f"{BASE}/{PHENO}", ph_path)
    say(f"phenotype {PHENO} sha256 {sha256(ph_path)[:16]}")
    rows = list(csv.DictReader(ph_path.open(encoding="utf-8")))
    subjects = [r for r in rows if r["FILE_ID"] and r["FILE_ID"] != "no_filename"]
    say(f"phenotype 행 {len(rows)} · 파일 있는 subject {len(subjects)}")

    def one(r):
        fid = r["FILE_ID"]
        name = f"{fid}_{DERIV}.1D"
        url = f"{BASE}/Outputs/{PIPELINE}/{STRATEGY}/{DERIV}/{name}"
        dest = roi_dir / name
        fresh = not dest.exists()
        if fresh:
            fetch(url, dest)
        n_t, n_roi = shape_of(dest)
        return {"file_id": fid, "sub_id": r["SUB_ID"], "site": r["SITE_ID"],
                "dx_group": int(r["DX_GROUP"]), "dx": "ASD" if r["DX_GROUP"] == "1" else "TC",
                "sex": r.get("SEX"), "age": r.get("AGE_AT_SCAN"),
                "func_mean_fd": r.get("func_mean_fd"),
                "nilearn_qc_pass": all(r.get(c, "") != "fail" for c in QC_COLS),
                "path": str(dest.relative_to(out)), "url": url, "bytes": dest.stat().st_size,
                "sha256": sha256(dest), "n_timepoints": n_t, "n_rois": n_roi,
                "downloaded_now": fresh}

    recs, fails = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, r): r["FILE_ID"] for r in subjects}
        for k, f in enumerate(as_completed(futs), 1):
            try:
                recs.append(f.result())
            except Exception as exc:                   # noqa: BLE001 — 실패를 모아 보고한다
                fails.append({"file_id": futs[f], "error": str(exc)})
            if k % 100 == 0 or k == len(futs):
                say(f"   {k}/{len(futs)} (실패 {len(fails)})")
    recs.sort(key=lambda r: r["file_id"])
    with (out / "manifest.jsonl").open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    bad_shape = [r["file_id"] for r in recs if r["n_rois"] != 200 or r["n_timepoints"] == 0]
    summ = {
        "schema_version": "i1-abide-pcp-fetch-0.1", "created_utc": now(),
        "source": BASE, "pipeline": PIPELINE, "strategy": STRATEGY, "derivative": DERIV,
        "phenotype_sha256": sha256(ph_path),
        "n_subjects_with_file": len(subjects), "n_downloaded_ok": len(recs), "n_failed": len(fails),
        "failed": fails, "bad_shape": bad_shape,
        "by_dx": dict(collections.Counter(r["dx"] for r in recs)),
        "by_dx_nilearn_qc_pass": dict(collections.Counter(r["dx"] for r in recs if r["nilearn_qc_pass"])),
        "n_sites": len({r["site"] for r in recs}),
        "by_site": dict(sorted(collections.Counter(r["site"] for r in recs).items())),
        "timepoints": dict(sorted(collections.Counter(r["n_timepoints"] for r in recs).items())),
        "total_bytes": sum(r["bytes"] for r in recs),
        "manifest_sha256": sha256(out / "manifest.jsonl"),
        "qc_rule_note": "nilearn_qc_pass 는 기록만 — 선택 규칙은 I1 설계에서 정한다",
    }
    (out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    say(f"끝: ok {len(recs)} · 실패 {len(fails)} · 모양 이상 {len(bad_shape)} · {summ['by_dx']} · "
        f"QC 통과 {summ['by_dx_nilearn_qc_pass']} · {summ['total_bytes'] / 2**20:.0f} MiB")
    say("FETCH_RC=" + ("0" if not fails and not bad_shape else "1"))
    return 0 if not fails and not bad_shape else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
