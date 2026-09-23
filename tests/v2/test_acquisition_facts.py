"""Wave 1 으로 확정된 획득 사실을 시험으로 고정한다.

이 값들은 추정이 아니라 OpenNeuro raw sidecar 전수 조사 결과다
(`scripts/h197/09_survey_discarded_volumes.py`, 1,295 run, 조합 내 분산 0).
값이 바뀌면 재조사 결과를 먼저 갱신해야 하며, 코드가 조용히 달라지면 여기서 깨진다.
"""

from __future__ import annotations

import numpy as np
import pytest

from mobse.v2 import preprocess as P

#: 스캐너가 버린 dummy volume 수. 6개 조합 1,295 run 전부 동일 (U3 해소).
DISCARDED_BY_SCANNER = 2

#: (dataset, task, native_tr, n_volumes) — sidecar 직접 판독값 (U1/U2 해소).
COMBOS = (
    ("piop1", "emomatching", 2.00, 135),
    ("piop1", "workingmemory", 2.00, 162),
    ("piop1", "restingstate", 0.75, 480),
    ("piop2", "emomatching", 2.00, 135),
    ("piop2", "workingmemory", 2.00, 160),
    ("piop2", "restingstate", 2.00, 240),
)

TARGET_TASKS = ("emomatching", "workingmemory")


def _start(tr: float) -> float:
    """폐기된 dummy 뒤 첫 저장 표본의 원 acquisition 시각."""
    return DISCARDED_BY_SCANNER * tr


@pytest.mark.parametrize("ds,task,tr,nv", COMBOS, ids=lambda v: str(v))
def test_every_combo_supports_the_fixed_interval(ds, task, tr, nv):
    """[12,252) 가 6개 조합 전부에서 성립한다 — 개정 P3 철회의 근거."""
    assert P.supports_analysis_interval(nv, tr, derivative_start_sec=_start(tr))


@pytest.mark.parametrize("ds,task,tr,nv", COMBOS, ids=lambda v: str(v))
def test_original_clock_reaches_252(ds, task, tr, nv):
    times = P.original_times(nv, tr, derivative_start_sec=_start(tr))
    assert times[0] == pytest.approx(_start(tr))
    assert times[-1] >= P.ANALYSIS_END, f"{ds}/{task}: 마지막 표본 {times[-1]} < 252"


@pytest.mark.parametrize(
    "ds,task,tr,nv", [c for c in COMBOS if c[1] in TARGET_TASKS], ids=lambda v: str(v)
)
def test_target_tasks_need_no_interpolation(ds, task, tr, nv):
    """TR=2초 target task 는 2초 목표 격자와 정확히 겹친다.

    dummy 2개를 되살린 원 시각이 4, 6, 8, … 초이므로 12, 14, …, 250 초가
    모두 실제 획득 시점이다. 즉 두 target task 의 시계열은 보간되지 않는다.
    """
    times = P.original_times(nv, tr, derivative_start_sec=_start(tr))
    target = P.target_times()
    hit = np.isclose(target[:, None], times[None, :], atol=1e-9).any(axis=1)
    assert hit.all(), f"{ds}/{task}: 격자 불일치 {int((~hit).sum())}개"
    assert len(target) == P.TOTAL_TARGET_SAMPLES == 120


def test_bank_source_does_need_interpolation():
    """PIOP1 rest(TR=0.75)만 보간이 필요하다는 사실을 명시적으로 고정한다."""
    times = P.original_times(480, 0.75, derivative_start_sec=_start(0.75))
    target = P.target_times()
    hit = np.isclose(target[:, None], times[None, :], atol=1e-9).any(axis=1)
    assert 0 < int(hit.sum()) < len(target), "보간 없음/전부 중 하나로 바뀌었다"


@pytest.mark.parametrize("tr", (2.00, 0.75))
def test_window_source_frames_respect_discarded_volumes(tr):
    """12초 guard 를 derivative 시작점에 다시 더하지 않는다 (계획서 §3.1)."""
    windows = P.fixed_windows(tr, derivative_start_sec=_start(tr))
    assert len(windows) == 4
    first = windows[0]
    expected_first_frame = round((P.ANALYSIS_START - _start(tr)) / tr)
    assert first.source_frame_range[0] == expected_first_frame
    assert first.start_sec == P.ANALYSIS_START
    assert windows[-1].end_sec == P.ANALYSIS_END
    for w in windows:
        assert w.grid_slice[1] - w.grid_slice[0] == P.SAMPLES_PER_WINDOW


def test_windows_are_contiguous_and_non_overlapping():
    windows = P.fixed_windows(2.0, derivative_start_sec=4.0)
    for a, b in zip(windows, windows[1:]):
        assert a.end_sec == b.start_sec
        assert a.grid_slice[1] == b.grid_slice[0]


@pytest.mark.parametrize("ds,task,tr,nv", COMBOS, ids=lambda v: str(v))
def test_passband_leaves_room_above_threshold(ds, task, tr, nv):
    """개정 P9/P10 — spike 없는 run 의 정확 DOF (통과 성분 − nuisance 31 + 1) 가 30을 넘는지.

    결합 설계 rank = nuisance 31 + 차단대역 (n − 통과 − 1) 이므로
    DOF = 통과 + 1 − 31. spike 하나마다 최대 1 줄어든다.
    """
    from mobse.v2.extract import passband_component_count

    typical = passband_component_count(nv, tr) + 1 - 31
    assert typical > P.MIN_RESIDUAL_DOF, f"{ds}/{task}: typical DOF {typical}"


def test_antialias_required_for_downsampling_rest():
    """0.75초 → 2초 downsample 에는 anti-aliasing 이 필요하다."""
    from mobse.v2.extract import BANDPASS_HIGH_HZ

    P.assert_antialiased(0.75, lowpass_hz=BANDPASS_HIGH_HZ)  # 0.2 Hz < 새 Nyquist 0.25 Hz
    P.assert_antialiased(0.75, lowpass_hz=0.1)
    with pytest.raises(P.PreprocessError):
        P.assert_antialiased(0.75, lowpass_hz=0.4)
