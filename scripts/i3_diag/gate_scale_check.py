#!/usr/bin/env python3
"""gate 입력 크기 맞춤의 학습 없는 확인 (pilot 만) — 초기화 직후 dynamic gate 의 routing entropy 를 세 입력으로 잰다.

* raw: 지금 입력 (training-rest PCA 10 점수 그대로).
* (가) rest 기준: 학습 피험자 rest 창 PCA 점수의 열 평균 · SD 로 표준화.
* (나) 과제 기준: 학습 피험자 과제 블록 PCA 점수 (``pca_train``, label 안 씀) 의 열 평균 · SD 로 표준화.

자료는 구동기 smoke 의 pilot 가짜 분할 (``smoke_folds.json`` · ``prep/outer0``) 만 쓴다 — main 피험자를 읽지 않는다.

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_scale_check.py --smoke data/i3/smoke/smoke_a1 \
        --data-root data/h1h2_scope/aomic
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "i3"))
import core  # noqa: E402
from mobse.v2.features import fit_transform_on_training_rest, stack_window_features  # noqa: E402
from mobse.v2.models import ModelConfig  # noqa: E402
from mobse.v2.train import build_grid  # noqa: E402
from mobse.v3.models import MoBSEv3  # noqa: E402


def entropy(w: np.ndarray) -> np.ndarray:
    return -(w * np.log(np.clip(w, 1e-12, None))).sum(axis=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    a = ap.parse_args()

    folds = json.loads((a.smoke / "smoke_folds.json").read_text())
    parts = core.fold_parts(folds, 0)
    rest = [w for s in parts["train"] for w in core.rest_windows(a.data_root, s)]
    rest_subs = [s for s in parts["train"] for _ in range(4)]
    _, z_rest = stack_window_features(rest)
    trans = fit_transform_on_training_rest(z_rest, rest_subs)
    p_rest = trans.transform(z_rest)
    z = np.load(a.smoke / "prep" / "outer0" / "prep.npz")
    # 같은 변환인지: 저장된 pca_train 을 다시 만든 변환으로 재현
    _, zf = stack_window_features(list(z["x_train"].transpose(0, 2, 1)))
    same = float(np.abs(trans.transform(zf) - z["pca_train"]).max())

    scalers = {
        "raw": (np.zeros(10), np.ones(10)),
        "rest_std": (p_rest.mean(0), p_rest.std(0)),
        "task_std": (z["pca_train"].mean(0), z["pca_train"].std(0)),
    }
    gc = {g.config_id: g for g in build_grid()}[core.CONFIG_ID]
    out = {"n_rest_windows": len(rest), "pca_train_rebuild_max_diff": same,
           "rest_pca_col_sd": np.round(p_rest.std(0), 2).tolist(),
           "task_pca_col_mean_in_rest_sd": np.round((z["pca_train"].mean(0) - p_rest.mean(0)) / p_rest.std(0), 2).tolist(),
           "ln3": float(np.log(3)), "entropy": {}}
    for name, (mu, sd) in scalers.items():
        res = {}
        for r in ("val", "test"):
            pv = ((z[f"pca_{r}"] - mu) / sd).astype(np.float32)
            ents = []
            for seed in core.SEEDS:
                core.seed_all(seed)
                cfg = ModelConfig(n_roi=z["x_train"].shape[1], n_samples=core.BLOCK_FRAMES, pca_dim=10,
                                  dropout=float(gc.dropout))
                m = MoBSEv3(cfg, torch.as_tensor(z["bank"]), routing="dynamic", roi_structure="embedding").eval()
                with torch.no_grad():
                    w = m.gate(torch.as_tensor(pv)).numpy()
                ents.append(float(entropy(w).mean()))
            res[r] = [round(e, 3) for e in ents]
        out["entropy"][name] = res
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
