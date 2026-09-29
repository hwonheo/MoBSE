"""학습 규칙 — 결정 31-1·32 (2026-09-29).

v1 (``mobse.v2.train``) 은 두 상수를 함께 잠갔다: ``MIN_UPDATES = 5000`` 과
``MAX_EPOCHS = 400``. 창이 사람당 8 개·batch 32 이므로 학습 subject 가 약 50 명
아래로 내려가면 두 상수를 동시에 만족할 수 없다 (10 명이면 1,667 epoch 이 필요하다).
저표본 곡선 (결정 30) 은 바로 그 구간을 봐야 하므로 규칙을 바꾼다.

**바뀐 규칙 (P8-c 후보)**

* **update 예산 5,000 을 모든 N 이 동일하게 받는다.** 곡선의 차이가 "학습량" 이 아니라
  "자료의 양" 이 되게 하기 위해서다. 예산이 곧 epoch 상한이다
  (``epochs_for_budget`` = ``ceil(예산 / update_per_epoch)``) — 별도의 epoch 상한은 없다.
* **best checkpoint 는 어느 epoch 에서든 고른다.** v1 은 ``min_epoch`` 이전 epoch 를
  best 후보에서 뺐다 (``mobse.v2.fitting`` 613·670, ``mobse.v2.train`` 288). 저표본에서
  그 결합을 그대로 두면 10 명짜리 학습이 창 80 개를 1,667 epoch 반복한 뒤에야
  checkpoint 를 고르게 되어 구조적으로 과적합된다 (결정 32).
* early stopping 이 먼저 걸리면 학습도 거기서 끝난다 — 예산은 상한이지 목표가 아니다.

바뀌지 않은 것 (grid · 손실 · 동률 규칙 · 누설 검사) 은 동결된 ``mobse.v2.train`` 을
그대로 쓴다. 여기서 다시 쓰지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence

from mobse.v2.train import (  # 동결된 v1 규칙 중 바뀌지 않는 것
    BATCH_SIZE,
    CELLS,
    GRAD_CLIP,
    INNER_SEED,
    MIN_DELTA,
    MODEL_SEEDS,
    PATIENCE,
    PROB_CLIP,
    TIE_TOLERANCE,
    GridConfig,
    TrainError,
    assert_no_test_leakage,
    build_grid,
    clipped_log_loss,
    early_stop_epoch,
    subject_equal_loss,
    updates_per_epoch,
)
from mobse.v2.train import _median, _require_complete  # noqa: F401  (구현 선택: 사문 재작성 안 함)

__all__ = [
    "BATCH_SIZE", "CELLS", "GRAD_CLIP", "INNER_SEED", "MIN_DELTA", "MODEL_SEEDS",
    "PATIENCE", "PROB_CLIP", "TIE_TOLERANCE", "UPDATE_BUDGET", "EPOCH_SANITY_CEILING",
    "GridConfig", "TrainError", "Selection", "CellFoldResult",
    "assert_no_test_leakage", "build_grid", "clipped_log_loss", "early_stop_epoch",
    "epochs_for_budget", "select_config", "subject_equal_loss", "updates_per_epoch",
    "select_best_epoch",
]

#: 모든 N 이 동일하게 받는 optimizer update 예산 (결정 31-1·32). v1 의 MIN_UPDATES 와
#: 같은 수지만 뜻이 다르다 — v1 은 **최소치**, v3 는 **예산이자 상한**이다.
UPDATE_BUDGET = 5000

#: 폭주를 막는 안전 상한. 규칙이 아니라 방어선이다 — 예산으로 계산한 epoch 수가
#: 이 값을 넘으면 설정이 잘못된 것으로 본다 (창 2 개짜리 학습 집합 같은 경우).
EPOCH_SANITY_CEILING = 20000


def epochs_for_budget(n_train: int, *, batch_size: int = BATCH_SIZE,
                      update_budget: int = UPDATE_BUDGET) -> int:
    """update 예산을 다 쓰는 epoch 수 = ``ceil(예산 / update_per_epoch)``.

    이 값이 그 학습 집합의 **epoch 상한**이다. 별도의 고정 상한은 없다 (결정 31-1).

    Raises:
        TrainError: 예산이 양수가 아니거나 계산된 epoch 이 안전 상한을 넘을 때.
    """
    if update_budget <= 0:
        raise TrainError(f"update 예산은 양수여야 한다: {update_budget}")
    upe = updates_per_epoch(n_train, batch_size)
    n = max(1, math.ceil(update_budget / upe))
    if n > EPOCH_SANITY_CEILING:
        raise TrainError(
            f"예산 {update_budget} 에 epoch {n} 이 필요하다 — 안전 상한 "
            f"{EPOCH_SANITY_CEILING} 을 넘는다 (학습 창 {n_train}, update/epoch {upe}). "
            "학습 집합이 지나치게 작은지 확인하라")
    return n


def select_best_epoch(val_losses: Sequence[float], *, patience: int = PATIENCE,
                      min_delta: float = MIN_DELTA) -> int:
    """best epoch 를 고른다 — **최소 epoch 결합 없이** (결정 32).

    동결된 ``mobse.v2.train.early_stop_epoch`` 를 ``min_epoch=1`` 로 부른다.
    규칙 자체 (patience · min_delta) 는 v1 과 같고, 달라진 것은 "언제부터 고를 수
    있는가" 뿐이다.
    """
    return early_stop_epoch(val_losses, patience=patience, min_delta=min_delta,
                            min_epoch=1)


@dataclass(frozen=True)
class CellFoldResult:
    """한 (config, cell, inner fold) 의 결과.

    v1 과 다른 점은 ``epoch_ceiling`` 이 인자로 들어온다는 것뿐이다 — 상한이 상수가
    아니라 그 학습 집합의 예산에서 나오기 때문이다. 기본값을 두지 않는다 (빠뜨리면
    조용히 잘못된 상한으로 통과할 수 있다).
    """

    config_id: int
    cell: str
    inner_fold: int
    loss: float
    balanced_accuracy: float
    best_epoch: int
    n_subjects: int
    epoch_ceiling: int

    def __post_init__(self) -> None:
        if self.cell not in CELLS:
            raise TrainError(f"알 수 없는 cell: {self.cell!r}")
        if self.epoch_ceiling < 1:
            raise TrainError(f"epoch_ceiling 은 1 이상이어야 한다: {self.epoch_ceiling}")
        if not 1 <= self.best_epoch <= self.epoch_ceiling:
            raise TrainError(
                f"best_epoch 가 1–{self.epoch_ceiling} 밖이다: {self.best_epoch}")
        if isinstance(self.n_subjects, bool) or not isinstance(self.n_subjects, int) \
                or self.n_subjects < 1:
            raise TrainError(f"n_subjects 는 1 이상의 정수여야 한다: {self.n_subjects!r}")


@dataclass(frozen=True)
class Selection:
    """공동 선택 결과. v1 과 같되 상한을 함께 기록한다."""

    config_id: int
    common_epochs: int
    joint_loss: float
    joint_ba: float
    tie_rule: str
    epoch_ceiling: int
    per_config: Dict[int, Dict[str, float]]


def select_config(results: Sequence[CellFoldResult], *, n_folds: int = 3) -> Selection:
    """A–D 공동 config 와 공통 epoch 를 고른다.

    선택 규칙 (OOF 병합 · subject 동일 가중 · 동률 처리) 은 v1 과 **같다**. 달라진
    것은 공통 E 의 상한이 상수 400 이 아니라 그 학습 집합의 ``epoch_ceiling`` 이라는
    점뿐이다 (결정 31-1).

    Raises:
        TrainError: grid 가 불완전하거나, inner fold 의 subject 수가 어긋나거나,
            결과들의 ``epoch_ceiling`` 이 서로 다르거나, 공통 E 가 상한 밖일 때.
    """
    _require_complete(results, n_folds)

    ceilings = {r.epoch_ceiling for r in results}
    if len(ceilings) != 1:
        raise TrainError(
            f"epoch_ceiling 이 결과마다 다르다: {sorted(ceilings)[:5]} — 같은 학습 "
            "집합에서 나온 결과여야 한다")
    ceiling = ceilings.pop()

    fold_n: Dict[int, int] = {}
    for r in results:
        n0 = fold_n.setdefault(r.inner_fold, r.n_subjects)
        if n0 != r.n_subjects:
            raise TrainError(
                f"inner fold {r.inner_fold} 의 subject 수가 다르다: {n0} vs {r.n_subjects} "
                f"(config {r.config_id}, cell {r.cell}) — 같은 inner 모집단에서 비교해야 한다")
    n_total = sum(fold_n.values())

    per_config: Dict[int, Dict[str, float]] = {}
    for cid in sorted({r.config_id for r in results}):
        rows = [r for r in results if r.config_id == cid]
        cell_loss = {c: sum(r.loss * r.n_subjects for r in rows if r.cell == c) / n_total
                     for c in CELLS}
        cell_ba = {c: sum(r.balanced_accuracy * r.n_subjects for r in rows if r.cell == c)
                   / n_total for c in CELLS}
        per_config[cid] = {
            "joint_loss": sum(cell_loss.values()) / len(CELLS),
            "joint_ba": sum(cell_ba.values()) / len(CELLS),
        }

    best_loss = min(v["joint_loss"] for v in per_config.values())
    tied = [cid for cid, v in per_config.items()
            if v["joint_loss"] - best_loss <= TIE_TOLERANCE]
    tie_rule = "unique minimum"
    if len(tied) > 1:
        best_ba = max(per_config[c]["joint_ba"] for c in tied)
        tied = [c for c in tied if per_config[c]["joint_ba"] >= best_ba - TIE_TOLERANCE]
        tie_rule = "tie broken by joint BA" if len(tied) == 1 else \
            "tie broken by joint BA then smallest config_id"
    chosen = min(tied)

    epochs = sorted(r.best_epoch for r in results if r.config_id == chosen)
    if len(epochs) != len(CELLS) * n_folds:
        raise TrainError(f"선택 config 의 best epoch 수가 {len(CELLS) * n_folds} 가 아니다")
    common_e = math.ceil(_median(epochs))
    # 불변식 방어선이다. ``CellFoldResult`` 가 이미 best_epoch ≤ epoch_ceiling 을
    # 강제하므로 그 중앙값의 올림도 상한을 넘을 수 없다 — 즉 **정상 경로로는 닿지
    # 않는다**. 돌연변이 시험이 이 줄을 잡지 못하는 것은 그 때문이며, 지우지 않는
    # 이유는 select_config 가 CellFoldResult 밖에서 만들어진 입력을 받을 수도 있기
    # 때문이다 (구현 선택, 2026-09-29).
    if not 1 <= common_e <= ceiling:
        raise TrainError(f"공통 E 가 1–{ceiling} 밖이다: {common_e}")

    return Selection(config_id=chosen, common_epochs=common_e,
                     joint_loss=per_config[chosen]["joint_loss"],
                     joint_ba=per_config[chosen]["joint_ba"],
                     tie_rule=tie_rule, epoch_ceiling=ceiling, per_config=per_config)
