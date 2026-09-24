"""T02 provenance + T11 target + T15 integrity — mobse/v2/manifests.py."""

from __future__ import annotations

import json

import pytest

from mobse.v2.manifests import (
    EMPTY_ENTITY, ManifestError, RunKey, assert_no_glob_fallback, code_hash,
    expected_prediction_rows, fit_id, make_release_id, read_jsonl, sha256_file,
    sha256_obj, validate_canonical_subject, validate_record, write_jsonl,
)

H = "a" * 64


def _source_run(**over):
    rec = {
        "schema_version": "v2.0",
        "run_key": "ds002785/sub-0001/na/emomatching/na/seq",
        "dataset": "ds002785", "canonical_subject": "ds002785:sub-0001",
        "group_id": "ds002785:sub-0001", "task": "emomatching",
        "source_path": "x/y.nii.gz", "source_sha256": H,
        "native_tr": 2.0, "n_volumes": 135,
        "derivative_start_sec": 0.0, "discarded_volumes": 2,
        "event_origin": "events.tsv onset", "atlas_id": "schaefer100",
        "atlas_hash": H, "roi_order_hash": H,
    }
    rec.update(over)
    return rec


# --------------------------------------------------------------------------- #
# run_key — 빈 entity 를 조용히 합치지 않는다
# --------------------------------------------------------------------------- #

def test_run_key_serialises_all_six_fields():
    rk = RunKey("ds002785", "sub-0001", task="emomatching", acquisition="seq")
    assert str(rk) == "ds002785/sub-0001/na/emomatching/na/seq"
    assert rk.session == EMPTY_ENTITY and rk.run == EMPTY_ENTITY


def test_run_key_roundtrip():
    text = "ds002790/sub-0226/ses-1/workingmemory/run-2/seq"
    assert str(RunKey.parse(text)) == text


def test_run_key_rejects_empty_and_slash():
    with pytest.raises(ManifestError, match="비어 있다"):
        RunKey("ds", "sub-1", task="")
    with pytest.raises(ManifestError, match="'/'"):
        RunKey("ds", "sub/1")
    with pytest.raises(ManifestError, match="6 개 필드"):
        RunKey.parse("ds/sub-1/na")


def test_canonical_subject_requires_dataset_prefix():
    assert validate_canonical_subject("ds002785:sub-0001")
    with pytest.raises(ManifestError, match="U17"):
        validate_canonical_subject("sub-0001")
    assert RunKey("ds002790", "sub-0001").canonical_subject == "ds002790:sub-0001"


# --------------------------------------------------------------------------- #
# T02 — 조용한 default 없음
# --------------------------------------------------------------------------- #

def test_missing_field_fails_explicitly():
    rec = _source_run()
    del rec["native_tr"]
    with pytest.raises(ManifestError, match="필수 필드 누락"):
        validate_record("source_runs", rec)


def test_none_value_fails_rather_than_defaulting():
    with pytest.raises(ManifestError, match="None"):
        validate_record("source_runs", _source_run(native_tr=None))


def test_type_mismatch_fails():
    with pytest.raises(ManifestError, match="타입 불일치"):
        validate_record("source_runs", _source_run(n_volumes="135"))


def test_bool_is_not_accepted_as_int():
    with pytest.raises(ManifestError, match="타입 불일치"):
        validate_record("source_runs", _source_run(n_volumes=True))


def test_bad_hash_fails():
    with pytest.raises(ManifestError, match="SHA256"):
        validate_record("source_runs", _source_run(source_sha256="deadbeef"))


def test_unknown_artifact_fails():
    with pytest.raises(ManifestError, match="알 수 없는 artifact"):
        validate_record("nope", {})


def test_duplicate_run_key_fails(tmp_path):
    p = tmp_path / "source_runs.jsonl"
    with pytest.raises(ManifestError, match="중복"):
        write_jsonl(p, "source_runs", [_source_run(), _source_run()])


