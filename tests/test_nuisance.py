from __future__ import annotations

import numpy as np

from mobse.data.nuisance import expand_confounds


def test_expand_confounds_derivatives_and_quadratic():
    base = np.array([[1.0, 2.0], [3.0, 5.0], [6.0, 10.0]], dtype=np.float32)
    out = expand_confounds(base, add_derivatives=True, add_quadratic=True)

    # base + deriv + base^2 + deriv^2
    assert out.shape == (3, 8)

    expected_deriv = np.array([[0.0, 0.0], [2.0, 3.0], [3.0, 5.0]], dtype=np.float32)
    np.testing.assert_allclose(out[:, 0:2], base)
    np.testing.assert_allclose(out[:, 2:4], expected_deriv)
    np.testing.assert_allclose(out[:, 4:6], base**2)
    np.testing.assert_allclose(out[:, 6:8], expected_deriv**2)


def test_expand_confounds_without_derivatives():
    base = np.array([[1.0], [2.0]], dtype=np.float32)
    out = expand_confounds(base, add_derivatives=False, add_quadratic=True)
    assert out.shape == (2, 2)
    np.testing.assert_allclose(out[:, 0:1], base)
    np.testing.assert_allclose(out[:, 1:2], base**2)
