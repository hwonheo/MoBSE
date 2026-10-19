"""R2T T1 개선판 F3 (결정 88) — F2 + 가중치 단위 h 선택. **합성 개발용.**

근거 (`docs/experiments/r2t_t1_synth_diagnosis_2026-10-17.md` 12 절): 상태가 창 안에서 바뀌면 창 전체를 한 상태로 보는 가중치가
병목이다. frame 주변 h frame 의 관측 우도로 frame 마다 가중치를 정하면 oracle 수준에 닿았다 (prototype).

F3 규칙 (사전 기록 12.3):
* w_t ∝ π exp(τ Σ_{u ∈ 창, |u − t| ≤ (h − 1)/2} ℓ_k(x_u)). h 후보 = 창 전체 (F2 와 같음) · 5 · 3 · 1, 동률이면 앞쪽.
* (EM a, λ, τ, h) 240 조합을 inner val 로 선택. 나머지는 F2 (`t1_reg2`) 와 같다. 창 밖 frame · 가린 값은 쓰지 않는다.

실패 처리 (사전 기록 14 절, 검증 전 확정):
* inner 의 모든 a 후보 실패 또는 선택 a 의 fold train 재적합 실패 → 그 fold test 사람의 F3 예측 = 그 fold 의 BEST 예측 (fallback).
* 주지표는 모든 fold · 모든 사람 (fallback 포함). 성공 fold 한정 Δ 는 참고로 따로. 실패 · fallback 수를 따로 보고.
"""
from __future__ import annotations

import numpy as np

import mix as M
import r2t_lib as R
import select_rules as SR
import t1
import t1_reg as F1
import t1_reg2 as F2

WINDOW = "win"


def _window_sum(lf: np.ndarray, h) -> np.ndarray:
    """(L, K) frame 로그우도 → (L, K) frame 별 합 (창 전체 또는 창 안 주변 h)."""
    if h == WINDOW:
        return np.broadcast_to(lf.sum(0), lf.shape)
    c = np.cumsum(np.vstack([np.zeros((1, lf.shape[1])), lf]), 0)
    L, r = lf.shape[0], (int(h) - 1) // 2
    lo, hi = np.clip(np.arange(L) - r, 0, L), np.clip(np.arange(L) + r + 1, 0, L)
    return c[hi] - c[lo]


def make_mix_pred_h(fit: M.MixFit, lam: float, tau: float, h):
    M._require_ok(fit)

    def make(obs, msk):
        Bs = [F1._coef(c, obs, msk, lam) for c in fit.covs]
        chols = [np.linalg.cholesky(c[np.ix_(obs, obs)]) for c in fit.covs]
        logdets = [2 * np.sum(np.log(np.diag(L))) for L in chols]
        q = len(obs)

        def pred(x, o, m):
            lf = np.stack([-0.5 * (q * M.LOG2PI + ld + np.sum(np.linalg.solve(L, x.T) ** 2, axis=0))
                           for L, ld in zip(chols, logdets)], 1)                      # (L, K)
            a = np.log(fit.pis)[None, :] + tau * _window_sum(lf, h)
            w = np.exp(a - M._logsumexp(a, 1)[:, None])
            P = np.stack([x @ B.T for B in Bs])                                       # (K, L, |M|)
            return np.einsum("lk,klm->lm", w, P)
        return pred
    return make


def h_candidates(cfg):
    return [WINDOW if h == "window" else int(h) for h in cfg["mix"]["weight_unit_candidates"]]


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
        fi = F2.fit_mixture_a(Xi, K, inner_tr, a, **kw)
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
    f = F2.fit_mixture_a(t1.t1_windows(rest, train), K, train, a, **kw)
    rec["mix_status"] = f.status
    if f.status != "ok":
        rec.update(mix="실패", mix_reason=f"train: {f.reason}")
        return _fallback(rec)
    rec["nmse"]["F3"] = rec["nmse"]["MIX-a"] = t1.subject_nmse(task, test, train, masks, n_roi, make_mix_pred_h(f, lam, tau, h))
    rec["nmse"]["MIX-p"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_pooled_pred(f, lam))
    rec["nmse"]["MIX-f"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_mix_pred(f, lam, 0.0, "fixed"))
    rec.update(mix="ok", fallback=False, pis=f.pis.tolist(), shrinkage=f.shrinkage.tolist())
    return rec


def _fallback(rec: dict) -> dict:
    """사전 지정 fallback — 그 fold test 사람의 F3 예측은 같은 fold BEST 예측 (NMSE 도 같음). MIX-a 는 만들지 않는다."""
    rec["nmse"]["F3"] = np.array(rec["nmse"]["BEST"], copy=True)
    rec["fallback"] = True
    return rec


# ---------------------------------------------------------------- 집계 · 판정 (모든 사람 분모)

def verdict3(folds, d_all_ci, nonfinite: bool) -> dict:
    fails = sum(1 for r in folds if r.get("mix") != "ok")
    flags = []
    if nonfinite:
        flags.append("중단: 비유한 예측")
    if fails:
        flags.append(f"혼합 실패 fold {fails}/{len(folds)} → BEST fallback (사전 규칙)")
    if d_all_ci is not None and d_all_ci[2] < 0:
        flags.append("K>1 경로 중단 권고: Δ 상한 < 0")
    ok = [r for r in folds if r.get("mix") == "ok"]
    if ok and all(r["tau"] == 0.0 for r in ok):
        flags.append("적응 경로 중단 권고: 성공 fold 모두 τ̂ = 0")
    stop = any(f.startswith("중단") for f in flags)
    return {"flags": flags, "stop": stop, "mix_fail_folds": fails,
            "next": "중단 · 보고" if stop else "기술값 보고"}


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
