"""report 하위 명령 본체 (WI-06, 계획서 §8·§10) — 합성 release 로 evaluate → report.

실자료 fit 은 없다. 잠긴 main pool 을 소비하지 않는다. evaluate 시험의 합성 release
(outer fold 2 × cell 4 × seed 3, main pool 10명)를 그대로 쓴다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("yaml")

import importlib.util

from mobse.v2 import cli

# evaluate 시험의 합성 release fixture 를 파일 경로로 불러 재사용한다. import 문으로
# 부르면 import closure 가드가 third-party 로 오인한다 (핀 없는 모듈).
_spec = importlib.util.spec_from_file_location(
    "_mobse_test_cli_evaluate", Path(__file__).with_name("test_cli_evaluate.py"))
_ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ev)
CONFIG, _argv, release = _ev.CONFIG, _ev._argv, _ev.release

pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _subjects(path: Path, pool, *, group=None, drop=(), ineligible=()) -> Path:
    group = group or {}
    rows = [{"schema_version": "t", "canonical_subject": s,
             "group_id": group.get(s, s), "cohort": "ds002785",
             "eligible": s not in ineligible, "assignment": "main",
             "assignment_reason": "t"} for s in pool if s not in drop]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


@pytest.fixture()
def evaluated(release):  # noqa: F811
    ev = release["tmp"] / "ev"
    assert cli.main(_argv(release, ev)) == 0
    subj = _subjects(release["tmp"] / "subjects.jsonl", release["pool"])
    return {**release, "ev": ev, "subjects": subj}


def _rargv(e, out, *, subjects=None, evaluation=None, predictions=None):
    return ["report", "--config", str(CONFIG),
            "--evaluation", str(evaluation or e["ev"] / "evaluation.json"),
            "--predictions", str(predictions or e["ev"] / "run_predictions.jsonl"),
            "--subjects", str(subjects or e["subjects"]), "--output-dir", str(out)]


def _hand_ci(vec, n_groups_members, pct, seed=9001, n_boot=10_000):
    """statistics.py 를 쓰지 않는 독립 재계산 (subject 하나 = group 하나일 때)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    draws = rng.integers(0, n_groups_members, size=(n_boot, n_groups_members))
    stats = np.asarray(vec)[draws].mean(axis=1)
    return tuple(float(x) for x in np.percentile(stats, pct))


def test_report_hand_checked(evaluated, capsys):
    out = evaluated["tmp"] / "rep"
    assert cli.main(_rargv(evaluated, out)) == 0
    st = json.loads((out / "statistics.json").read_text(encoding="utf-8"))
    pool = sorted(evaluated["pool"])
    # B 는 짝수 subject 의 WM 을 틀린다 → b_B = 0.5 (5명), 나머지 cell 은 1.0
    h1_vec = [0.5 if int(s[-4:]) % 2 == 0 else 0.0 for s in pool]
    h1 = st["primary_contrasts"]["H1_A_minus_B"]
    assert h1["point_estimate"] == pytest.approx(0.25)
    assert (h1["ci_lo"], h1["ci_hi"]) == pytest.approx(_hand_ci(h1_vec, 10, (1.25, 98.75)))
    assert h1["percentiles"] == [1.25, 98.75]
    h2 = st["primary_contrasts"]["H2_A_minus_C"]
    assert (h2["point_estimate"], h2["ci_lo"], h2["ci_hi"]) == (0.0, 0.0, 0.0)
    assert "0 을 포함" in h2["interpretation"]
    assert st["both_primary_lower_gt_0"] is False
    inter = st["auxiliary_contrasts"]["interaction"]
    assert inter["percentiles"] == [2.5, 97.5]
    assert (inter["ci_lo"], inter["ci_hi"]) == pytest.approx(_hand_ci(h1_vec, 10, (2.5, 97.5)))
    assert st["cell_balanced_accuracy"]["B"]["point_estimate"] == pytest.approx(0.75)
    assert st["bootstrap"] == {"seed": 9001, "n_boot": 10_000, "shared_across_cells": True,
                               "unit": "group", "n_subjects": 10, "n_groups": 10}
    assert st["g3_verdict"]["significance_is_gate"] is False
    assert st["delta"] == 0.02


