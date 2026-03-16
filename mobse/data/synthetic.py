from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def generate_synthetic_hcp(timeseries_dir: str | Path, num_subjects: int, states, num_nodes: int) -> None:
    root = Path(timeseries_dir)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    for sid in range(num_subjects):
        subject_dir = root / f"sub-{sid:04d}"
        subject_dir.mkdir(parents=True, exist_ok=True)
        for state in states:
            base = rng.normal(size=(160, num_nodes)).astype(np.float32)
            drift = np.linspace(0, 1, 160, dtype=np.float32).reshape(-1, 1)
            signal = base + drift * (states.index(state) + 1) * 0.05
            np.save(subject_dir / f"{state}.npy", signal)


def generate_synthetic_etth1(csv_path: str | Path, rows: int = 3000) -> None:
    rng = np.random.default_rng(7)
    hours = pd.date_range(start="2020-01-01", periods=rows, freq="h")
    features = rng.normal(size=(rows, 6)).astype(np.float32)
    trend = np.sin(np.linspace(0, 40, rows)).astype(np.float32)
    target = (trend + 0.1 * rng.normal(size=rows)).reshape(-1, 1)

    df = pd.DataFrame(features, columns=[f"f{i}" for i in range(6)])
    df["OT"] = target
    df.insert(0, "date", hours.astype(str))

    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
