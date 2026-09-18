"""정밀도 simulation 의 근거 확인 — `scripts/h197/20_precision_simulation.py`.

두 가지를 확인한다.

1. **index 재표집 경로가 계획서 구현과 완전히 동일**한가.
   group = subject (개정 P4) 일 때 `statistics.paired_bootstrap` 의 group
   bootstrap 은 평범한 subject bootstrap 으로 퇴화한다. simulation 이 그 사실에
   기대고 있으므로 **완전 일치**를 요구한다.
2. **multinomial 경로가 index 경로와 같은 분포**를 주는가. simulation 은 속도를
   위해 multinomial 경로를 쓴다. Monte Carlo 오차 안에서 CI 가 일치해야 한다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from mobse.v2.statistics import (BOOTSTRAP_SEED, FAMILYWISE_PCT, bootstrap_indices,
                                 paired_bootstrap)

_SPEC = importlib.util.spec_from_file_location(
    "precision_sim",
    Path(__file__).resolve().parents[2] / "scripts/h197/20_precision_simulation.py")
SIM = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SIM)


def _values(n, seed=7):
    rng = np.random.Generator(np.random.PCG64(seed))
    d = rng.choice(SIM.D_VALUES, size=n)
    subs = [f"ds002785:sub-{i:04d}" for i in range(n)]
    return dict(zip(subs, d.tolist())), {s: s for s in subs}


# --------------------------------------------------------------------------- #
# 1. group=subject 에서 group bootstrap == subject bootstrap
# --------------------------------------------------------------------------- #


def test_group_bootstrap_degenerates_to_plain_subject_bootstrap():
    n = 60
    values, groups = _values(n)
    subjects = sorted(values)
    idx = bootstrap_indices(groups, subjects, seed=BOOTSTRAP_SEED, n_boot=500)
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    draws = rng.integers(0, n, size=(500, n))
    for k in range(500):
        assert np.array_equal(idx[k], draws[k]), f"{k} 번째 재표집이 다르다"


def test_vectorised_mean_matches_paired_bootstrap_exactly():
    n = 80
    values, groups = _values(n, seed=11)
    subjects = sorted(values)
    vec = np.asarray([values[s] for s in subjects])
    res = paired_bootstrap(values, groups, n_boot=400)

    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    draws = rng.integers(0, n, size=(400, n))
    stats = vec[draws].mean(axis=1)
    lo, hi = np.percentile(stats, FAMILYWISE_PCT)
    assert res.lo == pytest.approx(lo, abs=0, rel=0)
    assert res.hi == pytest.approx(hi, abs=0, rel=0)
    assert res.point == pytest.approx(float(vec.mean()))


# --------------------------------------------------------------------------- #
# 2. multinomial 경로 == index 경로 (분포적으로)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("n", [126, 189])
def test_multinomial_path_matches_index_path_within_mc_error(n):
    """두 경로의 CI 차이가 격자 한 칸 규모인지 본다.

    ``d`` 가 0.5 단위이므로 재표집 평균은 ``0.5/n`` 간격의 격자 위에만 놓인다
    (n=126 이면 0.003968). percentile 추정은 그 격자에서 한 칸씩 튈 수 있으므로
    '완전 일치'를 요구하면 안 되고, **한 칸 규모를 넘지 않는지**와
    **계통 편차가 없는지**를 봐야 한다.
    """
    values, _ = _values(n, seed=n)
    vec = np.asarray([values[s] for s in sorted(values)])
    step = 0.5 / n
    n_boot = 20_000

    diffs_lo, diffs_hi = [], []
    for rep in range(6):
        rng_i = np.random.Generator(np.random.PCG64(1000 + rep))
        draws = rng_i.integers(0, n, size=(n_boot, n))
        lo_i, hi_i = np.percentile(vec[draws].mean(axis=1), FAMILYWISE_PCT)

        rng_m = np.random.Generator(np.random.PCG64(2000 + rep))
        lo_m, hi_m = SIM.bootstrap_lo_hi_multinomial(
            rng_m, vec.reshape(1, -1), n_boot, FAMILYWISE_PCT)
        diffs_lo.append(lo_m[0] - lo_i)
        diffs_hi.append(hi_m[0] - hi_i)

    for name, diffs in (("lo", diffs_lo), ("hi", diffs_hi)):
        worst = max(abs(d) for d in diffs)
        assert worst <= 2 * step + 1e-12, (name, worst, step)
        # 계통 편차가 있으면 같은 절차가 아니다.
        assert abs(np.mean(diffs)) <= step, (name, np.mean(diffs), step)


# --------------------------------------------------------------------------- #
# 생성 모형
# --------------------------------------------------------------------------- #


def test_thresholds_reject_impossible_effect():
    with pytest.raises(ValueError):
        SIM.trinomial_thresholds(0.05, 0.10)


@pytest.mark.parametrize("pi,delta", [(0.10, 0.0), (0.20, 0.02), (0.30, 0.04)])
def test_generator_reproduces_pi_and_delta(pi, delta):
    rng = np.random.Generator(np.random.PCG64(3))
    d = SIM.simulate_d(rng, 400, 3000, pi, delta, rho=0.0)
    # d = (Δe + Δw)/2 이므로 평균은 task 별 δ 와 같다.
    assert d.mean() == pytest.approx(delta, abs=0.004)
    # 한 task 의 불일치율: |Δ| = 1 인 비율. d 에서 직접 못 읽으므로 분산으로 확인한다.
    # Var(Δ) = π - δ²,  Var(d) = Var(Δ)/2  (ρ=0)
    assert d.var() == pytest.approx((pi - delta ** 2) / 2.0, rel=0.05)


def test_rho_increases_variance_of_the_paired_difference():
    rng = np.random.Generator(np.random.PCG64(5))
    lo = SIM.simulate_d(rng, 200, 2000, 0.20, 0.02, rho=0.0).var()
    hi = SIM.simulate_d(rng, 200, 2000, 0.20, 0.02, rho=0.6).var()
    assert hi > lo * 1.1, (lo, hi)


def test_pilot_uncertainty_is_wide_at_n31():
    """pilot 31명으로는 π 를 좁히지 못한다 — 보고서가 주장하는 바의 근거."""
    rows = SIM.pilot_uncertainty(31, [0.15])
    assert rows[0]["width"] > 0.15, rows


def test_thresholds_handle_the_delta_equals_pi_boundary():
    """MDE 탐색이 δ = π 를 실제로 시도한다. 거기서 죽으면 안 된다."""
    lo, hi = SIM.trinomial_thresholds(0.20, 0.20)
    assert lo == float("-inf")
    rng = np.random.Generator(np.random.PCG64(1))
    d = SIM.simulate_d(rng, 50, 500, 0.20, 0.20, rho=0.0)
    assert d.min() >= 0.0, "δ = π 이면 Δ = -1 이 나올 수 없다"
    assert d.mean() == pytest.approx(0.20, abs=0.02)


def test_thresholds_handle_the_negative_boundary():
    lo, hi = SIM.trinomial_thresholds(0.20, -0.20)
    assert hi == float("inf")
    rng = np.random.Generator(np.random.PCG64(2))
    d = SIM.simulate_d(rng, 50, 500, 0.20, -0.20, rho=0.0)
    assert d.max() <= 0.0
