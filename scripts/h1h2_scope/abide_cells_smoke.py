#!/usr/bin/env python3
"""ABIDE 에서 A–D · NG · SG 를 돌릴 수 있는지 보는 범위 확인 smoke (결정 67 ②) — 학습 여부 · 시간 · 붕괴만 본다.

**결정 67 의 범위**: 범위 확인까지. 잠금 · 본 실행은 하지 않는다. smoke 는 셀 사이 차이를 해석하지 않으며,
**test 피험자는 읽지도 예측하지도 않는다** — 학습 가능 여부는 train · val (학습 fold 안) 으로만 본다.

ABIDE MoBSE 팔 (결정 58 · 59, ``scripts/i1_mobse_abide/core.py``) 과 같은 입력 · 창 · 준비 · 학습 규칙을 쓰고,
cell 만 넓힌다. 잠긴 코드 (``mobse/v2`` · ``mobse/v3`` · ``scripts/i1_mobse_abide``) 는 import 만 한다.

* A · B · C · D: ``mobse.v2.models.CELL_SPEC`` (bank brain/null × routing dynamic/fixed) 를 ``MoBSEv3`` 에
  (mean · embedding). null 은 ``mobse.v3.templates.make_null_bank`` — 주 null 은 순열 (seed 1729), 확인용으로 rewire 하나.
* NG · SG: ``mobse.v2.models.build_comparator`` (v2 encoder — mean 구조만 있음). SG 의 graph 는 학습 fold 창 전부의
  평균 correlation (``build_single_graph``).

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/abide_cells_smoke.py --npy <abide.npy> --folds <folds_draw0.json> \
        --out <dir> [--fold 0] [--seed 1] [--device mps] [--only A_mean,NG]
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "i1_mobse_abide"))
import core  # noqa: E402  (ABIDE MoBSE 팔의 창 · 상수 영역 · seed 규칙을 그대로 쓴다)

RUNS = (
    [(f"{c}_{s}", c, s, "permutation") for c in ("A", "B", "C", "D") for s in ("mean", "embedding")]
    + [("C_mean_rewire", "C", "mean", "rewire"), ("NG", "NG", "mean", None), ("SG", "SG", "mean", None)]
)


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """동점 평균 순위 AUC."""
    from scipy.stats import rankdata
    r = rankdata(p)
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--npy", type=Path, required=True)
    ap.add_argument("--folds", type=Path, required=True)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--only", default="", help="쉼표로 고른 run 이름만 (기본 전부)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    import torch

    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    from mobse.v2.models import CELL_SPEC, ModelConfig, build_comparator
    from mobse.v2.templates import OUTER_FIT_INNER_FOLD, bank_seed, build_bank, build_single_graph
    from mobse.v2.train import BATCH_SIZE, GRAD_CLIP, PROB_CLIP, build_grid
    from mobse.v3.models import MoBSEv3
    from mobse.v3.templates import make_null_bank
    from mobse.v3.train import UPDATE_BUDGET, epochs_for_budget

    a.out.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()
    ts, label = core.load_npy(a.npy)
    wins = core.windows(ts)
    const = core.constant_subjects(wins)
    f = json.loads(a.folds.read_text())["folds"][a.fold]
    tr = [int(i) for i in f["train"] if not const[int(i)]]
    va = [int(i) for i in f["val"] if not const[int(i)]]
    nw = len(core.WIN_STARTS)

    t0 = time.perf_counter()
    c_tr, z_tr = stack_window_features([wins[i, w].T for i in tr for w in range(nw)])
    _, z_va = stack_window_features([wins[i, w].T for i in va for w in range(nw)])
    fit_subs = [str(i) for i in tr for _ in range(nw)]
    trans = fit_transform_on_training_rest(z_tr, fit_subs)
    p_tr, p_va = trans.transform(z_tr), trans.transform(z_va)
    bank = build_bank(c_tr, p_tr.astype(float), fit_subs, seed=bank_seed(a.fold, OUTER_FIT_INNER_FOLD),
                      allowed_subjects=[str(i) for i in tr])
    nulls = {k: make_null_bank(bank, kind=k) for k in ("permutation", "rewire")}
    single = build_single_graph(c_tr, fit_subs)
    t_prep = time.perf_counter() - t0
    print(f"prep {t_prep:.1f}s  train {len(tr)}  val {len(va)}  excluded_const {int(const.sum())}", flush=True)

    gc = {g.config_id: g for g in build_grid()}[core.CONFIG_ID]
    dev = torch.device(a.device)
    cfg = ModelConfig(n_roi=wins.shape[2], n_samples=core.WIN_LEN, pca_dim=p_tr.shape[1], dropout=float(gc.dropout))
    xt = torch.as_tensor(wins[tr].reshape(-1, wins.shape[2], core.WIN_LEN), dtype=torch.float32).to(dev)
    xv = torch.as_tensor(wins[va].reshape(-1, wins.shape[2], core.WIN_LEN), dtype=torch.float32).to(dev)
    pt = torch.as_tensor(p_tr, dtype=torch.float32).to(dev)
    pv = torch.as_tensor(p_va, dtype=torch.float32).to(dev)
    yt = torch.as_tensor(np.repeat(label[tr], nw), dtype=torch.long).to(dev)
    y_va = label[va]
    n_epochs = epochs_for_budget(len(xt), batch_size=BATCH_SIZE, update_budget=UPDATE_BUDGET)

    only = set(filter(None, a.only.split(",")))
    results = []
    for name, cell, structure, null_kind in RUNS:
        if only and name not in only:
            continue
        core.seed_all(a.seed)
        if cell in CELL_SPEC:
            spec = CELL_SPEC[cell]
            tmpl = bank.templates if spec["bank"] == "brain" else nulls[null_kind].templates
            model = MoBSEv3(cfg, torch.as_tensor(tmpl, dtype=torch.float32), routing=spec["routing"],
                            roi_structure=structure)
        else:
            g = torch.as_tensor(single.template, dtype=torch.float32) if cell == "SG" else None
            model = build_comparator(cell, cfg, single_graph=g)
        model = model.to(dev)
        n_params = int(sum(p.numel() for p in model.parameters() if p.requires_grad))
        opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate, weight_decay=gc.weight_decay)
        lossf = torch.nn.CrossEntropyLoss()

        def subj_probs(x, p, n):
            model.eval()
            out = []
            with torch.no_grad():
                for s in range(0, len(x), 256):
                    out.append(torch.softmax(model(x[s:s + 256], p[s:s + 256])["logits"], dim=1)[:, 1].cpu().numpy())
            return np.concatenate(out).reshape(n, nw).mean(axis=1)

        gen = torch.Generator(device="cpu")
        gen.manual_seed(a.seed)
        rows, best = [], None
        t0 = time.perf_counter()
        for ep in range(n_epochs):
            model.train()
            order = torch.randperm(len(xt), generator=gen).to(dev)
            for s in range(0, len(xt), BATCH_SIZE):
                b = order[s:s + BATCH_SIZE]
                opt.zero_grad(set_to_none=True)
                lossf(model(xt[b], pt[b])["logits"], yt[b]).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                opt.step()
            pv1 = subj_probs(xv, pv, len(va))
            q = np.clip(np.where(y_va == 1, pv1, 1 - pv1), PROB_CLIP, 1 - PROB_CLIP)
            rows.append({"epoch": ep, "val_loss": float(-np.log(q).mean()), "val_auc": auc(y_va, pv1),
                         "val_p_sd": float(pv1.std())})
            if best is None or rows[-1]["val_loss"] < rows[best]["val_loss"]:   # 같으면 앞 epoch (I1 규칙)
                best = ep
        sec = time.perf_counter() - t0
        r = {"run": name, "cell": cell, "structure": structure, "null_kind": null_kind, "n_params": n_params,
             "n_epochs": n_epochs, "selected_epoch": best, "val_loss_selected": rows[best]["val_loss"],
             "val_auc_selected": rows[best]["val_auc"], "val_p_sd_selected": rows[best]["val_p_sd"],
             "collapsed_selected": rows[best]["val_p_sd"] < 1e-3, "seconds": sec}
        results.append(r)
        (a.out / f"epochs_{name}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        print(json.dumps(r, ensure_ascii=False), flush=True)

    summary = {"schema": "h1h2-scope-abide-smoke-0.1", "decision": "결정 67 ② — 범위 확인 smoke (셀 차이 해석 없음 · test 미사용)",
               "npy": str(a.npy), "npy_sha12": core.sha256(a.npy)[:12], "folds_sha12": core.sha256(a.folds)[:12],
               "fold": a.fold, "seed": a.seed, "device": str(dev), "host": platform.node(), "torch": torch.__version__,
               "n_train": len(tr), "n_val": len(va), "n_excluded_constant_roi": int(const.sum()),
               "n_train_windows": int(len(xt)), "update_budget": UPDATE_BUDGET, "config_id": core.CONFIG_ID,
               "bank_id": bank.bank_id, "transform_id": trans.artifact_id,
               "null_ids": {k: v.bank_id for k, v in nulls.items()},
               "prep_seconds": t_prep, "total_seconds": time.perf_counter() - t_all, "runs": results}
    (a.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
