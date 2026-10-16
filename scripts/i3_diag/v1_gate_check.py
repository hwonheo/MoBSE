#!/usr/bin/env python3
"""v1 (PIOP1 run identity) main OOF 의 gate routing 점검 (결정 72) — 새 학습 없음, 저장 checkpoint 만 읽는다.

outer fold · seed 마다 ``mobse.v2.cli fit`` 과 같은 경로로 fold 변환 (training-rest scaler · PCA · bank · null) 을 다시
만들고, outer test 창을 저장 checkpoint 에 통과시켜:

* 저장 ``window_predictions.jsonl`` 과의 확률 최대 차이 (재현 확인 — CUDA 학습 · CPU 재평가라 0 이 아닐 수 있다).
* test 창 routing (expert 별 평균 · 표본 사이 SD · entropy) · label 사이 routing 차이 (dynamic 칸).
* **routing 고정 대조**: gate 를 그 fit 의 train 창 평균 weight 로 바꾼 test 확률 (dynamic 칸).
* 초기화 직후 (seed 고정, 학습 없음) gate 의 test entropy.
* seed 평균 run 확률로 낸 run 단위 BA (원래 · 고정 대조). 원래 값은 v1 보고값 (A 0.877 · C 0.893) 과 대조한다.

Usage (h197, 그 run 의 code 사본으로):
    PYTHONPATH=$D/main_oof/20260928_1cd4054_main_a2/code $VENV/bin/python -B scripts/i3_diag/v1_gate_check.py \
        --root $D/main_oof/20260928_1cd4054_main_a2 --out <out.json> [--cells A C]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from mobse.v2 import fitting as FIT
from mobse.v2 import templates as TPL
from mobse.v2.labels import class_index
from mobse.v2.models import ModelConfig, build_cell, load_checkpoint

D = Path("/mnt/data/mp2026/MoBSE_dataset")
V = D / "derivatives_v3"
REST = V / "wi02_ds002785_restingstate.jsonl"
TASKS = [V / "wi02_ds002785_emomatching.jsonl", V / "wi02_ds002785_workingmemory.jsonl"]
WINDOWS = V / "windows_piop1.jsonl"
FOLDS = V / "splits_piop1_p7" / "folds.json"
SEEDS = (42, 43, 44)
OUTER_INNER = 9          # outer 최종 적합 (templates.OUTER_FIT_INNER_FOLD)


def entropy(w: np.ndarray) -> np.ndarray:
    return -(w * np.log(np.clip(w, 1e-12, None))).sum(axis=1)


def forward(model, x, pca, override=None, bs=256):
    ps, ws = [], []
    model.eval()
    with torch.no_grad():
        for s in range(0, len(x), bs):
            xb, pb = torch.as_tensor(x[s:s + bs]), torch.as_tensor(pca[s:s + bs])
            ov = None if override is None else override.expand(len(xb), -1)
            o = model(xb, pb, routing_override=ov)
            ps.append(torch.softmax(o["logits"], dim=-1)[:, 1].numpy())
            ws.append(o["routing"].numpy())
    return np.concatenate(ps), np.concatenate(ws)


def run_ba(run_p: dict) -> float:
    """run 단위 balanced accuracy (class 별 정확도 평균)."""
    acc = defaultdict(list)
    for rk, p in run_p.items():
        t = class_index(FIT.task_of(rk))
        acc[t].append(int((p >= 0.5) == (t == 1)))
    return float(np.mean([np.mean(v) for v in acc.values()]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cells", nargs="+", default=["A", "C"])
    ap.add_argument("--null-seed", type=int, default=1729)
    a = ap.parse_args()

    folds = json.loads(FOLDS.read_text())
    task_refs = []
    for mp in TASKS:
        task_refs += FIT.refs_from_extract_manifest(mp, labelled=True)
    FIT.crosscheck_with_windows_manifest(task_refs, WINDOWS)
    rest_refs = FIT.refs_from_extract_manifest(REST, labelled=False)

    out = {"root": str(a.root), "cells": {}}
    run_p = {c: defaultdict(lambda: defaultdict(list)) for c in a.cells}   # cell → kind → run → [p]
    for o in range(5):
        fold = FIT.resolve_fold_subjects(folds, o, OUTER_INNER)
        tr = FIT.fit_fold_transform(rest_refs, fold.train, bank_seed=TPL.bank_seed(o, OUTER_INNER),
                                    null_seed=a.null_seed, n_components=10, k=3, density=0.2)
        train_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.train), tr)
        test_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.evaluate), tr)
        brain = torch.as_tensor(tr.brain.templates, dtype=torch.float32)
        null = torch.as_tensor(tr.null.templates, dtype=torch.float32)
        pca_tr = test_set.pca
        print(f"outer{o} test pca col mean {np.round(pca_tr.mean(0)[:3], 2)} col SD {np.round(pca_tr.std(0)[:3], 2)}", flush=True)
        for cell in a.cells:
            for seed in SEEDS:
                fd = a.root / "fits" / "outer" / f"o{o}" / f"{cell}_s{seed}"
                saved = {json.loads(l)["window_key"]: json.loads(l)["p_class1"]
                         for l in (fd / "window_predictions.jsonl").read_text().splitlines()}
                model = load_checkpoint(fd / "checkpoint.pt", brain, null, cell)
                p, w = forward(model, test_set.x, test_set.pca)
                diff = max(abs(saved[r.window_key] - float(q)) for r, q in zip(test_set.refs, p))
                rec = {"max_abs_diff_vs_saved": diff, "routing": model.routing}
                for rk, q in FIT.run_probabilities(test_set.refs, p).items():
                    run_p[cell]["orig"][rk].append(q)
                if model.routing == "dynamic":
                    y = test_set.y
                    rec.update({"test_entropy": float(entropy(w).mean()), "test_w_mean": w.mean(0).tolist(),
                                "test_w_sd": w.std(0).tolist(),
                                "label_gap": (w[y == 1].mean(0) - w[y == 0].mean(0)).tolist()})
                    _, w_train = forward(model, train_set.x, train_set.pca)
                    mw = torch.as_tensor(w_train.mean(0), dtype=torch.float32).view(1, -1)
                    p_fix, _ = forward(model, test_set.x, test_set.pca, override=mw)
                    rec["override_train_mean_w"] = mw.numpy().ravel().tolist()
                    for rk, q in FIT.run_probabilities(test_set.refs, p_fix).items():
                        run_p[cell]["fixed"][rk].append(q)
                    torch.manual_seed(seed)
                    cfg = ModelConfig(**model.cfg.as_dict())
                    init = build_cell(cell, cfg, brain, null).eval()
                    _, w0 = forward(init, test_set.x, test_set.pca)
                    rec["init_test_entropy"] = float(entropy(w0).mean())
                out["cells"].setdefault(cell, {})[f"o{o}_s{seed}"] = rec
                print(f"outer{o} {cell} s{seed} {json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items() if not isinstance(v, list)})}", flush=True)
    for cell in a.cells:
        for kind, d in run_p[cell].items():
            out["cells"][cell][f"run_ba_seedmean_{kind}"] = run_ba({rk: float(np.mean(v)) for rk, v in d.items()})
    out["ln3"] = float(np.log(3))
    args_out = a.out
    args_out.parent.mkdir(parents=True, exist_ok=True)
    args_out.write_text(json.dumps(out, indent=1))
    print(json.dumps({c: {k: v for k, v in out["cells"][c].items() if k.startswith("run_ba")} for c in a.cells}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
