"""WI-02 재추출 — nuisance 설계, ROI 시계열, 창 절단.

원자료(fMRIPrep derivative)를 읽는 부분은 얇게 두고, **검증 가능한 계산을 전부
순수 함수로** 분리했다. 합성 fixture 로 시험할 수 있어야 Wave 2 가 끝나기 전에
정확성을 확인할 수 있기 때문이다.

계획서 §3.2 가 요구하는 nuisance 구성:
    24 motion  = {trans,rot}_{x,y,z} 와 그 derivative1, 각각의 power2
    aCompCor 5 = WM/CSF 유래 성분을 metadata 의 설명분산 내림차순으로 5개
    spike      = 원본 frame 의 FD > 0.5 mm 마다 1개 (one-hot)
    상수/추세  = intercept + linear drift (중복 drift 를 넣어 rank 를 올리지 않는다)

frame 을 삭제해 이어 붙이지 않는다. spike 는 regressor 로만 처리한다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from mobse.v2.preprocess import (
    ANALYSIS_END,
    ANALYSIS_START,
    MIN_RESIDUAL_DOF,
    PreprocessError,
)

__all__ = [
    "ExtractError",
    "ExtractDataError",
    "MOTION_BASE",
    "motion_column_names",
    "BANDPASS_LOW_HZ",
    "BANDPASS_HIGH_HZ",
    "ACOMPCOR_MASKS",
    "N_ACOMPCOR",
    "select_acompcor",
    "spike_regressors",
    "build_design",
    "design_rank",
    "filter_degrees_of_freedom",
    "residual_degrees_of_freedom",
    "regress_out",
    "zscore_rois",
    "DesignReport",
]


class ExtractError(RuntimeError):
    """재추출 전제가 깨졌다. 조용한 대체 없이 실패시킨다.

    **구조적** 실패에 쓴다 — 형상 불일치, parcel 결손, 파일 손상처럼 "무언가
    잘못됐다"는 뜻이다. 이런 건 고쳐야 할 결함이다.
    """


class ExtractDataError(ExtractError):
    """계획서가 **미리 정해 둔** 자료 조건이라 이 run 을 제외한다.

    aCompCor 5개가 없다거나 constant ROI 가 있다거나 하는 경우다. 계획서 §3.2 가
    "선택 정의에 맞는 5개가 없으면 임의 다른 열로 대체하지 않는다"고 못박은
    상황이며, **결함이 아니라 예상된 제외 사유**다.

    구조적 실패(`ExtractError`)와 나누는 이유는 하나다 — 둘을 같은 'error' 로
    묶으면 진짜 고장이 정상적인 제외 건수에 묻힌다. 실제로 PIOP1 workingmemory
    전량 추출에서 error 3건 중 2건이 이 부류였고 1건만 진짜 I/O 오류였다.
    """


#: 24 motion regressor 의 기본 6축.
MOTION_BASE: Tuple[str, ...] = ("trans_x", "trans_y", "trans_z",
                                "rot_x", "rot_y", "rot_z")

#: 계획서 §3.2 의 주 band-pass.
BANDPASS_LOW_HZ = 0.008
BANDPASS_HIGH_HZ = 0.100

#: aCompCor 를 고를 mask. 계획서의 "WM/CSF noise 영역에서 유래한" 에 해당한다.
#: fMRIPrep 은 combined(WM+CSF), WM, CSF 세 가지를 낸다.
ACOMPCOR_MASKS: Tuple[str, ...] = ("combined",)
N_ACOMPCOR = 5

#: FD spike 판정 (계획서 §3.2).
FD_SPIKE_MM = 0.5


def motion_column_names() -> List[str]:
    """24 motion regressor 의 열 이름을 고정 순서로 만든다.

    Returns:
        길이 24 의 이름 목록. 순서는 축 → (원값, derivative1, power2,
        derivative1_power2) 이며, 이 순서가 design 열 순서이자 manifest 기록 순서다.
    """
    names: List[str] = []
    for base in MOTION_BASE:
        names.extend([base, f"{base}_derivative1", f"{base}_power2",
                      f"{base}_derivative1_power2"])
    return names


def select_acompcor(metadata: Mapping[str, Mapping[str, Any]],
                    *, masks: Sequence[str] = ACOMPCOR_MASKS,
                    n: int = N_ACOMPCOR) -> List[str]:
    """aCompCor 성분을 설명분산 내림차순으로 n개 고른다.

    Args:
        metadata: confounds sidecar JSON (열 이름 -> 속성).
        masks: 허용 mask 이름.
        n: 고를 개수.

    Returns:
        선택된 열 이름 n개. 동률은 열 이름 오름차순으로 깬다 — 순서가 실행마다
        달라지면 fit 해시가 흔들린다.

    Raises:
        ExtractError: 조건을 만족하는 성분이 n개 미만일 때. 계획서가 "임의 다른
            열로 대체하지 않는다"고 못박았으므로 여기서 실패시킨다.
    """
    allowed = set(masks)
    candidates: List[Tuple[float, str]] = []
    for name, attrs in metadata.items():
        if not name.startswith("a_comp_cor"):
            continue
        if attrs.get("Mask") not in allowed:
            continue
        if attrs.get("Retained") is not True:
            continue
        explained = attrs.get("VarianceExplained")
        if explained is None:
            raise ExtractDataError(
                f"{name}: VarianceExplained 가 없다. 설명분산 순서를 정할 수 없으므로 "
                "임의 순서로 진행하지 않는다")
        candidates.append((float(explained), name))

    if len(candidates) < n:
        raise ExtractDataError(
            f"mask {sorted(allowed)} 의 Retained aCompCor 가 {len(candidates)}개뿐이다 "
            f"(필요 {n}). 다른 열로 대체하지 않는다 — 계획서 §3.2")

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [name for _explained, name in candidates[:n]]


def spike_regressors(fd: Sequence[float], *, threshold: float = FD_SPIKE_MM
                     ) -> Tuple[np.ndarray, List[int]]:
    """FD > threshold 인 원본 frame 마다 one-hot regressor 를 만든다.

    첫 frame 의 FD 는 구조적으로 결측이며(미분 정의상) spike 로 치지 않는다.
    그 외 결측은 실패다 — 계획서 §3.2.

    Args:
        fd: 원본 frame 단위 framewise displacement. 첫 값은 NaN 일 수 있다.
        threshold: spike 판정 임계 (mm).

    Returns:
        (design_block, spike_frame_indices). design_block 형상은
        (n_frames, n_spikes) 이며 spike 가 없으면 (n_frames, 0).

    Raises:
        ExtractError: 첫 frame 이 아닌 곳에 결측이 있을 때.
    """
    values = np.asarray(fd, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ExtractError(f"FD 배열 형상이 잘못됐다: {values.shape}")
    missing = np.flatnonzero(~np.isfinite(values))
    stray = [int(i) for i in missing if i != 0]
    if stray:
        raise ExtractDataError(
            f"첫 frame 이 아닌 곳에 FD 결측이 있다: frame {stray[:10]} "
            "(구조적 결측은 첫 frame 만 허용)")

    flagged = [int(i) for i in np.flatnonzero(np.isfinite(values) & (values > threshold))]
    block = np.zeros((values.size, len(flagged)), dtype=float)
    for col, frame in enumerate(flagged):
        block[frame, col] = 1.0
    return block, flagged


def build_design(confounds: Mapping[str, Sequence[float]],
                 *, acompcor_names: Sequence[str],
                 n_frames: int) -> Tuple[np.ndarray, List[str]]:
    """nuisance 설계행렬을 만든다.

    열 순서: 24 motion → aCompCor 5 → spike* → intercept → linear drift.
    drift 는 하나만 넣는다 — filter 와 중복해 rank 를 올리지 않기 위해서다.

    Args:
        confounds: 열 이름 -> 값. 결측은 0 으로 채우지 **않는다**.
        acompcor_names: `select_acompcor` 가 고른 이름.
        n_frames: 원본 frame 수.

    Returns:
        (design, column_names). design 형상은 (n_frames, n_columns).

    Raises:
        ExtractError: 필요한 열이 없거나 길이가 다르거나 결측이 있을 때.
    """
    columns: List[np.ndarray] = []
    names: List[str] = []

    required = motion_column_names() + list(acompcor_names)
    missing = [c for c in required if c not in confounds]
    if missing:
        raise ExtractError(f"confounds 에 없는 열: {missing}")

    for name in required:
        values = np.asarray(confounds[name], dtype=float)
        if values.size != n_frames:
            raise ExtractError(
                f"{name}: 길이 {values.size} != frame 수 {n_frames}")
        if not np.all(np.isfinite(values)):
            bad = int(np.sum(~np.isfinite(values)))
            if name.endswith("derivative1") or name.endswith("derivative1_power2"):
                # 미분 첫 행의 구조적 결측만 0 으로 정의한다. 그 외는 실패.
                if not np.isfinite(values[0]) and np.all(np.isfinite(values[1:])):
                    values = values.copy()
                    values[0] = 0.0
                else:
                    raise ExtractError(f"{name}: 결측 {bad}개 (첫 행 외)")
            else:
                raise ExtractError(f"{name}: 결측 {bad}개")
        columns.append(values)
        names.append(name)

    fd = confounds.get("framewise_displacement")
    if fd is None:
        raise ExtractError("framewise_displacement 열이 없다 — spike 를 만들 수 없다")
    block, flagged = spike_regressors(fd)
    for col, frame in enumerate(flagged):
        columns.append(block[:, col])
        names.append(f"spike_frame_{frame:04d}")

    columns.append(np.ones(n_frames, dtype=float))
    names.append("intercept")
    drift = np.linspace(-1.0, 1.0, n_frames)
    columns.append(drift)
    names.append("linear_drift")

    return np.column_stack(columns), names


def design_rank(design: np.ndarray) -> int:
    """설계행렬의 수치적 rank."""
    if design.ndim != 2:
        raise ExtractError(f"design 은 2차원이어야 한다: {design.shape}")
    return int(np.linalg.matrix_rank(design))


def filter_degrees_of_freedom(t_run_sec: float,
                              *, low_hz: float = BANDPASS_LOW_HZ,
                              high_hz: float = BANDPASS_HIGH_HZ) -> int:
    """band-pass 가 남기는 실수 자유도 (개정 P6-b 의 둘째 항).

    통과대역에 남는 주파수마다 sin/cos 2개의 자유도가 있다.
    """
    if t_run_sec <= 0:
        raise ExtractError(f"run 길이가 0 이하다: {t_run_sec}")
    if not 0 <= low_hz < high_hz:
        raise ExtractError(f"통과대역이 잘못됐다: [{low_hz}, {high_hz}]")
    return int(math.floor(2 * (high_hz - low_hz) * t_run_sec))


def residual_degrees_of_freedom(n_frames: int, rank: int, t_run_sec: float) -> int:
    """개정 P6-b 로 동결한 residual DOF.

        min( n_frames - rank, floor(2*(f_high-f_low)*T_run) )

    filter 로 잃는 자유도를 세지 않으면 residual DOF 를 과대 보고한다.
    """
    return min(n_frames - rank, filter_degrees_of_freedom(t_run_sec))


def regress_out(data: np.ndarray, design: np.ndarray) -> np.ndarray:
    """최소제곱 잔차를 돌려준다.

    Args:
        data: (n_frames, n_roi).
        design: (n_frames, n_columns).

    Returns:
        (n_frames, n_roi) 잔차.

    Raises:
        ExtractError: 형상 불일치 또는 비유한값.
    """
    if data.ndim != 2 or design.ndim != 2:
        raise ExtractError(f"형상 오류: data {data.shape}, design {design.shape}")
    if data.shape[0] != design.shape[0]:
        raise ExtractError(
            f"frame 수 불일치: data {data.shape[0]} vs design {design.shape[0]}")
    if not np.all(np.isfinite(data)) or not np.all(np.isfinite(design)):
        raise ExtractError("data 또는 design 에 비유한값이 있다")
    beta, *_ = np.linalg.lstsq(design, data, rcond=None)
    return data - design @ beta


def zscore_rois(data: np.ndarray) -> np.ndarray:
    """run 내 ROI별 z-score (계획서 §3.2).

    Raises:
        ExtractError: 표준편차가 0 인 ROI 가 있으면 (constant ROI 는 제외 사유다).
    """
    if data.ndim != 2:
        raise ExtractError(f"data 는 2차원이어야 한다: {data.shape}")
    std = data.std(axis=0, ddof=0)
    dead = np.flatnonzero(std <= 0)
    if dead.size:
        raise ExtractDataError(
            f"표준편차 0 인 ROI {dead.tolist()[:10]} — constant ROI 는 run 제외 사유다")
    return (data - data.mean(axis=0)) / std


@dataclass(frozen=True)
class DesignReport:
    """한 run 의 nuisance 설계 요약. `preprocessing.jsonl` 에 그대로 들어간다."""

    n_frames: int
    columns: Tuple[str, ...]
    n_motion: int
    n_acompcor: int
    n_spike: int
    rank: int
    t_run_sec: float
    filter_dof: int
    residual_dof: int
    passes_dof: bool

    def to_record(self) -> Dict[str, Any]:
        """manifest 레코드용 dict."""
        return {
            "n_frames": self.n_frames,
            "nuisance_columns": list(self.columns),
            "n_motion": self.n_motion,
            "n_acompcor": self.n_acompcor,
            "n_spike": self.n_spike,
            "design_rank": self.rank,
            "t_run_sec": self.t_run_sec,
            "filter_dof": self.filter_dof,
            "residual_dof": self.residual_dof,
            "min_residual_dof": MIN_RESIDUAL_DOF,
            "passes_dof": self.passes_dof,
            "bandpass_hz": [BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ],
            "analysis_interval_sec": [ANALYSIS_START, ANALYSIS_END],
        }


def summarize_design(design: np.ndarray, names: Sequence[str],
                     *, native_tr: float) -> DesignReport:
    """설계행렬에서 manifest 에 넣을 수치를 계산한다."""
    n_frames = design.shape[0]
    rank = design_rank(design)
    t_run = native_tr * n_frames
    filter_dof = filter_degrees_of_freedom(t_run)
    residual = residual_degrees_of_freedom(n_frames, rank, t_run)
    n_spike = sum(1 for n in names if n.startswith("spike_frame_"))
    n_acompcor = sum(1 for n in names if n.startswith("a_comp_cor"))
    return DesignReport(
        n_frames=n_frames,
        columns=tuple(names),
        n_motion=sum(1 for n in names if n.split("_")[0] in ("trans", "rot")),
        n_acompcor=n_acompcor,
        n_spike=n_spike,
        rank=rank,
        t_run_sec=t_run,
        filter_dof=filter_dof,
        residual_dof=residual,
        passes_dof=residual > MIN_RESIDUAL_DOF,
    )


def read_confounds_tsv(path: Path) -> Dict[str, List[float]]:
    """fMRIPrep confounds TSV 를 읽는다. 'n/a' 는 NaN 으로만 바꾼다."""
    path = Path(path)
    if not path.is_file():
        raise ExtractError(f"confounds 파일이 없다: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        raise ExtractError(f"confounds 가 비었다: {path}")
    header = lines[0].split("\t")
    columns: Dict[str, List[float]] = {name: [] for name in header}
    for lineno, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != len(header):
            raise ExtractError(
                f"{path}:{lineno} 열 수 {len(cells)} != 머리글 {len(header)}")
        for name, cell in zip(header, cells):
            columns[name].append(float("nan") if cell in ("n/a", "", "NaN")
                                 else float(cell))
    return columns


def read_confounds_metadata(path: Path) -> Dict[str, Dict[str, Any]]:
    """confounds sidecar JSON 을 읽는다."""
    path = Path(path)
    if not path.is_file():
        raise ExtractError(f"confounds sidecar 가 없다: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ExtractError(f"confounds sidecar 형식 오류: {path}")
    return data
