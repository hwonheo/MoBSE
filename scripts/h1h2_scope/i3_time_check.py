#!/usr/bin/env python3
"""I3 시간 위치 점검 (결정 68, pilot 만) — 조건을 고정한 채 앞쪽 블록 (짝 1 · 2) 대 뒤쪽 블록 (짝 3 · 4) 을 blockz FC 로 가른다.

157 명 전원이 c e c e c e c e 순서라 조건과 시간 위치가 겹친다. 이 점검은 **조건과 무관한 시간 신호**가 FC 에 얼마나
있는지를 본다. 같은 절차 (피험자 5-fold logistic C=1, 피험자 안 라벨 섞기 우연 분포) 로 조건 구분 (blockz FC) 도 함께 낸다.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/i3_time_check.py --aomic data/h1h2_scope/aomic --out <json> [--lag 6]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i3_baselines import blocks, cv_score  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--aomic", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lag", type=float, default=6.0)
    ap.add_argument("--n-perm", type=int, default=200)
    a = ap.parse_args()
    from mobse.v2.features import stack_window_features

    subs = (a.aomic / "pilot_ids.txt").read_text().split()
    X, cond, late, g = [], [], [], []
    for s in subs:
        z = np.load(a.aomic / "full_ts" / f"{s}_emomatching.npz")
        ts, t = z["ts"].astype(float), z["times"]
        blk, _ = blocks(a.aomic / "raw/aomic_wave1/ds002785/raw" / s / "func" / f"{s}_task-emomatching_acq-seq_events.tsv")
        for i, b in enumerate(blk):
            w = ts[(t >= b["start"] + a.lag) & (t < b["end"] + a.lag)]
            X.append((w - w.mean(0)) / w.std(0))
            cond.append(int(b["cond"] == "emotion"))
            late.append(int(i >= 4))
            g.append(s)
    _, Z = stack_window_features(X)
    cond, late, g = np.array(cond), np.array(late), np.array(g)
    rng = np.random.default_rng(20261016)
    out = {"schema": "h1h2-scope-i3-time-check-0.1", "lag": a.lag, "n_subjects": len(subs), "n_blocks": int(len(cond))}

    def run(name, Xs, y, gs):
        ba, auc = cv_score(Xs, y, gs)
        null = []
        for _ in range(a.n_perm):
            yp = y.copy()
            for s in np.unique(gs):
                m = gs == s
                yp[m] = rng.permutation(yp[m])
            null.append(cv_score(Xs, yp, gs)[0])
        null = np.array(null)
        out[name] = {"n": int(len(y)), "ba": ba, "auc": auc, "null_ba_mean": float(null.mean()),
                     "null_ba_p95": float(np.quantile(null, .95)), "p_perm": float((1 + (null >= ba).sum()) / (1 + len(null)))}
        print(name, json.dumps(out[name]), flush=True)

    run("condition_blockz_fc", Z, cond, g)
    idx = np.tile(np.arange(8), len(subs))
    keep = idx >= 2
    run("condition_blockz_fc_drop_first_pair", Z[keep], cond[keep], g[keep])
    for k in range(4):                                  # 짝 k (블록 2k · 2k+1) 의 control 이 나머지 control 과 갈리는가
        m = cond == 0
        run(f"control_pair{k}_vs_rest", Z[m], (idx[m] // 2 == k).astype(int), g[m])
    for c, nm in ((0, "late_vs_early_within_control"), (1, "late_vs_early_within_emotion")):
        m = cond == c
        run(nm, Z[m], late[m], g[m])
    out["note"] = "control_pair{k}_vs_rest 는 사람당 1:3 불균형 — BA 로 읽음"
    a.out.write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
