"""T16 scope + T15 무결성 + CLI 경로 계약 — evaluate.py, cli.py."""

from __future__ import annotations

import pathlib
import pytest

from mobse.v2.cli import CLIError, REQUIRED_PATHS, SUBCOMMANDS, build_parser, \
    check_inputs_exist, resolve_paths
from mobse.v2.evaluate import (
    CELLS, CLASSIFICATION_TASKS, EvaluationError, WindowPrediction,
    aggregate_runs, assert_classification_only, cell_balanced_accuracy,
    primary_contrasts, subject_scores, verify_checkpoint_integrity,
    verify_release_completeness,
)
from mobse.v2.manifests import ManifestError


def _preds(subjects, *, cells=CELLS, p_by=None, truth=1):
    out = []
    for c in cells:
        for s in subjects:
            for t in CLASSIFICATION_TASKS:
                for w in range(4):
                    for seed in (42, 43, 44):
                        p = (p_by or {}).get((c, s, t), 0.9)
                        out.append(WindowPrediction(
                            canonical_subject=s, group_id=s, task=t,
                            window_index=w, model_seed=seed, cell=c,
                            truth=truth, p_class1=p))
    return out


# --------------------------------------------------------------------------- #
# T16 — classification only
# --------------------------------------------------------------------------- #

def test_only_trained_classification_tasks_are_evaluated():
    assert assert_classification_only(CLASSIFICATION_TASKS) == CLASSIFICATION_TASKS
    with pytest.raises(EvaluationError, match="학습하지 않은 task"):
        assert_classification_only(["emomatching", "etth1"])
    with pytest.raises(EvaluationError, match="학습하지 않은 task"):
        assert_classification_only(["restingstate"])
    with pytest.raises(EvaluationError, match="비었다"):
        assert_classification_only([])


def test_window_prediction_rejects_unknown_task_and_cell():
    kw = dict(canonical_subject="ds:sub-0001", group_id="g", window_index=0,
              model_seed=42, truth=1, p_class1=0.5)
    with pytest.raises(EvaluationError, match="알 수 없는 task"):
        WindowPrediction(task="etth1", cell="A", **kw)
    with pytest.raises(EvaluationError, match="알 수 없는 cell"):
        WindowPrediction(task="emomatching", cell="E", **kw)


# --------------------------------------------------------------------------- #
# 집계
# --------------------------------------------------------------------------- #

def test_aggregate_produces_one_run_per_subject_task_cell():
    subs = ["ds:sub-0001", "ds:sub-0002"]
    runs = aggregate_runs(_preds(subs))
    assert len(runs) == len(CELLS) * len(subs) * 2
    for rec in runs.values():
        assert rec["n_windows"] == 4 and rec["n_seeds"] == 3
        assert rec["p"] == pytest.approx(0.9)
        assert rec["prediction"] == 1 and rec["correct"]


def test_missing_seed_fails_rather_than_averaging_partially():
    preds = _preds(["ds:sub-0001"])
    preds = [p for p in preds if not (p.cell == "A" and p.model_seed == 44
                                      and p.window_index == 0
                                      and p.task == "emomatching")]
    with pytest.raises(EvaluationError, match="불완전한 격자|빠진"):
        aggregate_runs(preds)


def test_duplicate_prediction_fails():
    preds = _preds(["ds:sub-0001"])
    with pytest.raises(EvaluationError, match="중복 예측"):
        aggregate_runs(preds + [preds[0]])


def test_conflicting_truth_fails():
    preds = _preds(["ds:sub-0001"])
    bad = preds[0]
    preds[0] = WindowPrediction(
        canonical_subject=bad.canonical_subject, group_id=bad.group_id,
        task=bad.task, window_index=bad.window_index, model_seed=bad.model_seed,
        cell=bad.cell, truth=0, p_class1=bad.p_class1)
    with pytest.raises(EvaluationError, match="truth 가 엇갈린다"):
        aggregate_runs(preds)


def test_subject_scores_and_ba_hand_computed():
    subs = ["ds:sub-0001", "ds:sub-0002"]
    # sub-0002 의 emomatching 만 틀리게 만든다 -> b = 0.5
    p_by = {("A", "ds:sub-0002", "emomatching"): 0.2}
    runs = aggregate_runs(_preds(subs, p_by=p_by))
    scores = subject_scores(runs, "A")
    assert scores == {"ds:sub-0001": 1.0, "ds:sub-0002": 0.5}
    assert cell_balanced_accuracy(runs, "A") == pytest.approx(0.75)


def test_incomplete_case_subject_is_rejected():
    preds = [p for p in _preds(["ds:sub-0001"])
             if not (p.cell == "A" and p.task == "workingmemory")]
    runs = aggregate_runs(preds)
    with pytest.raises(EvaluationError, match="complete-case"):
        subject_scores(runs, "A")


