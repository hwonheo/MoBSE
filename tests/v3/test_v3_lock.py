"""v3 구현 잠금 — `scripts/h197/29_build_v3_lock.py`.

잠금이 **다시 재어** 본다는 것, 그리고 v1 의 code_hash 를 쓸 수 없는 이유를
고정한다. `tests/v2/test_h197_scripts.py` 가 이 스크립트의 import·docstring·
import 시 부작용 없음을 이미 본다 — 여기서는 잠금 규칙만 본다.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "h197" / "29_build_v3_lock.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_v3_lock", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_v1_code_hash_cannot_be_used_here(mod):
    """v2 의 code_hash 는 파일명이 겹치면 거부한다 — v3 가 일곱 개를 겹쳐 쓴다."""
    from mobse.v2.manifests import ManifestError, code_hash
    paths = mod.module_paths(ROOT)
    names = [p.name for p in paths]
    dup = sorted({n for n in names if names.count(n) > 1})
    assert len(dup) >= 7, f"겹치는 파일명이 예상보다 적다: {dup}"
    with pytest.raises(ManifestError, match="파일명이 겹친다"):
        code_hash(paths)


def test_v3_code_hash_is_path_based_and_deterministic(mod):
    paths = mod.module_paths(ROOT)
    a = mod.v3_code_hash(ROOT, paths)
    b = mod.v3_code_hash(ROOT, list(reversed(paths)))
    assert a == b, "경로 순서가 해시를 바꾼다"
    assert len(a) == 64


def test_code_hash_covers_both_module_dirs(mod):
    paths = [str(p.relative_to(ROOT)) for p in mod.module_paths(ROOT)]
    assert any(p.startswith("mobse/v3/") for p in paths)
    assert any(p.startswith("mobse/v2/") for p in paths)
    assert mod.CODE_DIRS == ("mobse/v3", "mobse/v2")


def test_build_then_verify_round_trip(mod, tmp_path, monkeypatch):
    out = tmp_path / "v3_lock.json"
    args = mod.argparse.Namespace(repo_root=ROOT, out=out, verify=False,
                                  measurement_lock=None, pytest_junit=None,
                                  reason="시험")
    payload = mod.build(args)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert mod.verify(payload, args) == []


def test_verify_catches_a_changed_module(mod, tmp_path):
    args = mod.argparse.Namespace(repo_root=ROOT, out=tmp_path / "x.json",
                                  verify=True, measurement_lock=None,
                                  pytest_junit=None, reason="")
    payload = mod.build(args)
    key = "mobse/v3/train.py"
    assert key in payload["code"]["modules"]
    payload["code"]["modules"][key] = "0" * 64
    problems = mod.verify(payload, args)
    assert any("train.py" in p for p in problems)


def test_verify_catches_a_removed_or_added_module(mod, tmp_path):
    args = mod.argparse.Namespace(repo_root=ROOT, out=tmp_path / "x.json",
                                  verify=True, measurement_lock=None,
                                  pytest_junit=None, reason="")
    payload = mod.build(args)
    payload["code"]["modules"].pop("mobse/v3/subsample.py")
    payload["code"]["modules"]["mobse/v3/없던파일.py"] = "0" * 64
    problems = mod.verify(payload, args)
    assert any("기록되지 않은 모듈" in p for p in problems)
    assert any("사라진 모듈" in p for p in problems)


def test_tests_section_does_not_count_missing_junit_as_zero(mod):
    rec = mod.tests_section(None)
    assert rec["status"] == "not_reported"
    assert "passed" not in rec, "재지 않은 것을 0 으로 세면 안 된다"


def test_measurement_lock_is_referenced_not_rebuilt(mod):
    lock = ROOT / "results/redesign_v1/20260917_3c458d507e82_nocfg/locks/measurement_lock.json"
    rec = mod.measurement_ref(lock)
    assert rec["status"] == "referenced"
    assert rec["lock_hash"].startswith("9b7b11cf")
    assert mod.measurement_ref(None)["status"] == "not_reported"
