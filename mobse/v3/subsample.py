"""저표본 곡선의 학습 subject 부분표집 — 결정 30 (2026-09-29).

target 도 분할도 바꾸지 않는다. 바꾸는 것은 **outer fold 의 학습 subject 를 몇 명까지
쓰는가** 뿐이다. 그래야 곡선의 차이를 "자료의 양" 으로 읽을 수 있다.

두 가지를 설계로 못 박는다.

* **중첩 (nested)** — 작은 수준은 큰 수준의 **부분집합**이다. 수준마다 따로 뽑으면
  곡선의 오르내림에 "누구를 뽑았나" 가 섞인다. 한 번 섞은 순서의 앞에서 잘라 쓴다.
* **fold 마다 다른 순서** — 모든 outer fold 가 같은 순서를 쓰면 한 번의 운 나쁜
  섞기가 곡선 전체를 기울인다. seed 를 fold 로 가른다.

class 균형은 따로 맞추지 않는다. 이 target (run identity) 은 **사람마다 두 class 를
하나씩** 가지므로 subject 를 뽑으면 class 는 저절로 균형이다 — 그 사실을 시험이 지킨다.
pilot 은 애초에 outer fold 의 학습 집합에 없다 (분할이 이미 뺐다).
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

__all__ = ["LOW_SAMPLE_LEVELS", "SUBSAMPLE_SEED_BASE", "SubsampleError",
           "subsample_seed", "subsample_train", "subsample_curve"]


class SubsampleError(RuntimeError):
    """부분표집 규칙 위반."""


#: 학습 subject 수 수준. 가장 큰 값은 "전부" 를 뜻하는 ``None`` 이다.
#: outer fold 의 학습 집합은 100–101 명이므로 100 이 사실상 전부에 가깝다.
LOW_SAMPLE_LEVELS: Tuple[int, ...] = (10, 20, 40, 70, 100)

#: fold 별 섞기 seed 의 바탕. ``subsample_seed`` 가 fold 를 더한다.
SUBSAMPLE_SEED_BASE = 40000


def subsample_seed(outer_fold: int, *, seed_base: int = SUBSAMPLE_SEED_BASE) -> int:
    """outer fold 하나의 섞기 seed. fold 마다 다르고 재현 가능하다."""
    if not isinstance(outer_fold, int) or isinstance(outer_fold, bool) or outer_fold < 0:
        raise SubsampleError(f"outer_fold 는 0 이상의 정수여야 한다: {outer_fold!r}")
    return int(seed_base) + int(outer_fold)


def _shuffled(train_subjects: Sequence[str], outer_fold: int,
              seed_base: int) -> List[str]:
    subs = list(train_subjects)
    if len(set(subs)) != len(subs):
        raise SubsampleError("학습 subject 에 중복이 있다")
    if not subs:
        raise SubsampleError("학습 subject 가 비었다")
    # 입력 순서에 기대지 않는다 — 정렬해 두고 섞는다 (같은 집합이면 같은 결과).
    subs = sorted(subs)
    rng = np.random.Generator(np.random.PCG64(subsample_seed(outer_fold,
                                                             seed_base=seed_base)))
    order = rng.permutation(len(subs))
    return [subs[i] for i in order]


def subsample_train(train_subjects: Sequence[str], n_keep: int, *, outer_fold: int,
                    seed_base: int = SUBSAMPLE_SEED_BASE) -> List[str]:
    """학습 subject 를 ``n_keep`` 명으로 줄인다. 결과는 **정렬**해 돌려준다.

    같은 fold 의 작은 ``n_keep`` 은 큰 ``n_keep`` 의 부분집합이다 (중첩).

    Raises:
        SubsampleError: ``n_keep`` 이 1 미만이거나 학습 집합보다 클 때. 조용히
            잘라 맞추지 않는다 — 수준을 잘못 준 것을 숨기면 곡선이 거짓말을 한다.
    """
    shuffled = _shuffled(train_subjects, outer_fold, seed_base)
    if not isinstance(n_keep, int) or isinstance(n_keep, bool) or n_keep < 1:
        raise SubsampleError(f"n_keep 은 1 이상의 정수여야 한다: {n_keep!r}")
    if n_keep > len(shuffled):
        raise SubsampleError(
            f"n_keep {n_keep} 이 학습 subject 수 {len(shuffled)} 보다 크다 "
            f"(outer fold {outer_fold})")
    return sorted(shuffled[:n_keep])


def subsample_curve(train_subjects: Sequence[str], *, outer_fold: int,
                    levels: Sequence[int] = LOW_SAMPLE_LEVELS,
                    seed_base: int = SUBSAMPLE_SEED_BASE) -> Dict[int, List[str]]:
    """수준마다의 학습 집합을 한 번에 만든다.

    Raises:
        SubsampleError: 수준이 오름차순이 아니거나 중복이 있을 때 — 중첩 성질을
            읽는 사람이 헷갈리지 않도록 순서를 강제한다.
    """
    lv = list(levels)
    if lv != sorted(set(lv)):
        raise SubsampleError(f"수준은 중복 없는 오름차순이어야 한다: {lv}")
    return {n: subsample_train(train_subjects, n, outer_fold=outer_fold,
                               seed_base=seed_base) for n in lv}
