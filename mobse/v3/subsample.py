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

from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

__all__ = ["LOW_SAMPLE_LEVELS", "SUBSAMPLE_SEED_BASE", "INNER_SPLIT_SEED_BASE",
           "SubsampleError", "subsample_seed", "subsample_train", "subsample_curve",
           "inner_split_within", "curve_fold_subjects"]


class SubsampleError(RuntimeError):
    """부분표집 규칙 위반."""


#: 학습 subject 수 수준. 가장 큰 값은 "전부" 를 뜻하는 ``None`` 이다.
#: outer fold 의 학습 집합은 100–101 명이므로 100 이 사실상 전부에 가깝다.
LOW_SAMPLE_LEVELS: Tuple[int, ...] = (10, 20, 40, 70, 100)

#: fold 별 섞기 seed 의 바탕. ``subsample_seed`` 가 fold 를 더한다.
SUBSAMPLE_SEED_BASE = 40000

#: 부분표집한 pool 안에서 inner 분할을 다시 그을 때의 seed 바탕 (2026-10-01).
#: ``SUBSAMPLE_SEED_BASE`` 와 다른 값이어야 한다 — 같으면 "누구를 뽑았나" 와
#: "어느 fold 에 넣었나" 가 같은 난수에서 나와 둘이 얽힌다.
INNER_SPLIT_SEED_BASE = 41000


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


def inner_split_within(pool: Sequence[str], *, outer_fold: int, n_inner_folds: int = 3,
                       seed_base: int = INNER_SPLIT_SEED_BASE) -> List[Dict[str, List[str]]]:
    """부분표집한 학습 pool 안에서 inner 분할을 다시 긋는다.

    저표본 곡선은 수준마다 pool 크기가 다르므로 v1 의 `folds.json` 에 적힌 inner
    분할을 그대로 쓸 수 없다 (그 분할은 pool 100 명 기준이다). **누설을 막는
    경계 — pilot 과 outer test — 는 건드리지 않는다.** 여기서 나누는 것은 학습
    pool 내부뿐이라, 어느 조각도 test 나 pilot 에 닿지 않는다.

    Args:
        pool: 이 수준이 쓰는 학습 subject (정렬 여부 무관).
        outer_fold: seed 를 fold 로 가른다.
        n_inner_folds: 조각 수.
        seed_base: seed 바탕.

    Returns:
        inner fold 순서대로 ``{"val_subjects", "train_subjects"}`` 목록. 각 조각의
        합집합은 pool 과 같고 교집합은 비어 있다.

    Raises:
        SubsampleError: pool 이 조각 수보다 작거나 중복이 있을 때.
    """
    names = list(pool)
    if len(set(names)) != len(names):
        raise SubsampleError("pool 에 중복 subject 가 있다")
    if not isinstance(n_inner_folds, int) or isinstance(n_inner_folds, bool) \
            or n_inner_folds < 2:
        raise SubsampleError(f"n_inner_folds 는 2 이상의 정수여야 한다: {n_inner_folds!r}")
    if len(names) < n_inner_folds:
        raise SubsampleError(
            f"pool {len(names)} 명이 inner fold {n_inner_folds} 개보다 작다 — "
            "조용히 fold 수를 줄이지 않는다")
    rng = np.random.default_rng(int(seed_base) + int(outer_fold))
    shuffled = [names[i] for i in rng.permutation(len(names))]
    parts: List[Dict[str, List[str]]] = []
    for k in range(n_inner_folds):
        val = sorted(shuffled[k::n_inner_folds])          # 균등 분배
        train = sorted(set(names) - set(val))
        parts.append({"val_subjects": val, "train_subjects": train})
    return parts


def curve_fold_subjects(folds: Mapping[str, Any], outer_fold: int, inner_fold: int,
                        n_level: int, *, outer_inner_marker: int = 9,
                        n_inner_folds: int = 3,
                        subsample_seed_base: int = SUBSAMPLE_SEED_BASE,
                        inner_split_seed_base: int = INNER_SPLIT_SEED_BASE):
    """곡선 한 점의 fold 를 푼다 — **먼저 자르고, 그 안에서 나눈다.**

    v1 분할에서 **outer 경계만** 가져온다 (학습 pool 과 test). 그 pool 을
    ``n_level`` 명으로 줄인 뒤, inner 분할을 그 안에서 다시 긋는다. 이렇게 해야
    ``n_level`` 이 role 과 무관하게 같은 뜻 ("이 점이 쓰는 학습 subject 총수") 이
    되고, 가장 큰 수준에서 grid 를 한 번 고르는 결정 33 이 성립한다.

    ``n_level`` 이 pool 전체와 같으면 **v1 구성과 같아진다** (pool 100, inner
    train 약 66) — 곡선의 꼭대기 점이 v1 비교 기준이 된다.

    Args:
        folds: v1 `folds.json` 내용.
        outer_fold: outer fold 번호.
        inner_fold: inner fold 번호. ``outer_inner_marker`` 면 outer 최종 적합.
        n_level: 이 점이 쓰는 학습 subject 수.

    Returns:
        `mobse.v2.fitting.FoldSubjects`.

    Raises:
        SubsampleError: 수준이 pool 보다 크거나 inner fold 번호가 범위 밖일 때,
            또는 학습·평가 집합이 겹칠 때 (방어선).
    """
    from mobse.v2.fitting import (ROLE_INNER, ROLE_OUTER, FoldSubjects,
                                  resolve_fold_subjects)

    base = resolve_fold_subjects(folds, int(outer_fold), int(outer_inner_marker))
    pool = subsample_train(base.train, int(n_level), outer_fold=int(outer_fold),
                           seed_base=int(subsample_seed_base))
    if int(inner_fold) == int(outer_inner_marker):
        train, evaluate = pool, list(base.evaluate)
        role, eval_role = ROLE_OUTER, base.eval_role
    else:
        if not 0 <= int(inner_fold) < int(n_inner_folds):
            raise SubsampleError(
                f"inner fold {inner_fold} 가 0–{int(n_inner_folds) - 1} 밖이다")
        parts = inner_split_within(pool, outer_fold=int(outer_fold),
                                   n_inner_folds=int(n_inner_folds),
                                   seed_base=int(inner_split_seed_base))
        part = parts[int(inner_fold)]
        train, evaluate = part["train_subjects"], part["val_subjects"]
        role, eval_role = ROLE_INNER, "inner_validation"

    overlap = sorted(set(train) & set(evaluate))
    if overlap:  # 방어선 — 위 구성으로는 닿지 않는다.
        raise SubsampleError(f"학습·평가 집합이 겹친다: {overlap[:5]}")
    leaked = sorted(set(train) & set(base.evaluate))
    if leaked:   # 방어선 — pool 이 outer train 의 부분집합이므로 닿지 않는다.
        raise SubsampleError(f"학습 집합이 outer test 와 겹친다: {leaked[:5]}")
    return FoldSubjects(role=role, outer_fold=int(outer_fold),
                        inner_fold=int(inner_fold), train=sorted(train),
                        evaluate=sorted(evaluate), eval_role=eval_role)
