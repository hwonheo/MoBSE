"""T04 frozen transform + T07 FC information — mobse/v2/features.py."""

from __future__ import annotations

import numpy as np
import pytest

from mobse.v2.features import (
    FeatureError, FrozenTransform, fisher_z, fit_transform_on_training_rest,
    n_edges, shrinkage_correlation, stack_window_features, upper_triangle,
    window_features,
)

RNG = np.random.default_rng(20260917)


def _windows(n, samples=30, roi=20, seed=0):
    rng = np.random.default_rng(seed)
    return [rng.normal(size=(samples, roi)) for _ in range(n)]


# --------------------------------------------------------------------------- #
# FC 기본
# --------------------------------------------------------------------------- #

def test_n_edges_matches_protocol():
    assert n_edges(100) == 4950
    assert n_edges(20) == 190


def test_correlation_is_symmetric_unit_diagonal():
    c = shrinkage_correlation(RNG.normal(size=(30, 20)))
    assert c.shape == (20, 20)
    assert np.allclose(c, c.T)
    assert np.allclose(np.diag(c), 1.0)
    assert np.all(np.abs(c) <= 1.0 + 1e-9)


def test_constant_roi_is_rejected_not_silently_zeroed():
    w = RNG.normal(size=(30, 20))
    w[:, 7] = 3.0
    with pytest.raises(FeatureError, match="상수 ROI"):
        shrinkage_correlation(w)


def test_nonfinite_window_is_rejected():
    w = RNG.normal(size=(30, 20))
    w[0, 0] = np.nan
    with pytest.raises(FeatureError, match="비유한"):
        shrinkage_correlation(w)


def test_upper_triangle_length_and_fisher_z_clipping():
    c = shrinkage_correlation(RNG.normal(size=(30, 20)))
    ut = upper_triangle(c)
    assert ut.size == n_edges(20)
    z = fisher_z(np.array([-1.0, 0.0, 1.0]))
    assert np.all(np.isfinite(z))
    assert z[0] < 0 < z[2] and z[1] == 0.0


# --------------------------------------------------------------------------- #
# T07 — 평균이 같아도 correlation 이 다르면 feature 가 달라야 한다
# --------------------------------------------------------------------------- #

def test_same_mean_different_correlation_gives_different_features():
    n, roi = 400, 6
    rng = np.random.default_rng(7)
    a = rng.normal(size=(n, roi))
    shared = rng.normal(size=n)
    b = np.column_stack([shared + 0.05 * rng.normal(size=n) for _ in range(roi)])
    # 두 window 의 ROI 별 평균을 정확히 같게 맞춘다
    b = b - b.mean(axis=0) + a.mean(axis=0)
    assert np.allclose(a.mean(axis=0), b.mean(axis=0))

    _, za = window_features(a)
    _, zb = window_features(b)
    assert not np.allclose(za, zb), "correlation 구조 차이가 feature 에 반영되지 않았다"
    assert zb.mean() > za.mean(), "공유 신호가 큰 쪽의 FC 가 더 커야 한다"


def test_stack_window_features_shapes():
    corrs, zs = stack_window_features(_windows(5, roi=20, seed=1))
    assert corrs.shape == (5, 20, 20)
    assert zs.shape == (5, n_edges(20))


# --------------------------------------------------------------------------- #
# T04 — frozen transform
# --------------------------------------------------------------------------- #

def _fit(n=40, roi=20, seed=2, subjects=None):
    _, zs = stack_window_features(_windows(n, roi=roi, seed=seed))
    subs = subjects or [f"ds:sub-{i//4:04d}" for i in range(n)]
    return zs, fit_transform_on_training_rest(zs, subs)


def test_transform_does_not_change_fitted_parameters():
    zs, ft = _fit()
    before = ft.fingerprint()
    ft.transform(zs)
    ft.transform(zs[:1])
    assert ft.fingerprint() == before, "transform 이 fit 상태를 바꿨다"


def test_transform_output_shape_and_determinism():
    zs, ft = _fit()
    a = ft.transform(zs)
    b = ft.transform(zs)
    assert a.shape == (zs.shape[0], 10)
    assert np.array_equal(a, b)


def test_refitting_on_more_data_changes_artifact_id():
    zs1, ft1 = _fit(n=40, seed=3)
    zs2, ft2 = _fit(n=60, seed=3)
    assert ft1.artifact_id != ft2.artifact_id


def test_feature_count_mismatch_fails():
    _, ft = _fit(roi=20)
    with pytest.raises(FeatureError, match="feature 수 불일치"):
        ft.transform(np.zeros((1, 5)))


def test_fit_rejects_forbidden_subjects():
    zs, _ = _fit()
    subs = [f"ds:sub-{i//4:04d}" for i in range(zs.shape[0])]
    allowed = sorted(set(subs))[:-1]          # 마지막 subject 를 금지
    with pytest.raises(FeatureError, match="허용되지 않은 subject"):
        fit_transform_on_training_rest(zs, subs, allowed_subjects=allowed)


def test_rank_shortfall_fails_rather_than_reducing_dimension():
    # 같은 window 를 복제하면 rank 가 1 이다
    _, z = window_features(RNG.normal(size=(30, 20)))
    dup = np.repeat(z[None, :], 20, axis=0)
    with pytest.raises(FeatureError, match="rank"):
        fit_transform_on_training_rest(dup, [f"ds:sub-{i:04d}" for i in range(20)])


def test_too_few_windows_fails():
    _, zs = stack_window_features(_windows(4, roi=20, seed=5))
    with pytest.raises(FeatureError, match="PCA"):
        fit_transform_on_training_rest(zs, ["ds:sub-0001"] * 4)


def test_fit_records_audit_trail():
    zs, ft = _fit(n=40)
    assert ft.n_fit_windows == 40
    assert ft.n_features == n_edges(20)
    assert ft.n_components == 10
    assert len(ft.fit_subjects) == 40
    assert len(ft.artifact_id) == 16
