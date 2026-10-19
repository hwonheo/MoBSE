"""R2T 상태 혼합 최소 구현 (결정 84) — 합성 자료 검증용. 실제 자료에 쓰지 않았다.

계획서 v1.1 §3 · §4.4 의 MIX-f (고정 1/K) · MIX-a (관측만으로 정한 사후 가중치) 를 단계 0 규칙 (`r2t_lib`) 위에 얹는다.

설계 선택 (모두 잠금 전 제안값이며 결과를 보고 조정하지 않았다):

* 처리 신호는 창마다 평균 · 선형 추세를 지우므로 성분 평균은 0 으로 고정한다 — 상태는 **공분산으로만** 구별한다.
* EM 단위는 창 (15 frame 등). 창 안 frame 을 독립으로 보고 우도를 더한다 — 자기상관을 무시한 근사이며, 이 때문에
  사후 가중치가 과신될 수 있다 (τ 로 완화할 수 있게 둠; τ 는 여기서 고르지 않는다).
* 성분 공분산 = 책임도 가중 산포행렬에 Ledoit-Wolf 식 shrinkage (평균 0 가정 판) + 최소 고유값 하한.
* 초기화: 창 산포행렬 상삼각을 특징으로 k-means++ (seed 고정) 로 hard 책임도, n_init 회 중 로그우도 최대 판.
* 실패: 미수렴 · 성분 점유율 미달 (희박 · collapse) · 수치 오류는 status 로 기록하고, 예측 함수는 실패한 적합을 거부한다
  (G1 로 몰래 대체하지 않는다).
* 정보 접근: 적합은 train 창만, 예측은 창의 관측 열 `x_obs` 만 받는다. 정답 상태 · 가린 값 · 창 밖 frame 은 인자로 들어올 길이 없다.
  창 안의 뒤 frame 은 창 단위 처리 (추세 제거) 와 가중치 계산에 쓰인다 — 창이 관측 단위이기 때문이며, "미래 정보" 는 창 밖
  이후 frame 으로 정의한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np

import r2t_lib as R

LOG2PI = float(np.log(2 * np.pi))


# ---------------------------------------------------------------- 훈련 창

def windows_full(windows: Dict[str, List[np.ndarray]], ids: Sequence[str]) -> np.ndarray:
    """train 창 → (N, L, p) W-local 처리 신호 (g = 전 ROI, train 은 모두 관측)."""
    return np.stack([R._local(w, R.grand_mean(w)) for s in ids for w in windows[s]])


# ---------------------------------------------------------------- 가중 Ledoit-Wolf (평균 0)

def weighted_lw(X: np.ndarray, w: np.ndarray, eig_floor: float = 1e-6) -> Tuple[np.ndarray, float]:
    """X (n, p) · 가중치 w (n,) → (shrinkage 공분산, 강도). 같은 가중치면 sklearn LedoitWolf(assume_centered) 와 같다."""
    w = np.asarray(w, float)
    W = w.sum()
    if W <= 0:
        raise FloatingPointError("가중치 합이 0")
    p = X.shape[1]
    S = (X * w[:, None]).T @ X / W
    m = np.trace(S) / p
    d2 = np.sum((S - m * np.eye(p)) ** 2)
    xx = np.einsum("ij,ij->i", X, X)
    xSx = np.einsum("ij,jk,ik->i", X, S, X)
    b2bar = np.sum(w ** 2 * (xx ** 2 - 2 * xSx + np.sum(S ** 2))) / W ** 2
    b2 = min(b2bar, d2)
    a = 1.0 if d2 <= 0 else b2 / d2
    C = a * m * np.eye(p) + (1 - a) * S
    ev, V = np.linalg.eigh(C)
    floor = eig_floor * max(m, 1e-12)
    if ev.min() < floor:
        C = (V * np.maximum(ev, floor)) @ V.T
    return C, float(a)


# ---------------------------------------------------------------- 우도

def frame_logpdf(X: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """(…, q) 의 각 frame 에 대해 log N(x | 0, cov)."""
    c = np.linalg.cholesky(cov)
    z = np.linalg.solve(c, X.reshape(-1, X.shape[-1]).T)
    logdet = 2 * np.sum(np.log(np.diag(c)))
    out = -0.5 * (X.shape[-1] * LOG2PI + logdet + np.sum(z ** 2, axis=0))
    return out.reshape(X.shape[:-1])


def window_loglik(Xw: np.ndarray, covs: np.ndarray) -> np.ndarray:
    """(N, L, q) · (K, q, q) → (N, K) 창 로그우도 (frame 독립 근사)."""
    return np.stack([frame_logpdf(Xw, c).sum(axis=1) for c in covs], axis=1)


def _logsumexp(a: np.ndarray, axis: int) -> np.ndarray:
    m = a.max(axis=axis, keepdims=True)
    return (m + np.log(np.exp(a - m).sum(axis=axis, keepdims=True))).squeeze(axis)


# ---------------------------------------------------------------- 적합

@dataclass
class MixFit:
    K: int
    covs: np.ndarray
    pis: np.ndarray
    loglik: float
    n_iter: int
    converged: bool
    status: str                      # ok · not_converged · sparse_component · numerical · all_failed
    reason: str
    occupancy: np.ndarray
    shrinkage: np.ndarray
    fit_ids: Tuple[str, ...] = field(default_factory=tuple)
    restarts: List[dict] = field(default_factory=list)


def _m_step(Xw: np.ndarray, resp: np.ndarray, eig_floor: float):
    N, L, p = Xw.shape
    X = Xw.reshape(N * L, p)
    covs, shr = [], []
    for k in range(resp.shape[1]):
        c, a = weighted_lw(X, np.repeat(resp[:, k], L), eig_floor)
        covs.append(c)
        shr.append(a)
    return np.stack(covs), resp.sum(0) / N, np.array(shr)


def _init_resp(Xw: np.ndarray, K: int, seed: int) -> np.ndarray:
    from sklearn.cluster import KMeans

    N, L, p = Xw.shape
    iu = np.triu_indices(p)
    feats = np.stack([(x.T @ x / L)[iu] for x in Xw])
    lab = KMeans(n_clusters=K, init="k-means++", n_init=1, random_state=seed).fit_predict(feats)
    return np.eye(K)[lab]


def _one_run(Xw, K, seed, max_iter, tol, min_occupancy, eig_floor) -> MixFit:
    N = len(Xw)
    try:
        resp = _init_resp(Xw, K, seed) if K > 1 else np.ones((N, 1))
        prev = -np.inf
        converged = False
        it = 0
        for it in range(1, max_iter + 1):
            if np.any(resp.sum(0) < min_occupancy * N):
                covs, pis, shr = _m_step(Xw, np.maximum(resp, 1e-300), eig_floor)
                return MixFit(K, covs, pis, prev, it, False, "sparse_component",
                              f"성분 점유율 {np.round(resp.sum(0) / N, 3).tolist()} < {min_occupancy}",
                              resp.sum(0) / N, shr)
            covs, pis, shr = _m_step(Xw, resp, eig_floor)
            ll = window_loglik(Xw, covs) + np.log(pis)
            tot = float(_logsumexp(ll, 1).sum())
            resp = np.exp(ll - _logsumexp(ll, 1)[:, None])
            if K == 1 or abs(tot - prev) <= tol * abs(tot):
                converged = True
                prev = tot
                break
            prev = tot
        occ = resp.sum(0) / N
        if np.any(occ < min_occupancy):
            return MixFit(K, covs, pis, prev, it, converged, "sparse_component",
                          f"최종 점유율 {np.round(occ, 3).tolist()} < {min_occupancy}", occ, shr)
        if not converged:
            return MixFit(K, covs, pis, prev, it, False, "not_converged", f"{max_iter} 회 안에 수렴 안 함", occ, shr)
        covs, pis, shr = _m_step(Xw, resp, eig_floor)      # 최종 책임도에 맞춘 성분
        return MixFit(K, covs, pis, prev, it, True, "ok", "", occ, shr)
    except (np.linalg.LinAlgError, FloatingPointError, ValueError) as e:
        return MixFit(K, np.empty((0,)), np.empty((0,)), -np.inf, 0, False, "numerical", repr(e),
                      np.empty((0,)), np.empty((0,)))


def fit_mixture(Xw: np.ndarray, K: int, fit_ids: Sequence[str], *, seed: int = 0, n_init: int = 10,
                max_iter: int = 500, tol: float = 1e-6, min_occupancy: float = 0.05,
                eig_floor: float = 1e-6) -> MixFit:
    """train 창 (N, L, p) 로 K 성분 혼합. 성공한 재시작 중 로그우도 최대 판, 하나도 없으면 status all_failed."""
    runs = [_one_run(Xw, K, seed + i, max_iter, tol, min_occupancy, eig_floor) for i in range(n_init if K > 1 else 1)]
    log = [{"seed": seed + i, "status": r.status, "loglik": r.loglik, "n_iter": r.n_iter} for i, r in enumerate(runs)]
    ok = [r for r in runs if r.status == "ok"]
    if not ok:
        r = runs[0]
        return MixFit(K, r.covs, r.pis, r.loglik, r.n_iter, False, "all_failed",
                      "; ".join(sorted({x.status for x in runs})), r.occupancy, r.shrinkage, tuple(sorted(fit_ids)), log)
    best = max(ok, key=lambda r: r.loglik)
    best.fit_ids = tuple(sorted(fit_ids))
    best.restarts = log
    return best


# ---------------------------------------------------------------- 예측

def _require_ok(fit: MixFit) -> None:
    if fit.status != "ok":
        raise ValueError(f"실패한 혼합 적합으로는 예측하지 않는다: {fit.status} ({fit.reason})")


def _cond_means(fit: MixFit, x_obs: np.ndarray, obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
    """(K, L, |M|) 성분별 조건부 평균 (평균 0)."""
    out = []
    for c in fit.covs:
        B = np.linalg.solve(c[np.ix_(obs, obs)], c[np.ix_(msk, obs)].T).T
        out.append(x_obs @ B.T)
    return np.stack(out)


def predict_fixed(fit: MixFit, x_obs: np.ndarray, obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
    """MIX-f: 가중치 1/K."""
    _require_ok(fit)
    return _cond_means(fit, x_obs, obs, msk).mean(0)


def adaptive_weights(fit: MixFit, x_obs: np.ndarray, obs: np.ndarray, tau: float = 1.0) -> np.ndarray:
    """관측 열만으로 사후 가중치 w_k ∝ π_k exp(τ ℓ_k). ℓ_k = 창 관측 frame 의 주변 로그우도 합."""
    _require_ok(fit)
    ll = np.array([frame_logpdf(x_obs, c[np.ix_(obs, obs)]).sum() for c in fit.covs])
    a = np.log(fit.pis) + tau * ll
    return np.exp(a - _logsumexp(a, 0))


def predict_adaptive(fit: MixFit, x_obs: np.ndarray, obs: np.ndarray, msk: np.ndarray,
                     tau: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """MIX-a: (예측 (L, |M|), 가중치 (K,))."""
    w = adaptive_weights(fit, x_obs, obs, tau)
    return np.tensordot(w, _cond_means(fit, x_obs, obs, msk), axes=1), w
