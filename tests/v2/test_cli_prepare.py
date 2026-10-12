"""prepare 하위 명령 본체 (WI-06) — 합성 WI-02 manifest 로 windows·subjects 를 접는다.

원자료·잠긴 분할을 읽지 않는다. 핵심 대조는 `scripts/h197/12`·`15` 와 바이트 동일성이다
(같은 입력 → 같은 windows.jsonl·subjects.jsonl·exclusions.jsonl).
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from mobse.v2 import cli
from mobse.v2.preprocess import SAMPLES_PER_WINDOW, WINDOW_STARTS

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "redesign_v1" / "main.yaml"
ATLAS = "b" * 64

pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _header(task, dataset="ds002785", **kw):
    h = {"record_type": "header", "schema_version": "wi02-extract-0.2",
         "dataset": dataset, "task": task, "native_tr": 2.0,
         "atlas_sha256": ATLAS, "analysis_interval_sec": [12.0, 252.0],
         "bandpass_hz": [0.008, 0.2], "dry_run": False}
    h.update(kw)
    return h


def _run(subject, task, status="ok", dataset="ds002785", reason=None):
    rk = f"{dataset}/{subject}/na/{task}/na/seq"
    rec = {"record_type": "run", "run_key": rk,
           "canonical_subject": f"{dataset}:{subject}", "status": status}
    if status == "ok":
        rec["windows"] = [
            {"path": f"/x/{subject}_{task}_{i}.npy",
             "sha256": hashlib.sha256(f"{rk}{i}".encode()).hexdigest(),
             "shape": [SAMPLES_PER_WINDOW, 100], "start_sec": float(s),
             "source_frame_range": [4 + 30 * i, 34 + 30 * i]}
            for i, s in enumerate(WINDOW_STARTS)]
    else:
        rec["reason"] = reason or "mean_fd>0.2"
        rec["primary_reason"] = rec["reason"]
    return rec


#: sub-0003 은 workingmemory 제외 → 부적격, sub-0004 는 rest 제외 → 부적격.
STATUS = {("sub-0003", "workingmemory"): "excluded", ("sub-0004", "restingstate"): "excluded"}
SUBJECTS = ["sub-0001", "sub-0002", "sub-0003", "sub-0004", "sub-0005"]
TASKS = ("emomatching", "workingmemory", "restingstate")


def _write(tmp, task, *, header=None, runs=None, dataset="ds002785", name=None):
    header = header or _header(task, dataset)
    runs = runs if runs is not None else [
        _run(s, task, STATUS.get((s, task), "ok"), dataset) for s in SUBJECTS]
    p = tmp / (name or f"wi02_{dataset}_{task}.jsonl")
    p.write_text("".join(json.dumps(r) + "\n" for r in [header, *runs]), encoding="utf-8")
    return p


@pytest.fixture()
def manifests(tmp_path):
    return {t: _write(tmp_path, t) for t in TASKS}


def _argv(paths, out):
    return ["prepare", "--config", str(CONFIG), "--extract-manifests",
            *[str(p) for p in paths], "--output-dir", str(out)]


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_prepare_is_byte_identical_to_scripts_12_and_15(manifests, tmp_path):
    """같은 입력이면 12·15 스크립트와 바이트 단위로 같은 산출물 (인자 순서도 섞는다)."""
    out = tmp_path / "prep"
    order = [manifests["restingstate"], manifests["workingmemory"], manifests["emomatching"]]
    assert cli.main(_argv(order, out)) == 0

    ref = tmp_path / "ref"
    ref.mkdir()
    env_py = sys.executable
    r12 = subprocess.run([env_py, str(REPO / "scripts/h197/12_build_windows_manifest.py"),
                          "--manifest", str(manifests["emomatching"]),
                          str(manifests["workingmemory"]),
                          "--output", str(ref / "windows.jsonl")],
                         capture_output=True, text=True, cwd=REPO)
    assert r12.returncode == 0, r12.stderr
    r15 = subprocess.run([env_py, str(REPO / "scripts/h197/15_build_subjects.py"),
                          "--manifest", *[str(manifests[t]) for t in TASKS],
                          "--output-dir", str(ref / "cohort")],
                         capture_output=True, text=True, cwd=REPO)
    assert r15.returncode == 0, r15.stderr

    assert _sha(out / "windows.jsonl") == _sha(ref / "windows.jsonl")
    assert _sha(out / "subjects.jsonl") == _sha(ref / "cohort" / "subjects.jsonl")
    assert _sha(out / "exclusions.jsonl") == _sha(ref / "cohort" / "exclusions.jsonl")


def test_counts_and_report(manifests, tmp_path):
    out = tmp_path / "prep"
    assert cli.main(_argv(manifests.values(), out)) == 0
    rep = json.loads((out / "prepare_report.json").read_text(encoding="utf-8"))
    # 창: emomatching 5 run × 4 + workingmemory 4 run × 4
    assert rep["n_windows"] == 36
    assert rep["n_subjects"] == 5 and rep["n_eligible"] == 3
    assert rep["config_hash"] == cli.config_hash(cli.load_config(CONFIG))
    assert rep["inputs"]["restingstate"]["sha256"] == _sha(manifests["restingstate"])
    assert rep["outputs"]["windows"]["sha256"] == _sha(out / "windows.jsonl")
    rows = [json.loads(x) for x in (out / "windows.jsonl").read_text().splitlines()]
    assert {r["observed_label"] for r in rows} == {"emomatching", "workingmemory"}
    assert not any("restingstate" in r["run_key"] for r in rows)


def test_argument_order_does_not_change_outputs(manifests, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert cli.main(_argv([manifests[t] for t in TASKS], a)) == 0
    assert cli.main(_argv([manifests[t] for t in reversed(TASKS)], b)) == 0
    for name in ("windows.jsonl", "subjects.jsonl", "exclusions.jsonl"):
        assert _sha(a / name) == _sha(b / name)


def test_refuses_overwrite(manifests, tmp_path):
    out = tmp_path / "prep"
    assert cli.main(_argv(manifests.values(), out)) == 0
    with pytest.raises(cli.CLIError, match="덮어쓰지 않는다"):
        cli.main(_argv(manifests.values(), out))


def test_missing_rest_is_rejected(manifests, tmp_path):
    with pytest.raises(cli.CLIError, match="누락"):
        cli.main(_argv([manifests["emomatching"], manifests["workingmemory"]],
                       tmp_path / "o"))
    assert not (tmp_path / "o").exists()


def test_duplicate_task_is_rejected(manifests, tmp_path):
    dup = _write(tmp_path, "emomatching", name="dup.jsonl")
    with pytest.raises(cli.CLIError, match="두 번"):
        cli.main(_argv([*manifests.values(), dup], tmp_path / "o"))


def test_mixed_dataset_is_rejected(manifests, tmp_path):
    other = _write(tmp_path, "restingstate", dataset="ds002790")
    with pytest.raises(cli.CLIError, match="섞였다"):
        cli.main(_argv([manifests["emomatching"], manifests["workingmemory"], other],
                       tmp_path / "o"))


def test_unknown_task_is_rejected(manifests, tmp_path):
    bad = _write(tmp_path, "faces")
    with pytest.raises(cli.CLIError, match="허용되지 않는다"):
        cli.main(_argv([*manifests.values(), bad], tmp_path / "o"))


@pytest.mark.parametrize("field,value,match", [
    ("schema_version", "wi02-extract-0.1", "schema_version"),
    ("analysis_interval_sec", [12.0, 250.0], "analysis_interval_sec"),
    ("bandpass_hz", [0.008, 0.1], "bandpass_hz"),
    ("bandpass_hz", None, "bandpass_hz"),
    ("dry_run", True, "dry_run"),
    ("dry_run", None, "dry_run"),
    ("atlas_sha256", "xyz", "atlas_sha256"),
])
def test_header_must_match_locked_conditions(manifests, tmp_path, field, value, match):
    """헤더에 기록만 되고 대조되지 않는 값이 없어야 한다 (E21·E22 류)."""
    h = _header("restingstate")
    if value is None:
        h.pop(field)
    else:
        h[field] = value
    bad = _write(tmp_path, "restingstate", header=h, name="bad.jsonl")
    with pytest.raises(cli.CLIError, match=match):
        cli.main(_argv([manifests["emomatching"], manifests["workingmemory"], bad],
                       tmp_path / "o"))


def test_atlas_must_agree_across_tasks(manifests, tmp_path):
    bad = _write(tmp_path, "restingstate", header=_header("restingstate", atlas_sha256="c" * 64),
                 name="bad.jsonl")
    with pytest.raises(cli.CLIError, match="atlas_sha256 가 다르다"):
        cli.main(_argv([manifests["emomatching"], manifests["workingmemory"], bad],
                       tmp_path / "o"))


def test_eligible_subject_with_missing_window_is_rejected(manifests, tmp_path, monkeypatch):
    """창 대조가 실제로 작동한다 — build_window_records 가 창 하나를 흘려도 잡는다."""
    from mobse.v2 import labels

    real = labels.build_window_records

    def drop_one(header, runs, **kw):
        out = real(header, runs, **kw)
        return out[1:] if header.get("task") == "workingmemory" else out

    monkeypatch.setattr(labels, "build_window_records", drop_one)
    with pytest.raises(cli.CLIError, match="창이 8개가 아니다"):
        cli.main(_argv(manifests.values(), tmp_path / "o"))
    assert not (tmp_path / "o" / "windows.jsonl").exists()


def test_old_source_runs_contract_is_gone(manifests, tmp_path):
    """prepare 는 --source-runs 를 받지 않는다 (경로 계약 변경, 부록 AE)."""
    assert cli.REQUIRED_PATHS["prepare"] == ("config", "extract_manifests", "output_dir")
    with pytest.raises(SystemExit):
        cli.main(["prepare", "--config", str(CONFIG), "--source-runs", str(tmp_path / "s"),
                  "--output-dir", str(tmp_path / "o")])


def test_every_subcommand_has_a_body():
    import inspect

    src = inspect.getsource(cli.main)
    assert "NotImplementedError" not in src
    for name in cli.SUBCOMMANDS:
        assert f'args.command == "{name}"' in src
