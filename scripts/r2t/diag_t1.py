#!/usr/bin/env python3
"""R2T T1 병목 분해 (결정 88) — **합성 자료만, 진단용**. oracle (참 상태 · 큰 표본 모집단 공분산) 은 병목을 가르는 데만 쓰고
모델 성능으로 보고하지 않는다. 기존 `t1` · `mix` · `synth_t1` 은 바꾸지 않고 불러 쓴다.

fold 마다 (승인 설정 그대로) `t1.run_fold` 로 BEST · MIX-a 를 얻고, 같은 test 사람 · mask · 분모로 아래 사다리를 잰다.

* POP-K1      : 모집단 pooled 공분산 (oracle) 의 조건부 예측 — K=1 상한
* POP-K3-true : 모집단 상태 공분산 + 참 task 창 상태 (oracle) — K=3 상한
* POP-K3-a    : 모집단 상태 공분산 + 관측으로 정한 가중치 (τ = fold 선택값) — 가중치 손실만
* LAB-K3-true : fold train rest 를 **참 상태 라벨**로 나눠 가중 LW 로 추정 + 참 task 상태 — 추정 손실 (군집 오류 없음)
* LAB-K3-a    : 같은 공분산 + 관측 가중치
* EM-K3-true  : EM 성분 (참 상태와 짝지음) + 참 task 상태 — 군집 · 추정 손실, 가중치 손실 없음
* MIX-a       : 실제 경로
* G1-LW · RIDGE λ 전체 : K=1 추정 경로 참고
* LAB-RIDGE-true : 참 상태별로 나눈 rest frame 에 ridge (λ grid 중 test 기준 최선 — oracle 진단용) + 참 task 상태

Usage:
    OMP_NUM_THREADS=2 PYTHONPATH=. .venv/bin/python -B scripts/r2t/diag_t1.py --seed 64 --n-roi 100 --n-subjects 31 --out X.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix as M  # noqa: E402
import r2t_lib as R  # noqa: E402
import synth_mix as SM  # noqa: E402
import synth_t1 as ST  # noqa: E402
import synth_variants as SV  # noqa: E402
import t1  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def make_with_states(n_subjects, n_roi, n_states, rho=0.5, seed=0, prefix="p", **variant):
    """`synth_t1.make` 와 같은 자료 + 창별 참 상태 (진단용). prefix 를 바꾸면 다른 사람 (모집단 표본용)."""
    w = SV.VariantWorld(SM.MixSpec(n_roi=n_roi, n_states=n_states, rho=rho, seed=seed, length=15,
                                   n_rest_windows=8, n_task_windows=9), **variant)
    ids = [f"{prefix}{i:03d}" for i in range(n_subjects)]
    rest, task, rs, ts = {}, {}, {}, {}
    for s in ids:
        d = w.subject(s)
        r, t = ST._z(np.concatenate(d["rest"])), ST._z(np.concatenate(d["task"]))
        rest[s] = [r[i:i + 15] for i in range(0, 120, 15)]
        task[s] = [t[i:i + 15] for i in range(0, 135, 15)]
        rs[s], ts[s] = np.asarray(d["rest_states"]), np.asarray(d["task_states"])
    return ids, rest, task, w.left, rs, ts


def pop_covs(n_roi, n_states, seed, n_big, **variant):
    """큰 독립 표본 (다른 사람 id) 에서 상태별 · pooled 표본 공분산 (평균 0) — task 쪽 생성 규칙 기준."""
    ids, _, task, _, _, ts = make_with_states(n_big, n_roi, n_states, seed=seed, prefix="POP", **variant)
    X = np.concatenate([w for s in ids for w in task[s]])
    lab = np.concatenate([np.repeat(ts[s], 15) for s in ids])
    covs = np.stack([X[lab == k].T @ X[lab == k] / (lab == k).sum() for k in range(n_states)])
    pis = np.array([(lab == k).mean() for k in range(n_states)])
    return covs, pis, X.T @ X / len(X)


def _fit(covs, pis, shr=None):
    K = len(covs)
    return M.MixFit(K, np.asarray(covs), np.asarray(pis), 0.0, 0, True, "ok", "", np.asarray(pis),
                    np.zeros(K) if shr is None else np.asarray(shr))


def nmse_by_window(task, eval_ids, v_ids, masks, n_roi, pred):
    """pred(s, i, x, obs, msk) → 예측. 사람별 NMSE."""
    R.check_disjoint(v_ids, eval_ids)
    per = {s: [] for s in eval_ids}
    for msk in masks:
        obs = np.setdiff1d(np.arange(n_roi), msk)
        v = t1.t1_target_variance(task, v_ids, obs, msk)
        for s in eval_ids:
            for i, win in enumerate(task[s]):
                x, y = t1.t1_split(win, obs, msk)
                per[s].append(R.nmse_terms(y, pred(s, i, x, obs, msk), v).ravel())
    return np.array([np.mean(np.concatenate(per[s])) for s in eval_ids])


def cond_k(fit, k, x, obs, msk):
    return M._cond_means(fit, x, obs, msk)[k]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-roi", type=int, default=100)
    ap.add_argument("--n-subjects", type=int, default=31)
    ap.add_argument("--n-states", type=int, default=3)
    ap.add_argument("--n-pop", type=int, default=800)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot.json")
    t0 = time.perf_counter()
    ids, rest, task, left, rs, ts = make_with_states(a.n_subjects, a.n_roi, a.n_states, seed=a.seed)
    ids0, rest0, task0, _ = ST.make(n_subjects=a.n_subjects, n_roi=a.n_roi, n_states=a.n_states, seed=a.seed)
    assert ids0 == ids and all(np.array_equal(rest0[s][j], rest[s][j]) for s in ids for j in range(8))
    Pc, Pp, Pk1 = pop_covs(a.n_roi, a.n_states, a.seed, a.n_pop)
    pop3, pop1 = _fit(Pc, Pp), _fit(Pk1[None], [1.0])
    masks = R.make_masks(a.n_roi, cfg["mask"]["frac"], cfg["mask"]["n_masks"], seed=cfg["mask"]["seed"], left=left)
    folds = t1.person_folds(ids, cfg["split"]["n_folds"], cfg["split"]["fold_seed"])
    kw = t1._fit_kw(cfg)
    per = {}
    diag = []
    for k, test in enumerate(folds):
        train = sorted(set(ids) - set(test))
        rec = t1.run_fold(rest, task, train, test, masks, a.n_roi, cfg, k)
        res = dict(rec["nmse"])
        tau = rec.get("tau", 1.0)
        d = {"fold": k, "best": rec["best"], "tau_label": rec.get("tau_label"), "tau": tau, "mix": rec["mix"]}
        # 참 라벨 추정 (군집 오류 없음)
        Xw = t1.t1_windows(rest, train)
        lab = np.concatenate([rs[s] for s in train])
        covs, pis, shr = M._m_step(Xw, np.eye(a.n_states)[lab], cfg["mix"]["eig_floor_rel"])
        labfit = _fit(covs, pis, shr)
        d["lab_shrinkage"] = shr.tolist()
        # EM 적합 (실제 경로와 같은 seed · 규칙) + 참 상태와 짝짓기
        em = M.fit_mixture(Xw, a.n_states, train, **kw)
        if em.status == "ok":
            ll = M.window_loglik(Xw, em.covs) + np.log(em.pis)
            resp = np.exp(ll - M._logsumexp(ll, 1)[:, None])
            cont = np.stack([resp[lab == j].sum(0) for j in range(a.n_states)])        # (참 상태, 성분)
            r_, c_ = linear_sum_assignment(-cont)
            emap = dict(zip(r_, c_))
            d["em_state_acc"] = float(sum(cont[j, emap[j]] for j in range(a.n_states)) / len(lab))
            d["em_shrinkage"] = em.shrinkage.tolist()
            d["em_cov_err_rel"] = [float(np.linalg.norm(em.covs[emap[j]] - Pc[j]) / np.linalg.norm(Pc[j]))
                                   for j in range(a.n_states)]
        d["lab_cov_err_rel"] = [float(np.linalg.norm(covs[j] - Pc[j]) / np.linalg.norm(Pc[j])) for j in range(a.n_states)]
        # 관측 가중치의 상태 맞힘 (test task 창, mask 0)
        obs0 = np.setdiff1d(np.arange(a.n_roi), masks[0])
        hit = {"POP": [], "LAB": [], "EM": []}
        for s in test:
            for i, win in enumerate(task[s]):
                x = win[:, obs0]
                hit["POP"].append(int(np.argmax(M.adaptive_weights(pop3, x, obs0, tau)) == ts[s][i]))
                hit["LAB"].append(int(np.argmax(M.adaptive_weights(labfit, x, obs0, tau)) == ts[s][i]))
                if em.status == "ok":
                    hit["EM"].append(int(np.argmax(M.adaptive_weights(em, x, obs0, tau)) == emap[ts[s][i]]))
        d["weight_state_acc"] = {kk: float(np.mean(v)) for kk, v in hit.items() if v}
        res["POP-K1"] = nmse_by_window(task, test, train, masks, a.n_roi, lambda s, i, x, o, m: cond_k(pop1, 0, x, o, m))
        res["POP-K3-true"] = nmse_by_window(task, test, train, masks, a.n_roi, lambda s, i, x, o, m: cond_k(pop3, ts[s][i], x, o, m))
        res["POP-K3-a"] = nmse_by_window(task, test, train, masks, a.n_roi,
                                         lambda s, i, x, o, m: M.predict_adaptive(pop3, x, o, m, tau)[0])
        res["LAB-K3-true"] = nmse_by_window(task, test, train, masks, a.n_roi, lambda s, i, x, o, m: cond_k(labfit, ts[s][i], x, o, m))
        res["LAB-K3-a"] = nmse_by_window(task, test, train, masks, a.n_roi,
                                         lambda s, i, x, o, m: M.predict_adaptive(labfit, x, o, m, tau)[0])
        if em.status == "ok":
            res["EM-K3-true"] = nmse_by_window(task, test, train, masks, a.n_roi,
                                               lambda s, i, x, o, m: cond_k(em, emap[ts[s][i]], x, o, m))
        for b in cfg["best_candidates"]:
            res[b] = t1.subject_nmse(task, test, train, masks, a.n_roi, t1._baseline(b, rest, train))
        # 참 상태별 ridge (λ 는 test 기준 최선 — oracle 진단)
        frames_lab = {j: [s_w for s in train for s_w, st in zip(rest[s], rs[s]) if st == j] for j in range(a.n_states)}
        best_lr = None
        for lam in (100.0, 10.0, 1.0, 0.1, 0.01):
            cache = {}

            def pr(s, i, x, o, m, lam=lam, cache=cache):
                key = (tuple(m), ts[s][i])
                if key not in cache:
                    W = frames_lab[ts[s][i]]
                    X = np.concatenate([w[:, o] for w in W])
                    Y = np.concatenate([w[:, m] for w in W])
                    cache[key] = R.fit_ridge(X, Y, lam, train)
                return cache[key].predict(x)
            v = nmse_by_window(task, test, train, masks, a.n_roi, pr)
            if best_lr is None or v.mean() < best_lr[1].mean():
                best_lr = (lam, v)
        res["LAB-RIDGE-true"] = best_lr[1]
        d["lab_ridge_lambda"] = best_lr[0]
        for m_, arr in res.items():
            for s, v in zip(test, arr):
                per.setdefault(m_, {})[s] = float(v)
        diag.append(d)
        print(f"fold {k} done {time.perf_counter() - t0:.0f}s", file=sys.stderr, flush=True)
    order = sorted(ids)
    mean = {m_: float(np.mean([per[m_][s] for s in order])) for m_ in per if len(per[m_]) == len(order)}
    out = {"schema": "r2t-t1-diag-0.1", "synthetic_only": True, "oracle_for_diagnosis_only": True, "decision": 88,
           "seed": a.seed, "n_roi": a.n_roi, "n_subjects": a.n_subjects, "n_states": a.n_states, "n_pop": a.n_pop,
           "mean_nmse": mean, "folds": diag, "seconds": time.perf_counter() - t0}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({"mean_nmse": mean, "folds": diag}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
