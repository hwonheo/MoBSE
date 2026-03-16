import pytest

from mobse.data.prepare import (
    OpenNeuroFileEntry,
    _download_openneuro_rest_bold_multi,
    _parse_openneuro_dataset_ids,
    _select_openneuro_bold_entries,
    _select_openneuro_subjects,
)


def test_select_openneuro_subjects_strict_hc():
    tsv = """participant_id\tage\tdiagnosis\trest
sub-01\t25\tCONTROL\t1
sub-02\t17\tCONTROL\t1
sub-03\t30\tPATIENT\t1
sub-04\t40\tCONTROL\t0
"""
    result = _select_openneuro_subjects(
        participants_tsv_text=tsv,
        diagnosis="CONTROL",
        min_age=18,
        n_subjects=10,
        strict_hc=True,
    )
    assert result["participant_ids"] == ["sub-01"]
    assert result["filters_applied"]["diagnosis"] == "CONTROL"
    assert result["filters_applied"]["min_age"] == 18


def test_select_openneuro_subjects_strict_requires_columns():
    tsv = """participant_id\tage
sub-01\t25
sub-02\t30
"""
    with pytest.raises(RuntimeError, match="diagnosis/group"):
        _select_openneuro_subjects(
            participants_tsv_text=tsv,
            diagnosis="CONTROL",
            min_age=18,
            n_subjects=10,
            strict_hc=True,
        )


def test_select_openneuro_subjects_non_strict_skips_missing_columns():
    tsv = """participant_id\tage
01\t20
02\t21
"""
    result = _select_openneuro_subjects(
        participants_tsv_text=tsv,
        diagnosis="CONTROL",
        min_age=18,
        n_subjects=1,
        strict_hc=False,
    )
    assert result["participant_ids"] == ["sub-01"]
    assert "diagnosis" in result["filters_skipped"]


def test_select_openneuro_subjects_diagnosis_flexible_matching():
    tsv = """participant_id\tage\tgroup\trest
sub-01\t25\thealthy control\t1
sub-02\t28\tpatient\t1
sub-03\t31\tHC\t1
"""
    result = _select_openneuro_subjects(
        participants_tsv_text=tsv,
        diagnosis="CONTROL,HC",
        min_age=18,
        n_subjects=10,
        strict_hc=True,
    )
    assert result["participant_ids"] == ["sub-01", "sub-03"]
    assert result["filters_applied"]["diagnosis"] == ["CONTROL", "HC"]


def test_select_openneuro_bold_entries_prefers_participant_list():
    files = [
        OpenNeuroFileEntry(
            relative_path="sub-01/func/sub-01_task-rest_run-2_bold.nii.gz",
            url="https://example.org/sub-01-run2",
        ),
        OpenNeuroFileEntry(
            relative_path="sub-01/func/sub-01_task-rest_run-1_bold.nii.gz",
            url="https://example.org/sub-01-run1",
        ),
        OpenNeuroFileEntry(
            relative_path="sub-02/func/sub-02_task-rest_run-1_bold.nii.gz",
            url="https://example.org/sub-02-run1",
        ),
        OpenNeuroFileEntry(
            relative_path="sub-03/func/sub-03_task-nback_run-1_bold.nii.gz",
            url="https://example.org/sub-03-nback",
        ),
        OpenNeuroFileEntry(
            relative_path="derivatives/sub-99/func/sub-99_task-rest_run-1_bold.nii.gz",
            url="https://example.org/sub-99-deriv",
        ),
    ]
    result = _select_openneuro_bold_entries(
        files=files,
        participant_ids=["sub-02", "sub-01", "sub-404"],
        task="rest",
        n_subjects=3,
    )

    assert result["participant_ids"] == ["sub-02", "sub-01"]
    assert result["entries"][0].relative_path.endswith("sub-02_task-rest_run-1_bold.nii.gz")
    # run-1 is picked because entries are path-sorted within each subject
    assert result["entries"][1].relative_path.endswith("sub-01_task-rest_run-1_bold.nii.gz")
    assert "sub-404" in result["missing_ids"]


