"""WI-03 코호트 구성 — 계획서 §3.3 primary complete-case."""

from __future__ import annotations

import json

import pytest

from mobse.v2.cohort import (
    BANK_TASK,
    REQUIRED_TASKS,
    TARGET_TASKS,
    CohortError,
    build_subjects,
    exclusion_records,
    read_extract_manifest,
    subjects_to_records,
    summarize,
)
from mobse.v2.manifests import ManifestError, validate_record
from mobse.v2.splits import build_folds, make_groups


def _run(subject, task, status="ok", reason=None, dataset="ds002785"):
    rec = {"record_type": "run",
           "canonical_subject": f"{dataset}:{subject}",
           "run_key": f"{dataset}/{subject}/na/{task}/na/seq",
           "status": status}
    if reason is not None:
        rec["reason"] = reason
    return rec


def _manifest(task, runs, dataset="ds002785"):
    return ({"record_type": "header", "dataset": dataset, "task": task}, runs)


def _complete(subjects, dataset="ds002785"):
    return [_manifest(t, [_run(s, t, dataset=dataset) for s in subjects], dataset)
            for t in REQUIRED_TASKS]


# --- 적격 판정 ---------------------------------------------------------------

def test_all_three_runs_ok_is_eligible():
    out = build_subjects(_complete(["sub-0001", "sub-0002"]))
    assert len(out) == 2
    assert all(s.eligible for s in out)
    assert out[0].passed_tasks == REQUIRED_TASKS


def test_missing_rest_makes_ineligible():
    """rest 가 없으면 bank 기여를 못 하므로 부적격 (§3.3)."""
    m = [_manifest(t, [_run("sub-0001", t)]) for t in TARGET_TASKS]
    out = build_subjects(m)
    assert out[0].eligible is False
    assert f"{BANK_TASK}_missing" in out[0].all_reasons


def test_missing_one_target_makes_ineligible():
    m = [_manifest(t, [_run("sub-0001", t)])
         for t in ("emomatching", BANK_TASK)]
    out = build_subjects(m)
    assert out[0].eligible is False
    assert "workingmemory_missing" in out[0].all_reasons


def test_excluded_run_propagates_all_reasons():
    m = _complete(["sub-0001"])
    m[0][1][0]["status"] = "excluded"
    m[0][1][0]["reason"] = ["window3_spike_ratio>0.1", "window3_spikes>3"]
    out = build_subjects(m)
    assert out[0].eligible is False
    assert out[0].all_reasons == [
        "emomatching:window3_spike_ratio>0.1", "emomatching:window3_spikes>3"]
    assert out[0].primary_reason == out[0].all_reasons[0]


def test_reasons_from_multiple_tasks_are_all_kept():
    m = _complete(["sub-0001"])
    m[0][1][0].update(status="excluded", reason=["mean_fd>0.2"])
    m[2][1][0].update(status="excluded", reason=["residual_dof<=30"])
    out = build_subjects(m)
    assert len(out[0].all_reasons) == 2
    assert any(r.startswith("emomatching:") for r in out[0].all_reasons)
    assert any(r.startswith("restingstate:") for r in out[0].all_reasons)


def test_status_without_reason_still_recorded():
    m = _complete(["sub-0001"])
    m[1][1][0]["status"] = "skipped"
    out = build_subjects(m)
    assert "workingmemory:skipped" in out[0].all_reasons


def test_string_reason_accepted():
    m = _complete(["sub-0001"])
    m[1][1][0].update(status="skipped", reason="파일 없음: ['confounds']")
    out = build_subjects(m)
    assert any("파일 없음" in r for r in out[0].all_reasons)


# --- 무결성 ------------------------------------------------------------------

def test_subject_without_dataset_prefix_is_rejected():
    """개정 P5 — prefix 없는 키는 자동 보정하지 않고 실패한다."""
    bad = [({"record_type": "header", "task": "emomatching"},
            [{"record_type": "run", "canonical_subject": "sub-0001",
              "run_key": "x", "status": "ok"}])]
    with pytest.raises(CohortError, match="dataset prefix"):
        build_subjects(bad)


def test_duplicate_subject_task_is_rejected():
    dup = [_manifest("emomatching", [_run("sub-0001", "emomatching"),
                                     _run("sub-0001", "emomatching")])]
    with pytest.raises(CohortError, match="중복"):
        build_subjects(dup)


def test_output_sorted_by_subject():
    out = build_subjects(_complete(["sub-0009", "sub-0001", "sub-0005"]))
    assert [s.canonical_subject for s in out] == sorted(
        s.canonical_subject for s in out)


def test_two_cohorts_do_not_collide():
    """같은 sub-0001 이라도 dataset 이 다르면 다른 사람이다 (U17)."""
    m = _complete(["sub-0001"], "ds002785") + _complete(["sub-0001"], "ds002790")
    out = build_subjects(m)
    assert len(out) == 2
    assert {s.cohort for s in out} == {"ds002785", "ds002790"}


# --- 스키마 적합 -------------------------------------------------------------

def test_subject_records_satisfy_manifest_schema():
    out = build_subjects(_complete(["sub-0001", "sub-0002"]))
    for rec in subjects_to_records(out):
        validate_record("subjects", rec)


