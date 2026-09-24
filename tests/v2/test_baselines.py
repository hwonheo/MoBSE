"""S 후보 1·3 (logistic)·2·4 (32-hidden MLP) 와 S 선택 규칙 — 계획서 §6 "S 후보" 행. 합성 자료만 쓴다."""

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
    with pytest.raises(B.BaselineError, match="모든 설정 2개가 미수렴"):
        B.select_s([B.SEntry(B.S1, "C=1", 3, _oof(0.7), converged=False),
                    B.SEntry(B.S3, "C=1", 3, _oof(0.9), converged=False)])


def test_select_s_excludes_unconverged_and_reports_count():
    """[개정 P11] 미수렴 설정은 loss 가 가장 낮아도 빼고, 뺀 설정·수를 남긴다."""
    e = [B.SEntry(B.S1, "C=1", 3, _oof(0.7)),
         B.SEntry(B.S1, "C=10", 4, _oof(0.75)),
         B.SEntry(B.S3, "C=1", 3, _oof(0.95), converged=False),
         B.SEntry(B.S3, "C=100", 5, _oof(0.99), converged=False)]
    sel = B.select_s(e)
    assert (sel.candidate, sel.setting_id) == (B.S1, "C=10")
    assert sel.loss == pytest.approx(-math.log(0.75))
    assert sel.excluded == (f"{B.S3}/C=1", f"{B.S3}/C=100")
    assert sel.n_excluded == 2
    assert len(sel.table) == 4
    assert [r["converged"] for r in sel.table] == [True, True, False, False]
    # 동률 판정도 수렴 설정 안에서만: 미수렴 설정이 동률 기준(best)을 끌어내리지 않는다
    same = _oof(0.8)
    sel2 = B.select_s([B.SEntry(B.S1, "C=1", 3, same, converged=False),
                       B.SEntry(B.S3, "C=1", 3, same)])
    assert sel2.candidate == B.S3 and sel2.n_excluded == 1


def test_select_s_all_converged_reports_zero_excluded():
    sel = B.select_s([B.SEntry(B.S1, "C=1", 3, _oof(0.7))])
    assert sel.excluded == () and sel.n_excluded == 0


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


# ---- MLP (S 후보 2·4) ---------------------------------------------------------


def _task_set(kind: str, n_sub: int, seed: int):
    """subject 마다 emo 4창(class 0) + wm 4창(class 1). run key 는 창마다."""
    a = _windows(n_sub * 4, seed=seed, **({"shift": 0.0} if kind == "mean" else {"corr": 0.0}))
    b = _windows(n_sub * 4, seed=seed + 1,
                 **({"shift": 1.0} if kind == "mean" else {"corr": 2.0}))
    keys = ([_rk(i, "emomatching") for i in range(n_sub) for _ in range(4)]
            + [_rk(i, "workingmemory") for i in range(n_sub) for _ in range(4)])
    y = np.array([0] * (n_sub * 4) + [1] * (n_sub * 4))
    return a + b, y, keys


def _mean_xy(n_sub: int, seed: int):
    w, y, keys = _task_set("mean", n_sub, seed)
    return B.feature_matrix(w, B.FEATURE_ROI_MEAN_VAR), y, keys


def test_mlp_constants_match_protocol():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "동일 200 features + 32-hidden MLP" in text
    assert "위 FC + 32-hidden MLP" in text
    assert "MLP는 아래 8개 grid와 같은 예산이다" in text
    assert B.MLP_HIDDEN == 32
    assert B.MLP_CANDIDATES == (B.S2, B.S4)
    assert B.CANDIDATE_FEATURE[B.S2] == B.FEATURE_ROI_MEAN_VAR
    assert B.CANDIDATE_FEATURE[B.S4] == B.FEATURE_FC_FISHER_Z


def test_mlp_settings_share_the_common_grid():
    s = B.mlp_settings()
    ids = [g.config_id for g in TR.build_grid()]
    assert len(s) == 16 and ids == list(range(8))
    assert [c for c, _, _ in s] == [B.S2] * 8 + [B.S4] * 8
    assert [r for _, _, r in s] == ids + ids
    assert s[0][1] == "config=0" and s[15][1] == "config=7"