def test_primary_contrasts_are_within_subject():
    subs = ["ds:sub-0001", "ds:sub-0002"]
    p_by = {("B", "ds:sub-0001", "emomatching"): 0.1,   # B 만 틀림
            ("C", "ds:sub-0002", "workingmemory"): 0.1}  # C 만 틀림
    runs = aggregate_runs(_preds(subs, p_by=p_by))
    con = primary_contrasts(runs)
    assert con["H1_A_minus_B"]["ds:sub-0001"] == pytest.approx(0.5)
    assert con["H1_A_minus_B"]["ds:sub-0002"] == pytest.approx(0.0)
    assert con["H2_A_minus_C"]["ds:sub-0002"] == pytest.approx(0.5)
    assert set(con) == {"H1_A_minus_B", "H2_A_minus_C", "interaction"}


# --------------------------------------------------------------------------- #
# T15 — 무결성
# --------------------------------------------------------------------------- #

def test_release_completeness_matches_protocol_arithmetic():
    subs = [f"ds:sub-{i:04d}" for i in range(3)]
    info = verify_release_completeness(_preds(subs), set(subs))
    assert info["window_rows"] == 3 * 2 * 4 * 3 * 4
    assert info["run_rows"] == 3 * 2 * 4


def test_release_completeness_detects_missing_rows():
    subs = [f"ds:sub-{i:04d}" for i in range(3)]
    preds = _preds(subs)[:-1]
    with pytest.raises(EvaluationError, match="행 수"):
        verify_release_completeness(preds, set(subs))


def test_release_completeness_detects_subject_mismatch():
    """subject 수는 같지만 구성이 다른 경우를 잡는다.

    expected 집합의 크기를 바꾸면 행 수 검사가 먼저 걸리므로, 같은 크기에서
    ID 하나만 교체해 subject 대조 분기를 겨냥한다.
    """
    subs = [f"ds:sub-{i:04d}" for i in range(3)]
    swapped = set(subs[:-1]) | {"ds:sub-9999"}
    assert len(swapped) == len(subs)
    with pytest.raises(EvaluationError, match="subject 불일치"):
        verify_release_completeness(_preds(subs), swapped)


def test_checkpoint_integrity_rejects_missing_and_mismatched():
    exp = {"f1": "a" * 64, "f2": "b" * 64}
    verify_checkpoint_integrity(dict(exp), exp)
    with pytest.raises(EvaluationError, match="누락"):
        verify_checkpoint_integrity({"f1": "a" * 64}, exp)
    with pytest.raises(EvaluationError, match="불일치"):
        verify_checkpoint_integrity({"f1": "a" * 64, "f2": "c" * 64}, exp)


# --------------------------------------------------------------------------- #
# CLI — 경로가 모두 필수다
# --------------------------------------------------------------------------- #

def test_every_subcommand_requires_all_its_paths():
    ap = build_parser()
    for cmd in SUBCOMMANDS:
        with pytest.raises(SystemExit):
            ap.parse_args([cmd])          # 필수 인자 없이 호출하면 실패


def test_parser_accepts_fully_specified_invocation(tmp_path):
    cfg = tmp_path / "c.yaml"; cfg.write_text("{}")
    src = tmp_path / "s.jsonl"; src.write_text("")
    ns = build_parser().parse_args(
        ["validate", "--config", str(cfg), "--source-runs", str(src)])
    paths = resolve_paths("validate", ns)
    assert set(paths) == set(REQUIRED_PATHS["validate"])
    check_inputs_exist(paths)


def test_missing_input_file_fails_without_fallback(tmp_path):
    cfg = tmp_path / "c.yaml"; cfg.write_text("{}")
    ns = build_parser().parse_args(
        ["validate", "--config", str(cfg), "--source-runs", str(tmp_path / "nope.jsonl")])
    with pytest.raises(CLIError, match="U20"):
        check_inputs_exist(resolve_paths("validate", ns))


def test_unknown_subcommand_rejected():
    with pytest.raises(CLIError, match="알 수 없는 하위 명령"):
        resolve_paths("train", build_parser().parse_args(
            ["validate", "--config", "c", "--source-runs", "s"]))


