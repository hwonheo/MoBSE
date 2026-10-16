#!/usr/bin/env python3
"""I3 재추출 QC (결정 68) — 전체 길이 시계열을 2 s grid 로 다시 잘라 ``derivatives_v3`` 저장 창과 대조하고, 블록 구조를 센다.

label 과 성능 값은 보지 않는다 (블록 수 · 길이 · 조건 순서 · frame 수만).

Usage:
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/i3_extract_check.py --aomic data/h1h2_scope/aomic --out <json>
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

from mobse.v2 import preprocess as P

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i3_baselines import blocks  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--aomic", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    man = json.loads((a.aomic / "full_ts/manifest.json").read_text())
    rows, structure = [], collections.Counter()
    for r in man["runs"]:
        s = r["subject"]
        if r["status"] != "ok":
            rows.append({"subject": s, "status": r["status"]})
            continue
        z = np.load(a.aomic / "full_ts" / f"{s}_emomatching.npz")
        cut = P.cut_windows(P.resample_to_grid(z["ts"].astype(float), z["times"], P.target_times()))
        diffs = []
        for i, c in enumerate(cut):
            ref = np.load(a.aomic / "ref_all/derivatives_v3" / s / f"{s}_task-emomatching_acq-seq_win-{i}.npy")
            diffs.append(float(np.abs(ref - c.astype(np.float32)).max()))
        blk, soa = blocks(a.aomic / "raw/aomic_wave1/ds002785/raw" / s / "func" / f"{s}_task-emomatching_acq-seq_events.tsv")
        key = (len(blk), tuple(sorted({round(b["end"] - b["start"], 1) for b in blk})), "".join(b["cond"][0] for b in blk))
        structure[str(key)] += 1
        rows.append({"subject": s, "status": "ok", "n_frames": r["n_frames"], "qc_passed_wi02": r["qc_passed_wi02"],
                     "max_abs_diff": max(diffs), "n_blocks": len(blk), "soa": round(soa, 4)})
    ok = [x for x in rows if x["status"] == "ok"]
    out = {"schema": "h1h2-scope-i3-extract-check-0.1", "n_runs": len(rows), "n_ok": len(ok),
           "n_qc_passed_wi02": sum(bool(x["qc_passed_wi02"]) for x in ok),
           "n_frames": sorted({x["n_frames"] for x in ok}),
           "max_abs_diff_overall": max(x["max_abs_diff"] for x in ok),
           "block_structure_counts": dict(structure), "runs": rows}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "runs"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