def test_build_mlp_architecture():
    import torch.nn as nn

    m = B.build_mlp(200, 0.3)
    assert [type(l) for l in m] == [nn.Linear, nn.GELU, nn.Dropout, nn.Linear]
    assert (m[0].in_features, m[0].out_features) == (200, 32)
    assert (m[3].in_features, m[3].out_features) == (32, 2)
    assert m[2].p == 0.3
    assert B.build_mlp(4950, 0.1)[0].in_features == 4950
    with pytest.raises(B.BaselineError):
        B.build_mlp(0, 0.1)


def test_fit_mlp_defaults_are_read_from_train_at_call_time(monkeypatch):
    """P8 기본값이 조용히 굳지 않는다 — 인자 기본은 None, 값은 호출 시점 `train` 상수."""
    import inspect

    sig = inspect.signature(B.fit_mlp)
    assert sig.parameters["min_updates"].default is None
    assert sig.parameters["max_epochs"].default is None
    for banned in ("batch_size", "patience", "min_delta", "grad_clip"):
        assert banned not in sig.parameters
    X, y, keys = _mean_xy(4, seed=1)                 # 32 창 → 1 update/epoch
    with pytest.raises(B.BaselineError, match=f"최소 {TR.MIN_UPDATES} update"):
        B.fit_mlp(X, y, X, keys, role="inner", config_id=0, model_seed=42)
    monkeypatch.setattr(TR, "MIN_UPDATES", 3)
    fit, _ = B.fit_mlp(X, y, X, keys, role="inner", config_id=0, model_seed=42)
    assert fit.min_epoch == 3 and fit.epochs_run >= 3


def test_fit_mlp_guards():
    X, y, keys = _mean_xy(4, seed=2)
    kw = dict(model_seed=42, min_updates=0)
    with pytest.raises(B.BaselineError, match="role"):
        B.fit_mlp(X, y, X, keys, role="test", config_id=0, **kw)
    with pytest.raises(B.BaselineError, match="config_id"):
        B.fit_mlp(X, y, X, keys, role="inner", config_id=8, **kw)
    with pytest.raises(B.BaselineError, match="정확히"):
        B.fit_mlp(X, y, X, keys, role="outer", config_id=0, **kw)
    with pytest.raises(B.BaselineError, match="epochs_exact"):
        B.fit_mlp(X, y, X, keys, role="inner", config_id=0, epochs_exact=3, **kw)
    with pytest.raises(B.BaselineError, match="상한"):
        B.fit_mlp(X, y, X, keys, role="outer", config_id=0,
                  epochs_exact=TR.MAX_EPOCHS + 1, **kw)
    with pytest.raises(B.BaselineError, match="P8"):
        B.fit_mlp(X, y, X, keys, role="outer", config_id=0, epochs_exact=5,
                  model_seed=42, min_updates=6)
    with pytest.raises(B.BaselineError, match="두 class"):
        B.fit_mlp(X, np.zeros_like(y), X, keys, role="inner", config_id=0, **kw)
    with pytest.raises(B.BaselineError, match="X_eval"):
        B.fit_mlp(X, y, X[:, :10], keys, role="inner", config_id=0, **kw)
    with pytest.raises(B.BaselineError, match="X_eval"):
        B.fit_mlp(X, y, X, keys[:-1], role="inner", config_id=0, **kw)


def test_fit_mlp_inner_never_stops_before_min_epoch():
    X, y, keys = _mean_xy(4, seed=3)
    V, _, vkeys = _mean_xy(3, seed=30)
    fit, _ = B.fit_mlp(X, y, V, vkeys, role="inner", config_id=3, model_seed=42,
                       min_updates=12)
    assert fit.min_epoch == 12
    assert fit.epochs_run >= 12 and fit.best_epoch >= 12
    assert len(fit.val_losses) == fit.epochs_run
    assert fit.updates_run == fit.updates_per_epoch * fit.epochs_run
    assert fit.eval_epoch == fit.best_epoch
    assert fit.record()["converged"] is True and fit.record()["hidden"] == 32


