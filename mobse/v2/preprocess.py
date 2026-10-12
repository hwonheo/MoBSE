"""시간축·window·QC — 재설계 프로토콜 v1.1 §3 구현.

의존성은 numpy 뿐이다.

프로토콜이 규정한 것을 그대로 옮긴다.

* native TR 에서 nuisance·주파수 처리를 마친 뒤 **anti-aliasing 을 명시해**
  2초 grid 로 resample 한다.
* 원본 acquisition 시간의 **[12, 252)초** 를 주분석 구간으로 한다.
* **12초 guard 를 derivative 시작점에서 다시 더하지 않는다.** 앞 volume 이 이미
  제거되었다면 남은 sample 의 원래 시간을 복원해 선택한다.
* 고정 window 는 [12,72), [72,132), [132,192), [192,252)초이며 각 30 samples 다.
* 임의 이동·padding 을 하지 않는다. 시간 원점이 불명확하면 그 run 은 실패다.
* motion QC 는 **원본 시간축의 frame** 으로 계산한다. 보간한 FD 로 희석하지 않는다.
* 구조적 첫 FD 결측만 별도 표시하며 그 외 결측은 실패 처리한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ANALYSIS_START = 12.0
ANALYSIS_END = 252.0
TARGET_GRID = 2.0
WINDOW_LEN = 60.0
WINDOW_STARTS = (12.0, 72.0, 132.0, 192.0)
SAMPLES_PER_WINDOW = 30
TOTAL_TARGET_SAMPLES = 120

FD_MEAN_MAX = 0.2
FD_SPIKE = 0.5
FD_SPIKE_RATIO_MAX = 0.10
WINDOW_SPIKE_ALLOWANCE = 3        # task 의 30 원본 frame 구간에서 최대 허용
#: 위 허용치가 정의된 기준 frame 수. 계획서 §3.3 은 "task의 30 원본 frames
#: 구간에서는 최대 3개까지 허용한다. rest는 native frame 수로 계산한다"고 적었다.
#: 3/30 = 0.10 으로 비율 상한과 정확히 같으므로, 절대 3개는 **30프레임 창에서의
#: 비율규칙을 개수로 표현한 것**이다. 창의 원본 frame 수가 다르면(PIOP1 rest 는
#: TR 0.75 라 60초 창이 80 frame) 같은 비율이 되도록 비례 조정한다 — 개정 P7.
SPIKE_ALLOWANCE_REFERENCE_FRAMES = 30
MIN_RESIDUAL_DOF = 30


class PreprocessError(RuntimeError):
    """시간축·QC 규칙 위반. 이동·padding 으로 메우지 않는다."""


# --------------------------------------------------------------------------- #
# 시간축
# --------------------------------------------------------------------------- #


def original_times(n_volumes: int, native_tr: float,
                   derivative_start_sec: float = 0.0) -> np.ndarray:
    """derivative sample 의 **원본 acquisition 시간**을 복원한다.

    Args:
        n_volumes: derivative 의 sample 수.
        native_tr: 원본 TR(초).
        derivative_start_sec: derivative 첫 sample 이 원본 clock 에서 갖는 시간.
            앞 volume 이 제거되었다면 ``제거수 × TR`` 이다.

    Raises:
        PreprocessError: TR 이 양수가 아니거나 시작점이 음수이면.
    """
    if native_tr <= 0:
        raise PreprocessError(f"native_tr 는 양수여야 한다: {native_tr}")
    if derivative_start_sec < 0:
        raise PreprocessError(
            f"derivative_start_sec 가 음수다: {derivative_start_sec}. "
            "시간 원점이 불명확하면 그 run 은 실패다")
    if n_volumes <= 0:
        raise PreprocessError(f"n_volumes 는 양수여야 한다: {n_volumes}")
    return derivative_start_sec + np.arange(n_volumes, dtype=float) * native_tr


def assert_antialiased(native_tr: float, lowpass_hz: float,
                       target_grid: float = TARGET_GRID) -> Dict[str, float]:
    """2초 grid 로 내려보낼 때 aliasing 이 없는지 명시적으로 확인한다.

    band-pass 의 상한이 target grid 의 Nyquist 아래여야 한다. 프로토콜은
    "anti-aliasing 을 명시해" resample 하라고 요구하므로, 암묵적 가정 대신
    검사로 남긴다.

    Raises:
        PreprocessError: lowpass 가 target Nyquist 이상이면.
    """
    nyquist = 1.0 / (2.0 * target_grid)
    if lowpass_hz >= nyquist:
        raise PreprocessError(
            f"lowpass {lowpass_hz} Hz 가 target grid Nyquist {nyquist} Hz 이상이다. "
            f"{target_grid}s grid 로 내려보내면 aliasing 이 생긴다")
    return {"native_tr": native_tr, "target_grid": target_grid,
            "target_nyquist_hz": nyquist, "lowpass_hz": lowpass_hz,
            "native_nyquist_hz": 1.0 / (2.0 * native_tr)}


def target_times() -> np.ndarray:
    """주분석 구간의 2초 grid 시각 120개: 12, 14, …, 250."""
    t = np.arange(ANALYSIS_START, ANALYSIS_END, TARGET_GRID)
    if t.size != TOTAL_TARGET_SAMPLES:
        raise PreprocessError(f"target sample 수가 {TOTAL_TARGET_SAMPLES} 가 아니다: {t.size}")
    return t


def supports_analysis_interval(n_volumes: int, native_tr: float,
                               derivative_start_sec: float = 0.0) -> bool:
    """이 run 이 [12,252) 를 덮는지 판정한다. 부족하면 padding 하지 않는다."""
    times = original_times(n_volumes, native_tr, derivative_start_sec)
    return bool(times[0] <= ANALYSIS_START and times[-1] >= ANALYSIS_END - TARGET_GRID)


def resample_to_grid(data: np.ndarray, src_times: np.ndarray,
                     dst_times: Optional[np.ndarray] = None) -> np.ndarray:
    """원본 시간축 자료를 2초 grid 로 선형 보간한다.

    외삽을 하지 않는다. 요청한 grid 가 원본 범위를 벗어나면 실패한다.

    Args:
        data: ``(n_samples, n_roi)``.
        src_times: ``(n_samples,)`` 원본 시간.
    """
    dst = target_times() if dst_times is None else np.asarray(dst_times, dtype=float)
    x = np.asarray(data, dtype=float)
    t = np.asarray(src_times, dtype=float)
    if x.shape[0] != t.shape[0]:
        raise PreprocessError(f"sample 수 불일치: data {x.shape[0]} vs times {t.shape[0]}")
    if dst[0] < t[0] - 1e-9 or dst[-1] > t[-1] + 1e-9:
        raise PreprocessError(
            f"요청 grid [{dst[0]}, {dst[-1]}] 가 원본 범위 [{t[0]}, {t[-1]}] 를 벗어난다. "
            "외삽·padding 하지 않는다")
    return np.stack([np.interp(dst, t, x[:, j]) for j in range(x.shape[1])], axis=1)


# --------------------------------------------------------------------------- #
# 고정 window
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Window:
    """고정 window 하나."""

    index: int
    start_sec: float
    end_sec: float
    grid_slice: Tuple[int, int]
    source_frame_range: Tuple[int, int]

    @property
    def n_samples(self) -> int:
        return self.grid_slice[1] - self.grid_slice[0]


def fixed_windows(native_tr: float, derivative_start_sec: float = 0.0) -> List[Window]:
    """네 개의 고정 window 와 그 원본 frame 범위를 만든다.

    ``grid_slice`` 는 `target_times()` 위의 index 이고, ``source_frame_range`` 는
    derivative index 기준 반열린 구간이다. 원본 frame 을 QC 에 쓰기 위한 것이다.
    """
    grid = target_times()
    out: List[Window] = []
    for i, start in enumerate(WINDOW_STARTS):
        end = start + WINDOW_LEN
        lo = int(np.searchsorted(grid, start, side="left"))
        hi = int(np.searchsorted(grid, end, side="left"))
        if hi - lo != SAMPLES_PER_WINDOW:
            raise PreprocessError(
                f"window {i} 의 sample 수가 {SAMPLES_PER_WINDOW} 가 아니다: {hi - lo}")
        f_lo = int(np.ceil((start - derivative_start_sec) / native_tr - 1e-9))
        f_hi = int(np.ceil((end - derivative_start_sec) / native_tr - 1e-9))
        if f_lo < 0:
            raise PreprocessError(
                f"window {i} 가 derivative 시작 이전을 가리킨다. "
                "12초 guard 를 derivative 시작점에 다시 더하지 않는다")
        out.append(Window(i, start, end, (lo, hi), (f_lo, f_hi)))
    return out


def cut_windows(gridded: np.ndarray) -> List[np.ndarray]:
    """2초 grid 자료를 네 window 로 자른다. 각 ``(30, n_roi)``."""
    x = np.asarray(gridded, dtype=float)
    if x.shape[0] != TOTAL_TARGET_SAMPLES:
        raise PreprocessError(
            f"grid sample 수가 {TOTAL_TARGET_SAMPLES} 가 아니다: {x.shape[0]}")
    return [x[lo:hi] for lo, hi in
            ((w.grid_slice[0], w.grid_slice[1]) for w in fixed_windows(2.0))]


# --------------------------------------------------------------------------- #
# QC
# --------------------------------------------------------------------------- #


def fd_quality(fd: Sequence[float], *, structural_missing_first: bool = True
               ) -> Dict[str, float]:
    """run 전체 FD 통계. 구조적 첫 결측만 허용한다.

    Raises:
        PreprocessError: 첫 frame 이 아닌 곳에 결측이 있으면.
    """
    arr = np.asarray(fd, dtype=float)
    nan_idx = np.flatnonzero(~np.isfinite(arr))
    allowed = {0} if structural_missing_first else set()
    bad = sorted(set(nan_idx.tolist()) - allowed)
    if bad:
        raise PreprocessError(
            f"구조적 첫 결측 외의 FD 결측이 있다: frame {bad[:5]}. 실패 처리한다")
    obs = arr[np.isfinite(arr)]
    if obs.size == 0:
        raise PreprocessError("관측 가능한 FD 가 없다")
    spikes = int(np.sum(obs > FD_SPIKE))
    return {"n_observed": float(obs.size), "n_structural_missing": float(nan_idx.size),
            "mean_fd": float(obs.mean()), "max_fd": float(obs.max()),
            "n_spikes": float(spikes), "spike_ratio": spikes / obs.size}


def window_fd_quality(fd: Sequence[float], window: Window) -> Dict[str, float]:
    """window 의 **원본 frame** 으로 FD 통계를 낸다. 보간값을 쓰지 않는다.

    분모는 그 구간의 관측 가능한 원본 frame 수이며, 구조적 첫 결측은 제외하고
    수를 함께 보고한다.
    """
    arr = np.asarray(fd, dtype=float)
    lo, hi = window.source_frame_range
    if hi > arr.size:
        raise PreprocessError(
            f"window {window.index} 의 frame 범위 [{lo},{hi}) 가 FD 길이 {arr.size} 를 넘는다")
    seg = arr[lo:hi]
    obs = seg[np.isfinite(seg)]
    if obs.size == 0:
        raise PreprocessError(f"window {window.index} 에 관측 가능한 FD 가 없다")
    spikes = int(np.sum(obs > FD_SPIKE))
    return {"window": float(window.index), "n_frames": float(seg.size),
            "n_observed": float(obs.size),
            "n_structural_missing": float(seg.size - obs.size),
            "n_spikes": float(spikes), "spike_ratio": spikes / obs.size,
            "mean_fd": float(obs.mean())}


def qc_decision(run_stats: Dict[str, float], window_stats: Sequence[Dict[str, float]],
                *, residual_dof: Optional[int] = None,
                spike_allowance: int = WINDOW_SPIKE_ALLOWANCE) -> Dict[str, object]:
    """프로토콜 §3.3 의 QC 판정. 사유를 **모두** 모아 돌려준다.

    중복 사유와 우선 사유를 함께 저장하라는 §3.3 요구에 맞춰, 첫 실패에서 멈추지
    않고 전 사유를 수집한다.
    """
    reasons: List[str] = []
    if run_stats["mean_fd"] > FD_MEAN_MAX:
        reasons.append(f"mean_fd>{FD_MEAN_MAX}")
    if run_stats["spike_ratio"] > FD_SPIKE_RATIO_MAX:
        reasons.append(f"run_spike_ratio>{FD_SPIKE_RATIO_MAX}")
    for w in window_stats:
        if w["spike_ratio"] > FD_SPIKE_RATIO_MAX:
            reasons.append(f"window{int(w['window'])}_spike_ratio>{FD_SPIKE_RATIO_MAX}")
        # 개정 P7 — 허용 개수를 창의 관측 frame 수에 비례 조정한다.
        # 30 frame 창에서는 3 으로 종전과 동일하고, 80 frame 창(PIOP1 rest,
        # TR 0.75)에서는 8 이 되어 비율 상한 10% 와 일치한다.
        allowance = spike_allowance * (w["n_observed"] / SPIKE_ALLOWANCE_REFERENCE_FRAMES)
        if w["n_spikes"] > allowance:
            reasons.append(
                f"window{int(w['window'])}_spikes>{allowance:.0f}")
    if residual_dof is not None and residual_dof <= MIN_RESIDUAL_DOF:
        reasons.append(f"residual_dof<={MIN_RESIDUAL_DOF}")
    return {"passed": not reasons, "all_reasons": reasons,
            "primary_reason": reasons[0] if reasons else None}