def test_fit_requires_cell_fold_seed_and_epochs(tmp_path):
    """fit 의 인자 계약. WI-05 본체가 붙으며 필수 인자가 늘었다 (부록 W.1)."""
    for p in ("c.yaml", "f.json", "w.jsonl", "s.jsonl", "r.jsonl", "t.jsonl"):
        (tmp_path / p).write_text("{}")
    ap = build_parser()

    base = ["fit", "--config", str(tmp_path / "c.yaml"),
            "--splits", str(tmp_path / "f.json"),
            "--subjects", str(tmp_path / "s.jsonl"),
            "--windows", str(tmp_path / "w.jsonl"),
            "--rest-manifest", str(tmp_path / "r.jsonl"),
            "--output-dir", str(tmp_path)]
    fit_args = ["--cell", "A", "--outer-fold", "0", "--inner-fold", "1",
                "--model-seed", "42", "--config-id", "3", "--epochs", "12",
                "--task-manifests", str(tmp_path / "t.jsonl")]

    with pytest.raises(SystemExit):
        ap.parse_args(base)                      # fit 전용 인자 없음

    ns = ap.parse_args(base + fit_args)
    assert ns.cell == "A" and ns.model_seed == 42
    assert ns.config_id == 3 and ns.epochs == 12
    assert [str(x) for x in ns.task_manifests] == [str(tmp_path / "t.jsonl")]
    assert ns.device == "cpu" and ns.skip_hash_verify is False

    # 새 필수 인자를 하나씩 빼면 전부 거부되어야 한다.
    for drop in ("--subjects", "--rest-manifest"):
        pruned = [a for i, a in enumerate(base)
                  if a != drop and (i == 0 or base[i - 1] != drop)]
        with pytest.raises(SystemExit):
            ap.parse_args(pruned + fit_args)
    for drop in ("--config-id", "--task-manifests"):
        pruned = [a for i, a in enumerate(fit_args)
                  if a != drop and (i == 0 or fit_args[i - 1] != drop)]
        with pytest.raises(SystemExit):
            ap.parse_args(base + pruned)


def test_evaluate_requires_explicit_task_list(tmp_path):
    for p in ("c.yaml", "f.json", "p.jsonl", "m.json"):
        (tmp_path / p).write_text("{}")
    base = ["evaluate", "--config", str(tmp_path / "c.yaml"),
            "--splits", str(tmp_path / "f.json"),
            "--predictions", str(tmp_path / "p.jsonl"),
            "--fit-manifest", str(tmp_path / "m.json"),
            "--output-dir", str(tmp_path)]
    with pytest.raises(SystemExit):
        build_parser().parse_args(base)
    ns = build_parser().parse_args(base + ["--tasks", "emomatching", "workingmemory"])
    assert assert_classification_only(ns.tasks)


# ---------------------------------------------------------------------------
# validate 하위 명령 본체 (WI-06) — 원자료 없이 완결되는 유일한 명령
# ---------------------------------------------------------------------------

import copy as _copy
import json as _json

import pytest as _pytest

_yaml = _pytest.importorskip("yaml")

from mobse.v2 import cli as _cli

_CONFIG = (
    pathlib.Path(__file__).resolve().parents[2] / "configs" / "redesign_v1" / "main.yaml"
)

_AUDIT_RECORD = {
    "schema_version": _cli.AUDIT_SCHEMA_VERSION,
    "record_type": "run",
    "run_key": "piop1/sub-0001/na/emomatching/na/na",
    "dataset": "piop1",
    "canonical_subject": "sub-0001",
    "task": "emomatching",
    "n_volumes": 200,
    "group_id": None,
    "source_bold_path": None,
    "source_bold_sha256": None,
    "sidecar_json_path": None,
    "sidecar_json_sha256": None,
    "confounds_path": None,
    "confounds_sha256": None,
    "events_path": None,
    "events_sha256": None,
    "native_tr": None,
    "derivative_start_sec": None,
    "discarded_volumes": None,
    "event_origin": None,
    "atlas_id": None,
    "atlas_hash": None,
    "roi_order_hash": None,
    "usable_for_primary_analysis": False,
    "usable_reason": "G0 blocked",
    "unresolved": [
        "group_id_unknown", "source_bold_absent", "sidecar_absent",
        "confounds_absent", "events_absent", "native_tr_unknown",
        "derivative_start_sec_unknown", "discarded_volumes_unknown",
        "event_origin_unverifiable", "atlas_identity_unverified",
        "roi_order_unverified",
    ],
}
_AUDIT_HEADER = {"schema_version": _cli.AUDIT_SCHEMA_VERSION, "record_type": "header"}