def test_fit_mlp_inner_evaluates_best_checkpoint_not_last_epoch():
    """inner 평가 확률 = 같은 seed 로 best_epoch 만큼만 학습한 모델의 확률 (결정 12).

    검증 forward 는 eval 모드·no_grad 라 RNG 를 소비하지 않으므로, outer 로 정확히
    best_epoch 학습한 궤적과 inner 궤적은 그 epoch 까지 같다.
    """
    X, y, keys = _mean_xy(6, seed=4)
    V, _, vkeys = _mean_xy(4, seed=40)
    found = False
    for cid in range(8):
        inner, m_in = B.fit_mlp(X, y, V, vkeys, role="inner", config_id=cid,
                                model_seed=43, min_updates=4)
        if inner.best_epoch == inner.epochs_run:
            continue
        found = True
        outer, m_out = B.fit_mlp(X, y, V, vkeys, role="outer", config_id=cid,
                                 model_seed=43, epochs_exact=inner.best_epoch,
                                 min_updates=4)
        np.testing.assert_array_equal(inner.eval_window_p1, outer.eval_window_p1)
        for (k, a), (_, b) in zip(m_in.state_dict().items(), m_out.state_dict().items()):
            assert bool((a == b).all()), k
        assert inner.eval_loss == pytest.approx(inner.val_losses[inner.best_epoch - 1],
                                                rel=1e-6)
        break
    assert found, "합성 자료에서 best < 마지막 epoch 인 fit 이 없었다 — 시험 자료를 바꿔야 한다"


def test_fit_mlp_is_deterministic_and_scaler_uses_training_only():
    X, y, keys = _mean_xy(4, seed=5)
    V, _, vkeys = _mean_xy(3, seed=50)
    V = V + 10.0                                        # 분포 다른 평가 창
    a, _ = B.fit_mlp(X, y, V, vkeys, role="outer", config_id=1, model_seed=44,
                     epochs_exact=6, min_updates=0)
    b, _ = B.fit_mlp(X, y, V, vkeys, role="outer", config_id=1, model_seed=44,
                     epochs_exact=6, min_updates=0)
    np.testing.assert_array_equal(a.eval_window_p1, b.eval_window_p1)
    np.testing.assert_allclose(a.scaler_mean, X.mean(axis=0))
    c, _ = B.fit_mlp(X, y, V, vkeys, role="outer", config_id=1, model_seed=42,
                     epochs_exact=6, min_updates=0)
    assert not np.array_equal(a.eval_window_p1, c.eval_window_p1)
    assert a.determinism["use_deterministic_algorithms"] is True
    import torch

    torch.manual_seed(44)
    assert a.init_hash == B.mlp_param_hash(B.build_mlp(X.shape[1], 0.1))
    assert a.init_hash == b.init_hash != c.init_hash
    assert a.record()["init_hash"] == a.init_hash


@pytest.mark.parametrize("cand,data", [(B.S2, "mean"), (B.S4, "corr")])
def test_mlp_synthetic_signal_is_recovered(cand, data):
    kind = B.CANDIDATE_FEATURE[cand]
    w, y, _ = _task_set(data, 10, seed=60)
    vw, yv, vkeys = _task_set(data, 5, seed=70)
    fit, _ = B.fit_mlp(B.feature_matrix(w, kind), y, B.feature_matrix(vw, kind), vkeys,
                       role="outer", config_id=0, model_seed=42, epochs_exact=40,
                       min_updates=0)
    assert ((fit.eval_window_p1 >= 0.5).astype(int) == yv).mean() >= 0.9
    assert len(fit.eval_run_probs) == 10


def test_select_s_orders_mlp_between_logistic_candidates():
    """동률이면 S1 < S2 < S3 < S4, 같은 후보 안에서는 config_id 순."""
    same = _oof(0.8)
    e = [B.SEntry(B.S4, "config=0", 0, same), B.SEntry(B.S3, "C=0.001", 0, same),
         B.SEntry(B.S2, "config=5", 5, same), B.SEntry(B.S2, "config=2", 2, same)]
    sel = B.select_s(e)
    assert (sel.candidate, sel.setting_id) == (B.S2, "config=2")
    sel2 = B.select_s(e + [B.SEntry(B.S1, "C=1", 3, same)])
    assert sel2.candidate == B.S1
    sel3 = B.select_s([B.SEntry(B.S2, "config=0", 0, _oof(0.7)),
                       B.SEntry(B.S4, "config=7", 7, _oof(0.9))])
    assert (sel3.candidate, sel3.setting_id) == (B.S4, "config=7")


# ---- 결정 14 3단계: seed 제약·구조 비교 독립 선택 --------------------------------


@pytest.mark.parametrize("seed", [0, 41, 45])
def test_fit_mlp_rejects_seed_outside_locked_model_seeds(seed):
    X, y, keys = _mean_xy(4, seed=2)
    with pytest.raises(B.BaselineError, match="MODEL_SEEDS"):
        B.fit_mlp(X, y, X, keys, role="inner", config_id=0, model_seed=seed,
                  min_updates=0, max_epochs=1)


