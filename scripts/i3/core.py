"""I3 (exploratory v4) 의 핵심 — 블록 · 창 · 분할 · 준비 (PCA · bank · null) · 학습 한 판 (결정 67 · 68 · 69).

설계는 ``docs/experiments/i3_lock_v1.md`` (잠금 문서) 가 정본이다. 요지:

* target: PIOP1 emomatching 블록 조건 (control 0 · emotion 1). 블록 = 같은 trial_type 이 이어지는 30 s, run 마다 8 개.
* 창: [블록 시작 + 6 s, 끝 + 6 s) 의 15 frame. 입력은 **blockz** (블록 안 ROI 별 평균 0 · 분산 1) — 활성 크기를 지워 FC 만 남김.
* 분할: WI-03 ``folds.json`` 의 outer 5 fold 그대로. 학습은 outer 마다 **inner fold 0** 의 train (66 명), best checkpoint 는
  inner fold 0 의 val (34 명), 예측은 outer test.
* bank · PCA: 학습 피험자 (inner train) 의 rest 60 s 창 (``derivatives_v3``, 사람당 4 개) 으로 K=3 · PCA 10. 과제 창은 그 고정
  변환을 통과시키기만 한다.
* 칸: A–D × {mean, embedding} (``MoBSEv3``) + NG · SG (``mobse.v2`` 비교 모델, mean). null 은 주 순열 (seed 1729) +
  spin · rewire 민감도 (C · D 만).
* 학습: config 0 고정, batch 32, grad clip 1, update 예산 5,000 (epoch 상한 없음), best = val 블록 평균 cross-entropy 최소
  (같으면 앞 epoch).

잠긴 코드 (``mobse/v2`` · ``mobse/v3``) 는 import 만 한다.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

LAG_S = 6.0
N_BLOCKS = 8
BLOCK_FRAMES = 15
CONDS = ("control", "emotion")
SEEDS = (42, 43, 44)
CONFIG_ID = 0
INNER_FOLD = 0
N_OUTER = 5
STRUCTURES = ("mean", "embedding")
NULL_SEED = 1729
MAIN_CELLS = [(c, s, "permutation") for c in ("A", "B", "C", "D") for s in STRUCTURES] + [("NG", "mean", None),
                                                                                       ("SG", "mean", None)]
SENS_CELLS = [(c, s, k) for k in ("spin", "rewire") for c in ("C", "D") for s in STRUCTURES]
ATLAS = "atlas/tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz"
EVENTS = "raw/aomic_wave1/ds002785/raw/{s}/func/{s}_task-emomatching_acq-seq_events.tsv"
REST = "rest_win/derivatives_v3/{s}/{s}_task-restingstate_acq-mb3_win-{i}.npy"
FULL_TS = "full_ts/{s}_emomatching.npz"
FOLDS = "splits/folds.json"


def cell_name(cell: str, structure: str, null_kind) -> str:
    if cell in ("NG", "SG"):
        return cell
    return f"{cell}_{structure}" + ("" if null_kind in (None, "permutation") else f"_{null_kind}")


# ───────────────────────────── 자료

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def blocks(events: Path) -> List[dict]:
    """events → 블록 목록. 블록 = 같은 trial_type 연속 구간, 끝 = 마지막 onset + trial 간격 (중앙값)."""
    rows = list(csv.DictReader(Path(events).open(), delimiter="\t"))
    onsets = np.array([float(r["onset"]) for r in rows])
    soa = float(np.median(np.diff(onsets)))
    out: List[dict] = []
    for r, t in zip(rows, onsets):
        if not out or r["trial_type"] != out[-1]["cond"]:
            out.append({"cond": r["trial_type"], "start": float(t), "end": float(t) + soa, "n_trials": 0})
        out[-1]["end"] = float(t) + soa
        out[-1]["n_trials"] += 1
    return out


def blockz(w: np.ndarray) -> np.ndarray:
    """(frames, roi) → 블록 안 ROI 별 평균 0 · 분산 1. 상수 ROI 가 있으면 멈춘다 (임의로 고치지 않음)."""
    sd = w.std(axis=0)
    if np.any(sd == 0):
        raise ValueError("블록 안에 상수 ROI 가 있다")
    return (w - w.mean(axis=0)) / sd


def task_blocks(root: Path, subject: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """한 사람의 (blockz 창 (8, 15, roi), 원 창 (8, 15, roi), label (8,))."""
    z = np.load(root / FULL_TS.format(s=subject))
    ts, t = z["ts"].astype(float), z["times"]
    blk = blocks(root / EVENTS.format(s=subject))
    if len(blk) != N_BLOCKS or [b["cond"] for b in blk] != list(CONDS) * (N_BLOCKS // 2):
        raise ValueError(f"{subject}: 블록 구조가 잠긴 형태 (c e × 4) 가 아니다")
    raw, bz, y = [], [], []
    for b in blk:
        m = (t >= b["start"] + LAG_S) & (t < b["end"] + LAG_S)
        if int(m.sum()) != BLOCK_FRAMES:
            raise ValueError(f"{subject}: 블록 창 frame 수 {int(m.sum())} ≠ {BLOCK_FRAMES}")
        raw.append(ts[m])
        bz.append(blockz(ts[m]))
        y.append(CONDS.index(b["cond"]))
    return np.stack(bz), np.stack(raw), np.array(y)


def rest_windows(root: Path, subject: str) -> List[np.ndarray]:
    return [np.load(root / REST.format(s=subject, i=i)).astype(float) for i in range(4)]


def fold_parts(folds: dict, outer: int) -> Dict[str, List[str]]:
    """outer fold 의 train (inner fold 0 train) · val (inner fold 0 val) · test. 서로 겹치면 멈춘다."""
    f = folds["outer_folds"][outer]
    inner = f["inner"][INNER_FOLD]
    strip = lambda xs: [x.split(":")[1] for x in xs]  # noqa: E731
    parts = {"train": strip(inner["train_subjects"]), "val": strip(inner["val_subjects"]),
             "test": strip(f["test_subjects"])}
    sets = {k: set(v) for k, v in parts.items()}
    if sets["train"] & sets["val"] or sets["train"] & sets["test"] or sets["val"] & sets["test"]:
        raise SystemExit(f"outer {outer}: train · val · test 가 겹친다")
    if sets["train"] | sets["val"] != {x.split(":")[1] for x in f["train_subjects"]}:
        raise SystemExit(f"outer {outer}: inner train ∪ val 이 outer train 과 다르다")
    return parts


def smoke_folds(pilot: Sequence[str]) -> dict:
    """smoke 전용 가짜 분할 — pilot 31 명만으로 outer 1 개 (test 6 · inner train 19 · val 6). main 을 쓰지 않는다."""
    order = list(np.random.default_rng(20261016).permutation(sorted(pilot)))
    tag = lambda xs: [f"ds002785:{x}" for x in sorted(xs)]  # noqa: E731
    test, val, train = order[:6], order[6:12], order[12:]
    return {"outer_folds": [{"outer_fold": 0, "test_subjects": tag(test), "train_subjects": tag(train + val),
                             "inner": [{"inner_fold": 0, "train_subjects": tag(train), "val_subjects": tag(val)}]}],
            "smoke": True}


def seed_all(seed: int) -> None:
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


# ───────────────────────────── 준비

def prep_one(root: Path, folds: dict, outer: int, out_dir: Path) -> dict:
    """outer fold 하나의 창 · PCA 특징 · bank · null (순열 · spin · rewire) · single graph 를 만든다."""
    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    from mobse.v2.templates import bank_seed, build_bank, build_single_graph
    from mobse.v3.templates import make_null_bank, roi_centroids

    t0 = time.perf_counter()
    parts = fold_parts(folds, outer)
    rest = [w for s in parts["train"] for w in rest_windows(root, s)]
    rest_subs = [s for s in parts["train"] for _ in range(4)]
    c_rest, z_rest = stack_window_features(rest)
    trans = fit_transform_on_training_rest(z_rest, rest_subs)
    bank = build_bank(c_rest, trans.transform(z_rest).astype(float), rest_subs, seed=bank_seed(outer, INNER_FOLD),
                      allowed_subjects=list(parts["train"]))
    coords, is_left = roi_centroids(root / ATLAS)
    nulls = {"permutation": make_null_bank(bank, kind="permutation", seed=NULL_SEED),
             "spin": make_null_bank(bank, kind="spin", seed=NULL_SEED, coords=coords, is_left=is_left),
             "rewire": make_null_bank(bank, kind="rewire", seed=NULL_SEED)}
    single = build_single_graph(c_rest, rest_subs)
    arrays: Dict[str, np.ndarray] = {}
    for r, subs in parts.items():
        bz, raw, y = zip(*(task_blocks(root, s) for s in subs))
        x = np.concatenate(bz)                                           # (n*8, 15, roi)
        _, zf = stack_window_features(list(x))
        arrays[f"x_{r}"] = x.transpose(0, 2, 1).astype(np.float32)        # (n*8, roi, 15)
        arrays[f"pca_{r}"] = trans.transform(zf).astype(np.float32)
        arrays[f"fcz_{r}"] = zf.astype(np.float32)                       # S 용 FC 특징
        arrays[f"act_{r}"] = np.concatenate(raw).mean(axis=1).astype(np.float32)   # 활성 참고값 (원 입력 블록 평균)
        arrays[f"y_{r}"] = np.concatenate(y)
        arrays[f"subj_{r}"] = np.repeat(np.array(subs), N_BLOCKS)
        arrays[f"block_{r}"] = np.tile(np.arange(N_BLOCKS), len(subs))
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "prep.tmp.npz", **arrays, bank=bank.templates.astype(np.float32),
             **{f"null_{k}": v.templates.astype(np.float32) for k, v in nulls.items()},
             single=single.template.astype(np.float32))
    os.replace(out_dir / "prep.tmp.npz", out_dir / "prep.npz")
    meta = {"outer": outer, "n_subjects": {r: len(v) for r, v in parts.items()},
            "n_windows": {r: int(len(arrays[f"y_{r}"])) for r in parts}, "transform_id": trans.artifact_id,
            "bank_id": bank.bank_id, "null_ids": {k: v.bank_id for k, v in nulls.items()},
            "single_graph_id": single.graph_id,
            "bank_cluster_sizes": np.bincount(bank.assignment, minlength=len(bank.templates)).tolist(),
            "seconds": time.perf_counter() - t0}
    atomic_write(out_dir / "prep.json", json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


# ───────────────────────────── 학습

def fit_one(prep_dir: Path, cell: str, structure: str, null_kind, seed: int, out_dir: Path,
            device: str = "mps") -> dict:
    """준비물 하나로 한 칸 · 한 seed 를 학습하고 test 블록 예측을 쓴다."""
    import torch

    from mobse.v2.models import CELL_SPEC, ModelConfig, build_comparator
    from mobse.v2.train import BATCH_SIZE, GRAD_CLIP, PROB_CLIP, build_grid
    from mobse.v3.models import MoBSEv3
    from mobse.v3.train import UPDATE_BUDGET, epochs_for_budget

    t0 = time.perf_counter()
    z = np.load(prep_dir / "prep.npz")
    gc = {g.config_id: g for g in build_grid()}[CONFIG_ID]
    seed_all(seed)
    dev = torch.device(device)
    cfg = ModelConfig(n_roi=z["x_train"].shape[1], n_samples=BLOCK_FRAMES, pca_dim=z["pca_train"].shape[1],
                      dropout=float(gc.dropout))
    if cell in CELL_SPEC:
        spec = CELL_SPEC[cell]
        tm = z["bank"] if spec["bank"] == "brain" else z[f"null_{null_kind}"]
        model = MoBSEv3(cfg, torch.as_tensor(tm), routing=spec["routing"], roi_structure=structure)
    else:
        model = build_comparator(cell, cfg, single_graph=torch.as_tensor(z["single"]) if cell == "SG" else None)
    model = model.to(dev)
    n_params = int(sum(p.numel() for p in model.parameters() if p.requires_grad))
    opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate, weight_decay=gc.weight_decay)
    lossf = torch.nn.CrossEntropyLoss()
    T = {r: (torch.as_tensor(z[f"x_{r}"]).to(dev), torch.as_tensor(z[f"pca_{r}"]).to(dev)) for r in ("train", "val", "test")}
    yt = torch.as_tensor(z["y_train"], dtype=torch.long).to(dev)
    y_val = z["y_val"]

    def probs(r):
        model.eval()
        x, p = T[r]
        out = []
        with torch.no_grad():
            for s in range(0, len(x), 512):
                out.append(torch.softmax(model(x[s:s + 512], p[s:s + 512])["logits"], dim=1)[:, 1].cpu().numpy())
        return np.concatenate(out)

    xt, pt = T["train"]
    n_epochs = epochs_for_budget(len(xt), batch_size=BATCH_SIZE, update_budget=UPDATE_BUDGET)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    rows, best, best_state = [], None, None
    for ep in range(n_epochs):
        model.train()
        order = torch.randperm(len(xt), generator=gen).to(dev)
        for s in range(0, len(xt), BATCH_SIZE):
            b = order[s:s + BATCH_SIZE]
            opt.zero_grad(set_to_none=True)
            lossf(model(xt[b], pt[b])["logits"], yt[b]).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            opt.step()
        pv = probs("val")
        q = np.clip(np.where(y_val == 1, pv, 1 - pv), PROB_CLIP, 1 - PROB_CLIP)
        rows.append({"epoch": ep, "val_loss": float(-np.log(q).mean()), "val_p_sd": float(pv.std())})
        if best is None or rows[-1]["val_loss"] < rows[best]["val_loss"]:     # 같으면 앞 epoch
            best = ep
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    p_test = probs("test")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "epochs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    atomic_write(out_dir / "predictions.jsonl", "".join(
        json.dumps({"subject": str(s), "block": int(b), "label": int(y), "p1": float(p)}) + "\n"
        for s, b, y, p in zip(z["subj_test"], z["block_test"], z["y_test"], p_test)))
    summary = {"cell": cell, "structure": structure, "null_kind": null_kind, "seed": seed, "config_id": CONFIG_ID,
               "n_params": n_params, "n_epochs": n_epochs, "selected_epoch": best,
               "val_loss": rows[best]["val_loss"], "val_p_sd": rows[best]["val_p_sd"],
               "n_test_blocks": int(len(p_test)), "test_p_sd": float(p_test.std()),
               "seconds": time.perf_counter() - t0, "device": str(dev)}
    atomic_write(out_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=1))
    return summary


def fit_s(prep_dir: Path, out_dir: Path) -> dict:
    """S (blockz FC logistic) 와 활성 참고값 (원 입력 블록 평균 logistic) — 같은 학습 피험자, C=1 고정, 결정론."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    z = np.load(prep_dir / "prep.npz")
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, key in (("S_fc_logistic", "fcz"), ("REF_activation_logistic", "act")):
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
        clf.fit(z[f"{key}_train"], z["y_train"])
        p = clf.predict_proba(z[f"{key}_test"])[:, 1]
        atomic_write(out_dir / f"{name}.jsonl", "".join(
            json.dumps({"subject": str(s), "block": int(b), "label": int(y), "p1": float(q)}) + "\n"
            for s, b, y, q in zip(z["subj_test"], z["block_test"], z["y_test"], p)))
        res[name] = {"n_features": int(z[f"{key}_train"].shape[1]), "n_test_blocks": int(len(p))}
    atomic_write(out_dir / "summary.json", json.dumps(res, indent=1))
    return res