def test_group_id_degenerates_to_subject():
    """개정 P4 / U10 — 관계 metadata 가 없으므로 group = subject."""
    out = build_subjects(_complete(["sub-0001"]))
    rec = subjects_to_records(out)[0]
    assert rec["group_id"] == rec["canonical_subject"]


def test_ineligible_subject_is_marked_excluded():
    m = _complete(["sub-0001"])
    m[0][1][0].update(status="excluded", reason=["mean_fd>0.2"])
    rec = subjects_to_records(build_subjects(m))[0]
    assert rec["eligible"] is False
    assert rec["assignment"] == "excluded"
    assert "mean_fd" in rec["assignment_reason"]


def test_exclusion_records_satisfy_schema():
    m = _complete(["sub-0001", "sub-0002"])
    m[0][1][0].update(status="excluded", reason=["mean_fd>0.2", "run_spike_ratio>0.1"])
    out = build_subjects(m)
    recs = exclusion_records(out)
    assert len(recs) == 1
    for rec in recs:
        validate_record("exclusions", rec)
    assert len(recs[0]["all_reasons"]) == 2
    assert recs[0]["primary_reason"] == recs[0]["all_reasons"][0]


def test_eligible_subjects_produce_no_exclusion_records():
    assert exclusion_records(build_subjects(_complete(["sub-0001"]))) == []


# --- 요약 --------------------------------------------------------------------

def test_summary_counts_by_cohort():
    m = _complete(["sub-0001", "sub-0002"], "ds002785") + \
        _complete(["sub-0100"], "ds002790")
    m[0][1][0].update(status="excluded", reason=["mean_fd>0.2"])
    s = summarize(build_subjects(m))
    assert s["n_subjects"] == 3 and s["n_eligible"] == 2
    assert s["by_cohort"]["ds002785"] == {"total": 2, "eligible": 1}
    assert s["by_cohort"]["ds002790"] == {"total": 1, "eligible": 1}


def test_summary_counts_each_subject_once_per_reason():
    m = _complete(["sub-0001"])
    m[0][1][0].update(status="excluded", reason=["mean_fd>0.2", "mean_fd>0.2"])
    s = summarize(build_subjects(m))
    assert s["reason_counts"]["emomatching:mean_fd>0.2"] == 1


# --- splits 와의 접합 ---------------------------------------------------------

def test_eligible_subjects_feed_build_folds():
    """코호트 출력이 splits.build_folds() 에 그대로 들어간다.

    반환 키는 `build_folds` 가 실제로 내는 것을 쓴다 — 기억으로 적지 않는다.
    """
    subjects = [f"sub-{i:04d}" for i in range(1, 51)]
    out = build_subjects(_complete(subjects))
    eligible = [s.canonical_subject for s in out if s.eligible]
    assert len(eligible) == 50
    folds = build_folds(make_groups(subjects=eligible))
    assert folds["n_subjects_total"] == 50
    assert folds["pilot"]["n"] == min(32, int(0.2 * 50))
    assert folds["pilot"]["target"] == min(32, int(0.2 * 50))
    assert set(folds["pilot"]["subjects"]) <= set(eligible)


def test_build_folds_return_shape_is_what_callers_expect():
    """상위 키·pilot 키 집합을 직접 고정한다 (E12 부류 재발 방지)."""
    folds = build_folds(make_groups(subjects=[f"ds002785:sub-{i:04d}"
                                              for i in range(1, 41)]))
    assert {"schema_version", "seeds", "n_subjects_total", "n_groups_total",
            "pilot", "grouping_assumption"} <= set(folds)
    assert {"seed", "target", "n", "groups", "subjects",
            "shortfall_reason"} <= set(folds["pilot"])


def test_ineligible_subjects_never_reach_folds():
    subjects = [f"sub-{i:04d}" for i in range(1, 21)]
    m = _complete(subjects)
    for row in m[0][1][:5]:
        row.update(status="excluded", reason=["mean_fd>0.2"])
    out = build_subjects(m)
    eligible = [s.canonical_subject for s in out if s.eligible]
    assert len(eligible) == 15
    groups = make_groups(subjects=eligible)
    assert sum(len(g.subjects) for g in groups) == 15


# --- 파일 입출력 --------------------------------------------------------------

def test_read_extract_manifest(tmp_path):
    path = tmp_path / "m.jsonl"
    header, runs = _manifest("emomatching", [_run("sub-0001", "emomatching")])
    path.write_text("\n".join(json.dumps(r) for r in [header] + list(runs)) + "\n",
                    encoding="utf-8")
    h, r = read_extract_manifest(path)
    assert h["task"] == "emomatching" and len(r) == 1


def test_read_extract_manifest_missing_file(tmp_path):
    with pytest.raises(CohortError, match="자동 탐색하지 않는다"):
        read_extract_manifest(tmp_path / "nope.jsonl")


def test_read_extract_manifest_without_header(tmp_path):
    path = tmp_path / "m.jsonl"
    path.write_text(json.dumps(_run("sub-0001", "emomatching")) + "\n", encoding="utf-8")
    with pytest.raises(CohortError, match="헤더가 아니다"):
        read_extract_manifest(path)


def test_read_extract_manifest_empty(tmp_path):
    path = tmp_path / "m.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(CohortError, match="비었다"):
        read_extract_manifest(path)
