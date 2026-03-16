from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset


@dataclass
class StandardScaler:
    mean: np.ndarray
    std: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / np.clip(self.std, 1e-6, None)


class ETTh1Dataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray):
        self.x = torch.tensor(x, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)

    def __len__(self) -> int:
        return int(self.x.shape[0])

    def __getitem__(self, idx: int):
        return {
            "x": self.x[idx],
            "y": self.y[idx],
            "task": torch.tensor(1, dtype=torch.long),
        }


def _build_windows(
    values: np.ndarray,
    target: np.ndarray,
    seq_len: int,
    pred_len: int,
) -> Tuple[np.ndarray, np.ndarray]:
    x_list = []
    y_list = []
    n = len(values)
    horizon = seq_len + pred_len
    for i in range(0, n - horizon + 1):
        x_list.append(values[i : i + seq_len])
        y_list.append(target[i + seq_len : i + horizon])
    return np.stack(x_list), np.stack(y_list)


def load_etth1_arrays(
    csv_path: str | Path,
    target_col: str,
    seq_len: int,
    pred_len: int,
    train_ratio: float,
    val_ratio: float,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"ETTh1 CSV not found: {path}")

    df = pd.read_csv(path)
    feature_cols = [c for c in df.columns if c != "date"]
    if target_col not in feature_cols:
        raise ValueError(f"target_col={target_col} not in ETTh1 columns")

    raw_features = df[feature_cols].to_numpy(dtype=np.float32)
    raw_target = df[[target_col]].to_numpy(dtype=np.float32)

    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    scaler = StandardScaler(
        mean=raw_features[:train_end].mean(axis=0, keepdims=True),
        std=raw_features[:train_end].std(axis=0, keepdims=True),
    )

    features = scaler.transform(raw_features)

    x_train, y_train = _build_windows(features[:train_end], raw_target[:train_end], seq_len, pred_len)
    x_val, y_val = _build_windows(
        features[train_end - seq_len : val_end],
        raw_target[train_end - seq_len : val_end],
        seq_len,
        pred_len,
    )
    x_test, y_test = _build_windows(
        features[val_end - seq_len :],
        raw_target[val_end - seq_len :],
        seq_len,
        pred_len,
    )

    return {
        "train": (x_train, y_train),
        "val": (x_val, y_val),
        "test": (x_test, y_test),
    }


def create_etth1_dataloaders(
    csv_path: str | Path,
    target_col: str,
    seq_len: int,
    pred_len: int,
    train_ratio: float,
    val_ratio: float,
    batch_size: int,
) -> Dict[str, DataLoader]:
    arrays = load_etth1_arrays(
        csv_path=csv_path,
        target_col=target_col,
        seq_len=seq_len,
        pred_len=pred_len,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
    )
    datasets = {k: ETTh1Dataset(*v) for k, v in arrays.items()}
    return {
        "train": DataLoader(datasets["train"], batch_size=batch_size, shuffle=True),
        "val": DataLoader(datasets["val"], batch_size=batch_size, shuffle=False),
        "test": DataLoader(datasets["test"], batch_size=batch_size, shuffle=False),
    }