def _write_audit(tmp_path, records):
    path = tmp_path / "source_runs.jsonl"
    lines = [_json.dumps(_AUDIT_HEADER, ensure_ascii=False)]
    lines += [_json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _paths(tmp_path, records):
    return {"config": str(_CONFIG), "source_runs": str(_write_audit(tmp_path, records))}


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_passes_on_well_formed_audit_manifest(tmp_path):
    result = _cli.run_validate(_paths(tmp_path, [_AUDIT_RECORD]))
    assert result["verdict"] == "pass", result["record_errors"]
    assert result["records"] == 1
    assert result["manifest_schema_version"] == _cli.AUDIT_SCHEMA_VERSION


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_rejects_null_without_reason(tmp_path):
    """이유 없는 null 이 조용한 default 자리다 (T02)."""
    bad = _copy.deepcopy(_AUDIT_RECORD)
    bad["unresolved"] = [r for r in bad["unresolved"] if "native_tr" not in r]
    result = _cli.run_validate(_paths(tmp_path, [bad]))
    assert result["verdict"] == "fail"
    assert any("native_tr" in e["error"] for e in result["record_errors"])


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_rejects_missing_audit_field(tmp_path):
    bad = _copy.deepcopy(_AUDIT_RECORD)
    del bad["confounds_sha256"]
    result = _cli.run_validate(_paths(tmp_path, [bad]))
    assert result["verdict"] == "fail"
    assert any("필드 누락" in e["error"] for e in result["record_errors"])


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_rejects_unusable_without_reason(tmp_path):
    bad = _copy.deepcopy(_AUDIT_RECORD)
    bad["usable_reason"] = ""
    result = _cli.run_validate(_paths(tmp_path, [bad]))
    assert result["verdict"] == "fail"
    assert any("사유가 없다" in e["error"] for e in result["record_errors"])


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_detects_duplicate_run_keys(tmp_path):
    result = _cli.run_validate(_paths(tmp_path, [_AUDIT_RECORD, _copy.deepcopy(_AUDIT_RECORD)]))
    assert result["verdict"] == "fail"
    assert any("중복" in e["error"] for e in result["record_errors"])


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_detects_tr_conflict_within_task(tmp_path):
    """TR 충돌을 조용히 평균 내지 않는다 (T02)."""
    a = _copy.deepcopy(_AUDIT_RECORD)
    a["native_tr"] = 2.0
    a["unresolved"] = [r for r in a["unresolved"] if "native_tr" not in r]
    b = _copy.deepcopy(a)
    b["run_key"] = a["run_key"].replace("sub-0001", "sub-0002")
    b["canonical_subject"] = "sub-0002"
    b["native_tr"] = 0.75
    result = _cli.run_validate(_paths(tmp_path, [a, b]))
    assert result["verdict"] == "fail"
    assert any("TR 충돌" in e["error"] for e in result["record_errors"])


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_collects_all_errors_not_just_first(tmp_path):
    bad = _copy.deepcopy(_AUDIT_RECORD)
    bad["unresolved"] = []
    result = _cli.run_validate(_paths(tmp_path, [bad]))
    assert len(result["record_errors"]) > 3, result["record_errors"]


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_rejects_malformed_json_line(tmp_path):
    path = tmp_path / "source_runs.jsonl"
    path.write_text(
        _json.dumps(_AUDIT_HEADER) + "\n{not json}\n", encoding="utf-8")
    result = _cli.run_validate({"config": str(_CONFIG), "source_runs": str(path)})
    assert result["verdict"] == "fail"
    assert any("JSON 파싱 실패" in e["error"] for e in result["record_errors"])


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_rejects_empty_manifest(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    with _pytest.raises(_cli.CLIError, match="비어 있다"):
        _cli.run_validate({"config": str(_CONFIG), "source_runs": str(path)})


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_propagates_config_error(tmp_path):
    bad_cfg = tmp_path / "bad.yaml"
    bad_cfg.write_text("meta:\n  name: x\n", encoding="utf-8")
    with _pytest.raises(_cli.CLIError, match="config 검증 실패"):
        _cli.run_validate({"config": str(bad_cfg),
                           "source_runs": str(_write_audit(tmp_path, [_AUDIT_RECORD]))})


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_main_returns_zero_on_pass(tmp_path, capsys):
    rc = _cli.main([
        "validate", "--config", str(_CONFIG),
        "--source-runs", str(_write_audit(tmp_path, [_AUDIT_RECORD])),
    ])
    assert rc == 0
    assert '"verdict": "pass"' in capsys.readouterr().out


@_pytest.mark.skipif(not _CONFIG.is_file(), reason="배포 config 없음")
def test_validate_main_returns_one_on_fail(tmp_path, capsys):
    bad = _copy.deepcopy(_AUDIT_RECORD)
    bad["unresolved"] = []
    rc = _cli.main([
        "validate", "--config", str(_CONFIG),
        "--source-runs", str(_write_audit(tmp_path, [bad])),
    ])
    assert rc == 1
    assert '"verdict": "fail"' in capsys.readouterr().out


def test_prepare_no_longer_takes_source_runs(tmp_path):
    """prepare 본체가 생기며 경로 계약이 바뀌었다 — 감사본 source_runs 를 받지 않는다
    (본체 시험은 test_cli_prepare.py)."""
    src = _write_audit(tmp_path, [_AUDIT_RECORD])
    with _pytest.raises(SystemExit):
        _cli.main(["prepare", "--config", str(_CONFIG), "--source-runs", str(src),
                   "--output-dir", str(tmp_path)])
