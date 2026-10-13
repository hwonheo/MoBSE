#!/usr/bin/env python3
"""963 명 공통 분석 (결정 59 D1) — MoBSE 2 구조와 I1 공개 모델 3 종을 같은 피험자로 다시 낸다.

계산은 I1 ``scripts/i1/analyze.py`` 의 함수 (``load_units`` · ``to_items`` · ``analyze``) 를 import 해 그대로 쓴다 — 고치지 않는다.
다른 점은 하나: 각 단위의 예측에서 상수 영역 피험자 (46 명) 를 빼고, 남은 963 명의 index 를 0–962 로 다시 매긴 뒤 넘긴다.
붕괴 표시는 I1 과 같게 fit 의 **전체** test 예측으로 판단한다 (``load_units`` 그대로). 공개 모델은 새 학습이 없다.

Usage:
    python scripts/i1_mobse_abide/analyze963.py --data-root <D> --mobse-root <OUT>/abide --kept <OUT>/kept_subjects.json \
        --out <OUT>/analysis [--n-boot 2000]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ("bqn", "bnt", "han")
MOBSE = ("mobse_mean", "mobse_embedding")
I1_ABIDE = "i1/main/20261005_ac3bad06_a2/abide"


def i1_analyze():
    spec = importlib.util.spec_from_file_location("i1_analyze", ROOT / "scripts/i1/analyze.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(model_dir: Path, model: str, kept: list, n_boot: int, seed: int, A) -> dict:
    remap = {old: new for new, old in enumerate(kept)}
    units, fits = A.load_units(model_dir)
    items, incomplete = {}, []
    for key, u in units.items():
        preds = {remap[i]: v for i, v in u["preds"].items() if i in remap}
        it = A.to_items(preds, len(kept), None) if u["n_folds"] == A.N_FOLDS else None
        if it is None:
            incomplete.append({"unit": "/".join(map(str, key)), "n_folds": u["n_folds"], "n_preds": len(preds)})
        else:
            items[key] = it
    collapsed_units = sorted("/".join(map(str, k)) for k, u in units.items() if u["any_collapsed"])
    res = {"schema_version": "i1-mobse-abide-analysis-0.1", "model": model, "root": str(model_dir),
           "n_boot": n_boot, "seed": seed, "level": "피험자 (963 명 공통)", "n_items_expected": len(kept),
           "n_fits": len(fits), "n_collapsed_fits": int(sum(f["collapsed"] for f in fits)),
           "collapsed_units": collapsed_units, "incomplete_units": incomplete}
    res["all"] = A.analyze(items, n_boot, seed) if items else None
    keep = {k: v for k, v in items.items() if not units[k]["any_collapsed"]}
    if collapsed_units and keep:
        res["excluding_collapsed"] = A.analyze(keep, n_boot, seed)
    return res


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--mobse-root", required=True, type=Path)
    ap.add_argument("--kept", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261006)
    ap.add_argument("--models", default=",".join(MOBSE + PUBLIC))
    a = ap.parse_args(argv[1:])
    A = i1_analyze()
    kept = json.loads(a.kept.read_text())["kept"]
    a.out.mkdir(parents=True, exist_ok=True)
    for m in a.models.split(","):
        mdir = a.mobse_root / m if m in MOBSE else a.data_root / I1_ABIDE / m
        res = run(mdir, m, kept, a.n_boot, a.seed, A)
        (a.out / f"{m}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        al = res["all"]
        print(f"{m}: fits {res['n_fits']} · collapsed {res['n_collapsed_fits']} · incomplete {len(res['incomplete_units'])}"
              + (f" · orig AUC {al['orig_auc_mean']:.4f}" if al else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
