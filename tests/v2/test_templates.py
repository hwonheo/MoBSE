"""T05 graph/null — mobse/v2/templates.py."""

from __future__ import annotations

import numpy as np
import pytest

from mobse.v2.templates import (
    EDGE_DENSITY, NULL_SEED_PRIMARY, NULL_SEEDS_SENSITIVITY, TemplateError,
    apply_joint_permutation, bank_seed, build_bank, cluster_rest, make_null_bank,
    mix_templates, normalize_with_self_loop, raw_centroids, roi_permutation,
    sparsify_positive,
)


# --------------------------------------------------------------------------- #
# seed 규칙
# --------------------------------------------------------------------------- #

def test_bank_seed_formula():
    assert bank_seed(0, 0) == 30000
    assert bank_seed(2, 1) == 30201
    assert bank_seed(0, 9) == 30009       # outer fit
    assert bank_seed(9, 0) == 30900       # external inner
    assert bank_seed(9, 9) == 30909       # external final
    with pytest.raises(TemplateError):
        bank_seed(10, 0)


def test_bank_seed_is_separate_from_model_seeds():
    assert min(bank_seed(o, i) for o in range(10) for i in range(10)) > 44


# --------------------------------------------------------------------------- #
# 손계산 소형 bank
# --------------------------------------------------------------------------- #

def test_sparsify_keeps_largest_positive_edges_only():
    a = np.array([
        [0.0, 0.9, 0.5, -0.8],
        [0.9, 0.0, 0.1, 0.7],
        [0.5, 0.1, 0.0, 0.2],
        [-0.8, 0.7, 0.2, 0.0],
    ])
    # upper triangle 6개 중 20% = 1.2 -> round = 1개
    out, st = sparsify_positive(a, density=0.2)
    assert st["target_edges"] == 1 and st["kept_edges"] == 1
    assert np.count_nonzero(np.triu(out, 1)) == 1
    assert out[0, 1] == pytest.approx(0.9)      # 최대 양수
    assert np.allclose(out, out.T)
    assert np.all(np.diag(out) == 0)
    assert np.all(out >= 0), "음수 edge 가 남았다"


def test_sparsify_ties_broken_by_roi_index():
    a = np.zeros((4, 4))
    a[0, 2] = a[1, 3] = 0.5      # 동률 두 개
    a = a + a.T
    out, st = sparsify_positive(a, density=1 / 6)   # 1개만 남김
    assert st["kept_edges"] == 1
    # 상삼각을 편 순서에서 (0,2) 가 (1,3) 보다 앞선다
    assert out[0, 2] == pytest.approx(0.5) and out[1, 3] == 0.0


def test_sparsify_records_actual_density_when_positives_are_scarce():
    a = np.zeros((10, 10))
    a[0, 1] = 0.5
    a = a + a.T
    out, st = sparsify_positive(a, density=EDGE_DENSITY)
    assert st["n_positive"] == 1
    assert st["kept_edges"] == 1 < st["target_edges"]
    assert st["actual_density"] == pytest.approx(1 / 45)


def test_normalize_with_self_loop_hand_computed():
    a = np.array([[0.0, 1.0], [1.0, 0.0]])
    s = normalize_with_self_loop(a)
    # A+I = [[1,1],[1,1]], degree 2 -> S = [[.5,.5],[.5,.5]]
    assert np.allclose(s, np.full((2, 2), 0.5))
    assert np.allclose(s, s.T)
    assert np.all(np.isfinite(s)) and np.all(s >= 0)


def test_isolated_node_survives_via_self_loop():
    a = np.zeros((3, 3))
    a[0, 1] = a[1, 0] = 1.0
    s = normalize_with_self_loop(a)
    assert s[2, 2] == pytest.approx(1.0)
    assert np.all(np.isfinite(s))


# --------------------------------------------------------------------------- #
# centroid 는 원래 correlation 의 평균
# --------------------------------------------------------------------------- #

def test_raw_centroid_is_mean_of_original_matrices():
    m0 = np.full((4, 4), 0.2)
    m1 = np.full((4, 4), 0.8)
    corrs = np.stack([m0, m0, m1, m1])
    labels = np.array([0, 0, 1, 1])
    cent = raw_centroids(corrs, labels, k=2)
    assert np.allclose(cent[0], 0.2) and np.allclose(cent[1], 0.8)


def test_empty_cluster_fails_loudly():
    corrs = np.stack([np.eye(3)] * 4)
    with pytest.raises(TemplateError, match="비었다"):
        raw_centroids(corrs, np.array([0, 0, 0, 0]), k=3)


# --------------------------------------------------------------------------- #
# joint permutation null
# --------------------------------------------------------------------------- #

