#!/usr/bin/env python3
"""δ=0.02 정밀도 시나리오 simulation — 지침서 WI-03, 계획서 §8.

계획서는 "정밀도 계획은 QC 후 N과 사전 paired-error discordance/상관 시나리오로
simulation하며, 분리된 pilot의 추정은 불확실성과 함께 보조적으로 사용한다.
metadata만으로 paired effect power를 추정했다고 하지 않는다"고 정한다.

그래서 이 스크립트는 **공식이 아니라 simulation** 이다. 가정을 grid 로 놓고,
각 칸에서 자료를 생성해 계획서가 정한 bootstrap 절차를 그대로 돌린다.

생성 모형
---------
subject i, task t 의 정오 차이를 ``Δ_it ∈ {-1, 0, +1}`` 로 둔다
(+1 = cell A 만 맞음, -1 = cell B 만 맞음, 0 = 둘 다 같음). McNemar 구조다.

* ``P(Δ=+1) = (π + δ) / 2``, ``P(Δ=-1) = (π - δ) / 2``, ``P(Δ=0) = 1 - π``
* π 는 **discordance rate**, δ 는 그 task 의 참 효과. ``|δ| ≤ π``.
* 두 task 는 잠재 정규 copula 로 상관 ρ 를 준다.
* subject 의 endpoint 차이는 ``d_i = (Δ_emo + Δ_wm) / 2`` 이고
  BA 차이는 ``mean_i(d_i)`` 다 — 계획서 §8 의 ``b_i`` 정의와 같다.

**주변 정확도(marginal accuracy)는 들어가지 않는다.** paired 차이의 분포는
π 와 δ 로 완전히 정해진다. 그래서 "기준선 정확도 몇 %" 를 가정할 필요가 없다.

bootstrap
---------
group = subject 이므로(개정 P4) group bootstrap 은 subject bootstrap 과 같다.
``d`` 가 ``{-1, -0.5, 0, 0.5, 1}`` 다섯 값만 취하므로 재표집 평균의 분포는
다섯 칸 multinomial 로 **정확히** 같다. 그 경로를 쓰면 계획서의 n_boot=10,000 을
줄이지 않고도 grid 전체를 돌릴 수 있다.

동치성은 `tests/v2/test_precision_simulation.py` 가 확인한다 —
(a) index 경로와 multinomial 경로의 CI 가 Monte Carlo 오차 안에서 일치하고,
(b) index 경로 자체가 `mobse.v2.statistics.paired_bootstrap` 과 **완전히 동일**하다.

Usage:
    python scripts/h197/20_precision_simulation.py --out /tmp/precision.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import NormalDist
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2.statistics import FAMILYWISE_PCT, N_BOOTSTRAP            # noqa: E402

#: d_i 가 취할 수 있는 다섯 값.
D_VALUES = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])

DELTA = 0.02


def trinomial_thresholds(pi: float, delta: float) -> Tuple[float, float]:
    """``Δ`` 의 잠재 정규 절단점 두 개."""
    if not 0.0 <= pi <= 1.0:
        raise ValueError(f"π 가 [0,1] 밖이다: {pi}")
    if abs(delta) > pi:
        raise ValueError(f"|δ| ≤ π 여야 한다: δ={delta}, π={pi}")
    p_minus = (pi - delta) / 2.0
    p_zero = 1.0 - pi
    return _ppf(p_minus), _ppf(p_minus + p_zero)


def _ppf(p: float) -> float:
    """정규 분위수. 경계 0·1 에서 ±inf 를 돌려준다.

    `δ = ±π` 이면 한쪽 확률이 정확히 0 이 되고 `NormalDist.inv_cdf` 는 거기서
    예외를 던진다. MDE 탐색이 상한 `δ = π` 를 실제로 시도하므로 경계를 막지
    않고 ±inf 로 처리한다 — 절단점이 -inf 면 그 칸의 확률이 0 이라는 뜻이다.
    """
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    return NormalDist().inv_cdf(p)


def simulate_d(rng: np.random.Generator, n_rep: int, n_subj: int,
               pi: float, delta: float, rho: float) -> np.ndarray:
    """``(n_rep, n_subj)`` 의 subject 별 endpoint 차이 ``d``."""
    t_lo, t_hi = trinomial_thresholds(pi, delta)
    z = rng.standard_normal(size=(n_rep, n_subj, 2))
    # copula: z2 를 z1 과 상관 ρ 로 만든다.
    z2 = rho * z[..., 0] + np.sqrt(max(0.0, 1.0 - rho * rho)) * z[..., 1]
    deltas = []
    for zi in (z[..., 0], z2):
        d = np.zeros_like(zi)
        d[zi < t_lo] = -1.0
        d[zi >= t_hi] = 1.0
        deltas.append(d)
    return (deltas[0] + deltas[1]) / 2.0


def bootstrap_lo_hi_multinomial(rng: np.random.Generator, d: np.ndarray,
                                n_boot: int,
                                pct: Sequence[float]) -> Tuple[np.ndarray, np.ndarray]:
    """각 replicate 의 bootstrap CI 하한·상한.

    ``d`` 의 다섯 값 빈도로 multinomial 을 뽑는다. index 재표집과 분포가 같다.
    """
    n_rep, n_subj = d.shape
    # 다섯 값의 경험 빈도
    counts = np.stack([(d == v).sum(axis=1) for v in D_VALUES], axis=1)  # (n_rep, 5)
    probs = counts / n_subj
    los = np.empty(n_rep)
    his = np.empty(n_rep)
    for r in range(n_rep):
        draw = rng.multinomial(n_subj, probs[r], size=n_boot)            # (n_boot, 5)
        stats = draw @ D_VALUES / n_subj
        los[r], his[r] = np.percentile(stats, pct)
    return los, his


def run_cell(seed: int, n_subj: int, pi: float, delta: float, rho: float,
             n_rep: int, n_boot: int) -> Dict[str, Any]:
    """시나리오 한 칸."""
    rng = np.random.Generator(np.random.PCG64(seed))
    d = simulate_d(rng, n_rep, n_subj, pi, delta, rho)
    los, his = bootstrap_lo_hi_multinomial(rng, d, n_boot, FAMILYWISE_PCT)
    half = (his - los) / 2.0
    # 실현된 두 task 상관 (참고용) — 첫 replicate 에서 잰다.
    return {
        "n_subjects": n_subj, "pi": pi, "delta_true": delta, "rho_latent": rho,
        "n_replicates": n_rep, "n_boot": n_boot,
        "point_mean": float(d.mean()),
        "sd_d": float(d.mean(axis=1).std(ddof=1)),
        "ci_halfwidth_median": float(np.median(half)),
        "ci_halfwidth_p90": float(np.percentile(half, 90)),
        "p_lower_gt_0": float((los > 0).mean()),
        "p_lower_gt_delta": float((los > DELTA).mean()),
        "p_ci_contains_0": float(((los <= 0) & (his >= 0)).mean()),
    }


def minimum_detectable_effect(seed: int, n_subj: int, pi: float, rho: float,
                             n_rep: int, n_boot: int, target: float = 0.80,
                             tol: float = 0.002) -> Dict[str, Any]:
    """``P(CI 하한 > 0) = target`` 이 되는 δ 를 이분법으로 찾는다.

    "80% power 를 확보했다"고 적지 않기 위해, 반대로 **80% 를 주려면 효과가
    얼마여야 하는지**를 구한다. 계획서 §8 의 δ=0.02 와 비교하면 이 설계가
    무엇을 검출할 수 있는지가 바로 보인다.

    Returns:
        ``{"mde", "achieved_power", "iterations", "hit_ceiling"}``.
        δ 는 ``|δ| ≤ π`` 이므로 π 에서도 target 에 못 미치면 `hit_ceiling` 이다.
    """
    lo, hi = 0.0, pi
    best: Dict[str, Any] = {"mde": None, "achieved_power": None}
    it = 0
    top = run_cell(seed, n_subj, pi, pi, rho, n_rep, n_boot)["p_lower_gt_0"]
    if top < target:
        return {"mde": None, "achieved_power": float(top), "iterations": 0,
                "hit_ceiling": True,
                "note": f"δ 를 상한 π={pi} 까지 올려도 power {top:.3f} < {target}"}
    while it < 12 and (hi - lo) > tol:
        it += 1
        mid = (lo + hi) / 2.0
        power = run_cell(seed + it, n_subj, pi, mid, rho, n_rep, n_boot)["p_lower_gt_0"]
        if power >= target:
            hi, best = mid, {"mde": float(mid), "achieved_power": float(power)}
        else:
            lo = mid
    best.update({"iterations": it, "hit_ceiling": False})
    if best["mde"] is None:
        best.update({"mde": float(hi), "achieved_power": float(top)})
    return best


def pilot_uncertainty(n_pilot: int, pis: Sequence[float]) -> List[Dict[str, Any]]:
    """pilot 이 π 를 얼마나 정확히 추정하는가 (Wilson 95% 구간)."""
    z = NormalDist().inv_cdf(0.975)
    out = []
    for pi in pis:
        n = n_pilot
        centre = (pi + z * z / (2 * n)) / (1 + z * z / n)
        halfw = (z * np.sqrt(pi * (1 - pi) / n + z * z / (4 * n * n))) / (1 + z * z / n)
        out.append({"n_pilot": n, "pi_true": pi,
                    "wilson_lo": float(max(0.0, centre - halfw)),
                    "wilson_hi": float(min(1.0, centre + halfw)),
                    "width": float(min(1.0, centre + halfw) - max(0.0, centre - halfw))})
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n-rep", type=int, default=2000)
    ap.add_argument("--n-boot", type=int, default=N_BOOTSTRAP)
    ap.add_argument("--seed", type=int, default=20260918)
    args = ap.parse_args(argv[1:])

    grid_pi = (0.05, 0.10, 0.20, 0.30)
    grid_rho = (0.0, 0.5)
    grid_delta = (0.00, 0.02, 0.04)
    grid_n = (126, 189)

    cells: List[Dict[str, Any]] = []
    seed = args.seed
    for n in grid_n:
        for pi in grid_pi:
            for rho in grid_rho:
                for delta in grid_delta:
                    if abs(delta) > pi:
                        continue
                    seed += 1
                    cells.append(run_cell(seed, n, pi, delta, rho,
                                          args.n_rep, args.n_boot))
                    c = cells[-1]
                    print(f"N={n} π={pi:.2f} ρ={rho:.1f} δ={delta:.2f}  "
                          f"halfwidth={c['ci_halfwidth_median']:.4f}  "
                          f"P(lo>0)={c['p_lower_gt_0']:.3f}  "
                          f"P(lo>δ)={c['p_lower_gt_delta']:.3f}", flush=True)

    mde_rows: List[Dict[str, Any]] = []
    for n in grid_n:
        for pi in grid_pi:
            for rho in grid_rho:
                seed += 100
                row = minimum_detectable_effect(seed, n, pi, rho,
                                                max(500, args.n_rep // 4), args.n_boot)
                row.update({"n_subjects": n, "pi": pi, "rho_latent": rho})
                mde_rows.append(row)
                print(f"[MDE] N={n} π={pi:.2f} ρ={rho:.1f} → "
                      f"δ80={row['mde']} (ceiling={row['hit_ceiling']})", flush=True)

    payload = {
        "schema_version": "precision_scenarios_v1",
        "generator": "McNemar trinomial per task, Gaussian copula across tasks",
        "bootstrap": {"n_boot": args.n_boot, "pct": list(FAMILYWISE_PCT),
                      "path": "multinomial over the five values of d (index 재표집과 동치)"},
        "delta_target": DELTA,
        "n_replicates": args.n_rep,
        "base_seed": args.seed,
        "cells": cells,
        "minimum_detectable_effect": mde_rows,
        "pilot_uncertainty": pilot_uncertainty(31, grid_pi),
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
