"""R2T T1 F4 (결정 88) 시험 — 합성 자료만. F4 = F3 + EM 초기화 (주성분 20 특징 k-means++, 최종 점유율만 검사)."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg4 as F4  # noqa: E402

CFG3 = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg3.json")
CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg4.json")


def test_config_is_f3_plus_init_only():
    a, b = dict(CFG3), dict(CFG)
    for k in ("schema", "status", "derived_from"):
        a.pop(k, None), b.pop(k, None)
    ma, mb = dict(a.pop("mix")), dict(b.pop("mix"))
    assert mb.pop("init")["n_pc"] == F4.N_PC == 20
    assert ma == mb and a == b


def test_pca_init_is_hard_assignment_and_deterministic():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=5)
    Xw = t1.t1_windows(rest, ids)
    r1, r2 = F4.init_resp_pca(Xw, 3, 7), F4.init_resp_pca(Xw, 3, 7)
    assert np.array_equal(r1, r2) and np.all(r1.sum(1) == 1) and r1.shape == (len(Xw), 3)


def test_final_occupancy_rule_still_fails_impossible_requirement():
    ids, rest, task, left = ST.make(n_subjects=12, n_roi=30, n_states=3, seed=5)
    f = F4.fit_mixture4(t1.t1_windows(rest, ids), 3, ids, None, seed=1, n_init=2, min_occupancy=0.5)
    assert f.status == "all_failed" and "sparse_component" in f.reason


@pytest.fixture(scope="module")
def pos():
    ids, rest, task, left = ST.make(n_states=3, seed=51)
    return ids, rest, task, left, F4.run_pipeline(rest, task, ids, CFG, left)


def test_fold_selection_ignores_that_folds_test_people(pos):
    ids, rest, task, left, res = pos
    f0 = res["folds"][0]
    test0 = set(f0["test"])
    rest2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in rest.items()}
    task2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in task.items()}
    masks = [np.array(m) for m in res["masks"]]
    r2 = F4.run_fold(rest2, task2, sorted(set(ids) - test0), sorted(test0), masks, 40, CFG, 0)
    for k in ("best", "best_scores", "mix_pick", "mix_scores", "em_a", "lam", "tau", "h", "pis"):
        assert r2[k] == f0[k], k


def test_best_unchanged_all_people_and_fallback(pos):
    ids, rest, task, left, res = pos
    old = t1.run_pipeline(rest, task, ids, t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot.json"), left)
    assert old["per_subject_nmse"]["BEST"] == res["per_subject_nmse"]["BEST"]
    assert len(res["per_subject_nmse"]["F3"]) == 31 and res["delta_best_minus_f3_all"][1] > 0
    ids2, rest2, task2, left2 = ST.make(n_states=3, seed=53)
    cfg = copy.deepcopy(CFG)
    cfg["mix"]["min_occupancy"] = 0.5
    r = F4.run_pipeline(rest2, task2, ids2, cfg, left2)
    assert r["n_fallback_subjects"] == 31 and r["delta_best_minus_f3_all"] == (0.0, 0.0, 0.0)


def test_inner_and_test_people_disjoint_and_each_person_tested_once(pos):
    ids, rest, task, left, res = pos
    tests = [s for f in res["folds"] for s in f["test"]]
    assert sorted(tests) == sorted(ids) and len(set(tests)) == 31
    for f in res["folds"]:
        assert not set(f["inner_train"]) & set(f["test"]) and not set(f["inner_val"]) & set(f["test"])
        assert not set(f["inner_train"]) & set(f["inner_val"])
        assert sorted(f["inner_train"] + f["inner_val"]) == sorted(f["train"])
        assert sorted(f["train"] + f["test"]) == sorted(ids)
