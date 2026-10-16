#!/usr/bin/env python3
"""I3 routing 재현 진단 (결정 71) 집계 — ``routing_repro.py`` 산출만 읽는다.

칸마다: 본 실행과 바이트 동일한 fit 수 · test routing (expert 별 평균 · 표본 사이 SD · entropy) · label 사이 routing 차이 ·
dynamic 칸은 routing 고정 대조 정확도 (seed 평균 p 를 0.5 로 자름, 블록 단위). epoch 별 val routing entropy 궤적 (중앙).

Usage:
    python3 scripts/i3_diag/routing_summary.py data/i3/diag/routing_a1
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path


def block_acc(files) -> float:
    probs, lab = defaultdict(list), {}
    for f in files:
        for line in f.read_text().splitlines():
            r = json.loads(line)
            probs[(r["subject"], r["block"])].append(r["p1"])
            lab[(r["subject"], r["block"])] = r["label"]
    ok = [int((sum(p) / len(p) >= 0.5) == lab[k]) for k, p in probs.items()]
    return sum(ok) / len(ok)


def main() -> int:
    root = Path(sys.argv[1])
    out = {}
    for cell_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        sums = [json.loads(f.read_text()) for f in sorted(cell_dir.glob("outer*/seed*/summary.json"))]
        if not sums:
            continue
        fit_dirs = sorted(f.parent for f in cell_dir.glob("outer*/seed*/summary.json"))
        ent_traj = defaultdict(list)
        for d in fit_dirs:
            for line in (d / "epochs.jsonl").read_text().splitlines():
                r = json.loads(line)
                ent_traj[r["epoch"]].append(r["val_routing"]["entropy_mean"])
        res = {
            "n_fits": len(sums),
            "repro_identical": sum(s["repro_identical"] for s in sums),
            "test_routing_mean_median": [st.median(s["test_routing"]["mean"][e] for s in sums) for e in range(3)],
            "test_routing_sd_median": [st.median(s["test_routing"]["sd"][e] for s in sums) for e in range(3)],
            "test_entropy_median": st.median(s["test_routing"]["entropy_mean"] for s in sums),
            "test_entropy_range": [min(s["test_routing"]["entropy_mean"] for s in sums),
                                   max(s["test_routing"]["entropy_mean"] for s in sums)],
            "max_abs_label_gap_median": st.median(max(abs(v) for v in s["routing_label_gap"]) for s in sums),
            "acc_seedmean": block_acc([d / "test_routing.jsonl" for d in fit_dirs]),
            "val_entropy_epoch": {e: st.median(ent_traj[e]) for e in (0, 1, 5, 20, 50, 100, 294) if e in ent_traj},
        }
        if "test_acc_block_override" in sums[0]:
            res["acc_seedmean_fixed_override"] = block_acc([d / "test_fixed_override.jsonl" for d in fit_dirs])
        out[cell_dir.name] = res
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
