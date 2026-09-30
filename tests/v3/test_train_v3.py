"""v3 학습 규칙 시험 — 결정 31-1·32.

무엇을 지키려는 시험인지 적어 둔다.

* 예산 산술은 v1 과 **같은 수**를 낸다 — 바뀐 것은 뜻 (최소치 → 예산·상한) 이다.
* best epoch 선택에서 **최소 epoch 결합이 풀렸다** (결정 32). v1 이 거부하던
  이른 epoch 를 v3 는 고를 수 있어야 한다.
* 선택 규칙 (공동 loss · 동률 · 공통 E) 자체는 **v1 과 같아야 한다** — 상한만 달라진다.
"""

from __future__ import annotations

import math

import pytest

from mobse.v2 import train as T2
from mobse.v3 import train as T3


# --------------------------------------------------------------------- 예산

@pytest.mark.parametrize("n_windows", [80, 160, 320, 400, 800, 1000])
def test_epoch_budget_matches_the_v1_arithmetic(n_windows):
    """예산 epoch 수는 v1 의 최소 epoch 수와 같은 산술이다 (뜻만 달라졌다)."""
    assert T3.epochs_for_budget(n_windows) == T2.min_epochs_for(
        n_windows, min_updates=T3.UPDATE_BUDGET)


def test_epoch_budget_is_ceiling_of_budget_over_updates_per_epoch():
    upe = T3.updates_per_epoch(80)
    assert upe == math.ceil(80 / T3.BATCH_SIZE)
    assert T3.epochs_for_budget(80) == math.ceil(T3.UPDATE_BUDGET / upe)


def test_low_sample_no_longer_hits_a_fixed_epoch_cap():
    """v1 은 400 상한 때문에 저표본을 돌릴 수 없었다 — v3 는 상한이 예산에서 나온다."""
    n_windows = 80                      # 학습 subject 10 명 × 창 8
    need = T2.min_epochs_for(n_windows, min_updates=T2.MIN_UPDATES)
    assert need > T2.MAX_EPOCHS         # v1 에서는 충돌한다
    assert T3.epochs_for_budget(n_windows) == need   # v3 는 그 값이 곧 상한이다


def test_budget_must_be_positive():
    with pytest.raises(T3.TrainError):
        T3.epochs_for_budget(80, update_budget=0)


def test_sanity_ceiling_refuses_an_absurdly_small_training_set():
    with pytest.raises(T3.TrainError, match="안전 상한"):
        T3.epochs_for_budget(1, update_budget=T3.EPOCH_SANITY_CEILING * 2)


# ------------------------------------------------------- best epoch 선택 (결정 32)

def test_best_epoch_may_come_from_any_epoch():
    """이른 곳에 최저점이 있으면 그것을 고른다 — v1 은 최소치 전이라 거부했다."""
    losses = [0.9, 0.5, 0.6, 0.62, 0.63, 0.64, 0.65]
    assert T3.select_best_epoch(losses) == 2
    with pytest.raises(T2.TrainError):
        T2.early_stop_epoch(losses, min_epoch=len(losses) + 1)


def test_best_epoch_rule_is_otherwise_the_v1_rule():
    losses = [0.9, 0.8, 0.7, 0.71, 0.72, 0.73, 0.74, 0.75]
    assert T3.select_best_epoch(losses) == T2.early_stop_epoch(losses, min_epoch=1)


def test_best_epoch_refuses_empty_losses():
    with pytest.raises(T2.TrainError):
        T3.select_best_epoch([])


# ------------------------------------------------------------ CellFoldResult

def _result(cid, cell, fold, *, best_epoch=5, ceiling=200, loss=0.5, ba=0.8, n=20):
    return T3.CellFoldResult(config_id=cid, cell=cell, inner_fold=fold, loss=loss,
                             balanced_accuracy=ba, best_epoch=best_epoch,
                             n_subjects=n, epoch_ceiling=ceiling)


def test_cell_fold_result_requires_an_explicit_ceiling():
    with pytest.raises(TypeError):
        T3.CellFoldResult(config_id=0, cell="A", inner_fold=0, loss=0.5,
                          balanced_accuracy=0.8, best_epoch=5, n_subjects=20)


def test_cell_fold_result_rejects_best_epoch_above_its_ceiling():
    with pytest.raises(T3.TrainError, match="best_epoch"):
        _result(0, "A", 0, best_epoch=201, ceiling=200)


def test_cell_fold_result_rejects_a_ceiling_below_one():
    """상한이 0 이면 상한 자신의 메시지로 걸려야 한다 — best_epoch 검사에 묻히면 안 된다."""
    with pytest.raises(T3.TrainError, match="epoch_ceiling"):
        _result(0, "A", 0, best_epoch=1, ceiling=0)


def test_cell_fold_result_accepts_an_epoch_far_above_the_v1_cap():
    """저표본에서는 상한이 v1 의 400 보다 훨씬 크다."""
    r = _result(0, "A", 0, best_epoch=1500, ceiling=T3.epochs_for_budget(80))
    assert r.best_epoch == 1500


# ------------------------------------------------------------------ 공동 선택

