"""S 후보 기준선 — 재설계 프로토콜 v1.1 §6 "S 후보" 행.

이 판은 **S 후보 1·3 (logistic regression)**, **S 후보 2·4 (32-hidden MLP)** 와
네 후보 공통의 선택 규칙을 담는다. 선생님 결정 5 ("§6 S 후보 4 + 구조 비교 2 -
추천안 대로") 에 따라 구현·합성 시험까지만 하고, 실자료 실행은 main OOF 와 같은
release 에서 한다.

프로토콜이 규정한 것 (그대로 옮긴다):

* S 후보 1: raw ROI mean/variance (200 features) + logistic regression.
* S 후보 3: signed Fisher-z FC 4,950 + logistic regression.
  FC 는 `features.window_features` 와 **같은 함수** (Ledoit–Wolf, clip, arctanh).
* StandardScaler 는 해당 training task 창에만 fit 한다.
* logistic C ∈ {0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000}, L2·intercept 사용,
  solver 와 tolerance 는 고정.
* S 는 각 outer fold 에서 inner subject-equal log loss 가 가장 낮은 후보/설정으로
  고른다. 외부 S 도 PIOP1 main pool 의 inner 결과로만 고른다.
* **[개정 P11]** 미수렴 설정은 빼고 나머지 grid 에서 고르되, 뺀 설정 수를 보고한다
  (``SSelection.excluded``·``n_excluded``).

구현 선택 (프로토콜이 정하지 않은 값 — 결정이 아니다, 보고서에 명시):

* variance 는 ``ddof=0``. feature 순서는 ROI 0..99 mean 뒤 ROI 0..99 variance.
* solver ``lbfgs``, tol ``1e-4``, max_iter ``10000``, class_weight 없음.
  수렴 여부(``converged``)와 반복 수를 fit 기록에 남긴다.
* 모든 설정이 미수렴일 때 선택을 멈추는 것 (P11 이 정하지 않은 경우의 처리).
* 선택 동률(차이 ≤ ``train.TIE_TOLERANCE``)은 후보 순서(S1<S2<S3<S4), 그 다음
  설정 순서(C 오름차순)로 정한다. A–D 의 동률 규칙(공동 BA)과는 별개다.
* inner loss 는 A–D 와 같은 방식: inner fold 셋의 OOF run 확률을 모아
  subject 동일 가중 log loss (`train.subject_equal_loss`).

MLP (S 후보 2·4) — 프로토콜이 규정한 것:

* hidden 32. "MLP는 아래 8개 grid와 같은 예산이다" → §7 공통 grid config_id 0–7
  (lr × dropout × weight decay), AdamW·batch 32·cross-entropy·gradient clip 1.0,
  [개정 P8] 최소 update·상한 epoch·최소치 이후 early stopping, inner seed 42,
  subject-equal validation log loss·patience·min_delta, selected best checkpoint
  (결정 12 — inner 는 best epoch 가중치로 평가), outer 는 "해당 선택 모델의 3개
  inner best epochs 중앙값 올림" 만큼 정확히 학습 (`train.baseline_epochs`).
* 값은 모두 `train` 모듈 상수를 **호출 시점에** 참조한다 — 최소 update·상한이
  결정 12 로 바뀌어도 여기서 따로 고칠 값이 없다.

MLP 구현 선택 (결정이 아니다, 보고서에 명시):

* 은닉층 1개: ``Linear(d→32) → GELU → Dropout(p) → Linear(32→2)``. GELU 는 §6
  ROI encoder·gate 와 같은 활성화, dropout p 는 grid 값.
* 입력은 logistic 과 같은 StandardScaler (training 창에만 fit).
* 초기화는 ``torch.manual_seed(model_seed)`` 뒤 PyTorch 기본, 창 순서 shuffle 은
  ``model_seed`` 로 seed 한 CPU generator — `fitting.train_fold` 와 같은 방식.
* 수렴 개념이 없으므로 ``SEntry.converged`` 는 항상 True 다 (P11 은 logistic 규칙).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from . import features as F
from . import train as TR
from .train import TIE_TOLERANCE, subject_equal_loss

# sklearn 은 features.py 와 같은 이유로 지연 import 한다.

S1 = "S1_roi_mean_var_logreg"
S2 = "S2_roi_mean_var_mlp"
S3 = "S3_fc_fisher_z_logreg"
S4 = "S4_fc_fisher_z_mlp"
CANDIDATE_ORDER: Tuple[str, ...] = (S1, S2, S3, S4)

FEATURE_ROI_MEAN_VAR = "roi_mean_var"
FEATURE_FC_FISHER_Z = "fc_fisher_z"
CANDIDATE_FEATURE: Dict[str, str] = {
    S1: FEATURE_ROI_MEAN_VAR, S2: FEATURE_ROI_MEAN_VAR,
    S3: FEATURE_FC_FISHER_Z, S4: FEATURE_FC_FISHER_Z,
}
LOGISTIC_CANDIDATES: Tuple[str, ...] = (S1, S3)
MLP_CANDIDATES: Tuple[str, ...] = (S2, S4)
MLP_HIDDEN = 32

LOGISTIC_CS: Tuple[float, ...] = (0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
LOGISTIC_SOLVER = "lbfgs"
LOGISTIC_TOL = 1e-4
LOGISTIC_MAX_ITER = 10000


class BaselineError(RuntimeError):
    """S 후보 규칙 위반."""


# --------------------------------------------------------------------------- #
# feature
# --------------------------------------------------------------------------- #


def _check_window(window: np.ndarray) -> np.ndarray:
    arr = np.asarray(window, dtype=float)
    if arr.ndim != 2:
        raise BaselineError(f"window 는 2차원이어야 한다: {arr.shape}")
    if arr.shape[0] < 2 or arr.shape[1] < 2:
        raise BaselineError(f"window 가 너무 작다: {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise BaselineError("window 에 비유한값이 있다")
    return arr


def roi_mean_var(window: np.ndarray) -> np.ndarray:
    """``(n_samples, n_roi)`` → ROI mean ``n_roi`` 개 뒤 ROI variance(ddof=0) ``n_roi`` 개."""
    arr = _check_window(window)
    return np.concatenate([arr.mean(axis=0), arr.var(axis=0, ddof=0)])


def fc_fisher_z(window: np.ndarray) -> np.ndarray:
    """signed Fisher-z upper triangle. `features.window_features` 와 같은 함수다."""
    return F.window_features(_check_window(window))[1]


FEATURE_BUILDERS: Dict[str, Callable[[np.ndarray], np.ndarray]] = {
    FEATURE_ROI_MEAN_VAR: roi_mean_var,
    FEATURE_FC_FISHER_Z: fc_fisher_z,
}


def expected_dim(kind: str, n_roi: int = F.N_ROI_DEFAULT) -> int:
    """feature 차원. 100 ROI 면 200 / 4,950."""
    if kind == FEATURE_ROI_MEAN_VAR:
        return 2 * n_roi
    if kind == FEATURE_FC_FISHER_Z:
        return F.n_edges(n_roi)
    raise BaselineError(f"알 수 없는 feature 종류: {kind!r}")


def feature_matrix(windows: Sequence[np.ndarray], kind: str) -> np.ndarray:
    """창 목록 → ``(n_windows, dim)``. 창마다 ROI 수가 같아야 한다."""
    if kind not in FEATURE_BUILDERS:
        raise BaselineError(f"알 수 없는 feature 종류: {kind!r}")
    if not len(windows):
        raise BaselineError("창이 없다")
    n_roi = np.asarray(windows[0]).shape[-1]
    rows = [FEATURE_BUILDERS[kind](w) for w in windows]
    dim = expected_dim(kind, n_roi)
    for i, r in enumerate(rows):
        if r.shape != (dim,):
            raise BaselineError(f"창 {i} feature 차원 {r.shape} ≠ ({dim},)")
    return np.vstack(rows)


# --------------------------------------------------------------------------- #
# logistic regression (S 후보 1·3)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LogisticFit:
    """training task 창에 fit 한 StandardScaler + L2 logistic regression."""

    C: float
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    coef: np.ndarray
    intercept: float
    n_iter: int
    converged: bool
    n_train: int

    def predict_p1(self, X: np.ndarray) -> np.ndarray:
        """class 1 확률. 변환은 training 에서 고정한 scaler 로만 한다 (refit 없음)."""
        arr = np.asarray(X, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != self.coef.shape[0]:
            raise BaselineError(f"X 차원 {arr.shape} ≠ (n, {self.coef.shape[0]})")
        z = ((arr - self.scaler_mean) / self.scaler_scale) @ self.coef + self.intercept
        return 1.0 / (1.0 + np.exp(-z))

    def record(self) -> Dict[str, object]:
        return {"C": self.C, "solver": LOGISTIC_SOLVER, "tol": LOGISTIC_TOL,
                "max_iter": LOGISTIC_MAX_ITER, "n_iter": self.n_iter,
                "converged": self.converged, "n_train": self.n_train}


def fit_logistic(X_train: np.ndarray, y_train: Sequence[int], C: float) -> LogisticFit:
    """StandardScaler(training 창만) → L2 logistic regression(intercept).

    Raises:
        BaselineError: C 가 grid 밖, 라벨이 두 class 가 아님, 차원·유한성 위반.
    """
    if C not in LOGISTIC_CS:
        raise BaselineError(f"C={C} 는 프로토콜 grid {LOGISTIC_CS} 밖이다")
    X = np.asarray(X_train, dtype=float)
    y = np.asarray(y_train, dtype=int)
    if X.ndim != 2 or X.shape[0] != y.shape[0]:
        raise BaselineError(f"X {X.shape} 와 y {y.shape} 가 맞지 않는다")
    if not np.all(np.isfinite(X)):
        raise BaselineError("X 에 비유한값이 있다")
    if set(np.unique(y).tolist()) != {0, 1}:
        raise BaselineError(f"training 라벨이 두 class 가 아니다: {np.unique(y).tolist()}")

    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(X)
    model = LogisticRegression(C=C, l1_ratio=0.0, fit_intercept=True,
                               solver=LOGISTIC_SOLVER, tol=LOGISTIC_TOL,
                               max_iter=LOGISTIC_MAX_ITER)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(scaler.transform(X), y)
    n_iter = int(np.max(model.n_iter_))
    converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
    return LogisticFit(C=float(C), scaler_mean=scaler.mean_.copy(),
                       scaler_scale=scaler.scale_.copy(), coef=model.coef_[0].copy(),
                       intercept=float(model.intercept_[0]), n_iter=n_iter,
                       converged=converged and n_iter < LOGISTIC_MAX_ITER,
                       n_train=int(X.shape[0]))


def logistic_settings() -> List[Tuple[str, str, float]]:
    """(candidate, setting_id, C) 를 후보 순서·C 오름차순으로. setting_id 는 ``C=<값>``."""
    return [(cand, f"C={c:g}", c) for cand in LOGISTIC_CANDIDATES for c in LOGISTIC_CS]


# --------------------------------------------------------------------------- #
# MLP (S 후보 2·4)
# --------------------------------------------------------------------------- #

ROLE_INNER = "inner"
MLP_ROLES = ("inner", "outer", "external")


def mlp_settings() -> List[Tuple[str, str, int]]:
    """(candidate, setting_id, config_id) — 후보 순서(S2, S4) · config_id 0–7.

    setting_id 는 ``config=<id>``, 선택 시 setting_rank 는 config_id 다.
    """
    return [(cand, f"config={g.config_id}", g.config_id)
            for cand in MLP_CANDIDATES for g in TR.build_grid()]


def build_mlp(n_features: int, dropout: float):
    """``Linear(d→32) → GELU → Dropout(p) → Linear(32→2)``."""
    import torch.nn as nn

    if n_features < 1:
        raise BaselineError(f"feature 차원이 없다: {n_features}")
    return nn.Sequential(nn.Linear(int(n_features), MLP_HIDDEN), nn.GELU(),
                         nn.Dropout(float(dropout)), nn.Linear(MLP_HIDDEN, 2))


def mlp_param_hash(model) -> str:
    """parameter 이름순 연결의 sha256 앞 16자."""
    import hashlib

    import torch

    with torch.no_grad():
        flat = torch.cat([p.detach().reshape(-1).cpu()
                          for _, p in sorted(model.named_parameters())])
    return hashlib.sha256(flat.numpy().tobytes()).hexdigest()[:16]


def _run_probs(run_keys: Sequence[str], p1: np.ndarray) -> Dict[str, float]:
    """창 확률 → run 확률. `fitting.run_probabilities` 를 그대로 쓴다 (run 당 창 4개)."""
    from .fitting import run_probabilities

    return run_probabilities([SimpleNamespace(run_key=k) for k in run_keys], p1)


def _mlp_forward_p1(model, X, *, batch_size: int) -> np.ndarray:
    """class 1 확률. eval 모드·no_grad 라 RNG 를 소비하지 않는다."""
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, X.shape[0], batch_size):
            out.append(torch.softmax(model(X[s:s + batch_size]), dim=-1)[:, 1]
                       .cpu().numpy())
    return np.concatenate(out) if out else np.zeros(0)


@dataclass
class MLPFit:
    """MLP 한 fit 의 결과. 예측은 평가 집합에 대한 것이다."""

    role: str
    config_id: int
    model_seed: int
    n_train: int
    n_features: int
    epochs_run: int
    best_epoch: int
    eval_epoch: int
    min_epoch: int
    updates_per_epoch: int
    updates_run: int
    val_losses: List[float]
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    eval_window_p1: np.ndarray
    eval_run_probs: Dict[str, float]
    eval_loss: float
    determinism: Dict[str, Any]
    #: 학습 전 초기 parameter 의 sha256 앞 16자 (seed 재현 확인용).
    init_hash: str = ""

    def record(self) -> Dict[str, object]:
        return {"role": self.role, "config_id": self.config_id, "init_hash": self.init_hash,
                "model_seed": self.model_seed, "hidden": MLP_HIDDEN,
                "n_train": self.n_train, "n_features": self.n_features,
                "epochs_run": self.epochs_run, "best_epoch": self.best_epoch,
                "eval_epoch": self.eval_epoch, "min_epoch": self.min_epoch,
                "updates_per_epoch": self.updates_per_epoch,
                "updates_run": self.updates_run, "eval_loss": self.eval_loss,
                "converged": True}


def fit_mlp(X_train: np.ndarray, y_train: Sequence[int], X_eval: np.ndarray,
            eval_run_keys: Sequence[str], *, role: str, config_id: int,
            model_seed: int, epochs_exact: Optional[int] = None,
            max_epochs: Optional[int] = None, min_updates: Optional[int] = None,
            device: str = "cpu") -> Tuple[MLPFit, Any]:
    """StandardScaler(training 창만) → 32-hidden MLP. 학습 규칙은 `fitting.train_fold` 와 같다.

    * inner: 최소 epoch 전에는 멈추지 않고, 그 뒤 subject-equal validation log loss 로
      early stopping 한다. best 가 갱신될 때마다 가중치를 보관하고 끝나면 best 가중치를
      복원한 뒤 평가 확률을 낸다 (결정 12).
    * outer/external: early stopping 없이 정확히 ``epochs_exact`` epoch.

    batch·patience·min_delta·gradient clip 은 `train` 상수만 쓴다 (인자로 바꿀 수 없다).
    ``max_epochs``·``min_updates`` 의 기본은 **호출 시점의** `train.MAX_EPOCHS`·
    `train.MIN_UPDATES` 다. ``min_updates=0`` 은 합성 시험 전용이다.

    Returns:
        ``(MLPFit, model)``.

    Raises:
        BaselineError: role·config·차원·라벨 위반, outer 에 epoch 수가 없음,
            epoch 가 상한을 넘거나 최소 update 를 채우지 못함 (P8), best checkpoint
            불일치.
    """
    import torch

    from .fitting import apply_determinism, subject_run_true_probs

    if role not in MLP_ROLES:
        raise BaselineError(f"role 은 {MLP_ROLES} 중 하나여야 한다: {role!r}")
    # 결정 14 3단계: seed 42–44 제약을 fit_mlp 에도 (호출 시점 train 상수).
    if int(model_seed) not in tuple(int(s) for s in TR.MODEL_SEEDS):
        raise BaselineError(f"model_seed {model_seed} 는 잠긴 train.MODEL_SEEDS "
                            f"{tuple(TR.MODEL_SEEDS)} 밖이다 (계획서 §5)")
    grid = {g.config_id: g for g in TR.build_grid()}
    if config_id not in grid:
        raise BaselineError(f"config_id 는 0–7 이어야 한다: {config_id}")
    gc = grid[config_id]
    X = np.asarray(X_train, dtype=float)
    y = np.asarray(y_train, dtype=int)
    Xe = np.asarray(X_eval, dtype=float)
    if X.ndim != 2 or X.shape[0] != y.shape[0]:
        raise BaselineError(f"X {X.shape} 와 y {y.shape} 가 맞지 않는다")
    if Xe.ndim != 2 or Xe.shape[1] != X.shape[1] or Xe.shape[0] != len(eval_run_keys):
        raise BaselineError(f"X_eval {Xe.shape} 가 X {X.shape}·run key "
                            f"{len(eval_run_keys)} 와 맞지 않는다")
    if not (np.all(np.isfinite(X)) and np.all(np.isfinite(Xe))):
        raise BaselineError("X 에 비유한값이 있다")
    if set(np.unique(y).tolist()) != {0, 1}:
        raise BaselineError(f"training 라벨이 두 class 가 아니다: {np.unique(y).tolist()}")

    is_inner = role == ROLE_INNER
    if is_inner and epochs_exact is not None:
        raise BaselineError("inner fit 은 epochs_exact 를 받지 않는다 — early stopping 이다")
    if not is_inner and not epochs_exact:
        raise BaselineError(
            "outer/external fit 은 inner best epochs 중앙값 올림을 정확히 받아야 한다 "
            "(계획서 §7, `train.baseline_epochs`)")
    batch_size = TR.BATCH_SIZE
    mu = TR.MIN_UPDATES if min_updates is None else int(min_updates)
    cap = TR.MAX_EPOCHS if max_epochs is None else int(max_epochs)
    upe = TR.updates_per_epoch(X.shape[0], batch_size)
    min_epoch = TR.min_epochs_for(X.shape[0], batch_size=batch_size, min_updates=mu)
    n_epochs = int(epochs_exact) if epochs_exact else cap
    if n_epochs > TR.MAX_EPOCHS:
        raise BaselineError(f"epoch {n_epochs} 이 상한 {TR.MAX_EPOCHS} 를 넘는다 (P8)")
    if min_epoch > n_epochs:
        raise BaselineError(
            f"최소 {mu} update 에 {min_epoch} epoch 이 필요한데 "
            f"{'epochs_exact' if epochs_exact else 'epoch 상한'} 이 {n_epochs} 이다 "
            f"(학습 창 {X.shape[0]}, update/epoch {upe}) (계획서 §11 P8)")

    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(X)
    determinism = apply_determinism()
    dev = torch.device(device)
    torch.manual_seed(model_seed)
    model = build_mlp(X.shape[1], gc.dropout).to(dev)
    init_hash = mlp_param_hash(model)
    opt = torch.optim.AdamW(model.parameters(), lr=gc.learning_rate,
                            weight_decay=gc.weight_decay)
    lossf = torch.nn.CrossEntropyLoss()
    xt = torch.as_tensor(scaler.transform(X), dtype=torch.float32).to(dev)
    yt = torch.as_tensor(y, dtype=torch.int64).to(dev)
    xe = torch.as_tensor(scaler.transform(Xe), dtype=torch.float32).to(dev)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(model_seed)

    def val_loss() -> float:
        rp = _run_probs(eval_run_keys, _mlp_forward_p1(model, xe, batch_size=batch_size))
        return subject_equal_loss(subject_run_true_probs(rp))

    val_losses: List[float] = []
    best_state: Optional[Dict[str, Any]] = None
    best_state_epoch = 0
    for _ in range(n_epochs):
        model.train()
        order = torch.randperm(X.shape[0], generator=gen).to(dev)
        for s in range(0, X.shape[0], batch_size):
            idx = order[s:s + batch_size]
            opt.zero_grad(set_to_none=True)
            loss = lossf(model(xt[idx]), yt[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), TR.GRAD_CLIP)
            opt.step()
        if is_inner:
            val_losses.append(val_loss())
            if len(val_losses) >= min_epoch:
                cur = TR.early_stop_epoch(val_losses, patience=TR.PATIENCE,
                                          min_delta=TR.MIN_DELTA, min_epoch=min_epoch)
                if cur == len(val_losses):
                    best_state = {k: v.detach().clone()
                                  for k, v in model.state_dict().items()}
                    best_state_epoch = cur
                if len(val_losses) - cur >= TR.PATIENCE:
                    break

    if is_inner:
        TR.assert_no_test_leakage({f"epoch{i}": "inner_validation"
                                   for i in range(len(val_losses))})
        best_epoch = TR.early_stop_epoch(val_losses, patience=TR.PATIENCE,
                                         min_delta=TR.MIN_DELTA, min_epoch=min_epoch)
        if best_state is None or best_state_epoch != best_epoch:
            raise BaselineError(f"best checkpoint 불일치: 보관 epoch {best_state_epoch}, "
                                f"best epoch {best_epoch} (결정 12)")
        if best_epoch != len(val_losses):
            model.load_state_dict(best_state)
        epochs_run = len(val_losses)
    else:
        best_epoch = epochs_run = n_epochs

    p1 = _mlp_forward_p1(model, xe, batch_size=batch_size)
    run_probs = _run_probs(eval_run_keys, p1)
    return MLPFit(
        role=role, config_id=config_id, model_seed=model_seed, n_train=int(X.shape[0]),
        n_features=int(X.shape[1]), epochs_run=epochs_run, best_epoch=best_epoch,
        eval_epoch=best_epoch, min_epoch=min_epoch, updates_per_epoch=upe,
        updates_run=upe * epochs_run, val_losses=val_losses,
        scaler_mean=scaler.mean_.copy(), scaler_scale=scaler.scale_.copy(),
        eval_window_p1=p1, eval_run_probs=run_probs,
        eval_loss=subject_equal_loss(subject_run_true_probs(run_probs)),
        determinism=determinism, init_hash=init_hash,
    ), model


# --------------------------------------------------------------------------- #
# 선택 (S 후보 1–4 공통)
# --------------------------------------------------------------------------- #


def merge_inner_oof(fold_run_probs: Sequence[Mapping[str, float]]) -> Dict[str, float]:
    """inner fold 별 validation run 확률을 OOF 하나로 합친다. run 이 겹치면 실패한다."""
    if not fold_run_probs:
        raise BaselineError("inner fold 가 없다")
    out: Dict[str, float] = {}
    for i, probs in enumerate(fold_run_probs):
        dup = sorted(set(out) & set(probs))
        if dup:
            raise BaselineError(f"inner fold {i} 의 run 이 다른 fold 와 겹친다: {dup[:3]}")
        out.update({k: float(v) for k, v in probs.items()})
    return out


def inner_loss(oof_run_probs: Mapping[str, float]) -> float:
    """OOF run 확률 → subject 동일 가중 log loss (A–D 와 같은 함수)."""
    from .fitting import subject_run_true_probs

    return subject_equal_loss(subject_run_true_probs(oof_run_probs))


@dataclass(frozen=True)
class SEntry:
    """한 outer fold 의 후보/설정 하나의 inner OOF 결과."""

    candidate: str
    setting_id: str
    setting_rank: int
    oof_run_probs: Mapping[str, float]
    converged: bool = True


@dataclass(frozen=True)
class SSelection:
    candidate: str
    setting_id: str
    loss: float
    table: Tuple[Dict[str, object], ...]
    excluded: Tuple[str, ...] = ()
    n_excluded: int = 0


def select_s(entries: Sequence[SEntry]) -> SSelection:
    """inner subject-equal log loss 가 가장 낮은 후보/설정을 고른다.

    미수렴 설정(``converged=False``)은 후보에서 빼고 나머지에서 고른다 (계획서 §11
    P11). 뺀 설정은 ``excluded`` 에 ``"<candidate>/<setting_id>"`` 로, 그 수는
    ``n_excluded`` 에 남는다. ``table`` 에는 뺀 설정도 ``converged`` 와 함께 남는다.

    Raises:
        BaselineError: 빈 입력, 알 수 없는 후보, 중복, OOF run 집합 불일치,
            모든 설정이 미수렴일 때.
    """
    if not entries:
        raise BaselineError("선택할 후보가 없다")
    keys = [(e.candidate, e.setting_id) for e in entries]
    unknown = sorted({e.candidate for e in entries} - set(CANDIDATE_ORDER))
    if unknown:
        raise BaselineError(f"알 수 없는 후보: {unknown}")
    if len(set(keys)) != len(keys):
        raise BaselineError("후보/설정이 중복되었다")
    runs0 = set(entries[0].oof_run_probs)
    for e in entries[1:]:
        if set(e.oof_run_probs) != runs0:
            raise BaselineError(
                f"{e.candidate}/{e.setting_id} 의 OOF run 집합이 다르다 — 같은 inner "
                "모집단에서 비교해야 한다")
    excluded = tuple(f"{e.candidate}/{e.setting_id}" for e in entries if not e.converged)
    usable = [e for e in entries if e.converged]
    if not usable:
        raise BaselineError(
            f"모든 설정 {len(entries)}개가 미수렴이다 — 고를 설정이 없다: {list(excluded)[:5]}")

    scored = [(inner_loss(e.oof_run_probs), e) for e in entries]
    best = min(s for s, e in scored if e.converged)
    tied = [(s, e) for s, e in scored if e.converged and s - best <= TIE_TOLERANCE]
    s_sel, e_sel = min(tied, key=lambda t: (CANDIDATE_ORDER.index(t[1].candidate),
                                            t[1].setting_rank))
    table = tuple({"candidate": e.candidate, "setting_id": e.setting_id,
                   "setting_rank": e.setting_rank, "inner_loss": s,
                   "converged": e.converged}
                  for s, e in scored)
    return SSelection(candidate=e_sel.candidate, setting_id=e_sel.setting_id,
                      loss=float(s_sel), table=table, excluded=excluded,
                      n_excluded=len(excluded))


# --------------------------------------------------------------------------- #
# §6 구조 비교 2종 (NG·SG) — 구조별 독립 선택 (결정 14 3단계)
# --------------------------------------------------------------------------- #

#: 구조 비교 이름. `models.COMPARATOR_SPEC` 의 키와 같아야 한다 (시험이 고정).
COMPARATOR_ORDER: Tuple[str, ...] = ("NG", "SG")
#: 구조 비교 inner fold 수. outer E 는 `train.baseline_epochs` (3개 중앙값 올림) 다.
COMPARATOR_INNER_FOLDS = 3


@dataclass(frozen=True)
class ComparatorInner:
    """한 구조·config·inner fold 의 inner validation 결과 (`train_fold` inner fit 한 개)."""

    structure: str
    config_id: int
    inner_fold: int
    model_seed: int
    run_probs: Mapping[str, float]
    best_epoch: int


@dataclass(frozen=True)
class ComparatorSelection:
    """한 구조의 선택 결과와 outer fit 계획."""

    structure: str
    config_id: int
    outer_epochs: int
    loss: float
    balanced_accuracy: float
    tie_rule: str
    best_epochs: Tuple[int, ...]
    table: Tuple[Dict[str, object], ...]

    def outer_plan(self) -> List[Dict[str, object]]:
        """outer fit 계획: 선택 config, 정확히 ``outer_epochs``, seed 42–44 (계획서 §5·§7)."""
        return [{"structure": self.structure, "config_id": self.config_id,
                 "model_seed": int(s), "epochs_exact": self.outer_epochs}
                for s in TR.MODEL_SEEDS]


def select_comparator(results: Sequence[ComparatorInner], *,
                      structure: str) -> ComparatorSelection:
    """구조 비교 하나(NG 또는 SG)가 8개 config 중 하나를 **독립으로** 고른다 (결정 14 (가)).

    규칙 (구현 선택 — 결정 14 가 세부를 정하지 않았다. 계획서 §7 A–D 문장에 가장
    가까운 형태로 따른다):

    * 선택 손실 = config 별 3 inner fold validation run 확률을 OOF 하나로 합친 뒤
      subject 동일 가중 log loss (`inner_loss`, S 후보·계획서 §7 "inner OOF run loss를
      subject별 동일 가중으로 합산" 과 같은 함수). cell 가중은 없다 — 구조 하나다.
    * 동률(차이 ≤ ``train.TIE_TOLERANCE``) → OOF BA 가 높은 것 → config_id 가 작은 것.
    * outer E = 선택 config 의 3 inner best epoch 중앙값 올림 (`train.baseline_epochs`,
      계획서 §7 baseline 규칙).
    * inner fit 은 모두 ``train.INNER_SEED`` (계획서 §7 "Inner seed=42").

    Raises:
        BaselineError: 알 수 없는 구조, 다른 구조가 섞임, grid 불완전·중복·여분,
            inner seed 위반, fold 간 run 겹침, config 간 OOF run 집합 불일치,
            best epoch 가 1–상한 밖, outer E 가 상한을 넘을 때.
    """
    from .fitting import _balanced_accuracy_from_runs

    if structure not in COMPARATOR_ORDER:
        raise BaselineError(f"알 수 없는 구조 비교: {structure!r}. 허용: {COMPARATOR_ORDER}")
    if not results:
        raise BaselineError(f"{structure}: 선택할 inner 결과가 없다")
    other = sorted({r.structure for r in results} - {structure})
    if other:
        raise BaselineError(f"{structure} 선택에 다른 구조가 섞였다: {other} — 구조별 독립 선택")
    bad_seed = sorted({int(r.model_seed) for r in results} - {int(TR.INNER_SEED)})
    if bad_seed:
        raise BaselineError(f"{structure}: inner seed 는 {TR.INNER_SEED} 여야 한다: {bad_seed} "
                            "(계획서 §7)")
    grid_ids = [g.config_id for g in TR.build_grid()]
    need = {(c, f) for c in grid_ids for f in range(COMPARATOR_INNER_FOLDS)}
    keys = [(int(r.config_id), int(r.inner_fold)) for r in results]
    if len(set(keys)) != len(keys):
        raise BaselineError(f"{structure}: (config, inner fold) 가 중복되었다")
    missing, extra = sorted(need - set(keys)), sorted(set(keys) - need)
    if missing:
        raise BaselineError(f"{structure}: 불완전한 grid — {len(missing)}개 누락 "
                            f"(예: {missing[:3]}). 불완전 grid 를 정상 선택으로 처리하지 않는다")
    if extra:
        raise BaselineError(f"{structure}: 예상 밖 조합: {extra[:3]}")
    for r in results:
        if not 1 <= int(r.best_epoch) <= TR.MAX_EPOCHS:
            raise BaselineError(f"{structure}: best_epoch 가 1–{TR.MAX_EPOCHS} 밖이다: "
                                f"config {r.config_id} fold {r.inner_fold} {r.best_epoch}")

    per: Dict[int, Dict[str, object]] = {}
    runs0: Optional[set] = None
    for cid in grid_ids:
        rows = sorted((r for r in results if int(r.config_id) == cid),
                      key=lambda r: int(r.inner_fold))
        oof = merge_inner_oof([r.run_probs for r in rows])
        if runs0 is None:
            runs0 = set(oof)
        elif set(oof) != runs0:
            raise BaselineError(f"{structure}: config {cid} 의 OOF run 집합이 다르다 — "
                                "같은 inner 모집단에서 비교해야 한다")
        per[cid] = {"config_id": cid, "inner_loss": inner_loss(oof),
                    "inner_ba": _balanced_accuracy_from_runs(oof),
                    "best_epochs": tuple(int(r.best_epoch) for r in rows)}

    best = min(float(v["inner_loss"]) for v in per.values())
    tied = [c for c in grid_ids if float(per[c]["inner_loss"]) - best <= TIE_TOLERANCE]
    tie_rule = "unique minimum"
    if len(tied) > 1:
        best_ba = max(float(per[c]["inner_ba"]) for c in tied)
        tied = [c for c in tied if float(per[c]["inner_ba"]) >= best_ba - TIE_TOLERANCE]
        tie_rule = ("tie broken by BA" if len(tied) == 1
                    else "tie broken by BA then smallest config_id")
    chosen = min(tied)
    epochs = per[chosen]["best_epochs"]
    outer_e = TR.baseline_epochs(list(epochs))
    if not 1 <= outer_e <= TR.MAX_EPOCHS:
        raise BaselineError(f"{structure}: outer E {outer_e} 가 1–{TR.MAX_EPOCHS} 밖이다")
    return ComparatorSelection(
        structure=structure, config_id=chosen, outer_epochs=outer_e,
        loss=float(per[chosen]["inner_loss"]),
        balanced_accuracy=float(per[chosen]["inner_ba"]), tie_rule=tie_rule,
        best_epochs=tuple(epochs), table=tuple(per[c] for c in grid_ids))
