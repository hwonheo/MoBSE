"""T13 endpoint 손계산 + T14 통계 단위 — mobse/v2/statistics.py."""

from __future__ import annotations

import numpy as np
import pytest

from mobse.v2.statistics import (
    FAMILYWISE_PCT, NOMINAL_PCT, StatisticsError, balanced_accuracy,
    bootstrap_indices, classify, interpret, paired_bootstrap, paired_difference,
    run_probability, subject_score,
)


# --------------------------------------------------------------------------- #
# T13 — 손계산 fixture
# --------------------------------------------------------------------------- #

def test_run_probability_averages_seeds_then_windows():
    # 4 windows x 3 seeds. window 평균: 0.2, 0.5, 0.8, 0.9 -> run 평균 0.6
    probs = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9], [0.9, 0.9, 0.9]]
    assert run_probability(probs) == pytest.approx(0.6)


def test_run_probability_rejects_incomplete_input():
    with pytest.raises(StatisticsError, match="모양"):
        run_probability([[0.5, 0.5, 0.5]] * 3)            # window 3개
    with pytest.raises(StatisticsError, match="모양"):
        run_probability([[0.5, 0.5]] * 4)                 # seed 2개
    with pytest.raises(StatisticsError, match="비유한"):
        run_probability([[float("nan"), 0.5, 0.5]] + [[0.5] * 3] * 3)
    with pytest.raises(StatisticsError, match=r"\[0, 1\]"):
        run_probability([[1.5, 0.5, 0.5]] + [[0.5] * 3] * 3)


def test_threshold_tie_goes_to_class_one():
    assert classify(0.5) == 1
    assert classify(0.5 - 1e-12) == 0
    assert classify(0.0) == 0 and classify(1.0) == 1


def test_subject_score_and_ba_hand_computed():
    # subject A: emo 맞음, WM 틀림 -> 0.5 / subject B: 둘 다 맞음 -> 1.0
    a = subject_score(True, False)
    b = subject_score(True, True)
    assert (a, b) == (0.5, 1.0)
    assert balanced_accuracy([a, b]) == pytest.approx(0.75)


def test_full_endpoint_chain_two_subjects():
    """2 subject x 2 task x 4 window x 3 seed 를 손으로 따라간 값과 맞춘다."""
    # s1/emo: 모든 window·seed 0.9 -> run p 0.9 -> class 1
    # s1/wm : 모든 값 0.5           -> run p 0.5 -> class 1 (동일값 규칙)
    # s2/emo: 모든 값 0.4           -> run p 0.4 -> class 0
    # s2/wm : 모든 값 0.8           -> run p 0.8 -> class 1
    flat = lambda v: [[v] * 3 for _ in range(4)]
    p = {("s1", "emo"): run_probability(flat(0.9)),
         ("s1", "wm"): run_probability(flat(0.5)),
         ("s2", "emo"): run_probability(flat(0.4)),
         ("s2", "wm"): run_probability(flat(0.8))}
    assert p[("s1", "wm")] == pytest.approx(0.5)
    truth = {("s1", "emo"): 1, ("s1", "wm"): 1, ("s2", "emo"): 1, ("s2", "wm"): 1}
    correct = {k: classify(v) == truth[k] for k, v in p.items()}
    assert correct == {("s1", "emo"): True, ("s1", "wm"): True,
                       ("s2", "emo"): False, ("s2", "wm"): True}
    b = {"s1": subject_score(correct[("s1", "emo")], correct[("s1", "wm")]),
         "s2": subject_score(correct[("s2", "emo")], correct[("s2", "wm")])}
    assert b == {"s1": 1.0, "s2": 0.5}
    assert balanced_accuracy(list(b.values())) == pytest.approx(0.75)


def test_paired_difference_is_within_subject():
    a = {"s1": 1.0, "s2": 0.5, "s3": 0.0}
    b = {"s1": 0.5, "s2": 0.5, "s3": 0.5}
    assert paired_difference(a, b) == pytest.approx((0.5 + 0.0 - 0.5) / 3)


def test_paired_difference_requires_identical_subject_sets():
    with pytest.raises(StatisticsError, match="paired"):
        paired_difference({"s1": 1.0}, {"s2": 1.0})


# --------------------------------------------------------------------------- #
# T14 — 통계 단위와 bootstrap index
# --------------------------------------------------------------------------- #

def _degenerate(subjects):
    return {s: s for s in subjects}


def test_bootstrap_resamples_groups_not_subjects():
    """가족 fixture: 같은 group 의 subject 는 항상 함께 뽑히거나 함께 빠진다."""
    subjects = [f"s{i}" for i in range(8)]
    mapping = {s: f"fam{i // 2}" for i, s in enumerate(subjects)}   # 2명씩 4 group
    idx = bootstrap_indices(mapping, subjects, seed=9001, n_boot=200)
    for draw in idx:
        counts = np.bincount(draw, minlength=len(subjects))
        for g in range(4):
            assert counts[2 * g] == counts[2 * g + 1], \
                "group 의 두 subject 가 서로 다른 횟수로 뽑혔다"


