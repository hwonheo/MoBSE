"""T11 — label 은 task metadata 에서만 온다. 창 레코드 구성 (WI-02 → windows.jsonl)."""

from __future__ import annotations

import pytest

from mobse.v2.labels import (
    CLASS_LABELS,
    LABEL_SOURCE,
    NON_CLASSIFICATION_TASKS,
    LabelError,
    build_window_records,
    class_index,
    label_of,
    window_key,
)
from mobse.v2.manifests import ALLOWED_LABEL_SOURCES, ManifestError, validate_record
from mobse.v2.preprocess import SAMPLES_PER_WINDOW, TARGET_GRID, WINDOW_STARTS

H = "a" * 64
RUN_KEY = "ds002785/sub-0001/na/emomatching/na/seq"


def _windows(n=4, *, shape=None, starts=None):
    shape = shape or [SAMPLES_PER_WINDOW, 100]
    starts = starts or list(WINDOW_STARTS)
    return [{"path": f"/tmp/w{i}.npy", "sha256": H, "shape": list(shape),
             "start_sec": float(starts[i]),
             "source_frame_range": [4 + 30 * i, 34 + 30 * i]}
            for i in range(n)]


def _run(status="ok", **kw):
    rec = {"record_type": "run", "run_key": RUN_KEY,
           "canonical_subject": "ds002785:sub-0001",
           "status": status, "windows": _windows(),
           "qc_decision": {"passed": True, "all_reasons": [], "primary_reason": None}}
    rec.update(kw)
    return rec


def _header(task="emomatching"):
    return {"record_type": "header", "dataset": "ds002785", "task": task}


# --- label 출처 (T11) ---------------------------------------------------------

def test_target_tasks_map_to_themselves():
    assert label_of("emomatching") == "emomatching"
    assert label_of("workingmemory") == "workingmemory"


def test_class_index_follows_protocol_order():
    """계획서 §1 — emomatching=0, workingmemory=1."""
    assert class_index("emomatching") == 0
    assert class_index("workingmemory") == 1
    assert CLASS_LABELS == ("emomatching", "workingmemory")


def test_restingstate_is_not_a_class():
    """rest 는 bank source 다. label 을 붙이면 3-class 로 번진다."""
    assert "restingstate" in NON_CLASSIFICATION_TASKS
    with pytest.raises(LabelError, match="분류 대상이 아니다"):
        label_of("restingstate")


@pytest.mark.parametrize("task", ["faces", "gstroop", "anticipation", "", "EMOMATCHING"])
def test_unknown_task_is_rejected_not_defaulted(task):
    with pytest.raises(LabelError):
        label_of(task)


def test_label_source_is_the_only_allowed_one():
    assert LABEL_SOURCE == "task_metadata"
    assert LABEL_SOURCE in ALLOWED_LABEL_SOURCES


def test_cluster_id_can_never_become_a_label_source():
    """스키마 쪽 guard 를 여기서도 확인한다 (T11 이중 방어)."""
    for forbidden in ("cluster_id", "kmeans", "kmeans_cluster", "events_tsv"):
        assert forbidden not in ALLOWED_LABEL_SOURCES


# --- window_key ---------------------------------------------------------------

def test_window_key_format():
    assert window_key(RUN_KEY, 2) == f"{RUN_KEY}#win-2"


def test_window_key_separator_is_not_slash():
    """run_key 가 '/' 로 나뉘므로 창 구분자는 '/' 면 안 된다."""
    key = window_key(RUN_KEY, 0)
    assert key.count("/") == RUN_KEY.count("/")


@pytest.mark.parametrize("index", [-1, 4, 99])
def test_window_key_rejects_out_of_range(index):
    with pytest.raises(LabelError, match="범위"):
        window_key(RUN_KEY, index)


def test_window_key_validates_run_key():
    with pytest.raises(ManifestError):
        window_key("not/a/valid/key", 0)


