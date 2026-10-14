#!/usr/bin/env python3
"""ADHD-200 범위 확인 (결정 62) — 인원 · 라벨 · 시점 수 · 상수 영역 · 단순 기준선 (FC logistic) 천장 여부.

읽는 것 (data root 상대):
* ``adhd200/nitrc/x/<site>/<id>/sfnwmrda<id>_session_1_rest_1_cc200_TCs.1D`` — Athena 판 CC200 (190 영역),
  대역 0.009–0.08 Hz · 전역 신호 회귀 없음 (선생님이 NITRC 에서 받은 ``ADHD200_CC200_TCs_filtfix.tar.gz``).
* ``adhd200/nitrc/nvols.csv`` — 스캔별 시점 수 (대조용).
* ``adhd200/raw/pheno/<site>/participants.tsv`` — 공개 S3 BIDS 판 라벨 (시험판 DX 포함). NITRC 학습판
  ``<site>_phenotypic.csv`` 의 DX 코드와 겹치는 사람은 대조한다.

라벨: TD (DX 0 · "Typically Developing") = 0, ADHD 세 아형 = 1. 그 밖 (없음 · withheld) 은 뺀다.

기준선: 앞 ``--t`` 시점 (기본 100, I1 ABIDE 와 같음) 의 Pearson FC → Fisher-z 위삼각 → 표준화 → logistic (C=1),
기관 × 라벨 층화 5-fold (seed 0) 의 OOF AUC. **잠금 전 범위 확인용**이며 이 값으로 설계를 고르지 않는다.

Usage (h197, venv-mobse-v2):
    python scripts/i1_adhd200/inventory.py --data-root <D> --out <D>/adhd200/scoping_20261014
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

TD_NAMES = {"0", "typically developing", "td", "control"}
ADHD_NAMES = {"1", "2", "3", "adhd-combined", "adhd-hyperactive/impulsive", "adhd-inattentive"}


def dx_label(v: str):
    v = (v or "").strip().strip('"').lower()
    if v in TD_NAMES or v.startswith("typically developing"):
        return 0
    if v in ADHD_NAMES or v.startswith("adhd"):
        return 1
    return None


def read_tc(path: Path) -> np.ndarray:
    rows = [l.rstrip("\n").split("\t") for l in path.read_text().splitlines()]
    head, body = rows[0], rows[1:]
    assert head[0] == "File" and head[1] == "Sub-brick", head[:2]
    return np.array([[float(x) for x in r[2:]] for r in body], dtype=np.float64)  # T × ROI


def labels(data_root: Path):
    out, src = {}, {}
    for tsv in sorted((data_root / "adhd200/raw/pheno").glob("*/participants.tsv")):
        site = tsv.parent.name
        for r in csv.DictReader(tsv.open(encoding="latin-1"), delimiter="\t"):
            sid = int(r["participant_id"].replace("sub-", ""))
            out[sid] = {"site_bids": site, "dx": r.get("dx", ""), "y": dx_label(r.get("dx", "")),
                        "qc_rest_1": r.get("qc_rest_1", ""), "gender": r.get("gender", ""), "age": r.get("age", "")}
    nitrc = {}
    for c in sorted((data_root / "adhd200/nitrc/x").glob("*/*_phenotypic.csv")):
        if "TestRelease" in c.name:
            continue
        for r in csv.DictReader(c.open(encoding="latin-1")):
            sid = r.get("ScanDir ID") or r.get("ScanDirID")  # WashU 만 띄어쓰기 없음
            nitrc[int(sid)] = dx_label(r["DX"])
    return out, nitrc


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--t", type=int, default=100)
    a = ap.parse_args(argv[1:])
    D = a.data_root
    lab, nitrc = labels(D)
    nv = {}
    for r in csv.reader((D / "adhd200/nitrc/nvols.csv").open()):
        if len(r) == 2 and r[1].strip().isdigit():
            nv[Path(r[0]).name] = int(r[1])
    subs, n_roi = [], Counter()
    for f in sorted((D / "adhd200/nitrc/x").glob("*/*/sfnwmrda*_session_1_rest_1_cc200_TCs.1D")):
        site, sid = f.parts[-3], int(f.parts[-2])
        ts = read_tc(f)
        n_roi[ts.shape[1]] += 1
        T = ts.shape[0]
        sd = ts.std(axis=0)
        win_const = [int((ts[s:s + 30].std(axis=0) < 1e-8).sum()) for s in (0, 30, 60) if s + 30 <= T]
        L = lab.get(sid, {})
        nkey = f.name.replace("_cc200_TCs.1D", ".nii.gz")
        subs.append({"site": site, "id": sid, "T": T, "nvols": nv.get(nkey), "n_roi": ts.shape[1],
                     "const_roi_all": int((sd < 1e-8).sum()), "const_roi_win_max": max(win_const) if win_const else None,
                     "dx": L.get("dx"), "y": L.get("y"), "y_nitrc_train": nitrc.get(sid), "qc_rest_1": L.get("qc_rest_1"),
                     "path": str(f.relative_to(D))})
    by_site = defaultdict(list)
    for s in subs:
        by_site[s["site"]].append(s)
    site_rows = []
    for site, ss in sorted(by_site.items()):
        T = [s["T"] for s in ss]
        site_rows.append({"site": site, "n_scans": len(ss), "T_min": min(T), "T_median": int(np.median(T)), "T_max": max(T),
                          "n_T_ge": sum(t >= a.t for t in T), "n_td": sum(s["y"] == 0 for s in ss),
                          "n_adhd": sum(s["y"] == 1 for s in ss), "n_nolabel": sum(s["y"] is None for s in ss),
                          "n_const_win": sum((s["const_roi_win_max"] or 0) > 0 for s in ss)})
    mism = [s["id"] for s in subs if s["y_nitrc_train"] is not None and s["y"] is not None and s["y_nitrc_train"] != s["y"]]
    nv_mism = [s["id"] for s in subs if s["nvols"] is not None and s["nvols"] != s["T"]]
    use = [s for s in subs if s["y"] is not None and s["T"] >= a.t and (s["const_roi_win_max"] or 0) == 0
           and s["const_roi_all"] == 0]

    # 단순 기준선
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    X, y, strat = [], [], []
    for s in use:
        ts = read_tc(D / s["path"])[: a.t]
        c = np.corrcoef(ts.T)
        iu = np.triu_indices(c.shape[0], 1)
        X.append(np.arctanh(np.clip(c[iu], -0.999999, 0.999999)))
        y.append(s["y"])
        strat.append(f"{s['site']}_{s['y']}")
    X, y = np.array(X), np.array(y)
    oof = np.zeros(len(y))
    fold_auc = []
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(X, strat):
        sc = StandardScaler().fit(X[tr])
        m = LogisticRegression(C=1.0, max_iter=5000).fit(sc.transform(X[tr]), y[tr])
        oof[te] = m.predict_proba(sc.transform(X[te]))[:, 1]
        fold_auc.append(float(roc_auc_score(y[te], oof[te])))
    base = {"t": a.t, "n": int(len(y)), "n_td": int((y == 0).sum()), "n_adhd": int((y == 1).sum()),
            "n_features": int(X.shape[1]), "oof_auc": float(roc_auc_score(y, oof)), "fold_auc": fold_auc,
            "model": "StandardScaler + LogisticRegression(C=1, lbfgs), StratifiedKFold(5, seed 0, site x label)"}
    a.out.mkdir(parents=True, exist_ok=True)
    summ = {"n_scans": len(subs), "n_roi_counts": dict(n_roi), "sites": site_rows, "label_mismatch_vs_nitrc_train": mism,
            "nvols_mismatch": nv_mism, "n_usable": len(use), "baseline_fc_logistic": base}
    (a.out / "inventory.json").write_text(json.dumps({"summary": summ, "subjects": subs}, ensure_ascii=False, indent=1))
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
