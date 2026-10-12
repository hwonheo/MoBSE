"""T12 selection boundary — mobse/v2/train.py."""

from __future__ import annotations

import math

import pytest

from mobse.v2.train import (
    CELLS, MAX_EPOCHS, MIN_DELTA, MIN_UPDATES, PATIENCE, CellFoldResult,
    GridConfig, TrainError, min_epochs_for, updates_per_epoch,
    assert_no_test_leakage, baseline_epochs, build_grid, clipped_log_loss,
    early_stop_epoch, fit_budget, select_config, subject_equal_loss,
)


# --------------------------------------------------------------------------- #
# grid 순서 고정
# --------------------------------------------------------------------------- #

def test_grid_is_eight_configs_in_protocol_order():
    g = build_grid()
    assert len(g) == 8
    assert [c.config_id for c in g] == list(range(8))
    assert (g[0].learning_rate, g[0].dropout, g[0].weight_decay) == (0.001, 0.1, 0.0001)
    assert (g[1].learning_rate, g[1].dropout, g[1].weight_decay) == (0.001, 0.1, 0.001)
    assert (g[7].learning_rate, g[7].dropout, g[7].weight_decay) == (0.0003, 0.3, 0.001)
    assert len({(c.learning_rate, c.dropout, c.weight_decay) for c in g}) == 8


def test_grid_is_stable_across_calls():
    assert [c.as_dict() for c in build_grid()] == [c.as_dict() for c in build_grid()]


# --------------------------------------------------------------------------- #
# loss
# --------------------------------------------------------------------------- #

def test_log_loss_clips_extreme_probabilities():
    assert clipped_log_loss([1.0]) == pytest.approx(0.0, abs=1e-6)
    v = clipped_log_loss([0.0])
    assert math.isfinite(v) and v > 15


def test_subject_equal_weighting_ignores_run_count_imbalance():
    # subject A 는 run 2개, subject B 는 run 4개. subject 가중이 같아야 한다.
    per_run = {"a": [0.9, 0.9], "b": [0.5, 0.5, 0.5, 0.5]}
    expected = (clipped_log_loss([0.9, 0.9]) + clipped_log_loss([0.5] * 4)) / 2
    assert subject_equal_loss(per_run) == pytest.approx(expected)


def test_empty_inputs_fail():
    with pytest.raises(TrainError):
        clipped_log_loss([])
    with pytest.raises(TrainError):
        subject_equal_loss({})


# --------------------------------------------------------------------------- #
# 공동 선택
# --------------------------------------------------------------------------- #

def _results(loss_by_config, *, epochs=None, ba_by_config=None, n_folds=3):
    out = []
    for cid, loss in loss_by_config.items():
        for cell in CELLS:
            for f in range(n_folds):
                out.append(CellFoldResult(
                    config_id=cid, cell=cell, inner_fold=f, loss=loss,
                    balanced_accuracy=(ba_by_config or {}).get(cid, 0.5),
                    best_epoch=(epochs or {}).get(cid, 10), n_subjects=10))
    return out


def test_selects_config_with_lowest_joint_loss():
    losses = {i: 1.0 - 0.01 * i for i in range(8)}      # config 7 이 최소
    sel = select_config(_results(losses))
    assert sel.config_id == 7
    assert sel.tie_rule == "unique minimum"


def test_tie_broken_by_joint_ba_then_smallest_id():
    losses = {i: (0.5 if i in (2, 5) else 1.0) for i in range(8)}
    sel = select_config(_results(losses, ba_by_config={2: 0.60, 5: 0.70}))
    assert sel.config_id == 5 and "joint BA" in sel.tie_rule

    sel2 = select_config(_results(losses, ba_by_config={2: 0.70, 5: 0.70}))
    assert sel2.config_id == 2, "BA 도 동률이면 작은 config_id"
    assert "smallest config_id" in sel2.tie_rule


def test_all_four_cells_get_equal_weight():
    """A 만 나쁜 config 와 D 만 나쁜 config 는 공동 loss 가 같아야 한다."""
    def build(bad_cell):
        out = []
        for cid in range(8):
            for cell in CELLS:
                for f in range(3):
                    loss = 2.0 if (cid == 0 and cell == bad_cell) else 1.0
                    out.append(CellFoldResult(cid, cell, f, loss, 0.5, 10, 10))
        return out
    a = select_config(build("A")).per_config[0]["joint_loss"]
    d = select_config(build("D")).per_config[0]["joint_loss"]
    assert a == pytest.approx(d)


def test_common_epoch_is_ceil_of_median_over_12_values():
    # 12개(4 cell × 3 fold) best epoch 의 중앙값 올림
    results = []
    epochs = [3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 9]      # 중앙값 5.5 -> 6
    i = 0
    for cell in CELLS:
        for f in range(3):
            results.append(CellFoldResult(0, cell, f, 1.0, 0.5, epochs[i], 10))
            i += 1
    for cid in range(1, 8):
        for cell in CELLS:
            for f in range(3):
                results.append(CellFoldResult(cid, cell, f, 2.0, 0.5, 10, 10))
    sel = select_config(results)
    assert sel.config_id == 0 and sel.common_epochs == 6


