from __future__ import annotations

import torch

from mobse.config import ExperimentConfig
from mobse.models.baselines import SparseTransformerBaseline, StandardMoE, TransformerBaseline
from mobse.models.mobse import MoBSEModel


def build_model(cfg: ExperimentConfig, template_bank: torch.Tensor):
    arch = cfg.model.arch
    common = dict(
        os_in_dim=cfg.model.num_nodes,
        etth1_in_dim=cfg.model.etth1_in_dim,
        hidden_dim=cfg.model.hidden_dim,
        dropout=cfg.model.dropout,
        os_num_classes=cfg.model.os_num_classes,
        pred_len=cfg.data.etth1.pred_len,
        etth1_out_dim=cfg.model.etth1_out_dim,
        etth1_temporal_encoder=cfg.model.etth1_temporal_encoder,
    )

    if arch == "mobse":
        return MoBSEModel(
            num_nodes=cfg.model.num_nodes,
            hidden_dim=cfg.model.hidden_dim,
            num_experts=cfg.model.num_experts,
            num_graph_layers=cfg.model.num_graph_layers,
            dropout=cfg.model.dropout,
            routing_k=cfg.model.routing_k,
            routing_mode=cfg.model.routing_mode,
            os_num_classes=cfg.model.os_num_classes,
            etth1_in_dim=cfg.model.etth1_in_dim,
            etth1_out_dim=cfg.model.etth1_out_dim,
            etth1_temporal_encoder=cfg.model.etth1_temporal_encoder,
            pred_len=cfg.data.etth1.pred_len,
            template_bank=template_bank,
            use_template_prior=cfg.model.use_template_prior,
        )
    if arch == "transformer":
        return TransformerBaseline(**common)
    if arch == "sparse_transformer":
        return SparseTransformerBaseline(window=cfg.model.sparse_attn_window, **common)
    if arch == "moe":
        return StandardMoE(num_experts=cfg.model.num_experts, **common)

    raise ValueError(f"Unknown architecture: {arch}")
