"""사전 등록 문서의 개정 기록 무결성 (계획서 §11).

계획서는 사전 등록 문서이므로 본문을 조용히 고치면 안 된다. 본문의 `[개정 Pn]`
표시와 §11 표가 1:1 로 맞물리는지 시험으로 강제한다. 표시만 지우거나 표만
지우는 두 방향의 사고를 모두 잡는다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs" / "experiments"
PROTOCOL = DOCS / "mobse_redesign_protocol_2026-09-17.md"
INSTRUCTIONS = DOCS / "mobse_redesign_work_instructions_2026-09-17.md"
AMENDMENT_HEADING = "## 11. 개정 기록"
MARKER = re.compile(r"\[개정 (P\d(?:-[ab])?)\]")
#: 본문 표시 없이 표에만 남는 개정 (철회된 것).
WITHDRAWN = {"P3"}


@pytest.fixture(scope="module")
def protocol() -> str:
    if not PROTOCOL.is_file():
        pytest.skip(f"계획서 없음: {PROTOCOL}")
    return PROTOCOL.read_text(encoding="utf-8")


def _split(text: str):
    head, sep, tail = text.partition(AMENDMENT_HEADING)
    assert sep, "§11 개정 기록 절이 없다"
    return head, tail


def test_amendment_section_exists(protocol):
    assert AMENDMENT_HEADING in protocol


def test_every_body_marker_has_a_table_row(protocol):
    head, tail = _split(protocol)
    body = set(MARKER.findall(head))
    table = set(re.findall(r"^\| (P\d(?:-[ab])?) \|", tail, flags=re.M))
    orphan = sorted(body - table)
    assert not orphan, f"본문에만 있고 §11 표에 없는 개정: {orphan}"


def test_every_table_row_is_marked_or_withdrawn(protocol):
    head, tail = _split(protocol)
    body = set(MARKER.findall(head))
    table = set(re.findall(r"^\| (P\d(?:-[ab])?) \|", tail, flags=re.M))
    unmarked = sorted(table - body - WITHDRAWN)
    assert not unmarked, f"§11 표에만 있고 본문 표시가 없는 개정: {unmarked}"


def test_withdrawn_amendment_is_declared_withdrawn(protocol):
    _, tail = _split(protocol)
    for pid in WITHDRAWN:
        assert f"**{pid} 철회" in tail or f"{pid} | " in tail, f"{pid} 철회 선언이 없다"
    assert "철회" in tail


def test_amendments_record_no_relaxation(protocol):
    """개정이 QC 기준을 완화하지 않았다는 선언이 유지되는지."""
    _, tail = _split(protocol)
    assert "완화" in tail, "완화 여부 선언이 사라졌다"


def test_instructions_carry_p5(protocol):
    if not INSTRUCTIONS.is_file():
        pytest.skip(f"지침서 없음: {INSTRUCTIONS}")
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    assert "[개정 P5]" in text, "지침서에 P5 반영이 없다"
    assert "ds002785:sub-0001" in text, "P5 예시가 코드 형식과 다르다"


def test_p5_example_matches_code(protocol):
    """문서의 예시가 실제 검증기를 통과해야 한다 — 문서와 코드의 불일치 방지."""
    from mobse.v2.manifests import validate_canonical_subject

    examples = set(re.findall(r"`(ds\d+:sub-[A-Za-z0-9]+)`", protocol))
    assert examples, "계획서에 canonical_subject 예시가 없다"
    for example in examples:
        validate_canonical_subject(example)  # 실패하면 ManifestError


def test_p6b_formula_present(protocol):
    head, _ = _split(protocol)
    assert "residual_dof = min(" in head, "P6-b 의 동결된 수식이 본문에 없다"
    assert "rank(design)" in head


def test_p10_exact_formula_replaces_p6b(protocol):
    """개정 P10 — 정확식이 본문에 있고, P6-b 식은 기록으로 남아 있다."""
    head, _ = _split(protocol)
    assert "[개정 P10]" in head
    assert "residual_dof = n_volumes - rank([design, dct_stopband_basis])" in head
    assert "| P10 |" in protocol


def test_p9_decision_quoted_verbatim(protocol):
    """결정 9 원문을 넓히지 않고 인용한다."""
    assert "\"통과대역 0.2 Hz로\"" in protocol
    head, _ = _split(protocol)
    assert "0.008–0.2 Hz" in head


def test_fixed_window_definition_unchanged(protocol):
    """P3 철회의 의미 — [12,252) 는 수정 없이 남아야 한다."""
    head, _ = _split(protocol)
    assert "[12,252)" in head
    for start in ("[12,72)", "[72,132)", "[132,192)", "[192,252)"):
        assert start in head, f"고정 window {start} 가 사라졌다"
