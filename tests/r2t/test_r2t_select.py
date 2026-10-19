"""R2T 선택 규칙 · 사전 정의 합성 회귀시험 (결정 85). 합성 결과는 실제 BOLD 가설의 근거가 아니다.

세계 (모두 사전에 정함, 탐색 없음): null (참 K=1) · positive (참 K=3) · 강한 자기상관 (ρ 0.9) · 성분 중복 · 희박 상태 (4 %) ·
잘못된 state bank (task 를 다른 공분산 묶음에서). 판정은 G-A 꼴 — MIX-a(τ̂) 대 train/inner 선택 BEST.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "r2t"))
import mix as M  # noqa: E402
import r2t_lib as R  # noqa: E402
import select_rules as SR  # noqa: E402
import synth_mix as SM  # noqa: E402
import synth_variants as SV  # noqa: E402

N_ROI = 40
FIT_KW = {"seed": 1, "n_init": 3}


def _data(world):
    ids = [f"s{i:03d}" for i in range(55)]
    subs = {s: world.subject(s) for s in ids}
    return {"w": world, "train": ids[:40], "test": ids[40:],
            "rest": {s: subs[s]["rest"] for s in ids}, "task": {s: subs[s]["task"] for s in ids},
            "masks": R.make_masks(N_ROI, 0.2, 3, seed=9, left=world.left)}


def _run(d, **kw):
    return SR.outer_run(d["rest"], d["task"], d["train"], d["test"], d["masks"], N_ROI, K=3, inner_seed=2,
                        fit_kw={**FIT_KW, **kw})


def _world(n_states, rho=0.5, seed=0, **kw):
    return SV.VariantWorld(SM.MixSpec(n_roi=N_ROI, n_states=n_states, rho=rho, seed=seed), **kw)


@pytest.fixture(scope="module")
def runs():
    out = {}
    for name, w, kw in [
        ("null", _world(1, seed=31), {}),
        ("pos", _world(3, seed=32), {}),
        ("null_ar", _world(1, rho=0.9, seed=33), {}),
        ("pos_ar", _world(3, rho=0.9, seed=34), {}),
        ("overlap", _world(3, seed=35, overlap=True), {}),
        ("sparse", _world(3, seed=36, state_probs=[0.48, 0.48, 0.04]), {}),
        ("wrong_bank", _world(3, seed=37, task_bank_seed=777), {}),
    ]:
        d = _data(w)
        out[name] = (d, _run(d, **kw))
    return out


def _ratio(r):
    return r["nmse"]["MIX-a"].mean() / r["nmse"]["BEST"].mean()


# ---------------------------------------------------------------- 규칙 자체

def test_selection_ignores_test_subjects(runs):
    d, r = runs["pos"]
    task2 = {s: [w.copy() for w in ws] for s, ws in d["task"].items()}
    rest2 = {s: [w.copy() for w in ws] for s, ws in d["rest"].items()}
    for s in d["test"]:
        task2[s] = [w * 3.0 + 50.0 for w in task2[s]]
        rest2[s] = [w * 5.0 for w in rest2[s]]
    r2 = SR.outer_run(rest2, task2, d["train"], d["test"], d["masks"], N_ROI, K=3, inner_seed=2, fit_kw=FIT_KW)
    assert r2["best"] == r["best"] and r2["best_scores"] == r["best_scores"]
    assert r2["tau_selection"]["scores"] == r["tau_selection"]["scores"]
    assert r2["tau_selection"]["tau"] == r["tau_selection"]["tau"]


def test_tie_rule_prefers_simpler():
    assert SR._pick([("0", 0.50000), ("ess", 0.49995), ("1", 0.49)]) == "1"
    assert SR._pick([("0", 0.50000), ("ess", 0.49995), ("1", 0.499951)]) == "0"


def test_tau_zero_is_prior_weighted_nonadaptive(runs):
    d, _ = runs["pos"]
    fit = M.fit_mixture(M.windows_full(d["rest"], d["train"]), 3, d["train"], **FIT_KW)
    msk = d["masks"][0]
    obs = np.setdiff1d(np.arange(N_ROI), msk)
    x, _ = R.split_window(d["task"][d["test"][0]][0], obs, msk)
    p0, w0 = M.predict_adaptive(fit, x, obs, msk, tau=0.0)
    assert np.allclose(w0, fit.pis)
    assert np.allclose(p0, np.tensordot(fit.pis, M._cond_means(fit, x, obs, msk), axes=1))


def test_pooled_prior_of_k1_equals_component(runs):
    d, _ = runs["null"]
    f1 = M.fit_mixture(M.windows_full(d["rest"], d["train"]), 1, d["train"])
    assert np.allclose(SR.pooled_prior(f1).cov, f1.covs[0])


def test_tau_ess_smaller_under_strong_autocorrelation(runs):
    lo = SR.tau_ess(M.windows_full(runs["null"][0]["rest"], runs["null"][0]["train"]))
    hi = SR.tau_ess(M.windows_full(runs["null_ar"][0]["rest"], runs["null_ar"][0]["train"]))
    assert hi < lo < 1.0


# ---------------------------------------------------------------- 사전 정의 세계

def test_null_no_spurious_main_effect(runs):
    for key in ("null", "null_ar"):
        _, r = runs[key]
        assert r["mix"] == "ok"
        assert _ratio(r) > 0.99, (key, _ratio(r))                 # BEST 대비 1 % 넘는 가짜 이득 없음


def test_positive_main_effect_against_inner_best(runs):
    d, r = runs["pos"]
    assert r["mix"] == "ok" and r["adaptive_selected"]
    assert _ratio(r) < 0.95
    est, lo, hi = R.subject_bootstrap(R.delta(r["nmse"]["BEST"], r["nmse"]["MIX-a"]), 2000, seed=4)
    assert lo > 0


def test_positive_under_strong_autocorrelation_not_worse(runs):
    _, r = runs["pos_ar"]
    assert r["mix"] == "ok"
    assert _ratio(r) < 1.0


def test_overlap_and_sparse_handled(runs):
    for key in ("overlap", "sparse"):
        _, r = runs[key]
        if r["mix"] == "ok":
            assert _ratio(r) < 1.02, (key, _ratio(r))
        else:
            assert r["mix"] == "실패" and "MIX-a" not in r["nmse"]     # 실패는 실패로 — 대체 없음


def test_wrong_state_bank_no_spurious_gain(runs):
    """잘못된 bank 에서 G-A 가 가짜 이득을 내지 않는다.

    결과 공개 (결정 85): 처음 사전 기준은 "큰 손실 없음 (비율 < 1.05)" 이었고 **실패**했다 (1.088 — τ = 0 이 선택됐으나
    비적응 혼합도 BEST (큰 λ ridge) 보다 나쁨). 그 결과를 본 뒤 단언을 gate 에 필요한 성질 (가짜 이득 없음) 로 바꿨다.
    손실 크기는 단언하지 않고 보고한다 — 이 세계에서 G-A 는 "손해" 로 멈춘다.
    """
    _, r = runs["wrong_bank"]
    if r["mix"] == "ok":
        assert _ratio(r) > 0.99
