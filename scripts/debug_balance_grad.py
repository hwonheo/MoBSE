#!/usr/bin/env python3
"""Diagnose why balance loss had zero effect on training.

Tests two routing implementations:
1. OLD: scatter_(values) — suspected gradient-breaking
2. NEW: weights * mask — differentiable masking

Run locally:
    cd MoBSE && PYTHONPATH=. python scripts/debug_balance_grad.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mobse.config import load_config
from mobse.data import create_os_dataloaders
from mobse.models import build_model
from mobse.templates import load_template_bank


def _load_balance_loss(routing_weights: torch.Tensor) -> torch.Tensor:
    eps = 1e-8
    k = routing_weights.shape[1]
    max_entropy = torch.log(torch.tensor(float(k), device=routing_weights.device))
    mean_routing = routing_weights.mean(dim=0)
    batch_entropy = -(mean_routing * torch.log(mean_routing + eps)).sum()
    sample_entropy = -(routing_weights * torch.log(routing_weights + eps)).sum(dim=-1).mean()
    return -(batch_entropy + sample_entropy) / (2 * max_entropy)


def routing_old_scatter(weights: torch.Tensor, k: int) -> torch.Tensor:
    """OLD implementation: scatter_ values — may break grad."""
    topv, topi = torch.topk(weights, k=k, dim=-1)
    pruned = torch.zeros_like(weights)
    pruned.scatter_(1, topi, topv)
    return pruned / torch.clamp(pruned.sum(dim=-1, keepdim=True), min=1e-8)


def routing_new_mask(weights: torch.Tensor, k: int) -> torch.Tensor:
    """NEW implementation: differentiable masking."""
    topv, topi = torch.topk(weights, k=k, dim=-1)
    mask = torch.zeros_like(weights)
    mask.scatter_(1, topi, 1.0)
    pruned = weights * mask
    return pruned / torch.clamp(pruned.sum(dim=-1, keepdim=True), min=1e-8)


def test_routing_grad(name: str, routing_fn, weights: torch.Tensor, k: int):
    """Test gradient flow through a routing function."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    # Clone weights to get fresh grad
    w = weights.detach().clone().requires_grad_(True)
    routing = routing_fn(w, k)

    print(f"  routing.requires_grad = {routing.requires_grad}")
    print(f"  routing.grad_fn = {routing.grad_fn}")
    print(f"  routing mean per expert = {routing.mean(dim=0).detach().numpy()}")

    # Balance loss backward
    bal_loss = _load_balance_loss(routing)
    print(f"  balance_loss = {bal_loss.item():.6f}")
    print(f"  balance_loss.requires_grad = {bal_loss.requires_grad}")
    print(f"  balance_loss.grad_fn = {bal_loss.grad_fn}")

    bal_loss.backward()

    if w.grad is not None:
        grad_norm = w.grad.norm().item()
        print(f"  d(bal_loss)/d(weights) grad_norm = {grad_norm:.8f}")
        print(f"  grad per expert (mean abs) = {w.grad.abs().mean(dim=0).numpy()}")
        if grad_norm == 0:
            print("  *** GRADIENT IS ZERO — bug confirmed! ***")
        else:
            print("  *** GRADIENT IS NONZERO — working correctly ***")
    else:
        print("  *** w.grad is None — gradient BROKEN! ***")