def test_incomplete_grid_is_rejected():
    losses = {i: 1.0 for i in range(7)}                 # config 7 누락
    with pytest.raises(TrainError, match="불완전한 grid"):
        select_config(_results(losses))


def test_missing_single_fold_is_rejected():
    res = _results({i: 1.0 for i in range(8)})
    res = [r for r in res if not (r.config_id == 3 and r.cell == "B" and r.inner_fold == 2)]
    with pytest.raises(TrainError, match="누락"):
        select_config(res)


def _oof_fixture():
    """fold 크기 3/3/1 — 크기 가중(OOF)과 fold 단순 평균이 다른 선택을 내는 자료.

    config 0: fold 0·1 (각 3명) 손실 0.2, fold 2 (1명) 손실 2.0
      → OOF (0.2*3 + 0.2*3 + 2.0*1)/7 = 0.4571…, fold 평균 0.8
    config 1: 모든 fold 손실 0.5 → OOF 0.5, fold 평균 0.5
    OOF 로는 config 0, fold 평균으로는 config 1 이 뽑힌다.
    """
    sizes = {0: 3, 1: 3, 2: 1}
    out = []
    for cid in range(8):
        for cell in CELLS:
            for f in range(3):
                if cid == 0:
                    loss = 2.0 if f == 2 else 0.2
                elif cid == 1:
                    loss = 0.5
                else:
                    loss = 3.0
                out.append(CellFoldResult(cid, cell, f, loss, 0.5, 10, sizes[f]))
    return out


def test_joint_loss_is_oof_subject_equal_not_fold_mean():
    """계획서 §7 "inner OOF run loss를 subject별 동일 가중으로 합산" (19:15 정정)."""
    sel = select_config(_oof_fixture())
    assert sel.config_id == 0, "fold 단순 평균이면 config 1 이 뽑힌다"
    assert sel.per_config[0]["joint_loss"] == pytest.approx((0.2 * 3 + 0.2 * 3 + 2.0) / 7)
    assert sel.per_config[1]["joint_loss"] == pytest.approx(0.5)


def test_joint_loss_equals_pooled_subject_equal_loss_by_hand():
    """fold 손실을 subject 단위로 풀어 OOF 로 합친 손계산과 같다 (loss·BA)."""
    import math as _m
    # fold 별 subject 의 정답 확률 (subject 당 run 2개)
    folds = {0: {"s1": [0.9, 0.8], "s2": [0.6, 0.3]},
             1: {"s3": [0.7, 0.7], "s4": [0.2, 0.9], "s5": [0.55, 0.45]},
             2: {"s6": [0.99, 0.51]}}
    def b(v):
        return sum(1.0 for p in v if p > 0.5) / len(v)
    rows = []
    for cid in range(8):
        for cell in CELLS:
            for f, subj in folds.items():
                loss = subject_equal_loss(subj) + (0.0 if cid == 3 else 1.0)
                ba = sum(b(v) for v in subj.values()) / len(subj)
                rows.append(CellFoldResult(cid, cell, f, loss, ba, 10, len(subj)))
    sel = select_config(rows)
    pooled = {k: v for subj in folds.values() for k, v in subj.items()}
    assert sel.config_id == 3
    assert sel.joint_loss == pytest.approx(subject_equal_loss(pooled), abs=1e-12)
    want_ba = sum(b(v) for v in pooled.values()) / len(pooled)
    assert sel.joint_ba == pytest.approx(want_ba, abs=1e-12)
    assert not _m.isclose(sel.joint_loss,
                          sum(subject_equal_loss(s) for s in folds.values()) / 3)


def test_n_subjects_required_and_validated():
    with pytest.raises(TypeError):
        CellFoldResult(0, "A", 0, 1.0, 0.5, 10)          # 기본값 없음
    for bad in (0, -1, True, 2.0):
        with pytest.raises(TrainError, match="n_subjects"):
            CellFoldResult(0, "A", 0, 1.0, 0.5, 10, bad)


def test_fold_subject_count_must_match_across_configs_and_cells():
    res = _results({i: 1.0 for i in range(8)})
    res = [CellFoldResult(r.config_id, r.cell, r.inner_fold, r.loss, r.balanced_accuracy,
                          r.best_epoch, 11 if (r.config_id == 5 and r.cell == "C"
                                               and r.inner_fold == 1) else r.n_subjects)
           for r in res]
    with pytest.raises(TrainError, match="subject 수가 다르다"):
        select_config(res)


def test_bad_cell_and_epoch_rejected():
    with pytest.raises(TrainError, match="알 수 없는 cell"):
        CellFoldResult(0, "E", 0, 1.0, 0.5, 10, 10)
    with pytest.raises(TrainError, match="best_epoch"):
        CellFoldResult(0, "A", 0, 1.0, 0.5, MAX_EPOCHS + 1, 10)
    with pytest.raises(TrainError, match="best_epoch"):
        CellFoldResult(0, "A", 0, 1.0, 0.5, 0, 10)


