"""v3 모델 구조 시험 — 결정 28-2.

이 시험이 고정하려는 것은 **정렬을 쓸 수 있는 통로가 열렸는가** 하나다.
v1 은 ``C(x) = A(Pᵀx)`` 가 성립해서 (ROI 공유 encoder · ROI 평균 readout) 정렬이
성능에 들어갈 길이 이웃 평활화뿐이었다. 그 성질이 되살아나면 H2 를 검정할 수 없다.

읽는 법: 차이의 **크기는 성능을 뜻하지 않는다** (학습 전 가중치다). 0 인가 아닌가만 본다.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from mobse.v2.models import ModelConfig, MoBSEv2, ModelError
from mobse.v3.models import ROI_STRUCTURES, MoBSEv3

SEED = 1729
N_ROI, T, B = 24, 16, 4
EQUIVARIANT = 1e-5          # float 오차 수준
BROKEN = 1e-4               # 이보다 크면 정렬을 쓸 수 있다


def _bank(rng, n_roi, k):
    out = []
    for _ in range(k):
        m = rng.standard_normal((n_roi, n_roi))
        m = np.abs(m + m.T) / 2
        a = np.where(m >= np.quantile(m, 0.8), m, 0.0)
        np.fill_diagonal(a, 1.0)
        d = np.sqrt(a.sum(1, keepdims=True))
        out.append(a / (d * d.T))
    return torch.tensor(np.stack(out), dtype=torch.float32)


def _equivariance_gap(roi_structure, *, perturb_readout=False):
    """max│C(x) − A(Pᵀx)│ 를 잰다. 0 이면 정렬을 쓸 수 없다 (등변)."""
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    bank = _bank(rng, N_ROI, cfg.n_experts)
    perm = torch.as_tensor(rng.permutation(N_ROI).copy(), dtype=torch.long)
    bank_null = bank[:, perm][:, :, perm]

    a = MoBSEv3(cfg, bank, roi_structure=roi_structure).eval()
    c = MoBSEv3(cfg, bank_null, roi_structure=roi_structure).eval()
    if perturb_readout:
        with torch.no_grad():
            a.roi_readout.copy_(torch.randn(N_ROI, generator=torch.Generator()
                                            .manual_seed(SEED)) * 0.5)
    # bank 는 buffer 라 state_dict 에 들어간다 — 빼고 실어야 C 의 null bank 가 산다.
    state = {k: v for k, v in a.state_dict().items() if k != "template_bank"}
    missing, unexpected = c.load_state_dict(state, strict=False)
    assert not unexpected and list(missing) == ["template_bank"]
    assert torch.equal(c.template_bank, bank_null)

    x = torch.randn(B, N_ROI, T)
    pca = torch.randn(B, cfg.pca_dim)
    inv = torch.empty_like(perm)
    inv[perm] = torch.arange(N_ROI)
    with torch.no_grad():
        lc = c(x, pca)["logits"]
        la_perm = a(x[:, inv], pca)["logits"]
    return float((lc - la_perm).abs().max())


# ------------------------------------------------------------- 등변성

def test_mean_structure_is_equivariant_like_v1():
    """v1 의 성질을 그대로 가진다 — 대조군이다."""
    assert _equivariance_gap("mean") < EQUIVARIANT


def test_mean_structure_matches_v1_model_numerically():
    """같은 가중치라면 v3 의 mean 은 v2 와 같은 logits 를 낸다."""
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    bank = _bank(rng, N_ROI, cfg.n_experts)
    m3 = MoBSEv3(cfg, bank, roi_structure="mean").eval()
    m2 = MoBSEv2(cfg, bank).eval()
    m2.load_state_dict(m3.state_dict(), strict=True)
    x, pca = torch.randn(B, N_ROI, T), torch.randn(B, cfg.pca_dim)
    with torch.no_grad():
        assert torch.allclose(m3(x, pca)["logits"], m2(x, pca)["logits"], atol=1e-6)


def test_embedding_structure_breaks_equivariance():
    assert _equivariance_gap("embedding") > BROKEN


def test_readout_starts_identical_to_the_mean_structure():
    """``roi_readout`` 을 0 으로 두므로 **학습 전에는** v1 과 같다 (구현 선택).

    두 구조가 같은 출발점에서 갈라지게 하려는 선택이다. 그래서 초기 시점의
    등변성 측정은 0 이 나온다 — 설계 기록의 1.27e−03 은 무작위 초기화로 잰 값이었다.
    """
    assert _equivariance_gap("readout") < EQUIVARIANT


def test_readout_breaks_equivariance_once_its_weights_move():
    """학습이 ``roi_readout`` 을 움직이면 정렬을 쓸 수 있게 된다."""
    assert _equivariance_gap("readout", perturb_readout=True) > BROKEN


# ------------------------------------------------------------- 구성 규칙

@pytest.mark.parametrize("structure", ROI_STRUCTURES)
def test_every_structure_runs_and_shapes_are_right(structure):
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    rng = np.random.default_rng(SEED)
    m = MoBSEv3(cfg, _bank(rng, N_ROI, cfg.n_experts), roi_structure=structure).eval()
    out = m(torch.randn(B, N_ROI, T), torch.randn(B, cfg.pca_dim))
    assert out["logits"].shape == (B, cfg.n_classes)
    assert out["routing"].shape == (B, cfg.n_experts)
    assert out["graph"].shape == (B, N_ROI, N_ROI)


def test_unknown_structure_is_refused():
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    rng = np.random.default_rng(SEED)
    with pytest.raises(ModelError, match="roi_structure"):
        MoBSEv3(cfg, _bank(rng, N_ROI, cfg.n_experts), roi_structure="whatever")


def test_unknown_routing_is_refused():
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    rng = np.random.default_rng(SEED)
    with pytest.raises(ModelError, match="routing"):
        MoBSEv3(cfg, _bank(rng, N_ROI, cfg.n_experts), routing="sideways")


def test_bank_is_a_buffer_and_never_an_optimizer_parameter():
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    rng = np.random.default_rng(SEED)
    m = MoBSEv3(cfg, _bank(rng, N_ROI, cfg.n_experts), roi_structure="embedding")
    assert all(p is not m.template_bank for p in m.parameters())
    assert "template_bank" in dict(m.named_buffers())


def test_bank_travels_in_state_dict_which_is_the_trap_to_remember():
    """bank 가 ``state_dict`` 에 들어간다는 사실 자체를 고정한다.

    2026-09-29 설계 측정에서 A 의 state 를 C 에 통째로 실어 null bank 가 덮였고
    ``C(x) = A(x)`` 가 되어 버렸다. 그 성질이 조용히 바뀌면 같은 사고가 되풀이된다.
    """
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    rng = np.random.default_rng(SEED)
    m = MoBSEv3(cfg, _bank(rng, N_ROI, cfg.n_experts))
    assert "template_bank" in m.state_dict()


@pytest.mark.parametrize("structure,extra", [("mean", 0), ("embedding", N_ROI * 32),
                                             ("readout", N_ROI)])
def test_parameter_count_grows_only_by_the_new_structure(structure, extra):
    cfg = ModelConfig(n_roi=N_ROI, n_samples=T)
    rng = np.random.default_rng(SEED)
    bank = _bank(rng, N_ROI, cfg.n_experts)
    base = sum(p.numel() for p in MoBSEv3(cfg, bank, roi_structure="mean").parameters())
    got = sum(p.numel() for p in MoBSEv3(cfg, bank, roi_structure=structure).parameters())
    assert got - base == extra


# --------------------------------------------------------------------------- #
# checkpoint — ROI 구조를 함께 적는다 (2026-10-01 추가)
# --------------------------------------------------------------------------- #


def test_checkpoint_round_trip_keeps_the_roi_structure(tmp_path):
    import torch
    from mobse.v2.models import BACKEND, ModelConfig
    from mobse.v3.models import MoBSEv3, load_checkpoint, save_checkpoint

    cfg = ModelConfig(n_roi=8, n_samples=12, pca_dim=4, dropout=0.1)
    bank = torch.rand(cfg.n_experts, 8, 8)
    model = MoBSEv3(cfg, bank, routing="dynamic", roi_structure="readout")
    assert model.backend == BACKEND          # v1 의 save 경로가 요구하는 속성

    path = tmp_path / "ckpt.pt"
    info = save_checkpoint(model, path)
    assert info["roi_structure"] == "readout"
    back = load_checkpoint(path, bank)
    assert back.roi_structure == "readout"
    assert back.routing == "dynamic"


def test_a_checkpoint_without_the_structure_is_refused(tmp_path):
    """v1 판본 payload 를 기본값으로 메우지 않는다 — 조용히 다른 모델이 된다."""
    import torch
    from mobse.v2.models import BACKEND, ModelConfig
    from mobse.v3.models import ModelError, load_checkpoint

    cfg = ModelConfig(n_roi=8, n_samples=12, pca_dim=4, dropout=0.1)
    bank = torch.rand(cfg.n_experts, 8, 8)
    path = tmp_path / "old.pt"
    torch.save({"backend": BACKEND, "routing": "dynamic",
                "config": cfg.as_dict(), "state_dict": {}}, path)
    with pytest.raises(ModelError, match="roi_structure 가 없다"):
        load_checkpoint(path, bank)
