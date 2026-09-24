"""A–D 모델 — 재설계 프로토콜 v1.1 §6 구현.

의존성은 torch 다. **torch_geometric 을 import 하지 않는다.**
기존 `mobse/models/mobse.py:93-98` 은 PyG 설치 여부로 `DenseGCNConv` 와 자체
`DenseGraphLayer` 를 갈아탔다(차단 항목 U21). 프로토콜 §6 은 "명시적인 dense
tensor backend 하나를 사용하며 PyG 설치 유무로 연산을 바꾸지 않는다"고 규정하므로
여기서는 dense 구현 하나만 둔다.

네 cell 은 bank 와 gate 의 조합이다.

===  ====================  =========================
cell  고정 bank             routing
===  ====================  =========================
A     training-rest brain   FC 입력 의존 dynamic gate
B     A 와 동일             학습 logits 3개 (입력 비의존)
C     공동 ROI-permuted null A 와 같은 gate
D     C 와 동일             B 와 같은 fixed mixture
===  ====================  =========================

구조 규칙:

* ROI encoder 는 모든 ROI 에 **동일하게** 적용된다. graph 전에는 ROI 간 혼합도,
  ROI ID embedding 도 없다.
* Conv1d(1→16→32, kernel=3, padding=1), 각 층 GELU·dropout. Conv 후 시간축
  mean 과 std(correction=0)를 결합한 64차원을 Linear(64→32)로 줄인다.
* dynamic gate: PCA10 → Linear32 → GELU → Linear3 → softmax(temperature=1).
* fixed gate: 학습 logits 3개의 softmax. **uniform 과 다르다.**
* top-k, sample entropy loss, balance loss 는 모두 off.
* gate 의 FC bypass 를 prediction head 에 추가하지 않는다.
* ``S(x) = Σ_k π_k(x) S_k`` 이며 **혼합 뒤 다시 normalize 하지 않는다.**
* 공유 graph layer 2개: ``H_next = LayerNorm(H + Dropout(GELU(S(x)HW + b)))``.
* ROI mean pooling 후 Linear(32→2).
* **bank 는 optimizer 에서 제외한다** (buffer 로 등록).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple

import torch
from torch import Tensor, nn

BACKEND = "dense"          # 명시적 단일 backend. PyG 분기 없음 (U21).
N_EXPERTS = 3
N_CLASSES = 2
GATE_TEMPERATURE = 1.0


class ModelError(RuntimeError):
    """모델 구성 규칙 위반."""


@dataclass(frozen=True)
class ModelConfig:
    """A–D 공통 구조 설정. cell 은 bank/gate 조합만 바꾼다."""

    n_roi: int = 100
    n_samples: int = 30
    conv_channels: Tuple[int, int] = (16, 32)
    hidden_dim: int = 32
    pca_dim: int = 10
    gate_hidden: int = 32
    n_graph_layers: int = 2
    dropout: float = 0.1
    n_experts: int = N_EXPERTS
    n_classes: int = N_CLASSES

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


class ROIEncoder(nn.Module):
    """모든 ROI 에 동일하게 적용되는 1D encoder. ROI 간 혼합이 없다."""

    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()
        c1, c2 = cfg.conv_channels
        self.conv1 = nn.Conv1d(1, c1, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(c1, c2, kernel_size=3, padding=1)
        self.act = nn.GELU()
        self.drop = nn.Dropout(cfg.dropout)
        self.proj = nn.Linear(2 * c2, cfg.hidden_dim)
        self.n_roi = cfg.n_roi

    def forward(self, x: Tensor) -> Tensor:
        """``(B, n_roi, T)`` → ``(B, n_roi, hidden)``.

        ROI 축을 batch 로 접어 conv 를 돌리므로 ROI 간 정보가 섞이지 않는다.
        """
        if x.dim() != 3:
            raise ModelError(f"입력은 (B, n_roi, T) 여야 한다: {tuple(x.shape)}")
        b, r, t = x.shape
        h = x.reshape(b * r, 1, t)
        h = self.drop(self.act(self.conv1(h)))
        h = self.drop(self.act(self.conv2(h)))
        mean = h.mean(dim=2)
        std = h.std(dim=2, correction=0)
        feat = torch.cat([mean, std], dim=1)
        return self.proj(feat).reshape(b, r, -1)


class DynamicGate(nn.Module):
    """FC 입력 의존 gate: PCA10 → 32 → GELU → 3 → softmax."""

    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(cfg.pca_dim, cfg.gate_hidden),
            nn.GELU(),
            nn.Linear(cfg.gate_hidden, cfg.n_experts),
        )
        self.temperature = GATE_TEMPERATURE

    def forward(self, pca: Tensor) -> Tensor:
        if pca is None:
            raise ModelError("dynamic gate 에 PCA feature 가 필요하다")
        return torch.softmax(self.net(pca) / self.temperature, dim=-1)


class FixedGate(nn.Module):
    """입력 비의존 gate: 학습되는 logits 3개의 softmax. uniform 이 아니다."""

    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()
        self.logits = nn.Parameter(torch.zeros(cfg.n_experts))
        self.temperature = GATE_TEMPERATURE

    def forward(self, batch_size: int, device: torch.device) -> Tensor:
        w = torch.softmax(self.logits / self.temperature, dim=-1)
        return w.unsqueeze(0).expand(batch_size, -1).to(device)


class DenseGraphLayer(nn.Module):
    """``H_next = LayerNorm(H + Dropout(GELU(S H W + b)))``. 단일 dense backend."""

    def __init__(self, dim: int, dropout: float) -> None:
        super().__init__()
        self.lin = nn.Linear(dim, dim)
        self.act = nn.GELU()
        self.drop = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(dim)

    def forward(self, h: Tensor, s: Tensor) -> Tensor:
        msg = torch.bmm(s, h)
        return self.norm(h + self.drop(self.act(self.lin(msg))))


class MoBSEv2(nn.Module):
    """A–D 를 bank/gate 조합으로 표현하는 단일 모델.

    Args:
        cfg: 구조 설정.
        template_bank: ``(k, n_roi, n_roi)`` 정규화된 bank. **buffer 로 등록되어
            optimizer 에서 제외된다.**
        routing: ``"dynamic"`` 또는 ``"fixed"``.
    """

    def __init__(self, cfg: ModelConfig, template_bank: Tensor,
                 routing: str = "dynamic") -> None:
        super().__init__()
        if routing not in ("dynamic", "fixed"):
            raise ModelError(f"routing 은 dynamic|fixed 여야 한다: {routing!r}")
        bank = torch.as_tensor(template_bank, dtype=torch.float32)
        if bank.dim() != 3 or bank.shape[1] != bank.shape[2]:
            raise ModelError(f"bank 모양이 (k, n, n) 이 아니다: {tuple(bank.shape)}")
        if bank.shape[0] != cfg.n_experts:
            raise ModelError(f"expert 수 불일치: {cfg.n_experts} vs {bank.shape[0]}")
        if bank.shape[1] != cfg.n_roi:
            raise ModelError(f"ROI 수 불일치: {cfg.n_roi} vs {bank.shape[1]}")

        self.cfg = cfg
        self.routing = routing
        self.backend = BACKEND
        self.register_buffer("template_bank", bank)     # optimizer 제외
        self.encoder = ROIEncoder(cfg)
        self.gate = DynamicGate(cfg) if routing == "dynamic" else FixedGate(cfg)
        self.graph_layers = nn.ModuleList(
            [DenseGraphLayer(cfg.hidden_dim, cfg.dropout)
             for _ in range(cfg.n_graph_layers)])
        self.head = nn.Linear(cfg.hidden_dim, cfg.n_classes)

    # ------------------------------------------------------------------ #

    def routing_weights(self, batch_size: int, pca: Optional[Tensor],
                        device: torch.device) -> Tensor:
        if self.routing == "dynamic":
            return self.gate(pca)
        return self.gate(batch_size, device)

    def mix(self, weights: Tensor) -> Tensor:
        """``S(x) = Σ_k π_k S_k``. **재정규화하지 않는다.**"""
        return torch.einsum("be,enm->bnm", weights, self.template_bank)

    def forward(self, x: Tensor, pca: Optional[Tensor] = None,
                *, routing_override: Optional[Tensor] = None
                ) -> Dict[str, Tensor]:
        """``(B, n_roi, T)`` 와 선택적 PCA feature 로 logits 를 낸다.

        Args:
            routing_override: 주면 gate 대신 이 weight 를 쓴다. 보조 분석의
                routing 개입(프로토콜 §9)과 T09 검사에 쓴다.

        Returns:
            ``{"logits", "routing", "graph"}``.
        """
        b = x.shape[0]
        w = (routing_override if routing_override is not None
             else self.routing_weights(b, pca, x.device))
        if w.shape != (b, self.cfg.n_experts):
            raise ModelError(f"routing weight 모양이 잘못됐다: {tuple(w.shape)}")
        s = self.mix(w)
        h = self.encoder(x)
        for layer in self.graph_layers:
            h = layer(h, s)
        pooled = h.mean(dim=1)                    # ROI mean pooling
        return {"logits": self.head(pooled), "routing": w, "graph": s}

    # ------------------------------------------------------------------ #

    def trainable_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def bank_is_frozen(self) -> bool:
        """bank 가 parameter 가 아니라 buffer 인지 확인한다."""
        names = {n for n, _ in self.named_parameters()}
        return "template_bank" not in names and \
            "template_bank" in dict(self.named_buffers())


CELL_SPEC: Dict[str, Dict[str, str]] = {
    "A": {"bank": "brain", "routing": "dynamic"},
    "B": {"bank": "brain", "routing": "fixed"},
    "C": {"bank": "null", "routing": "dynamic"},
    "D": {"bank": "null", "routing": "fixed"},
}


def build_cell(cell: str, cfg: ModelConfig, brain_bank: Tensor,
               null_bank: Tensor) -> MoBSEv2:
    """cell 이름으로 모델을 만든다. A/B 는 같은 bank, C/D 는 같은 null 을 참조한다."""
    if cell not in CELL_SPEC:
        raise ModelError(f"알 수 없는 cell: {cell!r}. 허용: {sorted(CELL_SPEC)}")
    spec = CELL_SPEC[cell]
    bank = brain_bank if spec["bank"] == "brain" else null_bank
    return MoBSEv2(cfg, bank, routing=spec["routing"])


def save_checkpoint(model: MoBSEv2, path) -> Dict[str, object]:
    """구조 설정과 backend 를 함께 저장한다. 재로드 시 대조한다."""
    payload = {"backend": model.backend, "routing": model.routing,
               "config": model.cfg.as_dict(), "state_dict": model.state_dict()}
    torch.save(payload, path)
    return {"backend": model.backend, "routing": model.routing}


def load_checkpoint(path, brain_bank: Tensor, null_bank: Tensor,
                    cell: str) -> MoBSEv2:
    """checkpoint 를 되살린다. backend 나 구조가 다르면 실패한다 (T10)."""
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload.get("backend") != BACKEND:
        raise ModelError(
            f"backend 불일치: {payload.get('backend')!r} vs {BACKEND!r}. "
            "설치 환경에 따라 연산이 바뀌지 않아야 한다 (U21)")
    cfg = ModelConfig(**payload["config"])
    model = build_cell(cell, cfg, brain_bank, null_bank)
    if model.routing != payload["routing"]:
        raise ModelError(f"routing 불일치: {model.routing} vs {payload['routing']}")
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model


# --------------------------------------------------------------------------- #
# §6 구조 비교 2종 — 모델 구조만. 학습·선택 규칙은 여기서 정하지 않는다.
# --------------------------------------------------------------------------- #

#: §6 구조 비교 표의 두 행. key 는 구현 편의 이름이다 (계획서 ID 아님).
COMPARATOR_SPEC: Dict[str, str] = {
    "NG": "ROI encoder pooled feature + PCA FC10 fusion MLP (no-graph comparator)",
    "SG": "training-rest single average graph + 동일 encoder/head",
}
#: fusion MLP 은닉 폭. **구현 선택** — §6 S 후보 MLP·dynamic gate 와 같은 32.
FUSION_HIDDEN = 32


class FusionMLPComparator(nn.Module):
    """§6 구조 비교 "ROI encoder pooled feature + PCA FC10 fusion MLP".

    A–D 와 같은 ``ROIEncoder`` 뒤 ROI mean pooling(graph layer 없음) 한 32 차원과
    fold 변환의 PCA FC10 을 이어 붙여
    ``Linear(32+10→32) → GELU → Dropout(p) → Linear(32→2)`` 로 분류한다.
    graph·bank·gate 가 없다. 층 구성은 **구현 선택**이다 (결정 아님).
    """

    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.backend = BACKEND
        self.routing = "none"
        self.encoder = ROIEncoder(cfg)            # A–D 와 같은 순서로 먼저 만든다
        self.fusion = nn.Sequential(
            nn.Linear(cfg.hidden_dim + cfg.pca_dim, FUSION_HIDDEN),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
        )
        self.head = nn.Linear(FUSION_HIDDEN, cfg.n_classes)

    def forward(self, x: Tensor, pca: Optional[Tensor] = None,
                *, routing_override: Optional[Tensor] = None) -> Dict[str, Tensor]:
        if routing_override is not None:
            raise ModelError("no-graph comparator 에는 routing 이 없다")
        if pca is None:
            raise ModelError("fusion MLP 에 PCA FC10 feature 가 필요하다")
        if pca.dim() != 2 or pca.shape != (x.shape[0], self.cfg.pca_dim):
            raise ModelError(f"PCA feature 모양이 잘못됐다: {tuple(pca.shape)}")
        pooled = self.encoder(x).mean(dim=1)      # ROI mean pooling
        z = self.fusion(torch.cat([pooled, pca], dim=1))
        return {"logits": self.head(z)}

    def trainable_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class SingleGraphComparator(nn.Module):
    """§6 구조 비교 "training-rest single average graph + 동일 encoder/head".

    A–D 와 같은 ``ROIEncoder``·``DenseGraphLayer`` ×2·ROI mean pooling·
    ``Linear(32→2)`` 에 고정 graph 하나(buffer, optimizer 제외)를 쓴다. gate 가 없고
    PCA feature 는 받더라도 예측에 쓰지 않는다 (B/D 와 같은 규칙).
    bank ``[S, S, S]`` 인 A–D 모델과 가중치를 맞추면 출력이 같다 (시험).
    """

    def __init__(self, cfg: ModelConfig, graph: Tensor) -> None:
        super().__init__()
        g = torch.as_tensor(graph, dtype=torch.float32)
        if g.dim() != 2 or g.shape[0] != g.shape[1]:
            raise ModelError(f"graph 모양이 (n, n) 이 아니다: {tuple(g.shape)}")
        if g.shape[0] != cfg.n_roi:
            raise ModelError(f"ROI 수 불일치: {cfg.n_roi} vs {g.shape[0]}")
        if not torch.isfinite(g).all():
            raise ModelError("graph 에 유한하지 않은 값이 있다")
        self.cfg = cfg
        self.backend = BACKEND
        self.routing = "none"
        self.register_buffer("graph", g)          # optimizer 제외
        self.encoder = ROIEncoder(cfg)            # A–D 와 같은 순서로 먼저 만든다
        self.graph_layers = nn.ModuleList(
            [DenseGraphLayer(cfg.hidden_dim, cfg.dropout)
             for _ in range(cfg.n_graph_layers)])
        self.head = nn.Linear(cfg.hidden_dim, cfg.n_classes)

    def forward(self, x: Tensor, pca: Optional[Tensor] = None,
                *, routing_override: Optional[Tensor] = None) -> Dict[str, Tensor]:
        if routing_override is not None:
            raise ModelError("single graph comparator 에는 routing 이 없다")
        b = x.shape[0]
        s = self.graph.unsqueeze(0).expand(b, -1, -1)
        h = self.encoder(x)
        for layer in self.graph_layers:
            h = layer(h, s)
        return {"logits": self.head(h.mean(dim=1)), "graph": s}

    def trainable_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def bank_is_frozen(self) -> bool:
        names = {n for n, _ in self.named_parameters()}
        return "graph" not in names and "graph" in dict(self.named_buffers())


def build_comparator(name: str, cfg: ModelConfig,
                     single_graph: Optional[Tensor] = None) -> nn.Module:
    """구조 비교 모델을 이름으로 만든다. ``SG`` 는 graph 가 반드시 필요하다."""
    if name not in COMPARATOR_SPEC:
        raise ModelError(f"알 수 없는 구조 비교: {name!r}. 허용: {sorted(COMPARATOR_SPEC)}")
    if name == "NG":
        if single_graph is not None:
            raise ModelError("no-graph comparator 에 graph 를 줄 수 없다")
        return FusionMLPComparator(cfg)
    if single_graph is None:
        raise ModelError("SG 에는 training-rest single average graph 가 필요하다")
    return SingleGraphComparator(cfg, single_graph)
