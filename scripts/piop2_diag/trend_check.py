#!/usr/bin/env python3
"""기울기 진단 (결정 80, 기술값) — B emb 의 이득이 블록 안 시간 정보에서 오는지 새 학습 없이 잰다.

* T1 ``S_trend``: ROI 별 블록 안 OLS 기울기 (blockz 15 frame → 100 특징).
* T2 ``S_ts``: blockz 시계열 전체를 펼친 것 (100 × 15 = 1,500 특징).
* 둘 다 S 와 같은 방식 — StandardScaler + LogisticRegression C=1, 학습 블록 = ``prep.npz`` 의 ``x_train``.
* 정확도 · B emb 과 S 대비 차이를 본 분석과 같은 피험자 bootstrap (seed 20261016, 10,000, 95 %) 으로,
  8 블록 전체 · 첫 짝 제외 둘 다. I3 (PIOP1, outer 5) 와 PIOP2 확증 run (outer 1) 을 같은 코드로 읽는다.

잠금 대상 (``scripts/i3`` · ``scripts/piop2_confirm``) 은 import 만 한다.

Usage:
    PYTHONPATH=. .venv/bin/python -B scripts/piop2_diag/trend_check.py --run <run_dir> --out <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i3"))
import analyze  # noqa: E402
import core  # noqa: E402

B_NAME = "B_embedding"
PAIRS = [("S_trend", "S_fc_logistic"), ("S_ts", "S_fc_logistic"), (B_NAME, "S_trend"), (B_NAME, "S_ts"),
         (B_NAME, "S_fc_logistic")]


def slopes(x: np.ndarray) -> np.ndarray:
    """``(n, roi, T)`` → ROI 별 OLS 기울기 ``(n, roi)``."""
    t = np.arange(x.shape[2], dtype=float)
    t -= t.mean()
    return (x * t).sum(axis=2) / (t ** 2).sum()


def fit_extra(prep: Path) -> dict:
    """{name: {(subject, block): (label, p1)}} — T1 · T2 를 한 outer 의 prep 로."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    z = np.load(prep)
    feats = {"S_trend": slopes, "S_ts": lambda x: x.reshape(len(x), -1)}
    out = {}
    for name, f in feats.items():
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
        clf.fit(f(z["x_train"].astype(float)), z["y_train"])
        p = clf.predict_proba(f(z["x_test"].astype(float)))[:, 1]
        out[name] = {(str(s), int(b)): (int(y), float(q))
                     for s, b, y, q in zip(z["subj_test"], z["block_test"], z["y_test"], p)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-boot", type=int, default=10000)
    a = ap.parse_args()
    seeds = list(json.loads((a.run / "run_config.json").read_text())["seeds"])
    outers = sorted((a.run / "prep").glob("outer*/prep.npz"))
    n_outer = len(outers)

    preds = {B_NAME: analyze.load_cell(a.run, B_NAME, n_outer, seeds),
             "S_fc_logistic": analyze.load_s(a.run, "S_fc_logistic", n_outer)}
    extra: dict = {}
    for p in outers:
        for name, d in fit_extra(p).items():
            extra.setdefault(name, {}).update(d)
    preds.update(extra)
    keys = sorted(preds[B_NAME])
    for n, v in preds.items():
        if v is None or sorted(v) != keys:
            raise SystemExit(f"{n}: 블록 집합이 본 분석과 다르다")
        if any(v[k][0] != preds[B_NAME][k][0] for k in keys):
            raise SystemExit(f"{n}: label 이 본 분석과 다르다")

    subjects = sorted({s for s, _ in keys})
    sidx = {s: i for i, s in enumerate(subjects)}
    sub = np.array([sidx[s] for s, _ in keys])
    blk = np.array([b for _, b in keys])
    correct = {n: np.array([(v[k][1] > 0.5) == (v[k][0] == 1) for k in keys], dtype=float) for n, v in preds.items()}
    N = len(subjects)
    W = np.random.default_rng(analyze.BOOT_SEED).multinomial(N, np.full(N, 1 / N), size=a.n_boot).astype(float)

    def boot(mask):
        cnt = np.bincount(sub[mask], minlength=N).astype(float)
        res = {}
        for n, c in correct.items():
            per = np.bincount(sub[mask], weights=c[mask], minlength=N)
            res[n] = (float(per.sum() / cnt.sum()), (W @ per) / (W @ cnt))
        return res

    out = {"schema": "piop2-diag-trend-0.1", "run": str(a.run), "n_outer": n_outer, "seeds": seeds,
           "n_subjects": N, "n_blocks": len(keys), "boot_seed": analyze.BOOT_SEED, "n_boot": a.n_boot}
    for tag, mask in (("all", np.ones(len(keys), bool)), ("no_first_pair", blk >= 2)):
        b = boot(mask)
        out[tag] = {
            "accuracy": {n: {"estimate": b[n][0], "ci95": [float(np.percentile(b[n][1], 2.5)),
                                                           float(np.percentile(b[n][1], 97.5))]} for n in b},
            "contrasts": [{"a": x, "b": y, "estimate": b[x][0] - b[y][0],
                           "ci95": [float(np.percentile(b[x][1] - b[y][1], 2.5)),
                                    float(np.percentile(b[x][1] - b[y][1], 97.5))]} for x, y in PAIRS]}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    core.atomic_write(a.out, text)
    print(json.dumps({"out": str(a.out), "sha12": hashlib.sha256(text.encode()).hexdigest()[:12]}))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
