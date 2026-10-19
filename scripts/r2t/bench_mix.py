#!/usr/bin/env python3
"""R2T 상태 혼합 소형 측정 (결정 84) — **합성 자료만**. 파라미터 탐색 없음 (τ = 1, K = 참값 3, 고정 설정).

* 자기상관 ρ ∈ {0, 0.8} × {null (참 K=1), positive (참 K=3)}: G1 · MIX-f · MIX-a NMSE, Δ, MIX-a 가중치 최댓값 (과신 정도).
* 계산량: 100 ROI · train 100 명 × rest 창 8 · K=3 · n_init 10 적합 시간과 예측 시간 (test 26 명 × 9 창 × mask 20).
합성 결과는 실제 BOLD 가설의 근거가 아니다.

Usage:
    OMP_NUM_THREADS=2 PYTHONPATH=. .venv/bin/python -B scripts/r2t/bench_mix.py --out results/r2t/stage0/bench_mix.json
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
import mix as M  # noqa: E402
import r2t_lib as R  # noqa: E402
import synth_mix as SM  # noqa: E402


def world(n_states, rho, seed, n_roi, n_train, n_test, n_masks):
    w = SM.MixWorld(SM.MixSpec(n_roi=n_roi, n_states=n_states, rho=rho, seed=seed))
    ids = [f"s{i:03d}" for i in range(n_train + n_test)]
    subs = {s: w.subject(s) for s in ids}
    return {"w": w, "subs": subs, "train": ids[:n_train], "test": ids[n_train:],
            "rest": {s: subs[s]["rest"] for s in ids}, "task": {s: subs[s]["task"] for s in ids},
            "masks": R.make_masks(n_roi, 0.2, n_masks, seed=seed + 1, left=w.left)}


def evaluate(d, fit, g1):
    n = d["w"].spec.n_roi
    per = {k: {s: [] for s in d["test"]} for k in ("G1", "MIX-f", "MIX-a")}
    wmax = []
    for msk in d["masks"]:
        obs = np.setdiff1d(np.arange(n), msk)
        v = R.train_target_variance(d["task"], d["train"], obs, msk)
        for s in d["test"]:
            for win in d["task"][s]:
                x, y = R.split_window(win, obs, msk)
                pa, wt = M.predict_adaptive(fit, x, obs, msk)
                wmax.append(float(wt.max()))
                for k, p in (("G1", g1.predict(x, obs, msk)), ("MIX-f", M.predict_fixed(fit, x, obs, msk)), ("MIX-a", pa)):
                    per[k][s].append(R.nmse_terms(y, p, v).ravel())
    e = {k: np.array([np.mean(np.concatenate(v)) for v in d_.values()]) for k, d_ in per.items()}
    con = {}
    for a, b in (("MIX-a", "G1"), ("MIX-a", "MIX-f"), ("MIX-f", "G1")):
        con[f"{a} 대 {b}"] = list(R.subject_bootstrap(R.delta(e[b], e[a]), 2000, seed=7))
    return {"nmse": {k: float(v.mean()) for k, v in e.items()}, "delta": con,
            "mixa_weight_max_median": float(np.median(wmax)), "mixa_weight_max_p10": float(np.percentile(wmax, 10))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t_all = time.perf_counter()
    grid = []
    for n_states, tag in ((1, "null"), (3, "positive")):
        for rho in (0.0, 0.8):
            d = world(n_states, rho, seed=300 + 10 * n_states + int(rho * 10), n_roi=50, n_train=40, n_test=15, n_masks=4)
            fit = M.fit_mixture(M.windows_full(d["rest"], d["train"]), 3, d["train"], seed=1, min_occupancy=0.0)
            g1 = R.fit_prior(R.stack_full(d["rest"], d["train"]), "lw", d["train"])
            row = {"world": tag, "true_K": n_states, "rho": rho, "fit_status": fit.status,
                   "pis": fit.pis.tolist(), "shrinkage": fit.shrinkage.tolist()}
            row.update(evaluate(d, fit, g1))
            grid.append(row)

    d = world(3, 0.5, seed=400, n_roi=100, n_train=100, n_test=26, n_masks=20)
    t0 = time.perf_counter()
    Xw = M.windows_full(d["rest"], d["train"])
    fit = M.fit_mixture(Xw, 3, d["train"], seed=1)
    t_fit = time.perf_counter() - t0
    g1 = R.fit_prior(R.stack_full(d["rest"], d["train"]), "lw", d["train"])
    t0 = time.perf_counter()
    scale_eval = evaluate(d, fit, g1)
    t_pred = time.perf_counter() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out = {"schema": "r2t-mix-bench-0.1", "synthetic_only": True, "decision": 84, "tau": 1.0,
           "host": platform.node(), "platform": platform.platform(), "numpy": np.__version__,
           "omp_threads": os.environ.get("OMP_NUM_THREADS"), "grid": grid,
           "scale": {"n_roi": 100, "n_train": 100, "train_windows": int(len(Xw)), "K": 3, "n_init": 10,
                     "fit_status": fit.status, "fit_seconds": t_fit, "n_iter": fit.n_iter,
                     "predict_eval_seconds_3methods_20masks": t_pred, "eval": scale_eval},
           "peak_rss_mb": rss / 2 ** 20 if platform.system() == "Darwin" else rss / 2 ** 10,
           "wall_seconds_total": time.perf_counter() - t_all}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