# --- 창 레코드 ----------------------------------------------------------------

def test_builds_four_records_per_ok_run():
    recs = build_window_records(_header(), [_run()])
    assert len(recs) == len(WINDOW_STARTS) == 4
    for i, rec in enumerate(recs):
        validate_record("windows", rec)
        assert rec["observed_label"] == "emomatching"
        assert rec["label_source"] == LABEL_SOURCE
        assert rec["start_sec"] == WINDOW_STARTS[i]
        assert rec["end_sec"] == WINDOW_STARTS[i] + SAMPLES_PER_WINDOW * TARGET_GRID
        assert rec["n_samples"] == SAMPLES_PER_WINDOW
        assert rec["target_grid"] == TARGET_GRID


def test_excluded_runs_produce_no_records():
    """제외된 run 의 창은 만들지 않는다 — 만들어 두고 나중에 거르지 않는다."""
    recs = build_window_records(_header(), [_run(status="excluded"),
                                            _run(status="skipped"),
                                            _run(status="error")])
    assert recs == []


def test_mixed_statuses_keep_only_ok():
    runs = [_run(), _run(status="excluded")]
    runs[1]["run_key"] = RUN_KEY.replace("sub-0001", "sub-0002")
    recs = build_window_records(_header(), runs)
    assert len(recs) == 4
    assert all("sub-0001" in r["run_key"] for r in recs)


def test_rest_manifest_is_refused_outright():
    with pytest.raises(LabelError, match="분류 대상이 아니다"):
        build_window_records(_header("restingstate"), [_run()])


def test_partial_window_count_is_refused():
    run = _run()
    run["windows"] = _windows(3)
    with pytest.raises(LabelError, match="부분 창으로 진행하지 않는다"):
        build_window_records(_header(), [run])


def test_wrong_sample_count_is_refused():
    run = _run()
    run["windows"] = _windows(shape=[29, 100])
    with pytest.raises(LabelError, match="형상"):
        build_window_records(_header(), [run])


def test_wrong_roi_count_is_refused():
    run = _run()
    run["windows"] = _windows(shape=[SAMPLES_PER_WINDOW, 200])
    with pytest.raises(LabelError, match="형상"):
        build_window_records(_header(), [run])


def test_wrong_window_start_is_refused():
    run = _run()
    run["windows"] = _windows(starts=[0.0, 72.0, 132.0, 192.0])
    with pytest.raises(LabelError, match="시작"):
        build_window_records(_header(), [run])


def test_qc_flags_carried_from_run():
    run = _run()
    run["qc_decision"]["all_reasons"] = ["window0_spikes>3"]
    recs = build_window_records(_header(), [run])
    assert all(r["qc_flags"] == ["window0_spikes>3"] for r in recs)


def test_window_keys_are_unique():
    runs = [_run(), _run()]
    runs[1]["run_key"] = RUN_KEY.replace("sub-0001", "sub-0002")
    recs = build_window_records(_header(), runs)
    assert len({r["window_key"] for r in recs}) == len(recs) == 8


def test_workingmemory_label():
    header = _header("workingmemory")
    run = _run()
    run["run_key"] = RUN_KEY.replace("emomatching", "workingmemory")
    recs = build_window_records(header, [run])
    assert all(r["observed_label"] == "workingmemory" for r in recs)


def test_bad_hash_is_caught_by_self_validation():
    run = _run()
    run["windows"][0]["sha256"] = "not-a-hash"
    with pytest.raises(ManifestError, match="SHA256"):
        build_window_records(_header(), [run])


def test_expected_row_count_for_a_subject():
    """subject 당 2 task × 4 창 = 8 창 레코드."""
    emo = build_window_records(_header("emomatching"), [_run()])
    wm_run = _run()
    wm_run["run_key"] = RUN_KEY.replace("emomatching", "workingmemory")
    wm = build_window_records(_header("workingmemory"), [wm_run])
    assert len(emo) + len(wm) == 8
