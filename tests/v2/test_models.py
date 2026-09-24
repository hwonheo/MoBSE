"""T06 ROI alignment, T08 routing, T09 mixture, T10 backend/checkpoint."""

from __future__ import annotations

import sys

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from mobse.v2.models import (                     # noqa: E402
    BACKEND, CELL_SPEC, ModelConfig, ModelError, MoBSEv2, build_cell,
    load_checkpoint, save_checkpoint,
)

CFG = ModelConfig(n_roi=8, n_samples=12, hidden_dim=8, gate_hidden=8,
                  pca_dim=10, dropout=0.0)


def _banks(seed=0):
    g = torch.Generator().manual_seed(seed)
    def one():
        a = torch.rand(3, CFG.n_roi, CFG.n_roi, generator=g)
        a = (a + a.transpose(1, 2)) / 2
        return a
    return one(), one()


def _inputs(b=4, seed=1):
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(b, CFG.n_roi, CFG.n_samples, generator=g)
    pca = torch.randn(b, CFG.pca_dim, generator=g)
    return x, pca


# --------------------------------------------------------------------------- #
# 구성
# --------------------------------------------------------------------------- #

def test_cell_spec_matches_protocol_table():
    assert CELL_SPEC["A"] == {"bank": "brain", "routing": "dynamic"}
    assert CELL_SPEC["B"] == {"bank": "brain", "routing": "fixed"}
    assert CELL_SPEC["C"] == {"bank": "null", "routing": "dynamic"}
    assert CELL_SPEC["D"] == {"bank": "null", "routing": "fixed"}


def test_ab_share_bank_and_cd_share_null():
    brain, null = _banks()
    a, b = build_cell("A", CFG, brain, null), build_cell("B", CFG, brain, null)
    c, d = build_cell("C", CFG, brain, null), build_cell("D", CFG, brain, null)
    assert torch.equal(a.template_bank, b.template_bank)
    assert torch.equal(c.template_bank, d.template_bank)
    assert not torch.equal(a.template_bank, c.template_bank)


def test_bank_is_buffer_not_parameter():
    brain, null = _banks()
    for cell in "ABCD":
        m = build_cell(cell, CFG, brain, null)
        assert m.bank_is_frozen(), f"{cell}: bank 가 optimizer 에 들어갔다"


def test_pyg_is_not_imported():
    assert "torch_geometric" not in sys.modules
    import mobse.v2.models as mod
    assert "torch_geometric" not in mod.__dict__
    assert mod.BACKEND == "dense"


def test_unknown_cell_and_shape_mismatch_fail():
    brain, null = _banks()
    with pytest.raises(ModelError, match="알 수 없는 cell"):
        build_cell("E", CFG, brain, null)
    with pytest.raises(ModelError, match="ROI 수 불일치"):
        MoBSEv2(CFG, torch.rand(3, 5, 5))
    with pytest.raises(ModelError, match="expert 수 불일치"):
        MoBSEv2(CFG, torch.rand(4, CFG.n_roi, CFG.n_roi))


# --------------------------------------------------------------------------- #
# T06 — graph 전에는 ROI 간 혼합이 없다
# --------------------------------------------------------------------------- #

def test_changing_one_roi_leaves_other_roi_encodings_untouched():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, _ = _inputs()
    with torch.no_grad():
        h0 = m.encoder(x)
        x2 = x.clone()
        x2[:, 3, :] += 5.0
        h1 = m.encoder(x2)
    assert not torch.allclose(h0[:, 3], h1[:, 3]), "바꾼 ROI 가 반영되지 않았다"
    others = [r for r in range(CFG.n_roi) if r != 3]
    assert torch.allclose(h0[:, others], h1[:, others], atol=1e-6), \
        "graph 전에 ROI 간 정보가 섞였다"


def test_encoder_is_shared_across_roi():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, _ = _inputs(b=1)
    same = x.clone()
    same[:, 5, :] = same[:, 2, :]
    with torch.no_grad():
        h = m.encoder(same)
    assert torch.allclose(h[:, 2], h[:, 5], atol=1e-6), \
        "같은 시계열인데 ROI 위치에 따라 결과가 다르다 (ROI ID embedding 흔적)"


# --------------------------------------------------------------------------- #
# T08 — routing
# --------------------------------------------------------------------------- #

