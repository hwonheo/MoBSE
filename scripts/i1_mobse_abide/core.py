"""ABIDE MoBSE 팔의 핵심 — 입력 목록 · 창 · 준비 (PCA · bank) · 학습 한 판 (결정 58 · 59).

설계는 ``docs/experiments/i1_mobse_abide_lock_v1.md`` (잠금 문서) 가 정본이다. 요지:

* 입력은 I1 공개 모델과 같은 ``abide.npy`` (원판) 와 I1 본 실행의 ``inputs/abide/<cond>_k<k>/abide.npy`` (n0 k0 · n1 k0–4 ·
  n2 k0–4). n3 은 시계열을 바꾸지 않아 MoBSE 에 효과가 없으므로 쓰지 않는다 (결정 59 D2).
* 사람당 30 시점 창 3 개 (0–29 · 30–59 · 60–89). 창 안에 상수 영역이 있는 피험자 (원판 기준 46 명) 는 잠긴 특징 함수가
  거부하므로 빼고, 분석은 공개 모델까지 같은 963 명으로 한다 (결정 59 D1).
* 준비 (입력 × fold 마다 한 번): 창 FC · Fisher-z (``mobse.v2.features``) → **학습 fold 피험자의 창만으로** scaler + PCA 10 과
  K=3 bank (``mobse.v2.templates``) 를 만든다. val · test 창은 그 고정 변환을 통과시키기만 한다.
* 학습 (입력 × fold × 구조 × seed): cell A (brain bank + 입력 의존 routing) ``MoBSEv3`` (mean · embedding), config 0 고정
  (결정 59 D5), batch 32 · grad clip 1 · update 예산 5,000. epoch 은 I1 공개 모델 규칙 — 안쪽 val 의 피험자 평균
  cross-entropy 최소 (같으면 앞 epoch) — 의 가중치로 test 를 예측한다.

잠긴 코드 (``mobse/v2`` · ``mobse/v3`` · ``scripts/i1``) 는 import 만 한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

WIN_STARTS = (0, 30, 60)
WIN_LEN = 30
SEEDS = (1, 2, 3)
N_FOLDS = 5
K = 5
CONFIG_ID = 0
STRUCTURES = ("mean", "embedding")
ORIG_NPY = "i1/data/abide_noglobal_braingb/abide.npy"
FOLDS = "i1/data/folds_draw0.json"
I1_RUN = "i1/main/20261005_ac3bad06_a2"


def inputs(data_root: Path) -> List[Tuple[str, int, Path]]:
    """(cond, k, 경로) 목록 — 원판 · n0 은 k0 만, n1 · n2 는 k0–4."""
    out = [("orig", 0, data_root / ORIG_NPY), ("n0", 0, data_root / I1_RUN / "inputs/abide/n0_k0/abide.npy")]
    for c in ("n1", "n2"):
        out += [(c, k, data_root / I1_RUN / f"inputs/abide/{c}_k{k}/abide.npy") for k in range(K)]
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def load_npy(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    d = np.load(path, allow_pickle=True).item()
    return np.asarray(d["timeseires"], dtype=float), np.asarray(d["label"], dtype=int)


def windows(ts: np.ndarray) -> np.ndarray:
    """(N, roi, T) → (N, 3, roi, 30)."""
    if ts.shape[2] < WIN_STARTS[-1] + WIN_LEN:
        raise ValueError(f"시점 {ts.shape[2]} 개로 창 3 개를 만들 수 없다")
    return np.stack([ts[:, :, s:s + WIN_LEN] for s in WIN_STARTS], axis=1)


def constant_subjects(wins: np.ndarray) -> np.ndarray:
    """창 하나라도 상수 영역 (표준편차 0) 이 있는 피험자의 bool mask — 잠긴 특징 함수의 거부 조건과 같다."""
    return (wins.std(axis=3) == 0).any(axis=2).any(axis=1)


def kept_index(data_root: Path) -> List[int]:
    """원판 기준으로 남는 피험자 index (0–1008 번호). 모든 입력에서 같은 집합이어야 한다 (prep 이 대조)."""
    ts, _ = load_npy(data_root / ORIG_NPY)
    return [int(i) for i in np.flatnonzero(~constant_subjects(windows(ts)))]


def seed_all(seed: int) -> None:
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


# ───────────────────────────── 준비

def prep_one(npy: Path, folds: dict, fold: int, kept: Sequence[int], out_dir: Path) -> dict:
    """입력 하나 · fold 하나의 PCA 특징과 bank 를 만든다. 학습 fold 피험자만 변환 · bank fit 에 들어간다."""
    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    from mobse.v2.templates import OUTER_FIT_INNER_FOLD, bank_seed, build_bank

    t0 = time.perf_counter()
    ts, label = load_npy(npy)
    wins = windows(ts)
    const = constant_subjects(wins)
    kept_here = [int(i) for i in np.flatnonzero(~const)]
    if kept_here != list(kept):
        raise SystemExit(f"{npy}: 상수 영역 피험자 집합이 원판과 다르다 ({len(kept_here)} 대 {len(kept)})")
    kset = set(kept)
    f = folds["folds"][fold]
    part = {r: [int(i) for i in f[r] if int(i) in kset] for r in ("train", "val", "test")}
    if set(part["train"]) & (set(part["val"]) | set(part["test"])) or set(part["val"]) & set(part["test"]):
        raise SystemExit("fold 의 train · val · test 가 겹친다")

    feats = {}
    for r, idx in part.items():
        feats[r] = stack_window_features([wins[i, w].T for i in idx for w in range(len(WIN_STARTS))])
    t_feat = time.perf_counter() - t0
    fit_subs = [str(i) for i in part["train"] for _ in WIN_STARTS]
    tr = fit_transform_on_training_rest(feats["train"][1], fit_subs)
    pca = {r: tr.transform(feats[r][1]).astype(np.float32) for r in part}
    bank = build_bank(feats["train"][0], pca["train"].astype(float), fit_subs,
                      seed=bank_seed(fold, OUTER_FIT_INNER_FOLD), allowed_subjects=[str(i) for i in part["train"]])
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "prep.tmp.npz", **{f"pca_{r}": pca[r] for r in part},
             **{f"idx_{r}": np.asarray(part[r]) for r in part}, bank=bank.templates.astype(np.float32))
    os.replace(out_dir / "prep.tmp.npz", out_dir / "prep.npz")
    meta = {"npy": str(npy), "npy_sha256": sha256(npy), "fold": fold,
            "n": {r: len(v) for r, v in part.items()},
            "excluded_in_fold": {r: len(f[r]) - len(part[r]) for r in part},
            "transform_id": tr.artifact_id, "bank_id": bank.bank_id,
            "bank_cluster_sizes": np.bincount(bank.assignment, minlength=len(bank.templates)).tolist(),
            "fit_subjects_are_train_only": sorted(set(int(s) for s in fit_subs)) == sorted(part["train"]),
            "timing_s": {"features": t_feat, "total": time.perf_counter() - t0}}
    atomic_write(out_dir / "prep.json", json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


# ───────────────────────────── 학습

def mean_ce(prob1: np.ndarray, y: np.ndarray, clip: float) -> float:
    q = np.clip(np.where(y == 1, prob1, 1 - prob1), clip, 1 - clip)
    return float(-np.log(q).mean())


def fit_one(npy: Path, prep_dir: Path, structure: str, seed: int, out_dir: Path, device: str = "cuda") -> dict:
    """준비물 하나로 MoBSE cell A 한 판을 학습하고 test 피험자 예측을 쓴다 (I1 배치)."""
    import torch

    from mobse.v2.models import CELL_SPEC, ModelConfig
    from mobse.v2.train import BATCH_SIZE, GRAD_CLIP, PROB_CLIP, build_grid
    from mobse.v3.models import MoBSEv3
    from mobse.v3.train import UPDATE_BUDGET, epochs_for_budget

    t0 = time.perf_counter()
    ts, label = load_npy(npy)
    wins = windows(ts).astype(np.float32)
    z = np.load(prep_dir / "prep.npz")
    idx = {r: z[f"idx_{r}"].astype(int) for r in ("train", "val", "test")}
    gc = {g.config_id: g for g in build_grid()}[CONFIG_ID]
    seed_all(seed)
    dev = torch.device(device if (device == "cpu" or torch.cuda.is_available()) else "cpu")
    cfg = ModelConfig(n_roi=wins.shape[2], n_samples=WIN_LEN, pca_dim=z["pca_train"].shape[1], dropout=float(gc.dropout))
    spec = CELL_SPEC["A"]
    model = MoBSEv3(cfg, torch.as_tensor(z["bank"], dtype=torch.float32), routing=spec["routing"],
                    roi_structure=structure).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate, weight_decay=gc.weight_decay)
    lossf = torch.nn.CrossEntropyLoss()

    def tens(r):
        x = torch.as_tensor(wins[idx[r]].reshape(-1, wins.shape[2], WIN_LEN)).to(dev)
        p = torch.as_tensor(z[f"pca_{r}"]).to(dev)
        y = torch.as_tensor(np.repeat(label[idx[r]], len(WIN_STARTS)), dtype=torch.long).to(dev)
        return x, p, y

    (xt, pt, yt), (xv, pv, _), (xs, ps, _) = tens("train"), tens("val"), tens("test")

    def subj_probs(x, p, n):
        model.eval()
        out = []
        with torch.no_grad():
            for s in range(0, len(x), 256):
                out.append(torch.softmax(model(x[s:s + 256], p[s:s + 256])["logits"], dim=1)[:, 1].cpu().numpy())
        return np.concatenate(out).reshape(n, len(WIN_STARTS)).mean(axis=1)

    n_epochs = epochs_for_budget(len(xt), batch_size=BATCH_SIZE, update_budget=UPDATE_BUDGET)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    rows, best, best_state = [], None, None
    y_val = label[idx["val"]]
    for ep in range(n_epochs):
        model.train()
        order = torch.randperm(len(xt), generator=gen).to(dev)
        for s in range(0, len(xt), BATCH_SIZE):
            b = order[s:s + BATCH_SIZE]
            opt.zero_grad(set_to_none=True)
            loss = lossf(model(xt[b], pt[b])["logits"], yt[b])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            opt.step()
        pv1 = subj_probs(xv, pv, len(idx["val"]))
        rows.append({"epoch": ep, "val_loss": mean_ce(pv1, y_val, PROB_CLIP)})
        if best is None or rows[-1]["val_loss"] < rows[best]["val_loss"]:     # 같으면 앞 epoch (I1 규칙)
            best = ep
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    p_test = subj_probs(xs, ps, len(idx["test"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "epochs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    atomic_write(out_dir / "predictions.jsonl", "".join(
        json.dumps({"subject_index": int(i), "label": int(label[i]), "p1": float(p)}) + "\n"
        for i, p in zip(idx["test"], p_test)))
    summary = {"structure": structure, "seed": seed, "cell": "A", "config_id": CONFIG_ID, "npy": str(npy),
               "prep_dir": str(prep_dir), "n_epochs": n_epochs, "selected_epoch": best,
               "val_loss": rows[best]["val_loss"], "n_test": int(len(idx["test"])),
               "test_p_sd": float(p_test.std()), "seconds": time.perf_counter() - t0, "device": str(dev),
               "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(dev)) if dev.type == "cuda" else None}
    atomic_write(out_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=1))
    return summary
