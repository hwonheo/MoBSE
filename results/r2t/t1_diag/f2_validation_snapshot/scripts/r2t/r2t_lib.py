"""R2T 단계 0 최소 구현 (결정 83) — 창 안 처리 · 단일 공분산 prior · ridge · NMSE · 분할 · bootstrap.

계획서 `docs/experiments/r2t_rest_state_prior_plan_v1_2026-10-16.md` v1.1 의 주 분석 (W-local) 규칙을 따른다.
단계 0 은 **합성 자료로만** 계산 · 누수를 확인한다. 상태 혼합 (MIX) 은 이 파일에 없다.

정보 접근 규칙 (함수 서명으로 강제):

* 관측 입력 처리 ``process_observed`` 는 창의 **관측 ROI 열만** 받는다. 가린 ROI 값은 인자로 들어올 길이 없다.
* 크기 맞춤 상수 g (관측 ROI 의 창 평균 원 강도) 는 관측 열에서만 계산한다.
* 정답 ``process_truth`` 는 가린 열과 관측에서 온 g 를 받는다 — 정답의 정의일 뿐 모델 입력으로 가지 않는다.
* 적합 함수는 train 피험자 id 목록을 받아 기록하고, ``check_disjoint`` 로 test 와 겹치지 않음을 확인한다.
* NMSE 분모 v_r 는 ``train_target_variance`` 가 train 피험자의 task 창으로만 계산한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np

SCALE = 100.0           # 관측 grand mean 대비 백분율
VAR_FLOOR = 1e-12


class LeakError(RuntimeError):
    """train · test 분리 · 정보 접근 규칙 위반."""


# ---------------------------------------------------------------- 창 안 처리 (W-local)

def _detrend_matrix(n_frames: int) -> np.ndarray:
    """창 안 평균 · 선형 추세를 지우는 투영 (n × n)."""
    t = np.arange(n_frames, dtype=float)
    A = np.column_stack([np.ones(n_frames), t - t.mean()])
    return np.eye(n_frames) - A @ np.linalg.pinv(A)


def grand_mean(raw_observed: np.ndarray) -> float:
    """관측 ROI 의 창 평균 원 강도 — 크기 맞춤 상수. 관측 열만 받는다."""
    g = float(np.mean(raw_observed))
    if not np.isfinite(g) or g <= 0:
        raise ValueError(f"관측 grand mean 이 양수가 아니다: {g}")
    return g


def _local(raw: np.ndarray, g: float) -> np.ndarray:
    return _detrend_matrix(raw.shape[0]) @ (SCALE * raw / g)


def process_observed(raw_observed: np.ndarray) -> Tuple[np.ndarray, float]:
    """(L × |O|) 관측 원 신호 → (창 안 처리 신호, g). 가린 ROI 를 받지 않는다."""
    g = grand_mean(raw_observed)
    return _local(raw_observed, g), g


def process_truth(raw_masked: np.ndarray, g: float) -> np.ndarray:
    """(L × |M|) 가린 원 신호 → 정답. g 는 관측에서 온 값만 쓴다."""
    return _local(raw_masked, g)


def window_from_run(run: np.ndarray, start: int, length: int) -> np.ndarray:
    """run (T × R) 에서 창 하나를 복사해 꺼낸다 — 이후 처리는 이 창만 본다."""
    if start < 0 or start + length > run.shape[0]:
        raise ValueError("창이 run 밖이다")
    return np.array(run[start:start + length], copy=True)


def split_window(raw_window: np.ndarray, obs: np.ndarray, msk: np.ndarray):
    """(L × R) 창 → (관측 처리 신호, 정답). 관측 처리는 관측 열만 본다."""
    if np.intersect1d(obs, msk).size:
        raise LeakError("관측 ROI 와 가린 ROI 가 겹친다")
    x_o, g = process_observed(raw_window[:, obs])
    y_m = process_truth(raw_window[:, msk], g)
    return x_o, y_m


# ---------------------------------------------------------------- 분할

def check_disjoint(train_ids: Sequence[str], test_ids: Sequence[str]) -> None:
    both = set(train_ids) & set(test_ids)
    if both:
        raise LeakError(f"train 과 test 피험자가 겹친다: {sorted(both)[:5]}")


def subject_split(ids: Sequence[str], frac_val: float, seed: int) -> Tuple[List[str], List[str]]:
    """피험자 단위 inner 분할 (train, val)."""
    ids = sorted(ids)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(ids))
    n_val = max(1, int(round(frac_val * len(ids))))
    val = sorted(ids[i] for i in perm[:n_val])
    tr = sorted(ids[i] for i in perm[n_val:])
    check_disjoint(tr, val)
    return tr, val


# ---------------------------------------------------------------- 훈련 frame 모으기

def stack_frames(windows: Dict[str, List[np.ndarray]], ids: Sequence[str], obs: np.ndarray,
                 msk: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """train 피험자 창들을 같은 W-local 규칙 (관측 g) 으로 처리해 frame 을 쌓는다 → (X_obs, Y_msk)."""
    xs, ys = [], []
    for s in ids:
        for w in windows[s]:
            x, y = split_window(w, obs, msk)
            xs.append(x)
            ys.append(y)
    return np.concatenate(xs), np.concatenate(ys)


def stack_full(windows: Dict[str, List[np.ndarray]], ids: Sequence[str]) -> np.ndarray:
    """prior 적합용: train 창 전체 ROI 를 W-local 로 (g = 전 ROI 평균 — train 은 모두 관측)."""
    out = []
    for s in ids:
        for w in windows[s]:
            out.append(_local(w, grand_mean(w)))
    return np.concatenate(out)


# ---------------------------------------------------------------- 단일 공분산 prior (G1)

@dataclass
class GaussPrior:
    mu: np.ndarray
    cov: np.ndarray
    shrinkage: float
    method: str
    fit_ids: Tuple[str, ...] = field(default_factory=tuple)

    def predict(self, x_obs: np.ndarray, obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
        """조건부 평균 μ_M + Σ_MO Σ_OO⁻¹ (x_O − μ_O). x_obs: (L × |O|)."""
        S_oo = self.cov[np.ix_(obs, obs)]
        S_mo = self.cov[np.ix_(msk, obs)]
        B = np.linalg.solve(S_oo, S_mo.T).T          # |M| × |O|
        return self.mu[msk] + (x_obs - self.mu[obs]) @ B.T


def fit_prior(frames: np.ndarray, method: str, fit_ids: Sequence[str]) -> GaussPrior:
    """train frame (n × R) 로 Ledoit-Wolf 또는 OAS shrinkage 공분산."""
    from sklearn.covariance import OAS, LedoitWolf

    est = {"lw": LedoitWolf, "oas": OAS}[method]().fit(frames)
    return GaussPrior(mu=est.location_.copy(), cov=est.covariance_.copy(), shrinkage=float(est.shrinkage_),
                      method=method, fit_ids=tuple(sorted(fit_ids)))


# ---------------------------------------------------------------- ridge (BEST 후보)

@dataclass
class Ridge:
    x_mean: np.ndarray
    x_sd: np.ndarray
    y_mean: np.ndarray
    W: np.ndarray
    lam: float
    fit_ids: Tuple[str, ...] = field(default_factory=tuple)

    def predict(self, x_obs: np.ndarray) -> np.ndarray:
        return self.y_mean + ((x_obs - self.x_mean) / self.x_sd) @ self.W


def fit_ridge(X: np.ndarray, Y: np.ndarray, lam: float, fit_ids: Sequence[str]) -> Ridge:
    """train frame 만으로 표준화 (평균 · SD) 와 닫힌 해 ridge."""
    xm, xs = X.mean(0), X.std(0)
    xs = np.where(xs < 1e-12, 1.0, xs)
    ym = Y.mean(0)
    Z = (X - xm) / xs
    G = Z.T @ Z + lam * len(Z) * np.eye(Z.shape[1])
    W = np.linalg.solve(G, Z.T @ (Y - ym))
    return Ridge(xm, xs, ym, W, lam, tuple(sorted(fit_ids)))


# ---------------------------------------------------------------- 평가

def train_target_variance(task_windows: Dict[str, List[np.ndarray]], train_ids: Sequence[str],
                          obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
    """NMSE 분모 v_r — train 피험자 task 창의 정답 (같은 W-local 규칙) 분산. test 는 받지 않는다."""
    _, Y = stack_frames(task_windows, train_ids, obs, msk)
    return np.maximum(Y.var(0), VAR_FLOOR)


def nmse_terms(y_true: np.ndarray, y_pred: np.ndarray, v: np.ndarray) -> np.ndarray:
    """(L × |M|) → 항별 (ŷ − y)² / v_r."""
    return (y_pred - y_true) ** 2 / v


def subject_bootstrap(delta_per_subject: np.ndarray, n_boot: int, seed: int) -> Tuple[float, float, float]:
    """피험자 단위 percentile 95 % CI. 반환 (점추정, 하한, 상한)."""
    d = np.asarray(delta_per_subject, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    bs = d[idx].mean(1)
    return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def delta(nmse_comparator: np.ndarray, nmse_target: np.ndarray) -> np.ndarray:
    """부호 통일 Δ = NMSE(비교 대상) − NMSE(대상). 양수면 대상이 낫다."""
    return np.asarray(nmse_comparator) - np.asarray(nmse_target)


def make_masks(n_roi: int, frac: float, n_masks: int, seed: int, left: np.ndarray) -> List[np.ndarray]:
    """반구 균형 무작위 mask (가린 ROI 색인 정렬본). left: bool (n_roi)."""
    rng = np.random.default_rng(seed)
    L, R = np.flatnonzero(left), np.flatnonzero(~left)
    k = int(round(frac * n_roi)) // 2
    return [np.sort(np.concatenate([rng.choice(L, k, replace=False), rng.choice(R, k, replace=False)]))
            for _ in range(n_masks)]
