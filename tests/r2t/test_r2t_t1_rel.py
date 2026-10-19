"""R2T T1 신뢰성 보완판 F4R 시험 — 합성 자료만. 사전 규칙: `docs/experiments/r2t_t1_reliability_2026-10-17.md` 0 절.

* F4 와 같은 알고리즘 (실패가 없으면 선택 · 사람별 점수 동일)
* 실패 분류 · 처리: R3 정상 실패 → fallback, R4 수치 실패 → 중단, R5 경고, 비유한 · 비 SPD 분류
* 기록 왕복: 저장 예측 + 재생성 정답 → 사람별 NMSE · Δ (평균 · SD · CI) 일치, 변조 검출
* 누출: fold test 사람 자료를 바꿔도 그 fold 의 inner 점수 · 선택 불변
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import mix as M  # noqa: E402
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg4 as F4  # noqa: E402
import t1_rel as T  # noqa: E402

CFG4 = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg4.json")
CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_rel.json")


def small(seed=61, n_states=3):
    return ST.make(n_subjects=15, n_roi=20, n_states=n_states, seed=seed)


def cfg_light(**rel):
    c = copy.deepcopy(CFG)
    c["reliability"].update(rel)
    return c


def test_config_is_f4_plus_reliability_only():
    a, b = dict(CFG4), dict(CFG)
    for k in ("schema", "status", "derived_from"):
        a.pop(k, None), b.pop(k, None)
    assert b.pop("reliability")["rules_doc"].endswith("§0")
    bt = b.pop("best_tuned")
    assert len(bt["ridge_lambda"]) == 13 and len(bt["g1_shrink"]) * len(bt["g1_cond_lambda"]) == 30
    assert a == b
    assert len(T.tuned_best_candidates(CFG)) == 43


# ---------------------------------------------------------------- F4 와 같은 알고리즘

def test_equivalent_to_f4_when_no_failures():
    ids, rest, task, left = ST.make(n_states=3, seed=51)                  # 40 ROI · 31 명 (결정 87 시험 세계)
    c = cfg_light(keep_predictions=False, selection_audit=False, best_tuned=False)
    r4 = F4.run_pipeline(rest, task, ids, CFG4, left)
    rr = T.run_pipeline(rest, task, ids, c, left)
    assert r4["per_subject_nmse"]["BEST"] == rr["per_subject_nmse"]["BEST"]
    assert r4["per_subject_nmse"]["F3"] == rr["per_subject_nmse"]["F4R"]
    assert [f["mix_pick"] for f in r4["folds"]] == [f["F4R"]["pick"] for f in rr["folds"]]
    assert all(f["F4R"]["fold_status"] == "ok" for f in rr["folds"])
    assert rr["deltas"]["BEST − F4R (31 명, 주지표)"]["ci"] == list(r4["delta_best_minus_f3_all"])


# ---------------------------------------------------------------- 실패 분류 · 처리

def test_finite_spd_check_classifies():
    good = M.MixFit(2, np.stack([np.eye(3), np.eye(3)]), np.array([.5, .5]), -1.0, 1, True, "ok", "", np.array([.5, .5]), np.zeros(2))
    assert T.fit_is_finite_spd(good) is None
    bad = copy.deepcopy(good)
    bad.covs[1] = np.diag([1.0, 1.0, -0.1])
    assert "비 SPD" in T.fit_is_finite_spd(bad)
    nanf = copy.deepcopy(good)
    nanf.loglik = float("nan")
    assert "비유한" in T.fit_is_finite_spd(nanf)


def test_normal_failure_falls_back_with_all_people(tmp_path):
    ids, rest, task, left = small()
    c = cfg_light(selection_audit=False)
    c["mix"]["min_occupancy"] = 0.5                                       # K=3 에서 불가능 — 정상 실패 (sparse_component)
    r = T.run_pipeline(rest, task, ids, c, left)
    assert r["verdict"]["fold_status"] == ["fallback"] * 5 and not r["verdict"]["stop"]
    assert any("R3" in f for f in r["verdict"]["flags"])
    for f in r["folds"]:
        for fr in f["F4R"]["inner_fits"].values():
            assert fr["status"] == "failed" and set(fr["counts"]) == {"sparse_component"} and fr["numeric_failures"] == 0
    d = r["deltas"]["BEST − F4R (31 명, 주지표)"]
    assert d["n"] == 15 and d["mean"] == 0.0 and d["sd"] == 0.0 and r["n_fallback_subjects"] == 15
    assert "BEST − F4R (성공 fold 한정, 참고)" not in r["deltas"]


def test_numerical_failure_stops_instead_of_fallback(monkeypatch):
    ids, rest, task, left = small()

    def boom(*a, **k):
        raise np.linalg.LinAlgError("주입: 비 SPD")
    monkeypatch.setattr(F4, "_m", boom)
    r = T.run_pipeline(rest, task, ids, cfg_light(selection_audit=False), left)
    assert r["verdict"]["fold_status"] == ["stop_numerical"] * 5 and r["verdict"]["stop"]
    assert any("R4" in f for f in r["verdict"]["flags"])
    fr = r["folds"][0]["F4R"]["inner_fits"]["LW"]
    assert fr["counts"] == {"numerical": 10} and "주입: 비 SPD" in fr["restarts"][0]["reason"]
    assert "F4R" not in r["per_subject_nmse"] and "BEST − F4R (31 명, 주지표)" not in r["deltas"]
    assert len(r["per_subject_nmse"]["BEST"]) == 15                       # BEST · 기록은 남는다


def test_numerical_restart_warning_keeps_verdict(monkeypatch):
    ids, rest, task, left = small()
    orig = F4._one_run4

    def first_restart_numerical(Xw, K, seed, *a):
        if seed == CFG["mix"]["em_seed"]:
            return M.MixFit(K, np.empty((0,)), np.empty((0,)), -np.inf, 0, False, "numerical", "LinAlgError('주입')",
                            np.empty((0,)), np.empty((0,)))
        return orig(Xw, K, seed, *a)
    monkeypatch.setattr(F4, "_one_run4", first_restart_numerical)
    r = T.run_pipeline(rest, task, ids, cfg_light(selection_audit=False), left)
    assert not r["verdict"]["stop"] and any("R5" in f for f in r["verdict"]["flags"])
    st = r["verdict"]["fold_status"]
    assert "stop_numerical" not in st


def test_nonfinite_ok_restart_is_reclassified(monkeypatch):
    ids, rest, task, left = small()
    orig = F4._one_run4

    def nan_ok(Xw, K, seed, *a):
        f = orig(Xw, K, seed, *a)
        if f.status == "ok":
            f.loglik = float("nan")
        return f
    monkeypatch.setattr(F4, "_one_run4", nan_ok)
    r = T.run_pipeline(rest, task, ids, cfg_light(selection_audit=False), left)
    fr = r["folds"][0]["F4R"]["inner_fits"]["LW"]
    assert fr["status"] == "failed" and "nonfinite" in fr["counts"] and fr["numeric_failures"] > 0
    assert set(r["verdict"]["fold_status"]) == {"stop_numerical"} and r["verdict"]["stop"]


def test_nonfinite_input_stops():
    ids, rest, task, left = small()
    task[ids[2]][1][3, 4] = np.nan
    r = T.run_pipeline(rest, task, ids, CFG, left)
    assert r["verdict"]["stop"] and r["verdict"]["flags"] == ["중단: 비유한 입력"]


# ---------------------------------------------------------------- 기록 왕복 · 누출

@pytest.fixture(scope="module")
def full():
    ids, rest, task, left = small()
    return ids, rest, task, left, T.run_pipeline(rest, task, ids, CFG, left)


def test_roundtrip_recomputes_saved_scores_and_detects_tampering(full, tmp_path):
    ids, rest, task, left, res = full
    spec = {"generator": "synth_t1.make", "n_subjects": 15, "n_roi": 20, "n_states": 3, "seed": 61}
    T.save_run(tmp_path / "run", res, spec, CFG)
    with pytest.raises(FileExistsError):
        T.save_run(tmp_path / "run", res, spec, CFG)
    doc, arr = T.load_run(tmp_path / "run")
    _, _, task2, _ = small()                                              # 정답은 생성기 + seed 로 재생성
    chk = T.verify_roundtrip(doc, arr, task2, 20)
    assert chk["problems"] == [] and chk["n_subject_scores_rechecked"] == 15 * 3
    assert doc["deltas"]["BEST − F4R (31 명, 주지표)"]["sd"] is not None
    assert set(doc["code_sha256"]) == set(T.CODE_FILES) and doc["spec"] == spec
    bad = json.loads(json.dumps(doc))
    s0 = bad["folds"][0]["test"][0]
    bad["folds"][0]["nmse"]["F4R"][0] += 1e-9
    bad["per_subject_nmse"]["F4R"][s0] += 1e-9
    assert T.verify_roundtrip(bad, arr, task2, 20)["problems"]
    bad2 = json.loads(json.dumps(doc))
    bad2["deltas"]["BEST − F4R (31 명, 주지표)"]["sd"] += 1e-6
    assert any("Δ 재계산" in p for p in T.verify_roundtrip(bad2, arr, task2, 20)["problems"])


def test_selection_records_ignore_that_folds_test_people(full):
    ids, rest, task, left, res = full
    f0 = res["folds"][0]
    test0 = set(f0["test"])
    rest2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in rest.items()}
    task2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in task.items()}
    masks = [np.array(m) for m in res["masks"]]
    r2 = T.run_fold(rest2, task2, sorted(set(ids) - test0), sorted(test0), masks, 20, CFG, 0)
    for lab in ("BEST", "BEST-T"):
        assert r2[lab]["pick"] == f0[lab]["pick"] and r2[lab]["inner_scores"] == f0[lab]["inner_scores"]
    for k in ("pick", "inner_scores", "inner_fits", "tau_ess", "em_a", "lam", "tau", "h"):
        assert r2["F4R"][k] == f0["F4R"][k], k


def test_partition_and_denominator(full):
    ids, rest, task, left, res = full
    tests = [s for f in res["folds"] for s in f["test"]]
    assert sorted(tests) == sorted(ids) and len(set(tests)) == 15
    for f in res["folds"]:
        assert not set(f["inner_train"]) & set(f["test"]) and sorted(f["inner_train"] + f["inner_val"]) == f["train"]
    for m in ("BEST", "BEST-T", "F4R"):
        assert len(res["per_subject_nmse"][m]) == 15
    v0 = t1.t1_target_variance(task, res["folds"][0]["train"], np.arange(4, 20), np.arange(4))
    task_bump = {s: [w * (9.0 if s in res["folds"][0]["test"] else 1.0) for w in ws] for s, ws in task.items()}
    assert np.array_equal(v0, t1.t1_target_variance(task_bump, res["folds"][0]["train"], np.arange(4, 20), np.arange(4)))


def test_selection_audit_fields(full):
    *_, res = full
    for fa in res["selection_audit"]:
        for lab, a in fa.items():
            if a is None:
                continue
            assert a["regret"] >= 0 and a["n_candidates"] == {"BEST": 7, "BEST-T": 43}.get(lab, a["n_candidates"])
            assert np.isclose(a["optimism"], a["test_score_of_pick"] - a["inner_score_of_pick"])
