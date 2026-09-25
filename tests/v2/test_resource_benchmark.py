"""`scripts/h197/21_resource_benchmark.py` 의 cell 목록과 parameter 수 기록.

계획서 §6 "no-graph FC comparator와 실제 parameter/비용을 함께 보고한다" 와
§9 "동일 장비/batch/precision 에서 … parameter 수를 분리한다" — 구조 비교
NG·SG 가 A–D 와 같은 벤치마크 경로로 재어지는지 고정한다 (합성 자료, CPU).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "h197" / "21_resource_benchmark.py"


def _load():
    spec = importlib.util.spec_from_file_location("rb21", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bench():
    mod = _load()
    rng = np.random.Generator(np.random.PCG64(7))
    out = mod.bench_cells(rng, 8, torch.device("cpu"), 1)
    return mod, out


def test_cell_list_is_a_to_d_then_ng_sg():
    mod = _load()
    assert mod.BENCH_CELLS == ("A", "B", "C", "D", "NG", "SG")


def test_every_cell_is_measured(bench):
    mod, out = bench
    assert tuple(out) == mod.BENCH_CELLS
    for cell, rec in out.items():
        assert rec["trainable_parameters"] > 0, cell
        assert rec["epoch"]["repeats"] == 1
        assert rec["inference_full_pass"]["repeats"] == 1
        assert rec["flops"].startswith("NA")
        assert rec["structure_comparator"] is (cell in ("NG", "SG"))


def test_bank_flag_by_structure(bench):
    _, out = bench
    assert out["NG"]["bank_is_frozen"] is None      # graph 없음
    assert out["SG"]["bank_is_frozen"] is True      # graph 는 buffer
    for cell in "ABCD":
        assert out[cell]["bank_is_frozen"] is True


def test_parameter_counts_by_hand(bench):
    """NG = encoder + Linear(42→32) + Linear(32→2); SG = encoder + graph 층 + head."""
    from mobse.v2.models import (FUSION_HIDDEN, ModelConfig, ROIEncoder,
                                 build_comparator)
    _, out = bench
    cfg = ModelConfig()
    enc = sum(p.numel() for p in ROIEncoder(cfg).parameters())
    fusion_in = cfg.hidden_dim + cfg.pca_dim
    ng = (enc + fusion_in * FUSION_HIDDEN + FUSION_HIDDEN
          + FUSION_HIDDEN * cfg.n_classes + cfg.n_classes)
    assert out["NG"]["trainable_parameters"] == ng
    sg_model = build_comparator("SG", cfg, torch.eye(cfg.n_roi))
    graph = sum(p.numel() for p in sg_model.graph_layers.parameters())
    sg = enc + graph + cfg.hidden_dim * cfg.n_classes + cfg.n_classes
    assert out["SG"]["trainable_parameters"] == sg
    # graph 는 buffer — parameter 수에 N_ROI² 가 들어가지 않는다
    assert out["SG"]["trainable_parameters"] < cfg.n_roi * cfg.n_roi
