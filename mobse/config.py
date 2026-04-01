from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class OSDataConfig:
    root_dir: str = "data/os"
    timeseries_dir: str = "data/os/timeseries"
    nifti_manifest: str = ""
    tr: float = 0.72
    openneuro_use_image_tr: bool = True
    openneuro_require_exact_nodes: bool = True
    usable_target_subjects: int = 0
    dataset_chunk_size: int = 25
    subjects_limit: int = 200
    states: List[str] = field(
        default_factory=lambda: ["rest", "wm", "motor", "language", "attention"]
    )
    atlas_nodes_primary: int = 100
    atlas_nodes_secondary: int = 200
    window_len: int = 64
    stride: int = 16
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    train_subject_prefixes: List[str] = field(default_factory=list)
    val_subject_prefixes: List[str] = field(default_factory=list)
    test_subject_prefixes: List[str] = field(default_factory=list)
    random_seed: int = 42
    nuisance_strategy: str = "paper_compcor_gsr"
    nuisance_include_compcor: bool = True
    nuisance_compcor_components: int = 5
    nuisance_include_gsr: bool = True
    nuisance_add_derivatives: bool = True
    nuisance_add_quadratic: bool = True
    nuisance_detrend: bool = True
    nuisance_high_pass: float = 0.008
    nuisance_low_pass: float = 0.1


# Backward compatibility alias.
HCPDataConfig = OSDataConfig


@dataclass
class ETTh1DataConfig:
    csv_path: str = "data/reference_raw/ETTh1.csv"
    target_col: str = "OT"
    seq_len: int = 96
    pred_len: int = 24
    train_ratio: float = 0.7
    val_ratio: float = 0.15


@dataclass
class DataConfig:
    os: OSDataConfig = field(default_factory=OSDataConfig)
    etth1: ETTh1DataConfig = field(default_factory=ETTh1DataConfig)

    @property
    def hcp(self) -> OSDataConfig:
        # Backward compatibility for older code/config references.
        return self.os


@dataclass
class TemplateConfig:
    atlas_name: str = "schaefer"
    atlas_nodes_options: List[int] = field(default_factory=lambda: [100, 200])
    sparsity_levels: List[float] = field(default_factory=lambda: [0.1, 0.2, 0.3])
    default_sparsity: float = 0.2
    threshold_mode: str = "proportional"
    fisher_z_average: bool = True
    output_name: str = "template_bank.npz"


@dataclass
class ModelConfig:
    arch: str = "mobse"  # mobse | transformer | sparse_transformer | moe
    hidden_dim: int = 64
    num_nodes: int = 100
    num_graph_layers: int = 2
    dropout: float = 0.1
    num_experts: int = 5
    routing_k: int = 2
    routing_mode: str = "soft"  # soft | hard
    os_num_classes: int = 5
    etth1_in_dim: int = 7
    etth1_out_dim: int = 1
    etth1_temporal_encoder: str = "mean"  # mean | gru
    sparse_attn_window: int = 16
    use_template_prior: bool = True
    template_bank_path: str = ""
    os_windows_path: str = ""

    @property
    def hcp_num_classes(self) -> int:
        return self.os_num_classes

    @hcp_num_classes.setter
    def hcp_num_classes(self, value: int) -> None:
        self.os_num_classes = value

    @property
    def hcp_windows_path(self) -> str:
        return self.os_windows_path

    @hcp_windows_path.setter
    def hcp_windows_path(self, value: str) -> None:
        self.os_windows_path = value


@dataclass
class TrainConfig:
    tasks: List[str] = field(default_factory=lambda: ["os", "etth1"])
    batch_size: int = 32
    epochs: int = 20
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    grad_clip_norm: float = 1.0
    seeds: List[int] = field(default_factory=lambda: [42, 43, 44])
    os_loss_weight: float = 1.0
    etth1_loss_weight: float = 1.0
    etth1_loss_type: str = "huber"  # huber | mse | mae
    etth1_huber_delta: float = 1.0
    normalize_task_losses: bool = True
    task_loss_norm_batches: int = 8
    selection_metric: str = "weighted_normalized_loss"  # raw_loss | weighted_raw_loss | weighted_normalized_loss
    early_stopping_patience: int = 0
    early_stopping_min_delta: float = 0.0
    use_amp: bool = True
    device: str = "cuda"

    @property
    def hcp_loss_weight(self) -> float:
        return self.os_loss_weight

    @hcp_loss_weight.setter
    def hcp_loss_weight(self, value: float) -> None:
        self.os_loss_weight = value


@dataclass
class EvalConfig:
    metrics: List[str] = field(default_factory=lambda: ["accuracy", "f1", "mae", "mse"])
    profile_batches: int = 20
    latency_warmup: int = 5
    output_prefix: str = "eval"


@dataclass
class ArtifactConfig:
    root_dir: str = "artifacts"
    run_id: Optional[str] = None


@dataclass
class ExperimentConfig:
    data: DataConfig = field(default_factory=DataConfig)
    template: TemplateConfig = field(default_factory=TemplateConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    artifacts: ArtifactConfig = field(default_factory=ArtifactConfig)


def _merge_dict(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _dataclass_to_dict(config: ExperimentConfig) -> Dict[str, Any]:
    return {
        "data": {
            "os": vars(config.data.os),
            "etth1": vars(config.data.etth1),
        },
        "template": vars(config.template),
        "model": vars(config.model),
        "train": vars(config.train),
        "eval": vars(config.eval),
        "artifacts": vars(config.artifacts),
    }


def _dict_to_config(payload: Dict[str, Any]) -> ExperimentConfig:
    data = payload.get("data", {})
    model_payload = dict(payload.get("model", {}))
    train_payload = dict(payload.get("train", {}))

    if "os_num_classes" not in model_payload and "hcp_num_classes" in model_payload:
        model_payload["os_num_classes"] = model_payload["hcp_num_classes"]
    if "os_windows_path" not in model_payload and "hcp_windows_path" in model_payload:
        model_payload["os_windows_path"] = model_payload["hcp_windows_path"]

    if "os_loss_weight" not in train_payload and "hcp_loss_weight" in train_payload:
        train_payload["os_loss_weight"] = train_payload["hcp_loss_weight"]
    if "tasks" in train_payload and isinstance(train_payload["tasks"], list):
        train_payload["tasks"] = ["os" if t == "hcp" else t for t in train_payload["tasks"]]
    if "selection_metric" not in train_payload and "val_score_mode" in train_payload:
        train_payload["selection_metric"] = train_payload["val_score_mode"]

    return ExperimentConfig(
        data=DataConfig(
            os=OSDataConfig(**(data.get("os") or data.get("hcp", {}))),
            etth1=ETTh1DataConfig(**data.get("etth1", {})),
        ),
        template=TemplateConfig(**payload.get("template", {})),
        model=ModelConfig(**model_payload),
        train=TrainConfig(**train_payload),
        eval=EvalConfig(**payload.get("eval", {})),
        artifacts=ArtifactConfig(**payload.get("artifacts", {})),
    )


def load_config(path: str | Path) -> ExperimentConfig:
    base = _dataclass_to_dict(ExperimentConfig())
    with open(path, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}
    merged = _merge_dict(base, user_cfg)
    cfg = _dict_to_config(merged)

    if not cfg.artifacts.run_id:
        cfg.artifacts.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return cfg


def save_config(config: ExperimentConfig, path: str | Path) -> None:
    payload = _dataclass_to_dict(config)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)
