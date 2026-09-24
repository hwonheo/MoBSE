"""Fold 범위 적합 — 계획서 §4·§5·§6·§7, 지침서 WI-04~WI-06.

한 번의 fit 은 **(role, cell, outer fold, inner fold, config, model seed)** 하나다.
계획서 §7 의 비용표(480 + 60 + 120 + 96 + 12 = 768)가 그 단위로 세어져 있다.

이 모듈이 지키는 경계
--------------------
* **변환·bank 는 그 fit 의 training subject 로만 적합한다.** `allowed_subjects`
  를 넘겨 `features.fit_transform_on_training_rest` 가 위반을 **실패로** 만들게
  한다 (T03). 경계를 코드가 아니라 자료로 강제한다.
* **평가 집합으로 early stopping 하지 않는다.** inner fit 만 early stopping 을
  하며 그 점수의 출처를 `train.assert_no_test_leakage` 로 검사한다 (T12).
* **경로를 추측하지 않는다.** 창의 `.npy` 경로는 WI-02 manifest 가 기록한 값만
  쓰고, 읽은 뒤 sha256 을 대조한다 (U20).

fold 지정 규약은 `templates` 가 이미 정해 두었다 —
`OUTER_FIT_INNER_FOLD = 9` 는 outer 최종 적합, `EXTERNAL_OUTER_FOLD = 9` 는
외부 코호트다. 여기서도 같은 상수를 쓴다.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from . import features as F
from . import templates as T
from .labels import CLASS_LABELS, class_index, window_key
from .train import (BATCH_SIZE, CELLS, GRAD_CLIP, MAX_EPOCHS, MIN_DELTA, MIN_UPDATES,
                    MODEL_SEEDS, PATIENCE,
                    TrainError, assert_no_test_leakage, build_grid,
                    clipped_log_loss, early_stop_epoch, min_epochs_for,
                    subject_equal_loss, updates_per_epoch)

ROLE_INNER = "inner"
ROLE_OUTER = "outer"
ROLE_EXTERNAL = "external"
ROLES = (ROLE_INNER, ROLE_OUTER, ROLE_EXTERNAL)

#: inner fit 의 평가 집합은 inner validation, outer fit 은 outer test 다.
EVAL_ROLE = {ROLE_INNER: "inner_validation", ROLE_OUTER: "outer_test",
             ROLE_EXTERNAL: "external"}


class FitError(RuntimeError):
    """fold 적합 규칙 위반."""


# --------------------------------------------------------------------------- #
# 창 참조
# --------------------------------------------------------------------------- #


def canonical_subject_of(run_key: str) -> str:
    """``ds002785/sub-0002/...`` → ``ds002785:sub-0002``."""
    parts = run_key.split("/")
    if len(parts) < 2:
        raise FitError(f"run_key 형식이 아니다: {run_key!r}")
    return f"{parts[0]}:{parts[1]}"


def task_of(run_key: str) -> str:
    """run_key 의 task 성분."""
    parts = run_key.split("/")
    if len(parts) < 4:
        raise FitError(f"run_key 에 task 성분이 없다: {run_key!r}")
    return parts[3]


@dataclass(frozen=True)
class WindowRef:
    """창 하나의 참조. 경로는 manifest 가 기록한 값 그대로다."""

    window_key: str
    run_key: str
    canonical_subject: str
    task: str
    path: Path
    sha256: str
    label: Optional[int] = None


def _run_records(manifest: Path) -> List[Dict[str, Any]]:
    out = []
    for line in Path(manifest).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("record_type") == "run":
            out.append(rec)
    return out


def refs_from_extract_manifest(manifest: Path, *, labelled: bool) -> List[WindowRef]:
    """WI-02 추출 manifest 의 ``ok`` run 에서 창 참조를 만든다.

    Args:
        labelled: True 면 task 로부터 class index 를 붙인다. rest 는 False 다.
    """
    refs: List[WindowRef] = []
    for rec in _run_records(manifest):
        if rec.get("status") != "ok":
            continue
        rk = rec["run_key"]
        task = task_of(rk)
        if labelled and task not in CLASS_LABELS:
            raise FitError(f"분류 대상이 아닌 task 가 labelled manifest 에 있다: {task}")
        for i, w in enumerate(rec.get("windows") or []):
            refs.append(WindowRef(
                window_key=window_key(rk, i), run_key=rk,
                canonical_subject=rec["canonical_subject"], task=task,
                path=Path(w["path"]), sha256=w["sha256"],
                label=class_index(task) if labelled else None))
    return refs


def crosscheck_with_windows_manifest(refs: Sequence[WindowRef],
                                     windows_manifest: Path) -> Dict[str, int]:
    """창 manifest 와 추출 manifest 가 같은 창 집합을 가리키는지 대조한다.

    두 파일은 서로 다른 단계의 산출물이다. 하나만 믿고 진행하면 label 과 자료가
    어긋나도 알 수 없다.

    Raises:
        FitError: 창 집합이나 해시가 어긋나면.
    """
    by_key = {r.window_key: r for r in refs}
    seen = 0
    for line in Path(windows_manifest).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        wk = rec["window_key"]
        ref = by_key.get(wk)
        if ref is None:
            raise FitError(f"창 manifest 에만 있는 창: {wk}")
        if ref.sha256 != rec["data_sha256"]:
            raise FitError(f"창 해시 불일치: {wk}")
        if ref.label != class_index(rec["observed_label"]):
            raise FitError(f"label 불일치: {wk}")
        seen += 1
    if seen != len(refs):
        raise FitError(f"창 수 불일치: 추출 {len(refs)} vs 창 manifest {seen}")
    return {"n_windows": seen}


def read_window(ref: WindowRef, *, verify: bool = True) -> np.ndarray:
    """``(n_samples, n_roi)`` 배열. 읽은 뒤 sha256 을 대조한다."""
    raw = ref.path.read_bytes()
    if verify:
        got = hashlib.sha256(raw).hexdigest()
        if got != ref.sha256:
            raise FitError(f"창 해시 불일치: {ref.path} 기대 {ref.sha256[:12]} 실제 {got[:12]}")
    arr = np.load(ref.path)
    if arr.ndim != 2:
        raise FitError(f"창이 2차원이 아니다: {ref.path} {arr.shape}")
    return np.asarray(arr, dtype=float)


# --------------------------------------------------------------------------- #
# fold 해석
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FoldSubjects:
    """한 fit 의 학습·평가 subject."""

    role: str
    outer_fold: int
    inner_fold: int
    train: Tuple[str, ...]
    evaluate: Tuple[str, ...]
    eval_role: str


def resolve_fold_subjects(folds: Mapping[str, Any], outer_fold: int,
                          inner_fold: int) -> FoldSubjects:
    """``folds.json`` 에서 이 fit 의 학습·평가 subject 를 꺼낸다.

    ``inner_fold == templates.OUTER_FIT_INNER_FOLD`` 이면 outer 최종 적합이다 —
    outer train 전체로 학습하고 outer test 로 평가한다.

    Raises:
        FitError: fold 번호가 없거나 pilot 이 섞여 있으면.
    """
    outer_list = folds.get("outer_folds") or []
    match = [o for o in outer_list if int(o["outer_fold"]) == outer_fold]
    if not match:
        raise FitError(f"outer fold {outer_fold} 가 folds.json 에 없다")
    outer = match[0]
    pilot = set(folds.get("pilot", {}).get("subjects") or [])

    if inner_fold == T.OUTER_FIT_INNER_FOLD:
        train = tuple(outer["train_subjects"])
        evaluate = tuple(outer["test_subjects"])
        role, eval_role = ROLE_OUTER, EVAL_ROLE[ROLE_OUTER]
    else:
        inner_list = [i for i in outer.get("inner") or []
                      if int(i["inner_fold"]) == inner_fold]
        if not inner_list:
            raise FitError(f"inner fold {inner_fold} 가 outer {outer_fold} 에 없다")
        inner = inner_list[0]
        train = tuple(inner["train_subjects"])
        evaluate = tuple(inner["val_subjects"])
        role, eval_role = ROLE_INNER, EVAL_ROLE[ROLE_INNER]

    leaked = sorted(pilot & (set(train) | set(evaluate)))
    if leaked:
        raise FitError(f"pilot 이 fit 에 섞였다: {leaked[:5]} — 계획서 §4-2")
    overlap = sorted(set(train) & set(evaluate))
    if overlap:
        raise FitError(f"train 과 평가 집합이 겹친다: {overlap[:5]}")
    return FoldSubjects(role=role, outer_fold=outer_fold, inner_fold=inner_fold,
                        train=train, evaluate=evaluate, eval_role=eval_role)


# --------------------------------------------------------------------------- #
# 변환·bank
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FoldTransform:
    """이 fit 에 고정된 변환과 bank."""

    frozen: F.FrozenTransform
    brain: T.GraphBank
    null: T.GraphBank
    n_rest_windows: int
    fit_subjects: Tuple[str, ...]
    # §6 구조 비교 SG 의 training-rest single average graph (결정 14). SG fit 에만 만든다.
    single: Optional[T.SingleGraph] = None

    def provenance(self) -> Dict[str, Any]:
        out = self._bank_provenance()
        if self.single is not None:
            out["single_graph_id"] = self.single.graph_id
            out["single_graph_fingerprint"] = self.single.fingerprint()
            out["single_graph_n_windows"] = self.single.n_windows
        return out

    def _bank_provenance(self) -> Dict[str, Any]:
        return {
            "scaler_pca_id": self.frozen.artifact_id,
            "scaler_pca_fingerprint": self.frozen.fingerprint(),
            "bank_id": self.brain.bank_id,
            "bank_fingerprint": self.brain.fingerprint(),
            "null_bank_id": self.null.bank_id,
            "null_bank_fingerprint": self.null.fingerprint(),
            "bank_seed": self.brain.seed,
            "null_seed": self.null.seed,
            "n_rest_windows": self.n_rest_windows,
            "n_fit_subjects": len(self.fit_subjects),
            "cluster_sizes": np.bincount(self.brain.assignment,
                                         minlength=self.brain.k).tolist(),
        }


def fit_fold_transform(rest_refs: Sequence[WindowRef], train_subjects: Sequence[str],
                       *, bank_seed: int, null_seed: int = T.NULL_SEED_PRIMARY,
                       n_components: int = F.N_PCA, k: int = T.K_DEFAULT,
                       density: float = T.EDGE_DENSITY,
                       verify: bool = True,
                       single_graph: bool = False) -> FoldTransform:
    """training-rest 창으로 scaler/PCA 와 bank 를 적합한다.

    `allowed_subjects` 를 넘겨 허용 밖 subject 의 창이 하나라도 섞이면
    `FeatureError` 로 **실패**하게 한다 (T03).

    ``single_graph=True`` 이면 §6 구조 비교 SG 의 graph 하나를 bank 와 **같은**
    training-rest 창(training subject 경계)의 원래 correlation 으로 만든다 (결정 14).
    """
    allowed = set(train_subjects)
    used = [r for r in rest_refs if r.canonical_subject in allowed]
    if not used:
        raise FitError("training-rest 창이 하나도 없다")
    arrays = [read_window(r, verify=verify) for r in used]
    correlations, z = F.stack_window_features(arrays)
    fit_subjects = [r.canonical_subject for r in used]
    frozen = F.fit_transform_on_training_rest(
        z, fit_subjects, n_components=n_components,
        allowed_subjects=sorted(allowed))
    pca = frozen.transform(z)
    brain = T.build_bank(correlations, pca, fit_subjects,
                         seed=bank_seed, k=k, density=density)
    null = T.make_null_bank(brain, seed=null_seed)
    single = (T.build_single_graph(correlations, fit_subjects, density=density)
              if single_graph else None)
    return FoldTransform(frozen=frozen, brain=brain, null=null,
                         n_rest_windows=len(used),
                         fit_subjects=tuple(sorted(set(fit_subjects))),
                         single=single)


# --------------------------------------------------------------------------- #
# 입력 인코딩
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EncodedSet:
    """모델 입력으로 바꾼 창 묶음."""

    x: np.ndarray              # (n, n_roi, n_samples)
    pca: np.ndarray            # (n, n_components)
    y: np.ndarray              # (n,)
    refs: Tuple[WindowRef, ...]

    def __len__(self) -> int:
        return int(self.x.shape[0])


def encode_windows(refs: Sequence[WindowRef], transform: FoldTransform,
                   *, verify: bool = True) -> EncodedSet:
    """창을 ``(B, n_roi, T)`` 입력과 gate 용 PCA feature 로 바꾼다.

    gate 입력은 **그 창 자신의 FC** 를 고정 변환에 통과시킨 값이다
    (계획서 §6 — 입력 의존 routing).
    """
    if not refs:
        raise FitError("인코딩할 창이 없다")
    arrays = [read_window(r, verify=verify) for r in refs]
    _, z = F.stack_window_features(arrays)
    pca = transform.frozen.transform(z)
    x = np.stack([a.T for a in arrays])          # (n_samples, n_roi) → (n_roi, n_samples)
    labels = [r.label for r in refs]
    if any(v is None for v in labels):
        raise FitError("label 이 없는 창이 있다")
    return EncodedSet(x=np.asarray(x, dtype=np.float32),
                      pca=np.asarray(pca, dtype=np.float32),
                      y=np.asarray(labels, dtype=np.int64),
                      refs=tuple(refs))


def select_refs(refs: Sequence[WindowRef], subjects: Sequence[str]) -> List[WindowRef]:
    """해당 subject 의 창만 고른다."""
    keep = set(subjects)
    return [r for r in refs if r.canonical_subject in keep]


# --------------------------------------------------------------------------- #
# 학습
# --------------------------------------------------------------------------- #


def run_probabilities(refs: Sequence[WindowRef], p_class1: Sequence[float]
                      ) -> Dict[str, float]:
    """창 확률을 run 단위로 평균한다. run 당 창 수가 4가 아니면 실패한다."""
    buckets: Dict[str, List[float]] = {}
    for ref, p in zip(refs, p_class1):
        buckets.setdefault(ref.run_key, []).append(float(p))
    out = {}
    for rk, vals in buckets.items():
        if len(vals) != 4:
            raise FitError(f"run 의 창이 4개가 아니다: {rk} ({len(vals)}개)")
        out[rk] = float(np.mean(vals))
    return out


def subject_run_true_probs(run_probs: Mapping[str, float]) -> Dict[str, List[float]]:
    """subject → 각 run 의 **정답 class 확률**. `train.subject_equal_loss` 입력."""
    out: Dict[str, List[float]] = {}
    for rk, p1 in run_probs.items():
        truth = class_index(task_of(rk))
        out.setdefault(canonical_subject_of(rk), []).append(p1 if truth == 1 else 1.0 - p1)
    return out


def _forward_probs(model, x, pca, *, batch_size: int) -> "np.ndarray":
    """전체 집합의 class 1 확률. 학습하지 않는다."""
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, x.shape[0], batch_size):
            res = model(x[s:s + batch_size], pca[s:s + batch_size])
            out.append(torch.softmax(res["logits"], dim=-1)[:, 1].cpu().numpy())
    return np.concatenate(out) if out else np.zeros(0)


@dataclass
class FitResult:
    """한 fit 의 결과. 예측은 평가 집합에 대한 것이다."""

    role: str
    cell: str
    outer_fold: int
    inner_fold: int
    config_id: int
    model_seed: int
    epochs_run: int
    best_epoch: int
    min_epoch: int
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
    #: 평가 확률·반환 모델의 가중치가 나온 epoch (1-indexed). inner 는 best_epoch,
    #: outer/external 은 마지막 epoch 이다 (계획서 §7 selected best checkpoint).
    eval_epoch: int = 0


#: cuBLAS 가 결정적으로 도는 workspace 설정 (PyTorch reproducibility 문서).
CUBLAS_DETERMINISTIC_CONFIGS = (":4096:8", ":16:8")


def apply_determinism() -> Dict[str, Any]:
    """config ``runtime.deterministic: True`` 를 torch 에 실제로 적용한다 (E22).

    ``torch.use_deterministic_algorithms(True)`` (비결정 연산은 조용히 넘어가지 않고
    RuntimeError), cuDNN deterministic on·benchmark off, ``CUBLAS_WORKSPACE_CONFIG``
    를 켠다. 환경변수는 이미 결정적 값이면 그대로 두고, 다른 값이면 거부한다.

    Returns:
        적용 뒤 실제 상태 (fit_report 에 기록한다).

    Raises:
        FitError: ``CUBLAS_WORKSPACE_CONFIG`` 가 결정적이지 않은 값으로 이미 설정됐을 때.
    """
    import torch

    cur = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    if cur is None:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = CUBLAS_DETERMINISTIC_CONFIGS[0]
    elif cur not in CUBLAS_DETERMINISTIC_CONFIGS:
        raise FitError(f"CUBLAS_WORKSPACE_CONFIG={cur!r} 는 결정적이지 않다 — "
                       f"{CUBLAS_DETERMINISTIC_CONFIGS} 중 하나여야 한다 (E22)")
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    state = {
        "use_deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "torch_version": str(torch.__version__),
    }
    if not (state["use_deterministic_algorithms"] and state["cudnn_deterministic"]
            and not state["cudnn_benchmark"]):
        raise FitError(f"결정성 설정이 켜지지 않았다: {state}")
    return state


def _balanced_accuracy_from_runs(run_probs: Mapping[str, float],
                                 threshold: float = 0.5) -> float:
    """계획서 §8 의 ``b_i`` 평균. 동일값은 class 1 이다."""
    per_subject: Dict[str, List[int]] = {}
    for rk, p1 in run_probs.items():
        truth = class_index(task_of(rk))
        pred = 1 if p1 >= threshold else 0
        per_subject.setdefault(canonical_subject_of(rk), []).append(int(pred == truth))
    scores = [sum(v) / len(v) for v in per_subject.values()]
    if not scores:
        raise FitError("평가 subject 가 없다")
    return float(np.mean(scores))


def _encoder_init_hash(model) -> str:
    """encoder parameter 초기값의 해시. cell 간 공통 초기화 확인용."""
    import torch

    with torch.no_grad():
        flat = torch.cat([p.detach().reshape(-1).cpu()
                          for n, p in sorted(model.named_parameters())
                          if n.startswith("encoder.")])
    return hashlib.sha256(flat.numpy().tobytes()).hexdigest()[:16]


def _build_fit_model(cell: str, cfg, transform: FoldTransform):
    """``cell`` 이름으로 학습할 모델을 만든다 — A–D 와 §6 구조 비교(NG·SG)가 같은 경로.

    구조 비교를 위해 두 번째 학습 루프를 만들지 않는다 (결정 14): best checkpoint,
    결정성, 최소 update 가드, 상한은 이 함수를 부르는 ``train_fold`` 가 그대로 적용한다.
    SG 의 graph 는 fold 변환이 training-rest 로 만든 것만 쓴다 — 없으면 실패한다.
    """
    import torch

    from .models import CELL_SPEC, COMPARATOR_SPEC, build_cell, build_comparator

    if cell in CELL_SPEC:
        brain = torch.as_tensor(transform.brain.templates, dtype=torch.float32)
        null = torch.as_tensor(transform.null.templates, dtype=torch.float32)
        return build_cell(cell, cfg, brain, null)
    if cell not in COMPARATOR_SPEC:
        raise FitError(f"알 수 없는 cell/구조 비교: {cell!r}. "
                       f"허용: {sorted(CELL_SPEC)} + {sorted(COMPARATOR_SPEC)}")
    if cell == "NG":
        return build_comparator("NG", cfg)
    if transform.single is None:
        raise FitError("SG fit 에는 fold 변환의 training-rest single average graph 가 "
                       "필요하다 — fit_fold_transform(..., single_graph=True) (결정 14)")
    graph = torch.as_tensor(transform.single.template, dtype=torch.float32)
    return build_comparator("SG", cfg, graph)


def train_fold(train_set: EncodedSet, eval_set: EncodedSet,
               transform: FoldTransform, *, cell: str, config_id: int,
               model_seed: int, fold: FoldSubjects, device: str = "cpu",
               max_epochs: int = MAX_EPOCHS, batch_size: int = BATCH_SIZE,
               patience: int = PATIENCE, min_delta: float = MIN_DELTA,
               grad_clip: float = GRAD_CLIP,
               early_stopping: Optional[bool] = None,
               epochs_exact: Optional[int] = None,
               min_updates: int = MIN_UPDATES) -> Tuple["FitResult", Any]:
    """한 fit 을 학습하고 평가 집합의 예측을 낸다.

    Returns:
        ``(FitResult, model)``. 모델은 호출자가 checkpoint 로 저장한다 — 저장
        경로를 이 함수가 정하지 않는다 (U20). inner fit(early stopping)은 best
        epoch 의 가중치를 복원한 뒤 평가 확률을 내고 그 모델을 돌려준다 — 마지막
        epoch 모델이 아니다 (계획서 §7 "selected best checkpoint", 결정 12 정정).
        outer/external fit 은 정확히 E epoch 뒤의 모델이다.

    Args:
        early_stopping: 기본값은 role 이 inner 일 때만 True. **outer fit 에서
            True 로 켤 수 없다** — outer test 로 멈추는 것이 되기 때문이다.
        epochs_exact: outer fit 에서 정확히 이 epoch 만큼 학습한다 (계획서 §7).
        min_updates: 보장할 최소 optimizer update 수 (계획서 §11 P8, 기본 1,500).
            inner fit 은 최소치 epoch 전에 멈추지 않고, outer fit 은 ``epochs_exact``
            가 최소치를 채우지 못하면 거부한다. 0 은 합성 시험 전용이다.

    Raises:
        FitError: outer fit 에 early stopping 을 요구하거나 epoch 수가 없을 때,
            또는 epoch 상한·공통 E 가 최소 update 를 채우지 못할 때 (P8).
        TrainError: 선택 점수의 출처가 inner validation 이 아닐 때 (T12).
    """
    import time

    import torch

    from .models import ModelConfig

    grid = {g.config_id: g for g in build_grid()}
    if config_id not in grid:
        raise FitError(f"config_id 는 0–7 이어야 한다: {config_id}")
    gc = grid[config_id]
    # 결정 14 3단계: 구조 비교(NG·SG) fit 은 잠긴 seed 42–44 만 받는다. A–D 는 CLI
    # (`cli.run_fit`) 가 같은 검사를 한다 — 라이브러리 A–D 경로는 pilot 측정 틀이
    # 쓰므로 바꾸지 않는다.
    if cell not in CELLS and int(model_seed) not in MODEL_SEEDS:
        raise FitError(f"구조 비교 {cell!r} 의 model_seed {model_seed} 는 잠긴 "
                       f"train.MODEL_SEEDS {MODEL_SEEDS} 밖이다 (계획서 §5, 결정 14)")

    is_inner = fold.role == ROLE_INNER
    if early_stopping is None:
        early_stopping = is_inner
    if early_stopping and not is_inner:
        raise FitError(
            f"{fold.role} fit 에 early stopping 을 켤 수 없다 — 평가 집합은 "
            f"{fold.eval_role} 이고 그것으로 멈추면 leakage 다 (계획서 §7)")
    if not is_inner and not epochs_exact:
        raise FitError("outer/external fit 은 공통 E 를 정확히 받아야 한다 (계획서 §7)")
    upe = updates_per_epoch(len(train_set), batch_size)
    min_epoch = min_epochs_for(len(train_set), batch_size=batch_size,
                               min_updates=min_updates)
    n_epochs_planned = int(epochs_exact) if epochs_exact else int(max_epochs)
    if n_epochs_planned > MAX_EPOCHS:
        raise FitError(f"epoch {n_epochs_planned} 이 상한 {MAX_EPOCHS} 를 넘는다 (P8)")
    if min_epoch > n_epochs_planned:
        raise FitError(
            f"최소 {min_updates} update 에 {min_epoch} epoch 이 필요한데 "
            f"{'공통 E' if epochs_exact else 'epoch 상한'} 이 {n_epochs_planned} 이다 "
            f"(학습 창 {len(train_set)}, update/epoch {upe}). 최소치·상한 조정은 "
            "main OOF 전에 pilot 측정으로만 한다 (계획서 §11 P8)")

    determinism = apply_determinism()
    dev = torch.device(device)
    torch.manual_seed(model_seed)
    cfg = ModelConfig(n_roi=int(train_set.x.shape[1]),
                      n_samples=int(train_set.x.shape[2]),
                      pca_dim=int(train_set.pca.shape[1]),
                      dropout=float(gc.dropout))
    model = _build_fit_model(cell, cfg, transform).to(dev)
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
            if len(val_losses) >= min_epoch:
                cur_best = early_stop_epoch(val_losses, patience=patience,
                                            min_delta=min_delta, min_epoch=min_epoch)
                if cur_best == len(val_losses):
                    # best 가 갱신된 epoch — 가중치를 깊은 복사로 보관 (RNG 소비 없음).
                    best_state = {k: v.detach().clone()
                                  for k, v in model.state_dict().items()}
                    best_state_epoch = cur_best
                if len(val_losses) - cur_best >= patience:
                    break
    elapsed = time.perf_counter() - t0

    if early_stopping:
        assert_no_test_leakage({f"epoch{i}": "inner_validation"
                                for i in range(len(val_losses))})
        best_epoch = early_stop_epoch(val_losses, patience=patience,
                                      min_delta=min_delta, min_epoch=min_epoch)
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

    return FitResult(
        role=fold.role, cell=cell, outer_fold=fold.outer_fold,
        inner_fold=fold.inner_fold, config_id=config_id, model_seed=model_seed,
        epochs_run=len(val_losses) if early_stopping else n_epochs,
        best_epoch=best_epoch, min_epoch=min_epoch, updates_per_epoch=upe,
        updates_run=upe * (len(val_losses) if early_stopping else n_epochs),
        val_losses=val_losses,
        eval_run_probs=run_probs, eval_window_probs=window_probs,
        eval_loss=subject_equal_loss(subject_run_true_probs(run_probs)),
        eval_balanced_accuracy=_balanced_accuracy_from_runs(run_probs),
        transform=transform.provenance(),
        timing={"train_seconds": elapsed,
                "seconds_per_epoch": elapsed / max(1, (len(val_losses) if early_stopping else n_epochs))},
        memory=memory, encoder_init_hash=enc_hash,
        rng_note=("encoder 는 cell 간 같은 seed 에서 동일 초기화다. gate 가 소비하는 "
                  "RNG 양이 달라 graph layer·head 이후는 cell 마다 다르다 — 계획서 §7"),
        determinism=determinism, eval_epoch=eval_epoch,
    ), model
