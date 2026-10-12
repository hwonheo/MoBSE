"""T01 timing — mobse/v2/preprocess.py."""

from __future__ import annotations

import numpy as np
import pytest

from mobse.v2.preprocess import (
    ANALYSIS_END, ANALYSIS_START, PreprocessError, SAMPLES_PER_WINDOW,
    TOTAL_TARGET_SAMPLES, assert_antialiased, cut_windows, fd_quality,
    fixed_windows, original_times, qc_decision, resample_to_grid,
    supports_analysis_interval, target_times, window_fd_quality,
)


# --------------------------------------------------------------------------- #
# T01 — 원본 시간축 복원과 guard 중복 없음
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("tr,n_vol", [(2.0, 135), (2.0, 162), (0.75, 480)])
def test_target_grid_is_always_120_samples(tr, n_vol):
    assert supports_analysis_interval(n_vol, tr)
    assert target_times().size == TOTAL_TARGET_SAMPLES
    assert target_times()[0] == ANALYSIS_START
    assert target_times()[-1] == ANALYSIS_END - 2.0


def test_discarded_volumes_shift_the_clock_not_the_guard():
    """앞 2 volume 이 제거되면 derivative 첫 sample 의 원본 시간은 2×TR 이다."""
    tr, discarded = 2.0, 2
    t = original_times(133, tr, derivative_start_sec=discarded * tr)
    assert t[0] == 4.0
    # 12초 guard 를 derivative 시작점에 다시 더하면 첫 window 가 16초에서 시작한다.
    # 우리는 원본 clock 의 12초를 쓰므로 그렇게 되면 안 된다.
    w = fixed_windows(tr, derivative_start_sec=discarded * tr)
    assert w[0].start_sec == 12.0
    assert w[0].source_frame_range[0] == 4      # (12 - 4)/2 = 4 번째 derivative frame
    assert t[w[0].source_frame_range[0]] == 12.0


def test_source_frame_range_matches_original_times_for_both_tr():
    for tr, n_vol, discarded in [(2.0, 135, 0), (2.0, 133, 2), (0.75, 480, 0),
                                 (0.75, 476, 4)]:
        start = discarded * tr
        t = original_times(n_vol, tr, start)
        for w in fixed_windows(tr, start):
            lo, hi = w.source_frame_range
            assert t[lo] >= w.start_sec - 1e-9
            assert t[lo] - tr < w.start_sec + 1e-9
            if hi < t.size:
                assert t[hi] >= w.end_sec - 1e-9


def test_four_windows_each_30_samples_and_contiguous():
    ws = fixed_windows(2.0)
    assert len(ws) == 4
    assert [w.n_samples for w in ws] == [SAMPLES_PER_WINDOW] * 4
    assert [w.start_sec for w in ws] == [12.0, 72.0, 132.0, 192.0]
    assert [w.end_sec for w in ws] == [72.0, 132.0, 192.0, 252.0]
    assert sum(w.n_samples for w in ws) == TOTAL_TARGET_SAMPLES
    for a, b in zip(ws, ws[1:]):
        assert a.grid_slice[1] == b.grid_slice[0]


def test_window_before_derivative_start_fails():
    with pytest.raises(PreprocessError, match="guard"):
        fixed_windows(2.0, derivative_start_sec=20.0)


def test_negative_start_and_bad_tr_fail():
    with pytest.raises(PreprocessError, match="음수"):
        original_times(10, 2.0, -1.0)
    with pytest.raises(PreprocessError, match="양수"):
        original_times(10, 0.0)


# --------------------------------------------------------------------------- #
# anti-aliasing 은 명시적으로 검사한다
# --------------------------------------------------------------------------- #

def test_antialias_check_passes_for_protocol_band():
    info = assert_antialiased(0.75, lowpass_hz=0.1)
    assert info["target_nyquist_hz"] == 0.25
    assert info["lowpass_hz"] < info["target_nyquist_hz"]


def test_antialias_check_fails_above_target_nyquist():
    with pytest.raises(PreprocessError, match="aliasing"):
        assert_antialiased(0.75, lowpass_hz=0.3)


