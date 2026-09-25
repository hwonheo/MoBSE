"""`mobse-v2 split` 본체 — cohort 출력 → folds.json (T03 경계 포함)."""

from __future__ import annotations

import json
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

from mobse.v2 import cli
from mobse.v2.cohort import build_subjects, subjects_to_records
from mobse.v2.splits import SplitError

CONFIG = (pathlib.Path(__file__).resolve().parents[2]
          / "configs" / "redesign_v1" / "main.yaml")
pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _records(n, dataset="ds002785", broken=()):
    subjects = [f"sub-{i:04d}" for i in range(1, n + 1)]
    manifests = []
    for task in ("emomatching", "workingmemory", "restingstate"):
        runs = []
        for s in subjects:
            status = "excluded" if (s, task) in broken else "ok"
            run = {"record_type": "run", "canonical_subject": f"{dataset}:{s}",
                   "run_key": f"{dataset}/{s}/na/{task}/na/seq", "status": status}
            if status != "ok":
                run["reason"] = ["mean_fd>0.2"]
            runs.append(run)
        manifests.append(({"record_type": "header", "dataset": dataset,
                           "task": task}, runs))
    return subjects_to_records(build_subjects(manifests))


def _write(tmp_path, records, name="subjects.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                    encoding="utf-8")
    return path


def _paths(tmp_path, records, out="out"):
    return {"config": str(CONFIG), "subjects": str(_write(tmp_path, records)),
            "output_dir": str(tmp_path / out)}


# --- 정상 경로 ----------------------------------------------------------------

def test_split_reproduces_expected_sizes(tmp_path):
    """N=164 → pilot 32, main 132, outer test [27,27,26,26,26].

    이 수치는 코호트 상한 산정에서 독립적으로 계산했던 값과 같아야 한다.
    """
    result = cli.run_split(_paths(tmp_path, _records(164)))
    assert result["verdict"] == "pass"
    assert result["subjects_eligible"] == 164
    assert result["pilot_n"] == 32 == result["pilot_target"]
    assert result["main_pool_n"] == 132
    assert result["outer_test_sizes"] == [27, 27, 26, 26, 26]
    assert sum(result["outer_test_sizes"]) == 132


def test_split_writes_folds_json_with_hashes(tmp_path):
    result = cli.run_split(_paths(tmp_path, _records(60)))
    folds = json.loads(pathlib.Path(result["folds_path"]).read_text(encoding="utf-8"))
    assert folds["config_hash"] == result["config_hash"]
    assert len(folds["split_hash"]) == 64
    assert len(folds["subjects_manifest_sha256"]) == 64
    assert len(result["folds_sha256"]) == 64


def test_split_is_deterministic(tmp_path):
    a = cli.run_split(_paths(tmp_path, _records(60), out="a"))
    b = cli.run_split(_paths(tmp_path, _records(60), out="b"))
    assert a["split_hash"] == b["split_hash"]


def test_ineligible_subjects_are_excluded_from_split(tmp_path):
    broken = {("sub-0001", "emomatching"), ("sub-0002", "restingstate")}
    result = cli.run_split(_paths(tmp_path, _records(60, broken=broken)))
    assert result["subjects_total"] == 60
    assert result["subjects_eligible"] == 58
    folds = json.loads(pathlib.Path(result["folds_path"]).read_text(encoding="utf-8"))
    assigned = set(folds["pilot"]["subjects"]) | set(folds["main_pool"]["subjects"])
    assert "ds002785:sub-0001" not in assigned
    assert "ds002785:sub-0002" not in assigned


# --- T03 경계 ----------------------------------------------------------------

def test_pilot_and_main_pool_are_disjoint(tmp_path):
    """pilot 은 main·final fit 에서도 제외된다 (계획서 §4-2)."""
    result = cli.run_split(_paths(tmp_path, _records(100)))
    folds = json.loads(pathlib.Path(result["folds_path"]).read_text(encoding="utf-8"))
    assert not set(folds["pilot"]["subjects"]) & set(folds["main_pool"]["subjects"])


def test_outer_test_never_appears_in_its_train_or_inner(tmp_path):
    result = cli.run_split(_paths(tmp_path, _records(100)))
    folds = json.loads(pathlib.Path(result["folds_path"]).read_text(encoding="utf-8"))
    for outer in folds["outer_folds"]:
        test = set(outer["test_subjects"])
        assert not test & set(outer["train_subjects"])
        for inner in outer["inner"]:
            assert not test & set(inner["train_subjects"])
            assert not test & set(inner["val_subjects"])
            assert not set(inner["train_subjects"]) & set(inner["val_subjects"])


def test_every_main_subject_is_in_exactly_one_outer_test(tmp_path):
    result = cli.run_split(_paths(tmp_path, _records(100)))
    folds = json.loads(pathlib.Path(result["folds_path"]).read_text(encoding="utf-8"))
    counts = {s: 0 for s in folds["main_pool"]["subjects"]}
    for outer in folds["outer_folds"]:
        for s in outer["test_subjects"]:
            counts[s] += 1
    assert set(counts.values()) == {1}


def test_seeds_come_from_config_and_match_constants(tmp_path):
    from mobse.v2 import splits

    result = cli.run_split(_paths(tmp_path, _records(60)))
    folds = json.loads(pathlib.Path(result["folds_path"]).read_text(encoding="utf-8"))
    assert folds["seeds"]["pilot"] == splits.PILOT_SEED
    assert folds["seeds"]["outer"] == splits.OUTER_SEED
    assert folds["seeds"]["inner_base"] == splits.INNER_SEED_BASE


# --- 실패 경로 ----------------------------------------------------------------

def test_missing_subjects_file_does_not_fall_back(tmp_path):
    with pytest.raises(cli.CLIError, match="자동 탐색하지 않는다"):
        cli.run_split({"config": str(CONFIG),
                       "subjects": str(tmp_path / "nope.jsonl"),
                       "output_dir": str(tmp_path / "out")})


def test_zero_eligible_is_refused(tmp_path):
    broken = {(f"sub-{i:04d}", "emomatching") for i in range(1, 11)}
    with pytest.raises(cli.CLIError, match="임의 증원 대신 제한을 보고"):
        cli.run_split(_paths(tmp_path, _records(10, broken=broken)))


def test_schema_violation_in_subjects_is_refused(tmp_path):
    records = _records(10)
    records[0]["canonical_subject"] = "sub-0001"  # dataset prefix 없음 (P5)
    with pytest.raises(cli.CLIError, match="스키마 위반"):
        cli.run_split(_paths(tmp_path, records))


def test_malformed_json_line_is_refused(tmp_path):
    path = tmp_path / "subjects.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(cli.CLIError, match="JSON 파싱 실패"):
        cli.run_split({"config": str(CONFIG), "subjects": str(path),
                       "output_dir": str(tmp_path / "out")})


def test_existing_folds_json_is_not_overwritten(tmp_path):
    """지침서 §2 — 같은 release 결과를 덮어쓰지 않는다."""
    paths = _paths(tmp_path, _records(60))
    cli.run_split(paths)
    with pytest.raises(cli.CLIError, match="덮어쓰지 않는다"):
        cli.run_split(paths)


def test_too_few_groups_fails_rather_than_shrinking(tmp_path):
    """group 수가 부족하면 분할을 자동 축소하지 않는다 (계획서 §4-3)."""
    with pytest.raises((cli.CLIError, SplitError)):
        cli.run_split(_paths(tmp_path, _records(3)))


def test_bad_config_propagates(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("meta:\n  name: x\n", encoding="utf-8")
    with pytest.raises(cli.CLIError, match="config 검증 실패"):
        cli.run_split({"config": str(bad),
                       "subjects": str(_write(tmp_path, _records(60))),
                       "output_dir": str(tmp_path / "out")})


# --- main() 경유 --------------------------------------------------------------

def test_main_split_returns_zero(tmp_path, capsys):
    rc = cli.main(["split", "--config", str(CONFIG),
                   "--subjects", str(_write(tmp_path, _records(60))),
                   "--output-dir", str(tmp_path / "out")])
    assert rc == 0
    assert '"verdict": "pass"' in capsys.readouterr().out


def test_main_split_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "out"
    rc = cli.main(["split", "--config", str(CONFIG),
                   "--subjects", str(_write(tmp_path, _records(60))),
                   "--output-dir", str(out), "--dry-run"])
    assert rc == 0
    assert not (out / "folds.json").exists()


# --- 결정 17: external_folds.json ----------------------------------------------

def _load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def test_split_writes_external_folds_next_to_folds(tmp_path):
    from mobse.v2.splits import external_invariants, failed_external_invariants

    result = cli.run_split(_paths(tmp_path, _records(157)))
    ext_p = pathlib.Path(result["external_folds_path"])
    assert ext_p.name == cli.EXTERNAL_FOLDS_NAME == "external_folds.json"
    assert ext_p.parent == pathlib.Path(result["folds_path"]).parent
    ext, folds = _load(ext_p), _load(result["folds_path"])
    assert result["external_val_sizes"] == [42, 42, 42]
    assert ext["parent_split_hash"] == folds["split_hash"] == result["split_hash"]
    assert ext["seed"] == 20262000
    assert failed_external_invariants(external_invariants(ext, folds)) == []


def test_folds_json_content_is_unchanged_by_decision_17(tmp_path):
    """folds.json 에 외부 블록이 들어가지 않고 split_hash 가 build_folds 그대로다."""
    from mobse.v2.splits import build_folds, make_groups

    records = _records(157)
    result = cli.run_split(_paths(tmp_path, records))
    folds = _load(result["folds_path"])
    groups = make_groups(subject_to_group={r["canonical_subject"]: r["group_id"]
                                           for r in records if r["eligible"]})
    ref = build_folds(groups)
    assert folds["split_hash"] == ref["split_hash"]
    assert set(folds) == set(ref) | {"config_hash", "subjects_manifest",
                                     "subjects_manifest_sha256"}


def test_existing_external_folds_blocks_split_before_any_write(tmp_path):
    paths = _paths(tmp_path, _records(60))
    out = pathlib.Path(paths["output_dir"])
    out.mkdir()
    (out / "external_folds.json").write_text("{}", encoding="utf-8")
    with pytest.raises(cli.CLIError, match="덮어쓰지 않는다"):
        cli.run_split(paths)
    assert not (out / "folds.json").exists()
    assert (out / "external_folds.json").read_text(encoding="utf-8") == "{}"


def _split_then_drop_external(tmp_path, n=157):
    paths = _paths(tmp_path, _records(n))
    result = cli.run_split(paths)
    ext_p = pathlib.Path(result["external_folds_path"])
    first = ext_p.read_bytes()
    ext_p.unlink()
    return paths, result, first


def test_external_split_adds_only_the_new_file(tmp_path):
    paths, result, first = _split_then_drop_external(tmp_path)
    folds_p = pathlib.Path(result["folds_path"])
    before = folds_p.read_bytes()
    listing = sorted(p.name for p in folds_p.parent.iterdir())
    res = cli.run_external_split(paths)
    assert folds_p.read_bytes() == before
    assert sorted(p.name for p in folds_p.parent.iterdir()) == sorted(
        listing + ["external_folds.json"])
    assert pathlib.Path(res["external_folds_path"]).read_bytes() == first
    assert res["split_hash"] == result["split_hash"]
    assert res["external_val_sizes"] == [42, 42, 42]


def test_external_split_refuses_existing_file(tmp_path):
    paths = _paths(tmp_path, _records(60))
    cli.run_split(paths)
    with pytest.raises(cli.CLIError, match="덮어쓰지 않는다"):
        cli.run_external_split(paths)


def test_external_split_refuses_split_hash_mismatch(tmp_path):
    paths, result, _ = _split_then_drop_external(tmp_path)
    folds_p = pathlib.Path(result["folds_path"])
    folds = _load(folds_p)
    folds["split_hash"] = "e" * 64
    folds_p.write_text(json.dumps(folds), encoding="utf-8")
    with pytest.raises(cli.CLIError, match="split_hash"):
        cli.run_external_split(paths)
    assert not (folds_p.parent / "external_folds.json").exists()


def test_external_split_refuses_other_subjects_manifest(tmp_path):
    paths, result, _ = _split_then_drop_external(tmp_path)
    other = dict(paths, subjects=str(_write(tmp_path, _records(158), name="other.jsonl")))
    with pytest.raises(cli.CLIError, match="sha256"):
        cli.run_external_split(other)


def test_external_split_refuses_missing_folds(tmp_path):
    paths = _paths(tmp_path, _records(60))
    pathlib.Path(paths["output_dir"]).mkdir()
    with pytest.raises(cli.CLIError, match="folds.json 이 없다"):
        cli.run_external_split(paths)
