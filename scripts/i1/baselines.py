#!/usr/bin/env python3
"""I1 기준선 (D4) — FC logistic · FC-MLP · S1 을 공통 fold 로 돌린다 (결정 43, 잠금 초안 §3.8: 원판 입력만).

출력은 ``run_fold.py`` 와 같은 형식 (``predictions.jsonl`` · ``epochs.jsonl`` · ``summary.json``) 이라 분석 스크립트가 같이 읽는다.

* ``fc_logistic`` — v1 S3 와 같은 정의: 입력 FC (``corr``, 이미 Fisher-z · 대각 0) 의 상삼각 → StandardScaler (train 만) →
  L2 logistic, C 는 v2 grid 8 개 (``mobse.v2.baselines.LOGISTIC_CS``) 중 **안쪽 val log loss 최소** (결정 42 와 같은 규칙,
  같으면 작은 C). fit 은 ``mobse.v2.baselines.fit_logistic`` 을 그대로 부른다 (solver · tol · max_iter 같음). 결정적 — seed 무관.
  차이: v1 S3 는 창마다 v2 함수로 FC 를 다시 계산하지만, 여기서는 입력 파일의 ``corr`` (nilearn Ledoit–Wolf) 를 쓴다.
* ``s1_logistic`` — v1 S1 정의: ROI 별 시계열 평균 · 분산 (ddof 0, ROI 순서대로 평균 뒤 분산) → 같은 logistic 절차.
* ``fc_mlp`` — 상삼각 FC → StandardScaler → ``Linear(d, 32) → GELU → Dropout(0.1) → Linear(32, 2)``, AdamW (lr 1e−3,
  weight decay 1e−4), batch 32, 최대 200 epoch, 매 epoch 안쪽 val loss 를 재고 그 최소 epoch 의 test 예측 (결정 42).
  튜닝 없음 (공개 모델처럼 고정 설정 하나) [구현 선택]. seed 가 초기화 · 배치 순서를 정한다.

Usage:
    PYTHONPATH=. python scripts/i1/baselines.py --kind fc_logistic --npy <abide.npy> --folds <folds.json> \\
        --fold 0 --seed 1 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.i1.run_fold import Recorder, auc_ba, mean_ce, seed_all   # noqa: E402

KINDS = ("fc_logistic", "s1_logistic", "fc_mlp")
MLP = {"hidden": 32, "dropout": 0.1, "lr": 1e-3, "weight_decay": 1e-4, "batch": 32, "max_epochs": 200}


def features(data: dict, kind: str) -> np.ndarray:
    if kind == "s1_logistic":
        ts = np.asarray(data["timeseires"], dtype=float)          # (표본, ROI, 시점)
        return np.concatenate([ts.mean(axis=2), ts.var(axis=2)], axis=1)
    corr = np.asarray(data["corr"], dtype=float)
    iu = np.triu_indices(corr.shape[1], 1)
    return corr[:, iu[0], iu[1]]


def run_logistic(X, y, fold, rec: Recorder) -> dict:
    from mobse.v2.baselines import LOGISTIC_CS, fit_logistic
    tr, va, te = (np.asarray(fold[k]) for k in ("train", "val", "test"))
    rows = []
    for C in LOGISTIC_CS:
        lf = fit_logistic(X[tr], y[tr], C)
        z = lambda idx: ((X[idx] - lf.scaler_mean) / lf.scaler_scale) @ lf.coef + lf.intercept   # noqa: E731
        p_val, p_test = 1 / (1 + np.exp(-z(va))), 1 / (1 + np.exp(-z(te)))
        rows.append((mean_ce(p_val, y[va]), C, lf.converged, p_val, p_test))
    best = min(rows, key=lambda r: (r[0], r[1]))
    rec.add(best[3], best[4])                                     # 한 "epoch" = 고른 C
    return {"selected_C": best[1], "converged": best[2],
            "grid": [{"C": r[1], "val_loss": r[0], "converged": r[2]} for r in rows]}


def run_mlp(X, y, fold, rec: Recorder, seed: int) -> dict:
    import torch
    from sklearn.preprocessing import StandardScaler
    tr, va, te = (np.asarray(fold[k]) for k in ("train", "val", "test"))
    sc = StandardScaler().fit(X[tr])
    T = lambda idx: torch.as_tensor(sc.transform(X[idx]), dtype=torch.float32)   # noqa: E731
    Xtr, Xva, Xte, ytr = T(tr), T(va), T(te), torch.as_tensor(y[tr], dtype=torch.long)
    seed_all(seed)
    net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], MLP["hidden"]), torch.nn.GELU(),
                              torch.nn.Dropout(MLP["dropout"]), torch.nn.Linear(MLP["hidden"], 2))
    opt = torch.optim.AdamW(net.parameters(), lr=MLP["lr"], weight_decay=MLP["weight_decay"])
    gen = torch.Generator().manual_seed(seed)
    for _ in range(MLP["max_epochs"]):
        net.train()
        for b in torch.randperm(len(tr), generator=gen).split(MLP["batch"]):
            opt.zero_grad()
            torch.nn.functional.cross_entropy(net(Xtr[b]), ytr[b]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            rec.add(torch.softmax(net(Xva), 1)[:, 1].numpy(), torch.softmax(net(Xte), 1)[:, 1].numpy())
    return {"mlp": MLP}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--npy", required=True, type=Path)
    ap.add_argument("--folds", required=True, type=Path)
    ap.add_argument("--fold", required=True, type=int)
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv[1:])
    if (a.out / "summary.json").exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {a.out}", file=sys.stderr)
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    folds = json.loads(a.folds.read_text())
    fold = folds["folds"][a.fold]
    data = np.load(a.npy, allow_pickle=True).item()
    y = np.asarray(data["label"]).astype(int)
    if len(y) != folds["n_subj"]:
        raise SystemExit(f"표본 수 {len(y)} ≠ fold 파일 {folds['n_subj']}")
    X = features(data, a.kind)
    rec = Recorder(fold, y)
    t0 = time.time()
    extra = run_mlp(X, y, fold, rec, a.seed) if a.kind == "fc_mlp" else run_logistic(X, y, fold, rec)
    extra.update({"model": a.kind, "fold": a.fold, "seed": a.seed, "npy": str(a.npy), "folds_file": str(a.folds),
                  "folds_draw": folds.get("draw"), "n_features": int(X.shape[1]), "wall_s": round(time.time() - t0, 1),
                  "deterministic": True})
    s = rec.finish(a.out, extra)
    print(json.dumps({k: s[k] for k in ("selected_epoch", "n_epochs", "test", "wall_s")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
