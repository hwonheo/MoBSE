"""저표본 부분표집 시험 — 결정 30.

고정하려는 것은 **중첩**과 **재현성**이다. 둘 중 하나라도 깨지면 곡선의 오르내림에
"누구를 뽑았나" 가 섞여 자료의 양으로 읽을 수 없게 된다.
"""

from __future__ import annotations

import pytest

from mobse.v3 import subsample as S

SUBS = [f"ds002785:sub-{i:04d}" for i in range(1, 102)]


def test_levels_are_nested_within_a_fold():
    """작은 수준은 큰 수준의 부분집합이어야 한다 — 이 시험이 설계의 핵심이다."""
    curve = S.subsample_curve(SUBS, outer_fold=0)
    levels = sorted(curve)
    for small, large in zip(levels, levels[1:]):
        assert set(curve[small]) <= set(curve[large])


def test_each_level_has_exactly_the_requested_size():
    curve = S.subsample_curve(SUBS, outer_fold=3)
    for n, chosen in curve.items():
        assert len(chosen) == n
        assert len(set(chosen)) == n


def test_result_is_sorted_and_drawn_from_the_training_set():
    got = S.subsample_train(SUBS, 20, outer_fold=1)
    assert got == sorted(got)
    assert set(got) <= set(SUBS)


def test_same_inputs_give_the_same_subjects():
    assert S.subsample_train(SUBS, 20, outer_fold=1) == \
        S.subsample_train(SUBS, 20, outer_fold=1)


def test_input_order_does_not_change_the_result():
    """호출자가 어떤 순서로 주든 같은 집합이면 같은 결과여야 한다."""
    assert S.subsample_train(SUBS, 20, outer_fold=1) == \
        S.subsample_train(list(reversed(SUBS)), 20, outer_fold=1)


def test_different_folds_draw_different_subjects():
    """모든 fold 가 같은 순서를 쓰면 한 번의 운 나쁜 섞기가 곡선을 기울인다."""
    a = S.subsample_train(SUBS, 20, outer_fold=0)
    b = S.subsample_train(SUBS, 20, outer_fold=1)
    assert a != b


def test_seed_base_changes_the_draw():
    assert S.subsample_train(SUBS, 20, outer_fold=0) != \
        S.subsample_train(SUBS, 20, outer_fold=0, seed_base=S.SUBSAMPLE_SEED_BASE + 1)


def test_seed_is_fold_specific_and_reproducible():
    assert S.subsample_seed(0) == S.SUBSAMPLE_SEED_BASE
    assert S.subsample_seed(4) == S.SUBSAMPLE_SEED_BASE + 4
    with pytest.raises(S.SubsampleError):
        S.subsample_seed(-1)
    with pytest.raises(S.SubsampleError):
        S.subsample_seed(True)


def test_asking_for_more_than_the_training_set_is_refused():
    """조용히 잘라 맞추면 곡선이 거짓말을 한다."""
    with pytest.raises(S.SubsampleError, match="보다 크다"):
        S.subsample_train(SUBS, len(SUBS) + 1, outer_fold=0)


@pytest.mark.parametrize("bad", [0, -3, 2.5, True])
def test_bad_sizes_are_refused(bad):
    with pytest.raises(S.SubsampleError):
        S.subsample_train(SUBS, bad, outer_fold=0)


def test_duplicate_or_empty_training_sets_are_refused():
    with pytest.raises(S.SubsampleError, match="중복"):
        S.subsample_train(SUBS + SUBS[:1], 10, outer_fold=0)
    with pytest.raises(S.SubsampleError, match="비었다"):
        S.subsample_train([], 1, outer_fold=0)


def test_curve_levels_must_be_sorted_and_unique():
    with pytest.raises(S.SubsampleError, match="오름차순"):
        S.subsample_curve(SUBS, outer_fold=0, levels=(20, 10))
    with pytest.raises(S.SubsampleError, match="오름차순"):
        S.subsample_curve(SUBS, outer_fold=0, levels=(10, 10, 20))


def test_locked_levels_fit_inside_the_smallest_outer_training_set():
    """outer fold 의 학습 집합은 100–101 명이다 — 수준이 그 안에 들어가야 한다."""
    assert max(S.LOW_SAMPLE_LEVELS) <= 100
    assert list(S.LOW_SAMPLE_LEVELS) == sorted(set(S.LOW_SAMPLE_LEVELS))


def test_every_chosen_subject_carries_both_classes_by_construction():
    """이 target 은 사람마다 두 run (class 하나씩) 이라 subject 를 뽑으면 균형이다."""
    runs = {s: {"emomatching", "workingmemory"} for s in SUBS}
    chosen = S.subsample_train(SUBS, 10, outer_fold=2)
    assert all(runs[s] == {"emomatching", "workingmemory"} for s in chosen)
