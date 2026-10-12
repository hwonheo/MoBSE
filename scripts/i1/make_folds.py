#!/usr/bin/env python3
"""I1 공통 fold — 층화 무작위 5-fold (결정 38) · 층 = label × site · 안쪽 val = train fold 의 층화 10 % (결정 41 · 42).

모든 모델 · 조건 (원판 · N0–N3) 이 같은 fold 를 쓴다 — null 은 입력만 바꾸고 피험자 순서는 그대로라 index 가 그대로 통한다.
fold 는 피험자 **index** (표준 ``abide.npy`` 의 행 순서) 와 함께 ``kept_sub_ids`` 도 적어, 행 순서가 바뀌면 드러나게 한다.

``--draw`` 는 fold 를 몇 번째로 뽑았는가 (0 부터). R 반복에서 fold 는 다시 뽑지 않는다 (결정 43) — draw 0 하나.

``--by-site``: site 민감도 (결정 38-2 · 43) 용 **site 묶음 5-fold** — ``GroupKFold(5)`` (site 20 개, 결정적), 안쪽 val 은 같은 방식.

Usage (h197, venv-i1):
    python scripts/i1/make_folds.py --npy <abide.npy> --meta <abide.json> --out <folds_draw0.json> [--draw 0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

BASE_SEED = 20261004
N_FOLDS = 5
VAL_FRAC = 0.10


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npy", required=True, type=Path)
    ap.add_argument("--meta", required=True, type=Path, help="build_abide_npy.py 가 쓴 abide.json (kept_sub_ids)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--draw", type=int, default=0)
    ap.add_argument("--by-site", action="store_true", help="site 묶음 GroupKFold (site 민감도)")
    args = ap.parse_args(argv[1:])
    if args.out.exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {args.out}", file=sys.stderr)
        return 2
    from sklearn.model_selection import GroupKFold, StratifiedKFold, StratifiedShuffleSplit

    data = np.load(args.npy, allow_pickle=True).item()
    y, site = np.asarray(data["label"]).astype(int), np.asarray(data["site"]).astype(str)
    ids = json.loads(args.meta.read_text())["kept_sub_ids"]
    if len(ids) != len(y):
        raise SystemExit(f"kept_sub_ids {len(ids)} ≠ 표본 {len(y)}")
    strata = np.array([f"{s}|{l}" for s, l in zip(site, y)])
    seed = int(np.random.SeedSequence([BASE_SEED, args.draw]).generate_state(1)[0])
    if args.by_site:
        outer = GroupKFold(n_splits=N_FOLDS).split(np.zeros(len(y)), y, groups=site)
    else:
        outer = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed).split(np.zeros(len(y)), strata)
    folds = []
    for f, (tr, te) in enumerate(outer):
        vseed = int(np.random.SeedSequence([BASE_SEED, args.draw, f + 1]).generate_state(1)[0])
        sss = StratifiedShuffleSplit(n_splits=1, test_size=VAL_FRAC, random_state=vseed)
        itr, iva = next(sss.split(np.zeros(len(tr)), strata[tr]))
        train, val, test = np.sort(tr[itr]), np.sort(tr[iva]), np.sort(te)
        assert not (set(train) & set(val) or set(train) & set(test) or set(val) & set(test))
        if args.by_site:
            assert not set(site[test]) & set(site[train]) and not set(site[test]) & set(site[val]), "site 가 fold 를 넘었다"
        folds.append({"fold": f, "train": train.tolist(), "val": val.tolist(), "test": test.tolist(),
                      "test_sites": sorted(set(site[test].tolist())),
                      "n": [len(train), len(val), len(test)],
                      "test_label1_frac": float(y[test].mean()), "val_label1_frac": float(y[val].mean())})
    all_test = sorted(i for fd in folds for i in fd["test"])
    assert all_test == list(range(len(y))), "test 가 전체를 한 번씩 덮지 않는다"
    rec = {"schema_version": "i1-folds-0.1", "draw": args.draw, "base_seed": BASE_SEED, "outer_seed": seed,
           "n_folds": N_FOLDS, "val_frac": VAL_FRAC, "by_site": args.by_site,
           "outer": "GroupKFold(site)" if args.by_site else "StratifiedKFold(label × site)",
           "strata": "label × site", "n_strata": int(len(set(strata))),
           "min_stratum": int(min(np.unique(strata, return_counts=True)[1])),
           "npy_sha256": hashlib.sha256(args.npy.read_bytes()).hexdigest(),
           "sub_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(), "n_subj": len(y),
           "folds": folds}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k != "folds"} |
                     {"fold_sizes": [fd["n"] for fd in folds],
                      "test_label1_frac": [round(fd["test_label1_frac"], 3) for fd in folds]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
