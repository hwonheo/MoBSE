#!/usr/bin/env python3
"""I3 routing 재현 진단 (결정 71) — 본 실행 fit 을 같은 seed 로 다시 학습하며 routing 을 기록한다.

학습 절차는 ``scripts/i3/core.py`` ``fit_one`` 과 한 줄씩 같다 (잠금 코드는 import 만 하고 고치지 않는다). 더하는 것:

* epoch 마다 val 의 routing 요약 (expert 별 평균 weight · 표본 사이 SD · 평균 entropy).
* best checkpoint 를 ``best_state.pt`` 로 저장.
* best checkpoint 에서 test 블록마다 routing weight (``test_routing.jsonl``).
* dynamic 칸이면 **routing 고정 대조** (새 학습 없음): best checkpoint 의 gate 를 val 평균 weight 로 바꾼 test 예측.
* 본 실행 ``predictions.jsonl`` 과 test 확률이 **바이트 동일**한지 (``repro_identical``).

Usage (Mac, 저장소 루트 — tmux 에서):
    PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/routing_repro.py --run data/i3/main/20261016_1bc3622d_a1 \
        --out data/i3/diag/routing_a1 [--cells A_embedding B_embedding] [--jobs 2]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i3"))
import core  # noqa: E402

PY = sys.executable


def entropy(w: np.ndarray) -> np.ndarray:
    return -(w * np.log(np.clip(w, 1e-12, None))).sum(axis=1)


def summarize(w: np.ndarray) -> dict:
    return {"mean": w.mean(axis=0).tolist(), "sd": w.std(axis=0).tolist(), "entropy_mean": float(entropy(w).mean())}


def repro_one(prep_dir: Path, cell: str, structure: str, null_kind, seed: int, out_dir: Path, ref_dir: Path,
              device: str = "mps") -> dict:
    """``core.fit_one`` 과 같은 학습 + routing 기록."""
    import torch

    from mobse.v2.models import CELL_SPEC, ModelConfig
    from mobse.v2.train import BATCH_SIZE, GRAD_CLIP, PROB_CLIP, build_grid
    from mobse.v3.models import MoBSEv3
    from mobse.v3.train import UPDATE_BUDGET, epochs_for_budget

    t0 = time.perf_counter()
    z = np.load(prep_dir / "prep.npz")
    gc = {g.config_id: g for g in build_grid()}[core.CONFIG_ID]
    core.seed_all(seed)
    dev = torch.device(device)
    cfg = ModelConfig(n_roi=z["x_train"].shape[1], n_samples=core.BLOCK_FRAMES, pca_dim=z["pca_train"].shape[1],
                      dropout=float(gc.dropout))
    spec = CELL_SPEC[cell]
    tm = z["bank"] if spec["bank"] == "brain" else z[f"null_{null_kind}"]
    model = MoBSEv3(cfg, torch.as_tensor(tm), routing=spec["routing"], roi_structure=structure).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate, weight_decay=gc.weight_decay)
    lossf = torch.nn.CrossEntropyLoss()
    T = {r: (torch.as_tensor(z[f"x_{r}"]).to(dev), torch.as_tensor(z[f"pca_{r}"]).to(dev)) for r in ("train", "val", "test")}
    yt = torch.as_tensor(z["y_train"], dtype=torch.long).to(dev)
    y_val = z["y_val"]

    def run(r, override=None):
        """(p1, routing) — fit_one 의 probs 와 같은 batch 512 · eval · no_grad."""
        model.eval()
        x, p = T[r]
        ps, ws = [], []
        with torch.no_grad():
            for s in range(0, len(x), 512):
                ov = None if override is None else override.expand(len(x[s:s + 512]), -1)
                o = model(x[s:s + 512], p[s:s + 512], routing_override=ov)
                ps.append(torch.softmax(o["logits"], dim=1)[:, 1].cpu().numpy())
                ws.append(o["routing"].cpu().numpy())
        return np.concatenate(ps), np.concatenate(ws)

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
        pv, wv = run("val")
        q = np.clip(np.where(y_val == 1, pv, 1 - pv), PROB_CLIP, 1 - PROB_CLIP)
        rows.append({"epoch": ep, "val_loss": float(-np.log(q).mean()), "val_p_sd": float(pv.std()),
                     "val_routing": summarize(wv)})
        if best is None or rows[-1]["val_loss"] < rows[best]["val_loss"]:     # 같으면 앞 epoch
            best = ep
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    p_test, w_test = run("test")
    _, w_val = run("val")
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save({k: v.cpu() for k, v in best_state.items()}, out_dir / "best_state.pt")
    (out_dir / "epochs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    core.atomic_write(out_dir / "test_routing.jsonl", "".join(
        json.dumps({"subject": str(s), "block": int(b), "label": int(y), "p1": float(p), "w": [float(v) for v in w]}) + "\n"
        for s, b, y, p, w in zip(z["subj_test"], z["block_test"], z["y_test"], p_test, w_test)))

    ref = [json.loads(l) for l in (ref_dir / "predictions.jsonl").read_text().splitlines()]
    identical = len(ref) == len(p_test) and all(r["p1"] == float(p) and r["block"] == int(b)
                                                for r, p, b in zip(ref, p_test, z["block_test"]))
    y_test = z["y_test"]
    summary = {"cell": cell, "structure": structure, "seed": seed, "routing": spec["routing"], "n_epochs": n_epochs,
               "selected_epoch": best, "val_loss": rows[best]["val_loss"], "repro_identical": bool(identical),
               "test_acc_block": float(((p_test >= 0.5) == y_test).mean()),
               "test_routing": summarize(w_test), "val_routing": summarize(w_val),
               "routing_label_gap": (w_test[y_test == 1].mean(axis=0) - w_test[y_test == 0].mean(axis=0)).tolist()}
    if spec["routing"] == "dynamic":
        mean_w = torch.as_tensor(w_val.mean(axis=0), dtype=torch.float32, device=dev).view(1, -1)
        p_fix, _ = run("test", override=mean_w)
        core.atomic_write(out_dir / "test_fixed_override.jsonl", "".join(
            json.dumps({"subject": str(s), "block": int(b), "label": int(y), "p1": float(p)}) + "\n"
            for s, b, y, p in zip(z["subj_test"], z["block_test"], y_test, p_fix)))
        summary["override_val_mean_w"] = mean_w.cpu().numpy().ravel().tolist()
        summary["test_acc_block_override"] = float(((p_fix >= 0.5) == y_test).mean())
    summary["seconds"] = time.perf_counter() - t0
    core.atomic_write(out_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=1))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--one", action="store_true", help="(내부) fit 하나")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cells", nargs="+", default=["A_embedding", "B_embedding"])
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--cell"), ap.add_argument("--structure"), ap.add_argument("--outer", type=int)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.one:
        d = a.out / f"{a.cell}_{a.structure}" / f"outer{a.outer}" / f"seed{a.seed}"
        repro_one(a.run / "prep" / f"outer{a.outer}", a.cell, a.structure, "permutation", a.seed, d,
                  a.run / "fits" / f"{a.cell}_{a.structure}" / f"outer{a.outer}" / f"seed{a.seed}")
        return 0
    cfg = json.loads((a.run / "run_config.json").read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for name in a.cells:
        cell, structure = name.split("_")
        for k in range(cfg["n_outer"]):
            for s in cfg["seeds"]:
                if not (a.out / name / f"outer{k}" / f"seed{s}" / "summary.json").exists():
                    jobs.append((cell, structure, k, s))
    log = a.out / "status.log"

    def go(j):
        cell, structure, k, s = j
        r = subprocess.run([PY, "-B", str(Path(__file__).resolve()), "--one", "--run", str(a.run), "--out", str(a.out),
                            "--cell", cell, "--structure", structure, "--outer", str(k), "--seed", str(s)],
                           capture_output=True, text=True)
        return j, r.returncode, r.stderr[-800:]

    t0, fails, done = time.time(), [], 0
    with log.open("a") as fh:
        fh.write(f"{time.strftime('%FT%T')} start {len(jobs)} jobs jobs={a.jobs}\n")
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for f in as_completed([ex.submit(go, j) for j in jobs]):
            j, rc, err = f.result()
            done += 1
            if rc != 0:
                fails.append({"job": j, "rc": rc, "stderr": err})
            with log.open("a") as fh:
                fh.write(f"{time.strftime('%FT%T')} {done}/{len(jobs)} {j} rc={rc} elapsed={time.time() - t0:.0f}s fails={len(fails)}\n")
    core.atomic_write(a.out / "fails.json", json.dumps(fails, indent=1))
    with log.open("a") as fh:
        fh.write(f"{time.strftime('%FT%T')} {'ALL_DONE' if not fails else 'DONE_WITH_FAILS'}\n")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
