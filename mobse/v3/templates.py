"""null 세 종류 — 결정 28-3 (2026-09-29).

v1 은 null 이 하나였다: ROI 순서를 섞는 순열 ``P S_k Pᵀ`` (``mobse.v2.templates``).
그 null 은 spectrum·weight 분포·bank 간 관계를 보존하고 **해부학 배치만** 깬다.
공간 인접도 반구 대칭도 함께 깨지므로 비교적 느슨하다.

"무엇을 보존했느냐" 가 곧 "무엇을 검정하느냐" 이므로 (Váša & Mišić 2022) v3 는 셋을 쓴다.

* ``"permutation"`` — v1 과 같다. 가장 느슨하다.
* ``"spin"`` — parcel 중심을 반구 안에서 회전시킨 뒤 일대일 배정한다 (Váša et al. 2018).
  **공간 인접과 반구를 보존**하고 배치만 돌린다. 가장 엄격하다.
* ``"rewire"`` — degree 보존 double-edge swap (Maslov–Sneppen). 각 node 의 **연결 수**와
  edge weight 의 전체 분포를 보존하고 연결 상대를 바꾼다. node strength 는 보존되지 않는다.

읽는 법: A 가 ``permutation`` 만 이기고 ``spin`` 을 못 이기면, 모델이 쓰는 것은
해부학 배치가 아니라 공간 통계라는 뜻이다.

**측정 (2026-09-29, h197)**: Schaefer-100 (MNI152NLin2009cAsym) 100 parcel, 좌 50 · 우 50,
정중선 0. 반구 안 회전 + 일대일 배정 20 회에서 거리행렬 상관 중앙 **0.497**
(단순 순열 0.003), 반구 유지 **1.000**. ``neuromaps``·``netneurotools`` 없이 numpy+scipy 로 된다.

**한계**: 표면 (fsaverage 구면) spin 이 아니라 **부피 중심 회전**이다. 보고할 때 적어야 한다.

bank 자료구조와 sparsify·normalize 는 동결된 ``mobse.v2.templates`` 를 그대로 쓴다.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from mobse.v2.templates import (  # 동결된 v1 부품
    EDGE_DENSITY,
    NULL_SEED_PRIMARY,
    NULL_SEEDS_SENSITIVITY,
    GraphBank,
    TemplateError,
    apply_joint_permutation,
    normalize_with_self_loop,
    roi_permutation,
    sparsify_positive,
)

__all__ = [
    "NULL_KINDS", "NULL_SEED_PRIMARY", "NULL_SEEDS_SENSITIVITY", "TemplateError",
    "roi_centroids", "vasa_permutation", "degree_preserving_rewire", "make_null_bank",
]

#: null 종류. ``"permutation"`` 은 v1 과 같다.
NULL_KINDS: Tuple[str, str, str] = ("permutation", "spin", "rewire")

#: rewire 의 시도 횟수 = edge 수 × 이 배수 (Maslov–Sneppen 관례).
SWAPS_PER_EDGE = 10


def roi_centroids(atlas_path) -> Tuple[np.ndarray, np.ndarray]:
    """parcel 중심 좌표와 좌반구 표시를 낸다.

    경로를 추측하지 않는다 — 호출자가 atlas 파일을 명시한다 (U20).

    Args:
        atlas_path: ``*_dseg.nii.gz`` 경로.

    Returns:
        ``(coords (n_roi, 3) mm, is_left (n_roi,) bool)``.

    Raises:
        TemplateError: label 이 1..n 연속이 아니거나 정중선 (x = 0) parcel 이 있을 때.
            정중선은 반구 안 회전을 정의할 수 없으므로 조용히 넘기지 않는다.
    """
    import nibabel as nib                # 지연 import — null 을 안 쓰는 경로에 강제하지 않는다

    img = nib.load(str(atlas_path))
    data = np.asarray(img.dataobj)
    labels = np.array(sorted(int(v) for v in np.unique(data) if v > 0))
    if labels.tolist() != list(range(1, len(labels) + 1)):
        raise TemplateError(f"label 이 1..n 연속이 아니다: {labels[:5]} … ({len(labels)}개)")
    coords = np.zeros((len(labels), 3), dtype=float)
    for i, lab in enumerate(labels):
        ijk = np.argwhere(data == lab)
        if not len(ijk):
            raise TemplateError(f"label {lab} 의 voxel 이 없다")
        coords[i] = nib.affines.apply_affine(img.affine, ijk.mean(0))
    if np.any(coords[:, 0] == 0):
        raise TemplateError("x = 0 인 parcel 이 있다 — 반구를 정할 수 없다")
    return coords, coords[:, 0] < 0


def _random_rotation(rng: np.random.Generator) -> np.ndarray:
    """균일 무작위 3×3 회전 (QR 기반, det = +1)."""
    q, r = np.linalg.qr(rng.standard_normal((3, 3)))
    q = q * np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    return q


def vasa_permutation(coords: np.ndarray, is_left: np.ndarray, *,
                     seed: int = NULL_SEED_PRIMARY) -> np.ndarray:
    """공간 보존 순열 — 반구 안에서 회전 후 일대일 배정 (Váša et al. 2018).

    중심을 원점으로 옮기고 반구마다 독립적인 무작위 회전을 준 뒤, 회전된 좌표와
    원래 좌표 사이의 거리를 최소화하는 **일대일** 배정을 찾는다 (Hungarian).
    그래서 결과는 언제나 치환이고 반구를 넘지 않는다.

    Raises:
        TemplateError: 모양이 맞지 않거나 한쪽 반구가 비었을 때.
    """
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial.distance import cdist

    c = np.asarray(coords, dtype=float)
    left = np.asarray(is_left, dtype=bool)
    if c.ndim != 2 or c.shape[1] != 3:
        raise TemplateError(f"coords 모양이 (n, 3) 이 아니다: {c.shape}")
    if left.shape != (c.shape[0],):
        raise TemplateError(f"is_left 길이가 맞지 않는다: {left.shape} vs {c.shape[0]}")
    if not left.any() or left.all():
        raise TemplateError("반구 하나가 비었다 — 반구 안 회전을 정의할 수 없다")

    centred = c - c.mean(axis=0)
    rng = np.random.Generator(np.random.PCG64(seed))
    perm = np.empty(c.shape[0], dtype=int)
    for mask in (left, ~left):
        idx = np.flatnonzero(mask)
        rotated = centred[idx] @ _random_rotation(rng).T
        _, col = linear_sum_assignment(cdist(rotated, centred[idx]))
        perm[idx] = idx[col]
    # 불변식 방어선이다. ``linear_sum_assignment`` 는 정의상 일대일 배정을 돌려주므로
    # **정상 경로로는 닿지 않는다** — 돌연변이 시험이 이 줄을 잡지 못하는 이유다.
    # 지우지 않는 이유는 반구 분할이 잘못되면 (겹치거나 빠지면) 여기서 걸리기 때문이다.
    if sorted(perm.tolist()) != list(range(c.shape[0])):
        raise TemplateError("배정 결과가 치환이 아니다")
    return perm


def degree_preserving_rewire(adjacency: np.ndarray, *, seed: int,
                             swaps_per_edge: int = SWAPS_PER_EDGE) -> np.ndarray:
    """degree 보존 double-edge swap (Maslov–Sneppen).

    상삼각 edge 목록에서 두 edge ``(a,b)``·``(c,d)`` 를 골라 ``(a,d)``·``(c,b)`` 로
    바꾼다. self-loop 나 이미 있는 edge 가 되면 그 시도를 버린다. weight 는 edge 를
    따라 옮겨 간다 — 그래서 **각 node 의 연결 수**와 **weight 의 전체 분포**는 그대로이고
    node strength 와 연결 상대는 바뀐다.

    Raises:
        TemplateError: 정방·대칭이 아니거나 대각이 0 이 아닐 때.
    """
    a = np.array(adjacency, dtype=float, copy=True)
    n = a.shape[0]
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise TemplateError(f"adjacency 가 정방행렬이 아니다: {a.shape}")
    if not np.allclose(a, a.T):
        raise TemplateError("adjacency 가 대칭이 아니다")
    if np.any(np.diag(a) != 0):
        raise TemplateError("대각이 0 이 아니다 — self-loop 는 정규화 단계가 더한다")

    iu = np.triu_indices(n, k=1)
    edges = [(int(i), int(j), float(a[i, j]))
             for i, j in zip(*iu) if a[i, j] != 0]
    if len(edges) < 2:
        return a
    present = {(i, j) for i, j, _ in edges}
    rng = np.random.Generator(np.random.PCG64(seed))
    for _ in range(len(edges) * int(swaps_per_edge)):
        p, q = rng.integers(0, len(edges), size=2)
        if p == q:
            continue
        (i1, j1, w1), (i2, j2, w2) = edges[p], edges[q]
        if rng.random() < 0.5:
            i2, j2 = j2, i2                       # 방향을 섞어 편향을 줄인다
        n1 = (min(i1, j2), max(i1, j2))
        n2 = (min(i2, j1), max(i2, j1))
        if n1[0] == n1[1] or n2[0] == n2[1]:
            continue
        if n1 in present or n2 in present:
            continue
        present.discard((min(i1, j1), max(i1, j1)))
        present.discard((min(i2, j2), max(i2, j2)))
        present.add(n1)
        present.add(n2)
        edges[p] = (n1[0], n1[1], w1)
        edges[q] = (n2[0], n2[1], w2)

    out = np.zeros_like(a)
    for i, j, w in edges:
        out[i, j] = w
        out[j, i] = w
    return out


def make_null_bank(bank: GraphBank, *, kind: str = "permutation",
                   seed: int = NULL_SEED_PRIMARY,
                   coords: Optional[np.ndarray] = None,
                   is_left: Optional[np.ndarray] = None,
                   density: float = EDGE_DENSITY) -> GraphBank:
    """null bank 를 만든다.

    ``permutation`` 과 ``spin`` 은 모든 template 에 **같은 순열**을 준다 (v1 과 같은 방식).
    ``rewire`` 는 template 마다 따로 돌리되 seed 를 ``seed + k`` 로 갈라 재현 가능하게 한다.

    ``rewire`` 는 정규화된 template 을 직접 건드리지 않는다 — bank 를 만든 경로를 다시
    밟는다: ``raw_centroids`` → ``sparsify_positive(density)`` → rewire → ``normalize_with_self_loop``.
    정규화된 행렬을 섞으면 ``D^(−1/2)(A+I)D^(−1/2)`` 관계가 깨지기 때문이다.
    되밟은 sparsify 의 edge 수가 bank 가 기록한 값과 다르면 멈춘다.

    Raises:
        TemplateError: 알 수 없는 ``kind``, spin 인데 좌표가 없음, 되밟은 edge 수 불일치.
    """
    if kind not in NULL_KINDS:
        raise TemplateError(f"kind 는 {NULL_KINDS} 중 하나여야 한다: {kind!r}")
    n_roi = int(bank.templates.shape[1])

    if kind in ("permutation", "spin"):
        if kind == "permutation":
            perm = roi_permutation(n_roi, seed=seed)
        else:
            if coords is None or is_left is None:
                raise TemplateError("spin 에는 parcel 좌표와 반구 표시가 필요하다")
            if len(coords) != n_roi:
                raise TemplateError(f"좌표 수 {len(coords)} 가 ROI 수 {n_roi} 와 다르다")
            perm = vasa_permutation(coords, is_left, seed=seed)
        templates = apply_joint_permutation(bank.templates, perm)
    else:
        rebuilt = []
        for k in range(bank.k):
            adj, stats = sparsify_positive(bank.raw_centroids[k], density=density)
            recorded = bank.density_stats[k].get("kept_edges") if k < len(bank.density_stats) else None
            if recorded is not None and float(stats["kept_edges"]) != float(recorded):
                raise TemplateError(
                    f"template {k} 의 edge 수를 되밟지 못했다: {stats['kept_edges']} "
                    f"vs 기록 {recorded} — density 가 bank 를 만든 값과 다른지 확인하라")
            rewired = degree_preserving_rewire(adj, seed=seed + k)
            rebuilt.append(normalize_with_self_loop(rewired))
        templates = np.stack(rebuilt)

    null = GraphBank(
        templates=templates, raw_centroids=bank.raw_centroids,
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
