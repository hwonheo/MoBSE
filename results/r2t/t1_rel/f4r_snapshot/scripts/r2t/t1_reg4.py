"""R2T T1 개선판 F4 (결정 88) — F3 + EM 초기화 수정. **합성 개발용.**

근거 (`docs/experiments/r2t_t1_synth_diagnosis_2026-10-17.md` 17 절): 어려운 세계의 혼합 실패는 k-means++ 초기화 (5,050 차원
산포 특징) 가 이상치 창으로 아주 작은 군집을 만들어 반복 1 회째 점유율 검사에서 실패한 것이었다.

F4 규칙 (사전 기록 17.3):
* k-means 특징 = 창 산포행렬 상삼각 → 열 표준화 (적합 자료 안) → SVD 상위 20 주성분 점수. k-means++ · seed 는 그대로.
* 점유율 검사는 최종 해에서만 (반복 중 생략). 최종 점유율 < min_occupancy 면 sparse_component 실패.
* EM M-step (a = LW 는 `mix._m_step`, 고정 a 는 `t1_reg2._m_step_fixed`) · 수렴 · 재시작 · 고유값 하한은 그대로.
* 그 밖 (후보 · 선택 · fallback · 31 명 분모 · 판정) 은 F3 (`t1_reg3`) 와 같다. `t1_reg3` 는 바꾸지 않는다.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

import mix as M
import r2t_lib as R
import select_rules as SR
import t1
import t1_reg as F1
import t1_reg2 as F2
from t1_reg3 import WINDOW, _fallback, h_candidates, make_mix_pred_h, verdict3  # noqa: F401

N_PC = 20


def init_resp_pca(Xw: np.ndarray, K: int, seed: int, n_pc: int = N_PC) -> np.ndarray:
    from sklearn.cluster import KMeans

    N, L, p = Xw.shape
    iu = np.triu_indices(p)
    F = np.stack([(x.T @ x / L)[iu] for x in Xw])
    F = (F - F.mean(0)) / np.where(F.std(0) < 1e-12, 1.0, F.std(0))
    U, s, _ = np.linalg.svd(F, full_matrices=False)
    Z = U[:, :n_pc] * s[:n_pc]
    lab = KMeans(n_clusters=K, init="k-means++", n_init=1, random_state=seed).fit_predict(Z)
    return np.eye(K)[lab]


def _m(Xw, resp, a, eig_floor):
    return M._m_step(Xw, resp, eig_floor) if a is None else F2._m_step_fixed(Xw, resp, a, eig_floor)


def _one_run4(Xw, K, seed, max_iter, tol, min_occupancy, eig_floor, a) -> M.MixFit:
    N = len(Xw)
    try:
        resp = init_resp_pca(Xw, K, seed) if K > 1 else np.ones((N, 1))
        prev, converged, it = -np.inf, False, 0
        for it in range(1, max_iter + 1):
            covs, pis, shr = _m(Xw, np.maximum(resp, 1e-300), a, eig_floor)
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
        covs, pis, shr = _m(Xw, resp, a, eig_floor)
        return M.MixFit(K, covs, pis, prev, it, True, "ok", "", occ, shr)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError) as e:
        return M.MixFit(K, np.empty((0,)), np.empty((0,)), -np.inf, 0, False, "numerical", repr(e), np.empty((0,)), np.empty((0,)))


def fit_mixture4(Xw: np.ndarray, K: int, fit_ids: Sequence[str], a: Optional[float], *, seed=0, n_init=10, max_iter=500,
                 tol=1e-6, min_occupancy=0.05, eig_floor=1e-6) -> M.MixFit:
    runs = [_one_run4(Xw, K, seed + i, max_iter, tol, min_occupancy, eig_floor, a) for i in range(n_init if K > 1 else 1)]
    log = [{"seed": seed + i, "status": r.status, "loglik": r.loglik, "n_iter": r.n_iter} for i, r in enumerate(runs)]
    ok = [r for r in runs if r.status == "ok"]
    if not ok:
        r = runs[0]
        return M.MixFit(K, r.covs, r.pis, r.loglik, r.n_iter, False, "all_failed", "; ".join(sorted({x.status for x in runs})),
                        r.occupancy, r.shrinkage, tuple(sorted(fit_ids)), log)
    best = max(ok, key=lambda r: r.loglik)
    best.fit_ids, best.restarts = tuple(sorted(fit_ids)), log
    return best


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
    for en, a in F2.em_candidates(cfg):
        fi = fit_mixture4(Xi, K, inner_tr, a, **kw)
        inner_status[en] = fi.status
        if fi.status != "ok":
            continue
        for name, lam, tau in F1.candidates(cfg, te):
            for h in h_candidates(cfg):
                full = f"a={en}|{name}|h={h}"
                cands.append((full, a, lam, tau, h))
                scores.append((full, float(t1.subject_nmse(task, inner_va, inner_tr, masks, n_roi,
                                                            make_mix_pred_h(fi, lam, tau, h)).mean())))
    rec["inner_mix_status"] = inner_status
    rec["inner_failed_a"] = sum(v != "ok" for v in inner_status.values())
    if not scores:
        rec.update(mix="실패", mix_reason="inner: 모든 a 에서 혼합 적합 실패")
        return _fallback(rec)
    pick = SR._pick(scores, tie)
    _, a, lam, tau, h = next(c for c in cands if c[0] == pick)
    rec.update(mix_pick=pick, em_a=a, lam=lam, tau=tau, h=h, tau_label=pick.split("τ=")[1].split("|")[0], tau_ess=te,
               mix_scores=scores)
    f = fit_mixture4(t1.t1_windows(rest, train), K, train, a, **kw)
    rec["mix_status"] = f.status
    if f.status != "ok":
        rec.update(mix="실패", mix_reason=f"train: {f.reason}")
        return _fallback(rec)
    rec["nmse"]["F3"] = rec["nmse"]["MIX-a"] = t1.subject_nmse(task, test, train, masks, n_roi, make_mix_pred_h(f, lam, tau, h))
    rec["nmse"]["MIX-p"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_pooled_pred(f, lam))
    rec["nmse"]["MIX-f"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_mix_pred(f, lam, 0.0, "fixed"))
    rec.update(mix="ok", fallback=False, pis=f.pis.tolist(), shrinkage=f.shrinkage.tolist())
    return rec



def run_pipeline(rest, task, subjects, cfg, left) -> dict:
    n_roi = len(left)
    bad = sorted({s for d in (rest, task) for s in subjects for w in d[s] if not np.all(np.isfinite(w))})
    if bad:
        return {"n_subjects": len(subjects), "nonfinite_input_subjects": len(bad),
                "verdict": {"flags": ["중단: 비유한 입력"], "stop": True, "mix_fail_folds": None, "next": "중단 · 보고"}}
    masks = R.make_masks(n_roi, cfg["mask"]["frac"], cfg["mask"]["n_masks"], seed=cfg["mask"]["seed"], left=left)
    tests = t1.person_folds(subjects, cfg["split"]["n_folds"], cfg["split"]["fold_seed"])
    seen = sorted(s for t in tests for s in t)
    if seen != sorted(subjects) or len(seen) != len(set(seen)):
        raise R.LeakError("각 사람이 정확히 한 번 test 에 들어가지 않는다")
    folds = [run_fold(rest, task, sorted(set(subjects) - set(test)), test, masks, n_roi, cfg, k) for k, test in enumerate(tests)]
    per = {}
    for r in folds:
        for m, arr in r["nmse"].items():
            for s, v in zip(r["test"], arr):
                per.setdefault(m, {})[s] = float(v)
    allp = sorted(subjects)
    nonfinite = any(not np.isfinite(v) for d in per.values() for v in d.values())
    okp = sorted(s for r in folds if r.get("mix") == "ok" for s in r["test"])
    B, nb = cfg["bootstrap"]["seed"], cfg["bootstrap"]["n"]
    d_all = d_ok = None
    aux = {}
    if not nonfinite:
        d_all = R.delta(np.array([per["BEST"][s] for s in allp]), np.array([per["F3"][s] for s in allp]))
        if okp:
            d_ok = R.delta(np.array([per["BEST"][s] for s in okp]), np.array([per["MIX-a"][s] for s in okp]))
            for a, b in (("MIX-a", "MIX-p"), ("MIX-a", "MIX-f"), ("MIX-p", "BEST")):
                dd = R.delta(np.array([per[b][s] for s in okp]), np.array([per[a][s] for s in okp]))
                aux[f"{a} 대 {b} (성공 fold 한정)"] = R.subject_bootstrap(dd, nb, seed=B)
    ci_all = R.subject_bootstrap(d_all, nb, seed=B) if d_all is not None else None
    out = {"n_subjects": len(subjects), "n_ok_subjects": len(okp), "n_fallback_subjects": len(allp) - len(okp),
           "mix_fail_folds": sum(r.get("mix") != "ok" for r in folds),
           "inner_failed_a_total": sum(r.get("inner_failed_a", 0) for r in folds),
           "masks": [m.tolist() for m in masks], "per_subject_nmse": per,
           "delta_best_minus_f3_all": ci_all, "delta_sd_all": float(np.std(d_all, ddof=1)) if d_all is not None else None,
           "delta_best_minus_mixa_okfolds_reference": R.subject_bootstrap(d_ok, nb, seed=B) if d_ok is not None else None,
           "aux": aux, "folds": [{k: v for k, v in r.items() if k != "nmse"} for r in folds],
           "delta_report_only": cfg["delta_report_only"]}
    out["delta_best_minus_mixa"] = ci_all                     # 평가 스크립트 호환 — 주지표 (모든 사람, fallback 포함)
    out["verdict"] = verdict3(folds, ci_all, nonfinite)
    return out
