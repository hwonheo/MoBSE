#!/usr/bin/env python3
"""R2T T1 어려운 합성 세계 평가 (결정 88 · 실패 경계, 기술값) — **합성 자료만**. `eval_t1_worlds` 와 같은 출력 형식.

세계 지정: "sep=0.3,dwell=15,phase=aligned,rho=0.5,ns=3:401" (빠진 키는 기본값 sep 1 · dwell 15 · aligned · ρ 0.5 · ns 3).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_t1_hard as H  # noqa: E402
import t1  # noqa: E402
from eval_t1_worlds import METHODS, ROOT  # noqa: E402

DEFAULT = {"sep": 1.0, "dwell": 15, "phase": "aligned", "rho": 0.5, "ns": 3, "wrong": 0}


def parse(spec: str):
    body, seed = spec.rsplit(":", 1)
    kw = dict(DEFAULT)
    for item in filter(None, body.split(",")):
        k, v = item.split("=")
        kw[k] = v if k == "phase" else (int(v) if k in ("dwell", "ns", "wrong") else float(v))
    return kw, int(seed)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--method", choices=sorted(METHODS), required=True)
    ap.add_argument("--worlds", nargs="+", required=True)
    ap.add_argument("--n-roi", type=int, default=100)
    ap.add_argument("--n-subjects", type=int, default=31)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"덮어쓰지 않는다: {a.out}")
    mod, cfg_name = METHODS[a.method]
    cfg = t1.load_config(ROOT / "configs" / "r2t" / cfg_name)
    rows = []
    for spec in a.worlds:
        kw, seed = parse(spec)
        ids, rest, task, left, states = H.make(n_subjects=a.n_subjects, seed=seed, n_roi=a.n_roi, n_states=kw["ns"],
                                               sep=kw["sep"], dwell=kw["dwell"], phase=kw["phase"], rho=kw["rho"],
                                               task_bank_seed=seed + 10000 if kw["wrong"] else None)
        mixed = float(np.mean([len(set(ts[i:i + 15])) > 1 for s in ids for ts in [states[s][1]] for i in range(0, 135, 15)]))
        t0 = time.perf_counter()
        res = mod.run_pipeline(rest, task, ids, cfg, left)
        per = res.get("per_subject_nmse", {})
        means = {m: float(np.mean(list(v.values()))) for m, v in per.items()}
        row = {"world": spec, "params": kw, "seed": seed, "task_windows_with_state_change": mixed,
               "seconds": time.perf_counter() - t0, "mean_nmse": means, "delta": res.get("delta_best_minus_mixa"),
               "delta_sd": res.get("delta_sd"), "aux": res.get("aux"),
               "n_fallback_subjects": res.get("n_fallback_subjects"), "mix_fail_folds": res.get("mix_fail_folds"),
               "inner_failed_a_total": res.get("inner_failed_a_total"),
               "delta_okfolds_reference": res.get("delta_best_minus_mixa_okfolds_reference"), "verdict": res["verdict"],
               "folds": [{k: f.get(k) for k in ("best", "mix_pick", "tau_label", "lam", "em_a", "h", "tau_ess", "mix")}
                         for f in res.get("folds", [])]}
        rows.append(row)
        a.out.with_suffix(".partial.jsonl").open("a").write(json.dumps(row, ensure_ascii=False) + "\n")   # 중간 결과 보존
        d = row["delta"]
        print(f"{spec} mixed={mixed:.2f} Δ={d[0]:+.4f} [{d[1]:+.4f}, {d[2]:+.4f}] BEST={means['BEST']:.4f} "
              f"fb={res.get('n_fallback_subjects')} ok-only={res.get('delta_best_minus_mixa_okfolds_reference')} picks={sorted(set(str(f.get('mix_pick') or f.get('tau_label') or f.get('mix')) for f in row['folds']))} "
              f"{row['seconds']:.0f}s" if d else f"{spec} Δ=None {res['verdict']}", file=sys.stderr, flush=True)
    out = {"schema": "r2t-t1-hard-0.1", "synthetic_only": True, "decision": 88, "method": a.method, "config": cfg_name,
           "tag": a.tag, "n_roi": a.n_roi, "n_subjects": a.n_subjects, "rows": rows}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