def test_existing_file_is_not_overwritten(tmp_path):
    p = tmp_path / "source_runs.jsonl"
    write_jsonl(p, "source_runs", [_source_run()])
    with pytest.raises(ManifestError, match="덮어쓰지 않는다"):
        write_jsonl(p, "source_runs", [_source_run()])
    info = write_jsonl(p, "source_runs", [_source_run()], overwrite=True)
    assert info["n_records"] == 1


def test_write_read_roundtrip_and_hash(tmp_path):
    p = tmp_path / "source_runs.jsonl"
    recs = [_source_run(), _source_run(run_key="ds002785/sub-0002/na/emomatching/na/seq",
                                       canonical_subject="ds002785:sub-0002",
                                       group_id="ds002785:sub-0002")]
    info = write_jsonl(p, "source_runs", recs)
    assert info["n_records"] == 2 and info["unique_keys"] == 2
    back = read_jsonl(p, "source_runs")
    assert [r["run_key"] for r in back] == [r["run_key"] for r in recs]
    assert info["sha256"] == __import__("hashlib").sha256(
        p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# T11 — label 은 task metadata 여야 한다
# --------------------------------------------------------------------------- #

def _window(**over):
    rec = {
        "schema_version": "v2.0", "window_key": "w1",
        "run_key": "ds002785/sub-0001/na/emomatching/na/seq",
        "start_sec": 12.0, "end_sec": 72.0, "source_frame_range": [6, 36],
        "target_grid": 2.0, "n_samples": 30, "n_roi": 100, "qc_flags": [],
        "data_sha256": H, "observed_label": "emomatching",
        "label_source": "task_metadata",
    }
    rec.update(over)
    return rec


def test_label_source_must_be_task_metadata():
    validate_record("windows", _window())
    with pytest.raises(ManifestError, match="cluster ID"):
        validate_record("windows", _window(label_source="cluster_id"))
    with pytest.raises(ManifestError, match="cluster ID"):
        validate_record("windows", _window(label_source="kmeans"))


def test_unknown_cell_is_rejected():
    rec = {"schema_version": "v2.0", "canonical_subject": "ds002785:sub-0001",
           "group_id": "g", "run_key": "ds002785/sub-0001/na/emomatching/na/seq",
           "window_key": "w1", "truth": 0, "p_class1": 0.4, "cell": "E",
           "model_seed": 42, "scope": "outer0", "checkpoint_sha256": H,
           "fit_id": "f"}
    with pytest.raises(ManifestError, match="알 수 없는 cell"):
        validate_record("window_predictions", rec)
    rec["cell"] = "A"
    validate_record("window_predictions", rec)


def _run_prediction_record(cell):
    from mobse.v2.manifests import SCHEMAS
    base = {"schema_version": "v2.0", "canonical_subject": "ds002785:sub-0001",
            "group_id": "g", "run_key": "ds002785/sub-0001/na/emomatching/na/seq",
            "cell": cell}
    kinds = {"str": "x", "int": 0, "float": 0.5, "bool": False, "list": [], "dict": {}}
    for key, kind in SCHEMAS["run_predictions"].items():
        base.setdefault(key, kinds[kind])
    return base


@pytest.mark.parametrize("cell", ["NG", "SG"])
def test_comparator_cells_are_fit_scoped(cell):
    """결정 14 4단계 — NG·SG 는 fit 단위 산출물에서만 받고 run 집계에서는 거부한다."""
    rec = {"schema_version": "v2.0", "canonical_subject": "ds002785:sub-0001",
           "group_id": "g", "run_key": "ds002785/sub-0001/na/emomatching/na/seq",
           "window_key": "w1", "truth": 0, "p_class1": 0.4, "cell": cell,
           "model_seed": 42, "scope": "outer0", "checkpoint_sha256": H,
           "fit_id": "f"}
    validate_record("window_predictions", rec)
    with pytest.raises(ManifestError, match="알 수 없는 cell"):
        validate_record("run_predictions", _run_prediction_record(cell))
    validate_record("run_predictions", _run_prediction_record("A"))
    kw = dict(role="inner", cell=cell, outer_fold=0, inner_fold=1, model_seed=42,
              split_hash="s" * 64, config_hash="c" * 64)
    assert fit_id(**kw).startswith(f"inner-{cell}-o0i1s42-")
    assert fit_id(**kw) != fit_id(**{**kw, "cell": "A"})


def test_comparator_cell_names_match_models_and_baselines():
    pytest.importorskip("torch")
    from mobse.v2 import baselines, models
    from mobse.v2.manifests import (ALLOWED_CELLS, COMPARATOR_CELLS, FIT_CELLS,
                                    FIT_SCOPED_ARTIFACTS)
    assert COMPARATOR_CELLS == set(models.COMPARATOR_SPEC) == set(baselines.COMPARATOR_ORDER)
    assert ALLOWED_CELLS == set(models.CELL_SPEC)
    assert FIT_CELLS == ALLOWED_CELLS | COMPARATOR_CELLS
    assert FIT_SCOPED_ARTIFACTS == {"fit_manifest", "window_predictions"}


# --------------------------------------------------------------------------- #
# T15 — 무결성과 glob fallback 금지
# --------------------------------------------------------------------------- #

def test_sha256_file_fails_when_missing(tmp_path):
    with pytest.raises(ManifestError, match="해시할 파일이 없다"):
        sha256_file(tmp_path / "nope.txt")


def test_sha256_obj_is_key_order_independent():
    assert sha256_obj({"a": 1, "b": 2}) == sha256_obj({"b": 2, "a": 1})
    assert sha256_obj({"a": 1}) != sha256_obj({"a": 2})


def test_code_hash_changes_with_content(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1")
    h1 = code_hash([f])
    f.write_text("x = 2")
    assert code_hash([f]) != h1



def test_code_hash_is_location_independent(tmp_path):
    """E19: 같은 내용이면 저장소 위치가 달라도 같은 값이어야 한다."""
    a = tmp_path / "repo_a" / "mobse" / "v2"
    b = tmp_path / "somewhere" / "else" / "v2"
    for d in (a, b):
        d.mkdir(parents=True)
        (d / "m1.py").write_text("x = 1")
        (d / "m2.py").write_text("y = 2")
    assert code_hash(sorted(a.glob("*.py"))) == code_hash(sorted(b.glob("*.py")))


def test_code_hash_detects_rename(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1")
    h1 = code_hash([f])
    g = tmp_path / "b.py"
    f.rename(g)
    assert code_hash([g]) != h1


def test_code_hash_rejects_duplicate_names(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "q").mkdir()
    (tmp_path / "p" / "m.py").write_text("x = 1")
    (tmp_path / "q" / "m.py").write_text("x = 2")
    with pytest.raises(ManifestError, match="파일명이 겹친다"):
        code_hash([tmp_path / "p" / "m.py", tmp_path / "q" / "m.py"])

def test_assert_no_glob_fallback():
    assert_no_glob_fallback({"config": "c.yaml", "split": "folds.json"})
    with pytest.raises(ManifestError, match="U20"):
        assert_no_glob_fallback({"config": "c.yaml", "checkpoint": None})


def test_fit_id_is_deterministic_and_input_bound():
    kw = dict(role="main", cell="A", outer_fold=0, inner_fold=1, model_seed=42,
              split_hash="s" * 64, config_hash="c" * 64)
    assert fit_id(**kw) == fit_id(**kw)
    assert fit_id(**{**kw, "model_seed": 43}) != fit_id(**kw)
    assert fit_id(**kw).startswith("main-A-o0i1s42-")
    with pytest.raises(ManifestError):
        fit_id(**{**kw, "cell": "Z"})


def test_release_id_format():
    rid = make_release_id("20260917", "3c458d507e82ab", "nocfg12")
    assert rid.startswith("20260917_3c458d507e82_")
    with pytest.raises(ManifestError):
        make_release_id("2026", "abc", "x")


def test_expected_prediction_rows_matches_protocol():
    # 본문 부록 B.2 의 N=132 예상값
    got = expected_prediction_rows(132)
    assert got["window_predictions"] == 12672
    assert got["run_predictions"] == 1056
    assert got["checkpoints"] == 60


# --------------------------------------------------------------------------- #
# E16 — exclusions 의 중복 검출 (2026-09-18)
# --------------------------------------------------------------------------- #


def _exclusion(**kw):
    rec = {
        "schema_version": "wi03-subjects-0.1",
        "key": "ds002785:sub-0001",
        "key_level": "subject",
        "stage": "wi03_cohort",
        "all_reasons": ["workingmemory:mean_fd>0.2"],
        "primary_reason": "workingmemory:mean_fd>0.2",
        "rule_version": "protocol-1.1-§3.3",
    }
    rec.update(kw)
    return rec


def test_exclusions_unique_keys_is_counted_not_zero(tmp_path):
    """`unique_keys: 0` 은 '키가 없다'가 아니라 '키를 안 셌다'였다 — E16."""
    p = tmp_path / "exclusions.jsonl"
    info = write_jsonl(p, "exclusions", [
        _exclusion(key="ds002785:sub-0001"),
        _exclusion(key="ds002785:sub-0002"),
        _exclusion(key="ds002785:sub-0003"),
    ])
    assert info["n_records"] == 3
    assert info["unique_keys"] == 3


def test_exclusions_duplicate_same_stage_and_level_fails(tmp_path):
    p = tmp_path / "exclusions.jsonl"
    with pytest.raises(ManifestError, match="중복"):
        write_jsonl(p, "exclusions", [_exclusion(), _exclusion()])


def test_exclusions_same_key_different_stage_is_allowed(tmp_path):
    """같은 subject 가 run 단계와 subject 단계에서 각각 기록될 수 있다."""
    p = tmp_path / "exclusions.jsonl"
    info = write_jsonl(p, "exclusions", [
        _exclusion(stage="wi02_extract", key_level="run",
                   key="ds002785/sub-0001/na/emomatching/na/seq"),
        _exclusion(stage="wi03_cohort", key_level="subject"),
    ])
    assert info["unique_keys"] == 2


def test_every_schema_artifact_has_an_explicit_key_policy():
    """새 artifact 를 추가하면서 키 정책을 빠뜨리면 중복 검사가 조용히 꺼진다.

    E16 의 근본 원인이 정확히 이것이었다. 키가 필요 없는 artifact 는
    아래 집합에 **명시적으로** 넣어야 한다.
    """
    from mobse.v2.manifests import SCHEMAS, _primary_key_fields

    keyless_by_design = {
        "fit_manifest",        # fit_id 는 내용 해시라 중복이 곧 동일 레코드다
    }
    missing = [a for a in SCHEMAS
               if _primary_key_fields(a) is None and a not in keyless_by_design]
    assert not missing, f"키 정책이 없는 artifact: {missing}"


def test_prediction_keys_match_expected_row_cardinality():
    """예측 artifact 의 키는 완료기준 행 수 공식과 일치해야 한다.

    window 는 subject×task×창(=window_key) 당 seed×cell 행,
    run 은 subject×task(=run_key) 당 cell 행이다. 키가 이보다 넓으면
    중복이 통과하고, 좁으면 정상 행이 중복으로 잡힌다.
    """
    from mobse.v2.manifests import _primary_key_fields

    assert _primary_key_fields("window_predictions") == ("cell", "model_seed", "window_key")
    assert _primary_key_fields("run_predictions") == ("cell", "run_key")

    n = 7
    rows = expected_prediction_rows(n)
    # window_key 는 subject×task×창, run_key 는 subject×task
    assert rows["window_predictions"] == (n * 2 * 4) * 3 * 4   # window_key × seed × cell
    assert rows["run_predictions"] == (n * 2) * 4              # run_key × cell