def test_fit_mlp_seed_set_is_read_at_call_time(monkeypatch):
    X, y, keys = _mean_xy(4, seed=2)
    monkeypatch.setattr(TR, "MODEL_SEEDS", (7,))
    with pytest.raises(B.BaselineError, match="MODEL_SEEDS"):
        B.fit_mlp(X, y, X, keys, role="inner", config_id=0, model_seed=42,
                  min_updates=0, max_epochs=1)
    fit, _ = B.fit_mlp(X, y, X, keys, role="inner", config_id=0, model_seed=7,
                       min_updates=0, max_epochs=1)
    assert fit.model_seed == 7


def test_comparator_names_match_models():
    from mobse.v2 import models as M
    assert set(B.COMPARATOR_ORDER) == set(M.COMPARATOR_SPEC)


def _fold_probs(fold: int, p_wm: float, n_per_fold: int = 2):
    out = {}
    for i in range(fold * n_per_fold, (fold + 1) * n_per_fold):
        out[_rk(i, "emomatching")] = 1.0 - p_wm
        out[_rk(i, "workingmemory")] = p_wm
    return out


def _comp_results(structure="NG", p_by_config=None, epochs=None, seed=None):
    """8 config × 3 fold. 기본 정답 확률 0.6, best epoch (4, 7, 9)."""
    p_by_config = p_by_config or {}
    epochs = epochs or {}
    out = []
    for cid in range(8):
        for f in range(3):
            out.append(B.ComparatorInner(
                structure=structure, config_id=cid, inner_fold=f,
                model_seed=TR.INNER_SEED if seed is None else seed,
                run_probs=_fold_probs(f, p_by_config.get(cid, 0.6)),
                best_epoch=epochs.get(cid, (4, 7, 9))[f]))
    return out


def test_select_comparator_picks_lowest_oof_loss_and_baseline_epochs():
    res = _comp_results(p_by_config={5: 0.9, 2: 0.8}, epochs={5: (3, 10, 6)})
    sel = B.select_comparator(res, structure="NG")
    assert sel.config_id == 5 and sel.tie_rule == "unique minimum"
    assert sel.best_epochs == (3, 10, 6)
    assert sel.outer_epochs == TR.baseline_epochs([3, 10, 6]) == 6
    assert sel.loss == pytest.approx(-math.log(0.9), rel=1e-12)
    assert [row["config_id"] for row in sel.table] == list(range(8))


def test_select_comparator_loss_is_merged_oof_not_fold_mean():
    """선택 손실은 3 fold 를 합친 OOF 의 subject 동일 가중 loss 다 (S 와 같은 함수)."""
    res = _comp_results()
    # config 1: fold 0 의 subject 수를 늘려 fold 평균과 OOF 합산이 달라지게 한다
    res = [r for r in res if not (r.config_id == 1 and r.inner_fold == 0)]
    big = _fold_probs(0, 0.95, n_per_fold=2)
    big.update({_rk(i, t): (0.05 if t == "emomatching" else 0.95)
                for i in range(100, 104) for t in TASKS})
    for r in list(res):
        if r.inner_fold == 0:
            res.remove(r)
            extra = {_rk(i, t): (0.4 if t == "emomatching" else 0.6)
                     for i in range(100, 104) for t in TASKS}
            res.append(B.ComparatorInner(r.structure, r.config_id, 0, r.model_seed,
                                         {**r.run_probs, **extra}, r.best_epoch))
    res.append(B.ComparatorInner("NG", 1, 0, TR.INNER_SEED, big, 4))
    sel = B.select_comparator(res, structure="NG")
    rows = {row["config_id"]: row for row in sel.table}
    oof1 = B.merge_inner_oof([r.run_probs for r in sorted(
        (r for r in res if r.config_id == 1), key=lambda r: r.inner_fold)])
    assert rows[1]["inner_loss"] == pytest.approx(B.inner_loss(oof1), rel=1e-12)
    fold_mean = np.mean([B.inner_loss(r.run_probs) for r in res if r.config_id == 1])
    assert abs(rows[1]["inner_loss"] - fold_mean) > 1e-3