def test_select_openneuro_bold_entries_supports_multi_task_names():
    files = [
        OpenNeuroFileEntry(
            relative_path="sub-01/func/sub-01_task-restingstate_run-1_bold.nii.gz",
            url="https://example.org/sub-01-restingstate",
        ),
        OpenNeuroFileEntry(
            relative_path="sub-02/func/sub-02_task-rest_run-1_bold.nii.gz",
            url="https://example.org/sub-02-rest",
        ),
    ]
    result = _select_openneuro_bold_entries(
        files=files,
        participant_ids=["sub-01", "sub-02"],
        task="rest,restingstate",
        n_subjects=2,
    )
    assert result["participant_ids"] == ["sub-01", "sub-02"]


def test_select_openneuro_bold_entries_raises_without_match():
    files = [
        OpenNeuroFileEntry(
            relative_path="sub-01/func/sub-01_task-nback_run-1_bold.nii.gz",
            url="https://example.org/sub-01-nback",
        )
    ]
    with pytest.raises(RuntimeError, match="No task-rest BOLD"):
        _select_openneuro_bold_entries(
            files=files,
            participant_ids=["sub-01"],
            task="rest",
            n_subjects=1,
        )


def test_parse_openneuro_dataset_ids_dedup_and_split():
    assert _parse_openneuro_dataset_ids("ds000030", "") == ["ds000030"]
    assert _parse_openneuro_dataset_ids("ds000030", "ds000030, ds002790 ds002790") == [
        "ds000030",
        "ds002790",
    ]


def test_download_openneuro_rest_bold_multi_fallback(monkeypatch: pytest.MonkeyPatch):
    def fake_download(**kwargs):
        dataset_id = kwargs["dataset_id"]
        requested = kwargs["n_subjects"]
        if dataset_id == "ds_bad":
            raise RuntimeError("no participants.tsv")
        if dataset_id == "ds_ok1":
            ids = ["sub-01", "sub-02"][:requested]
            return {
                "openneuro_root": "/tmp/ds_ok1",
                "dataset_id": "ds_ok1",
                "snapshot_tag": "1.0.0",
                "task": "rest",
                "participant_ids": ids,
                "bold_files": [f"/tmp/{pid}.nii.gz" for pid in ids],
                "missing_ids": [],
                "participants_path": "/tmp/participants.tsv",
                "selection": {"rows": 2},
            }
        if dataset_id == "ds_ok2":
            ids = ["sub-10", "sub-11"][:requested]
            return {
                "openneuro_root": "/tmp/ds_ok2",
                "dataset_id": "ds_ok2",
                "snapshot_tag": "2.0.0",
                "task": "rest",
                "participant_ids": ids,
                "bold_files": [f"/tmp/{pid}.nii.gz" for pid in ids],
                "missing_ids": [],
                "participants_path": "/tmp/participants.tsv",
                "selection": {"rows": 2},
            }
        raise AssertionError(f"unexpected dataset_id: {dataset_id}")

    monkeypatch.setattr("mobse.data.prepare._download_openneuro_rest_bold", fake_download)

    result = _download_openneuro_rest_bold_multi(
        dataset_ids=["ds_bad", "ds_ok1", "ds_ok2"],
        snapshot_tag=None,
        task="rest",
        n_subjects=3,
        min_age=18,
        diagnosis="CONTROL",
        strict_hc=True,
        api_url="https://example.org/graphql",
        cache_root="/tmp/openneuro",
        progress=None,
    )

    assert result["requested_subjects"] == 3
    assert result["collected_subjects"] == 3
    assert len(result["records"]) == 3
    assert result["records"][0]["subject_key"] == "ds_ok1_sub-01"
    assert result["records"][2]["subject_key"] == "ds_ok2_sub-10"
    assert len(result["skipped_datasets"]) == 1
    assert result["skipped_datasets"][0]["dataset_id"] == "ds_bad"
