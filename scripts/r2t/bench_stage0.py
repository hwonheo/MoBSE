#!/usr/bin/env python3
"""R2T 단계 0 계산량 · 수치 안정성 측정 (결정 83) — **합성 자료만**, 실제 자료를 읽지 않는다.

* 계산량: 1 단계 규모를 흉내 낸 outer fold 하나 — train 100 명 (rest 15 frame 창 8 개), test 26 명 (task 135 frame → 9 창),
  mask 20 벌 (20 %), G1-LW · G1-OAS · RIDGE (λ 13 개 inner 선택). 벽시계 · 최대 RSS 를 잰다. 5 fold 값은 곱한 추정이다.
* 안정성: train frame 수 · AR(1) ρ 를 바꿔 LW shrinkage · 조건수 · oracle 대비 NMSE 비율을 잰다. AR(1) 근사 유효 표본
  n(1−ρ)/(1+ρ) 를 함께 적는다 (실제 BOLD 의 자기상관 구조를 대표한다는 뜻이 아니다).

Usage:
    OMP_NUM_THREADS=2 PYTHONPATH=. .venv/bin/python -B scripts/r2t/bench_stage0.py --out results/r2t/stage0/bench_stage0.json
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
import r2t_lib as R  # noqa: E402
import synth as S  # noqa: E402

LAMBDAS = [10.0 ** e for e in np.arange(-2, 4.01, 0.5)]


def subj_nmse(task, ids, pred_fn, obs, msk, v):
    out = []
    for s in ids:
        t = [R.nmse_terms(y, pred_fn(x), v) for x, y in (R.split_window(w, obs, msk) for w in task[s])]
        out.append(float(np.mean(np.concatenate(t))))
    return np.array(out)


def one_fold(n_train: int, n_test: int, n_masks: int, rho: float, seed: int) -> dict:
    w = S.World(S.SynthSpec(seed=seed, rho=rho))
    t0 = time.perf_counter()
    ids = [f"s{i:03d}" for i in range(n_train + n_test)]
    subs = {s: w.subject(s) for s in ids}
    train, test = ids[:n_train], ids[n_train:]
    R.check_disjoint(train, test)
    rest = {s: subs[s]["rest"] for s in ids}
    task = {s: S.task_windows(subs[s]["run"], 15) for s in ids}
    t_gen = time.perf_counter() - t0

    t0 = time.perf_counter()
    frames = R.stack_full(rest, train)
    g_lw = R.fit_prior(frames, "lw", train)
    g_oas = R.fit_prior(frames, "oas", train)
    t_prior = time.perf_counter() - t0

    masks = R.make_masks(w.spec.n_roi, 0.2, n_masks, seed=seed + 1, left=w.left)
    inner_tr, inner_va = R.subject_split(train, 0.2, seed=seed + 2)
    t_ridge = t_pred = 0.0
    res = {"G1-LW": [], "G1-OAS": [], "RIDGE": [], "ORACLE": []}
    chosen = []
    for msk in masks:
        obs = np.setdiff1d(np.arange(w.spec.n_roi), msk)
        v = R.train_target_variance(task, train, obs, msk)
        t0 = time.perf_counter()
        Xi, Yi = R.stack_frames(rest, inner_tr, obs, msk)
        best = None
        for lam in LAMBDAS:
            m = R.fit_ridge(Xi, Yi, lam, inner_tr)
            e = subj_nmse(task, inner_va, m.predict, obs, msk, v).mean()
            if best is None or e < best[0] - 1e-4:
                best = (e, lam)
        X, Y = R.stack_frames(rest, train, obs, msk)
        rg = R.fit_ridge(X, Y, best[1], train)
        chosen.append(best[1])
        t_ridge += time.perf_counter() - t0
        t0 = time.perf_counter()
        B = w.oracle_B(obs, msk)
        res["G1-LW"].append(subj_nmse(task, test, lambda x: g_lw.predict(x, obs, msk), obs, msk, v))
        res["G1-OAS"].append(subj_nmse(task, test, lambda x: g_oas.predict(x, obs, msk), obs, msk, v))
        res["RIDGE"].append(subj_nmse(task, test, rg.predict, obs, msk, v))
        res["ORACLE"].append(subj_nmse(task, test, lambda x: x @ B.T, obs, msk, v))
        t_pred += time.perf_counter() - t0
    per_subj = {k: np.mean(np.stack(v), 0) for k, v in res.items()}
    d = R.delta(per_subj["G1-LW"], per_subj["RIDGE"])
    est, lo, hi = R.subject_bootstrap(d, 2000, seed=seed + 3)
    return {
        "n_train": n_train, "n_test": n_test, "n_masks": n_masks, "rho": rho,
        "train_frames": int(len(frames)), "ess_ar1_approx": float(len(frames) * (1 - rho) / (1 + rho)),
        "lw_shrinkage": g_lw.shrinkage, "oas_shrinkage": g_oas.shrinkage,
        "cond_lw": float(np.linalg.cond(g_lw.cov)), "cond_oas": float(np.linalg.cond(g_oas.cov)),
        "nmse_mean": {k: float(v.mean()) for k, v in per_subj.items()},
        "nmse_ratio_to_oracle": {k: float(per_subj[k].mean() / per_subj["ORACLE"].mean()) for k in ("G1-LW", "G1-OAS", "RIDGE")},
        "delta_ridge_minus_g1lw_note": "Δ = NMSE(G1-LW) − NMSE(RIDGE), 양수면 RIDGE 가 낫다 (부호 통일 시험용)",
        "delta_ridge_vs_g1lw": [est, lo, hi],
        "ridge_lambda_chosen": sorted(set(chosen)),
        "seconds": {"generate": t_gen, "prior_fit": t_prior, "ridge_inner_and_fit": t_ridge, "predict_eval": t_pred},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t_all = time.perf_counter()
    scale = one_fold(n_train=100, n_test=26, n_masks=20, rho=0.5, seed=101)
    stab = [one_fold(n_train=n, n_test=26, n_masks=3, rho=rho, seed=200 + i)
            for i, (n, rho) in enumerate([(10, 0.5), (25, 0.5), (100, 0.0), (100, 0.5), (100, 0.8)])]
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / 2 ** 20 if platform.system() == "Darwin" else rss / 2 ** 10
    out = {"schema": "r2t-stage0-bench-0.1", "synthetic_only": True, "decision": 83,
           "host": platform.node(), "platform": platform.platform(), "python": platform.python_version(),
           "numpy": np.__version__, "omp_threads": os.environ.get("OMP_NUM_THREADS"),
           "scale_one_fold": scale,
           "scale_five_fold_seconds_estimate": 5 * sum(scale["seconds"].values()),
           "stability": stab, "peak_rss_mb": rss_mb, "wall_seconds_total": time.perf_counter() - t_all}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
