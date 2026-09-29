"""v3 null 세 종류 시험 — 결정 28-3.

고정하려는 것은 **각 null 이 무엇을 보존하는가** 다. 그것이 곧 검정 대상이기 때문이다.

* ``permutation`` — v1 과 **같은 결과**여야 한다 (대조군이 움직이면 비교가 무너진다).
* ``spin`` — 치환이고, 반구를 넘지 않고, **공간 구조를 실제로 보존**해야 한다.
* ``rewire`` — 각 node 의 연결 수와 weight 다중집합을 보존하고 연결 상대를 바꿔야 한다.
"""

from __future__ import annotations

import numpy as np
import pytest

from mobse.v2 import templates as T2
from mobse.v3 import templates as T3

SEED = 1729
N = 24


def _coords(n=N, seed=0):
    rng = np.random.default_rng(seed)
    c = rng.standard_normal((n, 3)) * 30.0
    c[: n // 2, 0] = -np.abs(c[: n // 2, 0]) - 1.0
    c[n // 2:, 0] = np.abs(c[n // 2:, 0]) + 1.0
    return c, c[:, 0] < 0


def _bank(n=N, k=3, seed=0):
    rng = np.random.default_rng(seed)
    raw, tmpl, stats = [], [], []
    for _ in range(k):
        m = rng.standard_normal((n, n))
        m = (m + m.T) / 2
        raw.append(m)
        adj, st = T2.sparsify_positive(m, density=T2.EDGE_DENSITY)
        tmpl.append(T2.normalize_with_self_loop(adj))
        stats.append(st)
    b = T2.GraphBank(templates=np.stack(tmpl), raw_centroids=np.stack(raw),
                     assignment=np.zeros(4, dtype=int), seed=seed,
                     density_stats=tuple(stats), fit_subjects=("s1",), bank_id="")
    return T2.GraphBank(templates=b.templates, raw_centroids=b.raw_centroids,
                        assignment=b.assignment, seed=b.seed,
                        density_stats=b.density_stats, fit_subjects=b.fit_subjects,
                        bank_id=b.fingerprint()[:16])


# ------------------------------------------------------------------ spin

def test_spin_is_a_permutation_and_stays_within_the_hemisphere():
    c, left = _coords()
    p = T3.vasa_permutation(c, left, seed=SEED)
    assert sorted(p.tolist()) == list(range(N))
    assert bool((left[p] == left).all())


def test_spin_preserves_spatial_structure_far_better_than_a_plain_permutation():
    """이 시험이 spin 의 존재 이유다 — 공간을 보존하지 못하면 느슨한 null 과 같다."""
    from scipy.spatial.distance import cdist
    c, left = _coords()
    d0 = cdist(c, c)
    iu = np.triu_indices(N, 1)

    def keep(perm):
        return float(np.corrcoef(d0[iu], d0[perm][:, perm][iu])[0, 1])

    spins = [keep(T3.vasa_permutation(c, left, seed=SEED + i)) for i in range(10)]
    rng = np.random.default_rng(SEED)
    plains = [keep(rng.permutation(N)) for _ in range(10)]
    assert float(np.median(spins)) > float(np.median(plains)) + 0.2


def test_spin_is_deterministic_and_seed_dependent():
    c, left = _coords()
    a = T3.vasa_permutation(c, left, seed=SEED)
    assert np.array_equal(a, T3.vasa_permutation(c, left, seed=SEED))
    assert not np.array_equal(a, T3.vasa_permutation(c, left, seed=SEED + 1))


def test_spin_refuses_a_single_hemisphere():
    c, _ = _coords()
    with pytest.raises(T3.TemplateError, match="반구"):
        T3.vasa_permutation(c, np.ones(N, dtype=bool), seed=SEED)


def test_spin_refuses_mismatched_shapes():
    c, left = _coords()
    with pytest.raises(T3.TemplateError):
        T3.vasa_permutation(c[:, :2], left, seed=SEED)
    with pytest.raises(T3.TemplateError):
        T3.vasa_permutation(c, left[:-1], seed=SEED)


# ---------------------------------------------------------------- rewire

def _sparse_sym(n=16, seed=3):
    rng = np.random.default_rng(seed)
    a = rng.random((n, n))
    a = (a + a.T) / 2
    a[a < 0.65] = 0.0
    np.fill_diagonal(a, 0.0)
    return a


def test_rewire_preserves_each_node_degree():
    a = _sparse_sym()
    r = T3.degree_preserving_rewire(a, seed=SEED)
    assert np.array_equal((a > 0).sum(1), (r > 0).sum(1))


def test_rewire_preserves_the_weight_multiset():
    a = _sparse_sym()
    r = T3.degree_preserving_rewire(a, seed=SEED)
    iu = np.triu_indices(a.shape[0], 1)
    assert np.allclose(np.sort(a[iu]), np.sort(r[iu]))


def test_rewire_actually_changes_who_is_connected_to_whom():
    a = _sparse_sym()
    r = T3.degree_preserving_rewire(a, seed=SEED)
    assert not np.allclose(a, r)


def test_rewire_output_is_symmetric_with_a_zero_diagonal():
    r = T3.degree_preserving_rewire(_sparse_sym(), seed=SEED)
    assert np.allclose(r, r.T)
    assert np.all(np.diag(r) == 0)


def test_rewire_is_deterministic_and_seed_dependent():
    a = _sparse_sym()
    assert np.allclose(T3.degree_preserving_rewire(a, seed=SEED),
                       T3.degree_preserving_rewire(a, seed=SEED))
    assert not np.allclose(T3.degree_preserving_rewire(a, seed=SEED),
                           T3.degree_preserving_rewire(a, seed=SEED + 1))


def test_rewire_refuses_an_asymmetric_matrix_or_a_nonzero_diagonal():
    a = _sparse_sym()
    bad = a.copy()
    bad[0, 1] = bad[1, 0] + 1.0
    with pytest.raises(T3.TemplateError, match="대칭"):
        T3.degree_preserving_rewire(bad, seed=SEED)
    diag = a.copy()
    diag[2, 2] = 0.5
    with pytest.raises(T3.TemplateError, match="대각"):
        T3.degree_preserving_rewire(diag, seed=SEED)


# --------------------------------------------------------- make_null_bank

def test_permutation_null_reproduces_v1_exactly():
    """대조군이 움직이면 v1 과의 비교가 무너진다."""
    b = _bank()
    got = T3.make_null_bank(b, kind="permutation", seed=SEED)
    want = T2.make_null_bank(b, seed=SEED)
    assert np.allclose(got.templates, want.templates)
    assert got.bank_id == want.bank_id


def test_spin_null_differs_from_the_plain_permutation_null():
    b = _bank()
    c, left = _coords()
    spin = T3.make_null_bank(b, kind="spin", seed=SEED, coords=c, is_left=left)
    plain = T3.make_null_bank(b, kind="permutation", seed=SEED)
    assert not np.allclose(spin.templates, plain.templates)
    assert spin.bank_id != plain.bank_id


def test_spin_null_needs_coordinates():
    with pytest.raises(T3.TemplateError, match="좌표"):
        T3.make_null_bank(_bank(), kind="spin", seed=SEED)


def test_spin_null_refuses_a_coordinate_count_mismatch():
    c, left = _coords(n=N + 2, seed=1)
    with pytest.raises(T3.TemplateError, match="좌표 수"):
        T3.make_null_bank(_bank(), kind="spin", seed=SEED, coords=c, is_left=left)


def test_rewire_null_keeps_the_degree_of_the_sparsified_graph():
    b = _bank()
    out = T3.make_null_bank(b, kind="rewire", seed=SEED)
    for k in range(b.k):
        adj, _ = T2.sparsify_positive(b.raw_centroids[k], density=T2.EDGE_DENSITY)
        # 정규화 뒤에도 0 이 아닌 off-diagonal 자리 수는 degree 그대로다
        off = ~np.eye(adj.shape[0], dtype=bool)
        assert np.array_equal((adj > 0).sum(1), (out.templates[k] * off > 0).sum(1))


def test_rewire_null_rebuilds_the_bank_from_the_raw_centroids(monkeypatch):
    """교환을 항등으로 바꾸면 **원래 bank 가 그대로** 나와야 한다.

    이것이 rewire 경로가 bank 를 만든 길 (raw_centroids → sparsify → normalize) 을
    정확히 되밟는지 보는 시험이다. 정규화된 template 에서 다시 sparsify 하면
    자리 (degree) 는 같아도 값이 달라져 이 시험이 깨진다.
    """
    b = _bank()
    monkeypatch.setattr(T3, "degree_preserving_rewire", lambda adj, **kw: adj)
    out = T3.make_null_bank(b, kind="rewire", seed=SEED)
    assert np.allclose(out.templates, b.templates)


def test_rewire_null_refuses_a_density_that_does_not_rebuild_the_bank():
    b = _bank()
    with pytest.raises(T3.TemplateError, match="edge 수"):
        T3.make_null_bank(b, kind="rewire", seed=SEED, density=T2.EDGE_DENSITY / 2)


def test_unknown_null_kind_is_refused():
    with pytest.raises(T3.TemplateError, match="kind"):
        T3.make_null_bank(_bank(), kind="shuffle", seed=SEED)


@pytest.mark.parametrize("kind", T3.NULL_KINDS)
def test_every_null_keeps_the_bank_shape_and_renews_the_id(kind):
    b = _bank()
    c, left = _coords()
    out = T3.make_null_bank(b, kind=kind, seed=SEED, coords=c, is_left=left)
    assert out.templates.shape == b.templates.shape
    assert out.bank_id and out.bank_id != b.bank_id


# ------------------------------------------------------------ 좌표 읽기

def test_roi_centroids_reads_labels_and_rejects_a_midline_parcel(tmp_path):
    nib = pytest.importorskip("nibabel")
    vol = np.zeros((8, 4, 4), dtype=np.int16)
    vol[1] = 1        # x 가 음수 쪽
    vol[6] = 2        # x 가 양수 쪽
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    affine[0, 3] = -8.0
    p = tmp_path / "dseg.nii.gz"
    nib.save(nib.Nifti1Image(vol, affine), str(p))
    coords, is_left = T3.roi_centroids(p)
    assert coords.shape == (2, 3)
    assert is_left.tolist() == [True, False]

    mid = np.zeros((8, 4, 4), dtype=np.int16)
    mid[4] = 1        # x = 0 에 놓이도록
    mid[6] = 2
    q = tmp_path / "mid.nii.gz"
    nib.save(nib.Nifti1Image(mid, affine), str(q))
    with pytest.raises(T3.TemplateError, match="x = 0"):
        T3.roi_centroids(q)


def test_roi_centroids_refuses_noncontiguous_labels(tmp_path):
    nib = pytest.importorskip("nibabel")
    vol = np.zeros((8, 4, 4), dtype=np.int16)
    vol[1] = 1
    vol[6] = 5
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    affine[0, 3] = -8.0
    p = tmp_path / "gap.nii.gz"
    nib.save(nib.Nifti1Image(vol, affine), str(p))
    with pytest.raises(T3.TemplateError, match="연속"):
        T3.roi_centroids(p)
