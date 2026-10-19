"""R2T T1 개선판 F1 (결정 88) — MIX 성분 조건부 예측에 예측 기준 정규화 λ 를 둔다. **합성 개발용.**

진단 (`docs/experiments/r2t_t1_synth_diagnosis_2026-10-17.md` §1): 100 ROI · 31 명 positive 의 손실은 군집 · 가중치가 아니라
성분 공분산 정규화 부족 (가중 LW 강도 약 0.015) 에서 왔다. BEST 의 ridge 는 λ 를 예측 오차로 고르는데 MIX 는 그럴 기회가 없었다.

F1 규칙 (사전 기록 §2):
* B_k = C_k,MO (C_k,OO + λ m_k I)⁻¹, m_k = tr(C_k)/p. λ 후보 = BEST ridge 와 같은 격자.
* EM 적합 · 성분 공분산 · 사후 가중치 (w ∝ π exp(τ ℓ), ℓ 은 λ 없는 C_k,OO 로) 는 `mix` 그대로.
* (λ, τ) 를 inner train 적합 → inner val 로 고르고 (동률이면 큰 λ · 작은 τ), fold train 재적합.
* MIX-p · MIX-f 도 같은 λ.
* BEST · 분할 · mask · 분모 · bootstrap · 판정은 `t1` 그대로 (불러 씀). `t1` · `mix` · 기존 설정은 바꾸지 않는다.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

import mix as M
import r2t_lib as R
import select_rules as SR
import t1


# ---------------------------------------------------------------- 정규화 조건부 예측 (mask 마다 계수 · Cholesky 를 한 번 계산)

def _coef(c: np.ndarray, obs, msk, lam: float) -> np.ndarray:
    m = np.trace(c) / c.shape[0]
    Coo = c[np.ix_(obs, obs)] + lam * m * np.eye(len(obs))
    return np.linalg.solve(Coo, c[np.ix_(msk, obs)].T).T


def make_mix_pred(fit: M.MixFit, lam: float, tau: float, weights: str = "adaptive"):
    """make_pred(obs, msk) → pred(x, o, m). weights: adaptive (MIX-a) · fixed (MIX-f, 1/K)."""
    M._require_ok(fit)

    def make(obs, msk):
        Bs = [_coef(c, obs, msk, lam) for c in fit.covs]
        if weights == "fixed":
            return lambda x, o, m: np.mean([x @ B.T for B in Bs], axis=0)
        chols = [np.linalg.cholesky(c[np.ix_(obs, obs)]) for c in fit.covs]
        logdets = [2 * np.sum(np.log(np.diag(L))) for L in chols]
        q = len(obs)

        def pred(x, o, m):
            ll = np.array([-0.5 * (x.shape[0] * (q * M.LOG2PI + ld) + np.sum(np.linalg.solve(L, x.T) ** 2))
                           for L, ld in zip(chols, logdets)])
            a = np.log(fit.pis) + tau * ll
            w = np.exp(a - M._logsumexp(a, 0))
            return np.tensordot(w, np.stack([x @ B.T for B in Bs]), axes=1)
        return pred
    return make


def make_pooled_pred(fit: M.MixFit, lam: float):
    cov = SR.pooled_prior(fit).cov

    def make(obs, msk):
        B = _coef(cov, obs, msk, lam)
        return lambda x, o, m: x @ B.T
    return make


def candidates(cfg, tau_ess: float):
    """(이름, λ, τ) — 단순한 순서 (큰 λ, 작은 τ 먼저)."""
    taus = [("0", 0.0), ("ess", tau_ess), ("1", 1.0)]
    assert [t[0] for t in taus] == cfg["mix"]["tau_candidates"]
    return [(f"λ={lam:g}|τ={lab}", float(lam), t) for lam in cfg["mix"]["cond_lambda_candidates"] for lab, t in taus]


# ---------------------------------------------------------------- fold 한 판 (t1.run_fold 와 같은 순서, MIX 쪽 선택만 다름)

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
    fi = M.fit_mixture(Xi, K, inner_tr, **kw)
    rec["inner_mix_status"] = fi.status
    if fi.status != "ok":
        rec.update(mix="실패", mix_reason=f"inner: {fi.reason}")
        return rec
    te = t1.tau_ess_t1(Xi)
    cands = candidates(cfg, te)
    scores = [(name, float(t1.subject_nmse(task, inner_va, inner_tr, masks, n_roi, make_mix_pred(fi, lam, tau)).mean()))
              for name, lam, tau in cands]
    pick = SR._pick(scores, tie)
    _, lam, tau = next(c for c in cands if c[0] == pick)
    rec.update(mix_pick=pick, lam=lam, tau=tau, tau_label=pick.split("τ=")[1], tau_ess=te, mix_scores=scores)
    f = M.fit_mixture(t1.t1_windows(rest, train), K, train, **kw)
    rec["mix_status"] = f.status
    if f.status != "ok":
        rec.update(mix="실패", mix_reason=f"train: {f.reason}")
        return rec
    rec["nmse"]["MIX-a"] = t1.subject_nmse(task, test, train, masks, n_roi, make_mix_pred(f, lam, tau))
    rec["nmse"]["MIX-p"] = t1.subject_nmse(task, test, train, masks, n_roi, make_pooled_pred(f, lam))
    rec["nmse"]["MIX-f"] = t1.subject_nmse(task, test, train, masks, n_roi, make_mix_pred(f, lam, 0.0, "fixed"))
    rec.update(mix="ok", pis=f.pis.tolist(), shrinkage=f.shrinkage.tolist())
    return rec


def run_pipeline(rest, task, subjects: Sequence[str], cfg: dict, left: np.ndarray) -> dict:
    """`t1.run_pipeline` 과 같은 집계 · 판정. fold 함수만 F1 판."""
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
    folds = [run_fold(rest, task, sorted(set(subjects) - set(test)), test, masks, n_roi, cfg, k)
             for k, test in enumerate(tests)]
    per = {}
    for r in folds:
        for m, arr in r["nmse"].items():
            for s, v in zip(r["test"], arr):
                per.setdefault(m, {})[s] = float(v)
    nonfinite = any(not np.isfinite(v) for d in per.values() for v in d.values())
    ok_subj = sorted(s for r in folds if r.get("mix") == "ok" for s in r["test"])
    delta_ci, d, aux = None, None, {}
    if ok_subj and not nonfinite:
        d = R.delta(np.array([per["BEST"][s] for s in ok_subj]), np.array([per["MIX-a"][s] for s in ok_subj]))
        delta_ci = R.subject_bootstrap(d, cfg["bootstrap"]["n"], seed=cfg["bootstrap"]["seed"])
        for a, b in (("MIX-a", "MIX-p"), ("MIX-a", "MIX-f"), ("MIX-p", "BEST")):
            dd = R.delta(np.array([per[b][s] for s in ok_subj]), np.array([per[a][s] for s in ok_subj]))
            aux[f"{a} 대 {b}"] = R.subject_bootstrap(dd, cfg["bootstrap"]["n"], seed=cfg["bootstrap"]["seed"])
    out = {"n_subjects": len(subjects), "n_ok_subjects": len(ok_subj), "masks": [m.tolist() for m in masks],
           "per_subject_nmse": per, "delta_best_minus_mixa": delta_ci,
           "delta_sd": float(np.std(d, ddof=1)) if delta_ci else None, "aux": aux,
           "folds": [{k: v for k, v in r.items() if k != "nmse"} for r in folds],
           "delta_report_only": cfg["delta_report_only"]}
    out["verdict"] = t1.verdict(folds, delta_ci, nonfinite, cfg)
    return out
