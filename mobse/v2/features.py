"""Fold 내부 FC 변환 — 재설계 프로토콜 v1.1 §5 전반부.

의존성은 numpy 와 scikit-learn 이다. fMRI 원자료는 필요 없으며 합성 시계열로
전 규칙을 검증할 수 있다.

프로토콜이 규정한 것을 그대로 옮긴다.

* 각 ``30×100`` window 에서 Ledoit–Wolf covariance 를 correlation 으로 바꾼다.
* **상수 ROI 는 사전에 거부한다.** 조용히 0 으로 두지 않는다.
* signed upper triangle 4,950 개를 ``clip(−1+1e−6, 1−1e−6)`` 후 Fisher-z 한다.
* **training-rest 4 windows/subject 에서만** StandardScaler 와 PCA 10차원
  (whiten=False, full SVD)을 fit 한다.
* 유효 rank < 10 이면 **실패한다.** 몰래 차원을 줄이지 않는다.
* 같은 변환 artifact 를 clustering 과 task gate 입력에 공유한다.
* validation transform 시 refit 하지 않는다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

# sklearn 은 **지연 import** 한다. 이 모듈의 상수(N_ROI_DEFAULT 등)만 필요한
# 모듈에까지 무거운 의존성을 강제하지 않기 위해서다 (U24 회피).

N_ROI_DEFAULT = 100
N_PCA = 10
CLIP_EPS = 1e-6
MIN_RANK = N_PCA


class FeatureError(RuntimeError):
    """FC·변환 규칙 위반. 조용한 축소나 대체를 하지 않는다."""


def n_edges(n_roi: int = N_ROI_DEFAULT) -> int:
    """upper triangle edge 수. 100 ROI 면 4,950."""
    return n_roi * (n_roi - 1) // 2


def shrinkage_correlation(window: np.ndarray) -> np.ndarray:
    """window 하나에서 Ledoit–Wolf correlation matrix 를 만든다.

    Args:
        window: ``(n_samples, n_roi)``.

    Returns:
        ``(n_roi, n_roi)`` correlation matrix. 대칭이며 대각은 1 이다.

    Raises:
        FeatureError: 상수 ROI 가 있거나 비유한값이 있으면. 프로토콜 §5 는
            상수 ROI 를 **사전에 거부**하라고 규정한다.
    """
    arr = np.asarray(window, dtype=float)
    if arr.ndim != 2:
        raise FeatureError(f"window 는 2차원이어야 한다: {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise FeatureError("window 에 비유한값이 있다")
    std = arr.std(axis=0)
    constant = np.flatnonzero(std == 0)
    if constant.size:
        raise FeatureError(
            f"상수 ROI 가 있다: {constant.tolist()[:5]} (총 {constant.size}개). "
            "ROI 를 임의 삭제하지 않고 window 를 거부한다")

    from sklearn.covariance import LedoitWolf

    cov = LedoitWolf(assume_centered=False).fit(arr).covariance_
    d = np.sqrt(np.diag(cov))
    corr = cov / np.outer(d, d)
    corr = (corr + corr.T) / 2.0          # 수치 대칭화
    np.fill_diagonal(corr, 1.0)
    return corr


def upper_triangle(mat: np.ndarray) -> np.ndarray:
    """상삼각(대각 제외)을 1차원으로 편다. 순서는 ROI index 순이다."""
    iu = np.triu_indices(mat.shape[0], k=1)
    return mat[iu]


def fisher_z(values: np.ndarray, eps: float = CLIP_EPS) -> np.ndarray:
    """``clip(−1+eps, 1−eps)`` 후 arctanh."""
    return np.arctanh(np.clip(np.asarray(values, dtype=float), -1.0 + eps, 1.0 - eps))


def window_features(window: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """window → (correlation matrix, Fisher-z signed upper triangle)."""
    corr = shrinkage_correlation(window)
    return corr, fisher_z(upper_triangle(corr))


@dataclass(frozen=True)
class FrozenTransform:
    """training-rest 에서 fit 된 scaler+PCA. **재fit 하지 않는다.**"""

    scaler: StandardScaler
    pca: PCA
    n_components: int
    n_features: int
    fit_subjects: Tuple[str, ...]
    n_fit_windows: int
    artifact_id: str

    def transform(self, z: np.ndarray) -> np.ndarray:
        """Fisher-z feature 를 PCA 공간으로 보낸다. 상태를 바꾸지 않는다."""
        arr = np.atleast_2d(np.asarray(z, dtype=float))
        if arr.shape[1] != self.n_features:
            raise FeatureError(
                f"feature 수 불일치: {self.n_features} 를 기대했으나 {arr.shape[1]}")
        return self.pca.transform(self.scaler.transform(arr))

    def fingerprint(self) -> str:
        """scaler·PCA 파라미터의 해시. transform 전후 불변이어야 한다 (T04)."""
        payload = np.concatenate([
            np.asarray(self.scaler.mean_, dtype=float).ravel(),
            np.asarray(self.scaler.scale_, dtype=float).ravel(),
            np.asarray(self.pca.components_, dtype=float).ravel(),
            np.asarray(self.pca.explained_variance_, dtype=float).ravel(),
            np.asarray(self.pca.mean_, dtype=float).ravel(),
        ])
        return hashlib.sha256(np.ascontiguousarray(payload).tobytes()).hexdigest()


def fit_transform_on_training_rest(
    rest_features: np.ndarray,
    fit_subjects: Sequence[str],
    *,
    n_components: int = N_PCA,
    allowed_subjects: Optional[Sequence[str]] = None,
) -> FrozenTransform:
    """training-rest feature 에서 scaler 와 PCA 를 fit 한다.

    Args:
        rest_features: ``(n_windows, n_edges)`` Fisher-z feature.
            **training-rest window 만** 들어와야 한다.
        fit_subjects: 그 window 를 제공한 subject. 감사 흔적으로 저장된다.
        allowed_subjects: 주면 `fit_subjects` 가 이 집합의 부분집합인지 확인한다.

    Raises:
        FeatureError: 허용되지 않은 subject 가 섞였거나(T03), window 수가
            차원보다 적거나, 유효 rank 가 `n_components` 미만이면(프로토콜 §5).
    """
    x = np.asarray(rest_features, dtype=float)
    if x.ndim != 2:
        raise FeatureError(f"rest_features 는 2차원이어야 한다: {x.shape}")
    if not np.all(np.isfinite(x)):
        raise FeatureError("rest_features 에 비유한값이 있다")

    subs = tuple(fit_subjects)
    if allowed_subjects is not None:
        illegal = sorted(set(subs) - set(allowed_subjects))
        if illegal:
            raise FeatureError(
                f"허용되지 않은 subject 가 변환 fit 에 들어갔다: {illegal[:5]} "
                f"(총 {len(illegal)}명). 프로토콜 §4-4")

    if x.shape[0] < n_components:
        raise FeatureError(
            f"window {x.shape[0]}개로 PCA {n_components}차원을 만들 수 없다")

    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(x)
    xs = scaler.transform(x)
    rank = int(np.linalg.matrix_rank(xs))
    if rank < n_components:
        raise FeatureError(
            f"유효 rank {rank} < {n_components}. 몰래 차원을 줄이지 않고 실패한다 (프로토콜 §5)")

    pca = PCA(n_components=n_components, whiten=False, svd_solver="full").fit(xs)
    ft = FrozenTransform(
        scaler=scaler, pca=pca, n_components=n_components,
        n_features=x.shape[1], fit_subjects=subs, n_fit_windows=x.shape[0],
        artifact_id="",
    )
    return FrozenTransform(
        scaler=scaler, pca=pca, n_components=n_components,
        n_features=x.shape[1], fit_subjects=subs, n_fit_windows=x.shape[0],
        artifact_id=ft.fingerprint()[:16],
    )


def stack_window_features(windows: Sequence[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """여러 window 를 (correlations, z-features) 로 쌓는다."""
    corrs, zs = [], []
    for w in windows:
        c, z = window_features(w)
        corrs.append(c)
        zs.append(z)
    return np.stack(corrs), np.stack(zs)
