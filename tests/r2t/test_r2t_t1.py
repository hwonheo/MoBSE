"""R2T T1 경로 시험 (결정 87) — 합성 자료 + 로컬 메타데이터 (설계 문서 · atlas tsv · manifest · npy 헤더) 만. 실제 BOLD 값은 읽지 않는다.

설정은 `configs/r2t/t1_pilot.json` 그대로 쓰되, 합성 속도를 위해 ROI 수만 40 으로 줄인다 (mask 비율 · 개수 · seed · K · τ 후보 ·
BEST 후보 · EM 규칙 · bootstrap 은 같다).
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import r2t_lib as R  # noqa: E402
import select_rules as SR  # noqa: E402
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402

CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot.json")


@pytest.fixture(scope="module")
def pos():
    ids, rest, task, left = ST.make(n_states=3, seed=51)
    return ids, rest, task, left, t1.run_pipeline(rest, task, ids, CFG, left)


@pytest.fixture(scope="module")
def null():
    ids, rest, task, left = ST.make(n_states=1, seed=52)
    return ids, rest, task, left, t1.run_pipeline(rest, task, ids, CFG, left)


# ---------------------------------------------------------------- 설정 · 문서 대조

def test_config_matches_pilot_design_doc():
    doc = (ROOT / CFG["design_doc"]).read_text()
    for seed in (CFG["split"]["fold_seed"], CFG["split"]["inner_seed"], CFG["mask"]["seed"], CFG["bootstrap"]["seed"]):
        assert str(seed) in doc, seed
    assert "pilot 31 명" in doc and CFG["subjects"]["expected_n"] == 31 and "20260917" in doc
    assert "5 fold" in doc and CFG["split"]["n_folds"] == 5
    assert "15 frame" in doc and CFG["window"]["length"] == 15
    assert "20 %" in doc and CFG["mask"]["frac"] == 0.2
    assert "M = 10" in doc and CFG["mask"]["n_masks"] == 10
    assert "K = 3" in doc and CFG["mix"]["K"] == 3
    assert "{0, τ_ESS, 1}" in doc and CFG["mix"]["tau_candidates"] == ["0", "ess", "1"]
    lams = re.search(r"λ ∈ \{([^}]*)\}", doc).group(1)
    assert [float(x) for x in lams.split(",")] == [float(b.split("=")[1]) for b in CFG["best_candidates"][2:]]
    assert "10,000" in doc and CFG["bootstrap"]["n"] == 10000
    assert "1e-4" in doc and CFG["selection"]["tie"] == 1e-4
    assert "5 %" in doc and CFG["mix"]["min_occupancy"] == 0.05
    assert "1e-6 · 500" in doc and CFG["mix"]["tol"] == 1e-6 and CFG["mix"]["max_iter"] == 500
    assert "NMSE 0.01" in doc and CFG["delta_report_only"] == 0.01


def test_left_hemisphere_from_local_atlas_tsv():
    p = ROOT / CFG["data"]["atlas_tsv"]
    if not p.is_file():
        pytest.skip("로컬 atlas tsv 없음")
    left = t1.left_from_atlas_tsv(p)
    assert len(left) == 100 and left.sum() == 50 and left[:50].all() and not left[50:].any()


def test_person_folds_31():
    ids = [f"x{i}" for i in range(31)]
    folds = t1.person_folds(ids, 5, CFG["split"]["fold_seed"])
    assert sorted(len(f) for f in folds) == [6, 6, 6, 6, 7]
    flat = [s for f in folds for s in f]
    assert sorted(flat) == sorted(ids) and len(set(flat)) == 31
    assert folds == t1.person_folds(list(reversed(ids)), 5, CFG["split"]["fold_seed"])


# ---------------------------------------------------------------- T1 처리 · 누수

def test_t1_masked_values_do_not_reach_inputs():
    win = np.random.default_rng(0).normal(size=(15, 20))
    msk, obs = np.arange(16, 20), np.arange(16)
    x0, y0 = t1.t1_split(win, obs, msk)
    win[:, msk] = 1e6
    x1, y1 = t1.t1_split(win, obs, msk)
    assert np.array_equal(x0, x1) and not np.allclose(y0, y1)
    with pytest.raises(R.LeakError):
        t1.t1_split(win, np.arange(17), msk)


def test_t1_denominator_train_only(pos):
    ids, rest, task, left, _ = pos
    train, test = ids[:25], ids[25:]
    msk = np.arange(30, 38)
    obs = np.setdiff1d(np.arange(40), msk)
    v0 = t1.t1_target_variance(task, train, obs, msk)
    task2 = {s: [w * (9.0 if s in test else 1.0) for w in ws] for s, ws in task.items()}
    assert np.array_equal(v0, t1.t1_target_variance(task2, train, obs, msk))


def test_fold_selection_and_fit_ignore_that_folds_test_people(pos):
    ids, rest, task, left, res = pos
    f0 = res["folds"][0]
    test0 = set(f0["test"])
    rest2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in rest.items()}
    task2 = {s: [w * 4.0 + 1.0 for w in ws] if s in test0 else ws for s, ws in task.items()}
    masks = [np.array(m) for m in res["masks"]]
    train = sorted(set(ids) - test0)
    r2 = t1.run_fold(rest2, task2, train, sorted(test0), masks, 40, CFG, 0)
    for k in ("best", "best_scores", "tau_scores", "tau", "pis", "inner_train", "inner_val"):
        assert r2[k] == f0[k], k


# ---------------------------------------------------------------- 전체 파이프라인

def test_pipeline_positive_full(pos):
    ids, _, _, _, res = pos
    assert res["n_subjects"] == 31 and res["n_ok_subjects"] == 31
    tests = [s for f in res["folds"] for s in f["test"]]
    assert sorted(tests) == sorted(ids) and len(set(tests)) == 31
    for f in res["folds"]:
        assert f["mix"] == "ok" and f["best"] in CFG["best_candidates"] and f["tau_label"] in ("0", "ess", "1")
        assert not set(f["inner_val"]) & set(f["test"]) and not set(f["inner_train"]) & set(f["test"])
    assert all(len(v) == 31 for v in res["per_subject_nmse"].values())
    est, lo, hi = res["delta_best_minus_mixa"]
    assert lo > 0                                          # 양수 = MIX-a 가 BEST 보다 나음 (부호 통일)
    assert not res["verdict"]["stop"] and res["verdict"]["next"].startswith("기술값 보고")
    assert len(res["masks"]) == 10 and all(len(m) == 8 for m in res["masks"])


def test_pipeline_null_no_spurious_gain(null):
    *_, res = null
    est, lo, hi = res["delta_best_minus_mixa"]
    best_mean = np.mean(list(res["per_subject_nmse"]["BEST"].values()))
    assert est < 0.01 * best_mean
    assert not res["verdict"]["stop"]


def test_pipeline_deterministic(pos):
    ids, rest, task, left, res = pos
    again = t1.run_pipeline(rest, task, ids, CFG, left)
    assert again["delta_best_minus_mixa"] == res["delta_best_minus_mixa"]
    assert again["per_subject_nmse"] == res["per_subject_nmse"]


# ---------------------------------------------------------------- 실패 · 중단

def test_mix_failure_stops_without_substitution():
    ids, rest, task, left = ST.make(n_states=3, seed=53)
    cfg = copy.deepcopy(CFG)
    cfg["mix"]["min_occupancy"] = 0.5            # K=3 에서 불가능 — 실패 경로 시험용 (설정 파일은 그대로)
    res = t1.run_pipeline(rest, task, ids, cfg, left)
    assert res["verdict"]["stop"] and any("혼합 실패 fold 5/5" in f for f in res["verdict"]["flags"])
    assert "MIX-a" not in res["per_subject_nmse"] and "BEST" in res["per_subject_nmse"]
    assert res["delta_best_minus_mixa"] is None


def test_nonfinite_input_stops_before_selection():
    ids, rest, task, left = ST.make(n_states=3, seed=54)
    task[ids[3]][2][4, 7] = np.nan
    res = t1.run_pipeline(rest, task, ids, CFG, left)
    assert res["verdict"]["stop"] and res["verdict"]["flags"] == ["중단: 비유한 입력"]


def test_verdict_rules():
    ok = {"mix": "ok", "tau": 0.0}
    v = t1.verdict([ok] * 5, (-0.02, -0.03, -0.001), False, CFG)
    assert "K>1 경로 중단 권고: Δ 상한 < 0" in v["flags"] and "적응 경로 중단 권고: 모든 fold τ̂ = 0" in v["flags"]
    assert not v["stop"]
    v = t1.verdict([ok, ok, ok, {"mix": "실패"}, {"mix": "실패"}], (0.01, 0.0, 0.02), False, CFG)
    assert v["stop"] and v["mix_fail_folds"] == 2
    v = t1.verdict([ok] * 4 + [{"mix": "실패"}], (0.01, 0.002, 0.02), False, CFG)
    assert not v["stop"] and v["mix_fail_folds"] == 1


def test_tau_ess_t1_demeans_windows():
    rng = np.random.default_rng(3)
    Xw = rng.normal(size=(200, 15, 10)) + rng.normal(0, 3, size=(200, 1, 10))   # 창 평균만 큰 백색 잡음
    assert SR.rho_hat(Xw) > 0.5                       # 평균을 안 빼면 자기상관이 높게 나옴
    assert abs(t1.rho_hat_t1(Xw)) < 0.15 and 0.75 < t1.tau_ess_t1(Xw) <= 1.0


# ---------------------------------------------------------------- 실제 자료 보호 · 사전 점검 (헤더만)

def test_load_real_refuses_without_approval():
    with pytest.raises(PermissionError):
        t1.load_real(CFG, ROOT)


def test_preflight_metadata_and_headers_only():
    if not (ROOT / CFG["subjects"]["source"]).is_file():
        pytest.skip("로컬 분할 파일 없음")
    pf = t1.preflight(CFG, ROOT)
    assert pf["values_read"] is False and pf["n_subjects"] == 31
    assert pf["problems"] == [], pf["problems"][:3]
    assert pf["task_shapes"] == ["((135, 100), 'float32')"] and pf["rest_shapes"] == ["((30, 100), 'float32')"]
    assert pf["atlas_lh"] == 50 and pf["atlas_n"] == 100
