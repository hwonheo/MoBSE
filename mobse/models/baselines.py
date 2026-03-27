from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F


class _TaskEncoder(nn.Module):
    def __init__(self, os_in_dim: int, etth1_in_dim: int, hidden_dim: int):
        super().__init__()
        self.os_proj = nn.Linear(os_in_dim, hidden_dim)
        self.etth1_proj = nn.Linear(etth1_in_dim, hidden_dim)

    def forward(self, x: torch.Tensor, task: str) -> torch.Tensor:
        if task == "hcp":
            task = "os"
        if task == "os":
            return self.os_proj(x)
        if task == "etth1":
            return self.etth1_proj(x)
        raise ValueError(f"Unsupported task: {task}")


class TransformerBaseline(nn.Module):
    def __init__(
        self,
        os_in_dim: int,
        etth1_in_dim: int,
        hidden_dim: int,
        dropout: float,
        os_num_classes: int,
        pred_len: int,
        etth1_out_dim: int,
        etth1_temporal_encoder: str = "mean",
    ):
        super().__init__()
        self.encoder = _TaskEncoder(os_in_dim, etth1_in_dim, hidden_dim)
        layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=4,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.backbone = nn.TransformerEncoder(layer, num_layers=2)
        self.cls_head = nn.Linear(hidden_dim, os_num_classes)
        self.pred_head = nn.Linear(hidden_dim, pred_len * etth1_out_dim)
        self.pred_len = pred_len
        self.etth1_out_dim = etth1_out_dim
        self.etth1_temporal_encoder = etth1_temporal_encoder.strip().lower()
        if self.etth1_temporal_encoder not in {"mean", "gru"}:
            raise ValueError(
                "etth1_temporal_encoder must be one of {'mean', 'gru'} "
                f"(got: {etth1_temporal_encoder})"
            )
        if self.etth1_temporal_encoder == "gru":
            self.etth1_temporal_gru = nn.GRU(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                batch_first=True,
            )

    def _pool_hidden(self, h: torch.Tensor, task: str) -> torch.Tensor:
        if task == "etth1" and self.etth1_temporal_encoder == "gru":
            # temporal encoder control (no mean pooling for ETTh1)
            out, _ = self.etth1_temporal_gru(h)
            return out[:, -1, :]
        return h.mean(dim=1)

    def forward(self, x: torch.Tensor, task: str) -> Dict[str, torch.Tensor]:
        if task == "hcp":
            task = "os"
        h = self.encoder(x, task)
        h = self.backbone(h)
        pooled = self._pool_hidden(h, task)
        if task == "os":
            return {"logits": self.cls_head(pooled), "routing_weights": torch.empty(0, device=x.device)}
        pred = self.pred_head(pooled).reshape(x.shape[0], self.pred_len, self.etth1_out_dim)
        return {"pred": pred, "routing_weights": torch.empty(0, device=x.device)}


class SparseTransformerBaseline(TransformerBaseline):
    def __init__(
        self,
        os_in_dim: int,
        etth1_in_dim: int,
        hidden_dim: int,
        dropout: float,
        os_num_classes: int,
        pred_len: int,
        etth1_out_dim: int,
        window: int,
    ):
        super().__init__(
            os_in_dim=os_in_dim,
            etth1_in_dim=etth1_in_dim,
            hidden_dim=hidden_dim,
            dropout=dropout,
            os_num_classes=os_num_classes,
            pred_len=pred_len,
            etth1_out_dim=etth1_out_dim,
        )
        self.window = window

    def _local_mask(self, seq_len: int, device: torch.device) -> torch.Tensor:
        idx = torch.arange(seq_len, device=device)
        dist = torch.abs(idx[:, None] - idx[None, :])
        mask = dist > self.window
        return mask

    def forward(self, x: torch.Tensor, task: str) -> Dict[str, torch.Tensor]:
        if task == "hcp":
            task = "os"
        h = self.encoder(x, task)
        mask = self._local_mask(h.shape[1], h.device)
        for layer in self.backbone.layers:
            h = layer(h, src_mask=mask)
        pooled = h.mean(dim=1)
        if task == "os":
            return {"logits": self.cls_head(pooled), "routing_weights": torch.empty(0, device=x.device)}
        pred = self.pred_head(pooled).reshape(x.shape[0], self.pred_len, self.etth1_out_dim)
        return {"pred": pred, "routing_weights": torch.empty(0, device=x.device)}


class StandardMoE(nn.Module):
    def __init__(
        self,
        os_in_dim: int,
        etth1_in_dim: int,
        hidden_dim: int,
        num_experts: int,
        dropout: float,
        os_num_classes: int,
        pred_len: int,
        etth1_out_dim: int,
        etth1_temporal_encoder: str = "mean",
    ):
        super().__init__()
        self.encoder = _TaskEncoder(os_in_dim, etth1_in_dim, hidden_dim)
        self.gate_os = nn.Linear(hidden_dim, num_experts)
        self.gate_etth1 = nn.Linear(hidden_dim, num_experts)
        self.experts = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim * 2),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim * 2, hidden_dim),
                )
                for _ in range(num_experts)
            ]
        )
        self.norm = nn.LayerNorm(hidden_dim)
        self.cls_head = nn.Linear(hidden_dim, os_num_classes)
        self.pred_head = nn.Linear(hidden_dim, pred_len * etth1_out_dim)
        self.pred_len = pred_len
        self.etth1_out_dim = etth1_out_dim
        self.etth1_temporal_encoder = etth1_temporal_encoder.strip().lower()
        if self.etth1_temporal_encoder not in {"mean", "gru"}:
            raise ValueError(
                "etth1_temporal_encoder must be one of {'mean', 'gru'} "
                f"(got: {etth1_temporal_encoder})"
            )
        if self.etth1_temporal_encoder == "gru":
            self.etth1_temporal_gru = nn.GRU(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                batch_first=True,
            )

    def _pool_hidden(self, h: torch.Tensor, task: str) -> torch.Tensor:
        if task == "etth1" and self.etth1_temporal_encoder == "gru":
            # temporal encoder control (no mean pooling for ETTh1)
            out, _ = self.etth1_temporal_gru(h)
            return out[:, -1, :]
        return h.mean(dim=1)

    def forward(self, x: torch.Tensor, task: str) -> Dict[str, torch.Tensor]:
        if task == "hcp":
            task = "os"
        h = self.encoder(x, task)
        pooled = self._pool_hidden(h, task)
        gate = self.gate_os(pooled) if task == "os" else self.gate_etth1(pooled)
        routing = F.softmax(gate, dim=-1)

        expert_outputs = []
        for expert in self.experts:
            expert_outputs.append(expert(pooled))
        expert_stack = torch.stack(expert_outputs, dim=1)
        mixed = torch.einsum("be,beh->bh", routing, expert_stack)
        mixed = self.norm(mixed)

        if task == "os":
            return {"logits": self.cls_head(mixed), "routing_weights": routing}
        pred = self.pred_head(mixed).reshape(x.shape[0], self.pred_len, self.etth1_out_dim)
        return {"pred": pred, "routing_weights": routing}
