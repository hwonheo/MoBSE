"""R2T 단계 0 시험 (결정 83) — 합성 자료만. 실제 자료를 읽지 않는다.

1. 누수: 가린 값 · run 의 창 밖 frame · test 피험자 자료 · test 정답이 입력 · 정규화 · 적합 · 분모로 새지 않는다.
2. 정확성: K=1 참 자료에서 G1 (LW · OAS) · ridge 가 oracle 조건부 예측에 가깝고 평균 예측보다 훨씬 낫다.
3. 수치 안정성 · 부호 · bootstrap · mask · 분할.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "r2t"))
import r2t_lib as R  # noqa: E402
import synth as S  # noqa: E402

L = 15


@pytest.fixture(scope="module")
def world():
    w = S.World(S.SynthSpec(seed=7))
    subs = {f"s{i:03d}": w.subject(f"s{i:03d}") for i in range(60)}
    ids = sorted(subs)
    train, test = ids[:45], ids[45:]
    rest = {s: subs[s]["rest"] for s in ids}
    task = {s: S.task_windows(subs[s]["run"], L) for s in ids}
    masks = R.make_masks(w.spec.n_roi, 0.2, 5, seed=11, left=w.left)
    return {"w": w, "subs": subs, "train": train, "test": test, "rest": rest, "task": task, "masks": masks}


def _fit_all(d, obs, msk, rest=None):
    rest = rest if rest is not None else d["rest"]
    frames = R.stack_full(rest, d["train"])
    g_lw = R.fit_prior(frames, "lw", d["train"])
    X, Y = R.stack_frames(rest, d["train"], obs, msk)
    rg = R.fit_ridge(X, Y, 1e-2, d["train"])
    return g_lw, rg


def _obs(msk, n):
    return np.setdiff1d(np.arange(n), msk)


# ---------------------------------------------------------------- 1. 누수

def test_masked_values_do_not_change_prediction(world):
    d = world
    msk = d["masks"][0]
    obs = _obs(msk, d["w"].spec.n_roi)
    g_lw, rg = _fit_all(d, obs, msk)
    win = d["task"][d["test"][0]][3].copy()
    x0, y0 = R.split_window(win, obs, msk)
    p0 = (g_lw.predict(x0, obs, msk), rg.predict(x0))
    bad = win.copy()
    bad[:, msk] = np.random.default_rng(1).normal(5000, 3000, size=bad[:, msk].shape)
    x1, y1 = R.split_window(bad, obs, msk)
    assert np.array_equal(x0, x1)
    assert np.array_equal(p0[0], g_lw.predict(x1, obs, msk))
    assert np.array_equal(p0[1], rg.predict(x1))
    assert not np.allclose(y0, y1)        # 정답은 바뀐다 — 정답만 가린 값을 본다


def test_outside_window_frames_do_not_change_prediction(world):
    d = world
    msk = d["masks"][1]
    obs = _obs(msk, d["w"].spec.n_roi)
    g_lw, rg = _fit_all(d, obs, msk)
    run = d["subs"][d["test"][1]]["run"].copy()
    start = 45
    x0, _ = R.split_window(R.window_from_run(run, start, L), obs, msk)
    run2 = run.copy()
    run2[:start] *= 3.0
    run2[start + L:] += 777.0
    x1, _ = R.split_window(R.window_from_run(run2, start, L), obs, msk)
    assert np.array_equal(x0, x1)
    assert np.array_equal(g_lw.predict(x0, obs, msk), g_lw.predict(x1, obs, msk))


def test_scaling_constant_uses_observed_only(world):
    d = world
    msk = d["masks"][0]
    obs = _obs(msk, d["w"].spec.n_roi)
    win = d["task"][d["test"][0]][0].copy()
    _, g0 = R.process_observed(win[:, obs])
    win[:, msk] *= 50.0
    _, g1 = R.process_observed(win[:, obs])
    assert g0 == g1


def test_overlap_of_observed_and_masked_rejected():
    with pytest.raises(R.LeakError):
        R.split_window(np.ones((L, 10)) * 100, np.arange(0, 6), np.arange(5, 10))


def test_denominator_ignores_test_targets(world):
    d = world
    msk = d["masks"][2]
    obs = _obs(msk, d["w"].spec.n_roi)
    v0 = R.train_target_variance(d["task"], d["train"], obs, msk)
    task2 = {s: [w.copy() for w in ws] for s, ws in d["task"].items()}
    for s in d["test"]:
        for w in task2[s]:
            w[:, msk] *= 25.0
    v1 = R.train_target_variance(task2, d["train"], obs, msk)
    assert np.array_equal(v0, v1)


def test_fit_ignores_test_subjects_and_records_ids(world):
    d = world
    msk = d["masks"][3]
    obs = _obs(msk, d["w"].spec.n_roi)
    g0, r0 = _fit_all(d, obs, msk)
    rest2 = {s: [w.copy() for w in ws] for s, ws in d["rest"].items()}
    for s in d["test"]:
        rest2[s] = [w * 9.0 + 100.0 for w in rest2[s]]
    g1, r1 = _fit_all(d, obs, msk, rest=rest2)
    assert np.array_equal(g0.cov, g1.cov) and np.array_equal(g0.mu, g1.mu)
    assert np.array_equal(r0.W, r1.W) and np.array_equal(r0.x_mean, r1.x_mean) and np.array_equal(r0.x_sd, r1.x_sd)
    R.check_disjoint(g0.fit_ids, d["test"])
    R.check_disjoint(r0.fit_ids, d["test"])
    with pytest.raises(R.LeakError):
        R.check_disjoint(d["train"], d["test"][:1] + d["train"][:1])


def test_inner_split_is_subject_disjoint():
    ids = [f"s{i}" for i in range(50)]
    tr, va = R.subject_split(ids, 0.2, seed=3)
    assert not set(tr) & set(va) and len(va) == 10 and sorted(tr + va) == sorted(ids)
    assert R.subject_split(ids, 0.2, seed=3) == (tr, va)


# ---------------------------------------------------------------- 2. 정확성

def _subject_nmse(d, model, obs, msk, v, kind):
    out = []
    for s in d["test"]:
        terms = []
        for win in d["task"][s]:
            x, y = R.split_window(win, obs, msk)
            if kind == "g1":
                p = model.predict(x, obs, msk)
            elif kind == "ridge":
                p = model.predict(x)
            elif kind == "oracle":
                p = x @ model.T
            else:
                p = np.zeros_like(y)
            terms.append(R.nmse_terms(y, p, v))
        out.append(np.mean(np.concatenate(terms)))
    return np.array(out)


def test_g1_and_ridge_near_oracle(world):
    d = world
    msk = d["masks"][0]
    obs = _obs(msk, d["w"].spec.n_roi)
    g_lw, rg = _fit_all(d, obs, msk)
    g_oas = R.fit_prior(R.stack_full(d["rest"], d["train"]), "oas", d["train"])
    v = R.train_target_variance(d["task"], d["train"], obs, msk)
    oracle = _subject_nmse(d, d["w"].oracle_B(obs, msk), obs, msk, v, "oracle").mean()
    zero = _subject_nmse(d, None, obs, msk, v, "zero").mean()
    for m, kind in ((g_lw, "g1"), (g_oas, "g1"), (rg, "ridge")):
        e = _subject_nmse(d, m, obs, msk, v, kind).mean()
        assert e < 1.05 * oracle, (kind, e, oracle)
    assert oracle < 0.6 * zero


# ---------------------------------------------------------------- 3. 안정성 · 부호 · bootstrap · mask

@pytest.mark.parametrize("n_frames", [30, 60, 120])
def test_shrinkage_cov_positive_definite_with_few_frames(n_frames):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(n_frames, 100))
    p = R.fit_prior(X, "lw", ["a"])
    ev = np.linalg.eigvalsh(p.cov)
    assert ev.min() > 0 and np.isfinite(np.linalg.cond(p.cov))
    msk = np.arange(80, 100)
    obs = np.arange(80)
    pred = p.predict(X[:5, obs], obs, msk)
    assert np.all(np.isfinite(pred))


def test_ridge_finite_at_small_lambda():
    rng = np.random.default_rng(1)
    X, Y = rng.normal(size=(40, 80)), rng.normal(size=(40, 20))
    m = R.fit_ridge(X, Y, 1e-6, ["a"])
    assert np.all(np.isfinite(m.predict(X)))


def test_nmse_terms_and_delta_sign():
    y = np.array([[1.0, 2.0], [3.0, 4.0]])
    p = np.array([[1.0, 1.0], [3.0, 2.0]])
    v = np.array([1.0, 2.0])
    assert np.allclose(R.nmse_terms(y, p, v), [[0.0, 0.5], [0.0, 2.0]])
    assert R.delta(0.5, 0.3) == pytest.approx(0.2)        # 양수 = 대상 (0.3) 이 낫다


def test_bootstrap_ci_behaviour():
    rng = np.random.default_rng(2)
    null = rng.normal(0, 0.05, 126)
    est, lo, hi = R.subject_bootstrap(null - null.mean(), 2000, seed=5)
    assert lo < 0 < hi
    est, lo, hi = R.subject_bootstrap(rng.normal(0.05, 0.02, 126), 2000, seed=5)
    assert lo > 0
    assert R.subject_bootstrap(null, 500, seed=9) == R.subject_bootstrap(null, 500, seed=9)


def test_masks_hemisphere_balanced_and_deterministic():
    left = np.zeros(100, bool)
    left[:50] = True
    ms = R.make_masks(100, 0.2, 20, seed=4, left=left)
    for m in ms:
        assert len(m) == 20 and left[m].sum() == 10 and len(set(m)) == 20
    assert all(np.array_equal(a, b) for a, b in zip(ms, R.make_masks(100, 0.2, 20, seed=4, left=left)))
