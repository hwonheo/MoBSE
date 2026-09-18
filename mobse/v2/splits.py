"""불변 grouped split — 재설계 프로토콜 v1.1 §4 구현.

의존성은 numpy 뿐이다. 원자료가 없어도 subject ID 목록만으로 완성·검증된다.

프로토콜이 규정한 것을 그대로 옮긴다.

* `group_id` 는 canonical subject 와 알려진 가족/중복 관계를 묶는다. 관계
  metadata 가 없으면 subject 하나가 곧 group 이다(차단 항목 U10). 이 모듈은
  어느 쪽이든 동일하게 동작하며, 어떤 가정을 썼는지는 manifest 에 남는다.
* pilot 목표 인원은 ``min(32, floor(0.2N))`` 이고 **목표를 넘기지 않는 전체
  group 만** 배정한다. group 을 쪼개지 않는다.
* fold 배정은 지정 seed 의 NumPy PCG64 로 group tie-break 순서를 만든 뒤,
  group 인원수 내림차순(동률은 그 순서)으로 **현재 subject 수가 가장 적은
  fold** 에 넣는다. fold 인원 동률이면 작은 fold index 를 택한다.
* inner 는 해당 outer train 에만 같은 알고리즘을 적용한다.
* 확정된 ``folds.json`` 과 그 hash 가 실행의 최종 기준이다.

Seeds (프로토콜 §4-2, §4-3):
    pilot        20260917
    outer        20260918
    inner        20261000 + outer_fold   (fold 0–4)
    external     20262000
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

PILOT_SEED = 20260917
OUTER_SEED = 20260918
INNER_SEED_BASE = 20261000
EXTERNAL_SEED = 20262000

PILOT_CAP = 32
PILOT_FRACTION = 0.2


class SplitError(RuntimeError):
    """분할 규칙 위반. 조용히 축소하지 않고 실패시킨다."""


@dataclass(frozen=True)
class Group:
    """가족/중복 관계로 묶인 subject 집합.

    Attributes:
        group_id: group 식별자.
        subjects: canonical subject ID. dataset prefix 를 포함해야 한다
            (차단 항목 U17: PIOP1/PIOP2 가 같은 ``sub-0001…`` 네임스페이스를 쓴다).
    """

    group_id: str
    subjects: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.group_id:
            raise SplitError("group_id 가 비어 있다")
        if not self.subjects:
            raise SplitError(f"group {self.group_id} 에 subject 가 없다")
        if len(set(self.subjects)) != len(self.subjects):
            raise SplitError(f"group {self.group_id} 에 중복 subject 가 있다")

    @property
    def size(self) -> int:
        return len(self.subjects)


@dataclass(frozen=True)
class FoldAssignment:
    """한 단계(outer 또는 inner)의 fold 배정 결과."""

    seed: int
    n_folds: int
    fold_groups: Tuple[Tuple[str, ...], ...]
    fold_subjects: Tuple[Tuple[str, ...], ...]

    @property
    def sizes(self) -> Tuple[int, ...]:
        return tuple(len(s) for s in self.fold_subjects)


def make_groups(
    subject_to_group: Optional[Mapping[str, str]] = None,
    subjects: Optional[Iterable[str]] = None,
) -> List[Group]:
    """subject→group 매핑에서 Group 목록을 만든다.

    Args:
        subject_to_group: subject ID → group ID. None 이면 `subjects` 로부터
            subject 하나당 group 하나(퇴화 형태)를 만든다.
        subjects: `subject_to_group` 이 None 일 때 쓰는 subject 목록.

    Returns:
        group_id 사전순으로 정렬된 Group 목록. subject 도 사전순이다.

    Raises:
        SplitError: 두 인자가 모두 없거나 모두 주어진 경우.
    """
    if (subject_to_group is None) == (subjects is None):
        raise SplitError("subject_to_group 과 subjects 중 정확히 하나를 주어야 한다")
    if subject_to_group is None:
        mapping = {s: s for s in subjects}  # type: ignore[union-attr]
    else:
        mapping = dict(subject_to_group)

    buckets: Dict[str, List[str]] = {}
    for subject, gid in mapping.items():
        buckets.setdefault(gid, []).append(subject)
    return [Group(gid, tuple(sorted(members)))
            for gid, members in sorted(buckets.items())]


def _tie_break_rank(n_groups: int, seed: int) -> np.ndarray:
    """지정 seed 의 PCG64 로 group tie-break 순위를 만든다."""
    rng = np.random.Generator(np.random.PCG64(seed))
    return rng.permutation(n_groups)


def order_groups(groups: Sequence[Group], seed: int) -> List[Group]:
    """인원수 내림차순, 동률은 seed 가 만든 tie-break 순서로 정렬한다."""
    rank = _tie_break_rank(len(groups), seed)
    return [g for _, _, g in sorted(
        ((-g.size, int(rank[i]), g) for i, g in enumerate(groups)),
        key=lambda t: (t[0], t[1]),
    )]


def assign_to_folds(groups: Sequence[Group], n_folds: int, seed: int) -> FoldAssignment:
    """group 을 fold 에 배정한다 (프로토콜 §4-4).

    현재 subject 수가 가장 적은 fold 에 넣고, 동률이면 작은 fold index 를 쓴다.

    Raises:
        SplitError: group 수가 fold 수보다 적어 빈 fold 가 생기는 경우.
            프로토콜은 자동 축소를 금지한다.
    """
    if n_folds < 2:
        raise SplitError(f"n_folds 는 2 이상이어야 한다: {n_folds}")
    if len(groups) < n_folds:
        raise SplitError(
            f"group {len(groups)}개로 {n_folds} fold 를 만들 수 없다. "
            "프로토콜 §4-3: 분할을 자동 축소하지 않고 설계를 갱신한다")

    fold_groups: List[List[str]] = [[] for _ in range(n_folds)]
    fold_subjects: List[List[str]] = [[] for _ in range(n_folds)]
    for g in order_groups(groups, seed):
        counts = [len(s) for s in fold_subjects]
        target = min(range(n_folds), key=lambda i: (counts[i], i))
        fold_groups[target].append(g.group_id)
        fold_subjects[target].extend(g.subjects)

    empty = [i for i, s in enumerate(fold_subjects) if not s]
    if empty:
        raise SplitError(f"빈 fold 가 생겼다: {empty}")

    return FoldAssignment(
        seed=seed, n_folds=n_folds,
        fold_groups=tuple(tuple(sorted(f)) for f in fold_groups),
        fold_subjects=tuple(tuple(sorted(s)) for s in fold_subjects),
    )


@dataclass(frozen=True)
class PilotSelection:
    """pilot 분리 결과 (프로토콜 §4-2)."""

    seed: int
    target: int
    group_ids: Tuple[str, ...]
    subjects: Tuple[str, ...]
    shortfall_reason: Optional[str] = None

    @property
    def n(self) -> int:
        return len(self.subjects)


def select_pilot(groups: Sequence[Group], seed: int = PILOT_SEED,
                 cap: int = PILOT_CAP, fraction: float = PILOT_FRACTION) -> PilotSelection:
    """pilot 을 분리한다. 목표를 넘기지 않는 전체 group 만 배정한다.

    pilot 은 구현·설정 점검용이며 **main 및 최종 external 의 모든 model/template
    fit 에서 제외된다**(프로토콜 §4-2).
    """
    total = sum(g.size for g in groups)
    target = min(cap, int(total * fraction))
    chosen: List[Group] = []
    used = 0
    for g in order_groups(groups, seed):
        if used + g.size <= target:
            chosen.append(g)
            used += g.size
    reason = None
    if used < target:
        reason = (f"목표 {target}명에 {target - used}명 미달. group 을 쪼개지 않으므로 "
                  f"남은 group 크기가 모두 여유를 초과한다")
    return PilotSelection(
        seed=seed, target=target,
        group_ids=tuple(sorted(g.group_id for g in chosen)),
        subjects=tuple(sorted(s for g in chosen for s in g.subjects)),
        shortfall_reason=reason,
    )


def verify_disjoint(named_sets: Mapping[str, Iterable[str]]) -> None:
    """이름 붙은 subject 집합들이 서로 겹치지 않는지 확인한다.

    Raises:
        SplitError: 어떤 두 집합이라도 교집합이 있으면. 겹침은 조용히 넘기지 않는다.
    """
    sets = {k: set(v) for k, v in named_sets.items()}
    keys = sorted(sets)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            overlap = sets[a] & sets[b]
            if overlap:
                raise SplitError(
                    f"{a} 와 {b} 의 교집합이 비어 있지 않다: {sorted(overlap)[:5]}"
                    f" (총 {len(overlap)}명)")


def build_folds(
    groups: Sequence[Group],
    *,
    n_outer: int = 5,
    n_inner: int = 3,
    pilot_seed: int = PILOT_SEED,
    outer_seed: int = OUTER_SEED,
    inner_seed_base: int = INNER_SEED_BASE,
    grouping_assumption: str = "one subject per group (no family/duplicate metadata)",
) -> Dict[str, object]:
    """pilot 분리와 outer/inner fold 를 모두 만들어 manifest 를 돌려준다.

    Returns:
        ``folds.json`` 으로 직렬화할 dict. 모든 경계는 subject ID 목록으로 명시되며
        `split_hash` 는 그 내용의 SHA256 이다.

    Raises:
        SplitError: 경계가 겹치거나 fold 를 만들 수 없는 경우.
    """
    all_subjects = sorted(s for g in groups for s in g.subjects)
    if len(set(all_subjects)) != len(all_subjects):
        raise SplitError("group 간에 subject 가 중복된다")

    pilot = select_pilot(groups, seed=pilot_seed)
    pilot_ids = set(pilot.group_ids)
    main_groups = [g for g in groups if g.group_id not in pilot_ids]
    if not main_groups:
        raise SplitError("pilot 분리 후 main pool 이 비었다")

    outer = assign_to_folds(main_groups, n_outer, outer_seed)
    by_id = {g.group_id: g for g in main_groups}

    outer_payload = []
    for k in range(n_outer):
        test_groups = [by_id[gid] for gid in outer.fold_groups[k]]
        train_groups = [g for g in main_groups if g.group_id not in set(outer.fold_groups[k])]
        inner_seed = inner_seed_base + k
        inner = assign_to_folds(train_groups, n_inner, inner_seed)

        test_subjects = sorted(s for g in test_groups for s in g.subjects)
        train_subjects = sorted(s for g in train_groups for s in g.subjects)
        verify_disjoint({"outer_test": test_subjects, "outer_train": train_subjects,
                         "pilot": pilot.subjects})

        inner_payload = []
        for j in range(n_inner):
            val = list(inner.fold_subjects[j])
            tr = sorted(set(train_subjects) - set(val))
            verify_disjoint({"inner_val": val, "inner_train": tr,
                             "outer_test": test_subjects, "pilot": pilot.subjects})
            inner_payload.append({
                "inner_fold": j, "seed": inner_seed,
                "val_groups": list(inner.fold_groups[j]),
                "val_subjects": val, "train_subjects": tr,
            })

        outer_payload.append({
            "outer_fold": k, "seed": outer_seed,
            "test_groups": list(outer.fold_groups[k]),
            "test_subjects": test_subjects,
            "train_subjects": train_subjects,
            "inner": inner_payload,
        })

    manifest: Dict[str, object] = {
        "schema_version": "folds_v1",
        "algorithm": ("PCG64 tie-break order; groups by size desc (ties by that order); "
                      "assign to fold with fewest subjects; fold ties to smallest index"),
        "library": {"numpy": np.__version__},
        "grouping_assumption": grouping_assumption,
        "seeds": {"pilot": pilot_seed, "outer": outer_seed,
                  "inner_base": inner_seed_base, "external": EXTERNAL_SEED},
        "n_subjects_total": len(all_subjects),
        "n_groups_total": len(groups),
        "pilot": {
            "seed": pilot.seed, "target": pilot.target, "n": pilot.n,
            "groups": list(pilot.group_ids), "subjects": list(pilot.subjects),
            "shortfall_reason": pilot.shortfall_reason,
            "note": "pilot 은 main 과 최종 external 의 모든 fit 에서 제외된다",
        },
        "main_pool": {
            "n_subjects": len(all_subjects) - pilot.n,
            "n_groups": len(main_groups),
            "subjects": sorted(s for g in main_groups for s in g.subjects),
        },
        "outer_folds": outer_payload,
    }
    manifest["split_hash"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return manifest


def assert_fit_scope(allowed: Iterable[str], used: Iterable[str]) -> None:
    """fit 에 쓰인 subject 가 허용 집합 안에 있는지 확인한다 (T03).

    Raises:
        SplitError: 허용되지 않은 subject 가 하나라도 있으면.
    """
    allowed_set, used_set = set(allowed), set(used)
    illegal = used_set - allowed_set
    if illegal:
        raise SplitError(
            f"허용되지 않은 subject 가 fit 에 들어갔다: {sorted(illegal)[:5]} "
            f"(총 {len(illegal)}명)")
