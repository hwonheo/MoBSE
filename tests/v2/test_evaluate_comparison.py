"""보조 비교 칸(S·NG·SG) outer 예측 집계 — 남은 작업 2-c (09-25 13:15).

계획서 §8: 각 window 의 seed 평균 → task 의 네 window 평균, threshold 0.5 (동일값
class 1), subject b_i. 보조 contrast 는 §8 이 이름으로 정한 A−S 만.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mobse.v2 import baselines as BL
from mobse.v2 import train as TR
from mobse.v2.evaluate import (
    CELLS, COMPARISON_CELLS, COMPARISON_CONTRASTS, ComparisonWindowPrediction,
    EvaluationError, WindowPrediction, aggregate_comparison_runs, aggregate_runs,
    cell_balanced_accuracy, comparison_contrasts,
)

TASKS = ("emomatching", "workingmemory")
PLAN = Path(__file__).resolve().parents[2] / "docs" / "experiments" / \
    "mobse_redesign_protocol_2026-09-17.md"


def _cmp(cell, seeds_by_subject, *, p_by=None, truth=1, skip=None):
    """``p_by[(subject, task)]`` 가 있으면 window×seed 전부 그 확률."""
    out = []
    for subject, seeds in seeds_by_subject.items():
        for task in TASKS:
            for w in range(4):
                for s in seeds:
                    if skip and skip(subject, task, w, s):
                        continue
                    p = (p_by or {}).get((subject, task), 0.9)
                    out.append(ComparisonWindowPrediction(
                        canonical_subject=subject, group_id=f"g-{subject}", task=task,
                        window_index=w, model_seed=s, cell=cell, truth=truth,
                        p_class1=p))
    return out


def _ad(subjects, *, p_by=None):
    out = []
    for c in CELLS:
        for subject in subjects:
            for task in TASKS:
                for w in range(4):
                    for s in TR.MODEL_SEEDS:
                        p = (p_by or {}).get((c, subject, task), 0.9)
                        out.append(WindowPrediction(
                            canonical_subject=subject, group_id=f"g-{subject}",
                            task=task, window_index=w, model_seed=s, cell=c,
                            truth=1, p_class1=p))
    return out


MIXED = {"s1": (None,), "s2": TR.MODEL_SEEDS, "s3": (None,)}


def test_names_match_baselines_and_plan():
    assert COMPARISON_CELLS == ("S",) + tuple(BL.COMPARATOR_ORDER)
    assert COMPARISON_CONTRASTS == ("A_minus_S",)
    assert "A−S" in PLAN.read_text(encoding="utf-8")


def test_mixed_logistic_and_mlp_subjects_hand_computed():
    # s2 (MLP, 3 seeds): window 0 seed 확률 0.2/0.5/0.8 → 0.5, 나머지 window 0.1
    def p_of(subject, task, w, s):
        if subject == "s2" and task == "emomatching":
            return {42: 0.2, 43: 0.5, 44: 0.8}[s] if w == 0 else 0.1
        return 0.9
    preds = [ComparisonWindowPrediction(
        canonical_subject=p.canonical_subject, group_id=p.group_id, task=p.task,
        window_index=p.window_index, model_seed=p.model_seed, cell="S", truth=1,
        p_class1=p_of(p.canonical_subject, p.task, p.window_index, p.model_seed))
        for p in _cmp("S", MIXED)]
    runs = aggregate_comparison_runs(preds, cell="S", seeds_by_subject=MIXED)
    assert len(runs) == 6
    r = runs[("S", "s2", "emomatching")]
    assert r["p"] == pytest.approx((0.5 + 0.1 * 3) / 4)
    assert r["n_seeds"] == 3 and r["prediction"] == 0 and r["correct"] is False
    assert runs[("S", "s1", "emomatching")]["n_seeds"] == 1
    # b: s1 1.0, s2 0.5, s3 1.0 → BA 2.5/3
    assert cell_balanced_accuracy(runs, "S") == pytest.approx(2.5 / 3)


def test_tie_at_threshold_is_class_one():
    seeds = {"s1": (None,)}
    runs = aggregate_comparison_runs(
        _cmp("S", seeds, p_by={("s1", "emomatching"): 0.5}, truth=1),
        cell="S", seeds_by_subject=seeds)
    assert runs[("S", "s1", "emomatching")]["prediction"] == 1


def test_ng_three_seeds_recorded():
    seeds = {"s1": TR.MODEL_SEEDS, "s2": TR.MODEL_SEEDS}
    runs = aggregate_comparison_runs(_cmp("NG", seeds), cell="NG",
                                     seeds_by_subject=seeds)
    assert {r["n_seeds"] for r in runs.values()} == {3}


def test_seed_set_must_match_exactly_not_just_count():
    seeds = {"s1": TR.MODEL_SEEDS}
    preds = _cmp("SG", {"s1": (42, 43, 45)})
    with pytest.raises(EvaluationError, match="≠ 기대"):
        aggregate_comparison_runs(preds, cell="SG", seeds_by_subject=seeds)


def test_missing_seed_fails():
    preds = _cmp("S", MIXED, skip=lambda sub, t, w, s: sub == "s2" and s == 44)
    with pytest.raises(EvaluationError, match="≠ 기대"):
        aggregate_comparison_runs(preds, cell="S", seeds_by_subject=MIXED)


def test_missing_window_fails():
    preds = _cmp("S", MIXED, skip=lambda sub, t, w, s: sub == "s1" and w == 3)
    with pytest.raises(EvaluationError, match="window 3/4"):
        aggregate_comparison_runs(preds, cell="S", seeds_by_subject=MIXED)


def test_one_missing_window_seed_cell_fails():
    preds = _cmp("NG", {"s1": TR.MODEL_SEEDS},
                 skip=lambda sub, t, w, s: w == 2 and s == 43)
    with pytest.raises(EvaluationError, match="빠진"):
        aggregate_comparison_runs(preds, cell="NG",
                                  seeds_by_subject={"s1": TR.MODEL_SEEDS})


def test_duplicate_prediction_fails():
    preds = _cmp("S", MIXED)
    with pytest.raises(EvaluationError, match="중복 예측"):
        aggregate_comparison_runs(preds + [preds[0]], cell="S", seeds_by_subject=MIXED)


def test_subject_set_must_equal_seed_map():
    preds = _cmp("S", MIXED)
    with pytest.raises(EvaluationError, match="누락 \\['s4'\\]"):
        aggregate_comparison_runs(preds, cell="S",
                                  seeds_by_subject={**MIXED, "s4": (None,)})
    with pytest.raises(EvaluationError, match="추가 \\['s3'\\]"):
        aggregate_comparison_runs(preds, cell="S",
                                  seeds_by_subject={"s1": (None,), "s2": TR.MODEL_SEEDS})


def test_cells_must_not_mix_and_must_be_known():
    preds = _cmp("S", {"s1": (None,)}) + _cmp("NG", {"s1": TR.MODEL_SEEDS})
    with pytest.raises(EvaluationError, match="칸이 섞였다"):
        aggregate_comparison_runs(preds, cell="S", seeds_by_subject={"s1": (None,)})
    with pytest.raises(EvaluationError, match="알 수 없는 보조 비교 칸: 'A'"):
        aggregate_comparison_runs([], cell="A", seeds_by_subject={})
    with pytest.raises(EvaluationError, match="알 수 없는 보조 비교 칸: 'B'"):
        _cmp("B", {"s1": (42,)})


def test_prediction_types_do_not_cross():
    ad = _ad(["s1"])
    with pytest.raises(EvaluationError, match="ComparisonWindowPrediction 만"):
        aggregate_comparison_runs(ad[:1], cell="S", seeds_by_subject={"s1": (42,)})
    with pytest.raises(EvaluationError, match="WindowPrediction 만"):
        aggregate_runs(ad + _cmp("NG", {"s1": TR.MODEL_SEEDS}))


def test_seedless_only_for_s_logistic_alone():
    with pytest.raises(EvaluationError, match="seed 없는 예측은 S"):
        _cmp("NG", {"s1": (None,)})
    preds = _cmp("S", {"s1": (None,)})
    with pytest.raises(EvaluationError, match="S logistic 단독만"):
        aggregate_comparison_runs(preds, cell="S", seeds_by_subject={"s1": (None, 42)})
    with pytest.raises(EvaluationError, match="S logistic 단독만"):
        aggregate_comparison_runs(_cmp("SG", {"s1": (42,)}), cell="SG",
                                  seeds_by_subject={"s1": (None,)})


def test_seed_list_empty_or_duplicate_rejected():
    preds = _cmp("NG", {"s1": (42,)})
    with pytest.raises(EvaluationError, match="비었거나 중복"):
        aggregate_comparison_runs(preds, cell="NG", seeds_by_subject={"s1": ()})
    with pytest.raises(EvaluationError, match="비었거나 중복"):
        aggregate_comparison_runs(preds, cell="NG", seeds_by_subject={"s1": (42, 42)})


def test_a_minus_s_is_within_subject_hand_computed():
    subs = ["s1", "s2", "s3"]
    ad_runs = aggregate_runs(_ad(subs, p_by={("A", "s3", "workingmemory"): 0.1}))
    s_runs = aggregate_comparison_runs(
        _cmp("S", MIXED, p_by={("s1", "emomatching"): 0.2,
                               ("s2", "emomatching"): 0.2,
                               ("s2", "workingmemory"): 0.2}),
        cell="S", seeds_by_subject=MIXED)
    got = comparison_contrasts(ad_runs, s_runs)
    assert set(got) == set(COMPARISON_CONTRASTS)
    # A: s1 1, s2 1, s3 0.5 / S: s1 0.5, s2 0, s3 1
    assert got["A_minus_S"] == pytest.approx({"s1": 0.5, "s2": 1.0, "s3": -0.5})


def test_a_minus_s_rejects_unpaired_subjects():
    ad_runs = aggregate_runs(_ad(["s1", "s2"]))
    seeds = {"s1": (None,), "s3": (None,)}
    s_runs = aggregate_comparison_runs(_cmp("S", seeds), cell="S",
                                       seeds_by_subject=seeds)
    with pytest.raises(EvaluationError, match="paired 불가"):
        comparison_contrasts(ad_runs, s_runs)


def test_ad_aggregation_still_counts_seeds_only():
    # 기존 동작 불변: A–D 는 seed 개수만 본다 (seed 값 45 허용 — 거부는 CLI 몫)
    preds = [WindowPrediction(canonical_subject="s1", group_id="g", task=t,
                              window_index=w, model_seed=s, cell=c, truth=1,
                              p_class1=0.9)
             for c in CELLS for t in TASKS for w in range(4) for s in (42, 43, 45)]
    runs = aggregate_runs(preds)
    assert {r["n_seeds"] for r in runs.values()} == {3}