def test_full_model(cfg_path: str):
    """Test balance loss gradient flow through the full model."""
    print(f"\n{'='*60}")
    print(f"FULL MODEL TEST: {cfg_path}")
    print(f"{'='*60}")

    cfg = load_config(cfg_path)
    device = torch.device("cpu")

    windows_path = Path(cfg.model.os_windows_path)
    os_loaders = create_os_dataloaders(
        npz_path=windows_path,
        batch_size=cfg.train.batch_size,
        train_ratio=cfg.data.os.train_ratio,
        val_ratio=cfg.data.os.val_ratio,
        seed=cfg.data.os.random_seed,
    )
    batch = next(iter(os_loaders["train"]))
    x = batch["x"].to(device)
    y = batch["y"].to(device)
    cfg.model.num_nodes = int(x.shape[-1])
    cfg.model.os_num_classes = len(cfg.data.os.states)

    template_path = Path(cfg.model.template_bank_path)
    template_bank = load_template_bank(template_path, cfg.data.os.states)
    template_tensor = torch.tensor(template_bank, dtype=torch.float32, device=device)
    model = build_model(cfg, template_bank=template_tensor).to(device)
    model.train()

    print(f"  routing_k={cfg.model.routing_k}, routing_mode={cfg.model.routing_mode}")
    print(f"  gate_temperature={cfg.model.gate_temperature}")
    print(f"  balance_loss_weight={cfg.train.balance_loss_weight}")

    # Forward
    out = model(x, task="os")
    routing = out["routing_weights"]
    logits = out["logits"]

    print(f"  routing.requires_grad = {routing.requires_grad}")
    print(f"  routing.grad_fn = {routing.grad_fn}")
    print(f"  routing mean per expert = {routing.mean(dim=0).detach().numpy()}")

    # Balance loss only
    model.zero_grad()
    bal_loss = _load_balance_loss(routing)
    print(f"  balance_loss = {bal_loss.item():.6f}")
    bal_loss.backward(retain_graph=True)

    gate_grad_from_bal = {}
    for name, p in model.named_parameters():
        if "gate" in name and p.grad is not None:
            gate_grad_from_bal[name] = p.grad.clone()
            print(f"  [BAL] {name}: grad_norm = {p.grad.norm().item():.8f}")
        elif "gate" in name:
            print(f"  [BAL] {name}: grad is None!")

    # CE loss only
    model.zero_grad()
    ce_loss = nn.CrossEntropyLoss()(logits, y)
    ce_loss.backward(retain_graph=True)

    for name, p in model.named_parameters():
        if "gate" in name and p.grad is not None:
            print(f"  [CE]  {name}: grad_norm = {p.grad.norm().item():.8f}")
            if name in gate_grad_from_bal:
                ratio = gate_grad_from_bal[name].norm().item() / max(p.grad.norm().item(), 1e-12)
                print(f"        BAL/CE ratio = {ratio:.4f}")

    # Combined: CE + balance
    model.zero_grad()
    out2 = model(x, task="os")
    routing2 = out2["routing_weights"]
    logits2 = out2["logits"]
    ce2 = nn.CrossEntropyLoss()(logits2, y)
    bal2 = _load_balance_loss(routing2)
    total = ce2 + cfg.train.balance_loss_weight * bal2
    total.backward()

    print(f"\n  [COMBINED] CE={ce2.item():.6f} + {cfg.train.balance_loss_weight}*BAL={bal2.item():.6f}")
    for name, p in model.named_parameters():
        if "gate" in name and p.grad is not None:
            print(f"  [COMBINED] {name}: grad_norm = {p.grad.norm().item():.8f}")


def main():
    # Part 1: Isolated routing function test
    print("PART 1: Isolated routing function gradient test")
    print("=" * 60)

    # Simulate collapsed softmax output (dfc_1 dominant)
    torch.manual_seed(42)
    logits = torch.randn(32, 3)
    logits[:, 1] += 2.0  # bias towards expert 1
    weights = F.softmax(logits / 3.0, dim=-1)  # temperature=3.0
    print(f"Softmax weights (first 5):\n{weights[:5].detach().numpy()}")

    test_routing_grad("OLD scatter_(values)", routing_old_scatter, weights, k=2)
    test_routing_grad("NEW weights*mask", routing_new_mask, weights, k=2)

    # Part 2: Full model test (if config exists)
    cfg_c = "artifacts/mobse_dfc_piop1_sch100/config_dfc_alltasks_balanced_C.yaml"
    cfg_d = "artifacts/mobse_dfc_piop1_sch100/config_dfc_alltasks_balanced_D.yaml"

    for cfg_path in [cfg_c, cfg_d]:
        if Path(cfg_path).exists():
            test_full_model(cfg_path)
        else:
            print(f"\n  [SKIP] {cfg_path} not found")


if __name__ == "__main__":
    main()
