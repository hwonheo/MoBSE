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
    STOPBAND_PREFIX,
    add_stopband,
    dct_stopband_basis,
    design_rank,
    motion_column_names,
    passband_component_count,
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


# --- band-pass 동시 회귀·자유도 (개정 P9, P10) ---------------------------------

# 6개 조합 (n_frames, TR) — 통과대역 DCT 성분 수와, spike 없는 일반 run 의 정확 DOF.
# 기대값은 h197 recovery_20260923/checks/dof_probe_hi0.2.json 의 n_pass_dct 와
# new_dof 중앙값 (spike 가 없는 run 이 중앙값을 이룬다).
SIX_COMBOS = [
    # (label,            n,   tr,   n_pass, typical_dof)
    ("PIOP1 emo",       135, 2.0,  104,  74),
    ("PIOP1 WM",        162, 2.0,  124,  94),
    ("PIOP1 rest",      480, 0.75, 139, 109),
    ("PIOP2 emo",       135, 2.0,  104,  74),
    ("PIOP2 WM",        160, 2.0,  123,  93),
    ("PIOP2 rest",      240, 2.0,  185, 155),
]


def test_band_constants_follow_decision_9():
    """결정 9 원문 "통과대역 0.2 Hz로" — 상한만 바뀌고 하한은 그대로."""
    assert (BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ) == (0.008, 0.200)
    assert MIN_RESIDUAL_DOF == 30  # 결정 범위 밖 — 불변


@pytest.mark.parametrize("label,n,tr,n_pass,_dof", SIX_COMBOS, ids=[c[0] for c in SIX_COMBOS])
def test_passband_count_matches_probe(label, n, tr, n_pass, _dof):
    assert passband_component_count(n, tr) == n_pass
    basis, names = dct_stopband_basis(n, tr)
    # k=0 (상수) 는 intercept 와 같아 뺀다 → 차단대역 열 = n − 통과 − 1
    assert basis.shape == (n, n - n_pass - 1)
    assert len(names) == basis.shape[1] and all(s.startswith(STOPBAND_PREFIX) for s in names)
    assert f"{STOPBAND_PREFIX}0000" not in names


@pytest.mark.parametrize("label,n,tr,_np,dof", SIX_COMBOS, ids=[c[0] for c in SIX_COMBOS])
def test_exact_dof_reproduces_probe(label, n, tr, _np, dof):
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    nuis, names = build_design(_confounds(n=n), acompcor_names=acomp, n_frames=n)
    design, all_names = add_stopband(nuis, names, native_tr=tr)
    rep = summarize_design(design, all_names, native_tr=tr)
    assert rep.nuisance_rank == 31
    assert rep.residual_dof == n - rep.rank == dof
    assert rep.passes_dof is True


def test_stopband_basis_is_orthonormal_dct():
    basis, _ = dct_stopband_basis(135, 2.0)
    gram = basis.T @ basis
    assert np.allclose(gram, np.diag(np.diag(gram)))  # 서로 직교
    assert np.allclose(np.diag(gram), 135 / 2)


def _dct(n, k):
    t = np.arange(n)
    return np.cos(np.pi * k * (t + 0.5) / n)


def test_simultaneous_regression_keeps_passband_and_removes_stopband():
    n, tr = 135, 2.0
    freqs = np.arange(n) / (2 * n * tr)
    k_pass = int(np.flatnonzero((freqs > 0.05) & (freqs < 0.1))[0])
    k_low = 1                                   # 0.0019 Hz < 0.008
    k_high = int(np.flatnonzero(freqs > 0.22)[0])
    passband = 2.0 * _dct(n, k_pass)
    data = (passband + 3.0 * _dct(n, k_low) + 1.5 * _dct(n, k_high) + 7.0)[:, None]
    intercept = np.ones((n, 1))
    design, _ = add_stopband(intercept, ["intercept"], native_tr=tr)
    resid = regress_out(data, design)
    assert np.allclose(resid[:, 0], passband, atol=1e-8)


