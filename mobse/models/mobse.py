from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn.dense import DenseGCNConv
except ImportError:  # pragma: no cover
    DenseGCNConv = None


class DenseGraphLayer(nn.Module):
    def __init__(self, hidden_dim: int, dropout: float):
        super().__init__()
        self.proj = nn.Linear(hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        msg = torch.matmul(adj, x)
        out = self.proj(msg)
        out = self.dropout(out)
        return self.norm(x + out)


class MoBSEModel(nn.Module):
    def __init__(
        self,
        num_nodes: int,
        hidden_dim: int,
        num_experts: int,
        num_graph_layers: int,
        dropout: float,
        routing_k: int,
        routing_mode: str,
        os_num_classes: int,
        etth1_in_dim: int,
        etth1_out_dim: int,
        pred_len: int,
        template_bank: torch.Tensor,
        use_template_prior: bool = True,
    ):
        super().__init__()
        self.num_nodes = num_nodes
        self.hidden_dim = hidden_dim
        self.num_experts = num_experts
        self.routing_k = routing_k
        self.routing_mode = routing_mode
        self.pred_len = pred_len
        self.etth1_out_dim = etth1_out_dim
        self.use_template_prior = use_template_prior

        self.os_adapter = nn.Linear(num_nodes, num_nodes * hidden_dim)
        self.etth1_adapter = nn.Linear(etth1_in_dim, num_nodes * hidden_dim)
        self.gate = nn.Sequential(
            nn.Linear(num_nodes + etth1_in_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_experts),
        )

        if template_bank.shape[0] != num_experts:
            raise ValueError(
                f"template_bank experts ({template_bank.shape[0]}) must match num_experts ({num_experts})"
            )
        if template_bank.shape[1] != num_nodes or template_bank.shape[2] != num_nodes:
            raise ValueError("template_bank node dimension mismatch")

        if self.use_template_prior:
            self.register_buffer("template_bank", template_bank)
        else:
            self.template_bank_param = nn.Parameter(0.02 * torch.randn_like(template_bank))

        self.graph_layers = nn.ModuleList()
        self.use_pyg = DenseGCNConv is not None
        for _ in range(num_graph_layers):
            if self.use_pyg:
                self.graph_layers.append(DenseGCNConv(hidden_dim, hidden_dim))
            else:
                self.graph_layers.append(DenseGraphLayer(hidden_dim, dropout))

        self.node_norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

        self.os_head = nn.Linear(hidden_dim, os_num_classes)
        self.etth1_head = nn.Linear(hidden_dim, pred_len * etth1_out_dim)

    def _pool_for_gate(self, x: torch.Tensor, task: str, etth1_in_dim: int) -> torch.Tensor:
        pooled = x.mean(dim=1)
        if task == "os":
            if pooled.shape[-1] < self.num_nodes:
                pad = pooled.new_zeros(pooled.shape[0], self.num_nodes - pooled.shape[-1])
                pooled_os = torch.cat([pooled, pad], dim=-1)
            else:
                pooled_os = pooled[:, : self.num_nodes]
            pooled_etth = pooled.new_zeros(pooled.shape[0], etth1_in_dim)
        else:
            pooled_os = pooled.new_zeros(pooled.shape[0], self.num_nodes)
            if pooled.shape[-1] < etth1_in_dim:
                pad = pooled.new_zeros(pooled.shape[0], etth1_in_dim - pooled.shape[-1])
                pooled_etth = torch.cat([pooled, pad], dim=-1)
            else:
                pooled_etth = pooled[:, :etth1_in_dim]
        return torch.cat([pooled_os, pooled_etth], dim=-1)

    def _routing_weights(self, gate_input: torch.Tensor) -> torch.Tensor:
        logits = self.gate(gate_input)
        weights = F.softmax(logits, dim=-1)
        if self.routing_mode == "hard":
            topv, topi = torch.topk(weights, k=min(self.routing_k, self.num_experts), dim=-1)
            hard = torch.zeros_like(weights)
            hard.scatter_(1, topi, topv)
            weights = hard / torch.clamp(hard.sum(dim=-1, keepdim=True), min=1e-8)
        elif self.routing_mode == "soft":
            if self.routing_k < self.num_experts:
                topv, topi = torch.topk(weights, k=self.routing_k, dim=-1)
                pruned = torch.zeros_like(weights)
                pruned.scatter_(1, topi, topv)
                weights = pruned / torch.clamp(pruned.sum(dim=-1, keepdim=True), min=1e-8)
        else:
            raise ValueError(f"Unknown routing_mode: {self.routing_mode}")
        return weights

    def _graph_forward(self, node_x: torch.Tensor, routing: torch.Tensor) -> torch.Tensor:
        bank = self.template_bank if self.use_template_prior else self._learned_template_bank()
        adj = torch.einsum("be,enm->bnm", routing, bank)
        h = node_x
        for layer in self.graph_layers:
            if self.use_pyg:
                h = layer(h, adj)
                h = F.gelu(h)
            else:
                h = layer(h, adj)
                h = F.gelu(h)
        return self.node_norm(h)

    def _learned_template_bank(self) -> torch.Tensor:
        bank = 0.5 * (self.template_bank_param + self.template_bank_param.transpose(-1, -2))
        eye = torch.eye(self.num_nodes, device=bank.device).unsqueeze(0)
        return bank * (1.0 - eye)

    def forward(self, x: torch.Tensor, task: str) -> Dict[str, torch.Tensor]:
        if task == "hcp":
            task = "os"
        if task not in {"os", "etth1"}:
            raise ValueError(f"Unsupported task: {task}")

        if task == "os":
            adapter = self.os_adapter
        else:
            adapter = self.etth1_adapter

        pooled = x.mean(dim=1)
        node_latent = adapter(pooled).reshape(x.shape[0], self.num_nodes, self.hidden_dim)
        node_latent = self.dropout(node_latent)

        gate_input = self._pool_for_gate(x, task=task, etth1_in_dim=self.etth1_adapter.in_features)
        routing = self._routing_weights(gate_input)

        graph_out = self._graph_forward(node_latent, routing)
        graph_pool = graph_out.mean(dim=1)

        if task == "os":
            logits = self.os_head(graph_pool)
            return {"logits": logits, "routing_weights": routing}

        pred = self.etth1_head(graph_pool).reshape(x.shape[0], self.pred_len, self.etth1_out_dim)
        return {"pred": pred, "routing_weights": routing}