# --------------------------------------------------------------------------- #
# T12 — outer test 로 선택하지 않는다
# --------------------------------------------------------------------------- #

def test_leakage_guard_rejects_outer_test_scores():
    assert_no_test_leakage({"cfg0": "inner_validation", "cfg1": "inner_validation"})
    with pytest.raises(TrainError, match="outer test"):
        assert_no_test_leakage({"cfg0": "inner_validation", "cfg1": "outer_test"})
    with pytest.raises(TrainError):
        assert_no_test_leakage({"cfg0": "external"})


def test_early_stopping_uses_patience_and_min_delta():
    """개선폭이 min_delta 미만이면 patience 소진 후 멈춘다.

    경계값을 피한다. best=0.9 일 때 임계는 0.9−0.0005 인데 이 뺄셈은 부동소수에서
    0.8995000000000001 이 되므로, 정확히 0.8995 를 쓰면 개선으로 판정된다.
    검사 의도는 "명백히 미달인 개선"이므로 여유를 두고 값을 고른다.
    """
    losses = [1.0, 0.9, 0.8999, 0.89985, 0.8998, 0.89975, 0.8997, 0.1]
    assert early_stop_epoch(losses) == 2, "patience 5 소진 후 멈춰야 한다"
    # 꾸준히 개선되면 마지막이 best
    assert early_stop_epoch([1.0, 0.8, 0.6, 0.4, 0.2]) == 5


def test_early_stopping_boundary_is_strict_inequality():
    """개선 판정은 ``v < best - min_delta`` 다. 경계 동작을 명시적으로 고정한다."""
    # 정확히 min_delta 만큼 줄면 개선으로 세지 않는다 (부동소수 여유를 둔 값)
    assert early_stop_epoch([1.0, 1.0 - 0.0004, 1.0, 1.0, 1.0, 1.0, 1.0]) == 1
    # min_delta 를 확실히 넘으면 개선이다
    assert early_stop_epoch([1.0, 1.0 - 0.002]) == 2


def test_baseline_epoch_is_ceil_median_of_three():
    assert baseline_epochs([4, 7, 9]) == 7
    assert baseline_epochs([4, 5, 5]) == 5
    with pytest.raises(TrainError):
        baseline_epochs([4, 5])


# --------------------------------------------------------------------------- #
# 예산
# --------------------------------------------------------------------------- #

def test_fit_budget_matches_protocol_table():
    b = fit_budget()
    assert b["main_inner"] == 480
    assert b["main_outer"] == 60
    assert b["null_sensitivity"] == 120
    assert b["external_selection"] == 96
    assert b["external_final"] == 12
    assert b["total"] == 768


# --------------------------------------------------------------------------- #
# [개정 P8-b] 최소 5,000 update · 상한 400 epoch · 최소치 이후 early stopping
# --------------------------------------------------------------------------- #

def test_p8_constants_and_unchanged_stopping_parameters():
    assert MIN_UPDATES == 5000 and MAX_EPOCHS == 400   # 결정 15 (P8-b)
    # 결정은 patience·min_delta 를 바꾸지 않았다
    assert PATIENCE == 5 and MIN_DELTA == 0.0005


def test_p8_min_epochs_counts_the_last_partial_batch():
    assert updates_per_epoch(544, 32) == 17          # main inner 규모 (부록 W)
    assert updates_per_epoch(545, 32) == 18
    assert min_epochs_for(544) == 295                 # ceil(5000 / 17)
    assert min_epochs_for(544) <= MAX_EPOCHS          # main inner 가 상한 안에 든다
    assert min_epochs_for(808) == 193 and min_epochs_for(800) == 200  # outer E 하한
    assert min_epochs_for(544) * updates_per_epoch(544) >= MIN_UPDATES
    assert min_epochs_for(10, min_updates=0) == 1
    with pytest.raises(TrainError):
        updates_per_epoch(0)
    with pytest.raises(TrainError):
        min_epochs_for(10, min_updates=-1)


def test_p8_early_stopping_ignores_epochs_before_the_minimum():
    # epoch 2 가 전역 최소지만 min_epoch=4 이전이라 후보가 아니다
    losses = [1.0, 0.1, 0.9, 0.8, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7]
    assert early_stop_epoch(losses) == 2
    assert early_stop_epoch(losses, min_epoch=4) == 5
    # 최소치 전에는 인내가 소진되지 않는다: 1–5 가 정체여도 best 는 min_epoch 이후
    flat = [1.0] * 6 + [0.5]
    assert early_stop_epoch(flat, min_epoch=6) == 7


def test_p8_early_stopping_refuses_a_curve_shorter_than_the_minimum():
    with pytest.raises(TrainError, match="최소 epoch"):
        early_stop_epoch([1.0, 0.9], min_epoch=3)
    with pytest.raises(TrainError):
        early_stop_epoch([1.0], min_epoch=0)


def test_p8_common_e_may_reach_the_new_cap():
    CellFoldResult(0, "A", 0, 1.0, 0.5, 400, 10)          # 상한 이내
    with pytest.raises(TrainError, match="best_epoch"):
        CellFoldResult(0, "A", 0, 1.0, 0.5, 401, 10)
