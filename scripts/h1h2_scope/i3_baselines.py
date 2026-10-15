#!/usr/bin/env python3
"""I3 범위 확인 (결정 67 ①) — emomatching 블록 (emotion / control) 을 단순 기준선이 얼마나 맞히는가.

목적은 **천장 · 바닥 확인**이다 (G-a 와 같은 성격, 결정 29: 버리는 쪽으로만 판단). 모델 비교가 아니다.

* 블록: events 에서 같은 trial_type 이 이어지는 구간 하나. 시작 = 첫 trial onset, 끝 = 마지막 onset + trial 간격
  (중앙값). 창 = [시작 + lag, 끝 + lag) 안의 frame (혈역학 지연, lag 4 · 6 s 를 함께 본다 — 구현 선택).
* 특징 셋:
  - ``act``: 블록 안 ROI 평균 (100) — 활성 크기.
  - ``fc``: 블록 안 Pearson 상관 → Fisher z, 위 삼각 4,950.
  - ``fc_taskreg``: run 전체에서 조건 대비 boxcar (lag 이동) 를 회귀로 뺀 뒤의 블록 FC — 유발 반응이 만든 공활성을 뺀 것.
* 분류: StandardScaler + logistic (C=1 고정, grid 없음), 피험자 단위 5-fold (GroupKFold). 지표는 블록 balanced accuracy
  와 AUC. 우연 분포는 **피험자 안에서** 라벨을 섞어 (200 회) 같은 절차를 다시 돈다.
* FC 안정성: 같은 사람의 블록 FC 끼리 상관 (같은 조건 · 다른 조건), 블록 FC 와 그 run 전체 FC 의 상관.

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/i3_baselines.py --ts data/h1h2_scope/aomic/full_ts \
        --events-root data/h1h2_scope/aomic/raw/aomic_wave1/ds002785/raw --out <dir> [--n-perm 200]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

LAGS = (4.0, 6.0)
CONDS = ("control", "emotion")


def blocks(events: Path) -> list:
    rows = list(csv.DictReader(events.open(), delimiter="\t"))
    onsets = np.array([float(r["onset"]) for r in rows])
    soa = float(np.median(np.diff(onsets)))
    out, cur = [], None
    for r, t in zip(rows, onsets):
        tt = r["trial_type"]
        if cur is None or tt != cur["cond"]:
            cur = {"cond": tt, "start": t, "end": t + soa, "n_trials": 0}
            out.append(cur)
        cur["end"] = t + soa
        cur["n_trials"] += 1
    return out, soa


def fisher_fc(x: np.ndarray) -> np.ndarray:
    c = np.corrcoef(x.T)
    iu = np.triu_indices(c.shape[0], 1)
    return np.arctanh(np.clip(c[iu], -0.999999, 0.999999))


def features(ts: np.ndarray, times: np.ndarray, blk: list, lag: float) -> dict:
    # 조건 대비 boxcar (emotion +1 · control −1 · 밖 0) 를 lag 만큼 늦춰 run 전체에서 회귀로 뺀다
    reg = np.zeros(len(times))
    for b in blk:
        m = (times >= b["start"] + lag) & (times < b["end"] + lag)
        reg[m] = 1.0 if b["cond"] == "emotion" else -1.0
    X = np.column_stack([np.ones(len(times)), reg])
    beta, *_ = np.linalg.lstsq(X, ts, rcond=None)
    resid = ts - X @ beta
    out = {"act": [], "fc": [], "fc_taskreg": [], "y": [], "n_frames": []}
    for b in blk:
        m = (times >= b["start"] + lag) & (times < b["end"] + lag)
        if m.sum() < 10:
            continue
        out["act"].append(ts[m].mean(axis=0))
        out["fc"].append(fisher_fc(ts[m]))
        out["fc_taskreg"].append(fisher_fc(resid[m]))
        out["y"].append(CONDS.index(b["cond"]))
        out["n_frames"].append(int(m.sum()))
    out["full_fc"] = fisher_fc(ts)
    return out


def cv_score(X, y, groups, seed=0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    p = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
        clf.fit(X[tr], y[tr])
        p[te] = clf.predict_proba(X[te])[:, 1]
    return float(balanced_accuracy_score(y, p > 0.5)), float(roc_auc_score(y, p))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ts", type=Path, required=True)
    ap.add_argument("--events-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-perm", type=int, default=200)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()
    man = json.loads((a.ts / "manifest.json").read_text())
    subs = [r["subject"] for r in man["runs"] if r["status"] == "ok"]
    report = {"schema": "h1h2-scope-i3-baselines-0.1", "decision": "결정 67 ① — 천장 · 바닥 확인 (모델 비교 아님)",
              "n_subjects": len(subs), "qc_passed_wi02": sum(bool(r.get("qc_passed_wi02")) for r in man["runs"]),
              "lags": {}}
    blk_desc = {}
    for lag in LAGS:
        F = {k: [] for k in ("act", "fc", "fc_taskreg", "y", "g")}
        stab = {"same_cond": [], "diff_cond": [], "block_vs_run": []}
        nfr = []
        for s in subs:
            z = np.load(a.ts / f"{s}_emomatching.npz")
            blk, soa = blocks(a.events_root / s / "func" / f"{s}_task-emomatching_acq-seq_events.tsv")
            blk_desc[s] = {"n_blocks": len(blk), "soa": soa,
                           "len_s": sorted({round(b["end"] - b["start"], 1) for b in blk}),
                           "conds": [b["cond"][0] for b in blk]}
            f = features(z["ts"].astype(float), z["times"], blk, lag)
            for k in ("act", "fc", "fc_taskreg"):
                F[k] += f[k]
            F["y"] += f["y"]
            F["g"] += [s] * len(f["y"])
            nfr += f["n_frames"]
            fc = np.array(f["fc"])
            yy = np.array(f["y"])
            r = np.corrcoef(fc)
            iu = np.triu_indices(len(yy), 1)
            same = yy[iu[0]] == yy[iu[1]]
            stab["same_cond"].append(float(r[iu][same].mean()))
            stab["diff_cond"].append(float(r[iu][~same].mean()))
            stab["block_vs_run"].append(float(np.mean([np.corrcoef(v, f["full_fc"])[0, 1] for v in fc])))
        y = np.array(F["y"])
        g = np.array(F["g"])
        res = {"n_blocks": int(len(y)), "n_per_class": np.bincount(y).tolist(),
               "frames_per_block": sorted(set(nfr)),
               "fc_stability_median": {k: float(np.median(v)) for k, v in stab.items()}}
        rng = np.random.default_rng(20261016)
        for k in ("act", "fc", "fc_taskreg"):
            X = np.array(F[k])
            ba, auc = cv_score(X, y, g)
            null = []
            for _ in range(a.n_perm):
                yp = y.copy()
                for s in subs:
                    m = g == s
                    yp[m] = rng.permutation(yp[m])
                null.append(cv_score(X, yp, g)[0])
            null = np.array(null)
            res[k] = {"n_features": int(X.shape[1]), "ba": ba, "auc": auc,
                      "null_ba_mean": float(null.mean()), "null_ba_p95": float(np.quantile(null, .95)),
                      "p_perm": float((1 + (null >= ba).sum()) / (1 + len(null)))}
            print(json.dumps({"lag": lag, "feat": k, **res[k]}, ensure_ascii=False), flush=True)
        report["lags"][str(lag)] = res
    report["blocks_per_subject"] = blk_desc
    report["seconds"] = time.perf_counter() - t_all
    (a.out / "baselines.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
