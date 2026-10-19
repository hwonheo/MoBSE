"""R2T T1 F3 (결정 88) 시험 — 합성 자료만. F3 = F2 + 가중치 단위 h (창 전체 · 5 · 3 · 1) 선택."""
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
import t1_reg as F1  # noqa: E402
import t1_reg3 as F3  # noqa: E402

CFG2 = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg2.json")
CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg3.json")


def test_config_is_f2_plus_weight_unit_only():
    a, b = dict(CFG2), dict(CFG)
    for k in ("schema", "status", "derived_from"):
        a.pop(k, None), b.pop(k, None)
    ma, mb = dict(a.pop("mix")), dict(b.pop("mix"))
    assert mb.pop("weight_unit_candidates") == ["window", 5, 3, 1]
    ma.pop("selection_order"), mb.pop("selection_order")
    assert ma == mb and a == b


def test_window_unit_equals_f2_weights_and_sums():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=5)
    f = M.fit_mixture(t1.t1_windows(rest, ids[:10]), 3, ids[:10], seed=1, n_init=2)
    msk, obs = np.arange(24, 30), np.arange(24)
    x = task[ids[11]][0][:, obs]
    for tau in (0.0, 0.4, 1.0):
        assert np.allclose(F3.make_mix_pred_h(f, 0.3, tau, F3.WINDOW)(obs, msk)(x, obs, msk),
                           F1.make_mix_pred(f, 0.3, tau)(obs, msk)(x, obs, msk))
    lf = np.random.default_rng(0).normal(size=(15, 3))
    assert np.allclose(F3._window_sum(lf, 1), lf)
    assert np.allclose(F3._window_sum(lf, 3)[5], lf[4:7].sum(0)) and np.allclose(F3._window_sum(lf, 5)[0], lf[0:3].sum(0))
    assert np.allclose(F3._window_sum(lf, 5)[14], lf[12:15].sum(0))      # 창 밖으로 넘지 않음


def test_frame_unit_uses_only_that_windows_observed_columns():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=6)
    f = M.fit_mixture(t1.t1_windows(rest, ids[:10]), 3, ids[:10], seed=1, n_init=2)
    msk, obs = np.arange(24, 30), np.arange(24)
    win = task[ids[11]][2].copy()
    p = F3.make_mix_pred_h(f, 0.3, 1.0, 3)(obs, msk)
    y0 = p(win[:, obs], obs, msk)
    win[:, msk] = 1e6                                                    # 가린 값을 바꿔도 예측 불변 (관측 열만 들어감)
    assert np.array_equal(y0, p(win[:, obs], obs, msk))


@pytest.fixture(scope="module")
def pos():
    ids, rest, task, left = ST.make(n_states=3, seed=51)
    return ids, rest, task, left, F3.run_pipeline(rest, task, ids, CFG, left)


def test_fold_selection_ignores_that_folds_test_people(pos):
    ids, rest, task, left, res = pos
    f0 = res["folds"][0]
    test0 = set(f0["test"])
    rest2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in rest.items()}
    task2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in task.items()}
    masks = [np.array(m) for m in res["masks"]]
    r2 = F3.run_fold(rest2, task2, sorted(set(ids) - test0), sorted(test0), masks, 40, CFG, 0)
    for k in ("best", "best_scores", "mix_pick", "mix_scores", "em_a", "lam", "tau", "h", "pis"):
        assert r2[k] == f0[k], k


def test_best_unchanged_and_run_fold_restored(pos):
    ids, rest, task, left, res = pos
    assert F1.run_fold.__module__ == "t1_reg"
    old = t1.run_pipeline(rest, task, ids, t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot.json"), left)
    assert old["per_subject_nmse"]["BEST"] == res["per_subject_nmse"]["BEST"]
    assert res["delta_best_minus_mixa"][1] > 0


# ---------------------------------------------------------------- 실패 처리 (사전 기록 14 절)

def test_all_fail_falls_back_to_best_and_keeps_all_people():
    import copy
    ids, rest, task, left = ST.make(n_states=3, seed=53)
    cfg = copy.deepcopy(CFG)
    cfg["mix"]["min_occupancy"] = 0.5                 # K=3 에서 불가능 — 모든 fold 실패 (설정 파일은 그대로)
    res = F3.run_pipeline(rest, task, ids, cfg, left)
    assert res["n_subjects"] == 31 and res["n_fallback_subjects"] == 31 and res["mix_fail_folds"] == 5
    assert res["per_subject_nmse"]["F3"] == res["per_subject_nmse"]["BEST"]
    assert res["delta_best_minus_f3_all"] == (0.0, 0.0, 0.0) and res["delta_best_minus_mixa_okfolds_reference"] is None
    assert "MIX-a" not in res["per_subject_nmse"]
    assert any("혼합 실패 fold 5/5 → BEST fallback" in f for f in res["verdict"]["flags"])


def test_primary_delta_uses_all_people(pos):
    ids, rest, task, left, res = pos
    per = res["per_subject_nmse"]
    assert len(per["F3"]) == len(per["BEST"]) == 31
    d = np.array([per["BEST"][s] - per["F3"][s] for s in sorted(ids)])
    assert res["delta_best_minus_f3_all"][0] == pytest.approx(d.mean())
