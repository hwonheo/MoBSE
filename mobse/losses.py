from __future__ import annotations

import torch
import torch.nn.functional as F


def canonical_etth1_loss_name(name: str) -> str:
    key = str(name).strip().lower()
    if key in {"mse", "l2"}:
        return "mse"
    if key in {"mae", "l1"}:
        return "mae"
    if key in {"huber", "smooth_l1", "smoothl1"}:
        return "huber"
    raise ValueError(f"Unsupported etth1 loss type: {name}")


def compute_etth1_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    *,
    loss_type: str,
    huber_delta: float,
) -> torch.Tensor:
    mode = canonical_etth1_loss_name(loss_type)
    if mode == "mse":
        return F.mse_loss(pred, target)
    if mode == "mae":
        return F.l1_loss(pred, target)
    return F.smooth_l1_loss(pred, target, beta=float(huber_delta))