def test_fixed_gate_ignores_input_and_dynamic_does_not():
    brain, null = _banks()
    xa, pa = _inputs(seed=1)
    xb, pb = _inputs(seed=2)

    fixed = build_cell("B", CFG, brain, null).eval()
    with torch.no_grad():
        wa = fixed(xa, pa)["routing"]
        wb = fixed(xb, pb)["routing"]
    assert torch.allclose(wa, wb), "fixed gate 가 입력에 반응했다"

    dyn = build_cell("A", CFG, brain, null).eval()
    with torch.no_grad():
        da = dyn(xa, pa)["routing"]
        db = dyn(xb, pb)["routing"]
    assert not torch.allclose(da, db), "dynamic gate 가 입력에 반응하지 않았다"


def test_routing_weights_are_finite_and_sum_to_one():
    brain, null = _banks()
    for cell in "ABCD":
        m = build_cell(cell, CFG, brain, null).eval()
        x, pca = _inputs()
        with torch.no_grad():
            w = m(x, pca)["routing"]
        assert torch.all(torch.isfinite(w))
        assert torch.allclose(w.sum(dim=-1), torch.ones(w.shape[0]), atol=1e-6)
        assert torch.all(w >= 0)


def test_fixed_gate_is_learnable_and_not_forced_uniform():
    brain, null = _banks()
    m = build_cell("B", CFG, brain, null)
    assert any(p.requires_grad and p.numel() == 3 for p in m.gate.parameters())
    with torch.no_grad():
        m.gate.logits.copy_(torch.tensor([2.0, 0.0, -1.0]))
        w = m.gate(1, torch.device("cpu"))
    assert not torch.allclose(w, torch.full((1, 3), 1 / 3)), "uniform 으로 고정됐다"


def test_gradients_are_finite_for_every_cell():
    brain, null = _banks()
    for cell in "ABCD":
        m = build_cell(cell, CFG, brain, null).train()
        x, pca = _inputs()
        out = m(x, pca)
        loss = torch.nn.functional.cross_entropy(
            out["logits"], torch.tensor([0, 1, 0, 1]))
        loss.backward()
        grads = [p.grad for p in m.parameters() if p.grad is not None]
        assert grads, f"{cell}: gradient 가 없다"
        assert all(torch.all(torch.isfinite(g)) for g in grads)
        assert m.template_bank.grad is None, f"{cell}: bank 에 gradient 가 붙었다"


def test_dynamic_gate_requires_pca_features():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, _ = _inputs()
    with pytest.raises(ModelError, match="PCA"):
        m(x, None)


# --------------------------------------------------------------------------- #
# T09 — mixture
# --------------------------------------------------------------------------- #

def test_one_hot_override_equals_single_template():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, pca = _inputs(b=3)
    w = torch.eye(3)
    with torch.no_grad():
        s = m(x, pca, routing_override=w)["graph"]
    for k in range(3):
        assert torch.allclose(s[k], m.template_bank[k], atol=1e-6)


def test_uniform_override_equals_bank_mean_without_renormalisation():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, pca = _inputs(b=2)
    w = torch.full((2, 3), 1 / 3)
    with torch.no_grad():
        s = m(x, pca, routing_override=w)["graph"]
    assert torch.allclose(s[0], m.template_bank.mean(dim=0), atol=1e-6)
    assert not torch.allclose(s[0].sum(dim=1), torch.ones(CFG.n_roi), atol=1e-3)


def test_override_reproduces_original_gate_output():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, pca = _inputs()
    with torch.no_grad():
        base = m(x, pca)
        again = m(x, pca, routing_override=base["routing"])
    assert torch.allclose(base["logits"], again["logits"], atol=1e-6)


def test_bad_override_shape_fails():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, pca = _inputs(b=4)
    with pytest.raises(ModelError, match="routing weight 모양"):
        m(x, pca, routing_override=torch.full((2, 3), 1 / 3))


# --------------------------------------------------------------------------- #
# T10 — backend / checkpoint
# --------------------------------------------------------------------------- #

def test_checkpoint_roundtrip_preserves_eval_logits(tmp_path):
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, pca = _inputs()
    with torch.no_grad():
        before = m(x, pca)["logits"]
    p = tmp_path / "ckpt.pt"
    info = save_checkpoint(m, p)
    assert info["backend"] == BACKEND
    back = load_checkpoint(p, brain, null, "A")
    with torch.no_grad():
        after = back(x, pca)["logits"]
    assert torch.allclose(before, after, atol=1e-6)


