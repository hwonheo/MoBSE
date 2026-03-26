from pathlib import Path

import numpy as np

from mobse.data.hcp import create_os_dataloaders


def test_create_os_dataloaders_explicit_prefix_split(tmp_path: Path):
    npz_path = tmp_path / "os_windows.npz"

    x = np.random.default_rng(0).normal(size=(12, 8, 4)).astype(np.float32)
    y = np.array([0, 1] * 6, dtype=np.int64)
    subject_ids = np.array(
        [
            "ds000030_sub-001",
            "ds000030_sub-001",
            "ds000030_sub-002",
            "ds000030_sub-002",
            "ds000030_sub-003",
            "ds000030_sub-003",
            "ds000243_sub-001",
            "ds000243_sub-001",
            "ds000243_sub-002",
            "ds000243_sub-002",
            "ds000243_sub-003",
            "ds000243_sub-003",
        ],
        dtype=object,
    )
    np.savez_compressed(npz_path, x=x, y=y, subject_ids=subject_ids, labels=np.array(["rest", "wm"], dtype=object))

    loaders = create_os_dataloaders(
        npz_path=npz_path,
        batch_size=2,
        train_ratio=0.7,
        val_ratio=0.15,
        seed=42,
        train_subject_prefixes=["ds000030_"],
        test_subject_prefixes=["ds000243_"],
    )

    train_count = sum(len(batch["x"]) for batch in loaders["train"])
    val_count = sum(len(batch["x"]) for batch in loaders["val"])
    test_count = sum(len(batch["x"]) for batch in loaders["test"])

    assert train_count > 0
    assert val_count > 0
    assert test_count == 6
