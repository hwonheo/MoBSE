#!/usr/bin/env python3
"""BrainGB · BNT · BQN 이 읽는 표준 ``abide.npy`` 를 우리가 받은 PCP 파일로 다시 만든다 (I1 사전 점검).

BrainGB `examples/utils/get_abide` (commit f042694) 의 01–03 단계를 그대로 따른다. 확인한 정의:

* 판: CPAC · **filt_noglobal** · CC200, 대상은 `subject_IDs.txt` 의 1,035 명 순서.
* ``corr`` · ``pcorr``: nilearn ``ConnectivityMeasure(kind="correlation" | "partial correlation")`` 를 **전체 시점**에
  적용 (기본 공분산 추정기 Ledoit-Wolf) → ``np.arctanh`` → ``inf`` 를 0 으로.
* ``timeseires`` (원 코드의 철자 그대로): (ROI, 시점) 로 전치, **시점 100 미만은 빼고** 앞 100 개만 남긴다.
* ``label``: ``DX_GROUP − 1`` — **ASD = 0, TC = 1**. BrainGB README 의 "1 = positive (ASD)" 와 반대다
  (이슈 #28 의 지적이 맞다). 원 코드 그대로 둔다.
* ``site``: phenotype ``SITE_ID``.

원 코드는 subject 별 ``.mat``/``.h5`` 를 거친다. 여기서는 같은 계산을 메모리에서 하고 결과만 쓴다.

Usage (h197, venv-i1):
    python scripts/i1/build_abide_npy.py --pcp /mnt/data/mp2026/MoBSE_dataset/abide_pcp/filt_noglobal \
        --ids <BrainGB repo>/examples/utils/get_abide/subject_IDs.txt --out <dir>/abide.npy
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pcp", required=True, type=Path, help="filt_noglobal 받기 산출 폴더")
    ap.add_argument("--ids", required=True, type=Path, help="BrainGB subject_IDs.txt")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--min-t", type=int, default=100)
    args = ap.parse_args(argv[1:])
    if args.out.exists():
        raise SystemExit(f"이미 존재한다: {args.out}")
    from nilearn import __version__ as nilearn_version
    from nilearn.connectome import ConnectivityMeasure

    pheno = {r["SUB_ID"]: r for r in csv.DictReader(
        (args.pcp / "phenotype" / "Phenotypic_V1_0b_preprocessed1.csv").open(encoding="utf-8"))}
    manifest = {}
    for line in (args.pcp / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        manifest[r["sub_id"]] = r
    ids = [l.strip() for l in args.ids.read_text().splitlines() if l.strip()]
    missing = [i for i in ids if str(int(i)) not in manifest]
    if missing:
        raise SystemExit(f"subject_IDs 중 받지 못한 사람: {missing[:5]} (총 {len(missing)})")

    series = []
    for i in ids:
        rec = manifest[str(int(i))]
        p = args.pcp / rec["path"]
        if hashlib.sha256(p.read_bytes()).hexdigest() != rec["sha256"]:
            raise SystemExit(f"sha256 불일치: {p}")
        ts = np.loadtxt(p)                                 # '#' 머리줄은 loadtxt 가 건너뛴다
        series.append(ts)                                  # (시점, ROI)

    corr = ConnectivityMeasure(kind="correlation").fit_transform(series)
    pcorr = ConnectivityMeasure(kind="partial correlation").fit_transform(series)
    with np.errstate(divide="ignore"):
        corr, pcorr = np.arctanh(corr), np.arctanh(pcorr)
    corr[np.isinf(corr)] = 0
    pcorr[np.isinf(pcorr)] = 0

    keep = [k for k, ts in enumerate(series) if ts.shape[0] >= args.min_t]
    times = np.stack([series[k].T[:, :args.min_t] for k in keep])
    labels = np.array([int(pheno[str(int(ids[k]))]["DX_GROUP"]) - 1 for k in keep])
    sites = np.array([pheno[str(int(ids[k]))]["SITE_ID"] for k in keep])
    data = {"timeseires": times, "label": labels, "corr": corr[keep], "pcorr": pcorr[keep], "site": sites}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.out, data)
    meta = {"schema_version": "i1-abide-npy-0.1", "nilearn": nilearn_version,
            "n_ids": len(ids), "n_kept": len(keep), "n_dropped_short": len(ids) - len(keep),
            "min_t": args.min_t, "label_rule": "DX_GROUP - 1 (ASD=0, TC=1) — BrainGB 원 코드 그대로",
            "label_counts": {"ASD(0)": int((labels == 0).sum()), "TC(1)": int((labels == 1).sum())},
            "shapes": {k: list(v.shape) for k, v in data.items()},
            "n_sites": int(len(set(sites))), "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
            "kept_sub_ids": [str(int(ids[k])) for k in keep]}
    args.out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "kept_sub_ids"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