def test_checkpoint_rejects_foreign_backend(tmp_path):
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null)
    p = tmp_path / "ckpt.pt"
    save_checkpoint(m, p)
    payload = torch.load(p, map_location="cpu", weights_only=False)
    payload["backend"] = "pyg"
    torch.save(payload, p)
    with pytest.raises(ModelError, match="backend 불일치"):
        load_checkpoint(p, brain, null, "A")


def test_checkpoint_rejects_wrong_cell(tmp_path):
    brain, null = _banks()
    p = tmp_path / "ckpt.pt"
    save_checkpoint(build_cell("A", CFG, brain, null), p)
    with pytest.raises(ModelError, match="routing 불일치"):
        load_checkpoint(p, brain, null, "B")


def test_parameter_count_is_identical_across_cells_except_gate():
    brain, null = _banks()
    counts = {c: build_cell(c, CFG, brain, null).trainable_parameter_count()
              for c in "ABCD"}
    assert counts["A"] == counts["C"] and counts["B"] == counts["D"]
    assert counts["A"] != counts["B"], "dynamic/fixed gate 의 파라미터 수가 같다"


# --------------------------------------------------------------------------- #
# T16 — classification only
# --------------------------------------------------------------------------- #

def test_model_has_no_forecasting_head():
    brain, null = _banks()
    m = build_cell("A", CFG, brain, null).eval()
    x, pca = _inputs()
    with torch.no_grad():
        out = m(x, pca)
    assert set(out) == {"logits", "routing", "graph"}
    assert out["logits"].shape == (x.shape[0], 2)
    names = " ".join(n for n, _ in m.named_modules())
    assert "etth" not in names.lower() and "forecast" not in names.lower()


# --------------------------------------------------------------------------- #
# §6 구조 비교 2종 (모델 구조만)
# --------------------------------------------------------------------------- #

from mobse.v2.models import (                     # noqa: E402
    COMPARATOR_SPEC, FUSION_HIDDEN, FusionMLPComparator, SingleGraphComparator,
    build_comparator,
)


def _graph(seed=3):
    g = torch.Generator().manual_seed(seed)
    a = torch.rand(CFG.n_roi, CFG.n_roi, generator=g)
    return (a + a.T) / 2


def _enc_hash(model):
    return torch.cat([p.detach().reshape(-1) for n, p in sorted(model.named_parameters())
                      if n.startswith("encoder.")])


def test_comparator_spec_matches_protocol_rows():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "docs/experiments/mobse_redesign_protocol_2026-09-17.md").read_text(encoding="utf-8")
    assert "| 구조 비교 | ROI encoder pooled feature + PCA FC10 fusion MLP |" in text
    assert "| 구조 비교 | training-rest single average graph + 동일 encoder/head |" in text
    assert set(COMPARATOR_SPEC) == {"NG", "SG"}
    assert FUSION_HIDDEN == 32


def test_fusion_forward_shape_and_structure():
    torch.manual_seed(0)
    m = build_comparator("NG", CFG).eval()
    x, pca = _inputs()
    out = m(x, pca)
    assert set(out) == {"logits"} and out["logits"].shape == (4, CFG.n_classes)
    assert isinstance(m, FusionMLPComparator)
    assert not list(m.buffers())                       # graph·bank 없음
    assert not any("graph" in n or "gate" in n for n, _ in m.named_parameters())
    lin = m.fusion[0]
    assert (lin.in_features, lin.out_features) == (CFG.hidden_dim + CFG.pca_dim, FUSION_HIDDEN)
    assert isinstance(m.fusion[1], torch.nn.GELU)
    assert (m.head.in_features, m.head.out_features) == (FUSION_HIDDEN, CFG.n_classes)
    enc = sum(p.numel() for n, p in m.named_parameters() if n.startswith("encoder."))
    want = enc + (CFG.hidden_dim + CFG.pca_dim) * FUSION_HIDDEN + FUSION_HIDDEN \
        + FUSION_HIDDEN * CFG.n_classes + CFG.n_classes
    assert m.trainable_parameter_count() == want


