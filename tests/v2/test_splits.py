"""T03 subject isolation + 분할 결정성 — mobse/v2/splits.py."""

from __future__ import annotations

import pytest

from mobse.v2.splits import (
    EXTERNAL_SEED, Group, SplitError, assert_fit_scope, assign_to_folds,
    build_folds, make_groups, order_groups, select_pilot, verify_disjoint,
)


def _subjects(n: int, ds: str = "ds002785") -> list:
    return [f"{ds}:sub-{i:04d}" for i in range(1, n + 1)]


# --------------------------------------------------------------------------- #
# 기본 구조
# --------------------------------------------------------------------------- #

def test_group_rejects_empty_and_duplicates():
    with pytest.raises(SplitError):
        Group("g", ())
    with pytest.raises(SplitError):
        Group("g", ("a", "a"))
    with pytest.raises(SplitError):
        Group("", ("a",))


def test_make_groups_requires_exactly_one_argument():
    with pytest.raises(SplitError):
        make_groups()
    with pytest.raises(SplitError):
        make_groups(subject_to_group={"a": "g"}, subjects=["a"])


def test_make_groups_degenerate_is_one_subject_per_group():
    groups = make_groups(subjects=_subjects(5))
    assert len(groups) == 5
    assert all(g.size == 1 for g in groups)


def test_make_groups_respects_family_mapping():
    mapping = {"ds:s1": "fam1", "ds:s2": "fam1", "ds:s3": "fam2"}
    groups = make_groups(subject_to_group=mapping)
    assert {g.group_id: g.size for g in groups} == {"fam1": 2, "fam2": 1}


# --------------------------------------------------------------------------- #
# 결정성과 배정 규칙
# --------------------------------------------------------------------------- #

def test_ordering_is_size_descending_and_deterministic():
    groups = [Group("a", ("x1",)), Group("b", ("y1", "y2", "y3")),
              Group("c", ("z1", "z2"))]
    ordered = order_groups(groups, seed=20260918)
    assert [g.size for g in ordered] == [3, 2, 1]
    assert [g.group_id for g in order_groups(groups, 20260918)] == \
           [g.group_id for g in ordered]


def test_different_seed_can_change_tie_order_only():
    groups = [Group(f"g{i}", (f"s{i}",)) for i in range(20)]
    a = [g.group_id for g in order_groups(groups, 1)]
    b = [g.group_id for g in order_groups(groups, 2)]
    assert sorted(a) == sorted(b)
    assert a != b, "동률 group 의 tie-break 는 seed 에 따라 달라져야 한다"


def test_assign_to_folds_balances_and_never_splits_groups():
    groups = make_groups(subject_to_group={
        **{f"ds:s{i}": "fam" for i in range(1, 5)},           # 4명짜리 group
        **{f"ds:t{i}": f"solo{i}" for i in range(1, 17)},     # 1명짜리 16개
    })
    fa = assign_to_folds(groups, n_folds=5, seed=20260918)
    assert sum(fa.sizes) == 20
    assert max(fa.sizes) - min(fa.sizes) <= 4    # 가장 큰 group 크기 이내
    fam_folds = [k for k, gs in enumerate(fa.fold_groups) if "fam" in gs]
    assert len(fam_folds) == 1, "group 이 두 fold 에 쪼개졌다"


def test_assign_to_folds_refuses_to_shrink():
    groups = make_groups(subjects=_subjects(3))
    with pytest.raises(SplitError, match="자동 축소"):
        assign_to_folds(groups, n_folds=5, seed=1)


def test_fold_assignment_is_reproducible():
    groups = make_groups(subjects=_subjects(50))
    a = assign_to_folds(groups, 5, 20260918)
    b = assign_to_folds(groups, 5, 20260918)
    assert a.fold_subjects == b.fold_subjects


# --------------------------------------------------------------------------- #
# pilot
# --------------------------------------------------------------------------- #

def test_pilot_target_is_min_32_and_floor_20_percent():
    assert select_pilot(make_groups(subjects=_subjects(164))).target == 32
    assert select_pilot(make_groups(subjects=_subjects(100))).target == 20
    assert select_pilot(make_groups(subjects=_subjects(7))).target == 1


