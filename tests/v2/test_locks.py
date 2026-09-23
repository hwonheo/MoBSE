"""측정 잠금 — `mobse/v2/locks.py` (지침서 WI-03 / gate G1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mobse.v2 import locks as L


# --------------------------------------------------------------------------- #
# fixture — 작은 folds 구조
# --------------------------------------------------------------------------- #


def _subjects(n, start=1):
    return [f"ds002785:sub-{i:04d}" for i in range(start, start + n)]


def _folds(pilot, pool, n_outer=2, n_inner=2):
    outer = []
    for i in range(n_outer):
        test = pool[i::n_outer]
        train = [s for s in pool if s not in test]
        inner = []
        for j in range(n_inner):
            val = train[j::n_inner]
            inner.append({"inner_fold": j,
                          "val_subjects": val,
                          "train_subjects": [s for s in train if s not in val]})
        outer.append({"outer_fold": i, "test_subjects": test,
                      "train_subjects": train, "inner": inner})
    return {
        "pilot": {"subjects": pilot, "n": len(pilot), "target": len(pilot)},
        "main_pool": {"subjects": pool, "n_subjects": len(pool)},
        "outer_folds": outer,
        "split_hash": "a" * 64, "config_hash": "85556f56",
        "seeds": {"pilot": 20260917, "outer": 20260918},
        "subjects_manifest_sha256": "b" * 64,
    }


@pytest.fixture
def good():
    pilot = _subjects(4, 1)
    pool = _subjects(12, 5)
    return pilot, pool, _folds(pilot, pool)


# --------------------------------------------------------------------------- #
# 불변식
# --------------------------------------------------------------------------- #


def test_invariants_all_true_on_a_valid_split(good):
    pilot, pool, folds = good
    inv = L.fold_invariants(folds, pilot + pool)
    assert L.failed_invariants(inv) == []
    assert inv["n_pilot"] == 4 and inv["n_main_pool"] == 12 and inv["n_eligible"] == 16
    assert sum(inv["outer_test_sizes"]) == 12


def test_pilot_leaking_into_a_fold_is_caught(good):
    """WI-03 완료 기준의 핵심 문장 — pilot 은 모든 fit 에서 제외된다."""
    pilot, pool, folds = good
    folds["outer_folds"][0]["train_subjects"].append(pilot[0])
    inv = L.fold_invariants(folds, pilot + pool)
    assert "pilot_absent_from_every_fit" in L.failed_invariants(inv)


def test_pilot_leaking_into_inner_val_is_caught(good):
    pilot, pool, folds = good
    folds["outer_folds"][1]["inner"][0]["val_subjects"].append(pilot[1])
    assert "pilot_absent_from_every_fit" in L.failed_invariants(L.fold_invariants(folds, pilot + pool))


def test_pilot_overlapping_main_pool_is_caught(good):
    pilot, pool, folds = good
    folds["pilot"]["subjects"] = pilot + [pool[0]]
    bad = L.failed_invariants(L.fold_invariants(folds, pilot + pool))
    assert "pilot_and_main_pool_disjoint" in bad


def test_eligible_mismatch_is_caught(good):
    pilot, pool, folds = good
    bad = L.failed_invariants(L.fold_invariants(folds, pilot + pool + ["ds002785:sub-9999"]))
    assert "pilot_union_main_pool_is_eligible" in bad


def test_overlapping_outer_tests_are_caught(good):
    pilot, pool, folds = good
    folds["outer_folds"][0]["test_subjects"].append(folds["outer_folds"][1]["test_subjects"][0])
    bad = L.failed_invariants(L.fold_invariants(folds, pilot + pool))
    assert "outer_tests_mutually_disjoint" in bad
    assert "outer_test_train_disjoint" in bad


def test_inner_val_touching_outer_test_is_caught(good):
    pilot, pool, folds = good
    folds["outer_folds"][0]["inner"][0]["val_subjects"].append(
        folds["outer_folds"][0]["test_subjects"][0])
    assert "inner_structure_valid" in L.failed_invariants(L.fold_invariants(folds, pilot + pool))


def test_malformed_folds_raise(good):
    with pytest.raises(L.LockError):
        L.fold_invariants({"pilot": {}}, [])


# --------------------------------------------------------------------------- #
# lock_hash
# --------------------------------------------------------------------------- #


def test_lock_hash_ignores_itself_and_key_order():
    a = {"schema_version": L.SCHEMA_VERSION, "x": 1, "y": [1, 2], "lock_hash": "zzz"}
    b = {"y": [1, 2], "lock_hash": "different", "x": 1, "schema_version": L.SCHEMA_VERSION}
    assert L.lock_hash(a) == L.lock_hash(b)


def test_lock_hash_changes_with_content():
    a = {"schema_version": L.SCHEMA_VERSION, "x": 1}
    b = {"schema_version": L.SCHEMA_VERSION, "x": 2}
    assert L.lock_hash(a) != L.lock_hash(b)


# --------------------------------------------------------------------------- #
# verify_lock
# --------------------------------------------------------------------------- #


def _write_lock(tmp_path, good, *, tamper_body=None):
    pilot, pool, folds = good
    data = tmp_path / "data"
    repo = tmp_path / "repo"
    (data / "co").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)

    folds_p = data / "co" / "folds.json"
    folds_p.write_text(json.dumps(folds), encoding="utf-8")
    subj_p = data / "co" / "subjects.jsonl"
    subj_p.write_text("".join(
        json.dumps({"canonical_subject": s, "eligible": True}) + "\n"
        for s in pilot + pool), encoding="utf-8")
    doc_p = repo / "docs" / "protocol.md"
    doc_p.write_text("계획서", encoding="utf-8")

    body = {
        "schema_version": L.SCHEMA_VERSION,
        "cohorts": {"piop1": {
            "subjects": L.file_record(subj_p, base=data),
            "folds": L.file_record(folds_p, base=data,
                                   invariants=L.fold_invariants(folds, pilot + pool)),
        }},
        "environment": {"protocol": L.file_record(doc_p, base=repo)},
    }
    if tamper_body:
        tamper_body(body)
    body["lock_hash"] = L.lock_hash(body)
    return body, data, repo, folds_p, subj_p, doc_p


def test_verify_passes_on_an_untouched_lock(tmp_path, good):
    body, data, repo, *_ = _write_lock(tmp_path, good)
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert L.lock_is_clean(res), res
    assert "lock_hash" in res["ok"]


def test_verify_catches_a_changed_data_file(tmp_path, good):
    body, data, repo, folds_p, *_ = _write_lock(tmp_path, good)
    folds_p.write_text(folds_p.read_text(encoding="utf-8") + " ", encoding="utf-8")
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert not L.lock_is_clean(res)
    assert any("folds.json" in m for m in res["mismatch"])


def test_verify_catches_a_changed_repo_file(tmp_path, good):
    body, data, repo, _, _, doc_p = _write_lock(tmp_path, good)
    doc_p.write_text("계획서 수정", encoding="utf-8")
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("protocol.md" in m for m in res["mismatch"])


def test_verify_catches_a_deleted_file(tmp_path, good):
    body, data, repo, folds_p, *_ = _write_lock(tmp_path, good)
    folds_p.unlink()
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert res["missing"]


def test_verify_catches_an_edited_lock_file(tmp_path, good):
    body, data, repo, *_ = _write_lock(tmp_path, good)
    body["cohorts"]["piop1"]["folds"]["invariants"]["n_pilot"] = 999
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("lock_hash" in m for m in res["mismatch"])


def test_verify_recomputes_invariants_rather_than_trusting_them(tmp_path, good):
    """잠금이 '통과'라고 적어 두었어도 folds 가 바뀌면 잡아야 한다."""
    pilot, pool, folds = good

    def tamper(body):
        pass

    body, data, repo, folds_p, *_ = _write_lock(tmp_path, good, tamper_body=tamper)
    bad = json.loads(folds_p.read_text(encoding="utf-8"))
    bad["outer_folds"][0]["train_subjects"].append(pilot[0])
    folds_p.write_text(json.dumps(bad), encoding="utf-8")
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    # 해시도 깨지고 불변식도 깨진다. 둘 다 잡혀야 한다.
    assert res["mismatch"], res
    assert any("pilot_absent_from_every_fit" in m for m in res["invariant"]), res


def test_missing_data_root_is_not_silently_a_pass(tmp_path, good):
    body, data, repo, *_ = _write_lock(tmp_path, good)
    res = L.verify_lock(body, roots={"repo_root": repo})
    assert res["skipped"], "data_root 없이 검사를 건너뛰었으면 skipped 에 남아야 한다"
    assert not L.lock_is_clean(res), "검사하지 못한 것을 통과로 세면 안 된다"


def test_wrong_schema_version_is_caught(tmp_path, good):
    body, data, repo, *_ = _write_lock(tmp_path, good)
    body["schema_version"] = "measurement_lock_v0"
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("schema_version" in m for m in res["mismatch"])


# --------------------------------------------------------------------------- #
# E20 — environment.code 는 기록만 되고 검사되지 않았다
# --------------------------------------------------------------------------- #


def _code_lock(tmp_path, good):
    """`environment.code` 가 있는 잠금. 모듈 2개를 repo/mobse/v2 에 둔다."""
    from mobse.v2.manifests import code_hash, sha256_file

    def add_code(body):
        mod = tmp_path / "repo" / L.CODE_DIR
        mod.mkdir(parents=True, exist_ok=True)
        (mod / "a.py").write_text("x = 1", encoding="utf-8")
        (mod / "b.py").write_text("y = 2", encoding="utf-8")
        paths = sorted(mod.glob("*.py"))
        body["environment"]["code"] = {
            "code_hash": code_hash(paths),
            "modules": {p.name: sha256_file(p) for p in paths},
        }

    body, data, repo, *_ = _write_lock(tmp_path, good, tamper_body=add_code)
    return body, data, repo, repo / L.CODE_DIR


def test_verify_checks_code_on_an_untouched_lock(tmp_path, good):
    body, data, repo, _ = _code_lock(tmp_path, good)
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert L.lock_is_clean(res), res
    assert "environment/code/code_hash" in res["ok"]
    assert sum(s.startswith("environment/code/modules/") for s in res["ok"]) == 2


def test_verify_catches_an_edited_module(tmp_path, good):
    body, data, repo, mod = _code_lock(tmp_path, good)
    (mod / "a.py").write_text("x = 2", encoding="utf-8")
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("modules/a.py" in m for m in res["mismatch"])
    assert any("code_hash" in m for m in res["mismatch"])
    assert not L.lock_is_clean(res)


def test_verify_catches_an_added_module(tmp_path, good):
    body, data, repo, mod = _code_lock(tmp_path, good)
    (mod / "c.py").write_text("z = 3", encoding="utf-8")
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("modules/c.py" in m and "잠금에 없는" in m for m in res["mismatch"])
    assert not L.lock_is_clean(res)


def test_verify_catches_a_removed_module(tmp_path, good):
    body, data, repo, mod = _code_lock(tmp_path, good)
    (mod / "b.py").unlink()
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("modules/b.py" in m for m in res["missing"])
    assert not L.lock_is_clean(res)


def test_code_check_is_location_independent(tmp_path, good):
    """E19 와 함께: 같은 코드를 다른 위치에 복사해도 통과해야 한다."""
    import shutil
    body, data, repo, _ = _code_lock(tmp_path, good)
    moved = tmp_path / "elsewhere" / "repo_copy"
    shutil.copytree(repo, moved)
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": moved})
    assert L.lock_is_clean(res), res


def test_code_without_repo_root_is_skipped_not_passed(tmp_path, good):
    body, data, repo, _ = _code_lock(tmp_path, good)
    res = L.verify_lock(body, roots={"data_root": data})
    assert any(s.startswith("environment/code") for s in res["skipped"])
    assert not L.lock_is_clean(res)


def test_empty_module_record_is_a_mismatch(tmp_path, good):
    body, data, repo, _ = _code_lock(tmp_path, good)
    body["environment"]["code"]["modules"] = {}
    res = L.verify_lock(body, roots={"data_root": data, "repo_root": repo})
    assert any("기록이 없거나 비었다" in m for m in res["mismatch"])
