"""S 후보 1·3 (logistic) 과 S 선택 규칙 — 계획서 §6 "S 후보" 행. 합성 자료만 쓴다."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest

from mobse.v2 import baselines as B
from mobse.v2 import features as F
from mobse.v2 import train as TR

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPO_ROOT / "docs" / "experiments" / "mobse_redesign_protocol_2026-09-17.md"
TASKS = ("emomatching", "workingmemory")


def _rk(i: int, task: str) -> str:
    return f"ds002785/sub-{i:04d}/na/{task}/na/seq"


def _windows(n: int, *, seed: int, shift: float = 0.0, corr: float = 0.0):
    """30×100 합성 창. shift 는 앞 10 ROI 평균 이동, corr 는 앞 40 ROI 공통 성분."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        x = rng.standard_normal((30, 100))
        x[:, :10] += shift
        if corr:
            x[:, :40] += corr * rng.standard_normal((30, 1))
        out.append(x)
    return out


def _dataset(kind: str, n_per_class: int, seed: int):
    if kind == "mean":
        a = _windows(n_per_class, seed=seed, shift=0.0)
        b = _windows(n_per_class, seed=seed + 1, shift=1.0)
    else:
        a = _windows(n_per_class, seed=seed, corr=0.0)
        b = _windows(n_per_class, seed=seed + 1, corr=2.0)
    return a + b, np.array([0] * n_per_class + [1] * n_per_class)


# ---- 상수 ↔ 계획서 ------------------------------------------------------------


def test_logistic_grid_matches_protocol_text():
    text = PROTOCOL.read_text(encoding="utf-8")
    m = re.search(r"logistic C는 \{([^}]*)\}", text)
    assert m, "계획서에서 logistic C grid 문장을 찾지 못했다"
    assert tuple(float(v) for v in m.group(1).split(",")) == B.LOGISTIC_CS


def test_candidate_table_matches_protocol():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "raw ROI mean/variance(200 features) + logistic regression" in text
    assert "signed Fisher-z FC 4,950 + logistic regression" in text
    assert B.CANDIDATE_ORDER == (B.S1, B.S2, B.S3, B.S4)
    assert B.LOGISTIC_CANDIDATES == (B.S1, B.S3)
    assert B.expected_dim(B.FEATURE_ROI_MEAN_VAR) == 200
    assert B.expected_dim(B.FEATURE_FC_FISHER_Z) == 4950


# ---- feature ------------------------------------------------------------------


def test_roi_mean_var_order_and_ddof0():
    w = _windows(1, seed=0)[0]
    v = B.roi_mean_var(w)
    assert v.shape == (200,)
    np.testing.assert_array_equal(v[:100], w.mean(axis=0))
    np.testing.assert_array_equal(v[100:], ((w - w.mean(axis=0)) ** 2).mean(axis=0))


def test_fc_is_the_same_function_as_features():
    w = _windows(1, seed=1)[0]
    np.testing.assert_array_equal(B.fc_fisher_z(w), F.window_features(w)[1])
    assert B.fc_fisher_z(w).shape == (4950,)


def test_feature_matrix_rejects_bad_input():
    w = _windows(2, seed=2)
    with pytest.raises(B.BaselineError):
        B.feature_matrix(w, "nope")
    with pytest.raises(B.BaselineError):
        B.feature_matrix([], B.FEATURE_ROI_MEAN_VAR)
    bad = w[0].copy()
    bad[3, 4] = np.nan
    with pytest.raises(B.BaselineError):
        B.feature_matrix([bad], B.FEATURE_ROI_MEAN_VAR)
    const = w[0].copy()
    const[:, 7] = 1.0
    with pytest.raises(F.FeatureError):
        B.feature_matrix([const], B.FEATURE_FC_FISHER_Z)
    with pytest.raises(B.BaselineError):
        B.feature_matrix([w[0], w[1][:, :50]], B.FEATURE_ROI_MEAN_VAR)
    assert B.feature_matrix(w, B.FEATURE_ROI_MEAN_VAR).shape == (2, 200)


# ---- logistic -----------------------------------------------------------------


