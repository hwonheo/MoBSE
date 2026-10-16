#!/usr/bin/env python3
"""I3 추가 대조 (결정 74, 기술값) — 본 분석 (`scripts/i3/analyze.py`) 과 같은 재표집으로 사전 지정 밖의 대조를 잰다.

* routing 고정 embedding 칸 − S (B · D 순열 · spin · rewire).
* routing 고정 embedding 안 bank 대조: B − D (순열 · spin · rewire).
본 분석과 같은 피험자 단위 bootstrap (seed 20261016, 10,000) 과 블록 집합을 쓴다. 결과를 본 뒤 정한 대조라 95 % 기술값으로만 보고한다.

Usage:
    PYTHONPATH=. .venv/bin/python -B scripts/i3_diag/extra_contrasts.py --run data/i3/main/20261016_1bc3622d_a1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i3"))
import analyze  # noqa: E402
import core  # noqa: E402

PAIRS = [("B_embedding", "S_fc_logistic"), ("D_embedding", "S_fc_logistic"), ("D_embedding_spin", "S_fc_logistic"),
         ("D_embedding_rewire", "S_fc_logistic"), ("B_embedding", "D_embedding"), ("B_embedding", "D_embedding_spin"),
         ("B_embedding", "D_embedding_rewire")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--n-boot", type=int, default=10000)
    a = ap.parse_args()
    cfg = json.loads((a.run / "run_config.json").read_text())
    names = sorted({p for pair in PAIRS for p in pair} - {"S_fc_logistic"})
    preds = {n: analyze.load_cell(a.run, n, cfg["n_outer"], cfg["seeds"]) for n in names}
    preds["S_fc_logistic"] = analyze.load_s(a.run, "S_fc_logistic", cfg["n_outer"])
    keys = sorted(preds[names[0]])
    assert all(sorted(v) == keys for v in preds.values())
    subjects = sorted({s for s, _ in keys})
    sidx = {s: i for i, s in enumerate(subjects)}
    sub = np.array([sidx[s] for s, _ in keys])
    blk = np.array([b for _, b in keys])
    correct = {n: np.array([(v[k][1] > 0.5) == (v[k][0] == 1) for k in keys], dtype=float) for n, v in preds.items()}
    N = len(subjects)
    W = np.random.default_rng(analyze.BOOT_SEED).multinomial(N, np.full(N, 1 / N), size=a.n_boot).astype(float)

    def boot(mask):
        cnt = np.bincount(sub[mask], minlength=N).astype(float)
        return {n: (float(np.bincount(sub[mask], weights=c[mask], minlength=N).sum() / cnt.sum()),
                    (W @ np.bincount(sub[mask], weights=c[mask], minlength=N)) / (W @ cnt)) for n, c in correct.items()}

    out = {}
    for tag, mask in (("all", np.ones(len(keys), bool)), ("no_first_pair", blk >= 2)):
        b = boot(mask)
        out[tag] = [{"a": x, "b": y, "estimate": b[x][0] - b[y][0],
                     "ci95": [float(np.percentile(b[x][1] - b[y][1], 2.5)), float(np.percentile(b[x][1] - b[y][1], 97.5))]}
                    for x, y in PAIRS]
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
