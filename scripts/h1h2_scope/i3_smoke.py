#!/usr/bin/env python3
"""I3 범위 확인 smoke (결정 67 ①) — pilot 31 명 emomatching 블록 (15 시점) 으로 MoBSE 셀이 학습되는지만 본다.

**셀 차이를 해석하지 않는다.** pilot 안에서 학습 25 · val 6 명으로 나누고 (seed 20261016), 학습 여부 · 붕괴 · 시간만 본다.

* bank · PCA: 학습 피험자의 **rest 60 s 창** (``derivatives_v3`` 저장분, 사람당 4 개) — 원래 설계 (training-rest bank) 그대로.
* 과제 창: emomatching 블록 [시작 + lag, 끝 + lag) 의 15 frame. 입력은 **블록 안 ROI 별 z-score** (``blockz``) —
  활성 크기 (평균 · 분산) 를 지워 FC 만 남긴다. 기준선 확인 (``i3_baselines.py``) 에서 활성만으로 BA 0.95–0.98 이었기 때문.
* 셀: A–D (mean) · A (embedding) · NG · SG. 학습 규칙은 ABIDE 팔과 같다 (config 0, update 예산 5,000, val 피험자
  평균 cross-entropy 최소 epoch).
* 참고 기준선: 같은 분할에서 blockz 창 FC (LedoitWolf → Fisher z) logistic 의 val 값.

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/i3_smoke.py --aomic data/h1h2_scope/aomic --out <dir> [--lag 6]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "i1_mobse_abide"))
import core  # noqa: E402
from abide_cells_smoke import auc  # noqa: E402
from i3_baselines import blocks  # noqa: E402

RUNS = [("A_mean", "A", "mean"), ("B_mean", "B", "mean"), ("C_mean", "C", "mean"), ("D_mean", "D", "mean"),
        ("A_embedding", "A", "embedding"), ("NG", "NG", "mean"), ("SG", "SG", "mean")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--aomic", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lag", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--device", default="mps")
    a = ap.parse_args()

    import torch
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    from mobse.v2.models import CELL_SPEC, ModelConfig, build_comparator
    from mobse.v2.templates import build_bank, build_single_graph
    from mobse.v2.train import BATCH_SIZE, GRAD_CLIP, PROB_CLIP, build_grid
    from mobse.v3.models import MoBSEv3
    from mobse.v3.templates import make_null_bank
    from mobse.v3.train import UPDATE_BUDGET, epochs_for_budget

    a.out.mkdir(parents=True, exist_ok=True)
    subs = a.aomic.joinpath("pilot_ids.txt").read_text().split()
    rng = np.random.default_rng(20261016)
    order = list(rng.permutation(subs))
    va_s, tr_s = sorted(order[:6]), sorted(order[6:])

    def task_windows(s):
        z = np.load(a.aomic / "full_ts" / f"{s}_emomatching.npz")
        ts, t = z["ts"].astype(float), z["times"]
        blk, _ = blocks(a.aomic / "raw/aomic_wave1/ds002785/raw" / s / "func" / f"{s}_task-emomatching_acq-seq_events.tsv")
        X, y = [], []
        for b in blk:
            m = (t >= b["start"] + a.lag) & (t < b["end"] + a.lag)
            w = ts[m]
            X.append((w - w.mean(0)) / w.std(0))                       # blockz: (15, roi)
            y.append(0 if b["cond"] == "control" else 1)
        return X, y

    def rest_windows(s):
        return [np.load(a.aomic / "rest_win/derivatives_v3" / s / f"{s}_task-restingstate_acq-mb3_win-{i}.npy").astype(float)
                for i in range(4)]

    t0 = time.perf_counter()
    rest = [w for s in tr_s for w in rest_windows(s)]
    rest_subs = [s for s in tr_s for _ in range(4)]
    c_rest, z_rest = stack_window_features(rest)
    trans = fit_transform_on_training_rest(z_rest, rest_subs)
    bank = build_bank(c_rest, trans.transform(z_rest).astype(float), rest_subs, seed=1, allowed_subjects=tr_s)
    null = make_null_bank(bank, kind="permutation")
    single = build_single_graph(c_rest, rest_subs)

    def split(ss):
        X, y, g = [], [], []
        for s in ss:
            xs, ys = task_windows(s)
            X += xs
            y += ys
            g += [s] * len(ys)
        _, zf = stack_window_features(X)
        return np.stack(X), np.array(y), np.array(g), zf

    Xt, yt_np, gt, zt = split(tr_s)
    Xv, yv_np, gv, zv = split(va_s)
    pt_np, pv_np = trans.transform(zt), trans.transform(zv)
    t_prep = time.perf_counter() - t0

    # 참고 기준선: blockz 창 FC logistic (같은 분할)
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000)).fit(zt, yt_np)
    pvl = clf.predict_proba(zv)[:, 1]
    base = {"fc_logistic_val_ba": float(balanced_accuracy_score(yv_np, pvl > .5)), "fc_logistic_val_auc": auc(yv_np, pvl)}
    print(json.dumps({"prep_s": t_prep, "n_train_win": len(yt_np), "n_val_win": len(yv_np), **base}), flush=True)

    gc = {g.config_id: g for g in build_grid()}[0]
    dev = torch.device(a.device)
    cfg = ModelConfig(n_roi=100, n_samples=Xt.shape[1], pca_dim=pt_np.shape[1], dropout=float(gc.dropout))
    xt = torch.as_tensor(Xt.transpose(0, 2, 1), dtype=torch.float32).to(dev)   # (N, roi, 15)
    xv = torch.as_tensor(Xv.transpose(0, 2, 1), dtype=torch.float32).to(dev)
    pt = torch.as_tensor(pt_np, dtype=torch.float32).to(dev)
    pv = torch.as_tensor(pv_np, dtype=torch.float32).to(dev)
    yt = torch.as_tensor(yt_np, dtype=torch.long).to(dev)
    n_epochs = epochs_for_budget(len(xt), batch_size=BATCH_SIZE, update_budget=UPDATE_BUDGET)
    results = []
    for name, cell, structure in RUNS:
        core.seed_all(a.seed)
        if cell in CELL_SPEC:
            spec = CELL_SPEC[cell]
            tm = bank.templates if spec["bank"] == "brain" else null.templates
            model = MoBSEv3(cfg, torch.as_tensor(tm, dtype=torch.float32), routing=spec["routing"], roi_structure=structure)
        else:
            model = build_comparator(cell, cfg, single_graph=torch.as_tensor(single.template, dtype=torch.float32)
                                     if cell == "SG" else None)
        model = model.to(dev)
        opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate, weight_decay=gc.weight_decay)
        lossf = torch.nn.CrossEntropyLoss()

        def probs(x, p):
            model.eval()
            with torch.no_grad():
                return torch.softmax(model(x, p)["logits"], dim=1)[:, 1].cpu().numpy()

        gen = torch.Generator(device="cpu")
        gen.manual_seed(a.seed)
        rows, best = [], None
        t1 = time.perf_counter()
        for ep in range(n_epochs):
            model.train()
            o = torch.randperm(len(xt), generator=gen).to(dev)
            for s in range(0, len(xt), BATCH_SIZE):
                b = o[s:s + BATCH_SIZE]
                opt.zero_grad(set_to_none=True)
                lossf(model(xt[b], pt[b])["logits"], yt[b]).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                opt.step()
            p = probs(xv, pv)
            q = np.clip(np.where(yv_np == 1, p, 1 - p), PROB_CLIP, 1 - PROB_CLIP)
            rows.append({"epoch": ep, "val_loss": float(-np.log(q).mean()), "val_auc": auc(yv_np, p),
                         "val_ba": float(balanced_accuracy_score(yv_np, p > .5)), "val_p_sd": float(p.std())})
            if best is None or rows[-1]["val_loss"] < rows[best]["val_loss"]:
                best = ep
        r = {"run": name, "n_epochs": n_epochs, "selected_epoch": best, **{k: rows[best][k] for k in
             ("val_loss", "val_auc", "val_ba", "val_p_sd")}, "train_auc_last": auc(yt_np, probs(xt, pt)),
             "seconds": time.perf_counter() - t1}
        results.append(r)
        (a.out / f"epochs_{name}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        print(json.dumps(r), flush=True)
    (a.out / "summary.json").write_text(json.dumps({
        "schema": "h1h2-scope-i3-smoke-0.1", "decision": "결정 67 ① — pilot 안 smoke (셀 차이 해석 없음)",
        "lag": a.lag, "seed": a.seed, "train_subjects": tr_s, "val_subjects": va_s, "n_epochs": n_epochs,
        "bank_id": bank.bank_id, "null_id": null.bank_id, "baseline": base, "runs": results}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