def test_fit_logistic_guards():
    X = np.random.default_rng(0).standard_normal((20, 5))
    y = np.array([0, 1] * 10)
    with pytest.raises(B.BaselineError):
        B.fit_logistic(X, y, 0.5)                       # grid 밖
    with pytest.raises(B.BaselineError):
        B.fit_logistic(X, np.zeros(20, int), 1.0)       # 한 class
    with pytest.raises(B.BaselineError):
        B.fit_logistic(X, y[:-1], 1.0)                  # 길이 불일치
    Xn = X.copy()
    Xn[0, 0] = np.inf
    with pytest.raises(B.BaselineError):
        B.fit_logistic(Xn, y, 1.0)


def test_fit_logistic_equals_sklearn_l2_intercept_pipeline():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(3)
    X = rng.standard_normal((60, 8)) * rng.uniform(0.5, 5, 8) + 3.0
    y = (X[:, 0] + rng.standard_normal(60) > 3.0).astype(int)
    Xv = rng.standard_normal((15, 8)) + 10.0          # 분포 다른 평가 창
    for C in (0.01, 1.0, 100.0):
        fit = B.fit_logistic(X, y, C)
        ref = make_pipeline(StandardScaler(), LogisticRegression(
            C=C, l1_ratio=0.0, fit_intercept=True, solver="lbfgs",
            tol=B.LOGISTIC_TOL, max_iter=B.LOGISTIC_MAX_ITER)).fit(X, y)
        np.testing.assert_allclose(fit.predict_p1(Xv), ref.predict_proba(Xv)[:, 1],
                                   rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(fit.scaler_mean, X.mean(axis=0))   # training 창만
        assert fit.converged and fit.n_train == 60
    assert np.linalg.norm(B.fit_logistic(X, y, 0.001).coef) < \
        np.linalg.norm(B.fit_logistic(X, y, 10000.0).coef)            # L2 크기 순서


def test_unconverged_fit_is_recorded(monkeypatch):
    monkeypatch.setattr(B, "LOGISTIC_MAX_ITER", 1)
    rng = np.random.default_rng(4)
    X = rng.standard_normal((40, 6))
    y = (X[:, 0] > 0).astype(int)
    fit = B.fit_logistic(X, y, 10000.0)
    assert fit.converged is False
    assert fit.record()["converged"] is False


@pytest.mark.parametrize("cand,data", [(B.S1, "mean"), (B.S3, "corr")])
def test_synthetic_signal_is_recovered(cand, data):
    Xw, y = _dataset(data, 40, seed=10)
    Vw, yv = _dataset(data, 20, seed=50)
    kind = B.CANDIDATE_FEATURE[cand]
    fit = B.fit_logistic(B.feature_matrix(Xw, kind), y, 1.0)
    pred = (fit.predict_p1(B.feature_matrix(Vw, kind)) >= 0.5).astype(int)
    assert (pred == yv).mean() >= 0.9


def test_logistic_settings_order():
    s = B.logistic_settings()
    assert len(s) == 16
    assert [c for c, _, _ in s[:8]] == [B.S1] * 8 and s[8][0] == B.S3
    assert [v for _, _, v in s[:8]] == list(B.LOGISTIC_CS)
    assert s[0][1] == "C=0.001" and s[7][1] == "C=10000"


# ---- 선택 ---------------------------------------------------------------------


def _oof(p_wm: float, n: int = 6):
    """subject 마다 emo run p1 = 1-p_wm, wm run p1 = p_wm (둘 다 정답 확률 p_wm)."""
    out = {}
    for i in range(n):
        out[_rk(i, "emomatching")] = 1.0 - p_wm
        out[_rk(i, "workingmemory")] = p_wm
    return out


def test_inner_loss_is_subject_equal_log_loss():
    oof = _oof(0.8)
    oof[_rk(0, "workingmemory")] = 0.4
    expect = [-(math.log(0.8) + math.log(0.4)) / 2] + [-math.log(0.8)] * 5
    assert B.inner_loss(oof) == pytest.approx(sum(expect) / 6, rel=1e-12)
    per = {f"s{i}": [0.8, 0.8] for i in range(6)}
    per["s0"] = [0.8, 0.4]
    assert B.inner_loss(oof) == pytest.approx(TR.subject_equal_loss(per), rel=1e-12)


def test_merge_inner_oof_rejects_overlap():
    a = {_rk(0, "emomatching"): 0.3}
    b = {_rk(1, "emomatching"): 0.3}
    assert len(B.merge_inner_oof([a, b])) == 2
    with pytest.raises(B.BaselineError):
        B.merge_inner_oof([a, dict(a)])
    with pytest.raises(B.BaselineError):
        B.merge_inner_oof([])


def test_select_s_picks_lowest_loss():
    e = [B.SEntry(B.S1, "C=1", 3, _oof(0.7)),
         B.SEntry(B.S3, "C=0.1", 2, _oof(0.9)),
         B.SEntry(B.S3, "C=10", 4, _oof(0.6))]
    sel = B.select_s(e)
    assert (sel.candidate, sel.setting_id) == (B.S3, "C=0.1")
    assert sel.loss == pytest.approx(-math.log(0.9))
    assert len(sel.table) == 3


def test_select_s_tie_break_candidate_then_rank():
    same = _oof(0.8)
    e = [B.SEntry(B.S3, "C=0.01", 1, same), B.SEntry(B.S1, "C=100", 5, same),
         B.SEntry(B.S1, "C=10", 4, same)]
    sel = B.select_s(e)
    assert (sel.candidate, sel.setting_id) == (B.S1, "C=10")
    # 허용오차 안의 작은 차이도 동률
    near = dict(same)
    near[_rk(0, "workingmemory")] = 0.8 + 1e-9
    sel2 = B.select_s([B.SEntry(B.S3, "C=1", 3, near), B.SEntry(B.S1, "C=1", 3, same)])
    assert sel2.candidate == B.S1


def test_select_s_guards():
    with pytest.raises(B.BaselineError):
        B.select_s([])
    with pytest.raises(B.BaselineError):
        B.select_s([B.SEntry("S9", "x", 0, _oof(0.7))])
    with pytest.raises(B.BaselineError):
        B.select_s([B.SEntry(B.S1, "C=1", 3, _oof(0.7)),
                    B.SEntry(B.S1, "C=1", 3, _oof(0.8))])
    with pytest.raises(B.BaselineError, match="OOF run 집합"):
        B.select_s([B.SEntry(B.S1, "C=1", 3, _oof(0.7)),
                    B.SEntry(B.S3, "C=1", 3, _oof(0.7, n=5))])
    with pytest.raises(B.BaselineError, match="미수렴"):
        B.select_s([B.SEntry(B.S1, "C=1", 3, _oof(0.7)),
                    B.SEntry(B.S3, "C=1", 3, _oof(0.9), converged=False)])


def test_end_to_end_inner_selection_synthetic():
    """3 inner fold × 16 logistic 설정 → OOF → 선택. mean 신호 자료면 S1 이 뽑힌다."""
    n_sub = 18
    Xw, _ = _dataset("mean", n_sub * 4, seed=100)
    subj = np.repeat(np.arange(n_sub), 4)
    task = np.array(["emomatching"] * (n_sub * 4) + ["workingmemory"] * (n_sub * 4))
    subj = np.concatenate([subj, subj])
    y = (task == "workingmemory").astype(int)
    folds = [np.arange(n_sub)[k::3] for k in range(3)]
    entries = []
    for cand, sid, C in B.logistic_settings():
        X = B.feature_matrix(Xw, B.CANDIDATE_FEATURE[cand])
        per_fold, conv = [], True
        for val in folds:
            vm = np.isin(subj, val)
            fit = B.fit_logistic(X[~vm], y[~vm], C)
            conv &= fit.converged
            p = fit.predict_p1(X[vm])
            rp = {}
            for s, t, pv in zip(subj[vm], task[vm], p):
                rp.setdefault(_rk(int(s), t), []).append(pv)
            per_fold.append({k: float(np.mean(v)) for k, v in rp.items()})
        entries.append(B.SEntry(cand, sid, B.LOGISTIC_CS.index(C),
                                B.merge_inner_oof(per_fold), conv))
    sel = B.select_s(entries)
    assert sel.candidate == B.S1
    assert len(sel.table) == 16
