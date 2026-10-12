"""결정 17 — 외부 최종 선택 3-fold 를 별도 파생 산출물 `external_folds.json` 으로 고정.

`folds.json`·`build_folds` 는 불변 (split_hash 그대로). 외부 분할은 main pool 에
`assign_to_folds(…, 3, 20262000)` 를 적용하고, 부모 split_hash 와 자체 hash 를 가진다.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from mobse.v2 import fitting as FIT
from mobse.v2 import locks as L
from mobse.v2 import templates as T
from mobse.v2.splits import (EXTERNAL_SEED, SplitError, assign_to_folds, build_external_folds,
                             build_folds, external_invariants, external_split_hash,
                             failed_external_invariants, make_groups)


def _groups(n=157, prefix="ds002785"):
    return make_groups(subjects=[f"{prefix}:sub-{i:04d}" for i in range(1, n + 1)])


@pytest.fixture(scope="module")
def built():
    groups = _groups()
    folds = build_folds(groups)
    return groups, folds, build_external_folds(groups, folds)


# --------------------------------------------------------------------------- #
# 분할
# --------------------------------------------------------------------------- #


def test_sizes_are_42_42_42_and_partition_main_pool(built):
    _, folds, ext = built
    assert folds["pilot"]["n"] == 31 and folds["main_pool"]["n_subjects"] == 126
    vals = [set(i["val_subjects"]) for i in ext["inner"]]
    assert [len(v) for v in vals] == [42, 42, 42]
    assert set().union(*vals) == set(folds["main_pool"]["subjects"])
    assert not (vals[0] & vals[1] or vals[0] & vals[2] or vals[1] & vals[2])
    for i, v in zip(ext["inner"], vals):
        assert set(i["train_subjects"]) == set(folds["main_pool"]["subjects"]) - v
        assert len(i["train_subjects"]) == 84


def test_pilot_is_absent_from_every_external_fold(built):
    _, folds, ext = built
    pilot = set(folds["pilot"]["subjects"])
    for i in ext["inner"]:
        assert not pilot & (set(i["val_subjects"]) | set(i["train_subjects"]))


def test_uses_protocol_seed_and_same_algorithm_as_assign_to_folds(built):
    groups, folds, ext = built
    assert ext["seed"] == EXTERNAL_SEED == 20262000 == folds["seeds"]["external"]
    pool = [g for g in groups if g.group_id not in set(folds["pilot"]["groups"])]
    ref = assign_to_folds(pool, 3, EXTERNAL_SEED)
    assert [tuple(i["val_subjects"]) for i in ext["inner"]] == list(ref.fold_subjects)
    assert [i["inner_fold"] for i in ext["inner"]] == [0, 1, 2]
    assert all(i["seed"] == EXTERNAL_SEED for i in ext["inner"])


def test_is_deterministic(built):
    groups, folds, ext = built
    assert build_external_folds(groups, folds) == ext


def test_other_seed_gives_other_boundaries(built):
    groups, folds, ext = built
    other = build_external_folds(groups, folds, seed=EXTERNAL_SEED + 1)
    assert [i["val_subjects"] for i in other["inner"]] != [i["val_subjects"] for i in ext["inner"]]


def test_parent_folds_and_split_hash_are_untouched(built):
    groups, folds, _ = built
    before = copy.deepcopy(folds)
    build_external_folds(groups, folds)
    assert folds == before
    assert build_folds(groups)["split_hash"] == folds["split_hash"]
    assert "external_inner" not in folds and "external" not in json.dumps(
        folds["outer_folds"])


def test_records_parent_split_hash_and_own_hash(built):
    _, folds, ext = built
    assert ext["parent_split_hash"] == folds["split_hash"]
    assert ext["external_split_hash"] == external_split_hash(ext)
    body = {k: v for k, v in ext.items() if k != "external_split_hash"}
    assert ext["external_split_hash"] == hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def test_groups_from_another_cohort_are_refused(built):
    _, folds, _ = built
    with pytest.raises(SplitError, match="main pool"):
        build_external_folds(_groups(158), folds)


def test_malformed_parent_is_refused(built):
    groups, folds, _ = built
    bad = dict(folds)
    bad.pop("split_hash")
    with pytest.raises(SplitError, match="구조"):
        build_external_folds(groups, bad)
    bad2 = dict(folds, split_hash="abc")
    with pytest.raises(SplitError, match="split_hash"):
        build_external_folds(groups, bad2)


# --------------------------------------------------------------------------- #
# 불변식
# --------------------------------------------------------------------------- #


def test_invariants_all_true(built):
    _, folds, ext = built
    inv = external_invariants(ext, folds)
    assert failed_external_invariants(inv) == []
    assert inv["val_sizes"] == [42, 42, 42]


def _rehash(ext):
    ext["external_split_hash"] = external_split_hash(ext)
    return ext


@pytest.mark.parametrize("tamper, expect", [
    (lambda e, f: e.__setitem__("parent_split_hash", "0" * 64), "parent_split_hash_matches"),
    (lambda e, f: e["inner"][0]["val_subjects"].append(f["pilot"]["subjects"][0]), "pilot_absent"),
    (lambda e, f: e["inner"][1]["val_subjects"].append(e["inner"][0]["val_subjects"][0]),
     "val_mutually_disjoint"),
    (lambda e, f: e["inner"][2]["val_subjects"].pop(), "val_union_is_main_pool"),
    (lambda e, f: e["inner"][0]["train_subjects"].pop(), "train_is_main_pool_minus_val"),
    (lambda e, f: e.__setitem__("seed", 1), "seed_is_parent_external_seed"),
    (lambda e, f: e["inner"][1].__setitem__("seed", 7), "inner_seeds_match"),
    (lambda e, f: e["inner"][2].__setitem__("inner_fold", 5), "inner_fold_ids_are_0_to_n"),
    (lambda e, f: e.__setitem__("schema_version", "x"), "schema_version_valid"),
])
def test_each_invariant_catches_its_tamper(built, tamper, expect):
    _, folds, ext = built
    e = copy.deepcopy(ext)
    tamper(e, folds)
    _rehash(e)
    assert expect in failed_external_invariants(external_invariants(e, folds))


def test_edit_without_rehash_is_caught(built):
    _, folds, ext = built
    e = copy.deepcopy(ext)
    e["note"] = "바꿈"
    assert failed_external_invariants(external_invariants(e, folds)) == [
        "external_split_hash_recomputes"]


def test_missing_structure_is_a_failure_not_a_crash(built):
    _, folds, ext = built
    e = copy.deepcopy(ext)
    e.pop("inner")
    assert "structure_valid" in failed_external_invariants(external_invariants(e, folds))


# --------------------------------------------------------------------------- #
# resolve_fold_subjects(9, j)
# --------------------------------------------------------------------------- #


def test_external_outer_fold_constant_is_nine():
    assert T.EXTERNAL_OUTER_FOLD == 9 == T.OUTER_FIT_INNER_FOLD


@pytest.mark.parametrize("j", [0, 1, 2])
def test_resolve_external_inner(built, j):
    _, folds, ext = built
    fs = FIT.resolve_fold_subjects(folds, 9, j, external_folds=ext)
    assert fs.role == FIT.ROLE_INNER and fs.eval_role == "inner_validation"
    assert (fs.outer_fold, fs.inner_fold) == (9, j)
    assert fs.evaluate == tuple(ext["inner"][j]["val_subjects"])
    assert fs.train == tuple(ext["inner"][j]["train_subjects"])
    assert len(fs.train) == 84 and len(fs.evaluate) == 42


def test_resolve_external_without_file_is_refused(built):
    _, folds, _ = built
    with pytest.raises(FIT.FitError, match="external_folds.json 이 필요하다"):
        FIT.resolve_fold_subjects(folds, 9, 0)


def test_resolve_external_final_is_refused(built):
    _, folds, ext = built
    with pytest.raises(FIT.FitError, match="external final"):
        FIT.resolve_fold_subjects(folds, 9, 9, external_folds=ext)


def test_resolve_refuses_parent_split_hash_mismatch(built):
    _, folds, ext = built
    other = dict(folds, split_hash="f" * 64)
    with pytest.raises(FIT.FitError, match="parent_split_hash_matches"):
        FIT.resolve_fold_subjects(other, 9, 0, external_folds=ext)


def test_resolve_refuses_tampered_external(built):
    _, folds, ext = built
    e = copy.deepcopy(ext)
    e["inner"][0]["train_subjects"].append(folds["pilot"]["subjects"][0])
    _rehash(e)
    with pytest.raises(FIT.FitError, match="맞지 않는다"):
        FIT.resolve_fold_subjects(folds, 9, 0, external_folds=e)


def test_resolve_refuses_unknown_external_inner(built):
    _, folds, ext = built
    with pytest.raises(FIT.FitError, match="inner fold 3"):
        FIT.resolve_fold_subjects(folds, 9, 3, external_folds=ext)


def test_resolve_main_folds_ignore_external(built):
    _, folds, ext = built
    a = FIT.resolve_fold_subjects(folds, 0, 1)
    b = FIT.resolve_fold_subjects(folds, 0, 1, external_folds=ext)
    assert a == b
    assert a.train == tuple(folds["outer_folds"][0]["inner"][1]["train_subjects"])


# --------------------------------------------------------------------------- #
# 잠금
# --------------------------------------------------------------------------- #


def _lock(tmp_path, built, *, ext_override=None, with_ext=True):
    _, folds, ext = built
    data, repo = tmp_path / "data", tmp_path / "repo"
    (data / "co").mkdir(parents=True)
    repo.mkdir()
    folds_p = data / "co" / "folds.json"
    folds_p.write_text(json.dumps(folds), encoding="utf-8")
    ext_p = data / "co" / "external_folds.json"
    ext_p.write_text(json.dumps(ext), encoding="utf-8")
    subj_p = data / "co" / "subjects.jsonl"
    elig = folds["pilot"]["subjects"] + folds["main_pool"]["subjects"]
    subj_p.write_text("".join(json.dumps({"canonical_subject": s, "eligible": True}) + "\n"
                              for s in elig), encoding="utf-8")
    cohort = {"subjects": L.file_record(subj_p, base=data),
              "folds": L.file_record(folds_p, base=data, split_hash=folds["split_hash"],
                                     invariants=L.fold_invariants(folds, elig))}
    if with_ext:
        cohort["external_folds"] = L.file_record(
            ext_p, base=data, external_split_hash=ext["external_split_hash"],
            parent_split_hash=ext["parent_split_hash"],
            invariants=external_invariants(ext, folds))
    body = {"schema_version": L.SCHEMA_VERSION, "cohorts": {"piop1": cohort},
            "environment": {}}
    body["lock_hash"] = L.lock_hash(body)
    if ext_override is not None:
        ext_p.write_text(json.dumps(ext_override), encoding="utf-8")
    return L.verify_lock(body, roots={"data_root": data, "repo_root": repo})


def test_lock_verifies_external_folds(tmp_path, built):
    res = _lock(tmp_path, built)
    assert L.lock_is_clean(res), res
    assert any(s.startswith("cohorts/piop1/external_folds: 불변식") for s in res["ok"])
    assert any("external_folds.json" in s for s in res["ok"])


def test_lock_without_external_record_is_not_clean(tmp_path, built):
    res = _lock(tmp_path, built, with_ext=False)
    assert any("external_folds" in s for s in res["missing"])
    assert not L.lock_is_clean(res)


def test_lock_recomputes_external_invariants(tmp_path, built):
    _, folds, ext = built
    e = copy.deepcopy(ext)
    e["inner"][0]["val_subjects"].append(folds["pilot"]["subjects"][0])
    res = _lock(tmp_path, built, ext_override=_rehash(e))
    assert any("pilot_absent" in s for s in res["invariant"]), res
    assert any("external_split_hash" in s for s in res["mismatch"]), res