def _grid(ceiling=200, epochs=None, loss_of=None):
    out = []
    for cid in range(8):
        for cell in T3.CELLS:
            for f in range(3):
                out.append(_result(cid, cell, f, ceiling=ceiling,
                                   best_epoch=(epochs or {}).get(cid, 5),
                                   loss=(loss_of or {}).get(cid, 0.5 + 0.01 * cid)))
    return out


def test_selection_matches_v1_on_the_same_numbers():
    """선택 규칙은 바뀌지 않았다 — 같은 입력에서 같은 config·공통 E 가 나와야 한다."""
    epochs = {cid: 7 + cid for cid in range(8)}
    v3_sel = T3.select_config(_grid(epochs=epochs))
    v2_rows = [T2.CellFoldResult(config_id=r.config_id, cell=r.cell,
                                 inner_fold=r.inner_fold, loss=r.loss,
                                 balanced_accuracy=r.balanced_accuracy,
                                 best_epoch=r.best_epoch, n_subjects=r.n_subjects)
               for r in _grid(epochs=epochs)]
    v2_sel = T2.select_config(v2_rows)
    assert (v3_sel.config_id, v3_sel.common_epochs) == (v2_sel.config_id,
                                                        v2_sel.common_epochs)
    assert v3_sel.tie_rule == v2_sel.tie_rule


def test_selection_records_the_ceiling():
    sel = T3.select_config(_grid(ceiling=1667))
    assert sel.epoch_ceiling == 1667


def test_selection_refuses_mixed_ceilings():
    rows = _grid()
    rows[0] = _result(rows[0].config_id, rows[0].cell, rows[0].inner_fold, ceiling=999)
    with pytest.raises(T3.TrainError, match="epoch_ceiling"):
        T3.select_config(rows)


def test_selection_refuses_a_common_epoch_above_the_ceiling():
    rows = _grid(ceiling=10, epochs={cid: 10 for cid in range(8)})
    rows = [T3.CellFoldResult(config_id=r.config_id, cell=r.cell,
                              inner_fold=r.inner_fold, loss=r.loss,
                              balanced_accuracy=r.balanced_accuracy,
                              best_epoch=10, n_subjects=r.n_subjects, epoch_ceiling=10)
            for r in rows]
    sel = T3.select_config(rows)
    assert sel.common_epochs == 10          # 상한과 같은 값은 통과한다
    with pytest.raises(T3.TrainError):
        T3.CellFoldResult(config_id=0, cell="A", inner_fold=0, loss=0.5,
                          balanced_accuracy=0.8, best_epoch=11, n_subjects=20,
                          epoch_ceiling=10)


def test_selection_still_refuses_an_incomplete_grid():
    rows = _grid()[:-1]
    with pytest.raises(T3.TrainError, match="불완전"):
        T3.select_config(rows)


# --------------------------------------------------------------------------- #
# 공통 E 를 outer 로 옮기기 (구현 선택, 2026-09-30) — 단위는 update 다
# --------------------------------------------------------------------------- #


def test_carry_uses_updates_not_epochs():
    """outer 학습 집합이 크면 같은 update 를 더 적은 epoch 으로 채운다."""
    inner, outer = 160, 320          # outer 가 정확히 2 배
    e_out = T3.carry_epochs_to_outer(10, inner, outer, batch_size=32,
                                     update_budget=10_000)
    upe_in = T3.updates_per_epoch(inner, 32)
    upe_out = T3.updates_per_epoch(outer, 32)
    assert e_out == math.ceil(10 * upe_in / upe_out)
    assert e_out < 10                # epoch 을 그대로 옮기지 않는다


def test_carry_holds_the_update_count_not_the_epoch_count():
    inner, outer = 160, 400
    common_e = 7
    e_out = T3.carry_epochs_to_outer(common_e, inner, outer, batch_size=32,
                                     update_budget=100_000)
    carried = common_e * T3.updates_per_epoch(inner, 32)
    run = e_out * T3.updates_per_epoch(outer, 32)
    # 올림 한 번 분량 안에서 같은 update 를 쓴다.
    assert 0 <= run - carried < T3.updates_per_epoch(outer, 32)


def test_carry_never_exceeds_the_outer_budget_ceiling():
    """공통 E 가 inner 상한에 닿아 있어도 결과는 outer 상한 이하다."""
    for inner, outer in ((80, 120), (80, 800), (160, 161), (32, 3200)):
        ceiling_in = T3.epochs_for_budget(inner, batch_size=32, update_budget=5000)
        ceiling_out = T3.epochs_for_budget(outer, batch_size=32, update_budget=5000)
        e_out = T3.carry_epochs_to_outer(ceiling_in, inner, outer, batch_size=32,
                                         update_budget=5000)
        assert 1 <= e_out <= ceiling_out, (inner, outer, e_out, ceiling_out)


def test_carry_refuses_nonsense():
    with pytest.raises(T3.TrainError, match="공통 E"):
        T3.carry_epochs_to_outer(0, 80, 160)
    with pytest.raises(T3.TrainError, match="양수"):
        T3.carry_epochs_to_outer(3, 80, 160, update_budget=0)
