"""R2T 상태 혼합 시험 (결정 84) — 합성 자료만. 합성 결과는 실제 BOLD 가설의 근거가 아니다.

* 동일성: K=1 이면 MIX-f = MIX-a = 단일 prior (평균 0 LW). 가중 LW 는 같은 가중치에서 sklearn 과 같다.
* 불변성: 성분 순서 · 가린 값 · run 의 창 밖 frame · test 피험자 자료.
* 안정성 · 실패: 성분 공분산 SPD, 희박 성분 · 미수렴 · 수치 오류는 status 로 남고 예측이 거부된다.
* null (상태 없음): K>1 혼합이 단일 prior 보다 눈에 띄게 낫지 않다 (가짜 이득 없음).
* positive control (상태 구별): MIX-a 가 단일 prior · MIX-f 보다 낫다.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "r2t"))
import mix as M  # noqa: E402
import r2t_lib as R  # noqa: E402
import synth_mix as SM  # noqa: E402


def _world(n_states: int, seed: int):
    w = SM.MixWorld(SM.MixSpec(n_states=n_states, seed=seed))
    ids = [f"s{i:03d}" for i in range(55)]
    subs = {s: w.subject(s) for s in ids}
    train, test = ids[:40], ids[40:]
    return {"w": w, "subs": subs, "train": train, "test": test,
            "rest": {s: subs[s]["rest"] for s in ids}, "task": {s: subs[s]["task"] for s in ids},
            "masks": R.make_masks(w.spec.n_roi, 0.2, 4, seed=5, left=w.left)}


@pytest.fixture(scope="module")
def pos():
    d = _world(3, seed=21)
    d["fit"] = M.fit_mixture(M.windows_full(d["rest"], d["train"]), 3, d["train"], seed=1)
    return d


@pytest.fixture(scope="module")
def null():
    d = _world(1, seed=22)
    d["fit"] = M.fit_mixture(M.windows_full(d["rest"], d["train"]), 3, d["train"], seed=1, min_occupancy=0.0)
    return d


def _obs(msk, n):
    return np.setdiff1d(np.arange(n), msk)


def _nmse(d, fn):
    """피험자별 NMSE (창 · mask · ROI · frame 평균). fn(x_obs, obs, msk, k_true) → 예측."""
    n = d["w"].spec.n_roi
    per = {s: [] for s in d["test"]}
    for msk in d["masks"]:
        obs = _obs(msk, n)
        v = R.train_target_variance(d["task"], d["train"], obs, msk)
        for s in d["test"]:
            for win, k in zip(d["task"][s], d["subs"][s]["task_states"]):
                x, y = R.split_window(win, obs, msk)
                per[s].append(R.nmse_terms(y, fn(x, obs, msk, k), v).ravel())
    return np.array([np.mean(np.concatenate(v)) for v in per.values()])


# ---------------------------------------------------------------- 동일성

def test_weighted_lw_matches_sklearn_equal_weights():
    from sklearn.covariance import LedoitWolf

    X = np.random.default_rng(0).normal(size=(300, 40)) @ np.diag(np.linspace(0.5, 2, 40))
    C, a = M.weighted_lw(X, np.ones(len(X)), eig_floor=0.0)
    sk = LedoitWolf(assume_centered=True).fit(X)
    assert np.allclose(C, sk.covariance_, atol=1e-10) and a == pytest.approx(sk.shrinkage_, abs=1e-10)
    C2, _ = M.weighted_lw(X, np.full(len(X), 3.7), eig_floor=0.0)      # 가중치 배율 불변
    assert np.allclose(C, C2)


def test_k1_reduces_to_single_prior(pos):
    d = pos
    from sklearn.covariance import LedoitWolf

    Xw = M.windows_full(d["rest"], d["train"])
    f1 = M.fit_mixture(Xw, 1, d["train"])
    assert f1.status == "ok" and f1.covs.shape[0] == 1
    lw = LedoitWolf(assume_centered=True).fit(Xw.reshape(-1, Xw.shape[-1]))
    g1 = R.GaussPrior(mu=np.zeros(Xw.shape[-1]), cov=lw.covariance_, shrinkage=lw.shrinkage_, method="lw0")
    msk = d["masks"][0]
    obs = _obs(msk, d["w"].spec.n_roi)
    x, _ = R.split_window(d["task"][d["test"][0]][0], obs, msk)
    pa, wa = M.predict_adaptive(f1, x, obs, msk)
    assert np.allclose(wa, [1.0])
    assert np.allclose(M.predict_fixed(f1, x, obs, msk), pa)
    assert np.allclose(pa, g1.predict(x, obs, msk), atol=1e-8)


def test_component_order_invariance(pos):
    d = pos
    f = d["fit"]
    perm = np.array([2, 0, 1])
    g = M.MixFit(f.K, f.covs[perm], f.pis[perm], f.loglik, f.n_iter, f.converged, f.status, f.reason,
                 f.occupancy[perm], f.shrinkage[perm], f.fit_ids)
    msk = d["masks"][1]
    obs = _obs(msk, d["w"].spec.n_roi)
    x, _ = R.split_window(d["task"][d["test"][1]][2], obs, msk)
    pa, wa = M.predict_adaptive(f, x, obs, msk)
    pb, wb = M.predict_adaptive(g, x, obs, msk)
    assert np.allclose(pa, pb) and np.allclose(wa[perm], wb)
    assert np.allclose(M.predict_fixed(f, x, obs, msk), M.predict_fixed(g, x, obs, msk))


# ---------------------------------------------------------------- 불변성 · 정보 접근

def test_masked_and_outside_window_values_do_not_change_mix(pos):
    d = pos
    f = d["fit"]
    msk = d["masks"][2]
    obs = _obs(msk, d["w"].spec.n_roi)
    run = np.concatenate(d["task"][d["test"][2]])
    L = d["w"].spec.length
    start = 3 * L
    x0, y0 = R.split_window(R.window_from_run(run, start, L), obs, msk)
    run2 = run.copy()
    run2[start:start + L, msk] = 1e4                    # 가린 값
    run2[:start] *= 2.0                                 # 창 앞
    run2[start + L:] += 500.0                           # 창 뒤 (창 밖 미래)
    x1, y1 = R.split_window(R.window_from_run(run2, start, L), obs, msk)
    assert np.array_equal(x0, x1) and not np.allclose(y0, y1)
    pa0, w0 = M.predict_adaptive(f, x0, obs, msk)
    pa1, w1 = M.predict_adaptive(f, x1, obs, msk)
    assert np.array_equal(pa0, pa1) and np.array_equal(w0, w1)
    assert np.array_equal(M.predict_fixed(f, x0, obs, msk), M.predict_fixed(f, x1, obs, msk))


def test_fit_uses_train_only_and_takes_no_state_labels(pos):
    d = pos
    for fn in (M.fit_mixture, M.predict_fixed, M.predict_adaptive, M.adaptive_weights):
        params = set(inspect.signature(fn).parameters)
        assert not params & {"state", "states", "labels", "y", "target", "msk_values"}, fn.__name__
    rest2 = {s: [w.copy() for w in ws] for s, ws in d["rest"].items()}
    for s in d["test"]:
        rest2[s] = [w * 7.0 for w in rest2[s]]
    f2 = M.fit_mixture(M.windows_full(rest2, d["train"]), 3, d["train"], seed=1)
    assert np.array_equal(d["fit"].covs, f2.covs) and np.array_equal(d["fit"].pis, f2.pis)
    R.check_disjoint(d["fit"].fit_ids, d["test"])


# ---------------------------------------------------------------- 안정성 · 실패 처리

def test_components_spd_and_restart_log(pos):
    f = pos["fit"]
    assert f.status == "ok" and f.converged
    for c in f.covs:
        assert np.linalg.eigvalsh(c).min() > 0
    assert len(f.restarts) == 10 and np.isclose(f.pis.sum(), 1.0)


def test_spd_with_few_windows():
    d = _world(3, seed=23)
    Xw = M.windows_full(d["rest"], d["train"][:4])          # 창 32 개 · frame 480, p = 50
    f = M.fit_mixture(Xw, 2, d["train"][:4], seed=0, n_init=3, min_occupancy=0.0)
    if f.status == "ok":
        assert all(np.linalg.eigvalsh(c).min() > 0 for c in f.covs)
    else:
        assert f.status == "all_failed"


def test_sparse_component_and_collapse_flagged(null):
    d = null
    Xw = M.windows_full(d["rest"], d["train"])
    f = M.fit_mixture(Xw, 4, d["train"], seed=0, n_init=3, min_occupancy=0.3)   # 4 × 0.3 > 1 → 불가능
    assert f.status == "all_failed" and "sparse_component" in f.reason
    msk = d["masks"][0]
    obs = _obs(msk, d["w"].spec.n_roi)
    x, _ = R.split_window(d["task"][d["test"][0]][0], obs, msk)
    with pytest.raises(ValueError):
        M.predict_adaptive(f, x, obs, msk)
    with pytest.raises(ValueError):
        M.predict_fixed(f, x, obs, msk)


def test_not_converged_flagged(pos):
    d = pos
    f = M.fit_mixture(M.windows_full(d["rest"], d["train"]), 3, d["train"], seed=1, n_init=2, max_iter=1)
    assert f.status == "all_failed" and "not_converged" in f.reason


def test_numerical_failure_is_recorded_not_raised(pos):
    d = pos
    Xw = M.windows_full(d["rest"], d["train"]).copy()
    Xw[0, 0, 0] = np.nan
    f = M.fit_mixture(Xw, 2, d["train"], seed=0, n_init=2)
    assert f.status == "all_failed"


# ---------------------------------------------------------------- null · positive control

def test_null_no_spurious_state_gain(null):
    d = null
    g1 = R.fit_prior(R.stack_full(d["rest"], d["train"]), "lw", d["train"])
    f = d["fit"]
    assert f.status == "ok"
    e_g1 = _nmse(d, lambda x, o, m, k: g1.predict(x, o, m))
    e_a = _nmse(d, lambda x, o, m, k: M.predict_adaptive(f, x, o, m)[0])
    e_f = _nmse(d, lambda x, o, m, k: M.predict_fixed(f, x, o, m))
    ratio_a, ratio_f = e_a.mean() / e_g1.mean(), e_f.mean() / e_g1.mean()
    assert ratio_a > 0.99, ratio_a        # 상태가 없으면 1 % 넘는 개선이 나오지 않아야 한다
    assert ratio_a < 1.05 and ratio_f < 1.05


def test_positive_control_state_gain(pos):
    d = pos
    w = d["w"]
    g1 = R.fit_prior(R.stack_full(d["rest"], d["train"]), "lw", d["train"])
    f = d["fit"]
    e_g1 = _nmse(d, lambda x, o, m, k: g1.predict(x, o, m))
    e_a = _nmse(d, lambda x, o, m, k: M.predict_adaptive(f, x, o, m)[0])
    e_f = _nmse(d, lambda x, o, m, k: M.predict_fixed(f, x, o, m))
    e_or = _nmse(d, lambda x, o, m, k: x @ w.oracle_B(k, o, m).T)       # 참 상태 상한 (진단만)
    assert e_a.mean() < 0.9 * e_g1.mean()
    assert e_a.mean() < 0.9 * e_f.mean()
    assert e_or.mean() <= e_a.mean() * 1.02
    est, lo, hi = R.subject_bootstrap(R.delta(e_f, e_a), 2000, seed=3)
    assert lo > 0
