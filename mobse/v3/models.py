"""ROI 정체를 쓸 수 있는 구조 — 결정 28-2 (2026-09-29).

v1 의 ``mobse.v2.models.MoBSEv2`` 는 **ROI 순열에 등변**이다. ROI 공유 encoder ·
공유 Linear · ROI 평균 readout 이라 ``C(x) = A(Pᵀx)`` 가 성립한다 (수치 확인:
midreview 1절 1.2e−07, 2026-09-29 재현 1.19e−07). 그러면 "정렬된 bank" 와
"ROI 를 섞은 bank" 의 차이가 모델에 들어갈 통로가 **이웃 평활화 하나뿐**이고,
H2 (A−C) 는 사실상 그 통로만 검정하게 된다.

이 모듈은 등변성을 깨는 두 구조를 더한다 (결정 28-2 로 **둘 다** 돌려 비교한다).

* ``"embedding"`` — ROI 마다 학습되는 벡터를 encoder 출력에 더한다. 가장 작은 변경.
* ``"readout"`` — ROI 평균 대신 ROI 별 학습 가중치로 합한다.
* ``"mean"`` — v1 과 같은 동작. 대조군으로 남긴다.

**측정 (2026-09-29, 학습 전 무작위 가중치·seed 1729·ROI 100)**: ``mean`` 은
max│C(x) − A(Pᵀx)│ = 1.19e−07 (등변), ``embedding`` 은 5.68e−03, ``readout`` 은
1.27e−03 이다. 크기는 성능을 뜻하지 않는다 — 0 인가 아닌가만 읽는다.
``tests/v3/test_models_v3.py`` 가 이 성질을 고정한다.

구조 부품 (encoder · gate · graph layer) 은 동결된 v2 를 그대로 쓴다.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
from torch import Tensor, nn

from mobse.v2.models import (  # 동결된 v1 부품
    DenseGraphLayer,
    DynamicGate,
    FixedGate,
    ModelConfig,
    ModelError,
    ROIEncoder,
)

__all__ = ["ROI_STRUCTURES", "MoBSEv3", "ModelConfig", "ModelError"]

#: ROI 정체를 쓰는 방식. ``"mean"`` 은 v1 과 같다 (등변 — 정렬을 쓸 수 없다).
ROI_STRUCTURES: Tuple[str, str, str] = ("mean", "embedding", "readout")

#: ROI embedding 의 초기 크기. 0 이면 학습 시작 시점에 v1 과 완전히 같아져
#: 등변성이 깨지지 않으므로 작은 양수로 둔다.
ROI_EMBEDDING_INIT_STD = 0.1


class MoBSEv3(nn.Module):
    """A–D 를 bank/gate 조합으로 표현하되 ROI 정체를 쓸 수 있는 모델.

    Args:
        cfg: 구조 설정 (v2 의 것을 그대로 쓴다).
        template_bank: ``(k, n_roi, n_roi)`` 정규화된 bank. **buffer 로 등록되어
            optimizer 에서 제외된다.** v1 과 같은 취급이다.
        routing: ``"dynamic"`` 또는 ``"fixed"``.
        roi_structure: ``ROI_STRUCTURES`` 중 하나.

    Note:
        ``template_bank`` 는 buffer 이므로 ``state_dict`` 에 들어간다. 다른 모델의
        state 를 통째로 실으면 bank 까지 덮인다 — A 의 state 를 C 에 실어 null bank 가
        사라진 사고가 2026-09-29 설계 측정에서 있었다. 가중치만 옮길 때는 bank 키를 빼라.
    """

    def __init__(self, cfg: ModelConfig, template_bank: Tensor,
                 routing: str = "dynamic", roi_structure: str = "mean") -> None:
        super().__init__()
        if routing not in ("dynamic", "fixed"):
            raise ModelError(f"routing 은 dynamic|fixed 여야 한다: {routing!r}")
        if roi_structure not in ROI_STRUCTURES:
            raise ModelError(
                f"roi_structure 는 {ROI_STRUCTURES} 중 하나여야 한다: {roi_structure!r}")
        bank = torch.as_tensor(template_bank, dtype=torch.float32)
        if bank.dim() != 3 or bank.shape[1] != bank.shape[2]:
            raise ModelError(f"bank 모양이 (k, n, n) 이 아니다: {tuple(bank.shape)}")
        if bank.shape[0] != cfg.n_experts:
            raise ModelError(f"expert 수 불일치: {cfg.n_experts} vs {bank.shape[0]}")
        if bank.shape[1] != cfg.n_roi:
            raise ModelError(f"ROI 수 불일치: {cfg.n_roi} vs {bank.shape[1]}")

        self.cfg = cfg
        self.routing = routing
        self.roi_structure = roi_structure
        self.register_buffer("template_bank", bank)     # optimizer 제외
        self.encoder = ROIEncoder(cfg)
        self.gate = DynamicGate(cfg) if routing == "dynamic" else FixedGate(cfg)
        self.graph_layers = nn.ModuleList(
            [DenseGraphLayer(cfg.hidden_dim, cfg.dropout)
             for _ in range(cfg.n_graph_layers)])
        self.head = nn.Linear(cfg.hidden_dim, cfg.n_classes)

        if roi_structure == "embedding":
            self.roi_embedding = nn.Parameter(
                torch.randn(cfg.n_roi, cfg.hidden_dim) * ROI_EMBEDDING_INIT_STD)
        elif roi_structure == "readout":
            self.roi_readout = nn.Parameter(torch.zeros(cfg.n_roi))

    # ------------------------------------------------------------------ #

    def routing_weights(self, batch_size: int, pca: Optional[Tensor],
                        device: torch.device) -> Tensor:
        if self.routing == "dynamic":
            return self.gate(pca)
        return self.gate(batch_size, device)

    def mix(self, weights: Tensor) -> Tensor:
        """``S(x) = Σ_k π_k S_k``. **재정규화하지 않는다** (v1 과 같다)."""
        return torch.einsum("be,enm->bnm", weights, self.template_bank)

    def readout(self, h: Tensor) -> Tensor:
        """``(B, n_roi, hidden)`` → ``(B, hidden)``.

        ``"readout"`` 이면 ROI 별 학습 가중치의 softmax 로 합한다. 그 외에는 v1 과
        같은 ROI 평균이다 (``roi_readout`` 이 전부 0 이면 softmax 가 균일이라 평균과
        같지만, 학습되면 갈라진다).
        """
        if self.roi_structure == "readout":
            a = torch.softmax(self.roi_readout, dim=0).view(1, -1, 1)
            return (h * a).sum(dim=1)
        return h.mean(dim=1)

    def forward(self, x: Tensor, pca: Optional[Tensor] = None,
                *, routing_override: Optional[Tensor] = None
                ) -> Dict[str, Tensor]:
        """``(B, n_roi, T)`` 와 선택적 PCA feature 로 logits 를 낸다.

        Args:
            routing_override: 주면 gate 대신 이 weight 를 쓴다 (v1 과 같은 뜻).

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
        if self.roi_structure == "embedding":
            h = h + self.roi_embedding.unsqueeze(0)
        for layer in self.graph_layers:
            h = layer(h, s)
        return {"logits": self.head(self.readout(h)), "routing": w, "graph": s}
