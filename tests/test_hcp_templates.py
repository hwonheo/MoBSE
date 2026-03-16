import numpy as np

from mobse.data.hcp import compute_fc_matrix, sparsify_fc


def test_fc_and_sparsify_shape_and_density():
    rng = np.random.default_rng(0)
    ts = rng.normal(size=(128, 20)).astype(np.float32)

    fc = compute_fc_matrix(ts, fisher_z=False)
    sparse = sparsify_fc(fc, keep_ratio=0.2)

    assert fc.shape == (20, 20)
    assert sparse.shape == (20, 20)
    assert np.allclose(np.diag(sparse), 0.0)

    total_edges = (20 * 19) // 2
    kept_edges = np.count_nonzero(np.triu(np.abs(sparse) > 0, k=1))
    density = kept_edges / total_edges
    assert 0.1 <= density <= 0.3