def test_bootstrap_draw_size_equals_subject_count_for_equal_groups():
    subjects = [f"s{i}" for i in range(8)]
    mapping = {s: f"fam{i // 2}" for i, s in enumerate(subjects)}
    for draw in bootstrap_indices(mapping, subjects, seed=9001, n_boot=50):
        assert len(draw) == len(subjects)


def test_same_indices_applied_to_all_cells_preserves_pairing():
    subjects = [f"s{i}" for i in range(20)]
    mapping = _degenerate(subjects)
    idx = bootstrap_indices(mapping, sorted(subjects), seed=9001, n_boot=500)
    a = {s: 1.0 for s in subjects}
    b = {s: 0.5 for s in subjects}
    ra = paired_bootstrap(a, mapping, indices=idx)
    rb = paired_bootstrap(b, mapping, indices=idx)
    # 모든 subject 의 차이가 상수 0.5 이므로, 같은 재표집을 쓰면 차이도 상수여야 한다
    diff = {s: a[s] - b[s] for s in subjects}
    rd = paired_bootstrap(diff, mapping, indices=idx)
    assert rd.lo == pytest.approx(0.5) and rd.hi == pytest.approx(0.5)
    assert ra.point - rb.point == pytest.approx(rd.point)


def test_n_is_subjects_never_windows_or_seeds():
    subjects = [f"s{i}" for i in range(12)]
    mapping = {s: f"fam{i // 3}" for i, s in enumerate(subjects)}   # 3명씩 4 group
    r = paired_bootstrap({s: 0.1 for s in subjects}, mapping, n_boot=100)
    assert r.n_subjects == 12
    assert r.n_groups == 4
    assert "subject" in r.unit
    d = r.as_dict()
    assert d["n_subjects"] == 12 and d["statistical_unit"] == r.unit


def test_bootstrap_is_reproducible_and_seed_sensitive():
    subjects = [f"s{i}" for i in range(30)]
    mapping = _degenerate(subjects)
    vals = {s: float(i % 3) / 2 for i, s in enumerate(subjects)}
    r1 = paired_bootstrap(vals, mapping, seed=9001, n_boot=300)
    r2 = paired_bootstrap(vals, mapping, seed=9001, n_boot=300)
    r3 = paired_bootstrap(vals, mapping, seed=9002, n_boot=300)
    assert (r1.lo, r1.hi) == (r2.lo, r2.hi)
    assert (r1.lo, r1.hi) != (r3.lo, r3.hi)


def test_familywise_percentiles_are_wider_than_nominal():
    subjects = [f"s{i}" for i in range(40)]
    mapping = _degenerate(subjects)
    vals = {s: float((i * 7) % 5) / 4 for i, s in enumerate(subjects)}
    idx = bootstrap_indices(mapping, sorted(subjects), seed=9001, n_boot=2000)
    fam = paired_bootstrap(vals, mapping, indices=idx, pct=FAMILYWISE_PCT)
    nom = paired_bootstrap(vals, mapping, indices=idx, pct=NOMINAL_PCT)
    assert fam.lo <= nom.lo and fam.hi >= nom.hi
    assert fam.pct == (1.25, 98.75) and nom.pct == (2.5, 97.5)


def test_missing_group_mapping_fails_loudly():
    with pytest.raises(StatisticsError, match="group 매핑"):
        paired_bootstrap({"s1": 0.1, "s2": 0.2}, {"s1": "g1"}, n_boot=10)


def test_empty_input_fails():
    with pytest.raises(StatisticsError):
        paired_bootstrap({}, {}, n_boot=10)
    with pytest.raises(StatisticsError):
        balanced_accuracy([])


# --------------------------------------------------------------------------- #
# 판정 규칙
# --------------------------------------------------------------------------- #

def test_interpretation_follows_protocol_rules():
    subjects = [f"s{i}" for i in range(50)]
    mapping = _degenerate(subjects)

    strong = paired_bootstrap({s: 0.10 for s in subjects}, mapping, n_boot=200)
    assert "delta" in interpret(strong) and "우월성 지지" in interpret(strong)

    tiny = paired_bootstrap({s: 0.005 for s in subjects}, mapping, n_boot=200)
    assert "실질적 우월성 확정은 아님" in interpret(tiny)

    mixed = {s: (0.5 if i % 2 else -0.5) for i, s in enumerate(subjects)}
    null = paired_bootstrap(mixed, mapping, n_boot=200)
    assert "불확실" in interpret(null)
    assert "효과 없음" in interpret(null)   # 비유의를 효과 없음으로 바꾸지 않는다는 문구
