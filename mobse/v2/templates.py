"""Graph bank 와 joint permutation null — 재설계 프로토콜 v1.1 §5 후반부.

의존성은 numpy 와 scikit-learn 이다.

프로토콜이 규정한 것을 그대로 옮긴다.

* PCA rest feature 에 K-means ``K=3, n_init=50, max_iter=500``.
  seed 는 ``30000 + 100*outer_fold + inner_fold`` 이며 outer fit 은
  ``inner_fold=9``, external inner 는 ``outer_fold=9``, external final 은 (9,9) 다.
  이 RNG 는 **모델 seed 와 분리**한다.
* cluster 별 **원래 correlation matrix 의 평균**이 raw centroid 다.
  PCA 를 inverse-transform 한 값을 centroid 로 쓰지 않는다.
* 각 centroid 의 diagonal 을 0 으로 만들고, 전체 가능한 upper-triangle edge
  4,950 개의 **20% = 990 개**를 목표로 가장 큰 양수 edge 를 보존한다.
  양수가 부족하면 있는 양수만 보존하며 실제 density 를 기록한다.
  동률은 ROI index 순으로 처리한다.
* 대칭 복원 후 self-loop I 를 더해 ``S_k = D^(−1/2)(A_k+I)D^(−1/2)`` 를 저장한다.
* 주 null 은 seed 1729 로 **ROI permutation P 하나**를 만들어 모든 k 에 동일하게
  ``P S_k Pᵀ`` 를 적용한다. 입력 ROI 순서는 그대로다. 추가 null seed 1730–1733 은
  민감도 분석용이다.
* cluster 는 모델 구성 요소이며 **생리적 상태 정답이 아니다**.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

import numpy as np

if TYPE_CHECKING:  # sklearn 은 실제 군집 시에만 필요하다
    from sklearn.cluster import KMeans

K_DEFAULT = 3
N_INIT = 50
MAX_ITER = 500
BANK_SEED_BASE = 30000
OUTER_FIT_INNER_FOLD = 9
EXTERNAL_OUTER_FOLD = 9
NULL_SEED_PRIMARY = 1729
NULL_SEEDS_SENSITIVITY = (1730, 1731, 1732, 1733)
EDGE_DENSITY = 0.20


class TemplateError(RuntimeError):
    """bank·null 규칙 위반."""


def bank_seed(outer_fold: int, inner_fold: int) -> int:
    """``30000 + 100*outer_fold + inner_fold``. 모델 seed 와 분리된 stream."""
    for name, v in (("outer_fold", outer_fold), ("inner_fold", inner_fold)):
        if not 0 <= v <= 9:
            raise TemplateError(f"{name} 는 0–9 여야 한다: {v}")
    return BANK_SEED_BASE + 100 * outer_fold + inner_fold


def cluster_rest(pca_features: np.ndarray, *, seed: int,
                 k: int = K_DEFAULT) -> Tuple[np.ndarray, "KMeans"]:
    """PCA rest feature 에 K-means 를 적용한다.

    Returns:
        (labels, 적합된 KMeans).

    Raises:
        TemplateError: window 수가 k 보다 적으면.
    """
    x = np.asarray(pca_features, dtype=float)
    if x.ndim != 2:
        raise TemplateError(f"pca_features 는 2차원이어야 한다: {x.shape}")
    if x.shape[0] < k:
        raise TemplateError(f"window {x.shape[0]}개로 K={k} clustering 불가")
    # 지연 import: config 검증 등 군집이 필요 없는 경로에 sklearn 을 강제하지 않는다.
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=k, n_init=N_INIT, max_iter=MAX_ITER,
                random_state=seed).fit(x)
    return km.labels_.astype(int), km


def raw_centroids(correlations: np.ndarray, labels: np.ndarray,
                  k: int = K_DEFAULT) -> np.ndarray:
    """cluster 별 **원래 correlation matrix** 의 평균.

    PCA inverse-transform 을 쓰지 않는다 (프로토콜 §5).

    Raises:
        TemplateError: 비어 있는 cluster 가 있으면. 조용히 건너뛰지 않는다.
    """
    corr = np.asarray(correlations, dtype=float)
    lab = np.asarray(labels, dtype=int)
    if corr.shape[0] != lab.shape[0]:
        raise TemplateError("correlation 수와 label 수가 다르다")
    out = []
    for c in range(k):
        sel = corr[lab == c]
        if sel.shape[0] == 0:
            raise TemplateError(f"cluster {c} 가 비었다")
        out.append(sel.mean(axis=0))
    return np.stack(out)


def sparsify_positive(centroid: np.ndarray, *,
                      density: float = EDGE_DENSITY) -> Tuple[np.ndarray, Dict[str, float]]:
    """대각을 0 으로 두고 가장 큰 양수 edge 를 목표 개수만큼 보존한다.

    동률은 ROI index 순(상삼각을 편 순서)으로 처리한다. 양수가 목표보다 적으면
    있는 양수만 남기고 실제 density 를 기록한다.

    Returns:
        (대칭 인접행렬, ``{"target_edges", "kept_edges", "actual_density",
        "n_positive"}``).
    """
    a = np.array(centroid, dtype=float, copy=True)
    n = a.shape[0]
    if a.shape[0] != a.shape[1]:
        raise TemplateError(f"centroid 가 정방행렬이 아니다: {a.shape}")
    np.fill_diagonal(a, 0.0)

    iu = np.triu_indices(n, k=1)
    vals = a[iu]
    total_edges = vals.size
    target = int(round(total_edges * density))
    positive = np.flatnonzero(vals > 0)
    n_pos = int(positive.size)
    keep_n = min(target, n_pos)

    # 값 내림차순, 동률은 원래 index(=ROI index 순) 오름차순
    order = sorted(positive.tolist(), key=lambda i: (-vals[i], i))
    keep = np.asarray(order[:keep_n], dtype=int)

    kept = np.zeros_like(vals)
    if keep.size:
        kept[keep] = vals[keep]
    out = np.zeros_like(a)
    out[iu] = kept
    out = out + out.T
    stats = {"target_edges": float(target), "kept_edges": float(keep_n),
             "actual_density": keep_n / total_edges if total_edges else 0.0,
             "n_positive": float(n_pos)}
    return out, stats


def normalize_with_self_loop(adjacency: np.ndarray) -> np.ndarray:
    """``S = D^(−1/2)(A+I)D^(−1/2)``. degree 0 은 1 로 보호한다."""
    a = np.asarray(adjacency, dtype=float)
    n = a.shape[0]
    ai = a + np.eye(n)
    deg = ai.sum(axis=1)
    if np.any(deg <= 0):
        raise TemplateError("self-loop 를 더한 뒤에도 degree 가 0 이하인 node 가 있다")
    dinv = 1.0 / np.sqrt(deg)
    s = ai * dinv[:, None] * dinv[None, :]
    return (s + s.T) / 2.0


@dataclass(frozen=True)
class GraphBank:
    """정규화된 bank 와 그 provenance."""

    templates: np.ndarray               # (k, n_roi, n_roi)
    raw_centroids: np.ndarray           # (k, n_roi, n_roi)
    assignment: np.ndarray              # (n_windows,)
    seed: int
    density_stats: Tuple[Dict[str, float], ...]
    fit_subjects: Tuple[str, ...]
    bank_id: str

    @property
    def k(self) -> int:
        return int(self.templates.shape[0])

    def fingerprint(self) -> str:
        return hashlib.sha256(
            np.ascontiguousarray(self.templates, dtype=float).tobytes()).hexdigest()


def build_bank(correlations: np.ndarray, pca_features: np.ndarray,
               fit_subjects: Sequence[str], *, seed: int,
               k: int = K_DEFAULT, density: float = EDGE_DENSITY) -> GraphBank:
    """training-rest 에서 bank 를 만든다.

    Args:
        correlations: ``(n_windows, n_roi, n_roi)`` 원래 correlation.
        pca_features: ``(n_windows, n_components)`` — clustering 입력.
        fit_subjects: 이 window 를 제공한 subject (감사 흔적).
        seed: `bank_seed()` 가 만든 값.
    """
    labels, _ = cluster_rest(pca_features, seed=seed, k=k)
    centroids = raw_centroids(correlations, labels, k=k)
    sparse, stats = [], []
    for c in centroids:
        adj, st = sparsify_positive(c, density=density)
        sparse.append(normalize_with_self_loop(adj))
        stats.append(st)
    bank = GraphBank(
        templates=np.stack(sparse), raw_centroids=centroids, assignment=labels,
        seed=seed, density_stats=tuple(stats), fit_subjects=tuple(fit_subjects),
        bank_id="",
    )
    return GraphBank(
        templates=bank.templates, raw_centroids=bank.raw_centroids,
        assignment=bank.assignment, seed=bank.seed,
        density_stats=bank.density_stats, fit_subjects=bank.fit_subjects,
        bank_id=bank.fingerprint()[:16],
    )


def roi_permutation(n_roi: int, seed: int = NULL_SEED_PRIMARY) -> np.ndarray:
    """ROI permutation 하나. 모든 template 에 **동일하게** 적용한다."""
    rng = np.random.Generator(np.random.PCG64(seed))
    return rng.permutation(n_roi)


def apply_joint_permutation(templates: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """``P S_k Pᵀ`` 를 모든 k 에 같은 P 로 적용한다.

    전체 spectrum·weight 분포·bank 간 관계는 보존되고, 각 해부학 ROI 의 degree 는
    보존되지 않는다. 입력 ROI 순서는 바꾸지 않는다.
    """
    t = np.asarray(templates, dtype=float)
    p = np.asarray(perm, dtype=int)
    if t.ndim != 3 or t.shape[1] != t.shape[2]:
        raise TemplateError(f"templates 모양이 (k, n, n) 이 아니다: {t.shape}")
    if p.shape[0] != t.shape[1]:
        raise TemplateError("permutation 길이가 ROI 수와 다르다")
    if sorted(p.tolist()) != list(range(t.shape[1])):
        raise TemplateError("permutation 이 올바른 치환이 아니다")
    return t[:, p][:, :, p]


def make_null_bank(bank: GraphBank, seed: int = NULL_SEED_PRIMARY) -> GraphBank:
    """joint ROI permutation 을 적용한 null bank 를 만든다."""
    perm = roi_permutation(bank.templates.shape[1], seed=seed)
    permuted = apply_joint_permutation(bank.templates, perm)
    null = GraphBank(
        templates=permuted, raw_centroids=bank.raw_centroids,
        assignment=bank.assignment, seed=seed,
        density_stats=bank.density_stats, fit_subjects=bank.fit_subjects,
        bank_id="",
    )
    return GraphBank(
        templates=null.templates, raw_centroids=null.raw_centroids,
        assignment=null.assignment, seed=null.seed,
        density_stats=null.density_stats, fit_subjects=null.fit_subjects,
        bank_id=null.fingerprint()[:16],
    )


def mix_templates(templates: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """``S(x) = Σ_k π_k(x) S_k``. **혼합 뒤 다시 normalize 하지 않는다.**"""
    t = np.asarray(templates, dtype=float)
    w = np.asarray(weights, dtype=float)
    if w.ndim == 1:
        w = w[None, :]
    if w.shape[1] != t.shape[0]:
        raise TemplateError(f"weight 수 {w.shape[1]} 와 template 수 {t.shape[0]} 불일치")
    return np.einsum("be,enm->bnm", w, t)


# --------------------------------------------------------------------------- #
# §6 구조 비교 — training-rest single average graph
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SingleGraph:
    """§6 구조 비교 "training-rest single average graph" 의 graph 하나와 provenance.

    구현 선택 (계획서가 정하지 않은 부분, 결정 아님):

    * 평균 대상은 training-rest window 전부의 **원래 correlation matrix** 다
      (= clustering 없는 K=1 raw centroid). 따라서 군집 seed 가 없다.
    * sparsify·정규화는 §5 bank 와 같은 규칙 (대각 0, 양수 상위 20%, 동률은
      ROI index 순, ``D^(−1/2)(A+I)D^(−1/2)``) 을 그대로 쓴다.
    * null 짝은 만들지 않는다 (§6 표에 없다).
    """

    template: np.ndarray                # (n_roi, n_roi)
    raw_mean: np.ndarray                # (n_roi, n_roi)
    n_windows: int
    density_stats: Dict[str, float]
    fit_subjects: Tuple[str, ...]
    graph_id: str

    def fingerprint(self) -> str:
        return hashlib.sha256(
            np.ascontiguousarray(self.template, dtype=float).tobytes()).hexdigest()


def build_single_graph(correlations: np.ndarray, fit_subjects: Sequence[str], *,
                       density: float = EDGE_DENSITY) -> SingleGraph:
    """training-rest correlation 전부의 평균으로 graph 하나를 만든다.

    Args:
        correlations: ``(n_windows, n_roi, n_roi)`` training-rest 원래 correlation.
            호출자가 training subject 의 rest window 만 넘긴다 (bank 와 같은 경계).
        fit_subjects: 이 window 를 제공한 subject (감사 흔적).

    Raises:
        TemplateError: 모양이 틀리거나 window 가 없거나 유한하지 않은 값이 있으면.
    """
    corr = np.asarray(correlations, dtype=float)
    if corr.ndim != 3 or corr.shape[1] != corr.shape[2]:
        raise TemplateError(f"correlation 은 (n, r, r) 이어야 한다: {corr.shape}")
    if corr.shape[0] == 0:
        raise TemplateError("training-rest window 가 없다")
    if not np.all(np.isfinite(corr)):
        raise TemplateError("correlation 에 유한하지 않은 값이 있다")
    if len(fit_subjects) == 0:
        raise TemplateError("fit subject 가 없다")
    mean = corr.mean(axis=0)
    adj, stats = sparsify_positive(mean, density=density)
    tmpl = normalize_with_self_loop(adj)
    g = SingleGraph(template=tmpl, raw_mean=mean, n_windows=int(corr.shape[0]),
                    density_stats=stats, fit_subjects=tuple(fit_subjects), graph_id="")
    return SingleGraph(template=g.template, raw_mean=g.raw_mean, n_windows=g.n_windows,
                       density_stats=g.density_stats, fit_subjects=g.fit_subjects,
                       graph_id=g.fingerprint()[:16])
