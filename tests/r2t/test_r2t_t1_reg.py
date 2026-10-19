"""R2T T1 F1 (결정 88) 시험 — 합성 자료만. F1 은 MIX 조건부 예측에 λ (BEST ridge 와 같은 격자) 를 inner 에서 고른다.

40 ROI 합성 (결정 87 시험과 같은 크기) 으로 정보 접근 · 동치 · 판정 성질만 확인한다. 성능 수치는 `eval_t1_worlds.py` 결과에 있다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import mix as M  # noqa: E402
import select_rules as SR  # noqa: E402
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg as F  # noqa: E402

CFG0 = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot.json")
CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg.json")


def test_config_is_approved_config_plus_lambda_only():
    a, b = dict(CFG0), dict(CFG)
    for k in ("schema", "decision", "status", "derived_from"):
        a.pop(k, None), b.pop(k, None)
    mb = dict(b.pop("mix"))
    assert mb.pop("cond_lambda_candidates") == [float(x.split("=")[1]) for x in CFG0["best_candidates"][2:]]
    mb.pop("selection_order")
    assert mb == a.pop("mix") and a == b


def test_lambda_zero_equals_original_mix():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=5)
    f = M.fit_mixture(t1.t1_windows(rest, ids[:10]), 3, ids[:10], seed=1, n_init=2)
    msk, obs = np.arange(24, 30), np.arange(24)
    x = task[ids[11]][0][:, obs]
    for tau in (0.0, 0.4, 1.0):
        assert np.allclose(F.make_mix_pred(f, 0.0, tau)(obs, msk)(x, obs, msk), M.predict_adaptive(f, x, obs, msk, tau)[0])
    assert np.allclose(F.make_mix_pred(f, 0.0, 0.0, "fixed")(obs, msk)(x, obs, msk), M.predict_fixed(f, x, obs, msk))
    assert np.allclose(F.make_pooled_pred(f, 0.0)(obs, msk)(x, obs, msk), SR.pooled_prior(f).predict(x, obs, msk))


def test_lambda_does_not_change_weights():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=6)
    f = M.fit_mixture(t1.t1_windows(rest, ids[:10]), 3, ids[:10], seed=1, n_init=2)
    msk, obs = np.arange(24, 30), np.arange(24)
    x = task[ids[11]][1][:, obs]
    w = M.adaptive_weights(f, x, obs, 0.5)
    for lam in (0.01, 1.0, 100.0):
        Bs = [F._coef(c, obs, msk, lam) for c in f.covs]
        assert np.allclose(F.make_mix_pred(f, lam, 0.5)(obs, msk)(x, obs, msk),
                           np.tensordot(w, np.stack([x @ B.T for B in Bs]), axes=1))


@pytest.fixture(scope="module")
def pos():
    ids, rest, task, left = ST.make(n_states=3, seed=51)
    return ids, rest, task, left, F.run_pipeline(rest, task, ids, CFG, left)


def test_fold_selection_ignores_that_folds_test_people(pos):
    ids, rest, task, left, res = pos
    f0 = res["folds"][0]
    test0 = set(f0["test"])
    rest2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in rest.items()}
    task2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in task.items()}
    masks = [np.array(m) for m in res["masks"]]
    r2 = F.run_fold(rest2, task2, sorted(set(ids) - test0), sorted(test0), masks, 40, CFG, 0)
    for k in ("best", "best_scores", "mix_pick", "mix_scores", "lam", "tau", "pis"):
        assert r2[k] == f0[k], k


def test_best_unchanged_from_approved_path(pos):
    ids, rest, task, left, res = pos
    old = t1.run_pipeline(rest, task, ids, CFG0, left)
    assert [f["best"] for f in old["folds"]] == [f["best"] for f in res["folds"]]
    assert old["per_subject_nmse"]["BEST"] == res["per_subject_nmse"]["BEST"]


def test_positive_and_null_40roi(pos):
    *_, res = pos
    assert res["delta_best_minus_mixa"][1] > 0
    ids, rest, task, left = ST.make(n_states=1, seed=52)
    r0 = F.run_pipeline(rest, task, ids, CFG, left)
    best_mean = np.mean(list(r0["per_subject_nmse"]["BEST"].values()))
    assert r0["delta_best_minus_mixa"][0] < 0.01 * best_mean
