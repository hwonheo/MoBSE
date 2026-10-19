"""R2T T1 F2 (결정 88) 시험 — 합성 자료만. F2 = F1 + EM shrinkage 후보 (LW · 0.091 · 0.5 · 0.909) 를 inner 에서 선택."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import mix as M  # noqa: E402
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg2 as F2  # noqa: E402

CFG1 = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg.json")
CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg2.json")


def test_config_is_f1_plus_em_shrink_only():
    a, b = dict(CFG1), dict(CFG)
    for k in ("schema", "status", "derived_from"):
        a.pop(k, None), b.pop(k, None)
    ma, mb = dict(a.pop("mix")), dict(b.pop("mix"))
    assert mb.pop("em_shrink_candidates") == pytest.approx([0.1 / 1.1, 0.5, 10 / 11], abs=1e-6)
    ma.pop("selection_order"), mb.pop("selection_order")
    assert ma == mb and a == b


def test_a_none_is_original_mix_and_fixed_a_is_shrunk():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=5)
    Xw = t1.t1_windows(rest, ids[:10])
    kw = dict(seed=1, n_init=2)
    f0, g0 = F2.fit_mixture_a(Xw, 3, ids[:10], None, **kw), M.fit_mixture(Xw, 3, ids[:10], **kw)
    assert np.array_equal(f0.covs, g0.covs) and np.array_equal(f0.pis, g0.pis)
    f = F2.fit_mixture_a(Xw, 3, ids[:10], 0.5, **kw)
    assert f.status == "ok" and np.allclose(f.shrinkage, 0.5)
    for c in f.covs:                                   # a m I + (1 − a) S 이면 최소 고유값 ≥ a m
        assert np.linalg.eigvalsh(c).min() >= 0.5 * np.trace(c) / 30 * (1 - 1e-9)


@pytest.fixture(scope="module")
def pos():
    ids, rest, task, left = ST.make(n_states=3, seed=51)
    return ids, rest, task, left, F2.run_pipeline(rest, task, ids, CFG, left)


def test_fold_selection_ignores_that_folds_test_people(pos):
    ids, rest, task, left, res = pos
    f0 = res["folds"][0]
    test0 = set(f0["test"])
    rest2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in rest.items()}
    task2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in task.items()}
    masks = [np.array(m) for m in res["masks"]]
    r2 = F2.run_fold(rest2, task2, sorted(set(ids) - test0), sorted(test0), masks, 40, CFG, 0)
    for k in ("best", "best_scores", "mix_pick", "mix_scores", "em_a", "lam", "tau", "pis"):
        assert r2[k] == f0[k], k


def test_best_unchanged_and_run_fold_restored(pos):
    import t1_reg as F1
    ids, rest, task, left, res = pos
    assert F1.run_fold.__module__ == "t1_reg"         # F2 가 잠시 바꾼 함수를 되돌렸는지
    old = t1.run_pipeline(rest, task, ids, t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot.json"), left)
    assert old["per_subject_nmse"]["BEST"] == res["per_subject_nmse"]["BEST"]
    assert res["delta_best_minus_mixa"][1] > 0