def test_fusion_dropout_follows_config():
    m = build_comparator("NG", ModelConfig(n_roi=8, n_samples=12, hidden_dim=8,
                                           gate_hidden=8, dropout=0.3))
    assert m.fusion[2].p == 0.3 and m.encoder.drop.p == 0.3


def test_fusion_uses_pca_and_rejects_missing():
    torch.manual_seed(0)
    m = build_comparator("NG", CFG).eval()
    x, pca = _inputs()
    a = m(x, pca)["logits"]
    b = m(x, pca + 1.0)["logits"]
    assert not torch.allclose(a, b)
    with pytest.raises(ModelError):
        m(x, None)
    with pytest.raises(ModelError):
        m(x, pca[:, :5])
    with pytest.raises(ModelError):
        m(x, pca, routing_override=torch.ones(4, 3) / 3)


def test_fusion_is_roi_permutation_invariant():
    """graph 전 ROI 혼합·ROI ID 가 없으므로 ROI 순서를 바꿔도 출력이 같다."""
    torch.manual_seed(0)
    m = build_comparator("NG", CFG).eval()
    x, pca = _inputs()
    perm = torch.randperm(CFG.n_roi, generator=torch.Generator().manual_seed(9))
    assert torch.allclose(m(x, pca)["logits"], m(x[:, perm], pca)["logits"], atol=1e-6)


def test_single_graph_forward_buffer_and_pca_unused():
    torch.manual_seed(0)
    m = build_comparator("SG", CFG, _graph()).eval()
    assert isinstance(m, SingleGraphComparator) and m.bank_is_frozen()
    x, pca = _inputs()
    out = m(x, pca)
    assert out["logits"].shape == (4, CFG.n_classes)
    assert torch.equal(out["graph"][0], _graph())
    assert torch.allclose(out["logits"], m(x, pca * 7.0)["logits"])
    assert torch.allclose(out["logits"], m(x, None)["logits"])
    assert len(m.graph_layers) == CFG.n_graph_layers
    assert not any("gate" in n for n, _ in m.named_parameters())


def test_single_graph_equals_abcd_model_with_identical_templates():
    """'동일 encoder/head': bank [S,S,S] 인 A–D 모델과 가중치를 맞추면 출력이 같다."""
    s = _graph()
    torch.manual_seed(0)
    sg = build_comparator("SG", CFG, s).eval()
    for routing in ("fixed", "dynamic"):
        torch.manual_seed(5)
        ref = MoBSEv2(CFG, s.unsqueeze(0).repeat(3, 1, 1), routing=routing).eval()
        shared = {k: v for k, v in sg.state_dict().items() if k != "graph"}
        missing = ref.load_state_dict(shared, strict=False)
        assert all(k.startswith("gate.") or k == "template_bank" for k in missing.missing_keys)
        assert not missing.unexpected_keys
        x, pca = _inputs()
        assert torch.allclose(sg(x, pca)["logits"], ref(x, pca)["logits"], atol=1e-5)


def test_comparators_share_encoder_init_with_cells_under_same_seed():
    brain, null = _banks()
    torch.manual_seed(42)
    a = build_cell("A", CFG, brain, null)
    for name, g in (("NG", None), ("SG", _graph())):
        torch.manual_seed(42)
        m = build_comparator(name, CFG, g)
        assert torch.equal(_enc_hash(a), _enc_hash(m)), name


def test_single_graph_rejects_bad_graph_and_routing():
    with pytest.raises(ModelError):
        build_comparator("SG", CFG, torch.rand(3, CFG.n_roi, CFG.n_roi))
    with pytest.raises(ModelError):
        build_comparator("SG", CFG, torch.rand(CFG.n_roi + 1, CFG.n_roi + 1))
    bad = _graph().clone()
    bad[0, 1] = float("nan")
    with pytest.raises(ModelError):
        build_comparator("SG", CFG, bad)
    m = build_comparator("SG", CFG, _graph())
    x, pca = _inputs()
    with pytest.raises(ModelError):
        m(x, pca, routing_override=torch.ones(4, 3) / 3)


def test_build_comparator_argument_rules():
    with pytest.raises(ModelError):
        build_comparator("A", CFG)
    with pytest.raises(ModelError):
        build_comparator("SG", CFG)
    with pytest.raises(ModelError):
        build_comparator("NG", CFG, _graph())
