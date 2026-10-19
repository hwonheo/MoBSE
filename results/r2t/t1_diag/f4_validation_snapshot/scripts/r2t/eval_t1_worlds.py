#!/usr/bin/env python3
"""R2T T1 합성 세계 묶음 평가 (결정 88) — **합성 자료만**. 세계 종류 · seed · ROI 수 · 사람 수를 받아 G-A 를 잰다.

세계: pos (참 K=3) · null (참 K=1) · wrong (task 를 다른 상태 공분산 묶음에서, task bank seed = world seed + 10000).
방법: t1 (결정 87 승인판, configs/r2t/t1_pilot.json) · t1_reg (F1, configs/r2t/t1_pilot_reg.json).

Usage:
    OMP_NUM_THREADS=2 PYTHONPATH=. .venv/bin/python -B scripts/r2t/eval_t1_worlds.py --method t1_reg \
        --worlds pos:301 null:311 wrong:321 --n-roi 100 --n-subjects 31 --tag dev --out results/r2t/t1_diag/X.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg  # noqa: E402
import t1_reg2  # noqa: E402
import t1_reg3  # noqa: E402
import t1_reg4  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
METHODS = {"t1": (t1, "t1_pilot.json"), "t1_reg": (t1_reg, "t1_pilot_reg.json"),
           "t1_reg2": (t1_reg2, "t1_pilot_reg2.json"),
           "t1_reg3": (t1_reg3, "t1_pilot_reg3.json"),
           "t1_reg4": (t1_reg4, "t1_pilot_reg4.json")}


def world(kind: str, seed: int, n_roi: int, n_subjects: int):
    if kind == "pos":
        return ST.make(n_subjects=n_subjects, n_roi=n_roi, n_states=3, seed=seed)
    if kind == "null":
        return ST.make(n_subjects=n_subjects, n_roi=n_roi, n_states=1, seed=seed)
    if kind == "wrong":
        return ST.make(n_subjects=n_subjects, n_roi=n_roi, n_states=3, seed=seed, task_bank_seed=seed + 10000)
    raise ValueError(kind)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--method", choices=sorted(METHODS), required=True)
    ap.add_argument("--worlds", nargs="+", required=True, help="kind:seed")
    ap.add_argument("--n-roi", type=int, default=100)
    ap.add_argument("--n-subjects", type=int, default=31)
    ap.add_argument("--tag", required=True, help="dev · validation · boundary 등 — 결과 용도")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"덮어쓰지 않는다: {a.out}")
    mod, cfg_name = METHODS[a.method]
    cfg = t1.load_config(ROOT / "configs" / "r2t" / cfg_name)
    rows = []
    for spec in a.worlds:
        kind, seed = spec.split(":")
        ids, rest, task, left = world(kind, int(seed), a.n_roi, a.n_subjects)
        t0 = time.perf_counter()
        res = mod.run_pipeline(rest, task, ids, cfg, left)
        per = res.get("per_subject_nmse", {})
        means = {m: float(np.mean(list(v.values()))) for m, v in per.items()}
        row = {"world": kind, "seed": int(seed), "seconds": time.perf_counter() - t0, "mean_nmse": means,
               "delta": res.get("delta_best_minus_mixa"), "delta_sd": res.get("delta_sd"), "aux": res.get("aux"),
               "n_fallback_subjects": res.get("n_fallback_subjects"), "mix_fail_folds": res.get("mix_fail_folds"),
               "inner_failed_a_total": res.get("inner_failed_a_total"),
               "delta_okfolds_reference": res.get("delta_best_minus_mixa_okfolds_reference"),
               "verdict": res["verdict"],
               "folds": [{k: f.get(k) for k in ("best", "mix_pick", "tau_label", "lam", "em_a", "h", "tau_ess", "mix")}
                         for f in res.get("folds", [])]}
        rows.append(row)
        d = row["delta"]
        print(f"{kind}:{seed} Δ={d[0]:+.4f} [{d[1]:+.4f}, {d[2]:+.4f}] BEST={means['BEST']:.4f} "
              f"picks={[f.get('mix_pick') or f.get('tau_label') for f in row['folds']]} {row['seconds']:.0f}s"
              if d else f"{kind}:{seed} Δ=None {res['verdict']}", file=sys.stderr, flush=True)
    out = {"schema": "r2t-t1-worlds-0.1", "synthetic_only": True, "decision": 88, "method": a.method, "config": cfg_name,
           "tag": a.tag, "n_roi": a.n_roi, "n_subjects": a.n_subjects, "rows": rows}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
