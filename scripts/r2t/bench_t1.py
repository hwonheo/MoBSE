#!/usr/bin/env python3
"""R2T T1 pilot 규모 자원 측정 (결정 87) — **합성 자료만**. 설정은 `configs/r2t/t1_pilot.json` 그대로 (100 ROI · 31 명 · 5 fold ·
mask 10 · K 3 · n_init 10 · BEST 7 후보 · bootstrap 10,000). 실제 값은 읽지 않는다.

Usage:
    OMP_NUM_THREADS=2 PYTHONPATH=. .venv/bin/python -B scripts/r2t/bench_t1.py --out results/r2t/t1_prerun/bench_t1.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg = t1.load_config(Path(__file__).resolve().parents[2] / "configs" / "r2t" / "t1_pilot.json")
    rows = []
    for name, ns in (("positive (참 K=3)", 3), ("null (참 K=1)", 1)):
        ids, rest, task, left = ST.make(n_subjects=31, n_roi=100, n_states=ns, seed=61 + ns)
        t0 = time.perf_counter()
        res = t1.run_pipeline(rest, task, ids, cfg, left)
        sec = time.perf_counter() - t0
        rows.append({"world": name, "seconds": sec, "delta": res["delta_best_minus_mixa"], "delta_sd": res["delta_sd"],
                     "verdict": res["verdict"], "folds": [{k: f.get(k) for k in ("best", "tau_label", "tau_ess", "mix", "cond")}
                                                          for f in res["folds"]]})
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out = {"schema": "r2t-t1-bench-0.1", "synthetic_only": True, "decision": 87, "host": platform.node(),
           "platform": platform.platform(), "numpy": np.__version__, "omp_threads": os.environ.get("OMP_NUM_THREADS"),
           "rows": rows, "peak_rss_mb": rss / 2 ** 20 if platform.system() == "Darwin" else rss / 2 ** 10}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
