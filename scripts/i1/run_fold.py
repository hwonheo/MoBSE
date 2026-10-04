#!/usr/bin/env python3
"""I1 실행 wrapper — 공개 모델 하나를 공통 fold 하나 · seed 하나로 학습하고 피험자별 test 예측을 남긴다.

결정 41-1 (메모리 wrapper) · 결정 42 (공통 val loss 최소 epoch · label × site 층화). 저장소 파일은 **고치지 않는다** —
분할 함수와 평가 함수를 이 프로세스의 메모리 안에서만 바꿔 끼운다 (D1 의 BNT 호환 수정과 같은 방식).
바꿔 끼운 목록은 모델마다 ``PATCHES`` 에 적고 ``summary.json`` 에도 남긴다 (D5 재현 마찰 표의 자료).

공통 규칙:
* seed: ``random`` · ``numpy`` · ``torch`` (CPU · CUDA) 를 ``--seed`` 로 고정하고 ``cudnn.deterministic = True`` ·
  ``benchmark = False``. GPU 연산의 완전한 결정성은 보장하지 않는다 — smoke 에서 같은 seed 재실행을 비교한다.
* 분할: ``--folds`` 파일의 fold ``--fold`` (train · val · test index). 저장소의 batch 크기 · shuffle · drop_last 는 그대로.
* epoch 마다 val · test 를 **순서 고정 loader** 로 한 번 더 평가해 피험자별 class 1 확률을 얻는다 (eval 모드, 기울기 없음).
  val loss = 확률에서 계산한 평균 cross-entropy — 모델마다 출력 형식 (logit · log-softmax) 이 달라도 같은 정의.
* 선택: val loss 최소 epoch (같으면 앞 epoch) 의 test 예측. AUC 와 BA (문턱 0.5) 를 함께 적는다.
* 저장소 자신의 반환값 (예: BQN 의 val loss 최소 epoch test AUC) 도 ``repo_reported`` 로 남겨 대조한다.

Usage (h197, venv-i1):
    python scripts/i1/run_fold.py --model bqn --repos <i1/repos> --npy <조건별 abide.npy> \\
        --folds <folds_draw0.json> --fold 0 --seed 1 --out <dir> [--epochs N]
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

MODELS = ("bqn", "bnt", "braingb", "han")


def seed_all(seed: int, deterministic: bool = True) -> None:
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    # GPU scatter 합산 (torch_geometric) 등은 위 설정만으로는 비결정적이다 — 결정적 구현을 요구하고, 없으면 경고만 (로그에 남는다).
    # CUBLAS_WORKSPACE_CONFIG 는 main 이 CUDA 초기화 전에 넣는다.
    # BrainGB 는 끈다 — PyG scatter 가 결정적 모드에서 메모리를 크게 쓰는 경로로 바뀌어 24 GB GPU 에서 OOM (2026-10-04 smoke),
    # 저장소 mixup 이 .cuda() 고정이라 CPU 로도 못 돈다. 그래서 BrainGB 는 같은 seed 재실행도 값이 다를 수 있다 (D3 에 포함).
    torch.use_deterministic_algorithms(deterministic, warn_only=True)


def mean_ce(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc_ba(p: np.ndarray, y: np.ndarray) -> dict:
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    return {"auc": float(roc_auc_score(y, p)), "ba": float(balanced_accuracy_score(y, (p > 0.5).astype(int)))}


D1_N, D1_PERMS, D1_SEED = 8, 20, 1729        # 계획서 §3 D1 · 결정 43 §3.9 (순열 생성은 d1_equivariance.py 와 같음)


def permute_roi(t, p, v: int):
    """배치 축을 뺀 모든 크기 v 축 (ROI 축) 에 같은 순열을 준다 — FC 는 행 · 열, 시계열 · 고유벡터는 ROI 축."""
    for ax in range(1, t.dim()):
        if t.shape[ax] == v:
            t = t.index_select(ax, p)
    return t


def d1_measure(fwd, inputs: tuple, v: int) -> dict:
    """학습이 끝난 모델 (마지막 epoch) 의 등변성 — test 앞 D1_N 명, ROI 순열 D1_PERMS 개, class 1 확률의 최대 차."""
    import torch
    rng = np.random.default_rng(D1_SEED)
    base = fwd(inputs)
    self_diff = float(np.max(np.abs(fwd(inputs) - base)))
    diffs = []
    for _ in range(D1_PERMS):
        p = torch.as_tensor(rng.permutation(v))
        diffs.append(float(np.max(np.abs(fwd(tuple(permute_roi(t, p, v) for t in inputs)) - base))))
    return {"state": "학습 끝 (마지막 epoch)", "n_subj": len(base), "n_perm": D1_PERMS, "max_abs_diff_p1": max(diffs),
            "median_abs_diff_p1": float(np.median(diffs)), "self_diff": self_diff, "p1_mean": float(np.mean(base))}


class Recorder:
    """epoch 마다 순서 고정 val · test 확률을 모은다."""

    def __init__(self, fold: dict, labels: np.ndarray):
        self.val_idx, self.test_idx = np.asarray(fold["val"]), np.asarray(fold["test"])
        self.y_val, self.y_test = labels[self.val_idx], labels[self.test_idx]
        self.rows: list = []
        self.keep_last = False                                   # --save-last: D1 학습판용 마지막 epoch 상태
        self.last_state = None

    def add(self, p_val: np.ndarray, p_test: np.ndarray, model=None) -> None:
        self.rows.append({"epoch": len(self.rows), "val_loss": mean_ce(p_val, self.y_val),
                          "val": auc_ba(p_val, self.y_val), "test": auc_ba(p_test, self.y_test),
                          "_p_test": p_test.astype(float)})
        if model is not None:
            self.model_ref = model                               # --d1 이 학습 끝 모델을 쓴다
        if self.keep_last and model is not None:
            self.last_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    def finish(self, out: Path, extra: dict) -> dict:
        if not self.rows:
            raise RuntimeError("기록된 epoch 이 없다")
        best = min(range(len(self.rows)), key=lambda e: (self.rows[e]["val_loss"], e))
        p = self.rows[best]["_p_test"]
        with (out / "predictions.jsonl").open("w") as fh:
            for i, yy, pp in zip(self.test_idx.tolist(), self.y_test.tolist(), p.tolist()):
                fh.write(json.dumps({"subject_index": i, "label": int(yy), "p1": pp}) + "\n")
        with (out / "epochs.jsonl").open("w") as fh:
            for r in self.rows:
                fh.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}) + "\n")
        summary = {"selected_epoch": best, "n_epochs": len(self.rows), "val_loss": self.rows[best]["val_loss"],
                   "test": self.rows[best]["test"], "last_epoch_test": self.rows[-1]["test"], **extra}
        if self.keep_last:
            import torch
            if self.last_state is None:
                raise RuntimeError("--save-last 인데 저장할 상태가 없다")
            torch.save(self.last_state, out / "last_epoch_state.pt")
            summary["last_epoch_state"] = "last_epoch_state.pt"
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        return summary


def run_bqn(a, fold: dict, labels: np.ndarray, rec: Recorder) -> dict:
    """BQN-demo — ``main.run`` 을 그대로 부르고 분할 · 평가 두 함수만 바꿔 끼운다."""
    import torch
    import torch.nn.functional as F

    repo = a.repos / "BQN-demo"
    alias_root = a.repos / "_bqn_alias"                        # 저장소의 하드코딩된 import 경로 (D1 과 같은 alias)
    sys.path[:0] = [str(repo), str(alias_root)]
    sys.argv = ["main.py", "--data_dir", str(a.npy.parent), "--root_path", str(a.out), "--seed", str(a.seed)]
    if a.epochs:
        sys.argv += ["--epochs", str(a.epochs)]
    import main as bqn_main                                    # noqa: E402  (저장소 모듈)
    from parse import get_args

    args = get_args()
    args.runs = 1
    dataset = bqn_main.load_data(args)                         # (timeseries, pearson, label, site) — 저장소 그대로
    ts, pc, lab = dataset[0], dataset[1], dataset[2]
    if not np.array_equal(lab.numpy().astype(int), labels):
        raise SystemExit("저장소가 읽은 label 이 fold 파일의 label 과 다르다")
    dev = torch.device(f"cuda:{args.device}" if torch.cuda.is_available() else "cpu")

    def init_stratified_dataloader(args, final_timeseries, final_pearson, labels_t, stratified):
        onehot = F.one_hot(labels_t.to(torch.int64))
        mk = lambda idx: torch.utils.data.TensorDataset(  # noqa: E731
            final_timeseries[idx], final_pearson[idx], onehot[idx])
        tr, va, te = (torch.as_tensor(fold[k]) for k in ("train", "val", "test"))
        dl = torch.utils.data.DataLoader
        return {"train_dataloader": dl(mk(tr), batch_size=args.batch_size, shuffle=True, drop_last=True),
                "val_dataloader": dl(mk(va), batch_size=args.batch_size, shuffle=True, drop_last=False),
                "test_dataloader": dl(mk(te), batch_size=args.batch_size, shuffle=True, drop_last=False)}

    orig_val_test = bqn_main.val_test

    def probs(model, idx):
        out = []
        with torch.no_grad():
            for s in range(0, len(idx), 64):
                b = torch.as_tensor(idx[s:s + 64])
                out.append(F.softmax(model(ts[b].to(dev), pc[b].to(dev)), dim=1)[:, 1].cpu().numpy())
        return np.concatenate(out)

    def val_test(model, args, val_loader, test_loader):
        res = orig_val_test(model, args, val_loader, test_loader)   # 저장소 평가 그대로 (로그 · 선택 목록)
        model.eval()
        rec.add(probs(model, rec.val_idx), probs(model, rec.test_idx), model=model)
        return res

    bqn_main.init_stratified_dataloader = init_stratified_dataloader
    bqn_main.val_test = val_test
    seed_all(a.seed)
    acc, roc, sen, spec = bqn_main.run(args, dataset)
    if a.d1:
        b = torch.as_tensor(rec.test_idx[:D1_N])
        m = rec.model_ref.eval()
        rec.d1 = d1_measure(lambda T: F.softmax(m(T[0].to(dev), T[1].to(dev)), dim=1)[:, 1].detach().cpu().numpy(),
                            (ts[b], pc[b]), ts.shape[1])
    return {"repo_reported": {"test_acc": float(acc), "test_auc": float(roc), "rule": "repo: val loss 최소 epoch"},
            "patches": ["main.init_stratified_dataloader → 공통 fold", "main.val_test → 원래 함수 + 순서 고정 평가 기록",
                        "seed: wrapper seed_all (저장소 fix_seed 는 주석 처리돼 있음)", "runs = 1"],
            "epochs_arg": args.epochs, "batch_size": args.batch_size, "deterministic": True}


def run_bnt(a, fold: dict, labels: np.ndarray, rec: Recorder) -> dict:
    """BrainNetworkTransformer — README 의 ABIDE 명령 설정을 hydra compose 로 조립해 ``model_training`` 을 부른다."""
    import importlib
    import os

    import torch
    import torch.nn.functional as F
    import wandb
    from hydra import compose, initialize_config_dir
    from omegaconf import open_dict

    repo = a.repos / "BrainNetworkTransformer"
    sys.path.insert(0, str(repo))
    overrides = ["dataset=ABIDE", "model=bnt", "repeat_time=1", "preprocess=mixup", "datasz=100p",
                 f"dataset.path={a.npy}"]
    if a.epochs:
        overrides.append(f"training.epochs={a.epochs}")
    with initialize_config_dir(config_dir=str(repo / "source/conf"), version_base=None):
        cfg = compose(config_name="config", overrides=overrides)

    from source.models.BNT.components import transformer_encoder as te
    orig_sa = te.InterpretableTransformerEncoder._sa_block

    def _sa_block(self, x, attn_mask, key_padding_mask, is_causal=False):   # torch ≥ 2.0 호환 (D1 과 같음)
        return orig_sa(self, x, attn_mask, key_padding_mask)
    te.InterpretableTransformerEncoder._sa_block = _sa_block

    import source.dataset as ds
    from source.training.training import Train
    entry = importlib.import_module("source.__main__")
    held = {}

    def init_stratified_dataloader(cfg, final_timeseires, final_pearson, labels_t, stratified):
        held["ts"], held["pc"] = final_timeseires, final_pearson
        if not np.array_equal(labels_t.numpy().astype(int), labels):
            raise SystemExit("저장소가 읽은 label 이 fold 파일의 label 과 다르다")
        onehot = F.one_hot(labels_t.to(torch.int64))
        tr, va, te_ = (torch.as_tensor(fold[k]) for k in ("train", "val", "test"))
        with open_dict(cfg):                                     # 원래 함수가 하는 lr schedule 설정을 그대로
            cfg.steps_per_epoch = (len(tr) - 1) // cfg.dataset.batch_size + 1
            cfg.total_steps = cfg.steps_per_epoch * cfg.training.epochs
        mk = lambda idx: torch.utils.data.TensorDataset(  # noqa: E731
            final_timeseires[idx], final_pearson[idx], onehot[idx])
        dl = torch.utils.data.DataLoader
        bs = cfg.dataset.batch_size
        return [dl(mk(tr), batch_size=bs, shuffle=True, drop_last=cfg.dataset.drop_last),
                dl(mk(va), batch_size=bs, shuffle=True, drop_last=False),
                dl(mk(te_), batch_size=bs, shuffle=True, drop_last=False)]

    def probs(model, idx):
        out = []
        with torch.no_grad():
            for s in range(0, len(idx), 64):
                b = torch.as_tensor(idx[s:s + 64])
                out.append(F.softmax(model(held["ts"][b].cuda(), held["pc"][b].cuda()), dim=1)[:, 1].cpu().numpy())
        return np.concatenate(out)

    orig_tpe = Train.test_per_epoch

    def test_per_epoch(self, dataloader, loss_meter, acc_meter):
        res = orig_tpe(self, dataloader, loss_meter, acc_meter)
        if dataloader is self.test_dataloader:                   # 저장소 순서: val → test. test 뒤에 한 번 기록
            self.model.eval()
            rec.add(probs(self.model, rec.val_idx), probs(self.model, rec.test_idx), model=self.model)
        return res

    ds.init_stratified_dataloader = init_stratified_dataloader
    Train.test_per_epoch = test_per_epoch
    os.chdir(a.out)                                              # 저장소가 log_path (result/…) 에 쓰는 것을 출력 폴더 안으로
    wandb.init(mode="disabled")
    seed_all(a.seed)
    entry.model_training(cfg)
    if a.d1:
        b = torch.as_tensor(rec.test_idx[:D1_N])
        m = rec.model_ref.eval()
        with torch.no_grad():
            rec.d1 = d1_measure(lambda T: F.softmax(m(T[0].cuda(), T[1].cuda()), dim=1)[:, 1].cpu().numpy(),
                                (held["ts"][b], held["pc"][b]), held["ts"].shape[1])
    return {"repo_reported": {"rule": "repo: 선택 없음 (매 epoch 기록만)"},
            "patches": ["source.dataset.init_stratified_dataloader → 공통 fold (steps_per_epoch · total_steps 는 원래 식)",
                        "Train.test_per_epoch → 원래 함수 + test 뒤 순서 고정 평가 기록",
                        "InterpretableTransformerEncoder._sa_block ← is_causal 인자 받기 (torch ≥ 2.0 호환)",
                        "wandb.init(mode=disabled)", "seed: wrapper seed_all (저장소는 seed 를 두지 않음)"],
            "hydra_overrides": overrides, "epochs_arg": int(cfg.training.epochs), "batch_size": int(cfg.dataset.batch_size),
            "deterministic": True}


def run_braingb(a, fold: dict, labels: np.ndarray, rec: Recorder) -> dict:
    """BrainGB — 공식 진입점 ``examples.example_main`` 을 runpy 로 그대로 실행한다 (인자 parser 가 ``__main__`` 블록 안).

    구성은 결정 40: GCN · mean pooling · ``--node_features degree`` + README 의 ABIDE 명령 (edge_node_concate · hidden 256).
    바꿔 끼우는 것은 그 모듈이 실행 중에 import 하는 이름뿐이다.
    """
    import os
    import runpy

    import sklearn.model_selection as skms
    import torch

    repo = a.repos / "BrainGB"
    sys.path.insert(0, str(repo))
    import src.dataset as gbds
    import examples.train_and_evaluate as tae
    import examples.get_transform as gtf
    from torch_geometric.data import Data
    from src.dataset.brain_dataset import dense_to_ind_val

    root_dir = a.out / "braingb_root"                           # 처리 캐시 이름이 자료 내용과 무관 → fit 마다 새 root
    root_dir.mkdir()
    (root_dir / "abide.npy").symlink_to(a.npy)
    held = {}
    orig_bd = gbds.BrainDataset

    def BrainDataset(*args, root=None, **kw):                   # 저장소가 준 root (examples/datasets/ABIDE) 는 쓰지 않는다
        ds = orig_bd(*args, root=str(root_dir), **kw)
        held["ds"] = ds
        return ds

    class OneFold:                                               # StratifiedKFold(5) 자리에 공통 fold 하나
        def __init__(self, *args, **kwargs):
            pass

        def split(self, X, y):
            if not np.array_equal(np.asarray(y).astype(int), labels):
                raise SystemExit("저장소가 읽은 label 이 fold 파일의 label 과 다르다")
            yield np.asarray(fold["train"]), np.asarray(fold["test"])

    n_train = len(fold["train"])
    if n_train == len(fold["test"]):
        raise SystemExit("train 과 test 크기가 같으면 evaluate 호출을 구분할 수 없다")
    orig_eval = tae.evaluate

    def probs(model, idx):
        from torch_geometric.loader import DataLoader
        dev = next(model.parameters()).device
        out = []
        with torch.no_grad():
            for batch in DataLoader(held["ds"][torch.as_tensor(idx)], batch_size=64, shuffle=False):
                out.append(torch.exp(model(batch.to(dev)))[:, 1].cpu().numpy())   # 출력이 log_softmax
        return np.concatenate(out)

    def evaluate(model, device, loader, test_loader=None):
        res = orig_eval(model, device, loader, test_loader)
        if len(loader.dataset) == n_train:                       # 매 epoch 끝의 train 평가 = epoch 하나 끝
            rec.add(probs(model, rec.val_idx), probs(model, rec.test_idx), model=model)
        return res

    orig_gt = gtf.get_transform
    norm = None
    if a.braingb_degree_norm == "train_z":                       # 결정 46 확인용: degree (행 가중합) 를 train fold 통계로 전역 z-score.
        corr_all = torch.as_tensor(np.asarray(np.load(a.npy, allow_pickle=True).item()["corr"]), dtype=torch.float32)
        tf0 = orig_gt("degree")                                  # 저장소 변환을 그대로 써서 통계를 낸다 (정의가 어긋나지 않게)
        xs = []
        for i in fold["train"]:
            ei, ea = dense_to_ind_val(corr_all[i])
            xs.append(tf0(Data(num_nodes=corr_all.shape[1], edge_index=ei, edge_attr=ea)).x)
        xs = torch.cat(xs)
        norm = {"mode": "train_z", "mean": float(xs.mean()), "sd": float(xs.std())}

        class DegreeTrainZ(type(tf0)):                           # 상수 affine — 정보량 · 등변성은 그대로, 크기만 바뀐다
            def __call__(self, data):
                data = super().__call__(data)
                data.x = (data.x - norm["mean"]) / norm["sd"]
                return data

            def __str__(self):
                return "DegreeTrainZ"

        def get_transform(name):
            return DegreeTrainZ() if name == "degree" else orig_gt(name)
        gtf.get_transform = get_transform

    gbds.BrainDataset = BrainDataset
    skms.StratifiedKFold = OneFold
    tae.evaluate = evaluate
    argv = ["example_main", "--dataset_name", "ABIDE", "--model_name", "gcn", "--pooling", "mean",
            "--node_features", "degree", "--gcn_mp_type", "edge_node_concate", "--hidden_dim", "256", "--repeat", "1"]
    if a.epochs:
        argv += ["--epochs", str(a.epochs)]
    sys.argv = argv
    os.chdir(a.out)                                              # result.log 를 출력 폴더 안으로
    seed_all(a.seed, deterministic=False)              # 저장소는 seed_everything(random.randint(…)) — random 을 먼저 고정하므로 randint 값이 --seed 로 정해진다
    runpy.run_module("examples.example_main", run_name="__main__", alter_sys=True)
    if a.d1:                                                     # 순열 FC 로 저장소 처리 (dense_to_ind_val → Data → degree) 를 다시
        from torch_geometric.data import Batch
        tf = gtf.get_transform("degree")                         # 정규화 판이면 같은 정규화 변환
        corr = torch.as_tensor(np.asarray(np.load(a.npy, allow_pickle=True).item()["corr"])[rec.test_idx[:D1_N]],
                               dtype=torch.float32)
        m = rec.model_ref.eval()
        dev = next(m.parameters()).device

        def fwd(T):
            gs = []
            for adj in T[0]:
                ei, ea = dense_to_ind_val(adj)
                gs.append(tf(Data(num_nodes=adj.shape[0], edge_index=ei, edge_attr=ea)))
            with torch.no_grad():
                return torch.exp(m(Batch.from_data_list(gs).to(dev)))[:, 1].cpu().numpy()
        rec.d1 = d1_measure(fwd, (corr,), corr.shape[1])
    return {"repo_reported": {"rule": "repo: 마지막 epoch (val 없음)", "result_log": "result.log"},
            "patches": ["src.dataset.BrainDataset → root 를 fit 출력 폴더로 (처리 캐시가 자료 내용과 무관)",
                        "sklearn.model_selection.StratifiedKFold → 공통 fold 하나 (val 은 학습에서 뺌)",
                        "examples.train_and_evaluate.evaluate → 원래 함수 + train 평가 뒤 순서 고정 평가 기록",
                        "seed: wrapper seed_all 뒤 저장소 seed_everything(random.randint) 그대로"]
                       + (["examples.get_transform.get_transform → degree 를 train fold 통계로 전역 z-score (결정 46 확인용)"] if norm else []),
            "degree_norm": norm,
            "deterministic": False,
            "nondeterminism_note": "GPU scatter 비결정 — 결정적 모드는 OOM, mixup 의 .cuda() 고정으로 CPU 불가. 같은 seed 재실행 값이 다를 수 있다",
            "argv": argv[1:],
            "repo_quirks": ["train_and_evaluate 가 model.train() 을 첫 epoch 전에 한 번만 부르고 매 epoch evaluate 가 "
                            "model.eval() 로 바꿔, 둘째 epoch 부터 eval 모드로 학습한다 (저장소 그대로 둠)",
                            "train DataLoader shuffle=False (저장소 그대로)"]}


HAN_OVERRIDES = [  # 사전 점검 (probe_models.sh) 의 Han dual-pathway ABIDE 명령 그대로 — 저자 명령 [후보 문서 §6]
    "datasz=100p", "model=mixed_model", "dataset=ABIDE", "repeat_time=1", "preprocess=mixup", "training.epochs=100",
    "dataset.measure=Autism", "dataset.node_feature_type=learnable_time_series", "model.pooling=[False,False]",
    "model.sizes=[200,100]", "model.dim_reduction=False", "exp_name=dual_pathway_abide", "model.one_layer_fc=True",
    "dataset.only_positive_corr=True", "dataset.sparse_ratio=1", "dataset.feature_orig_or_sparse=orig",
    "dataset.binary_sparse=True", "dataset.time_series_hidden_size=32", "dataset.time_series_encoder=cnn",
    "dataset.node_feature_dim=32", "dataset.gnn_hidden_channels=32", "dataset.gnn_num_layers=1",
    "model.has_nonaggr_module=True", "model.nonaggr_type=input", "model.has_aggr_module=True", "model.aggr_module=gat",
    "model.aggr_combine_type=concat", "tune_new_learning_rates=[[1.0e-4,1.0e-5]]", "dataset.plot_figures=False",
    "dataset.tune_gnn_num_layers=[2]", "dataset.batch_size=16", "tune_combine_learning_rates=[[1.0e-4,1.0e-5]]",
    "pretrain_lower_epoch=50", "pretrain_nonaggr_coef=1", "nonaggr_coef=1", "dataset.tune_gnn_hidden_channels=[32]",
    "save_mlp_weight=False", "draw_heatmap=False", "new_weight_decay=1.0e-4"]


def run_han(a, fold: dict, labels: np.ndarray, rec: Recorder) -> dict:
    """Han dual-pathway (RethinkingBCA) — hydra main 의 grid 전처리 (조합 1 개) 를 그대로 하고 ``model_training`` 을 부른다."""
    import importlib
    import os

    import torch
    import torch.nn.functional as F
    import wandb
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf, open_dict

    repo = a.repos / "RethinkingBCA"
    sys.path.insert(0, str(repo))
    overrides = [o for o in HAN_OVERRIDES if not o.startswith("training.epochs=")]
    overrides += [f"dataset.path={a.npy}", f"training.epochs={a.epochs or 100}"]
    with initialize_config_dir(config_dir=str(repo / "source/conf"), version_base=None):
        cfg = compose(config_name="config", overrides=overrides)

    # torch ≥ 2.0 호환 — probe 의 COMPAT_SA 가 고친 세 파일의 _sa_block 을 메모리에서만 같은 방식으로 감싼다
    compat = []
    for mod_name in ("exp_transformer_encoder", "gatv2_transformer_encoder", "transformer_encoder"):
        mod = importlib.import_module(f"source.models.Mixed_model.components.{mod_name}")
        for cls in [c for c in vars(mod).values()                # torch 에서 import 한 클래스는 빼고 그 파일의 클래스만
                    if isinstance(c, type) and c.__module__ == mod.__name__ and "_sa_block" in vars(c)]:
            orig_sa = cls._sa_block

            def _sa_block(self, x, attn_mask, key_padding_mask, is_causal=False, _orig=orig_sa):
                return _orig(self, x, attn_mask, key_padding_mask)
            cls._sa_block = _sa_block
            compat.append(f"{mod_name}.{cls.__name__}")
    if len(compat) != 3:
        raise SystemExit(f"_sa_block 정의 클래스가 3 개가 아니다: {compat}")

    import source.dataset as ds
    from source.training.training import Train
    entry = importlib.import_module("source.__main__")
    held, state = {}, {"trained": False}

    def init_stratified_dataloader(cfg, final_timeseires, final_pearson, labels_t, stratified,
                                   orig_connection, saved_eigenvectors, sparse_connection, used_subjectids):
        if not np.array_equal(used_subjectids.numpy(), np.arange(len(labels))):
            raise SystemExit("used_subjectids 가 0..n−1 이 아니다")
        if not np.array_equal(labels_t.numpy().astype(int), labels):
            raise SystemExit("저장소가 읽은 label 이 fold 파일의 label 과 다르다")
        onehot = F.one_hot(labels_t.to(torch.int64))
        held["t"] = (final_timeseires, final_pearson, orig_connection, saved_eigenvectors, sparse_connection)
        tr, va, te_ = (torch.as_tensor(fold[k]) for k in ("train", "val", "test"))
        with open_dict(cfg):                                     # 원래 식 (train 길이 기준)
            cfg.steps_per_epoch = (len(tr) - 1) // cfg.dataset.batch_size + 1
            cfg.total_steps = cfg.steps_per_epoch * cfg.training.epochs
        mk = lambda idx: torch.utils.data.TensorDataset(  # noqa: E731
            final_timeseires[idx], final_pearson[idx], onehot[idx], orig_connection[idx],
            saved_eigenvectors[idx], sparse_connection[idx], used_subjectids[idx])
        dl = torch.utils.data.DataLoader
        bs = cfg.dataset.batch_size
        return [dl(mk(tr), batch_size=bs, shuffle=True, drop_last=cfg.dataset.drop_last),
                dl(mk(va), batch_size=bs, shuffle=True, drop_last=False),
                dl(mk(te_), batch_size=bs, shuffle=True, drop_last=False)]

    def probs(model, idx):
        ts, nf, oc, ev, sc = held["t"]
        out = []
        with torch.no_grad():
            for s in range(0, len(idx), 64):
                b = torch.as_tensor(idx[s:s + 64])
                o = model(ts[b].cuda(), nf[b].cuda(), None, None, False, oc[b].cuda(), ev[b].cuda(), sc[b].cuda())
                p = torch.sigmoid(o).squeeze(-1) if cfg.log_reg else F.softmax(o, dim=1)[:, 1]
                out.append(p.cpu().numpy())
        return np.concatenate(out)

    orig_tpe, orig_train_pe = Train.test_per_epoch_cog, Train.train_per_epoch

    def train_per_epoch(self, *args, **kwargs):
        res = orig_train_pe(self, *args, **kwargs)
        state["trained"] = True
        return res

    def test_per_epoch_cog(self, dataloader, *args, **kwargs):
        res = orig_tpe(self, dataloader, *args, **kwargs)
        if dataloader is self.test_dataloader and state["trained"]:   # 학습 전 성능 보기 (show_initial_performance) 는 빼고
            self.model.eval()
            rec.add(probs(self.model, rec.val_idx), probs(self.model, rec.test_idx), model=self.model)
            state["trained"] = False
        return res

    ds.init_stratified_dataloader = init_stratified_dataloader
    Train.train_per_epoch = train_per_epoch
    Train.test_per_epoch_cog = test_per_epoch_cog
    # hydra main 의 조합 전처리 (조합 1 개여야 한다)
    combos = entry.generate_param_combinations(entry.find_tune_keys(OmegaConf.to_container(cfg, resolve=True)))
    if len(combos) != 1:
        raise SystemExit(f"grid 조합이 1 개가 아니다: {len(combos)}")
    for key, value in combos[0].items():
        OmegaConf.update(cfg, key, value)
    with open_dict(cfg):
        entry.set_optimizer_param(cfg)
        cfg.common_save = f"{cfg.exp_name}_{cfg.dataset.measure}_{cfg.dataset.name}_param0"
        cfg.dataset.cur_repeat = 0
    for d in ("exp_results/split_with_valid", "exp_results/trained_models"):   # 저장소가 있다고 가정하는 폴더
        (a.out / d).mkdir(parents=True, exist_ok=True)
    os.chdir(a.out)
    wandb.init(mode="disabled")
    seed_all(a.seed)                                             # 저장소의 set_seed(338) 자리
    test_auc, test_acc, *_ = entry.model_training(cfg)
    if a.d1:
        b = torch.as_tensor(rec.test_idx[:D1_N])
        m = rec.model_ref.eval()

        def fwd(T):
            with torch.no_grad():
                o = m(T[0].cuda(), T[1].cuda(), None, None, False, T[2].cuda(), T[3].cuda(), T[4].cuda())
                return (torch.sigmoid(o).squeeze(-1) if cfg.log_reg else F.softmax(o, dim=1)[:, 1]).cpu().numpy()
        rec.d1 = d1_measure(fwd, tuple(t[b] for t in held["t"]), held["t"][0].shape[1])
    return {"repo_reported": {"test_auc": float(test_auc), "test_acc": float(test_acc), "rule": "repo: val AUC 최대 epoch"},
            "patches": ["source.dataset.init_stratified_dataloader → 공통 fold (steps 식은 원래 식)",
                        "Train.train_per_epoch · Train.test_per_epoch_cog → 원래 함수 + 학습 epoch 뒤 test 평가 때 순서 고정 평가 기록",
                        f"_sa_block ← is_causal 인자 받기 (torch ≥ 2.0 호환): {', '.join(compat)}",
                        "hydra main 의 grid 전처리를 그대로 옮겨 부름 (조합 1 개)", "wandb.init(mode=disabled)",
                        "seed: wrapper seed_all (저장소 set_seed(338) 대신)", "exp_results 폴더 생성"],
            "hydra_overrides": overrides, "grid_combo": combos[0], "epochs_arg": int(cfg.training.epochs),
            "batch_size": int(cfg.dataset.batch_size), "deterministic": True}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=MODELS)
    ap.add_argument("--repos", required=True, type=Path)
    ap.add_argument("--npy", required=True, type=Path, help="파일 이름은 abide.npy 여야 한다 (저장소가 이름으로 찾는다)")
    ap.add_argument("--folds", required=True, type=Path)
    ap.add_argument("--fold", required=True, type=int)
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=None, help="smoke 용 — 주지 않으면 저장소 기본값")
    ap.add_argument("--save-last", action="store_true", help="마지막 epoch 의 모델 상태를 저장 (D1 학습판용)")
    ap.add_argument("--braingb-degree-norm", choices=("none", "train_z"), default="none",
                    help="BrainGB 만 — train_z 는 degree 특성을 train fold 평균 · SD 로 표준화 (결정 46 확인용, 잠금 구성은 none)")
    ap.add_argument("--d1", action="store_true", help="학습이 끝난 모델로 D1 (등변성) 을 재어 summary 와 d1.json 에 남긴다")
    a = ap.parse_args(argv[1:])
    import os
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")    # 결정적 cuBLAS (torch 문서의 요구)
    if a.npy.name != "abide.npy":
        raise SystemExit("--npy 의 파일 이름은 abide.npy 여야 한다")
    if (a.out / "summary.json").exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {a.out}", file=sys.stderr)
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    folds = json.loads(a.folds.read_text())
    fold = folds["folds"][a.fold]
    labels = np.asarray(np.load(a.npy, allow_pickle=True).item()["label"]).astype(int)
    if len(labels) != folds["n_subj"]:
        raise SystemExit(f"표본 수 {len(labels)} ≠ fold 파일 {folds['n_subj']}")
    rec = Recorder(fold, labels)
    rec.keep_last = a.save_last
    t0 = time.time()
    extra = {"bqn": run_bqn, "bnt": run_bnt, "braingb": run_braingb, "han": run_han}[a.model](a, fold, labels, rec)
    extra.update({"model": a.model, "fold": a.fold, "seed": a.seed, "npy": str(a.npy), "folds_file": str(a.folds),
                  "folds_draw": folds["draw"], "wall_s": round(time.time() - t0, 1)})
    if a.d1:
        extra["d1"] = rec.d1
        (a.out / "d1.json").write_text(json.dumps(rec.d1, ensure_ascii=False, indent=1))
    s = rec.finish(a.out, extra)
    print(json.dumps({k: s[k] for k in ("selected_epoch", "n_epochs", "test", "last_epoch_test", "repo_reported", "wall_s")},
                     ensure_ascii=False))
    return 0 if all(math.isfinite(r["val_loss"]) for r in rec.rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
