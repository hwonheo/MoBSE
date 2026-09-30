"""Fold 범위 적합 — v3 학습 규칙 (결정 31-1·32) 과 ROI 정체 구조 (결정 28-2).

`mobse.v2.fitting` 을 그대로 쓸 수 없는 이유는 하나다. 그 모듈은 **최상위에서**
`MAX_EPOCHS` 와 `MIN_UPDATES` 를 import 하고 (`mobse/v2/fitting.py:36`), 그 두
상수를 `train_fold` 안에서 상한·하한으로 쓴다. v3 는 "update 예산 5,000 을 모든
N 이 동일하게, epoch 상한은 그 예산에서 나온다" 로 규칙이 바뀌었으므로
(`mobse.v3.train`), 같은 함수를 그 규칙으로 다시 쓴다. 프로세스 안에서 상수를
덮어쓰는 감싸개는 **쓰지 않는다** — 잠글 수 있는 판본이 아니기 때문이다.

바뀐 것은 셋뿐이다.

1. **epoch 상한이 상수가 아니다.** `epochs_for_budget(학습 창 수)` 가 그 fit 의
   상한이다. 고정 상한 400 은 없다.
2. **best checkpoint 를 고르는 데 최소 epoch 결합이 없다** (결정 32). v1 은
   `min_epoch` 이전 epoch 를 후보에서 뺐다 — 저표본에서 그 결합은 10 명짜리
   학습이 창 80 개를 1,667 epoch 반복한 뒤에야 checkpoint 를 고르게 만든다.
3. **모델이 ROI 정체 구조를 받는다** (결정 28-2). `roi_structure` 가 `"mean"`
   이면 v1 과 같은 등변 경로다.

바뀌지 않은 것 — 창 참조·manifest 대조·fold subject 해석·변환 적합·인코딩·
결정성·누설 검사·손실·balanced accuracy — 은 **동결된 `mobse.v2.fitting` 을
import 해 그대로 쓴다.** 여기서 다시 쓰지 않는다.

열린 갈래 (보고 사항, 2026-09-30)
--------------------------------
inner 에서 고른 공통 E 를 outer fit 으로 **어떻게 옮길지**는 아직 정해지지
않았다. v1 은 epoch 수를 그대로 옮겼다 (예산이 하한이고 상한이 공유라 문제가
없었다). v3 는 예산이 상한이므로, outer 학습 집합이 inner 보다 크면 같은 epoch
수가 예산을 넘을 수 있다. 이 모듈은 **넘으면 거부한다** — 조용히 잘라 내면
"모든 N 이 같은 예산" 이라는 전제가 기록 없이 깨진다. 옮기는 규칙 자체는
구동기·CLI 쪽 결정이라 여기서 정하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from mobse.v2.fitting import (  # 동결된 v1 부품 — 규칙이 바뀌지 않은 것
    CUBLAS_DETERMINISTIC_CONFIGS,
    EVAL_ROLE,
    ROLE_EXTERNAL,
    ROLE_INNER,
    ROLE_OUTER,
    ROLES,
    EncodedSet,
    FitError,
    FoldSubjects,
    FoldTransform,
    WindowRef,
    apply_determinism,
    canonical_subject_of,
    crosscheck_with_windows_manifest,
    encode_windows,
    fit_fold_transform,
    read_window,
    refs_from_extract_manifest,
    resolve_fold_subjects,
    run_probabilities,
    select_refs,
    subject_run_true_probs,
    task_of,
)
from mobse.v2.fitting import (  # noqa: F401  (구현 선택: 사문 재작성 안 함)
    _balanced_accuracy_from_runs,
    _encoder_init_hash,
    _forward_probs,
)
from mobse.v3.models import ROI_STRUCTURES
from mobse.v3.train import (
    BATCH_SIZE,
    CELLS,
    GRAD_CLIP,
    MIN_DELTA,
    MODEL_SEEDS,
    PATIENCE,
    UPDATE_BUDGET,
    assert_no_test_leakage,
    build_grid,
    epochs_for_budget,
    select_best_epoch,
    subject_equal_loss,
    updates_per_epoch,
)

__all__ = [
    "BATCH_SIZE", "CELLS", "GRAD_CLIP", "MIN_DELTA", "MODEL_SEEDS", "PATIENCE",
    "ROI_STRUCTURES", "UPDATE_BUDGET", "epochs_for_budget", "select_best_epoch",
    "CUBLAS_DETERMINISTIC_CONFIGS", "EVAL_ROLE", "ROLES", "ROLE_EXTERNAL",
    "ROLE_INNER", "ROLE_OUTER", "EncodedSet", "FitError", "FitResult",
    "FoldSubjects", "FoldTransform", "WindowRef", "apply_determinism",
    "build_fit_model", "canonical_subject_of", "crosscheck_with_windows_manifest",
    "encode_windows", "fit_fold_transform", "read_window",
    "refs_from_extract_manifest", "resolve_fold_subjects", "run_probabilities",
    "select_refs", "subject_run_true_probs", "task_of", "train_fold",
]


@dataclass
class FitResult:
    """한 fit 의 결과. v1 과 두 군데가 다르다.

    `min_epoch` 자리에 `epoch_ceiling` 이 온다 — v3 에서 그 수는 하한이 아니라
    예산에서 나온 **상한**이기 때문이다. `update_budget` 과 `roi_structure` 를
    함께 적어, 결과만 보고도 어떤 규칙·구조로 돌았는지 알 수 있게 한다.
    """

    role: str
    cell: str
    outer_fold: int
    inner_fold: int
    config_id: int
    model_seed: int
    roi_structure: str
    epochs_run: int
    best_epoch: int
    epoch_ceiling: int
    update_budget: int
    updates_per_epoch: int
    updates_run: int
    val_losses: List[float]
    eval_run_probs: Dict[str, float]
    eval_window_probs: Dict[str, float]
    eval_loss: float
    eval_balanced_accuracy: float
    transform: Dict[str, Any]
    timing: Dict[str, float]
    memory: Dict[str, Any]
    encoder_init_hash: str
    rng_note: str
    determinism: Dict[str, Any] = field(default_factory=dict)
    #: 평가 확률·반환 모델의 가중치가 나온 epoch (1-indexed).
    eval_epoch: int = 0


def build_fit_model(cell: str, cfg, transform: FoldTransform, *,
                    roi_structure: str = "mean"):
    """cell 과 ROI 정체 구조로 학습할 모델을 만든다.

    Args:
        cell: A–D. v3 에는 §6 구조 비교 (NG·SG) 가 없다 — 결정 33 의 칸은
            A–D 와 구조의 곱이다.
        cfg: `mobse.v2.models.ModelConfig`.
        transform: fold 변환. brain/null bank 를 여기서 가져온다.
        roi_structure: `ROI_STRUCTURES` 중 하나. `"mean"` 은 v1 과 같은 등변 경로다.

    Raises:
        FitError: 알 수 없는 cell 이거나 구조 이름이 틀렸을 때.
    """
    import torch

    from mobse.v2.models import CELL_SPEC
    from mobse.v3.models import MoBSEv3

    if cell not in CELL_SPEC:
        raise FitError(f"알 수 없는 cell: {cell!r}. v3 의 칸은 {sorted(CELL_SPEC)} 와 "
                       f"ROI 구조의 곱이다 (결정 33) — NG·SG 는 v3 에 없다")
    if roi_structure not in ROI_STRUCTURES:
        raise FitError(f"roi_structure 는 {ROI_STRUCTURES} 중 하나여야 한다: "
                       f"{roi_structure!r}")
    spec = CELL_SPEC[cell]
    templates = transform.brain if spec["bank"] == "brain" else transform.null
    bank = torch.as_tensor(templates.templates, dtype=torch.float32)
    return MoBSEv3(cfg, bank, routing=spec["routing"], roi_structure=roi_structure)


def train_fold(train_set: EncodedSet, eval_set: EncodedSet,
               transform: FoldTransform, *, cell: str, config_id: int,
               model_seed: int, fold: FoldSubjects, roi_structure: str = "mean",
               device: str = "cpu", batch_size: int = BATCH_SIZE,
               patience: int = PATIENCE, min_delta: float = MIN_DELTA,
               grad_clip: float = GRAD_CLIP,
               early_stopping: Optional[bool] = None,
               epochs_exact: Optional[int] = None,
               update_budget: int = UPDATE_BUDGET) -> Tuple["FitResult", Any]:
    """한 fit 을 학습하고 평가 집합의 예측을 낸다 — v3 규칙.

    Returns:
        `(FitResult, model)`. 저장 경로는 호출자가 정한다 (v1 과 같다). inner fit
        은 best epoch 의 가중치를 복원한 뒤 평가 확률을 내고 그 모델을 돌려준다.

    Args:
        roi_structure: 결정 28-2 의 ROI 정체 구조. `"mean"` 은 v1 과 같다.
        early_stopping: 기본값은 role 이 inner 일 때만 True. outer 에서 켤 수 없다.
        epochs_exact: outer/external fit 이 정확히 돌 epoch 수. **예산에서 나온
            상한을 넘으면 거부한다** (모듈 docstring 의 "열린 갈래").
        update_budget: 이 fit 이 받는 optimizer update 예산 (결정 31-1·32).

    Raises:
        FitError: outer fit 에 early stopping 을 요구하거나 epoch 수가 없을 때,
            `epochs_exact` 가 예산 상한 밖일 때, training 라벨이 두 class 가
            아닐 때 (T11), cell·구조 이름이 틀렸을 때.
        TrainError: 예산이 양수가 아니거나 안전 상한을 넘을 때
            (`epochs_for_budget`), 또는 선택 점수의 출처가 inner validation 이
            아닐 때 (T12).
    """
    import time

    import torch

    from mobse.v2.models import ModelConfig

    grid = {g.config_id: g for g in build_grid()}
    if config_id not in grid:
        raise FitError(f"config_id 는 0–7 이어야 한다: {config_id}")
    gc = grid[config_id]
    if cell not in CELLS:
        raise FitError(f"v3 의 cell 은 {sorted(CELLS)} 뿐이다: {cell!r}")
    if roi_structure not in ROI_STRUCTURES:
        raise FitError(f"roi_structure 는 {ROI_STRUCTURES} 중 하나여야 한다: "
                       f"{roi_structure!r}")

    is_inner = fold.role == ROLE_INNER
    if early_stopping is None:
        early_stopping = is_inner
    if early_stopping and not is_inner:
        raise FitError(
            f"{fold.role} fit 에 early stopping 을 켤 수 없다 — 평가 집합은 "
            f"{fold.eval_role} 이고 그것으로 멈추면 leakage 다 (계획서 §7)")
    if not is_inner and not epochs_exact:
        raise FitError("outer/external fit 은 공통 E 를 정확히 받아야 한다 (계획서 §7)")
    train_classes = sorted({int(v) for v in np.asarray(train_set.y).ravel().tolist()})
    if train_classes != [0, 1]:
        raise FitError(f"training 라벨이 두 class 가 아니다: {train_classes} "
                       "(single class fold 거부, T11)")

    upe = updates_per_epoch(len(train_set), batch_size)
    # 상한은 상수가 아니라 이 학습 집합의 예산에서 나온다 (결정 31-1).
    epoch_ceiling = epochs_for_budget(len(train_set), batch_size=batch_size,
                                      update_budget=update_budget)
    if epochs_exact:
        n_epochs_planned = int(epochs_exact)
        if not 1 <= n_epochs_planned <= epoch_ceiling:
            raise FitError(
                f"공통 E {n_epochs_planned} 가 예산 상한 1–{epoch_ceiling} 밖이다 "
                f"(학습 창 {len(train_set)}, update/epoch {upe}, 예산 {update_budget}). "
                "예산은 모든 N 이 똑같이 받는 상한이므로 여기서 조용히 자르지 않는다 "
                "— inner 의 공통 E 를 outer 로 옮기는 규칙은 아직 정해지지 않았다")
    else:
        n_epochs_planned = epoch_ceiling

    determinism = apply_determinism()
    dev = torch.device(device)
    torch.manual_seed(model_seed)
    cfg = ModelConfig(n_roi=int(train_set.x.shape[1]),
                      n_samples=int(train_set.x.shape[2]),
                      pca_dim=int(train_set.pca.shape[1]),
                      dropout=float(gc.dropout))
    model = build_fit_model(cell, cfg, transform, roi_structure=roi_structure).to(dev)
    enc_hash = _encoder_init_hash(model)

    opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate,
                            weight_decay=gc.weight_decay)
    lossf = torch.nn.CrossEntropyLoss()

    xt = torch.as_tensor(train_set.x).to(dev)
    pt = torch.as_tensor(train_set.pca).to(dev)
    yt = torch.as_tensor(train_set.y).to(dev)
    xe = torch.as_tensor(eval_set.x).to(dev)
    pe = torch.as_tensor(eval_set.pca).to(dev)

    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(model_seed)

    n_epochs = n_epochs_planned
    val_losses: List[float] = []
    best_state: Optional[Dict[str, Any]] = None
    best_state_epoch = 0
    t0 = time.perf_counter()
    for _ in range(n_epochs):
        model.train()
        order = torch.randperm(len(train_set), generator=gen).to(dev)
        for s in range(0, len(train_set), batch_size):
            idx = order[s:s + batch_size]
            opt.zero_grad(set_to_none=True)
            res = model(xt[idx], pt[idx])
            loss = lossf(res["logits"], yt[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            opt.step()
        if early_stopping:
            probs = _forward_probs(model, xe, pe, batch_size=batch_size)
            rp = run_probabilities(eval_set.refs, probs)
            val_losses.append(subject_equal_loss(subject_run_true_probs(rp)))
            # 결정 32: 최소 epoch 결합이 없다 — 1 epoch 부터 후보다.
            cur_best = select_best_epoch(val_losses, patience=patience,
                                         min_delta=min_delta)
            if cur_best == len(val_losses):
                best_state = {k: v.detach().clone()
                              for k, v in model.state_dict().items()}
                best_state_epoch = cur_best
            if len(val_losses) - cur_best >= patience:
                break
    elapsed = time.perf_counter() - t0

    if early_stopping:
        assert_no_test_leakage({f"epoch{i}": "inner_validation"
                                for i in range(len(val_losses))})
        best_epoch = select_best_epoch(val_losses, patience=patience,
                                       min_delta=min_delta)
        if best_state is None or best_state_epoch != best_epoch:
            raise FitError(f"best checkpoint 불일치: 보관 epoch {best_state_epoch}, "
                           f"best epoch {best_epoch} (결정 12)")
        if best_epoch != len(val_losses):
            model.load_state_dict(best_state)
        eval_epoch = best_epoch
    else:
        best_epoch = n_epochs
        eval_epoch = n_epochs

    probs = _forward_probs(model, xe, pe, batch_size=batch_size)
    run_probs = run_probabilities(eval_set.refs, probs)
    window_probs = {r.window_key: float(p) for r, p in zip(eval_set.refs, probs)}
    memory: Dict[str, Any] = {"device": str(dev)}
    if dev.type == "cuda":
        memory["peak_gpu_bytes"] = int(torch.cuda.max_memory_allocated(dev))

    epochs_run = len(val_losses) if early_stopping else n_epochs
    return FitResult(
        role=fold.role, cell=cell, outer_fold=fold.outer_fold,
        inner_fold=fold.inner_fold, config_id=config_id, model_seed=model_seed,
        roi_structure=roi_structure,
        epochs_run=epochs_run, best_epoch=best_epoch,
        epoch_ceiling=epoch_ceiling, update_budget=int(update_budget),
        updates_per_epoch=upe, updates_run=upe * epochs_run,
        val_losses=val_losses,
        eval_run_probs=run_probs, eval_window_probs=window_probs,
        eval_loss=subject_equal_loss(subject_run_true_probs(run_probs)),
        eval_balanced_accuracy=_balanced_accuracy_from_runs(run_probs),
        transform=transform.provenance(),
        timing={"train_seconds": elapsed,
                "seconds_per_epoch": elapsed / max(1, epochs_run)},
        memory=memory, encoder_init_hash=enc_hash,
        rng_note=("encoder 는 cell 간 같은 seed 에서 동일 초기화다. gate 가 소비하는 "
                  "RNG 양이 달라 graph layer·head 이후는 cell 마다 다르다 — 계획서 §7. "
                  "ROI 구조가 embedding 이면 parameter 가 하나 늘어 그 뒤 초기화가 "
                  "또 달라진다 (결정 28-2)"),
        determinism=determinism, eval_epoch=eval_epoch,
    ), model
