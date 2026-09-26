"""구현 잠금 스크립트 (scripts/h197/27) 의 순수 함수 시험 — 결정 21 명세 4.

junit 을 잘못 읽으면 "acceptance 통과" 가 거짓이 된다: parametrize 괄호를 떼지
않으면 대응표 이름과 안 맞고, skip·실패를 통과로 세면 잠금이 거짓을 기록한다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PATH = REPO_ROOT / "scripts" / "h197" / "27_build_implementation_lock.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("_h197_27", PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
<testcase classname="tests.v2.test_a" name="test_x[A-0]" time="0.1"/>
<testcase classname="tests.v2.test_a" name="test_x[B-1]" time="0.1"/>
<testcase classname="tests.v2.test_a" name="test_y" time="0.1"><skipped message="s"/></testcase>
<testcase classname="tests.v2.test_b" name="test_z" time="0.1"><failure message="f"/></testcase>
<testcase classname="tests.v2.test_b" name="test_w" time="0.1"><error message="e"/></testcase>
</testsuite></testsuites>
"""


def _junit(tmp_path):
    p = tmp_path / "j.xml"
    p.write_text(JUNIT, encoding="utf-8")
    return p


def test_parse_junit_counts_and_strips_parametrize(mod, tmp_path):
    j = mod.parse_junit(_junit(tmp_path))
    assert j["counts"] == {"passed": 2, "skipped": 1, "failed": 2}
    assert j["outcomes"]["tests/v2/test_a.py::test_x"] == {"passed"}
    assert j["outcomes"]["tests/v2/test_a.py::test_y"] == {"skipped"}
    assert j["outcomes"]["tests/v2/test_b.py::test_w"] == {"failed"}


def _map(*tests):
    return {"items": [{"id": "T01", "coverage": "full", "tests": list(tests)}]}


def test_named_tests_all_passed(mod, tmp_path):
    j = mod.parse_junit(_junit(tmp_path))
    r = mod.named_test_results(_map("tests/v2/test_a.py::test_x"), j["outcomes"])
    assert r["per_item"]["T01"]["all_passed"] is True
    assert r["missing"] == [] and r["not_passed"] == []


@pytest.mark.parametrize("name", ["tests/v2/test_a.py::test_y",
                                  "tests/v2/test_b.py::test_z"])
def test_skipped_or_failed_named_test_is_not_passed(mod, tmp_path, name):
    j = mod.parse_junit(_junit(tmp_path))
    r = mod.named_test_results(_map("tests/v2/test_a.py::test_x", name), j["outcomes"])
    assert r["per_item"]["T01"]["all_passed"] is False
    assert r["not_passed"] == [name]


def test_missing_named_test_is_reported(mod, tmp_path):
    j = mod.parse_junit(_junit(tmp_path))
    r = mod.named_test_results(_map("tests/v2/test_a.py::test_nope"), j["outcomes"])
    assert r["missing"] == ["tests/v2/test_a.py::test_nope"]
    assert r["per_item"]["T01"]["all_passed"] is False


def test_mixed_passed_and_failed_cases_are_not_passed(mod, tmp_path):
    p = tmp_path / "m.xml"
    p.write_text(JUNIT.replace('name="test_x[B-1]" time="0.1"/>',
                               'name="test_x[B-1]" time="0.1"><failure/></testcase>'),
                 encoding="utf-8")
    j = mod.parse_junit(p)
    r = mod.named_test_results(_map("tests/v2/test_a.py::test_x"), j["outcomes"])
    assert r["not_passed"] == ["tests/v2/test_a.py::test_x"]