def test_stopband_removes_high_frequency_sinusoid():
    """DCT 격자 밖 주파수에서도 차단대역 에너지가 거의 전부 제거된다."""
    n, tr = 480, 0.75
    t = np.arange(n) * tr
    hi = np.sin(2 * np.pi * 0.35 * t)
    mid = np.sin(2 * np.pi * 0.07 * t)
    design, _ = add_stopband(np.ones((n, 1)), ["intercept"], native_tr=tr)
    r_hi = regress_out(hi[:, None], design)[:, 0]
    r_mid = regress_out(mid[:, None], design)[:, 0]
    assert np.sum(r_hi ** 2) / np.sum(hi ** 2) < 0.01
    assert np.sum(r_mid ** 2) / np.sum(mid ** 2) > 0.99


def test_residual_dof_is_exact_rank_deficit():
    assert residual_degrees_of_freedom(135, 61) == 74
    with pytest.raises(ExtractError):
        residual_degrees_of_freedom(135, 136)


def test_exact_dof_counts_shared_freedom_once():
    """nuisance 가 차단대역 안에 있으면 rank 를 올리지 않는다 — P6-b 가 틀린 이유의 반대면."""
    n, tr = 135, 2.0
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    nuis, names = build_design(_confounds(n=n), acompcor_names=acomp, n_frames=n)
    nuis = nuis.copy()
    nuis[:, 0] = _dct(n, n - 1)  # 첫 motion 열을 순수 차단대역 성분으로 바꾼다
    design, all_names = add_stopband(nuis, names, native_tr=tr)
    rep = summarize_design(design, all_names, native_tr=tr)
    assert rep.residual_dof == 75  # 74 + 1: 겹친 자유도를 두 번 세지 않는다


def test_summarize_design_requires_stopband():
    """filter 없이 DOF 를 세면 조용히 과대 보고된다 — 거부해야 한다."""
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    nuis, names = build_design(_confounds(), acompcor_names=acomp, n_frames=135)
    with pytest.raises(ExtractError):
        summarize_design(nuis, names, native_tr=2.0)
    design, all_names = add_stopband(nuis, names, native_tr=2.0)
    with pytest.raises(ExtractError):
        add_stopband(design, all_names, native_tr=2.0)
    with pytest.raises(ExtractError):  # 다른 TR 의 기저 — 기대와 다르다
        summarize_design(design, all_names, native_tr=0.75)


def test_band_rejects_bad_inputs():
    with pytest.raises(ExtractError):
        dct_stopband_basis(135, 2.0, low_hz=0.2, high_hz=0.1)
    with pytest.raises(ExtractError):
        passband_component_count(1, 2.0)


def test_summarize_design_reports_all_fields():
    acomp = [f"a_comp_cor_{i:02d}" for i in range(5)]
    nuis, names = build_design(_confounds(fd_spikes=(5,)),
                               acompcor_names=acomp, n_frames=135)
    design, all_names = add_stopband(nuis, names, native_tr=2.0)
    rep = summarize_design(design, all_names, native_tr=2.0)
    assert rep.n_motion == 24 and rep.n_acompcor == 5 and rep.n_spike == 1
    assert rep.t_run_sec == 270.0
    assert rep.n_stopband == 30 and rep.n_passband == 104
    assert rep.residual_dof == 135 - rep.rank == 73
    assert rep.passes_dof is (rep.residual_dof > MIN_RESIDUAL_DOF)
    rec = rep.to_record()
    assert rec["bandpass_hz"] == [BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ]
    assert rec["filter_spec"]["method"] == "simultaneous_regression"
    assert len(rec["nuisance_columns"]) == nuis.shape[1]
    assert "filter_dof" not in rec


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
        dct_stopband_basis(135, 0.0)
    assert not isinstance(info.value, ExtractDataError)
