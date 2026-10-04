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

MODELS = ("bqn", "bnt")


def seed_all(seed: int) -> None:
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def mean_ce(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc_ba(p: np.ndarray, y: np.ndarray) -> dict:
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    return {"auc": float(roc_auc_score(y, p)), "ba": float(balanced_accuracy_score(y, (p > 0.5).astype(int)))}


class Recorder:
    """epoch 마다 순서 고정 val · test 확률을 모은다."""

    def __init__(self, fold: dict, labels: np.ndarray):
        self.val_idx, self.test_idx = np.asarray(fold["val"]), np.asarray(fold["test"])
        self.y_val, self.y_test = labels[self.val_idx], labels[self.test_idx]
        self.rows: list = []

    def add(self, p_val: np.ndarray, p_test: np.ndarray) -> None:
        self.rows.append({"epoch": len(self.rows), "val_loss": mean_ce(p_val, self.y_val),
                          "val": auc_ba(p_val, self.y_val), "test": auc_ba(p_test, self.y_test),
                          "_p_test": p_test.astype(float)})

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
        rec.add(probs(model, rec.val_idx), probs(model, rec.test_idx))
        return res

    bqn_main.init_stratified_dataloader = init_stratified_dataloader
    bqn_main.val_test = val_test
    seed_all(a.seed)
    acc, roc, sen, spec = bqn_main.run(args, dataset)
    return {"repo_reported": {"test_acc": float(acc), "test_auc": float(roc), "rule": "repo: val loss 최소 epoch"},
            "patches": ["main.init_stratified_dataloader → 공통 fold", "main.val_test → 원래 함수 + 순서 고정 평가 기록",
                        "seed: wrapper seed_all (저장소 fix_seed 는 주석 처리돼 있음)", "runs = 1"],
            "epochs_arg": args.epochs, "batch_size": args.batch_size}


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
            rec.add(probs(self.model, rec.val_idx), probs(self.model, rec.test_idx))
        return res

    ds.init_stratified_dataloader = init_stratified_dataloader
    Train.test_per_epoch = test_per_epoch
    os.chdir(a.out)                                              # 저장소가 log_path (result/…) 에 쓰는 것을 출력 폴더 안으로
    wandb.init(mode="disabled")
    seed_all(a.seed)
    entry.model_training(cfg)
    return {"repo_reported": {"rule": "repo: 선택 없음 (매 epoch 기록만)"},
            "patches": ["source.dataset.init_stratified_dataloader → 공통 fold (steps_per_epoch · total_steps 는 원래 식)",
                        "Train.test_per_epoch → 원래 함수 + test 뒤 순서 고정 평가 기록",
                        "InterpretableTransformerEncoder._sa_block ← is_causal 인자 받기 (torch ≥ 2.0 호환)",
                        "wandb.init(mode=disabled)", "seed: wrapper seed_all (저장소는 seed 를 두지 않음)"],
            "hydra_overrides": overrides, "epochs_arg": int(cfg.training.epochs), "batch_size": int(cfg.dataset.batch_size)}


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
    a = ap.parse_args(argv[1:])
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
    t0 = time.time()
    extra = {"bqn": run_bqn, "bnt": run_bnt}[a.model](a, fold, labels, rec)
    extra.update({"model": a.model, "fold": a.fold, "seed": a.seed, "npy": str(a.npy), "folds_file": str(a.folds),
                  "folds_draw": folds["draw"], "wall_s": round(time.time() - t0, 1)})
    s = rec.finish(a.out, extra)
    print(json.dumps({k: s[k] for k in ("selected_epoch", "n_epochs", "test", "last_epoch_test", "repo_reported", "wall_s")},
                     ensure_ascii=False))
    return 0 if all(math.isfinite(r["val_loss"]) for r in rec.rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