def test_pilot_never_exceeds_target_and_keeps_groups_whole():
    mapping = {f"ds:s{i}": f"fam{i // 5}" for i in range(50)}   # 5명짜리 group 10개
    groups = make_groups(subject_to_group=mapping)
    pilot = select_pilot(groups)
    assert pilot.target == 10
    assert pilot.n <= pilot.target
    assert pilot.n % 5 == 0, "group 이 쪼개졌다"


def test_pilot_records_shortfall_reason():
    mapping = {f"ds:s{i}": "one_big" for i in range(10)}
    pilot = select_pilot(make_groups(subject_to_group=mapping))
    assert pilot.n == 0
    assert pilot.shortfall_reason is not None


# --------------------------------------------------------------------------- #
# T03 — subject isolation
# --------------------------------------------------------------------------- #

def test_build_folds_boundaries_are_all_disjoint():
    manifest = build_folds(make_groups(subjects=_subjects(164)))
    pilot = set(manifest["pilot"]["subjects"])
    for outer in manifest["outer_folds"]:
        test = set(outer["test_subjects"])
        train = set(outer["train_subjects"])
        assert not (test & train)
        assert not (test & pilot) and not (train & pilot)
        for inner in outer["inner"]:
            val = set(inner["val_subjects"])
            tr = set(inner["train_subjects"])
            assert not (val & tr)
            assert not (val & test) and not (tr & test)
            assert not (val & pilot) and not (tr & pilot)
            assert val | tr == train


def test_every_main_subject_is_in_exactly_one_outer_test_fold():
    manifest = build_folds(make_groups(subjects=_subjects(164)))
    seen = [s for o in manifest["outer_folds"] for s in o["test_subjects"]]
    assert len(seen) == len(set(seen))
    assert set(seen) == set(manifest["main_pool"]["subjects"])


def test_assert_fit_scope_rejects_forbidden_subject():
    manifest = build_folds(make_groups(subjects=_subjects(164)))
    outer = manifest["outer_folds"][0]
    allowed = outer["inner"][0]["train_subjects"]
    assert_fit_scope(allowed, allowed)                      # 통과해야 한다
    intruder = outer["test_subjects"][0]
    with pytest.raises(SplitError, match="허용되지 않은"):
        assert_fit_scope(allowed, list(allowed) + [intruder])
    pilot_subject = manifest["pilot"]["subjects"][0]
    with pytest.raises(SplitError):
        assert_fit_scope(allowed, list(allowed) + [pilot_subject])


def test_verify_disjoint_raises_on_overlap():
    with pytest.raises(SplitError, match="교집합"):
        verify_disjoint({"a": ["s1", "s2"], "b": ["s2"]})


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #

def test_manifest_hash_is_stable_and_content_bound():
    g = make_groups(subjects=_subjects(164))
    m1 = build_folds(g)
    m2 = build_folds(g)
    assert m1["split_hash"] == m2["split_hash"]
    m3 = build_folds(make_groups(subjects=_subjects(163)))
    assert m3["split_hash"] != m1["split_hash"]


def test_manifest_records_seeds_and_grouping_assumption():
    m = build_folds(make_groups(subjects=_subjects(164)))
    assert m["seeds"] == {"pilot": 20260917, "outer": 20260918,
                          "inner_base": 20261000, "external": EXTERNAL_SEED}
    assert "no family/duplicate metadata" in m["grouping_assumption"]
    assert m["outer_folds"][2]["inner"][0]["seed"] == 20261002


def test_families_never_straddle_outer_folds():
    mapping = {f"ds:s{i}": f"fam{i // 2}" for i in range(160)}   # 2명짜리 group 80개
    manifest = build_folds(make_groups(subject_to_group=mapping))
    for outer in manifest["outer_folds"]:
        test = set(outer["test_subjects"])
        for i in range(0, 160, 2):
            pair = {f"ds:s{i}", f"ds:s{i+1}"}
            assert pair <= test or not (pair & test), \
                "가족이 outer test 경계를 가로질렀다"
