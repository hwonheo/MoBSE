"""Classification-only 예측 집계 — 재설계 프로토콜 v1.1 §8, 지침서 WI-06.

의존성은 표준 라이브러리와 numpy(통계 모듈 경유) 뿐이다.

기존 `mobse/evaluate.py:107,132` 는 분기 없이 ETTh1 forecasting 을 **항상** 평가하고
profiling·FLOPs 까지 돌렸다(차단 항목 U19). 지침서 WI-05 의 중단 조건과 T16 이
그것을 금지하므로, 이 모듈은 분류만 다루고 학습하지 않은 task 를 자동 평가하지
않는다. 평가 대상 task 를 명시적으로 받고, 목록에 없는 task 가 들어오면 실패한다.

무결성 규칙(지침서 §2, T15):

* 각 main subject 는 cell 마다 정확히 한 outer-test fold 에 있고
  ``2 tasks × 4 windows × 3 seeds`` 를 갖는다.
* seed 나 window 가 빠진 채로 평균하지 않는다.
* checkpoint/fit hash 가 맞지 않으면 실패한다. glob 으로 대체 탐색하지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from mobse.v2.statistics import (
    N_SEEDS, N_WINDOWS, THRESHOLD, balanced_accuracy, classify,
    paired_difference, run_probability, subject_score,
)

CLASSIFICATION_TASKS = ("emomatching", "workingmemory")
CELLS = ("A", "B", "C", "D")


class EvaluationError(RuntimeError):
    """집계·무결성 규칙 위반. 불완전 평균이나 glob 대체를 하지 않는다."""


def assert_classification_only(tasks: Iterable[str]) -> Tuple[str, ...]:
    """평가 대상이 학습한 분류 task 뿐인지 확인한다 (T16).

    Raises:
        EvaluationError: 학습하지 않은 task 가 들어오면. 특히 ETTh1 같은
            forecasting task 를 자동으로 평가하지 않는다.
    """
    got = tuple(tasks)
    unknown = [t for t in got if t not in CLASSIFICATION_TASKS]
    if unknown:
        raise EvaluationError(
            f"학습하지 않은 task 를 평가하려 한다: {unknown}. "
            f"허용: {list(CLASSIFICATION_TASKS)} (T16, 차단 항목 U19)")
    if not got:
        raise EvaluationError("평가 대상 task 가 비었다")
    return got


@dataclass(frozen=True)
class WindowPrediction:
    """window 하나의 예측."""

    canonical_subject: str
    group_id: str
    task: str
    window_index: int
    model_seed: int
    cell: str
    truth: int
    p_class1: float

    def __post_init__(self) -> None:
        if self.cell not in CELLS:
            raise EvaluationError(f"알 수 없는 cell: {self.cell!r}")
        if self.task not in CLASSIFICATION_TASKS:
            raise EvaluationError(f"알 수 없는 task: {self.task!r}")
        if not 0.0 <= self.p_class1 <= 1.0:
            raise EvaluationError(f"확률이 [0,1] 밖이다: {self.p_class1}")
        if self.truth not in (0, 1):
            raise EvaluationError(f"truth 는 0|1 이어야 한다: {self.truth}")


def aggregate_runs(predictions: Sequence[WindowPrediction], *,
                   n_windows: int = N_WINDOWS, n_seeds: int = N_SEEDS,
                   threshold: float = THRESHOLD) -> Dict[Tuple[str, str, str], Dict]:
    """window 예측을 run probability 로 집계한다.

    Returns:
        ``(cell, subject, task)`` → ``{"p", "truth", "prediction", "correct",
        "n_windows", "n_seeds", "group_id"}``.

    Raises:
        EvaluationError: window×seed 격자가 채워지지 않았거나 truth 가 엇갈리면.
    """
    for p in predictions:
        if not isinstance(p, WindowPrediction):
            raise EvaluationError(
                "A–D 집계는 WindowPrediction 만 받는다 — 보조 비교 칸은 "
                "aggregate_comparison_runs")
    return _aggregate_grid(predictions, n_windows=n_windows,
                           seeds_for=lambda _subject: None, n_seeds=n_seeds,
                           threshold=threshold)


def _aggregate_grid(predictions: Sequence, *, n_windows: int, seeds_for,
                    n_seeds: Optional[int], threshold: float
                    ) -> Dict[Tuple[str, str, str], Dict]:
    """window×seed 격자를 run probability 로 접는 공통 본체.

    ``seeds_for(subject)`` 가 None 이면 seed **개수** 만 ``n_seeds`` 와 맞춘다
    (A–D, 기존 동작). 튜플이면 seed **집합** 이 그 튜플과 정확히 같아야 한다.
    """
    buckets: Dict[Tuple[str, str, str], Dict[Tuple[int, Optional[int]], object]] = \
        defaultdict(dict)
    for p in predictions:
        key = (p.cell, p.canonical_subject, p.task)
        slot = (p.window_index, p.model_seed)
        if slot in buckets[key]:
            raise EvaluationError(
                f"중복 예측: {key} window {p.window_index} seed {p.model_seed}")
        buckets[key][slot] = p

    out: Dict[Tuple[str, str, str], Dict] = {}
    for key, slots in buckets.items():
        windows = sorted({w for w, _ in slots})
        want = seeds_for(key[1])
        if want is None:
            seeds = sorted({s for _, s in slots})
            if len(windows) != n_windows or len(seeds) != n_seeds:
                raise EvaluationError(
                    f"{key}: window {len(windows)}/{n_windows}, seed {len(seeds)}/{n_seeds}. "
                    "불완전한 격자로 평균하지 않는다")
        else:
            seeds = list(want)
            got_seeds = {s for _, s in slots}
            if len(windows) != n_windows or got_seeds != set(seeds):
                raise EvaluationError(
                    f"{key}: window {len(windows)}/{n_windows}, seed "
                    f"{sorted(got_seeds, key=str)} ≠ 기대 {seeds}. "
                    "불완전한 격자로 평균하지 않는다")
        missing = [(w, s) for w in windows for s in seeds if (w, s) not in slots]
        if missing:
            raise EvaluationError(f"{key}: 빠진 (window, seed) {missing[:3]}")
        truths = {slots[(w, s)].truth for w in windows for s in seeds}
        if len(truths) != 1:
            raise EvaluationError(f"{key}: truth 가 엇갈린다 {truths}")
        groups = {slots[(w, s)].group_id for w in windows for s in seeds}
        if len(groups) != 1:
            raise EvaluationError(f"{key}: group_id 가 엇갈린다 {groups}")

        grid = [[slots[(w, s)].p_class1 for s in seeds] for w in windows]
        p = run_probability(grid, n_windows=n_windows, n_seeds=len(seeds))
        truth = truths.pop()
        pred = classify(p, threshold)
        out[key] = {"p": p, "truth": truth, "prediction": pred,
                    "correct": pred == truth, "n_windows": n_windows,
                    "n_seeds": len(seeds), "group_id": groups.pop()}
    return out


def subject_scores(runs: Mapping[Tuple[str, str, str], Dict], cell: str,
                   *, tasks: Sequence[str] = CLASSIFICATION_TASKS
                   ) -> Dict[str, float]:
    """cell 하나의 subject 별 ``b_i``. 두 task 를 모두 가진 subject 만 남긴다."""
    assert_classification_only(tasks)
    by_subject: Dict[str, Dict[str, bool]] = defaultdict(dict)
    for (c, subject, task), rec in runs.items():
        if c == cell:
            by_subject[subject][task] = bool(rec["correct"])
    scores: Dict[str, float] = {}
    incomplete: List[str] = []
    for subject, got in by_subject.items():
        if set(got) != set(tasks):
            incomplete.append(subject)
            continue
        scores[subject] = subject_score(got[tasks[0]], got[tasks[1]])
    if incomplete:
        raise EvaluationError(
            f"cell {cell}: 두 task 를 모두 갖지 않은 subject {incomplete[:5]} "
            f"(총 {len(incomplete)}명). complete-case 만 집계한다")
    return scores


def cell_balanced_accuracy(runs: Mapping[Tuple[str, str, str], Dict],
                           cell: str) -> float:
    return balanced_accuracy(list(subject_scores(runs, cell).values()))


def primary_contrasts(runs: Mapping[Tuple[str, str, str], Dict]
                      ) -> Dict[str, Dict[str, float]]:
    """H1(A−B)과 H2(A−C), 그리고 보조 interaction 의 subject 별 차이."""
    scores = {c: subject_scores(runs, c) for c in CELLS}
    subjects = set(scores["A"])
    for c in CELLS[1:]:
        if set(scores[c]) != subjects:
            raise EvaluationError(f"cell {c} 의 subject 집합이 A 와 다르다 — paired 불가")
    return {
        "H1_A_minus_B": {s: scores["A"][s] - scores["B"][s] for s in subjects},
        "H2_A_minus_C": {s: scores["A"][s] - scores["C"][s] for s in subjects},
        "interaction": {s: (scores["A"][s] - scores["B"][s]) -
                           (scores["C"][s] - scores["D"][s]) for s in subjects},
    }


def verify_release_completeness(predictions: Sequence[WindowPrediction],
                                expected_subjects: Set[str], *,
                                n_tasks: int = 2, n_windows: int = N_WINDOWS,
                                n_seeds: int = N_SEEDS,
                                cells: Sequence[str] = CELLS) -> Dict[str, int]:
    """WI-07 완료기준을 검사한다.

    Raises:
        EvaluationError: 행 수가 기대와 다르거나 subject 집합이 어긋나면.
    """
    expected_rows = len(expected_subjects) * n_tasks * n_windows * n_seeds * len(cells)
    if len(predictions) != expected_rows:
        raise EvaluationError(
            f"window prediction 행 수가 {expected_rows} 가 아니다: {len(predictions)}")
    seen = {p.canonical_subject for p in predictions}
    if seen != set(expected_subjects):
        extra = sorted(seen - set(expected_subjects))[:3]
        missing = sorted(set(expected_subjects) - seen)[:3]
        raise EvaluationError(f"subject 불일치 — 추가 {extra}, 누락 {missing}")
    per_cell = defaultdict(int)
    for p in predictions:
        per_cell[p.cell] += 1
    if len(per_cell) != len(cells) or len(set(per_cell.values())) != 1:
        raise EvaluationError(f"cell 별 행 수가 고르지 않다: {dict(per_cell)}")
    return {"window_rows": len(predictions),
            "run_rows": len(expected_subjects) * n_tasks * len(cells),
            "subjects": len(expected_subjects)}


def verify_checkpoint_integrity(used: Mapping[str, str],
                                expected: Mapping[str, str]) -> None:
    """checkpoint hash 가 fit manifest 와 일치하는지 확인한다 (T15).

    Raises:
        EvaluationError: 누락되거나 불일치하면. 다른 파일로 대체하지 않는다.
    """
    missing = sorted(set(expected) - set(used))
    if missing:
        raise EvaluationError(f"checkpoint 누락: {missing[:5]}. glob 으로 대체하지 않는다")
    bad = sorted(k for k in expected if used[k] != expected[k])
    if bad:
        raise EvaluationError(f"checkpoint hash 불일치: {bad[:5]}")


# ---------------------------------------------------------------------------
# 보조 비교 칸 (S 후보·구조 비교) outer 예측 집계 — 남은 작업 2-c (09-25 13:15)
#
# 계획서 §8 의 run 집계 규칙(각 window 의 seed 평균 → task 의 네 window 평균,
# threshold 0.5, 동일값 class 1, subject 당 b_i)을 A–D 와 같은 함수로 적용한다.
# 보조 contrast 는 §8 이 이름으로 정한 **A−S 만** 계산한다. 구조 비교(NG·SG) 는
# §9 가 보조 분석으로만 나열하고 contrast 를 정하지 않아 칸별 b_i·BA 만 낸다.
#
# 구현 선택 (표시함): S 는 outer fold 마다 후보가 다를 수 있어(logistic 은 seed 없음,
# MLP 는 seed 3 개 — `baselines.s_outer_plan`) seed 집합을 **subject 별** 로 받는다.
# ---------------------------------------------------------------------------

#: 보조 비교 칸 이름. S = 선택된 S 후보, NG·SG = `baselines.COMPARATOR_ORDER`.
COMPARISON_CELLS = ("S", "NG", "SG")
#: 계획서 §8 이 이름으로 정한 보조 contrast (A−S). A−NG·A−SG 는 계획서에 없음.
COMPARISON_CONTRASTS = ("A_minus_S",)


@dataclass(frozen=True)
class ComparisonWindowPrediction:
    """보조 비교 칸 window 하나의 예측. logistic S 는 ``model_seed=None``."""

    canonical_subject: str
    group_id: str
    task: str
    window_index: int
    model_seed: Optional[int]
    cell: str
    truth: int
    p_class1: float

    def __post_init__(self) -> None:
        if self.cell not in COMPARISON_CELLS:
            raise EvaluationError(f"알 수 없는 보조 비교 칸: {self.cell!r}")
        if self.task not in CLASSIFICATION_TASKS:
            raise EvaluationError(f"알 수 없는 task: {self.task!r}")
        if not 0.0 <= self.p_class1 <= 1.0:
            raise EvaluationError(f"확률이 [0,1] 밖이다: {self.p_class1}")
        if self.truth not in (0, 1):
            raise EvaluationError(f"truth 는 0|1 이어야 한다: {self.truth}")
        if self.model_seed is None and self.cell != "S":
            raise EvaluationError(f"{self.cell}: seed 없는 예측은 S(logistic) 만 허용")


def aggregate_comparison_runs(
        predictions: Sequence[ComparisonWindowPrediction], *, cell: str,
        seeds_by_subject: Mapping[str, Sequence[Optional[int]]],
        n_windows: int = N_WINDOWS, threshold: float = THRESHOLD
) -> Dict[Tuple[str, str, str], Dict]:
    """보조 비교 칸 하나의 window 예측을 run probability 로 집계한다.

    Args:
        cell: ``COMPARISON_CELLS`` 중 하나. 모든 행의 cell 이 같아야 한다.
        seeds_by_subject: subject → 그 subject 의 outer fit seed 튜플 (outer 계획에서
            만든다). 예측 subject 집합과 정확히 같아야 한다 (빠진 subject 거부).

    Raises:
        EvaluationError: 칸 섞임, subject 집합 불일치, seed 집합 불일치, 불완전 격자.
    """
    if cell not in COMPARISON_CELLS:
        raise EvaluationError(f"알 수 없는 보조 비교 칸: {cell!r}")
    for p in predictions:
        if not isinstance(p, ComparisonWindowPrediction):
            raise EvaluationError("보조 비교 집계는 ComparisonWindowPrediction 만 받는다")
        if p.cell != cell:
            raise EvaluationError(f"칸이 섞였다: {p.cell!r} ≠ {cell!r}")
    seen = {p.canonical_subject for p in predictions}
    if seen != set(seeds_by_subject):
        extra = sorted(seen - set(seeds_by_subject))[:3]
        missing = sorted(set(seeds_by_subject) - seen)[:3]
        raise EvaluationError(f"{cell}: subject 불일치 — 추가 {extra}, 누락 {missing}")
    for subject, seeds in seeds_by_subject.items():
        seeds = tuple(seeds)
        if not seeds or len(set(seeds)) != len(seeds):
            raise EvaluationError(f"{cell}/{subject}: seed 목록이 비었거나 중복 {seeds}")
        if None in seeds and (cell != "S" or len(seeds) != 1):
            raise EvaluationError(f"{cell}/{subject}: seed 없음(None) 은 S logistic 단독만")
    return _aggregate_grid(predictions, n_windows=n_windows,
                           seeds_for=lambda s: tuple(seeds_by_subject[s]),
                           n_seeds=None, threshold=threshold)


def comparison_contrasts(ad_runs: Mapping[Tuple[str, str, str], Dict],
                         s_runs: Mapping[Tuple[str, str, str], Dict]
                         ) -> Dict[str, Dict[str, float]]:
    """보조 contrast A−S 의 subject 별 b 차이 (계획서 §8, 95% 기술적 CI 대상).

    Raises:
        EvaluationError: A 와 S 의 subject 집합이 다르면 (paired 불가).
    """
    a = subject_scores(ad_runs, "A")
    s = subject_scores(s_runs, "S")
    if set(a) != set(s):
        raise EvaluationError("S 의 subject 집합이 A 와 다르다 — paired 불가")
    return {"A_minus_S": {k: a[k] - s[k] for k in a}}
