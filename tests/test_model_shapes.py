import torch

from mobse.models.mobse import MoBSEModel


def test_mobse_forward_shapes():
    template_bank = torch.randn(5, 100, 100)
    model = MoBSEModel(
        num_nodes=100,
        hidden_dim=16,
        num_experts=5,
        num_graph_layers=2,
        dropout=0.1,
        routing_k=2,
        routing_mode="soft",
        os_num_classes=5,
        etth1_in_dim=7,
        etth1_out_dim=1,
        pred_len=12,
        template_bank=template_bank,
    )

    x_os = torch.randn(4, 64, 100)
    out_os = model(x_os, task="os")
    assert out_os["logits"].shape == (4, 5)
    assert out_os["routing_weights"].shape == (4, 5)

    x_etth = torch.randn(4, 96, 7)
    out_etth = model(x_etth, task="etth1")
    assert out_etth["pred"].shape == (4, 12, 1)
    assert out_etth["routing_weights"].shape == (4, 5)


def test_mobse_forward_without_template_prior():
    template_bank = torch.randn(5, 100, 100)
    model = MoBSEModel(
        num_nodes=100,
        hidden_dim=16,
        num_experts=5,
        num_graph_layers=1,
        dropout=0.1,
        routing_k=2,
        routing_mode="hard",
        os_num_classes=5,
        etth1_in_dim=7,
        etth1_out_dim=1,
        pred_len=12,
        template_bank=template_bank,
        use_template_prior=False,
    )
    x = torch.randn(2, 48, 100)
    out = model(x, task="os")
    assert out["logits"].shape == (2, 5)