# --------------------------------------------------------------------------- #
# resample
# --------------------------------------------------------------------------- #

def test_resample_is_exact_when_grid_already_matches():
    t = original_times(140, 2.0)
    data = np.column_stack([t, 2 * t])
    out = resample_to_grid(data, t)
    assert out.shape == (TOTAL_TARGET_SAMPLES, 2)
    assert np.allclose(out[:, 0], target_times())
    assert np.allclose(out[:, 1], 2 * target_times())


def test_resample_from_075_to_2s_grid_is_linear():
    t = original_times(480, 0.75)
    data = np.column_stack([t, -t])
    out = resample_to_grid(data, t)
    assert np.allclose(out[:, 0], target_times(), atol=1e-9)
    assert np.allclose(out[:, 1], -target_times(), atol=1e-9)


def test_resample_refuses_to_extrapolate():
    t = original_times(100, 2.0)       # 0–198초, 252초를 못 덮는다
    with pytest.raises(PreprocessError, match="외삽"):
        resample_to_grid(np.column_stack([t, t]), t)


def test_short_run_does_not_support_interval():
    assert not supports_analysis_interval(100, 2.0)
    assert not supports_analysis_interval(135, 0.75)    # 101.25초
    assert supports_analysis_interval(135, 2.0)         # 270초


def test_cut_windows_shapes():
    t = original_times(140, 2.0)
    grid = resample_to_grid(np.random.default_rng(0).normal(size=(140, 5)), t)
    ws = cut_windows(grid)
    assert len(ws) == 4
    assert all(w.shape == (SAMPLES_PER_WINDOW, 5) for w in ws)
    assert np.allclose(np.vstack(ws), grid)


# --------------------------------------------------------------------------- #
# FD QC — 원본 frame 으로 계산한다
# --------------------------------------------------------------------------- #

def test_structural_first_missing_is_allowed_and_counted():
    fd = np.concatenate([[np.nan], np.full(134, 0.05)])
    st = fd_quality(fd)
    assert st["n_structural_missing"] == 1
    assert st["n_observed"] == 134
    assert st["mean_fd"] == pytest.approx(0.05)


def test_non_structural_missing_fails():
    fd = np.full(135, 0.05)
    fd[0] = np.nan
    fd[50] = np.nan
    with pytest.raises(PreprocessError, match="구조적 첫 결측 외"):
        fd_quality(fd)


def test_window_fd_uses_original_frames_only():
    fd = np.full(135, 0.02)
    fd[0] = np.nan
    fd[6:36] = 0.9                      # 첫 window 구간(원본 frame 6–35)에 spike
    ws = fixed_windows(2.0)
    w0 = window_fd_quality(fd, ws[0])
    w1 = window_fd_quality(fd, ws[1])
    assert w0["n_frames"] == 30 and w0["n_spikes"] == 30
    assert w0["spike_ratio"] == pytest.approx(1.0)
    assert w1["n_spikes"] == 0


def test_window_fd_range_beyond_data_fails():
    ws = fixed_windows(2.0)
    with pytest.raises(PreprocessError, match="넘는다"):
        window_fd_quality(np.zeros(50), ws[3])


# --------------------------------------------------------------------------- #
# QC 판정은 사유를 모두 모은다
# --------------------------------------------------------------------------- #

def test_qc_collects_all_reasons_not_just_the_first():
    run = {"mean_fd": 0.4, "spike_ratio": 0.5, "n_observed": 134,
           "n_structural_missing": 1, "max_fd": 1.0, "n_spikes": 67}
    wins = [{"window": float(i), "spike_ratio": 0.5, "n_spikes": 15.0,
             "n_frames": 30.0, "n_observed": 30.0, "n_structural_missing": 0.0,
             "mean_fd": 0.4} for i in range(4)]
    d = qc_decision(run, wins, residual_dof=10)
    assert d["passed"] is False
    assert len(d["all_reasons"]) >= 6
    assert d["primary_reason"] == "mean_fd>0.2"
    assert any("residual_dof" in r for r in d["all_reasons"])


