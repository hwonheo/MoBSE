#!/usr/bin/env python3
"""I1 D1 등변성 진단 — 공개 모델이 ROI 순서에 의존하는가 (사전 작업, 결정 39).

학습된 모델 f 와 ROI 순열 P 에 대해 ``max |f(P·S·Pᵀ, P·x) − f(S, x)|`` 를 잰다 (S = 피험자 FC, x = 시계열).
등변/불변 구성이면 부동소수 수준 (≈ 1e−6 이하), 순서 의존 구성이면 그보다 훨씬 크다.

이 스크립트는 **학습 전 (무작위 초기화) 모델** 로 잰다 — 등변성은 구조의 성질이라 학습 전에도 드러난다.
모델 클래스는 저장소 clone 에서 **읽기만** 한다 (코드를 고치지 않는다). 기본 설정은 각 저장소의 기본값이다.
BNT 는 torch ≥ 2.0 호환 문제가 있어, 같은 한 줄 수정을 **메모리에서만** 적용한다 (파일은 그대로).

Usage (h197, venv-i1):
    python scripts/i1/d1_equivariance.py --repos <i1/repos> --npy <abide.npy> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

import numpy as np
import torch


def perms(n_roi: int, k: int, seed: int):
    rng = np.random.default_rng(seed)
    return [torch.as_tensor(rng.permutation(n_roi)) for _ in range(k)]


def bnt_models(repos: Path, n_roi: int, t: int):
    sys.path.insert(0, str(repos / "BrainNetworkTransformer"))
    from omegaconf import OmegaConf
    from source.models.BNT.components import transformer_encoder as te
    orig = te.InterpretableTransformerEncoder._sa_block

    def _sa_block(self, x, attn_mask, key_padding_mask, is_causal=False):   # 호환 (메모리에서만)
        return orig(self, x, attn_mask, key_padding_mask)
    te.InterpretableTransformerEncoder._sa_block = _sa_block
    from source.models.BNT.bnt import BrainNetworkTransformer
    from source.models.brainnetcnn import BrainNetCNN
    base = OmegaConf.load(repos / "BrainNetworkTransformer/source/conf/model/bnt.yaml")
    cfg = OmegaConf.create({"model": base, "dataset": {"node_sz": n_roi, "node_feature_sz": n_roi,
                                                       "timeseries_sz": t}})
    out = {"bnt": BrainNetworkTransformer(cfg)}
    cfg2 = OmegaConf.create({"model": {"name": "BrainNetCNN"}, "dataset": {"node_sz": n_roi}})
    out["brainnetcnn"] = BrainNetCNN(cfg2)
    for k in [m for m in list(sys.modules) if m == "source" or m.startswith("source.")]:
        del sys.modules[k]                                       # Han 저장소도 패키지명이 source 다
    sys.path.remove(str(repos / "BrainNetworkTransformer"))
    return {k: (m, lambda m, x, s: m(x, s)) for k, m in out.items()}


def bqn_model(repos: Path, n_roi: int, t: int):
    root = repos / "_bqn_alias"
    root.mkdir(exist_ok=True)
    alias = root / "BQN_Demo"
    if not alias.exists():
        alias.symlink_to(repos / "BQN-demo")                     # 저장소의 하드코딩된 import 경로를 맞춘다
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(repos / "BQN-demo"))
    from BQN_Demo.model.BQN import Quadratic_BN
    args = types.SimpleNamespace(activation="leaky_relu")
    m = Quadratic_BN(args=args, node_sz=n_roi, time_series_sz=t, corr_pearson_sz=n_roi, layers=3,
                     dropout=0.1, cluster_num=4, pooling=True)
    return {"bqn": (m, lambda m, x, s: m(x, s))}


def braingb_models(repos: Path, n_roi: int):
    """BrainGB GCN (기본 설정 + README 명령의 mp_type · hidden 256). 자료 처리는 저장소 그대로:
    `dense_to_ind_val` 로 모든 (i, j) 를 edge 로, `Adj` transform 으로 node 특성 = FC 행.
    결정 40 (2026-10-03) 의 등변 대표 = mean pooling + `Degree` transform (node 특성 = 연결 강도 합, 1 차원)."""
    sys.path.insert(0, str(repos / "BrainGB"))
    from src.models import GCN, BrainNN, MLP
    from src.dataset.brain_dataset import dense_to_ind_val
    from src.dataset.transforms import Adj, Degree
    from torch_geometric.data import Batch, Data
    out = {}
    for pooling, feat in (("mean", "adj"), ("concat", "adj"), ("mean", "degree")):
        a = types.SimpleNamespace(pooling=pooling, gcn_mp_type="edge_node_concate", hidden_dim=256,
                                  n_GNN_layers=2, n_MLP_layers=1, edge_emb_dim=256, bucket_sz=0.05,
                                  gat_hidden_dim=8, dropout=0.5, variant="gcn")
        in_dim = n_roi if feat == "adj" else 1                   # example_main 처럼 dataset[0].x.shape[1]
        model = BrainNN(a, GCN(in_dim, a, n_roi, num_classes=2),
                        MLP(2 * n_roi, a.hidden_dim, a.n_MLP_layers, torch.nn.ReLU, n_classes=2))
        adj = Adj() if feat == "adj" else Degree()

        def fwd(m, x, s, adj=adj, col_inv=None):
            # col_inv 를 주면 node 특성 (= FC 행) 의 열만 원래 ROI 순서로 되돌린다 — node 순서만 바뀐 입력.
            graphs = []
            for k in range(s.shape[0]):
                ei, ea = dense_to_ind_val(s[k])
                g = adj(Data(num_nodes=s.shape[1], edge_index=ei, edge_attr=ea))
                if col_inv is not None:
                    g.x = g.x[:, col_inv]
                graphs.append(g)
            return m(Batch.from_data_list(graphs))
        out[f"braingb_gcn_{pooling}" + ("" if feat == "adj" else f"_{feat}")] = (model, fwd)
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repos", required=True, type=Path)
    ap.add_argument("--npy", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n-perm", type=int, default=20)
    ap.add_argument("--n-subj", type=int, default=8)
    args = ap.parse_args(argv[1:])
    torch.manual_seed(0)
    data = np.load(args.npy, allow_pickle=True).item()
    S = torch.as_tensor(data["corr"][:args.n_subj], dtype=torch.float32)
    X = torch.as_tensor(data["timeseires"][:args.n_subj], dtype=torch.float32)
    n_roi, t = S.shape[1], X.shape[2]
    models = {}
    models.update(bnt_models(args.repos, n_roi, t))
    models.update(bqn_model(args.repos, n_roi, t))
    models.update(braingb_models(args.repos, n_roi))
    rows = {}
    for name, (m, fwd) in models.items():
        m.eval()
        with torch.no_grad():
            # forward 마다 난수를 다시 고정한다 — BrainNetCNN 은 F.dropout 을 학습 플래그 없이 써서
            # 평가 모드에서도 dropout 이 켜진다. 같은 입력을 두 번 넣은 차이 (self_diff) 도 잰다.
            torch.manual_seed(0); base = fwd(m, X, S)
            torch.manual_seed(0); self_diff = float((fwd(m, X, S) - base).abs().max())
            diffs, node_only = [], []
            for p in perms(n_roi, args.n_perm, seed=1729):
                Sp = S[:, p][:, :, p]
                Xp = X[:, p]
                torch.manual_seed(0)
                diffs.append(float((fwd(m, Xp, Sp) - base).abs().max()))
                if name.startswith("braingb") and not name.endswith("_degree"):
                    # node 특성이 FC 행이면 순열이 특성 차원 (열 = ROI 정체) 까지 섞는다. 열을 되돌려
                    # node 순서만 바꾼 차이를 따로 잰다 — 구조 (message passing + pooling) 자체의 대칭성.
                    torch.manual_seed(0)
                    node_only.append(float((fwd(m, Xp, Sp, col_inv=torch.argsort(p)) - base).abs().max()))
        rows[name] = {"max_abs_diff": max(diffs), "self_diff": self_diff, "median_abs_diff": float(np.median(diffs)),
                      "output_scale": float(base.abs().mean()), "n_perm": args.n_perm,
                      "n_params": int(sum(p.numel() for p in m.parameters()))}
        if node_only:
            rows[name]["node_only_max_abs_diff"] = max(node_only)
            print(f"{name:12s} node 순서만 바꾼 차 max = {max(node_only):.3e}", flush=True)
        print(f"{name:12s} max |f(Px)−f(x)| = {max(diffs):.3e}  자기 차 {self_diff:.1e}  (출력 크기 {float(base.abs().mean()):.3e}, "
              f"parameter {rows[name]['n_params']:,})", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"schema_version": "i1-d1-0.3", "state": "random init (학습 전)",
                                    "n_subj": args.n_subj, "rows": rows}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