def test_select_comparator_tie_breaks_ba_then_config_id():
    # 전부 같은 loss → BA 도 같음 → config_id 0
    sel = B.select_comparator(_comp_results("SG"), structure="SG")
    assert sel.config_id == 0 and sel.tie_rule == "tie broken by BA then smallest config_id"
    # 전 config 정답 확률 0.3 (BA 0). config 6 만 (0.9, 0.1) 쌍 — loss 같고 BA 0.5
    res = _comp_results("SG", p_by_config={c: 0.3 for c in range(8)})
    loss_target = -math.log(0.3)

    def pair(fold, pa, pb):
        out = {}
        for i in range(fold * 2, fold * 2 + 2):
            out[_rk(i, "emomatching")] = 1.0 - pa
            out[_rk(i, "workingmemory")] = pb
        return out
    pa = 0.9
    pb = math.exp(-2 * loss_target) / pa   # log loss (pa, pb) 평균 = loss_target
    res = [r if r.config_id != 6 else B.ComparatorInner(
        "SG", 6, r.inner_fold, r.model_seed, pair(r.inner_fold, pa, pb), r.best_epoch)
        for r in res]
    rows = {row["config_id"]: row for row in B.select_comparator(res, structure="SG").table}
    assert rows[6]["inner_loss"] == pytest.approx(rows[3]["inner_loss"], abs=1e-9)
    sel = B.select_comparator(res, structure="SG")
    assert sel.config_id == 6 and sel.tie_rule == "tie broken by BA"


def test_select_comparator_guards():
    base = _comp_results()
    with pytest.raises(B.BaselineError, match="알 수 없는 구조"):
        B.select_comparator(base, structure="A")
    with pytest.raises(B.BaselineError, match="없다"):
        B.select_comparator([], structure="NG")
    with pytest.raises(B.BaselineError, match="섞였다"):
        B.select_comparator(base + _comp_results("SG")[:1], structure="NG")
    with pytest.raises(B.BaselineError, match="inner seed"):
        B.select_comparator(_comp_results(seed=43), structure="NG")
    with pytest.raises(B.BaselineError, match="불완전"):
        B.select_comparator(base[:-1], structure="NG")
    with pytest.raises(B.BaselineError, match="중복"):
        B.select_comparator(base + base[:1], structure="NG")
    extra = B.ComparatorInner("NG", 0, 3, TR.INNER_SEED, _fold_probs(3, 0.6), 4)
    with pytest.raises(B.BaselineError, match="예상 밖"):
        B.select_comparator(base + [extra], structure="NG")
    with pytest.raises(B.BaselineError, match="best_epoch"):
        B.select_comparator(_comp_results(epochs={2: (4, 0, 9)}), structure="NG")
    with pytest.raises(B.BaselineError, match="best_epoch"):
        B.select_comparator(_comp_results(epochs={2: (4, TR.MAX_EPOCHS + 1, 9)}),
                            structure="NG")
    overlap = [r if not (r.config_id == 4 and r.inner_fold == 1) else B.ComparatorInner(
        "NG", 4, 1, r.model_seed, _fold_probs(0, 0.6), r.best_epoch) for r in base]
    with pytest.raises(B.BaselineError, match="겹친다"):
        B.select_comparator(overlap, structure="NG")
    shifted = [r if not (r.config_id == 4 and r.inner_fold == 2) else B.ComparatorInner(
        "NG", 4, 2, r.model_seed, _fold_probs(5, 0.6), r.best_epoch) for r in base]
    with pytest.raises(B.BaselineError, match="OOF run 집합"):
        B.select_comparator(shifted, structure="NG")


def test_select_comparator_is_independent_per_structure():
    ng = _comp_results("NG", p_by_config={1: 0.9})
    sg = _comp_results("SG", p_by_config={7: 0.9})
    assert B.select_comparator(ng, structure="NG").config_id == 1
    assert B.select_comparator(sg, structure="SG").config_id == 7


def test_comparator_outer_plan_uses_locked_seeds_and_exact_epochs(monkeypatch):
    sel = B.select_comparator(_comp_results("SG", p_by_config={2: 0.9}), structure="SG")
    plan = sel.outer_plan()
    assert [p["model_seed"] for p in plan] == list(TR.MODEL_SEEDS)
    assert {(p["structure"], p["config_id"], p["epochs_exact"]) for p in plan} == {
        ("SG", 2, sel.outer_epochs)}
    monkeypatch.setattr(TR, "MODEL_SEEDS", (42,))
    assert len(sel.outer_plan()) == 1


def test_comparator_fit_count_matches_decision_14():
    """결정 14: 구조당 inner 8×3×5 = 120 + outer 5×3 = 15 → 두 구조 270."""
    per_outer_inner = len(_comp_results())
    assert per_outer_inner == 24
    assert 2 * (per_outer_inner * 5 + 5 * len(TR.MODEL_SEEDS)) == 270