def test_qc_passes_clean_run():
    run = {"mean_fd": 0.05, "spike_ratio": 0.0, "n_observed": 134,
           "n_structural_missing": 1, "max_fd": 0.2, "n_spikes": 0}
    wins = [{"window": float(i), "spike_ratio": 0.0, "n_spikes": 0.0,
             "n_frames": 30.0, "n_observed": 30.0, "n_structural_missing": 0.0,
             "mean_fd": 0.05} for i in range(4)]
    d = qc_decision(run, wins, residual_dof=98)
    assert d["passed"] is True and d["all_reasons"] == []


# --- 개정 P7: spike 허용 개수는 창의 원본 frame 수에 비례한다 -------------------

def _win_stat(index, n_observed, n_spikes):
    return {"window": float(index), "n_frames": float(n_observed),
            "n_observed": float(n_observed), "n_structural_missing": 0.0,
            "n_spikes": float(n_spikes), "spike_ratio": n_spikes / n_observed,
            "mean_fd": 0.1}


_CLEAN_RUN = {"mean_fd": 0.1, "spike_ratio": 0.02}


def test_spike_allowance_reference_is_thirty_frames():
    """계획서 §3.3 의 '3개'는 30프레임 창 기준이고, 3/30 = 비율 상한과 같다."""
    from mobse.v2.preprocess import (
        FD_SPIKE_RATIO_MAX, SPIKE_ALLOWANCE_REFERENCE_FRAMES, WINDOW_SPIKE_ALLOWANCE)

    assert SPIKE_ALLOWANCE_REFERENCE_FRAMES == 30
    assert WINDOW_SPIKE_ALLOWANCE / SPIKE_ALLOWANCE_REFERENCE_FRAMES == pytest.approx(
        FD_SPIKE_RATIO_MAX)


@pytest.mark.parametrize("n_spikes,expect_excluded", [(2, False), (3, False), (4, True)])
def test_task_window_behaviour_unchanged(n_spikes, expect_excluded):
    """TR 2초 task 창(30 frame)의 판정은 개정 전과 같아야 한다."""
    decision = qc_decision(_CLEAN_RUN, [_win_stat(0, 30, n_spikes)])
    assert (not decision["passed"]) is expect_excluded


@pytest.mark.parametrize("n_spikes,expect_excluded", [(3, False), (8, False), (9, True)])
def test_rest_window_allowance_scales_with_native_frames(n_spikes, expect_excluded):
    """PIOP1 rest(TR 0.75)의 60초 창은 80 frame 이므로 허용이 8 이어야 한다.

    개정 전에는 절대 3개를 적용해 실효 비율 3.75% — 계획서의 10% 기준보다
    2.7배 엄격했고, 그만큼 rest 가 부당하게 제외됐다.
    """
    decision = qc_decision(_CLEAN_RUN, [_win_stat(0, 80, n_spikes)])
    assert (not decision["passed"]) is expect_excluded


def test_scaled_allowance_matches_ratio_rule_at_any_length():
    """비율 규칙과 개수 규칙이 어떤 창 길이에서도 같은 경계를 준다."""
    from mobse.v2.preprocess import FD_SPIKE_RATIO_MAX

    for n_observed in (20, 30, 40, 80, 120):
        boundary = int(FD_SPIKE_RATIO_MAX * n_observed)
        assert qc_decision(_CLEAN_RUN, [_win_stat(0, n_observed, boundary)])["passed"]
        assert not qc_decision(
            _CLEAN_RUN, [_win_stat(0, n_observed, boundary + 1)])["passed"]


def test_piop1_rest_window_is_eighty_frames():
    """개정 P7 이 겨냥한 실제 조합을 고정한다."""
    windows = fixed_windows(0.75, derivative_start_sec=1.5)
    lo, hi = windows[0].source_frame_range
    assert hi - lo == 80
    windows_task = fixed_windows(2.0, derivative_start_sec=4.0)
    lo, hi = windows_task[0].source_frame_range
    assert hi - lo == 30
