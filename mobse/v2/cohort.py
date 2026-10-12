"""WI-03 — WI-02 재추출 결과를 subject 단위 코호트로 접는다.

계획서 §3.3 의 primary complete-case 정의가 이 모듈의 유일한 기준이다:

    "두 task와 rest의 각 4개 window가 모두 유효한 subject만
     primary complete-case에 포함한다."

즉 subject 는 emomatching·workingmemory·restingstate **세 run 모두**가 QC 를
통과해야 적격이다. 하나라도 빠지면 부적격이고, **사유는 모두 보존한다**
(중복 사유와 우선 사유를 함께 저장하라는 §3.3 요구).

이 모듈은 분할을 하지 않는다. `splits.build_folds()` 가 먹을 수 있는 형태의
subject 목록을 만들 뿐이다. 분할 seed·알고리즘은 그쪽이 단일 출처다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "CohortError",
    "REQUIRED_TASKS",
    "TARGET_TASKS",
    "BANK_TASK",
    "SubjectRecord",
    "read_extract_manifest",
    "build_subjects",
    "subjects_to_records",
    "exclusion_records",
    "summarize",
]


class CohortError(RuntimeError):
    """코호트 구성 전제가 깨졌다."""


#: primary complete-case 에 필요한 run. 셋 다 있어야 한다 (계획서 §3.3).
TARGET_TASKS: Tuple[str, ...] = ("emomatching", "workingmemory")
BANK_TASK = "restingstate"
REQUIRED_TASKS: Tuple[str, ...] = TARGET_TASKS + (BANK_TASK,)

SCHEMA_VERSION = "wi03-subjects-0.1"
RULE_VERSION = "protocol-1.1-§3.3"


@dataclass
class SubjectRecord:
    """한 subject 의 적격 여부와 그 근거.

    Attributes:
        canonical_subject: `ds002785:sub-0001` 형식 (개정 P5).
        cohort: dataset accession.
        eligible: 세 run 이 모두 QC 를 통과했는가.
        present_tasks: manifest 에 레코드가 있었던 task.
        passed_tasks: QC 를 통과한 task.
        all_reasons: 부적격 사유 전부. 통과 시 빈 목록.
        primary_reason: 첫 사유. 통과 시 None.
        run_keys: task → run_key.
    """

    canonical_subject: str
    cohort: str
    eligible: bool = False
    present_tasks: Tuple[str, ...] = ()
    passed_tasks: Tuple[str, ...] = ()
    all_reasons: List[str] = field(default_factory=list)
    primary_reason: Optional[str] = None
    run_keys: Dict[str, str] = field(default_factory=dict)


def read_extract_manifest(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """WI-02 manifest(JSONL)를 읽는다.

    Returns:
        (헤더, run 레코드 목록).

    Raises:
        CohortError: 파일 부재, 빈 파일, 헤더 없음, JSON 오류.
    """
    path = Path(path)
    if not path.is_file():
        raise CohortError(f"manifest 가 없다: {path} (자동 탐색하지 않는다)")
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise CohortError(f"manifest 가 비었다: {path}")
    try:
        records = [json.loads(ln) for ln in lines]
    except json.JSONDecodeError as exc:
        raise CohortError(f"{path}: JSON 파싱 실패: {exc}") from exc
    header = records[0]
    if header.get("record_type") != "header":
        raise CohortError(f"{path}: 첫 줄이 헤더가 아니다")
    runs = [r for r in records[1:] if r.get("record_type") == "run"]
    return header, runs


def _task_of(header: Mapping[str, Any], record: Mapping[str, Any]) -> str:
    task = header.get("task") or record.get("task")
    if not task:
        raise CohortError(f"task 를 알 수 없다: {record.get('run_key')}")
    return str(task)


def build_subjects(manifests: Sequence[Tuple[Mapping[str, Any], Sequence[Mapping[str, Any]]]]
                   ) -> List[SubjectRecord]:
    """여러 WI-02 manifest 를 subject 단위로 접는다.

    Args:
        manifests: (헤더, run 레코드들) 의 목록. 보통 dataset×task 6개.

    Returns:
        `canonical_subject` 사전순 정렬된 기록.

    Raises:
        CohortError: dataset prefix 없는 subject, 같은 (subject, task) 중복.
    """
    by_subject: Dict[str, Dict[str, Mapping[str, Any]]] = {}
    tasks_seen: Dict[str, set] = {}

    for header, runs in manifests:
        for record in runs:
            subject = record.get("canonical_subject")
            if not subject or ":" not in subject:
                raise CohortError(
                    f"canonical_subject 에 dataset prefix 가 없다: {subject!r} "
                    "(개정 P5 — 자동 보정하지 않는다)")
            task = _task_of(header, record)
            slot = by_subject.setdefault(subject, {})
            if task in slot:
                raise CohortError(
                    f"{subject} 의 task {task} 가 중복이다 — 조용히 합치지 않는다")
            slot[task] = record
            tasks_seen.setdefault(subject.split(":", 1)[0], set()).add(task)

    out: List[SubjectRecord] = []
    for subject in sorted(by_subject):
        slot = by_subject[subject]
        cohort = subject.split(":", 1)[0]
        present = tuple(t for t in REQUIRED_TASKS if t in slot)
        passed = tuple(t for t in REQUIRED_TASKS
                       if slot.get(t, {}).get("status") == "ok")
        reasons: List[str] = []

        for task in REQUIRED_TASKS:
            record = slot.get(task)
            if record is None:
                reasons.append(f"{task}_missing")
                continue
            status = record.get("status")
            if status == "ok":
                continue
            detail = record.get("reason")
            if isinstance(detail, list):
                reasons.extend(f"{task}:{r}" for r in detail)
            elif detail:
                reasons.append(f"{task}:{detail}")
            else:
                reasons.append(f"{task}:{status}")

        out.append(SubjectRecord(
            canonical_subject=subject,
            cohort=cohort,
            eligible=not reasons,
            present_tasks=present,
            passed_tasks=passed,
            all_reasons=reasons,
            primary_reason=reasons[0] if reasons else None,
            run_keys={t: str(slot[t].get("run_key")) for t in sorted(slot)},
        ))
    return out


def subjects_to_records(subjects: Iterable[SubjectRecord],
                        *, assignment: str = "unassigned",
                        assignment_reason: str = "WI-03 분할 전") -> List[Dict[str, Any]]:
    """`manifests.SCHEMAS["subjects"]` 를 만족하는 레코드로 바꾼다.

    `group_id` 는 관계 metadata 부재로 subject 와 같다 (개정 P4, 차단 항목 U10).
    """
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_subject": s.canonical_subject,
            "group_id": s.canonical_subject,
            "cohort": s.cohort,
            "eligible": bool(s.eligible),
            "assignment": assignment if s.eligible else "excluded",
            "assignment_reason": assignment_reason if s.eligible
                                 else (s.primary_reason or "ineligible"),
        }
        for s in subjects
    ]


def exclusion_records(subjects: Iterable[SubjectRecord]) -> List[Dict[str, Any]]:
    """`manifests.SCHEMAS["exclusions"]` 를 만족하는 제외 레코드.

    중복 사유와 우선 사유를 **모두** 저장한다 (계획서 §3.3).
    """
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "key": s.canonical_subject,
            "key_level": "subject",
            "stage": "wi03_cohort",
            "all_reasons": list(s.all_reasons),
            "primary_reason": s.primary_reason or "",
            "rule_version": RULE_VERSION,
        }
        for s in subjects if not s.eligible
    ]


def summarize(subjects: Sequence[SubjectRecord]) -> Dict[str, Any]:
    """코호트 요약. 사유별 집계를 포함한다."""
    eligible = [s for s in subjects if s.eligible]
    by_cohort: Dict[str, Dict[str, int]] = {}
    for s in subjects:
        entry = by_cohort.setdefault(s.cohort, {"total": 0, "eligible": 0})
        entry["total"] += 1
        entry["eligible"] += int(s.eligible)

    reason_counts: Dict[str, int] = {}
    for s in subjects:
        for reason in set(s.all_reasons):  # 한 subject 가 같은 사유를 두 번 세지 않게
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "required_tasks": list(REQUIRED_TASKS),
        "n_subjects": len(subjects),
        "n_eligible": len(eligible),
        "by_cohort": dict(sorted(by_cohort.items())),
        "reason_counts": dict(sorted(reason_counts.items(),
                                     key=lambda kv: (-kv[1], kv[0]))),
        "group_id_policy": "1 subject = 1 group (관계 metadata 부재, 개정 P4 / U10)",
    }
