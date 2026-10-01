#!/usr/bin/env python3
"""G-b 검정력 simulation — exploratory v2 (T4 저표본 곡선), 학습 없음.

결정 29 를 v3 에 그대로 적용한다 — **기준값을 두지 않는다.** 자동 차단 gate 가 아니라
"반드시 재고 반드시 보고해 결정 요청으로 올린다" 는 보고 장치다 (설계안 §5.3.2).

무엇이 v1 (WI-03, ``scripts/h197/20_precision_simulation.py``) 과 다른가
--------------------------------------------------------------------
* **N 은 곡선의 모든 점에서 126 이다.** 점마다 outer fold 5 개를 전부 돌려 pooled
  252 run 을 만들기 때문이다 (2026-10-01 승인). 학습 subject 수 (수준) 는 bootstrap 의
  N 을 바꾸지 않는다. 수준이 바꾸는 것은 **두 칸의 판정이 갈리는 비율 π** 다 — 저표본
  모델은 더 흔들리므로 π 가 커질 수 있다. 그래서 grid 의 축이 N 이 아니라 π 다.
* π 의 기준점으로 **v1 main 의 실측 불일치율**을 함께 적는다 (``--anchor``). 수준 100 이
  v1 구성과 같으므로 (설계안 §5.3.2) 그 값이 곡선 꼭대기의 π 에 가장 가까운 근거다.
  저표본 점의 π 는 **본실험 전에는 알 수 없다** — 그래서 grid 로 넓게 둔다.
* CI 규칙 둘을 함께 낸다. ① **점마다 잠긴 규칙** (97.5%, percentile 1.25–98.75 —
  `configs/exploratory_v2/main.yaml` 의 ``stats.familywise_pct``). ② **읽기 보조**:
  곡선 10 점 (수준 5 × 구조 2) × 주 contrast 2 개를 Bonferroni 로 묶은 동시 규칙
  (99.75%, 0.125–99.875). ② 는 **결정이 아니다** — 곡선 전체에서 "어디선가 하한 > 0"
  을 읽을 때 우연 탐지가 얼마나 섞이는지 보여 주는 참고값이다.

생성 모형과 bootstrap 경로는 v1 스크립트의 함수를 **그대로** 불러 쓴다 (McNemar
trinomial per task, Gaussian copula, 다섯 값 multinomial 재표집 — 동치성은
`tests/v2/test_precision_simulation.py` 가 이미 확인했다).

Usage:
    PYTHONPATH=. .venv/bin/python scripts/exploratory_v2/gb_power_curve.py \
        --out <dir>/gb_power_curve.json --anchor "A-C v1 main=0.0794" ...
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mobse.v3.config import load_config  # noqa: E402


def _load_v1_sim():
    """파일명이 숫자로 시작해 import 문을 쓸 수 없다 — 경로로 싣는다."""
    path = ROOT / "scripts/h197/20_precision_simulation.py"
    spec = importlib.util.spec_from_file_location("v1_precision_sim", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, path


SIM, SIM_PATH = _load_v1_sim()

#: 곡선 점 수 (수준 5 × 구조 2) 와 점마다의 주 contrast 수 (H1·H2).
N_POINTS = 10
N_PRIMARY = 2


def rules(familywise_pct: Sequence[float]) -> Dict[str, Tuple[float, float]]:
    """CI 규칙 둘. ``per_point`` 은 잠긴 값, ``simultaneous`` 는 읽기 보조."""
    lo, hi = float(familywise_pct[0]), float(familywise_pct[1])
    # 잠긴 1.25–98.75 는 이미 H1·H2 두 개를 Bonferroni 로 묶은 값이다 (α=0.05/2).
    # 동시 규칙은 그 위에 곡선 10 점을 더 묶는다: α = 0.05 / (2 × 10).
    alpha = 0.05 / (N_PRIMARY * N_POINTS)
    return {"per_point": (lo, hi),
            "simultaneous": (100 * alpha / 2, 100 * (1 - alpha / 2))}


def bootstrap_bounds(rng: np.random.Generator, d: np.ndarray, n_boot: int,
                     pcts: Dict[str, Tuple[float, float]]) -> Dict[str, np.ndarray]:
    """replicate 마다 규칙별 CI 하한·상한. 한 번 뽑은 재표집으로 두 규칙을 다 잰다."""
    n_rep, n_subj = d.shape
    counts = np.stack([(d == v).sum(axis=1) for v in SIM.D_VALUES], axis=1)
    probs = counts / n_subj
    keys = list(pcts)
    flat = [p for k in keys for p in pcts[k]]
    out = {k: np.empty((n_rep, 2)) for k in keys}
    for r in range(n_rep):
        draw = rng.multinomial(n_subj, probs[r], size=n_boot)
        q = np.percentile(draw @ SIM.D_VALUES / n_subj, flat)
        for i, k in enumerate(keys):
            out[k][r] = q[2 * i: 2 * i + 2]
    return out


def run_cell(seed: int, n_subj: int, pi: float, delta: float, rho: float,
             n_rep: int, n_boot: int, pcts: Dict[str, Tuple[float, float]],
             delta_target: float) -> Dict[str, Any]:
    rng = np.random.Generator(np.random.PCG64(seed))
    d = SIM.simulate_d(rng, n_rep, n_subj, pi, delta, rho)
    bounds = bootstrap_bounds(rng, d, n_boot, pcts)
    row: Dict[str, Any] = {"n_subjects": n_subj, "pi": pi, "delta_true": delta,
                           "rho_latent": rho, "n_replicates": n_rep, "n_boot": n_boot,
                           "seed": seed, "point_mean": float(d.mean())}
    for k, b in bounds.items():
        half = (b[:, 1] - b[:, 0]) / 2.0
        row[k] = {"pct": list(pcts[k]),
                  "ci_halfwidth_median": float(np.median(half)),
                  "p_lower_gt_0": float((b[:, 0] > 0).mean()),
                  "p_lower_gt_delta": float((b[:, 0] > delta_target).mean())}
    return row


def mde(seed: int, n_subj: int, pi: float, rho: float, n_rep: int, n_boot: int,
        pct: Tuple[float, float], target: float, tol: float = 0.002) -> Dict[str, Any]:
    """``P(CI 하한 > 0) ≥ target`` 이 되는 가장 작은 δ (이분법). 상한은 ``δ = π``."""
    one = {"r": pct}

    def power(delta: float, s: int) -> float:
        return run_cell(s, n_subj, pi, delta, rho, n_rep, n_boot, one, 0.0)["r"]["p_lower_gt_0"]

    top = power(pi, seed)
    if top < target:
        return {"mde": None, "power_at_ceiling": top, "hit_ceiling": True}
    lo, hi, it = 0.0, pi, 0
    while it < 12 and hi - lo > tol:
        it += 1
        mid = (lo + hi) / 2.0
        if power(mid, seed + it) >= target:
            hi = mid
        else:
            lo = mid
    return {"mde": float(hi), "hit_ceiling": False, "iterations": it}


def parse_anchor(text: str) -> Dict[str, Any]:
    name, _, value = text.rpartition("=")
    if not name:
        raise SystemExit(f"--anchor 는 '이름=값' 형식이어야 한다: {text!r}")
    return {"name": name.strip(), "pi": float(value)}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--config", type=Path,
                    default=ROOT / "configs/exploratory_v2/main.yaml")
    ap.add_argument("--anchor", action="append", default=[],
                    help="실측 π 기준점 '이름=값' (여러 번)")
    ap.add_argument("--n-rep", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261001)
    args = ap.parse_args(argv[1:])
    if args.out.exists():
        raise SystemExit(f"이미 존재한다: {args.out}. 덮어쓰지 않는다")

    cfg = load_config(args.config)
    n_boot = int(cfg["stats.n_bootstrap"])
    delta_target = float(cfg["stats.delta"])
    pcts = rules(cfg["stats.familywise_pct"])
    n_subj = 126          # pooled endpoint — 모든 수준에서 같다

    anchors = [parse_anchor(a) for a in args.anchor]
    grid_pi = sorted({0.05, 0.10, 0.20, 0.30, 0.40, 0.50}
                     | {round(a["pi"], 4) for a in anchors})
    grid_rho = (0.0, 0.5)
    grid_delta = (0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15)

    t0 = time.time()
    seed = args.seed
    cells: List[Dict[str, Any]] = []
    for pi in grid_pi:
        for rho in grid_rho:
            for delta in grid_delta:
                if delta > pi:
                    continue
                seed += 1
                c = run_cell(seed, n_subj, pi, delta, rho, args.n_rep, n_boot, pcts,
                             delta_target)
                cells.append(c)
                print(f"π={pi:.4f} ρ={rho:.1f} δ={delta:.2f}  "
                      f"per-point P(lo>0)={c['per_point']['p_lower_gt_0']:.3f}  "
                      f"simult P(lo>0)={c['simultaneous']['p_lower_gt_0']:.3f}  "
                      f"halfw={c['per_point']['ci_halfwidth_median']:.4f}", flush=True)

    mde_rows: List[Dict[str, Any]] = []
    for pi in grid_pi:
        for rho in grid_rho:
            for rule, pct in pcts.items():
                for target in (0.5, 0.8):
                    seed += 100
                    row = mde(seed, n_subj, pi, rho, max(500, args.n_rep // 4), n_boot,
                              pct, target)
                    row.update({"pi": pi, "rho_latent": rho, "rule": rule,
                                "target_power": target})
                    mde_rows.append(row)
                    print(f"[MDE] π={pi:.4f} ρ={rho:.1f} {rule} power≥{target} → "
                          f"δ={row['mde']}", flush=True)

    payload = {
        "schema_version": "v3-gb-power-curve-0.1",
        "design_version": str(cfg["meta.design_version"]),
        "config": str(args.config),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "generator": "v1 WI-03 와 같음 — McNemar trinomial per task, Gaussian copula",
        "generator_source": {"path": str(SIM_PATH.relative_to(ROOT)),
                             "sha256": hashlib.sha256(SIM_PATH.read_bytes()).hexdigest()},
        "n_subjects": n_subj,
        "n_subjects_note": "곡선 점마다 outer fold 5 개 pooled — 수준과 무관하게 126",
        "bootstrap": {"n_boot": n_boot, "rules": {k: list(v) for k, v in pcts.items()},
                      "simultaneous_note": f"읽기 보조 — 곡선 {N_POINTS} 점 × 주 contrast "
                                           f"{N_PRIMARY} Bonferroni. 결정이 아니다"},
        "delta_target": delta_target,
        "threshold_policy": "없음 (결정 29) — 보고 장치",
        "anchors": anchors,
        "n_replicates": args.n_rep, "base_seed": args.seed,
        "cells": cells, "minimum_detectable_effect": mde_rows,
        "elapsed_s": round(time.time() - t0, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print("wrote", args.out, f"({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
