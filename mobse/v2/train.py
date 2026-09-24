"""선택 규칙과 공통 epoch — 재설계 프로토콜 v1.1 §7 구현.

의존성은 표준 라이브러리 뿐이다. 학습 루프 자체가 아니라 **선택 규칙**을 담는다.
그 규칙이 조용히 어긋나는 것이 프로토콜이 막으려는 실패 양식이기 때문이다.

프로토콜이 규정한 것을 그대로 옮긴다.

* 공통 grid 는 learning rate {0.001, 0.0003} × dropout {0.1, 0.3} ×
  weight decay {0.0001, 0.001} = 8개이며, 위 나열 순 Cartesian product 의
  ``config_id`` 0–7 로 **고정**한다.
* **A–D 는 공통 config 하나를 공동 선택**한다. 각 config 의 inner OOF run loss 를
  subject 별 동일 가중으로 합산하고 A–D 네 cell 에 같은 가중을 주어 최소화한다.
* 동률(차이 ≤ 1e−6)은 공동 BA 가 높은 것, 이후 ``config_id`` 가 작은 것으로 정한다.
* 선택 config 의 4 cells × 3 inner folds best epochs **중앙값을 올림**해 공통
  E(1–400)를 정한다.
* **[개정 P8, P8-b]** 모든 fit 은 최소 5,000 optimizer update 를 보장한다. epoch 상한은
  400 이다 (P8 1,500/200 → P8-b 5,000/400, 선생님 결정 15). early stopping 은 최소치(``min_epochs_for``)에 닿은 뒤에만 멈출 수 있고,
  best epoch 도 최소치 이후 epoch 중에서 고른다 — 그래야 공통 E 가 최소치 아래로
  내려가지 않는다 (구현 선택, 계획서 §11 P8).
* **outer test 로 early stopping 하지 않는다.**
* log loss 는 확률을 ``[1e−7, 1−1e−7]`` 로 clip 한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

LEARNING_RATES = (0.001, 0.0003)
DROPOUTS = (0.1, 0.3)
WEIGHT_DECAYS = (0.0001, 0.001)
BATCH_SIZE = 32
MAX_EPOCHS = 400          # [개정 P8-b] 50 → 200 (P8) → 400 (결정 15)
MIN_UPDATES = 5000        # [개정 P8-b] 최소 optimizer update 수 1,500 (P8) → 5,000 (결정 15)
PATIENCE = 5
MIN_DELTA = 0.0005
GRAD_CLIP = 1.0
INNER_SEED = 42
MODEL_SEEDS = (42, 43, 44)
PROB_CLIP = 1e-7
TIE_TOLERANCE = 1e-6
CELLS = ("A", "B", "C", "D")


class TrainError(RuntimeError):
    """선택 규칙 위반. 불완전 grid 를 정상 선택으로 처리하지 않는다."""


@dataclass(frozen=True)
class GridConfig:
    """공통 grid 의 한 점."""

    config_id: int
    learning_rate: float
    dropout: float
    weight_decay: float

    def as_dict(self) -> Dict[str, float]:
        return {"config_id": self.config_id, "learning_rate": self.learning_rate,
                "dropout": self.dropout, "weight_decay": self.weight_decay}


def build_grid() -> List[GridConfig]:
    """8개 config 를 프로토콜이 정한 순서로 만든다. 순서가 곧 ``config_id`` 다."""
    out: List[GridConfig] = []
    cid = 0
    for lr in LEARNING_RATES:
        for do in DROPOUTS:
            for wd in WEIGHT_DECAYS:
                out.append(GridConfig(cid, lr, do, wd))
                cid += 1
    if len(out) != 8:
        raise TrainError(f"grid 크기가 8 이 아니다: {len(out)}")
    return out


def clipped_log_loss(prob_true_class: Sequence[float]) -> float:
    """정답 class 의 확률에서 log loss. 확률을 ``[1e−7, 1−1e−7]`` 로 clip 한다."""
    if not len(prob_true_class):
        raise TrainError("확률이 비었다")
    total = 0.0
    for p in prob_true_class:
        q = min(max(float(p), PROB_CLIP), 1.0 - PROB_CLIP)
        total -= math.log(q)
    return total / len(prob_true_class)


def subject_equal_loss(per_run: Mapping[str, Sequence[float]]) -> float:
    """subject 별 동일 가중 log loss.

    subject 마다 run 이 두 개이므로, 먼저 subject 안에서 평균하고 그 다음
    subject 를 평균한다. run 수가 많은 subject 가 더 큰 가중을 갖지 않게 한다.
    """
    if not per_run:
        raise TrainError("subject 가 없다")
    per_subject = [clipped_log_loss(v) for v in per_run.values()]
    return sum(per_subject) / len(per_subject)


@dataclass(frozen=True)
class CellFoldResult:
    """한 (config, cell, inner fold) 의 결과.

    ``loss`` 는 그 fold validation subject 의 subject 동일 가중 log loss,
    ``balanced_accuracy`` 는 같은 subject 의 ``b_i`` 평균, ``n_subjects`` 는 그 subject 수다.
    ``n_subjects`` 는 기본값이 없다 — 빠뜨리면 fold 평균으로 조용히 돌아갈 수 있기 때문이다.
    """

    config_id: int
    cell: str
    inner_fold: int
    loss: float
    balanced_accuracy: float
    best_epoch: int
    n_subjects: int

    def __post_init__(self) -> None:
        if self.cell not in CELLS:
            raise TrainError(f"알 수 없는 cell: {self.cell!r}")
        if not 1 <= self.best_epoch <= MAX_EPOCHS:
            raise TrainError(f"best_epoch 가 1–{MAX_EPOCHS} 밖이다: {self.best_epoch}")
        if isinstance(self.n_subjects, bool) or not isinstance(self.n_subjects, int) \
                or self.n_subjects < 1:
            raise TrainError(f"n_subjects 는 1 이상의 정수여야 한다: {self.n_subjects!r}")


@dataclass(frozen=True)
class Selection:
    """공동 선택 결과."""

    config_id: int
    common_epochs: int
    joint_loss: float
    joint_ba: float
    tie_rule: str
    per_config: Dict[int, Dict[str, float]]


def _require_complete(results: Sequence[CellFoldResult], n_folds: int) -> None:
    """모든 config × cell × fold 가 채워졌는지 확인한다."""
    grid_ids = {c.config_id for c in build_grid()}
    have = {(r.config_id, r.cell, r.inner_fold) for r in results}
    need = {(cid, cell, f) for cid in grid_ids for cell in CELLS
            for f in range(n_folds)}
    missing = sorted(need - have)
    if missing:
        raise TrainError(
            f"불완전한 grid: {len(missing)}개 조합 누락 (예: {missing[:3]}). "
            "불완전 grid 를 정상 선택으로 처리하지 않는다")
    extra = sorted(have - need)
    if extra:
        raise TrainError(f"예상 밖 조합: {extra[:3]}")


def select_config(results: Sequence[CellFoldResult], *, n_folds: int = 3) -> Selection:
    """A–D 공동 config 와 공통 epoch 를 고른다.

    계획서 §7 "각 config의 inner OOF run loss를 subject별 동일 가중으로 합산하고 A–D 네
    cell에 같은 가중을 주어 최소화한다" 를 따른다. cell 하나의 손실은 3 inner fold
    validation 을 **OOF 하나로 합친** subject 동일 가중 log loss 다. inner validation
    subject 는 fold 끼리 겹치지 않으므로 이는 fold 손실의 ``n_subjects`` 가중 평균과
    정확히 같다 (fold 단순 평균이 아니다 — fold 크기가 다르면 둘이 다르다). 공동 BA 도
    같은 방식 (OOF ``b_i`` 평균). 그 다음 네 cell 을 같은 가중으로 평균한다.
    (09-24 19:15 슬롯 정정: 이전 구현은 fold 단순 평균이었다. 구조 비교·S 선택은 이미
    OOF 병합이었다.)

    Raises:
        TrainError: grid 가 불완전하거나, 같은 inner fold 의 subject 수가 config·cell 사이에서
            다르면 (같은 inner 모집단에서 비교해야 한다).
    """
    _require_complete(results, n_folds)

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
        # cell 안: OOF 병합 = fold subject 수 가중. cell 사이: 같은 가중.
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
    if not 1 <= common_e <= MAX_EPOCHS:
        raise TrainError(f"공통 E 가 1–{MAX_EPOCHS} 밖이다: {common_e}")

    return Selection(config_id=chosen, common_epochs=common_e,
                     joint_loss=per_config[chosen]["joint_loss"],
                     joint_ba=per_config[chosen]["joint_ba"],
                     tie_rule=tie_rule, per_config=per_config)


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return float(s[mid]) if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def baseline_epochs(best_epochs: Sequence[int]) -> int:
    """baseline 의 epoch = 해당 선택 모델의 3개 inner best epochs 중앙값 올림."""
    if len(best_epochs) != 3:
        raise TrainError(f"inner best epoch 3개가 필요하다: {len(best_epochs)}")
    return math.ceil(_median(best_epochs))


def assert_no_test_leakage(scores_used: Mapping[str, str]) -> None:
    """선택에 쓰인 점수의 출처가 모두 inner validation 인지 확인한다 (T12).

    Raises:
        TrainError: outer test 나 external 출처가 하나라도 있으면.
    """
    forbidden = sorted(k for k, v in scores_used.items()
                       if v not in ("inner_validation",))
    if forbidden:
        raise TrainError(
            f"선택에 inner validation 이 아닌 점수가 쓰였다: {forbidden[:5]}. "
            "outer test 로 early stopping·선택하지 않는다")


def updates_per_epoch(n_train: int, batch_size: int = BATCH_SIZE) -> int:
    """한 epoch 의 optimizer update 수 = ``ceil(n_train / batch_size)`` (마지막 배치 포함)."""
    if n_train <= 0 or batch_size <= 0:
        raise TrainError(f"학습 창 수·배치 크기는 양수여야 한다: {n_train}, {batch_size}")
    return math.ceil(n_train / batch_size)


def min_epochs_for(n_train: int, *, batch_size: int = BATCH_SIZE,
                   min_updates: int = MIN_UPDATES) -> int:
    """최소 update 를 채우는 최소 epoch 수 (계획서 §11 P8).

    ``min_updates`` 가 0 이면 1 을 돌려준다 — 합성 시험 전용이며 CLI 는 config 의
    잠긴 값(5,000, P8-b)을 넘긴다.
    """
    if min_updates < 0:
        raise TrainError(f"min_updates 는 음수일 수 없다: {min_updates}")
    upe = updates_per_epoch(n_train, batch_size)
    return max(1, math.ceil(min_updates / upe))


def early_stop_epoch(val_losses: Sequence[float], *, patience: int = PATIENCE,
                     min_delta: float = MIN_DELTA, min_epoch: int = 1) -> int:
    """subject-equal validation log loss 로 best epoch 를 고른다 (1-indexed).

    ``min_delta`` 이상 개선되지 않는 epoch 가 ``patience`` 번 이어지면 멈춘다.
    **[개정 P8]** ``min_epoch`` 이전 epoch 는 best 후보도, 인내 계산 대상도 아니다.
    따라서 돌려주는 값은 언제나 ``min_epoch`` 이상이다.

    Raises:
        TrainError: loss 가 비었거나 ``min_epoch`` 에 못 미칠 때.
    """
    if not len(val_losses):
        raise TrainError("validation loss 가 비었다")
    if min_epoch < 1:
        raise TrainError(f"min_epoch 는 1 이상이어야 한다: {min_epoch}")
    if len(val_losses) < min_epoch:
        raise TrainError(f"validation loss {len(val_losses)}개가 최소 epoch "
                         f"{min_epoch} 에 못 미친다 — 최소치 전에는 멈출 수 없다")
    best, best_epoch, bad = float("inf"), min_epoch, 0
    for i, v in enumerate(val_losses, start=1):
        if i < min_epoch:
            continue
        if v < best - min_delta:
            best, best_epoch, bad = v, i, 0
        else:
            bad += 1
            if bad >= patience:
                break
    return best_epoch


def fit_budget(n_outer: int = 5, n_inner: int = 3, n_cells: int = 4,
               n_configs: int = 8, n_seeds: int = 3) -> Dict[str, int]:
    """프로토콜 §7 의 계산 예산. 표의 곱셈을 코드로 고정한다."""
    main_inner = n_configs * n_inner * n_cells * n_outer
    main_outer = n_cells * n_outer * n_seeds
    null_sensitivity = 4 * 2 * n_outer * n_seeds
    external_selection = n_configs * n_inner * n_cells
    external_final = n_cells * n_seeds
    return {"main_inner": main_inner, "main_outer": main_outer,
            "null_sensitivity": null_sensitivity,
            "external_selection": external_selection,
            "external_final": external_final,
            "total": main_inner + main_outer + null_sensitivity +
                     external_selection + external_final}
