"""Endpoint 집계와 paired bootstrap — 재설계 프로토콜 v1.1 §8 구현.

의존성은 numpy 뿐이다. 원자료 없이 완성·검증된다.

프로토콜이 규정한 것을 그대로 옮긴다.

* 각 window 의 세 seed 확률을 평균하고, 각 task 의 네 window 를 평균해 subject 당
  두 run probability 를 얻는다.
* threshold 0.5 이며 **동일값은 class 1** 로 정한다.
* ``b_i = (I[emo correct] + I[WM correct]) / 2``, ``BA = mean_i(b_i)``.
* 주 contrast 는 **같은 subject 의 b 차이**로 계산한다.
* seed 9001, 10,000회 paired bootstrap 이며 **모든 cell 에 같은 재표집**을 적용한다.
* 두 contrast 각각 97.5% CI(1.25–98.75 percentile)로 family-wise 95% 를 보수적으로
  제어한다. 보조 지표는 95%(2.5–97.5)로 표시한다.
* 가족/중복 group 이 있으면 **group 전체를 재표집**하고 반복 추출된 subject 에
  동일 가중을 적용한다.
* **window·seed·fold 수를 N 으로 세지 않는다.**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

BOOTSTRAP_SEED = 9001
N_BOOTSTRAP = 10_000
FAMILYWISE_PCT = (1.25, 98.75)   # 97.5% CI — 주 contrast 2개용
NOMINAL_PCT = (2.5, 97.5)        # 95% CI — 보조 지표용
THRESHOLD = 0.5
N_WINDOWS = 4
N_SEEDS = 3


class StatisticsError(RuntimeError):
    """집계·통계 규칙 위반. 불완전한 평균으로 넘어가지 않는다."""


def run_probability(window_seed_probs: Sequence[Sequence[float]],
                    *, n_windows: int = N_WINDOWS, n_seeds: int = N_SEEDS) -> float:
    """window×seed 확률에서 run probability 를 만든다.

    먼저 각 window 의 seed 를 평균하고, 그 다음 window 를 평균한다. 순서를 바꾸면
    결측이 있을 때 값이 달라지므로 프로토콜이 규정한 순서를 지킨다.

    Args:
        window_seed_probs: ``[n_windows][n_seeds]`` 확률.

    Raises:
        StatisticsError: window 또는 seed 수가 맞지 않거나 확률이 [0,1] 밖이면.
            프로토콜 §8 은 불완전 평균을 금지한다.
    """
    arr = np.asarray(window_seed_probs, dtype=float)
    if arr.shape != (n_windows, n_seeds):
        raise StatisticsError(
            f"window×seed 모양이 ({n_windows}, {n_seeds}) 여야 한다: {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise StatisticsError("확률에 비유한값이 있다")
    if arr.min() < 0.0 or arr.max() > 1.0:
        raise StatisticsError("확률이 [0, 1] 밖이다")
    return float(arr.mean(axis=1).mean())


def classify(prob: float, threshold: float = THRESHOLD) -> int:
    """확률을 class 로 바꾼다. **동일값은 class 1** (프로토콜 §8)."""
    return 1 if prob >= threshold else 0


def subject_score(emo_correct: bool, wm_correct: bool) -> float:
    """``b_i = (I[emo] + I[WM]) / 2``."""
    return (int(bool(emo_correct)) + int(bool(wm_correct))) / 2.0


def balanced_accuracy(scores: Sequence[float]) -> float:
    """``BA = mean_i(b_i)``. 두 task complete-case 이므로 통상 binary BA 와 같다."""
    if len(scores) == 0:
        raise StatisticsError("subject 가 없다")
    return float(np.mean(np.asarray(scores, dtype=float)))


def paired_difference(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """같은 subject 의 b 차이 평균. subject 집합이 다르면 실패한다."""
    if set(a) != set(b):
        raise StatisticsError("두 cell 의 subject 집합이 다르다 — paired 계산 불가")
    subjects = sorted(a)
    return float(np.mean([a[s] - b[s] for s in subjects]))


@dataclass(frozen=True)
class BootstrapResult:
    """paired bootstrap 결과."""

    point: float
    lo: float
    hi: float
    pct: Tuple[float, float]
    n_boot: int
    seed: int
    n_subjects: int
    n_groups: int
    unit: str = "subject (group-resampled)"

    def as_dict(self) -> Dict[str, object]:
        return {
            "point_estimate": self.point, "ci_lo": self.lo, "ci_hi": self.hi,
            "percentiles": list(self.pct), "n_boot": self.n_boot, "seed": self.seed,
            "n_subjects": self.n_subjects, "n_groups": self.n_groups,
            "statistical_unit": self.unit,
        }


def _group_index(subject_to_group: Mapping[str, str],
                 subjects: Sequence[str]) -> Tuple[List[str], List[np.ndarray]]:
    """group 목록과, 각 group 에 속한 subject 의 위치 index 를 만든다."""
    pos = {s: i for i, s in enumerate(subjects)}
    buckets: Dict[str, List[int]] = {}
    for s in subjects:
        buckets.setdefault(subject_to_group[s], []).append(pos[s])
    gids = sorted(buckets)
    return gids, [np.asarray(buckets[g], dtype=int) for g in gids]


def bootstrap_indices(subject_to_group: Mapping[str, str], subjects: Sequence[str],
                      *, seed: int = BOOTSTRAP_SEED,
                      n_boot: int = N_BOOTSTRAP) -> List[np.ndarray]:
    """group 단위 재표집 index 를 만든다.

    group 을 복원추출하고 그 group 의 subject 를 통째로 넣는다. 같은 subject 가
    여러 번 뽑히면 그만큼 반복되며 각 인스턴스는 동일 가중이다.

    **모든 cell 에 같은 index 를 적용해야 paired 구조가 유지된다.** 그래서 index 를
    먼저 만들어 돌려주고, 통계 계산에서 재사용한다.
    """
    gids, members = _group_index(subject_to_group, subjects)
    rng = np.random.Generator(np.random.PCG64(seed))
    n_groups = len(gids)
    draws = rng.integers(0, n_groups, size=(n_boot, n_groups))
    return [np.concatenate([members[g] for g in row]) for row in draws]


def paired_bootstrap(
    values: Mapping[str, float],
    subject_to_group: Mapping[str, str],
    *,
    indices: Optional[Sequence[np.ndarray]] = None,
    seed: int = BOOTSTRAP_SEED,
    n_boot: int = N_BOOTSTRAP,
    pct: Tuple[float, float] = FAMILYWISE_PCT,
) -> BootstrapResult:
    """subject 별 값(보통 paired 차이)의 group bootstrap CI.

    Args:
        values: subject → 값. 주 contrast 에서는 ``b_i^A - b_i^B``.
        subject_to_group: subject → group. 관계 metadata 가 없으면 자기 자신.
        indices: `bootstrap_indices` 가 만든 재표집 index. 여러 contrast 에
            **같은 재표집을 적용**하려면 반드시 공유해야 한다.

    Raises:
        StatisticsError: subject 가 없거나 group 매핑이 빠진 경우.
    """
    subjects = sorted(values)
    if not subjects:
        raise StatisticsError("subject 가 없다")
    missing = [s for s in subjects if s not in subject_to_group]
    if missing:
        raise StatisticsError(f"group 매핑 없는 subject: {missing[:5]}")

    vec = np.asarray([values[s] for s in subjects], dtype=float)
    if indices is None:
        indices = bootstrap_indices(subject_to_group, subjects, seed=seed, n_boot=n_boot)
    stats = np.asarray([vec[idx].mean() for idx in indices], dtype=float)
    lo, hi = np.percentile(stats, pct)
    n_groups = len({subject_to_group[s] for s in subjects})
    return BootstrapResult(point=float(vec.mean()), lo=float(lo), hi=float(hi),
                           pct=pct, n_boot=len(indices), seed=seed,
                           n_subjects=len(subjects), n_groups=n_groups)


def interpret(result: BootstrapResult, delta: float = 0.02) -> str:
    """프로토콜 §8 의 판정 규칙을 문자열로 돌려준다.

    유의성은 실행 gate 가 아니며, 비유의를 '효과 없음'이나 동등성으로 바꾸지 않는다.
    """
    if result.lo > delta:
        return f"하한 {result.lo:.4f} > delta {delta} — 선택한 최소 효과 이상의 우월성 지지"
    if result.lo > 0:
        return (f"하한 {result.lo:.4f} > 0 이나 delta {delta} 이하 — 추가 기여는 지지되나 "
                "실질적 우월성 확정은 아님")
    if result.lo <= 0 <= result.hi:
        return "CI 가 0 을 포함 — 불확실. 비유의를 효과 없음·동등성으로 바꾸지 않는다"
    return f"상한 {result.hi:.4f} < 0 — 반대 방향"