def _toy_bank(n_roi=12, k=3, seed=11):
    rng = np.random.default_rng(seed)
    corrs, feats = [], []
    for c in range(k):
        for _ in range(6):
            base = rng.normal(size=(n_roi, n_roi)) * 0.1 + (c + 1) * 0.15
            m = (base + base.T) / 2
            np.fill_diagonal(m, 1.0)
            corrs.append(m)
            feats.append(np.concatenate([[c * 10.0], rng.normal(size=9) * 0.01]))
    subs = [f"ds:sub-{i:04d}" for i in range(len(corrs))]
    return build_bank(np.stack(corrs), np.stack(feats), subs,
                      seed=bank_seed(0, 9), k=k)


def test_bank_templates_are_symmetric_finite_nonnegative():
    bank = _toy_bank()
    assert bank.templates.shape[0] == 3
    for s in bank.templates:
        assert np.allclose(s, s.T)
        assert np.all(np.isfinite(s))
        assert np.all(s >= 0)


def test_null_preserves_spectrum_and_between_bank_distance():
    bank = _toy_bank()
    null = make_null_bank(bank, seed=NULL_SEED_PRIMARY)
    for s, sn in zip(bank.templates, null.templates):
        assert np.allclose(np.sort(np.linalg.eigvalsh(s)),
                           np.sort(np.linalg.eigvalsh(sn)), atol=1e-10)
        assert np.allclose(np.sort(s.ravel()), np.sort(sn.ravel()), atol=1e-12)
    for i in range(bank.k):
        for j in range(bank.k):
            assert np.linalg.norm(bank.templates[i] - bank.templates[j]) == \
                   pytest.approx(np.linalg.norm(null.templates[i] - null.templates[j]))


def test_null_uses_one_permutation_for_every_template():
    bank = _toy_bank()
    null = make_null_bank(bank)
    perm = roi_permutation(bank.templates.shape[1], NULL_SEED_PRIMARY)
    manual = apply_joint_permutation(bank.templates, perm)
    assert np.allclose(null.templates, manual)


def test_null_changes_per_roi_degree():
    bank = _toy_bank()
    null = make_null_bank(bank)
    deg_a = bank.templates.sum(axis=2)
    deg_b = null.templates.sum(axis=2)
    assert not np.allclose(deg_a, deg_b), "ROI 별 degree 가 보존되면 null 이 아니다"
    assert np.allclose(np.sort(deg_a, axis=1), np.sort(deg_b, axis=1))


def test_sensitivity_seeds_give_different_permutations():
    perms = {NULL_SEED_PRIMARY: roi_permutation(12, NULL_SEED_PRIMARY)}
    for s in NULL_SEEDS_SENSITIVITY:
        perms[s] = roi_permutation(12, s)
    keys = sorted(perms)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert not np.array_equal(perms[a], perms[b])


def test_invalid_permutation_is_rejected():
    bank = _toy_bank()
    with pytest.raises(TemplateError, match="치환"):
        apply_joint_permutation(bank.templates, np.zeros(12, dtype=int))
    with pytest.raises(TemplateError, match="길이"):
        apply_joint_permutation(bank.templates, np.arange(5))


def test_bank_id_is_content_bound():
    b1 = _toy_bank(seed=11)
    b2 = _toy_bank(seed=11)
    b3 = _toy_bank(seed=12)
    assert b1.bank_id == b2.bank_id
    assert b1.bank_id != b3.bank_id
    assert make_null_bank(b1).bank_id != b1.bank_id


# --------------------------------------------------------------------------- #
# 혼합
# --------------------------------------------------------------------------- #

def test_mixture_one_hot_equals_template():
    bank = _toy_bank()
    w = np.eye(bank.k)
    mixed = mix_templates(bank.templates, w)
    for k in range(bank.k):
        assert np.allclose(mixed[k], bank.templates[k])


def test_mixture_uniform_equals_mean_and_is_not_renormalised():
    bank = _toy_bank()
    w = np.full((1, bank.k), 1.0 / bank.k)
    mixed = mix_templates(bank.templates, w)[0]
    assert np.allclose(mixed, bank.templates.mean(axis=0))
    # 재정규화했다면 row sum 이 1 근처로 강제되었을 것이다
    assert not np.allclose(mixed.sum(axis=1), 1.0)


def test_mixture_weight_count_mismatch_fails():
    bank = _toy_bank()
    with pytest.raises(TemplateError, match="불일치"):
        mix_templates(bank.templates, np.ones((1, bank.k + 1)))


