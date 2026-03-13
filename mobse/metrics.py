from __future__ import annotations

from typing import Dict, List

import numpy as np
from sklearn.metrics import accuracy_score, f1_score


def classification_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
    }


def forecasting_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    diff = y_true - y_pred
    mae = np.mean(np.abs(diff))
    mse = np.mean(np.square(diff))
    return {"mae": float(mae), "mse": float(mse)}


def routing_metrics(routing_weights: np.ndarray) -> Dict[str, float]:
    if routing_weights.size == 0:
        return {"routing_entropy": 0.0, "routing_stability": 0.0}

    eps = 1e-8
    ent = -np.sum(routing_weights * np.log(routing_weights + eps), axis=-1)
    avg_entropy = float(np.mean(ent))

    # stability as inverse coefficient of variation for per-expert usage
    usage = routing_weights.mean(axis=0)
    stability = float(1.0 / (np.std(usage) / (np.mean(usage) + eps) + eps))
    return {
        "routing_entropy": avg_entropy,
        "routing_stability": stability,
    }
