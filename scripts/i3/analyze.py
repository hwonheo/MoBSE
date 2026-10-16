#!/usr/bin/env python3
"""I3 분석 (결정 69) — 칸마다 seed 3 개의 블록 확률 평균 → 0.5 로 자른 정확도 (블록이 사람마다 4:4 라 BA 와 같음).

* 주 contrast (97.5 %, v1 규칙 — H1 · H2 두 개 Bonferroni): 구조마다 H1 = A − B, H2 = A − C (순열 null).
* 보조 (95 %, 기술적): A − S (blockz FC logistic), A − NG, A − SG, A − C_spin, A − C_rewire.
* 민감도 (결정 69): **첫 짝 (블록 0 · 1) 을 뺀 평가**로 주 contrast 를 다시 (97.5 %).
* CI 는 **피험자 단위 bootstrap** (모든 칸에 같은 재표집 — 짝지은 비교), percentile.
* 판정 표기: 하한 > δ (0.02) · 하한 > 0 · CI 0 포함 · 상한 < 0. δ 는 G-b 상 탐지할 수 없는 크기임을 잠금 문서가 미리 적는다.
* 붕괴 표기: test 또는 val 확률 SD < 1e-3 인 fit 수.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/i3/analyze.py --run <run_dir> [--n-boot 10000]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

DELTA = 0.02
BOOT_SEED = 20261016
COLLAPSE_SD = 1e-3


def load_cell(run: Path, name: str, n_outer: int, seeds) -> dict:
    """{(subject, block): (label, mean p)}. 빠진 fit 이 있으면 None."""
    acc: dict = {}
    for k in range(n_outer):
        for s in seeds:
            f = run / "fits" / name / f"outer{k}" / f"seed{s}" / "predictions.jsonl"
            if not f.exists():
                return None
            for line in f.read_text().splitlines():
                r = json.loads(line)
                acc.setdefault((r["subject"], r["block"]), [r["label"], []])[1].append(r["p1"])
    return {key: (lab, float(np.mean(ps))) for key, (lab, ps) in acc.items()}


def load_s(run: Path, name: str, n_outer: int) -> dict:
    out = {}
    for k in range(n_outer):
        f = run / "s" / f"outer{k}" / f"{name}.jsonl"
        if not f.exists():
            return None
        for line in f.read_text().splitlines():
            r = json.loads(line)
            out[(r["subject"], r["block"])] = (r["label"], r["p1"])
    return out


def judge(lo: float, hi: float) -> str:
    if lo > DELTA:
        return "하한 > δ"
    if lo > 0:
        return "하한 > 0"
    if hi < 0:
        return "상한 < 0"
    return "CI 0 포함"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--n-boot", type=int, default=10000)
    a = ap.parse_args()
    cfg = json.loads((a.run / "run_config.json").read_text())
    n_outer, seeds = cfg["n_outer"], cfg["seeds"]

    names = [core.cell_name(*c) for c in core.MAIN_CELLS + core.SENS_CELLS]
    preds = {n: load_cell(a.run, n, n_outer, seeds) for n in names}
    for n in ("S_fc_logistic", "REF_activation_logistic"):
        preds[n] = load_s(a.run, n, n_outer)
    missing = sorted(n for n, v in preds.items() if v is None)
    if missing:
        raise SystemExit(f"빠진 칸이 있다: {missing}")
    keys = sorted(preds[names[0]])
    for n, v in preds.items():
        if sorted(v) != keys:
            raise SystemExit(f"{n}: 블록 집합이 다르다")
    subjects = sorted({s for s, _ in keys})
    sidx = {s: i for i, s in enumerate(subjects)}
    blk = np.array([b for _, b in keys])
    sub = np.array([sidx[s] for s, _ in keys])
    label = np.array([preds[names[0]][k][0] for k in keys])
    correct = {n: np.array([(v[k][1] > 0.5) == (v[k][0] == 1) for k in keys], dtype=float) for n, v in preds.items()}

    rng = np.random.default_rng(BOOT_SEED)
    N = len(subjects)
    W = rng.multinomial(N, np.full(N, 1 / N), size=a.n_boot).astype(float)       # (n_boot, N) 재표집 횟수

    def boot(mask):
        """마스크 블록만으로 칸별 (점추정, bootstrap 분포). 점추정 = 블록 평균, 재표집은 사람 단위 가중."""
        cnt = np.bincount(sub[mask], minlength=N).astype(float)
        out = {}
        for n, c in correct.items():
            per = np.bincount(sub[mask], weights=c[mask], minlength=N)            # 사람별 맞힌 블록 수
            out[n] = (float(per.sum() / cnt.sum()), (W @ per) / (W @ cnt))
        return out

    def contrast(b, x, y, level):
        pt = b[x][0] - b[y][0]
        dist = b[x][1] - b[y][1]
        q = (100 - level) / 2
        lo, hi = float(np.percentile(dist, q)), float(np.percentile(dist, 100 - q))
        return {"a": x, "b": y, "estimate": pt, "ci_level": level, "lo": lo, "hi": hi, "judgment": judge(lo, hi)}

    all_b = boot(np.ones(len(keys), bool))
    nofirst_b = boot(blk >= 2)
    res = {"schema": "i3-analysis-0.1", "run": str(a.run), "n_subjects": N, "n_blocks": int(len(keys)),
           "label_counts": np.bincount(label).tolist(), "n_boot": a.n_boot, "boot_seed": BOOT_SEED, "delta": DELTA,
           "accuracy": {n: {"all": all_b[n][0], "ci95": [float(np.percentile(all_b[n][1], 2.5)),
                                                         float(np.percentile(all_b[n][1], 97.5))],
                            "no_first_pair": nofirst_b[n][0]} for n in correct},
           "primary": [], "auxiliary": [], "sensitivity_no_first_pair": []}
    for s in core.STRUCTURES:
        A = f"A_{s}"
        for x, y in ((A, f"B_{s}"), (A, f"C_{s}")):
            res["primary"].append({"structure": s, "hypothesis": "H1" if y.startswith("B") else "H2",
                                   **contrast(all_b, x, y, 97.5)})
            res["sensitivity_no_first_pair"].append({"structure": s, "hypothesis": "H1" if y.startswith("B") else "H2",
                                                     **contrast(nofirst_b, x, y, 97.5)})
        for y in ("S_fc_logistic", "NG", "SG", f"C_{s}_spin", f"C_{s}_rewire"):
            res["auxiliary"].append({"structure": s, **contrast(all_b, A, y, 95)})

    fits = sorted((a.run / "fits").glob("*/outer*/seed*/summary.json"))
    sums = [json.loads(f.read_text()) for f in fits]
    res["fits"] = {"n": len(sums), "collapsed": sum(1 for x in sums if x["test_p_sd"] < COLLAPSE_SD
                                                   or x["val_p_sd"] < COLLAPSE_SD),
                   "selected_epoch_median": float(np.median([x["selected_epoch"] for x in sums])),
                   "selected_epoch0": sum(1 for x in sums if x["selected_epoch"] == 0),
                   "seconds_total": float(sum(x["seconds"] for x in sums))}
    out = a.run / "analysis" / "analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(res, ensure_ascii=False, indent=1)
    core.atomic_write(out, text)
    print(json.dumps({"analysis": str(out), "sha12": hashlib.sha256(text.encode()).hexdigest()[:12],
                      "n_subjects": N, "fits": res["fits"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
