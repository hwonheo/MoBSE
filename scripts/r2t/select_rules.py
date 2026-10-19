"""R2T 선택 규칙 (결정 85, 계획서 v1.2 §4.4 · §5) — BEST · τ 를 train/inner 에서만 고르고 outer test 에 한 번 적용.

* MIX-p: 같은 혼합 성분을 합친 단일 공분산 Σ̄ = Σ π_k Σ_k 의 조건부 예측 (기전 보조용 비적응 기준).
* τ_ESS = (1 − ρ̂)/(1 + ρ̂), ρ̂ = train 처리 창의 lag-1 자기상관 평균 (train-only). 짧은 창 · 추세 제거로 ρ̂ 가 아래로 치우칠 수 있다.
* τ 후보 {0, τ_ESS, 1} — τ = 0 은 π 가중 비적응 혼합 (fallback, "적응 미선택").
* 선택: inner train 으로 적합 → inner val 피험자 task 창 평균 NMSE (분모는 inner train task 창) → 동률 (< tie) 이면 단순한 쪽.
  선택 뒤 outer train 전체로 다시 적합해 outer test 에 적용. test 자료는 선택 함수에 들어가지 않는다.
* 혼합 적합이 실패하면 결과에 "실패" 로 남기고 MIX 예측을 만들지 않는다 (G1 대체 없음).
`r2t_lib` · `mix` 는 바꾸지 않고 불러 쓴다.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

import mix as M
import r2t_lib as R

TIE = 1e-4
LAMBDAS = (100.0, 10.0, 1.0, 0.1, 0.01)        # 큰 λ (단순) 부터 — 동률이면 앞쪽


# ---------------------------------------------------------------- 보조 모델 · τ_ESS

def pooled_prior(fit: M.MixFit) -> R.GaussPrior:
    """MIX-p — 성분 공분산의 π 가중 합 (평균 0)."""
    M._require_ok(fit)
    cov = np.tensordot(fit.pis, fit.covs, axes=1)
    return R.GaussPrior(mu=np.zeros(cov.shape[0]), cov=cov, shrinkage=float("nan"), method="mixp", fit_ids=fit.fit_ids)


def rho_hat(Xw: np.ndarray) -> float:
    """(N, L, p) train 처리 창 → ROI · 창 평균 lag-1 자기상관."""
    a, b = Xw[:, 1:, :], Xw[:, :-1, :]
    num = np.sum(a * b, axis=1)
    den = np.sqrt(np.sum(a * a, axis=1) * np.sum(b * b, axis=1))
    r = num[den > 0] / den[den > 0]
    return float(np.mean(r))


def tau_ess(Xw: np.ndarray) -> float:
    rho = float(np.clip(rho_hat(Xw), 0.0, 0.99))
    return (1 - rho) / (1 + rho)


# ---------------------------------------------------------------- 평가 도우미

Predict = Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def subject_nmse(task: Dict[str, List[np.ndarray]], eval_ids: Sequence[str], v_ids: Sequence[str],
                 masks: Sequence[np.ndarray], n_roi: int, make_pred: Callable[[np.ndarray, np.ndarray], Predict]
                 ) -> np.ndarray:
    """eval_ids 피험자별 NMSE. 분모 v 는 v_ids (train) task 창으로만. make_pred(obs, msk) → predict(x, obs, msk)."""
    R.check_disjoint(v_ids, eval_ids)
    per = {s: [] for s in eval_ids}
    for msk in masks:
        obs = np.setdiff1d(np.arange(n_roi), msk)
        v = R.train_target_variance(task, v_ids, obs, msk)
        pred = make_pred(obs, msk)
        for s in eval_ids:
            for win in task[s]:
                x, y = R.split_window(win, obs, msk)
                per[s].append(R.nmse_terms(y, pred(x, obs, msk), v).ravel())
    return np.array([np.mean(np.concatenate(per[s])) for s in eval_ids])


def _pick(scores: List[Tuple[str, float]], tie: float = TIE) -> str:
    """scores 는 단순한 순서로 정렬된 (이름, 점수). 최솟값과 tie 안이면 앞쪽 (단순한 쪽)."""
    best = min(sc for _, sc in scores)
    return next(name for name, sc in scores if sc <= best + tie)


# ---------------------------------------------------------------- BEST 후보

def _baseline_factory(name: str, rest, fit_ids):
    """후보 이름 → make_pred. G1 은 mask 와 무관하게 한 번 적합, RIDGE 는 mask 마다 적합."""
    if name in ("G1-LW", "G1-OAS"):
        g = R.fit_prior(R.stack_full(rest, fit_ids), "lw" if name == "G1-LW" else "oas", fit_ids)
        return lambda obs, msk: (lambda x, o, m: g.predict(x, o, m))
    lam = float(name.split("=")[1])

    def make(obs, msk):
        X, Y = R.stack_frames(rest, fit_ids, obs, msk)
        rg = R.fit_ridge(X, Y, lam, fit_ids)
        return lambda x, o, m: rg.predict(x)
    return make


BASELINES = ["G1-LW", "G1-OAS"] + [f"RIDGE λ={lam:g}" for lam in LAMBDAS]


def select_best(rest, task, inner_tr, inner_va, masks, n_roi) -> Tuple[str, List[Tuple[str, float]]]:
    scores = [(b, float(subject_nmse(task, inner_va, inner_tr, masks, n_roi,
                                     _baseline_factory(b, rest, inner_tr)).mean())) for b in BASELINES]
    return _pick(scores), scores


# ---------------------------------------------------------------- MIX τ 선택

def _mix_pred(fit: M.MixFit, tau: float):
    return lambda obs, msk: (lambda x, o, m: M.predict_adaptive(fit, x, o, m, tau=tau)[0])


def select_tau(rest, task, inner_tr, inner_va, masks, n_roi, K: int, fit_kw: dict) -> dict:
    Xw = M.windows_full(rest, inner_tr)
    fit = M.fit_mixture(Xw, K, inner_tr, **fit_kw)
    if fit.status != "ok":
        return {"status": "fit_failed", "reason": fit.reason, "tau": None, "scores": []}
    te = tau_ess(Xw)
    grid = [("0", 0.0), ("ess", te), ("1", 1.0)]                       # 작은 τ (단순) 부터
    scores = [(lab, float(subject_nmse(task, inner_va, inner_tr, masks, n_roi, _mix_pred(fit, t)).mean()))
              for lab, t in grid]
    lab = _pick(scores)
    return {"status": "ok", "tau_label": lab, "tau": dict(grid)[lab], "tau_ess": te, "scores": scores}


# ---------------------------------------------------------------- outer 한 판

def outer_run(rest, task, train: Sequence[str], test: Sequence[str], masks, n_roi: int, K: int = 3,
              inner_seed: int = 0, fit_kw: dict = None) -> dict:
    """train 안에서 BEST · τ 선택 → train 전체 재적합 → test 평가. 반환: 선택 기록 · 피험자별 NMSE."""
    fit_kw = dict(fit_kw or {})
    R.check_disjoint(train, test)
    inner_tr, inner_va = R.subject_split(train, 0.2, seed=inner_seed)
    best, best_scores = select_best(rest, task, inner_tr, inner_va, masks, n_roi)
    tsel = select_tau(rest, task, inner_tr, inner_va, masks, n_roi, K, fit_kw)
    out = {"best": best, "best_scores": best_scores, "tau_selection": tsel,
           "nmse": {"BEST": subject_nmse(task, test, train, masks, n_roi, _baseline_factory(best, rest, train))}}
    fit = M.fit_mixture(M.windows_full(rest, train), K, train, **fit_kw)
    out["mix_status"] = fit.status
    if fit.status != "ok" or tsel["status"] != "ok":
        out["mix"] = "실패"                                              # G1 로 대체하지 않는다
        return out
    mp = pooled_prior(fit)
    out["nmse"]["MIX-a"] = subject_nmse(task, test, train, masks, n_roi, _mix_pred(fit, tsel["tau"]))
    out["nmse"]["MIX-p"] = subject_nmse(task, test, train, masks, n_roi, lambda o, m: (lambda x, oo, mm: mp.predict(x, oo, mm)))
    out["nmse"]["MIX-f"] = subject_nmse(task, test, train, masks, n_roi,
                                        lambda o, m: (lambda x, oo, mm: M.predict_fixed(fit, x, oo, mm)))
    out["mix"] = "ok"
    out["adaptive_selected"] = tsel["tau"] > 0
    return out
