#!/usr/bin/env python3
"""I1 분석 — 모델 하나 · 자료 하나의 fit 산출물에서 OOF AUC · Δ · CI 두 종을 낸다 (결정 43, 잠금 초안 §3.1–3.3).

배치 (구동기가 따른다): ``<root>/<model>/<cond>/k<k>/r<seed>/f<fold>/predictions.jsonl`` —
cond ∈ ``orig`` · ``n0`` · ``n1`` · ``n2`` · ``n3`` (MoBSE 팔은 v3 null 이름을 그대로 cond 로 쓴다). ``orig`` · ``n0`` 은 k0 만.

* 단위 (unit) = (cond, k, r): 5 fold 의 test 예측을 모은 OOF. fold 가 빠지거나 표본이 겹치면 ``incomplete`` 로 보고하고 계산에서 뺀다.
* 평가 수준: ABIDE 는 표본 = 피험자. AOMIC (``--samples``) 은 창 예측을 **run 평균** 하고 bootstrap 단위는 피험자.
* AUC 주 · BA (문턱 0.5) 보조. Δ_{c,k,r} = AUC(orig, r) − AUC(c, k, r) — 같은 seed 짝.
* CI (각 ``--n-boot`` 회, 95 % percentile, 같은 피험자 재표집을 원판 · null 에 함께 — 짝 bootstrap):
  - ``single``: 가장 작은 r 과 k=0 한 쌍의 Δ.
  - ``retrain``: 피험자 재표집 + (k, r) 짝을 복원 재표집해 평균 Δ (2 단).
  - ``single_excludes_zero_rate``: 모든 (k, r) 짝마다 단일 CI 를 내 0 을 벗어나는 비율 (C3).
* 붕괴 (fit 단위): test 예측 표준편차 < 1e−6 또는 예측 class 가 하나뿐. 붕괴 fit 이 하나라도 있는 단위를 표시하고,
  그 단위를 뺀 결과를 ``excluding_collapsed`` 로 함께 낸다. 실패 판을 다시 돌리지 않는다 (결정 43).
* δ · 다중성 보정 없음 — 기술용 (결정 43).

Usage:
    python scripts/i1/analyze.py --root <dataset root> --model bqn --out <json> [--samples samples.jsonl] [--n-boot 2000]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

COND_ORDER = ("orig", "n0", "n1", "n2", "n3")
N_FOLDS = 5


def load_units(model_dir: Path):
    units, fits = {}, []
    for cond_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
        for k_dir in sorted(cond_dir.glob("k*")):
            for r_dir in sorted(k_dir.glob("r*")):
                preds, collapsed, folds = {}, [], []
                for f_dir in sorted(r_dir.glob("f*")):
                    pf = f_dir / "predictions.jsonl"
                    if not pf.exists():
                        continue
                    rows = [json.loads(x) for x in pf.read_text().splitlines() if x.strip()]
                    p = np.array([x["p1"] for x in rows])
                    col = bool(p.std() < 1e-6 or len(set((p > 0.5).tolist())) == 1)
                    collapsed.append(col)
                    folds.append(f_dir.name)
                    fits.append({"cond": cond_dir.name, "k": k_dir.name, "r": r_dir.name, "fold": f_dir.name,
                                 "collapsed": col})
                    for x in rows:
                        if x["subject_index"] in preds:
                            raise SystemExit(f"표본이 두 fold 에 있다: {r_dir} {x['subject_index']}")
                        preds[x["subject_index"]] = (x["label"], x["p1"])
                units[(cond_dir.name, int(k_dir.name[1:]), int(r_dir.name[1:]))] = {
                    "preds": preds, "n_folds": len(folds), "any_collapsed": any(collapsed)}
    return units, fits


def to_items(preds: dict, n: int, samples):
    """표본 예측 → 평가 항목 (ABIDE: 표본 그대로 · AOMIC: run 평균). 반환 (label, p, cluster)."""
    if len(preds) != n:
        return None
    idx = np.arange(n)
    lab = np.array([preds[i][0] for i in idx])
    p = np.array([preds[i][1] for i in idx])
    if samples is None:
        return lab, p, idx
    keys = [(s["subject"], s["task"]) for s in samples]
    groups = defaultdict(list)
    for i, key in enumerate(keys):
        groups[key].append(i)
    order = sorted(groups)
    subj = {s: j for j, s in enumerate(sorted({k[0] for k in order}))}
    return (np.array([lab[groups[k][0]] for k in order]), np.array([p[groups[k]].mean() for k in order]),
            np.array([subj[k[0]] for k in order]))


def auc_w(y, p, w):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p, sample_weight=w))


def ba(y, p):
    from sklearn.metrics import balanced_accuracy_score
    return float(balanced_accuracy_score(y, (p > 0.5).astype(int)))


def ci(a):
    a = np.asarray(a)
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def analyze(items: dict, n_boot: int, seed: int) -> dict:
    keys = sorted(items)
    y0, _, cl = items[keys[0]]
    for k in keys:
        if not (np.array_equal(items[k][0], y0) and np.array_equal(items[k][2], cl)):
            raise SystemExit(f"단위 사이 label · cluster 가 다르다: {k}")
    n_cl = int(cl.max()) + 1
    rng = np.random.Generator(np.random.PCG64(seed))
    boot = {k: np.empty(n_boot) for k in keys}

    for b in range(n_boot):
        cnt = np.bincount(rng.integers(0, n_cl, n_cl), minlength=n_cl)
        w = cnt[cl].astype(float)
        if len(set(y0[w > 0].tolist())) < 2:
            w = np.ones_like(w)                                    # 한 class 만 뽑힌 드문 경우 — 원표본으로 (기록)
        for k in keys:
            boot[k][b] = auc_w(y0, items[k][1], w)
    point = {k: {"auc": auc_w(y0, items[k][1], None), "ba": ba(y0, items[k][1])} for k in keys}
    out = {"n_items": int(len(y0)), "n_clusters": n_cl, "units": {f"{c}/k{k}/r{r}": point[(c, k, r)] for c, k, r in keys}}
    origs = {r: (c, k, r) for c, k, r in keys if c == "orig"}
    conds = sorted({c for c, _, _ in keys if c != "orig"}, key=lambda c: (COND_ORDER.index(c) if c in COND_ORDER else 99, c))
    out["orig_auc_mean"] = float(np.mean([point[u]["auc"] for u in origs.values()])) if origs else None
    out["conditions"] = {}
    for c in conds:
        pairs = [((c, k, r), origs[r]) for cc, k, r in keys if cc == c and r in origs]
        if not pairs:
            continue
        d_point = [point[o]["auc"] - point[u]["auc"] for u, o in pairs]
        d_boot = np.stack([boot[o] - boot[u] for u, o in pairs])          # (짝, n_boot)
        first = min(range(len(pairs)), key=lambda i: (pairs[i][0][2], pairs[i][0][1]))
        prng = np.random.Generator(np.random.PCG64(seed + 1))
        pick = prng.integers(0, len(pairs), size=(n_boot, len(pairs)))
        retrain = d_boot[pick, np.arange(n_boot)[:, None]].mean(axis=1)
        singles = [ci(d_boot[i]) for i in range(len(pairs))]
        out["conditions"][c] = {
            "n_pairs": len(pairs), "delta_mean": float(np.mean(d_point)),
            "delta_sd_between_runs": float(np.std(d_point, ddof=1)) if len(pairs) > 1 else None,
            "delta_by_pair": {f"k{u[1]}/r{u[2]}": float(v) for (u, _), v in zip(pairs, d_point)},
            "single": {"pair": f"k{pairs[first][0][1]}/r{pairs[first][0][2]}", "delta": float(d_point[first]),
                       "ci95": singles[first]},
            "retrain_ci95": ci(retrain),
            "single_halfwidth_median": float(np.median([(hi - lo) / 2 for lo, hi in singles])),
            "single_excludes_zero_rate": float(np.mean([lo > 0 or hi < 0 for lo, hi in singles])),
            "null_auc_mean": float(np.mean([point[u]["auc"] for u, _ in pairs])),
        }
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--samples", type=Path, default=None, help="AOMIC samples.jsonl (run 평균 · 피험자 bootstrap)")
    ap.add_argument("--n-items", type=int, required=True, help="표본 수 (ABIDE 1009 · AOMIC 창 1008)")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261006)
    a = ap.parse_args(argv[1:])
    samples = None
    if a.samples:
        samples = [json.loads(x) for x in a.samples.read_text().splitlines() if x.strip()]
    units, fits = load_units(a.root / a.model)
    items, incomplete = {}, []
    for key, u in units.items():
        it = to_items(u["preds"], a.n_items, samples) if u["n_folds"] == N_FOLDS else None
        if it is None:
            incomplete.append({"unit": "/".join(map(str, key)), "n_folds": u["n_folds"], "n_preds": len(u["preds"])})
        else:
            items[key] = it
    collapsed_units = sorted("/".join(map(str, k)) for k, u in units.items() if u["any_collapsed"])
    res = {"schema_version": "i1-analysis-0.1", "model": a.model, "root": str(a.root), "n_boot": a.n_boot, "seed": a.seed,
           "level": "run (창 평균) · 피험자 bootstrap" if samples else "피험자", "n_fits": len(fits),
           "n_collapsed_fits": int(sum(f["collapsed"] for f in fits)), "collapsed_units": collapsed_units,
           "incomplete_units": incomplete}
    res["all"] = analyze(items, a.n_boot, a.seed) if items else None
    keep = {k: v for k, v in items.items() if not units[k]["any_collapsed"]}
    if collapsed_units and keep:
        res["excluding_collapsed"] = analyze(keep, a.n_boot, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if res["all"]:
        print(f"{a.model}: orig AUC {res['all']['orig_auc_mean']}")
        for c, v in res["all"]["conditions"].items():
            print(f"  {c}: Δ {v['delta_mean']:+.4f}  retrain CI {np.round(v['retrain_ci95'], 4).tolist()}  "
                  f"single {np.round(v['single']['ci95'], 4).tolist()}  excl0 {v['single_excludes_zero_rate']:.2f}")
    print(f"fits {res['n_fits']} · collapsed {res['n_collapsed_fits']} · incomplete {len(incomplete)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