def test_clustering_is_reproducible_for_same_seed():
    rng = np.random.default_rng(3)
    x = np.vstack([rng.normal(loc=c * 5, size=(10, 4)) for c in range(3)])
    a, _ = cluster_rest(x, seed=30009)
    b, _ = cluster_rest(x, seed=30009)
    assert np.array_equal(a, b)


# --------------------------------------------------------------------------- #
# §6 구조 비교 — training-rest single average graph
# --------------------------------------------------------------------------- #

from mobse.v2.templates import SingleGraph, build_single_graph   # noqa: E402


def _corrs(n=12, r=10, seed=4):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        x = rng.standard_normal((40, r))
        out.append(np.corrcoef(x, rowvar=False))
    return np.stack(out)


def test_single_graph_is_mean_then_bank_rules():
    c = _corrs()
    g = build_single_graph(c, ["s1", "s2"])
    assert isinstance(g, SingleGraph)
    np.testing.assert_allclose(g.raw_mean, c.mean(axis=0))
    adj, st = sparsify_positive(c.mean(axis=0), density=EDGE_DENSITY)
    np.testing.assert_allclose(g.template, normalize_with_self_loop(adj))
    assert g.density_stats == st and g.n_windows == 12
    assert g.fit_subjects == ("s1", "s2")
    np.testing.assert_allclose(g.template, g.template.T)
    assert g.graph_id == g.fingerprint()[:16]


def test_single_graph_equals_k1_bank():
    """clustering 없는 K=1 raw centroid 와 같은 graph 다."""
    c = _corrs()
    pca = np.random.default_rng(0).standard_normal((12, 10))
    b = build_bank(c, pca, ["s1"], seed=bank_seed(0, 0), k=1)
    g = build_single_graph(c, ["s1"])
    np.testing.assert_allclose(g.template, b.templates[0])
    np.testing.assert_allclose(g.raw_mean, b.raw_centroids[0])


def test_single_graph_deterministic_and_input_sensitive():
    c = _corrs()
    assert build_single_graph(c, ["s"]).graph_id == build_single_graph(c.copy(), ["s"]).graph_id
    assert build_single_graph(c[:6], ["s"]).graph_id != build_single_graph(c, ["s"]).graph_id


def test_single_graph_rejects_bad_input():
    c = _corrs()
    with pytest.raises(TemplateError):
        build_single_graph(c[:0], ["s"])
    with pytest.raises(TemplateError):
        build_single_graph(c[:, :, :5], ["s"])
    with pytest.raises(TemplateError):
        build_single_graph(c[0], ["s"])
    with pytest.raises(TemplateError):
        build_single_graph(c, [])
    bad = c.copy()
    bad[0, 0, 1] = np.nan
    with pytest.raises(TemplateError):
        build_single_graph(bad, ["s"])


# --------------------------------------------------------------------------- #
# T03 — 금지 subject 를 bank fit 에 넣으면 실패 (결정 21 명세 2)
# --------------------------------------------------------------------------- #

def _toy_inputs(n_roi=12, k=3, seed=11):
    rng = np.random.default_rng(seed)
    corrs, feats = [], []
    for c in range(k):
        for _ in range(6):
            base = rng.normal(size=(n_roi, n_roi)) * 0.1 + (c + 1) * 0.15
            m = (base + base.T) / 2
            np.fill_diagonal(m, 1.0)
            corrs.append(m)
            feats.append(np.concatenate([[c * 10.0], rng.normal(size=9) * 0.01]))
    subs = [f"ds:sub-{i:04d}" for i in range(len(corrs))]
    return np.stack(corrs), np.stack(feats), subs


def test_build_bank_rejects_a_forbidden_subject():
    """T03 — 허용 집합 밖 subject 의 창이 하나라도 있으면 bank fit 이 실패한다."""
    corrs, feats, subs = _toy_inputs()
    allowed = subs[1:]                       # subs[0] 은 금지
    with pytest.raises(TemplateError, match="허용되지 않은 subject 가 bank fit"):
        build_bank(corrs, feats, subs, seed=bank_seed(0, 0), k=3,
                   allowed_subjects=allowed)


def test_build_bank_accepts_fit_subjects_within_the_allowed_set():
    """허용 집합이 fit subject 를 모두 담으면 결과는 검사 없이 만든 bank 와 같다."""
    corrs, feats, subs = _toy_inputs()
    plain = build_bank(corrs, feats, subs, seed=bank_seed(0, 0), k=3)
    checked = build_bank(corrs, feats, subs, seed=bank_seed(0, 0), k=3,
                         allowed_subjects=subs + ["ds:sub-9999"])
    assert checked.bank_id == plain.bank_id
    assert checked.fit_subjects == plain.fit_subjects
