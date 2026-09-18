"""T01–T16 수용 시험이 하나도 빠지지 않았는지 suite 안에서 강제한다.

지침서 §6 의 수용 시험 표가 단일 기준이다. 시험을 지우거나 이름만 바꿔 놓고
"통과"로 보고하는 일을 막기 위해, 각 T-ID 가 tests/v2 안에서 최소 1회
참조되는지 확인한다. 참조는 docstring 또는 주석에 `T07` 형태로 적는다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
INSTRUCTIONS = (
    REPO_ROOT / "docs" / "experiments" / "mobse_redesign_work_instructions_2026-09-17.md"
)

EXPECTED_IDS = tuple(f"T{i:02d}" for i in range(1, 17))

# T-ID -> 그 시험을 담당하는 파일. 담당이 바뀌면 여기도 함께 바꾼다.
OWNER: Dict[str, str] = {
    "T01": "test_preprocess.py",
    "T02": "test_manifests.py",
    "T03": "test_splits.py",
    "T04": "test_features.py",
    "T05": "test_templates.py",
    "T06": "test_models.py",
    "T07": "test_features.py",
    "T08": "test_models.py",
    "T09": "test_models.py",
    "T10": "test_models.py",
    "T11": "test_manifests.py",
    "T12": "test_train.py",
    "T13": "test_statistics.py",
    "T14": "test_statistics.py",
    "T15": "test_evaluate_cli.py",
    "T16": "test_evaluate_cli.py",
}


def _references() -> Dict[str, List[str]]:
    """tests/v2 안에서 각 T-ID 를 참조하는 파일 목록을 만든다."""
    found: Dict[str, List[str]] = {tid: [] for tid in EXPECTED_IDS}
    pattern = re.compile(r"\bT(0[1-9]|1[0-6])\b")
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for match in set(pattern.findall(text)):
            found[f"T{match}"].append(path.name)
    return found


def test_every_acceptance_id_has_a_test():
    found = _references()
    uncovered = [tid for tid, files in found.items() if not files]
    assert not uncovered, f"수용 시험 참조가 없는 T-ID: {', '.join(uncovered)}"


def test_named_owner_file_actually_references_id():
    found = _references()
    wrong = [
        f"{tid}: {OWNER[tid]} 에 없음 (현재 {found[tid]})"
        for tid in EXPECTED_IDS
        if OWNER[tid] not in found[tid]
    ]
    assert not wrong, "담당 파일이 해당 T-ID 를 참조하지 않는다: " + "; ".join(wrong)


def test_instruction_table_still_defines_sixteen_ids():
    """지침서 쪽 표가 늘어나면(T17…) 이 시험이 먼저 깨져 알려준다."""
    if not INSTRUCTIONS.is_file():
        import pytest

        pytest.skip(f"지침서 없음: {INSTRUCTIONS}")
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    declared = sorted(set(re.findall(r"^\| (T\d{2}) ", text, flags=re.MULTILINE)))
    assert declared == list(EXPECTED_IDS), (
        f"지침서가 정의한 T-ID 집합이 바뀌었다: {declared}"
    )
