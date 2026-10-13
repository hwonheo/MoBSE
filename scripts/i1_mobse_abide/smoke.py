#!/usr/bin/env python3
"""MoBSE 를 ABIDE 에서 돌리는 범위 확인 smoke (결정 58) — fit 시간 · 학습 여부 · 붕괴만 본다.

**결정 58 의 범위**: 설계 메모 · smoke · 잠금안 초안까지. 잠금 · 본 실행은 하지 않는다. smoke 는 Δ 를 해석하지 않으며,
**test 피험자는 읽지도 예측하지도 않는다** — 학습 가능 여부는 train · val (학습 fold 안) 으로만 본다.

잠긴 코드는 고치지 않고 import 만 한다 (``mobse/v2`` · ``mobse/v3`` · ``scripts/i1`` 은 각 잠금이 해시한다):
``mobse.v2.features`` (창 FC · Fisher-z · scaler+PCA 10), ``mobse.v2.templates`` (K=3 bank),
``mobse.v2.models.CELL_SPEC`` (cell A = brain bank + 입력 의존 routing), ``mobse.v3.models.MoBSEv3`` (mean · embedding),
``mobse.v2.train`` 의 grid · batch · grad clip, ``mobse.v3.train.epochs_for_budget`` (update 예산 5,000).

AOMIC 과 다른 점 (설계 메모 ``docs/experiments/i1_mobse_abide_scoping_2026-10-13.md`` 의 결정 후보):
* 입력은 I1 공개 모델과 같은 ``abide.npy`` (시계열 앞 100 시점) — 사람당 30 시점 창 3 개 (0–29 · 30–59 · 60–89).
* ABIDE 에는 따로 쉬는 scan 이 없어 **bank · PCA 를 학습 fold 피험자의 같은 창으로** 만든다 (진단군 구분 없이).
* label 은 피험자 단위 (진단). 창 label = 피험자 label 로 학습하고, 평가는 피험자별 창 확률 평균.
* epoch 선택은 I1 공개 모델과 같은 규칙: 안쪽 val 의 피험자 평균 cross-entropy 최소 (같으면 앞 epoch).
* 상수 영역이 있는 창은 잠긴 특징 함수가 거부한다 — smoke 는 그런 피험자를 **빼고** 돌리고 수를 적는다 (잠정).
* grid 를 열지 않고 config 하나로 고정 (기본 0 = v3 본 실행 embedding 선택에서 가장 많았던 것).

Usage (h197, venv-mobse-v2, 저장소 사본 루트):
    PYTHONPATH=. python scripts/i1_mobse_abide/smoke.py --npy <abide.npy> --folds <folds_draw0.json> \
        --fold 0 --seed 1 --structure mean --cond orig --out <dir> [--device cuda] [--config-id 0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

WIN_STARTS = (0, 30, 60)
WIN_LEN = 30


def sha12(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """동점 평균 순위 AUC."""
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p))
    sp = p[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--npy", type=Path, required=True)
    ap.add_argument("--folds", type=Path, required=True)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--structure", choices=("mean", "embedding"), required=True)
    ap.add_argument("--cond", required=True, help="기록용 이름 (orig · n1_k0 …)")
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    import torch

    from mobse.v2.features import FeatureError, fit_transform_on_training_rest, stack_window_features
    from mobse.v2.models import CELL_SPEC, ModelConfig
    from mobse.v2.templates import build_bank, bank_seed, OUTER_FIT_INNER_FOLD
    from mobse.v2.train import BATCH_SIZE, GRAD_CLIP, PROB_CLIP, build_grid
    from mobse.v3.models import MoBSEv3
    from mobse.v3.train import UPDATE_BUDGET, epochs_for_budget

    t_all = time.perf_counter()
    a.out.mkdir(parents=True, exist_ok=True)
    d = np.load(a.npy, allow_pickle=True).item()
    ts, label = np.asarray(d["timeseires"], dtype=float), np.asarray(d["label"], dtype=int)
    fold = json.loads(a.folds.read_text())["folds"][a.fold]
    n_subj = len(label)

    # 창 (사람당 3 개) 과 상수 영역 검사 — 잠긴 특징 함수가 거부하는 창을 미리 센다
    wins = np.stack([ts[:, :, s:s + WIN_LEN] for s in WIN_STARTS], axis=1)  # (N, 3, roi, 30)
    const = (wins.std(axis=3) == 0).any(axis=2).any(axis=1)                  # 피험자 단위
    excluded = sorted(int(i) for i in np.flatnonzero(const))
    keep = lambda idx: [int(i) for i in idx if not const[i]]  # noqa: E731
    tr, va = keep(fold["train"]), keep(fold["val"])

    # 특징: 학습 · val 피험자의 창만 (test 는 읽지 않음)
    t0 = time.perf_counter()
    def feats(idx):
        ws = [wins[i, w].T for i in idx for w in range(len(WIN_STARTS))]       # (30, roi)
        return stack_window_features(ws)
    try:
        c_tr, z_tr = feats(tr)
        c_va, z_va = feats(va)
    except FeatureError as e:
        raise SystemExit(f"특징 계산 실패: {e}")
    t_feat = time.perf_counter() - t0

    t0 = time.perf_counter()
    subs_tr = [str(i) for i in tr]
    fit_subs = [s for s in subs_tr for _ in WIN_STARTS]
    transform = fit_transform_on_training_rest(z_tr, fit_subs)
    p_tr, p_va = transform.transform(z_tr), transform.transform(z_va)
    bank = build_bank(c_tr, p_tr, fit_subs, seed=bank_seed(a.fold, OUTER_FIT_INNER_FOLD))
    t_bank = time.perf_counter() - t0

    gc = {g.config_id: g for g in build_grid()}[a.config_id]
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)
    torch.cuda.manual_seed_all(a.seed)
    dev = torch.device(a.device if (a.device == "cpu" or torch.cuda.is_available()) else "cpu")
    cfg = ModelConfig(n_roi=ts.shape[1], n_samples=WIN_LEN, pca_dim=p_tr.shape[1], dropout=float(gc.dropout))
    spec = CELL_SPEC["A"]
    model = MoBSEv3(cfg, torch.as_tensor(bank.templates, dtype=torch.float32), routing=spec["routing"],
                    roi_structure=a.structure).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate, weight_decay=gc.weight_decay)
    lossf = torch.nn.CrossEntropyLoss()

    def tensors(idx, pca):
        x = torch.as_tensor(np.stack([wins[i, w] for i in idx for w in range(len(WIN_STARTS))]), dtype=torch.float32)
        y = torch.as_tensor(np.repeat(label[idx], len(WIN_STARTS)), dtype=torch.long)
        return x.to(dev), torch.as_tensor(pca, dtype=torch.float32).to(dev), y.to(dev)

    xt, pt, yt = tensors(tr, p_tr)
    xv, pv, _ = tensors(va, p_va)
    y_va = label[va]

    def subj_probs(x, p, n):
        model.eval()
        out = []
        with torch.no_grad():
            for s in range(0, len(x), 256):
                out.append(torch.softmax(model(x[s:s + 256], p[s:s + 256])["logits"], dim=1)[:, 1].cpu().numpy())
        return np.concatenate(out).reshape(n, len(WIN_STARTS)).mean(axis=1)

    def mean_ce(prob1, y):
        q = np.clip(np.where(y == 1, prob1, 1 - prob1), PROB_CLIP, 1 - PROB_CLIP)
        return float(-np.log(q).mean())

    n_epochs = epochs_for_budget(len(xt), batch_size=BATCH_SIZE, update_budget=UPDATE_BUDGET)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(a.seed)
    rows, best, best_state = [], None, None
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)
    t0 = time.perf_counter()
    for ep in range(n_epochs):
        model.train()
        order = torch.randperm(len(xt), generator=gen).to(dev)
        for s in range(0, len(xt), BATCH_SIZE):
            idx = order[s:s + BATCH_SIZE]
            opt.zero_grad(set_to_none=True)
            loss = lossf(model(xt[idx], pt[idx])["logits"], yt[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            opt.step()
        pv1 = subj_probs(xv, pv, len(va))
        row = {"epoch": ep, "val_loss": mean_ce(pv1, y_va), "val_auc": auc(y_va, pv1),
               "val_p_sd": float(pv1.std()), "val_classes": sorted(set((pv1 > .5).astype(int).tolist()))}
        rows.append(row)
        if best is None or row["val_loss"] < rows[best]["val_loss"]:   # 같으면 앞 epoch (I1 규칙)
            best = ep
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    t_train = time.perf_counter() - t0
    model.load_state_dict(best_state)
    ptr1 = subj_probs(xt, pt, len(tr))
    pv1 = subj_probs(xv, pv, len(va))
    sel = rows[best]
    summary = {
        "schema": "i1-mobse-abide-smoke-0.1", "decision": "결정 58 — 범위 확인 smoke (Δ 해석 없음 · test 미사용)",
        "npy": str(a.npy), "npy_sha12": sha12(a.npy), "folds_sha12": sha12(a.folds), "cond": a.cond,
        "fold": a.fold, "seed": a.seed, "structure": a.structure, "cell": "A", "config": gc.__dict__ if hasattr(gc, "__dict__") else str(gc),
        "n_subj": n_subj, "n_excluded_constant_roi": len(excluded),
        "n_train": len(tr), "n_val": len(va), "n_train_windows": int(len(xt)),
        "n_train_excluded": len(fold["train"]) - len(tr), "n_val_excluded": len(fold["val"]) - len(va),
        "bank_id": bank.bank_id, "transform_id": transform.artifact_id,
        "bank_cluster_sizes": np.bincount(bank.assignment, minlength=len(bank.templates)).tolist(),
        "n_epochs": n_epochs, "update_budget": UPDATE_BUDGET, "selected_epoch": best,
        "selected_val_loss": sel["val_loss"], "selected_val_auc": sel["val_auc"],
        "train_auc_at_selected": auc(label[tr], ptr1),
        "val_collapsed_at_selected": bool(pv1.std() < 1e-6 or len(set((pv1 > .5).astype(int).tolist())) == 1),
        "val_p_sd_at_selected": float(pv1.std()),
        "val_loss_first": rows[0]["val_loss"], "val_loss_min": min(r["val_loss"] for r in rows),
        "timing_s": {"features": t_feat, "transform_bank": t_bank, "train": t_train,
                     "per_epoch": t_train / n_epochs, "total": time.perf_counter() - t_all},
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(dev)) if dev.type == "cuda" else None,
        "device": str(dev), "torch": torch.__version__,
    }
    (a.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (a.out / "epochs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (a.out / "excluded_constant_roi.json").write_text(json.dumps(excluded))
    print(json.dumps({k: summary[k] for k in ("cond", "structure", "n_excluded_constant_roi", "n_train", "n_epochs",
                                              "selected_epoch", "selected_val_auc", "train_auc_at_selected",
                                              "val_collapsed_at_selected", "timing_s")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