def test_report_refuses_to_overwrite(evaluated):
    out = evaluated["tmp"] / "rep"
    assert cli.main(_rargv(evaluated, out)) == 0
    with pytest.raises(cli.CLIError, match="덮어쓰지"):
        cli.main(_rargv(evaluated, out))


def test_family_group_is_resampled_whole(evaluated):
    pool = sorted(evaluated["pool"])
    subj = _subjects(evaluated["tmp"] / "fam.jsonl", pool,
                     group={pool[1]: "fam-1", pool[3]: "fam-1"})
    out = evaluated["tmp"] / "rep"
    assert cli.main(_rargv(evaluated, out, subjects=subj)) == 0
    st = json.loads((out / "statistics.json").read_text(encoding="utf-8"))
    assert st["bootstrap"]["n_groups"] == 9
    assert st["primary_contrasts"]["H1_A_minus_B"]["n_groups"] == 9


def test_tampered_run_predictions_fail_sha(evaluated):
    p = evaluated["ev"] / "run_predictions.jsonl"
    p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(cli.CLIError, match="sha256"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep"))


def _rewrite_runs(e, fn):
    """run 행을 고치고 evaluation.json 의 sha 기록도 맞춘다 — 내용 검사만 남긴다."""
    p = e["ev"] / "run_predictions.jsonl"
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x]
    blob = "".join(json.dumps(r, sort_keys=True) + "\n" for r in fn(rows))
    p.write_text(blob, encoding="utf-8")
    ev = json.loads((e["ev"] / "evaluation.json").read_text(encoding="utf-8"))
    ev["run_predictions"]["sha256"] = hashlib.sha256(blob.encode()).hexdigest()
    (e["ev"] / "evaluation.json").write_text(json.dumps(ev), encoding="utf-8")


def test_prediction_inconsistent_with_threshold_fails(evaluated):
    def flip(rows):
        rows[0]["prediction"] = 1 - rows[0]["prediction"]
        return rows
    _rewrite_runs(evaluated, flip)
    with pytest.raises(cli.CLIError, match="임계 판정"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep"))


def test_consistent_flip_is_caught_by_evaluation_crosscheck(evaluated):
    def flip(rows):
        rows[0]["ensemble_p"] = 1.0 - rows[0]["ensemble_p"]
        rows[0]["prediction"] = 1 - rows[0]["prediction"]
        return rows
    _rewrite_runs(evaluated, flip)
    with pytest.raises(cli.CLIError, match="evaluation.json 과 다르다"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep"))


def test_dropped_run_fails_complete_case(evaluated):
    _rewrite_runs(evaluated, lambda rows: rows[1:])
    with pytest.raises(cli.CLIError, match="complete-case|subject 집합"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep"))


def test_subject_without_group_fails(evaluated):
    subj = _subjects(evaluated["tmp"] / "s2.jsonl", evaluated["pool"],
                     drop=(evaluated["pool"][0],))
    with pytest.raises(cli.CLIError, match="group 이 없는"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep", subjects=subj))


def test_ineligible_subject_fails(evaluated):
    subj = _subjects(evaluated["tmp"] / "s3.jsonl", evaluated["pool"],
                     ineligible=(evaluated["pool"][0],))
    with pytest.raises(cli.CLIError, match="부적격"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep", subjects=subj))


def test_config_hash_mismatch_fails(evaluated):
    p = evaluated["ev"] / "evaluation.json"
    ev = json.loads(p.read_text(encoding="utf-8"))
    ev["config_hash"] = "0" * 64
    p.write_text(json.dumps(ev), encoding="utf-8")
    with pytest.raises(cli.CLIError, match="config_hash"):
        cli.main(_rargv(evaluated, evaluated["tmp"] / "rep"))


def test_parser_requires_evaluation_and_subjects():
    assert set(cli.REQUIRED_PATHS["report"]) == {
        "config", "evaluation", "predictions", "subjects", "output_dir"}
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["report", "--config", "c", "--predictions", "p",
                                       "--output-dir", "o"])
