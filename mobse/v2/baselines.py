"""S 후보 기준선 — 재설계 프로토콜 v1.1 §6 "S 후보" 행.

이 판은 **S 후보 1·3 (logistic regression)** 과 네 후보 공통의 선택 규칙을 담는다.
S 후보 2·4 (32-hidden MLP) 는 같은 feature 함수와 선택 규칙을 쓰며 다음 단위에서
추가한다. 선생님 결정 5 ("§6 S 후보 4 + 구조 비교 2 - 추천안 대로") 에 따라
구현·합성 시험까지만 하고, 실자료 실행은 main OOF 와 같은 release 에서 한다.

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
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from . import features as F
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
