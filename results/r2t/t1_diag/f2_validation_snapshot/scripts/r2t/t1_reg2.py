"""R2T T1 개선판 F2 (결정 88) — F1 + EM M-step shrinkage 를 예측 기준으로 선택. **합성 개발용.**

근거 (`docs/experiments/r2t_t1_synth_diagnosis_2026-10-17.md` 6.3 · 7 절): 상태 분리도가 낮으면 (sep 0.3) 병목이 EM 군집으로
옮겨 간다. EM 성분 공분산을 단위행렬 쪽으로 강하게 당기면 군집이 나아졌다 (prototype).

F2 규칙 (사전 기록 7 절):
* EM M-step 성분 공분산 = a m I + (1 − a) S_k. a 후보 = LW (현행 `mix`) · 0.091 · 0.5 · 0.909 (λ/(1+λ), λ ∈ {0.1, 1, 10}).
* a 마다 inner train EM → F1 (λ, τ) 15 조합 → 60 조합을 inner val NMSE 로 선택, 동률이면 앞쪽. 선택 a 로 fold train 재적합.
* EM 의 나머지 규칙 (k-means++ 초기화 · n_init · 수렴 · 점유율 · 고유값 하한 · 실패 처리) 은 `mix` 와 같다 — a = LW 는 `mix.fit_mixture` 그대로 부른다.
* 사후 가중치 · 조건부 예측 · BEST · 집계 · 판정은 F1 (`t1_reg`) 과 같다.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

import mix as M
import r2t_lib as R
import select_rules as SR
import t1
import t1_reg as F1


# ---------------------------------------------------------------- 고정 shrinkage EM (`mix._one_run` 과 같은 순서, M-step 만 다름)

def _m_step_fixed(Xw: np.ndarray, resp: np.ndarray, a: float, eig_floor: float):
    N, L, p = Xw.shape
    X = Xw.reshape(N * L, p)
    covs = []
    for k in range(resp.shape[1]):
        w = np.repeat(resp[:, k], L)
        W = w.sum()
        if W <= 0:
            raise FloatingPointError("가중치 합이 0")
        S = (X * w[:, None]).T @ X / W
        m = np.trace(S) / p
        C = a * m * np.eye(p) + (1 - a) * S
        ev, V = np.linalg.eigh(C)
        floor = eig_floor * max(m, 1e-12)
        if ev.min() < floor:
            C = (V * np.maximum(ev, floor)) @ V.T
        covs.append(C)
    return np.stack(covs), resp.sum(0) / N, np.full(resp.shape[1], a)


def _one_run_fixed(Xw, K, seed, max_iter, tol, min_occupancy, eig_floor, a) -> M.MixFit:
    N = len(Xw)
    try:
        resp = M._init_resp(Xw, K, seed) if K > 1 else np.ones((N, 1))
        prev, converged, it = -np.inf, False, 0
        for it in range(1, max_iter + 1):
            if np.any(resp.sum(0) < min_occupancy * N):
                covs, pis, shr = _m_step_fixed(Xw, np.maximum(resp, 1e-300), a, eig_floor)
                return M.MixFit(K, covs, pis, prev, it, False, "sparse_component",
                                f"성분 점유율 {np.round(resp.sum(0) / N, 3).tolist()} < {min_occupancy}", resp.sum(0) / N, shr)
            covs, pis, shr = _m_step_fixed(Xw, resp, a, eig_floor)
            ll = M.window_loglik(Xw, covs) + np.log(pis)
            tot = float(M._logsumexp(ll, 1).sum())
            resp = np.exp(ll - M._logsumexp(ll, 1)[:, None])
            if K == 1 or abs(tot - prev) <= tol * abs(tot):
                converged, prev = True, tot
                break
            prev = tot
        occ = resp.sum(0) / N
        if np.any(occ < min_occupancy):
            return M.MixFit(K, covs, pis, prev, it, converged, "sparse_component",
                            f"최종 점유율 {np.round(occ, 3).tolist()} < {min_occupancy}", occ, shr)
        if not converged:
            return M.MixFit(K, covs, pis, prev, it, False, "not_converged", f"{max_iter} 회 안에 수렴 안 함", occ, shr)
        covs, pis, shr = _m_step_fixed(Xw, resp, a, eig_floor)
        return M.MixFit(K, covs, pis, prev, it, True, "ok", "", occ, shr)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError) as e:
        return M.MixFit(K, np.empty((0,)), np.empty((0,)), -np.inf, 0, False, "numerical", repr(e), np.empty((0,)), np.empty((0,)))


def fit_mixture_a(Xw: np.ndarray, K: int, fit_ids: Sequence[str], a: Optional[float], *, seed=0, n_init=10, max_iter=500,
                  tol=1e-6, min_occupancy=0.05, eig_floor=1e-6) -> M.MixFit:
    """a = None 이면 `mix.fit_mixture` (가중 LW) 그대로. 아니면 고정 shrinkage a."""
    if a is None:
        return M.fit_mixture(Xw, K, fit_ids, seed=seed, n_init=n_init, max_iter=max_iter, tol=tol,
                             min_occupancy=min_occupancy, eig_floor=eig_floor)
    runs = [_one_run_fixed(Xw, K, seed + i, max_iter, tol, min_occupancy, eig_floor, a) for i in range(n_init if K > 1 else 1)]
    log = [{"seed": seed + i, "status": r.status, "loglik": r.loglik, "n_iter": r.n_iter} for i, r in enumerate(runs)]
    ok = [r for r in runs if r.status == "ok"]
    if not ok:
        r = runs[0]
        return M.MixFit(K, r.covs, r.pis, r.loglik, r.n_iter, False, "all_failed", "; ".join(sorted({x.status for x in runs})),
                        r.occupancy, r.shrinkage, tuple(sorted(fit_ids)), log)
    best = max(ok, key=lambda r: r.loglik)
    best.fit_ids, best.restarts = tuple(sorted(fit_ids)), log
    return best


def em_candidates(cfg):
    """(이름, a) — 앞쪽이 단순 (현행 LW 먼저)."""
    return [("LW", None)] + [(f"{x:.3f}", float(x)) for x in cfg["mix"]["em_shrink_candidates"]]


# ---------------------------------------------------------------- fold 한 판

def run_fold(rest, task, train, test, masks, n_roi: int, cfg: dict, fold: int) -> dict:
    R.check_disjoint(train, test)
    tie = cfg["selection"]["tie"]
    inner_tr, inner_va = R.subject_split(train, cfg["split"]["inner_val_frac"], seed=cfg["split"]["inner_seed"])
    best_scores = [(b, float(t1.subject_nmse(task, inner_va, inner_tr, masks, n_roi, t1._baseline(b, rest, inner_tr)).mean()))
                   for b in cfg["best_candidates"]]
    best = SR._pick(best_scores, tie)
    rec = {"fold": fold, "train": list(train), "test": list(test), "inner_train": inner_tr, "inner_val": inner_va,
           "best": best, "best_scores": best_scores,
           "nmse": {"BEST": t1.subject_nmse(task, test, train, masks, n_roi, t1._baseline(best, rest, train))}}
    K, kw = cfg["mix"]["K"], t1._fit_kw(cfg)
    Xi = t1.t1_windows(rest, inner_tr)
    te = t1.tau_ess_t1(Xi)
    cands, scores, inner_status = [], [], {}
    for en, a in em_candidates(cfg):
        fi = fit_mixture_a(Xi, K, inner_tr, a, **kw)
        inner_status[en] = fi.status
        if fi.status != "ok":
            continue                                   # 그 a 는 후보에서 빠진다 (실패로 기록)
        for name, lam, tau in F1.candidates(cfg, te):
            full = f"a={en}|{name}"
            cands.append((full, a, lam, tau))
            scores.append((full, float(t1.subject_nmse(task, inner_va, inner_tr, masks, n_roi, F1.make_mix_pred(fi, lam, tau)).mean())))
    rec["inner_mix_status"] = inner_status
    if not scores:
        rec.update(mix="실패", mix_reason="inner: 모든 a 에서 혼합 적합 실패")
        return rec
    pick = SR._pick(scores, tie)
    _, a, lam, tau = next(c for c in cands if c[0] == pick)
    rec.update(mix_pick=pick, em_a=a, lam=lam, tau=tau, tau_label=pick.split("τ=")[1], tau_ess=te, mix_scores=scores)
    f = fit_mixture_a(t1.t1_windows(rest, train), K, train, a, **kw)
    rec["mix_status"] = f.status
    if f.status != "ok":
        rec.update(mix="실패", mix_reason=f"train: {f.reason}")
        return rec
    rec["nmse"]["MIX-a"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_mix_pred(f, lam, tau))
    rec["nmse"]["MIX-p"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_pooled_pred(f, lam))
    rec["nmse"]["MIX-f"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_mix_pred(f, lam, 0.0, "fixed"))
    rec.update(mix="ok", pis=f.pis.tolist(), shrinkage=f.shrinkage.tolist())
    return rec


def run_pipeline(rest, task, subjects, cfg, left):
    """F1 집계 · 판정을 그대로 쓰되 fold 함수만 F2."""
    orig = F1.run_fold
    try:
        F1.run_fold = run_fold                         # F1.run_pipeline 이 모듈 전역 run_fold 를 부른다
        return F1.run_pipeline(rest, task, subjects, cfg, left)
    finally:
        F1.run_fold = orig
