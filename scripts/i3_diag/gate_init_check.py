#!/usr/bin/env python3
"""I3 gate 초기 상태 점검 (결정 71) — 학습 없이 seed 42 초기화 그대로 val 블록의 dynamic gate routing entropy 를 잰다.

gate 입력 (rest 창으로 맞춘 PCA 10) 의 열별 평균 · SD 도 함께 적는다.

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_init_check.py data/i3/main/20261016_1bc3622d_a1
"""
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "i3"))
import core  # noqa: E402
from mobse.v2.models import ModelConfig  # noqa: E402
from mobse.v2.train import build_grid  # noqa: E402
from mobse.v3.models import MoBSEv3  # noqa: E402

run = Path(sys.argv[1])
gc = {g.config_id: g for g in build_grid()}[core.CONFIG_ID]
for k in range(5):
    z = np.load(run / "prep" / f"outer{k}" / "prep.npz")
    pt, pv = z["pca_train"], z["pca_val"]
    print(f"outer{k} pca_train col mean {np.round(pt.mean(0), 2)} col SD {np.round(pt.std(0), 2)}")
    core.seed_all(42)
    cfg = ModelConfig(n_roi=z["x_train"].shape[1], n_samples=core.BLOCK_FRAMES, pca_dim=pt.shape[1],
                      dropout=float(gc.dropout))
    m = MoBSEv3(cfg, torch.as_tensor(z["bank"]), routing="dynamic", roi_structure="embedding").eval()
    with torch.no_grad():
        w = m.gate(torch.as_tensor(pv)).numpy()
    ent = -(w * np.log(np.clip(w, 1e-12, None))).sum(1)
    print(f"outer{k} init entropy mean {ent.mean():.3f} (ln3 = {np.log(3):.3f}) · w mean {w.mean(0).round(3)}")
