"""WI-02 재추출 — nuisance 설계·자유도·잔차 (계획서 §3.2, 개정 P6-b)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from mobse.v2.extract import (
    ACOMPCOR_MASKS,
    ExtractDataError,
    BANDPASS_HIGH_HZ,
    BANDPASS_LOW_HZ,
    ExtractError,
    N_ACOMPCOR,
    build_design,
    design_rank,
    filter_degrees_of_freedom,
    motion_column_names,
    read_confounds_metadata,
    read_confounds_tsv,
    regress_out,
    residual_degrees_of_freedom,
    select_acompcor,
    spike_regressors,
    summarize_design,
    zscore_rois,
)
from mobse.v2.preprocess import MIN_RESIDUAL_DOF

RNG = np.random.default_rng(20260917)


def _confounds(n=135, *, fd_spikes=(), seed=0):
    rng = np.random.default_rng(seed)
    cols = {name: rng.normal(size=n) for name in motion_column_names()}
    for name in cols:
        if name.endswith("derivative1") or name.endswith("derivative1_power2"):
            cols[name][0] = np.nan  # fMRIPrep 의 구조적 첫 행 결측
    for i in range(6):
        cols[f"a_comp_cor_{i:02d}"] = rng.normal(size=n)
    fd = np.abs(rng.normal(scale=0.05, size=n))
    fd[0] = np.nan
    for f in fd_spikes:
        fd[f] = 0.9
    cols["framewise_displacement"] = fd
    return cols


def _metadata(n_combined=10, n_wm=5, *, retained=True, missing_var=False):
    meta = {}
    idx = 0
    for i in range(n_combined):
        meta[f"a_comp_cor_{idx:02d}"] = {
            "Mask": "combined", "Retained": retained,
            **({} if missing_var and i == 0 else {"VarianceExplained": 0.10 - 0.005 * i}),
        }
        idx += 1
    for i in range(n_wm):
        meta[f"a_comp_cor_{idx:02d}"] = {
            "Mask": "WM", "Retained": True, "VarianceExplained": 0.99,
        }
        idx += 1
    meta["trans_x"] = {"Description": "not a compcor column"}
    return meta


# --- aCompCor 선택 -----------------------------------------------------------

def test_selects_five_by_descending_variance():
    picked = select_acompcor(_metadata())
    assert picked == [f"a_comp_cor_{i:02d}" for i in range(N_ACOMPCOR)]


def test_ignores_masks_outside_allowlist():
    """WM 성분이 설명분산이 더 높아도 골라선 안 된다."""
    picked = select_acompcor(_metadata())
    assert all(int(p.split("_")[-1]) < 10 for p in picked)
    assert ACOMPCOR_MASKS == ("combined",)


def test_fails_when_fewer_than_five_available():
    with pytest.raises(ExtractError, match="대체하지 않는다"):
        select_acompcor(_metadata(n_combined=4))


def test_fails_when_none_retained():
    with pytest.raises(ExtractError, match="대체하지 않는다"):
        select_acompcor(_metadata(retained=False))


def test_fails_when_variance_explained_missing():
    with pytest.raises(ExtractError, match="VarianceExplained"):
        select_acompcor(_metadata(missing_var=True))


def test_tie_broken_by_name_for_determinism():
    meta = {f"a_comp_cor_{i:02d}": {"Mask": "combined", "Retained": True,
                                     "VarianceExplained": 0.5} for i in range(8)}
    assert select_acompcor(meta) == select_acompcor(meta)
    assert select_acompcor(meta) == [f"a_comp_cor_{i:02d}" for i in range(5)]


# --- spike regressor ---------------------------------------------------------

def test_spike_one_hot_per_flagged_frame():
    fd = [np.nan, 0.1, 0.9, 0.2, 0.6]
    block, frames = spike_regressors(fd)
    assert frames == [2, 4]
    assert block.shape == (5, 2)
    assert block[2, 0] == 1.0 and block[4, 1] == 1.0
    assert block.sum() == 2.0


def test_first_frame_nan_is_structural_not_a_spike():
    block, frames = spike_regressors([np.nan, 0.1, 0.1])
    assert frames == []
    assert block.shape == (3, 0)


def test_non_first_nan_is_a_failure():
    with pytest.raises(ExtractError, match="첫 frame 이 아닌 곳"):
        spike_regressors([np.nan, 0.1, np.nan])


def test_threshold_is_strict_greater_than():
    _, frames = spike_regressors([np.nan, 0.5, 0.500001])
    assert frames == [2], "0.5 정확히는 spike 가 아니다"


def test_empty_fd_rejected():
    with pytest.raises(ExtractError):
        spike_regressors([])


# --- 설계행렬 ----------------------------------------------------------------

def test_design_column_order_and_counts():
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    design, names = build_design(_confounds(fd_spikes=(10, 20)),
                                 acompcor_names=acomp, n_frames=135)
    assert names[:24] == motion_column_names()
    assert names[24:29] == acomp
    assert names[29:31] == ["spike_frame_0010", "spike_frame_0020"]
    assert names[-2:] == ["intercept", "linear_drift"]
    assert design.shape == (135, 31 + 2)
    assert np.all(np.isfinite(design))


def test_derivative_first_row_nan_becomes_zero():
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    design, names = build_design(_confounds(), acompcor_names=acomp, n_frames=135)
    col = names.index("trans_x_derivative1")
    assert design[0, col] == 0.0


def test_non_structural_nan_is_a_failure():
    cols = _confounds()
    cols["trans_y"][7] = np.nan
    with pytest.raises(ExtractError, match="결측"):
        build_design(cols, acompcor_names=[f"a_comp_cor_{i:02d}" for i in range(5)],
                     n_frames=135)


def test_missing_column_is_a_failure():
    cols = _confounds()
    del cols["rot_z_power2"]
    with pytest.raises(ExtractError, match="없는 열"):
        build_design(cols, acompcor_names=[f"a_comp_cor_{i:02d}" for i in range(5)],
                     n_frames=135)


def test_missing_fd_is_a_failure():
    cols = _confounds()
    del cols["framewise_displacement"]
    with pytest.raises(ExtractError, match="framewise_displacement"):
        build_design(cols, acompcor_names=[f"a_comp_cor_{i:02d}" for i in range(5)],
                     n_frames=135)


def test_length_mismatch_is_a_failure():
    cols = _confounds(n=100)
    with pytest.raises(ExtractError, match="길이"):
        build_design(cols, acompcor_names=[f"a_comp_cor_{i:02d}" for i in range(5)],
                     n_frames=135)


def test_only_one_drift_column():
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    _design, names = build_design(_confounds(), acompcor_names=acomp, n_frames=135)
    assert sum(1 for n in names if "drift" in n) == 1


# --- 자유도 (개정 P6-b) -------------------------------------------------------

@pytest.mark.parametrize(
    "t_run,expected",
    [(270.0, 49), (324.0, 59), (360.0, 66), (320.0, 58), (480.0, 88)],
)
def test_filter_dof_matches_frozen_table(t_run, expected):
    assert filter_degrees_of_freedom(t_run) == expected


def test_residual_dof_takes_the_minimum():
    # n-rank = 102, filter = 49 -> 49
    assert residual_degrees_of_freedom(135, 33, 270.0) == 49
    # n-rank = 20, filter = 49 -> 20
    assert residual_degrees_of_freedom(135, 115, 270.0) == 20


def test_residual_dof_is_stricter_than_old_definition():
    """개정 P6-b 가 기준을 완화하지 않았음을 명시적으로 확인한다."""
    old = 135 - 33
    new = residual_degrees_of_freedom(135, 33, 270.0)
    assert new <= old


def test_filter_dof_rejects_bad_band():
    with pytest.raises(ExtractError):
        filter_degrees_of_freedom(270.0, low_hz=0.2, high_hz=0.1)
    with pytest.raises(ExtractError):
        filter_degrees_of_freedom(0.0)


def test_summarize_design_reports_all_fields():
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    design, names = build_design(_confounds(fd_spikes=(5,)),
                                 acompcor_names=acomp, n_frames=135)
    rep = summarize_design(design, names, native_tr=2.0)
    assert rep.n_motion == 24 and rep.n_acompcor == 5 and rep.n_spike == 1
    assert rep.t_run_sec == 270.0 and rep.filter_dof == 49
    assert rep.residual_dof == min(135 - rep.rank, 49)
    assert rep.passes_dof is (rep.residual_dof > MIN_RESIDUAL_DOF)
    rec = rep.to_record()
    assert rec["bandpass_hz"] == [BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ]
    assert len(rec["nuisance_columns"]) == design.shape[1]


# --- 잔차·z-score ------------------------------------------------------------

def test_regress_out_removes_the_design_exactly():
    n, p, r = 100, 5, 8
    design = RNG.normal(size=(n, p))
    beta = RNG.normal(size=(p, r))
    data = design @ beta
    resid = regress_out(data, design)
    assert np.allclose(resid, 0.0, atol=1e-8)


def test_regress_out_keeps_orthogonal_signal():
    """설계에 직교하는 성분은 거의 그대로 남는다.

    sin 이 아니라 cos 를 쓴다. 구간 중심에 대해 sin 은 홀함수이고 linear drift 도
    홀함수라 둘의 곱이 짝함수가 되어 **직교하지 않는다** — 첫 판에서 이걸 놓쳐
    시험이 잘못 깨졌다(코드가 아니라 시험이 틀렸다). cos 는 거의 직교하지만
    이산 표본의 위상 때문에 정확히 0 은 아니므로, 분산 보존으로 주장한다.
    """
    n = 200
    design = np.column_stack([np.ones(n), np.linspace(-1, 1, n)])
    signal = np.cos(np.linspace(0, 8 * np.pi, n, endpoint=False))[:, None]
    resid = regress_out(signal, design)
    assert np.corrcoef(resid[:, 0], signal[:, 0])[0, 1] > 0.999
    retained = resid.var() / signal.var()
    assert retained > 0.999, f"직교 성분의 분산이 {retained:.4f} 로 줄었다"


def test_regress_out_shape_mismatch():
    with pytest.raises(ExtractError, match="frame 수 불일치"):
        regress_out(np.zeros((10, 3)), np.zeros((9, 2)))


def test_regress_out_rejects_nonfinite():
    data = np.zeros((10, 2)); data[0, 0] = np.nan
    with pytest.raises(ExtractError, match="비유한값"):
        regress_out(data, np.ones((10, 1)))


def test_zscore_per_roi():
    data = RNG.normal(loc=[5.0, -3.0], scale=[2.0, 0.5], size=(200, 2))
    z = zscore_rois(data)
    assert np.allclose(z.mean(axis=0), 0.0, atol=1e-12)
    assert np.allclose(z.std(axis=0), 1.0, atol=1e-12)


def test_zscore_rejects_constant_roi():
    data = np.column_stack([RNG.normal(size=50), np.full(50, 3.0)])
    with pytest.raises(ExtractError, match="constant ROI"):
        zscore_rois(data)


# --- 파일 입출력 --------------------------------------------------------------

def test_read_confounds_tsv_maps_na_to_nan(tmp_path):
    path = tmp_path / "c.tsv"
    path.write_text("a\tb\nn/a\t1.5\n2.0\t3.0\n", encoding="utf-8")
    cols = read_confounds_tsv(path)
    assert np.isnan(cols["a"][0]) and cols["a"][1] == 2.0
    assert cols["b"] == [1.5, 3.0]


def test_read_confounds_tsv_rejects_ragged(tmp_path):
    path = tmp_path / "c.tsv"
    path.write_text("a\tb\n1\n", encoding="utf-8")
    with pytest.raises(ExtractError, match="열 수"):
        read_confounds_tsv(path)


def test_read_confounds_tsv_missing_file(tmp_path):
    with pytest.raises(ExtractError, match="없다"):
        read_confounds_tsv(tmp_path / "nope.tsv")


def test_read_confounds_metadata(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps(_metadata()), encoding="utf-8")
    assert len(select_acompcor(read_confounds_metadata(path))) == 5


# --- 자료 조건 vs 구조적 실패 구분 (실제 전량 추출에서 드러난 문제) ------------

def test_data_condition_errors_are_a_distinct_subclass():
    """계획서가 예상한 제외 사유와 진짜 고장을 같은 부류로 묶지 않는다.

    PIOP1 workingmemory 전량 추출에서 'error 3건' 중 2건이 계획서가 미리 정해 둔
    자료 조건(aCompCor 부족, VarianceExplained 부재)이었고 1건만 실제 I/O 오류였다.
    둘을 같은 error 로 세면 진짜 고장이 정상 제외 건수에 묻힌다.
    """
    assert issubclass(ExtractDataError, ExtractError)


def test_insufficient_acompcor_is_a_data_condition():
    with pytest.raises(ExtractDataError):
        select_acompcor(_metadata(n_combined=1))


def test_missing_variance_explained_is_a_data_condition():
    with pytest.raises(ExtractDataError):
        select_acompcor(_metadata(missing_var=True))


def test_constant_roi_is_a_data_condition():
    data = np.column_stack([RNG.normal(size=50), np.full(50, 3.0)])
    with pytest.raises(ExtractDataError):
        zscore_rois(data)


def test_stray_fd_gap_is_a_data_condition():
    with pytest.raises(ExtractDataError):
        spike_regressors([np.nan, 0.1, np.nan])


def test_structural_failures_stay_plain_extract_error():
    """형상 불일치 같은 구조적 실패는 자료 조건이 아니다."""
    with pytest.raises(ExtractError) as info:
        regress_out(np.zeros((10, 3)), np.zeros((9, 2)))
    assert not isinstance(info.value, ExtractDataError)

    with pytest.raises(ExtractError) as info:
        filter_degrees_of_freedom(0.0)
    assert not isinstance(info.value, ExtractDataError)
