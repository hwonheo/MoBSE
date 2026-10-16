#!/usr/bin/env python3
"""gate 입력 크기 맞춤의 pilot 학습 확인 (결정 73) — pilot 31 명만, main 피험자를 읽지 않는다.

* 분할: pilot 31 명을 5 fold 로 (seed 20261016 순열, test 7 · 6 · 6 · 6 · 6). outer 마다 나머지에서 val 6 · train 18–19.
* 준비: ``core.prep_one`` 그대로 (bank · PCA 는 학습 피험자 rest 창). 그에 더해 학습 피험자 rest 창 PCA 점수의 열 평균 · SD.
* 칸: A embedding × gate 입력 {raw · rest_std (가) · task_std (나)} + B embedding (raw, 고정 gate 라 입력을 쓰지 않음).
  seed 42 · 43 · 44. 학습 · 기록은 ``routing_repro.repro_one`` (update 예산 5,000 · val best checkpoint).
* 요약: seed 평균 확률의 test 블록 정확도 (31 명 · 248 블록) · B 대비 차이의 피험자 bootstrap 95 % CI (기술값) ·
  test routing entropy · label 사이 routing 차이 · gate 를 val 평균 weight 로 고정한 정확도.

Usage (Mac, 저장소 루트 — tmux 에서):
    PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/gate_scale_pilot.py --data-root data/h1h2_scope/aomic \
        --out data/i3/diag/gate_scale_pilot_a1 [--jobs 2]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i3"))
sys.path.insert(0, str(HERE))
import core  # noqa: E402

PY = sys.executable
N_OUTER = 5
VARIANTS = [("A", "raw"), ("A", "rest_std"), ("A", "task_std"), ("B", "raw")]
BOOT_SEED, N_BOOT = 20261016, 10000


def pilot_folds(pilot) -> dict:
    order = list(np.random.default_rng(20261016).permutation(sorted(pilot)))
    tag = lambda xs: [f"ds002785:{x}" for x in sorted(xs)]  # noqa: E731
    tests = np.array_split(np.array(order), N_OUTER)
    folds = []
    for k, test in enumerate(tests):
        rest = [s for s in order if s not in set(test)]
        val, train = rest[:6], rest[6:]
        folds.append({"outer_fold": k, "test_subjects": tag(test), "train_subjects": tag(train + val),
                      "inner": [{"inner_fold": 0, "train_subjects": tag(train), "val_subjects": tag(val)}]})
    return {"outer_folds": folds, "pilot_cv": True}


def rest_scale(root: Path, folds: dict, k: int) -> dict:
    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    parts = core.fold_parts(folds, k)
    rest = [w for s in parts["train"] for w in core.rest_windows(root, s)]
    _, z_rest = stack_window_features(rest)
    trans = fit_transform_on_training_rest(z_rest, [s for s in parts["train"] for _ in range(4)])
    p = trans.transform(z_rest)
    return {"mu": p.mean(0).tolist(), "sd": p.std(0).tolist(), "n_rest_windows": len(rest)}


def fit_child(a) -> int:
    from routing_repro import repro_one
    prep = a.out / "prep" / f"outer{a.outer}"
    scale = None
    if a.scale == "rest_std":
        s = json.loads((prep / "rest_scale.json").read_text())
        scale = (np.array(s["mu"], dtype=np.float32), np.array(s["sd"], dtype=np.float32))
    elif a.scale == "task_std":
        p = np.load(prep / "prep.npz")["pca_train"]
        scale = (p.mean(0), p.std(0))
    repro_one(prep, a.cell, "embedding", "permutation", a.seed,
              a.out / "fits" / f"{a.cell}_{a.scale}" / f"outer{a.outer}" / f"seed{a.seed}", pca_scale=scale)
    return 0


def summarize(out: Path) -> dict:
    res = {}
    acc_by_subj = {}
    for cell, scale in VARIANTS:
        name = f"{cell}_{scale}"
        probs, fixed, lab = defaultdict(list), defaultdict(list), {}
        ents, gaps, vls = [], [], []
        for f in sorted((out / "fits" / name).glob("outer*/seed*/summary.json")):
            s = json.loads(f.read_text())
            ents.append(s["test_routing"]["entropy_mean"])
            gaps.append(max(abs(v) for v in s["routing_label_gap"]))
            vls.append(s["val_loss"])
            for line in (f.parent / "test_routing.jsonl").read_text().splitlines():
                r = json.loads(line)
                probs[(r["subject"], r["block"])].append(r["p1"])
                lab[(r["subject"], r["block"])] = r["label"]
            ov = f.parent / "test_fixed_override.jsonl"
            if ov.exists():
                for line in ov.read_text().splitlines():
                    r = json.loads(line)
                    fixed[(r["subject"], r["block"])].append(r["p1"])
        ok = {k: int((np.mean(p) >= 0.5) == lab[k]) for k, p in probs.items()}
        subj = defaultdict(list)
        for (sbj, _), v in ok.items():
            subj[sbj].append(v)
        acc_by_subj[name] = {s: float(np.mean(v)) for s, v in subj.items()}
        res[name] = {"n_fits": len(ents), "n_blocks": len(ok), "acc": float(np.mean(list(ok.values()))),
                     "test_entropy_median": float(np.median(ents)), "label_gap_median": float(np.median(gaps)),
                     "val_loss_median": float(np.median(vls))}
        if fixed:
            res[name]["acc_fixed_override"] = float(np.mean(
                [int((np.mean(p) >= 0.5) == lab[k]) for k, p in fixed.items()]))
    subjects = sorted(acc_by_subj["B_raw"])
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(subjects), size=(N_BOOT, len(subjects)))
    for cell, scale in VARIANTS[:3]:
        name = f"{cell}_{scale}"
        d = np.array([acc_by_subj[name][s] - acc_by_subj["B_raw"][s] for s in subjects])
        bs = d[idx].mean(1)
        res[name]["minus_B"] = {"estimate": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)),
                                                                     float(np.percentile(bs, 97.5))]}
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--cell"), ap.add_argument("--scale"), ap.add_argument("--outer", type=int)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.child:
        return fit_child(a)

    a.out.mkdir(parents=True, exist_ok=True)
    log = a.out / "status.log"

    def say(msg):
        with log.open("a") as fh:
            fh.write(f"{time.strftime('%FT%T')} {msg}\n")

    folds = pilot_folds((a.data_root / "pilot_ids.txt").read_text().split())
    core.atomic_write(a.out / "pilot_folds.json", json.dumps(folds, indent=1))
    say("start")
    for k in range(N_OUTER):
        d = a.out / "prep" / f"outer{k}"
        if not (d / "prep.json").exists():
            m = core.prep_one(a.data_root, folds, k, d)
            say(f"prep outer{k} ok {m['n_windows']}")
        if not (d / "rest_scale.json").exists():
            core.atomic_write(d / "rest_scale.json", json.dumps(rest_scale(a.data_root, folds, k)))
    jobs = [(c, sc, k, s) for (c, sc) in VARIANTS for k in range(N_OUTER) for s in core.SEEDS
            if not (a.out / "fits" / f"{c}_{sc}" / f"outer{k}" / f"seed{s}" / "summary.json").exists()]
    say(f"fit {len(jobs)} jobs jobs={a.jobs}")

    def go(j):
        c, sc, k, s = j
        r = subprocess.run([PY, "-B", str(Path(__file__).resolve()), "--child", "--data-root", str(a.data_root),
                            "--out", str(a.out), "--cell", c, "--scale", sc, "--outer", str(k), "--seed", str(s)],
                           capture_output=True, text=True)
        return j, r.returncode, r.stderr[-800:]

    t0, fails, done = time.time(), [], 0
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for f in as_completed([ex.submit(go, j) for j in jobs]):
            j, rc, err = f.result()
            done += 1
            if rc != 0:
                fails.append({"job": j, "rc": rc, "stderr": err})
            if done % 10 == 0 or rc != 0 or done == len(jobs):
                say(f"fit {done}/{len(jobs)} last={j} rc={rc} elapsed={time.time() - t0:.0f}s fails={len(fails)}")
    core.atomic_write(a.out / "fails.json", json.dumps(fails, indent=1))
    if fails:
        say("DONE_WITH_FAILS")
        return 1
    core.atomic_write(a.out / "summary.json", json.dumps(summarize(a.out), ensure_ascii=False, indent=1))
    say("ALL_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
