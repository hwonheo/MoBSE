"""WI-02 드라이버의 계약 시험 (`scripts/h197/10_wi02_extract.py`).

이 시험이 존재하는 이유가 분명하다. 드라이버를 처음 쓸 때 `qc_decision()` 의
인자 이름과 반환 키를 **기억으로 적어** 두 번 깨졌다(`task=` / `decision["keep"]`).
실제 데이터 smoke 로만 잡히는 오류였는데, 그건 Wave 2 가 끝나야 돌릴 수 있는
경로다. 그래서 합성 fixture 로 같은 계약을 suite 안에서 강제한다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

nib = pytest.importorskip("nibabel")
pytest.importorskip("nilearn")

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO_ROOT / "scripts" / "h197" / "10_wi02_extract.py"

from mobse.v2 import extract as E  # noqa: E402
from mobse.v2 import preprocess as P  # noqa: E402


def _load_driver():
    spec = importlib.util.spec_from_file_location("_wi02_driver", DRIVER_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"드라이버 적재 실패: {DRIVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    if not DRIVER_PATH.is_file():
        pytest.skip(f"드라이버 없음: {DRIVER_PATH}")
    return _load_driver()


N_FRAMES = 135
NATIVE_TR = 2.0
SHAPE = (6, 6, 6)


def _write_run(tmp_path: Path, *, spikes=(), mean_fd=0.05, n_labels=100):
    """합성 run 한 벌 (BOLD, mask, atlas, confounds) 을 만든다."""
    rng = np.random.default_rng(7)
    affine = np.diag([3.0, 3.0, 3.3, 1.0])

    bold = rng.normal(size=SHAPE + (N_FRAMES,)) + 100.0
    nib.save(nib.Nifti1Image(bold, affine), tmp_path / "bold.nii.gz")
    nib.save(nib.Nifti1Image(np.ones(SHAPE, dtype=np.uint8), affine),
             tmp_path / "mask.nii.gz")

    # 각 voxel 에 1..n_labels 를 골고루 배정 (6^3 = 216 voxel >= 100 parcel)
    flat = np.zeros(int(np.prod(SHAPE)), dtype=np.int16)
    for i in range(flat.size):
        flat[i] = (i % n_labels) + 1
    nib.save(nib.Nifti1Image(flat.reshape(SHAPE), affine), tmp_path / "atlas.nii.gz")

    cols = {}
    for name in E.motion_column_names():
        values = rng.normal(size=N_FRAMES)
        if "derivative1" in name:
            values[0] = np.nan
        cols[name] = values
    for i in range(6):
        cols[f"a_comp_cor_{i:02d}"] = rng.normal(size=N_FRAMES)
    fd = np.full(N_FRAMES, mean_fd)
    fd[0] = np.nan
    for f in spikes:
        fd[f] = 0.9
    cols["framewise_displacement"] = fd

    header = sorted(cols)
    lines = ["\t".join(header)]
    for row in range(N_FRAMES):
        lines.append("\t".join(
            "n/a" if not np.isfinite(cols[c][row]) else repr(float(cols[c][row]))
            for c in header))
    (tmp_path / "conf.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    meta = {f"a_comp_cor_{i:02d}": {"Mask": "combined", "Retained": True,
                                    "VarianceExplained": 0.1 - 0.01 * i}
            for i in range(6)}
    (tmp_path / "conf.json").write_text(json.dumps(meta), encoding="utf-8")

    return {
        "bold": tmp_path / "bold.nii.gz",
        "mask": tmp_path / "mask.nii.gz",
        "confounds": tmp_path / "conf.tsv",
        "confounds_json": tmp_path / "conf.json",
        "raw_sidecar": tmp_path / "conf.json",  # 존재 확인용
    }


def test_driver_module_loads(driver):
    assert driver.DISCARDED_BY_SCANNER == 2
    assert driver.SPACE == "MNI152NLin2009cAsym"
    assert driver.N_ROI == 100


def test_qc_decision_contract_is_what_driver_expects():
    """드라이버가 쓰는 인자 이름과 반환 키를 직접 고정한다."""
    run_qc = P.fd_quality([np.nan] + [0.05] * 10)
    windows = P.fixed_windows(NATIVE_TR, derivative_start_sec=4.0)
    window_qc = [P.window_fd_quality([np.nan] + [0.05] * 200, w) for w in windows]
    decision = P.qc_decision(run_qc, window_qc, residual_dof=49)
    assert set(decision) == {"passed", "all_reasons", "primary_reason"}
    assert decision["passed"] is True


def test_process_run_happy_path(driver, tmp_path):
    paths = _write_run(tmp_path)
    result = driver.process_run(paths, NATIVE_TR, paths["bold"].parent / "atlas.nii.gz",
                                {}, None)
    assert result["status"] == "ok", result
    assert result["derivative_start_sec"] == 4.0
    assert result["n_frames"] == N_FRAMES
    design = result["design"]
    assert design["n_motion"] == 24 and design["n_acompcor"] == 5
    # 개정 P10 정확식: 135 − (nuisance 31 + 차단대역 DCT 30) = 74 (spike 없음).
    # dof_probe_hi0.2.json 의 PIOP1/PIOP2 emomatching 중앙값과 같다.
    assert design["residual_dof"] == 74
    assert design["design_rank"] == 61 and design["nuisance_rank"] == 31
    assert design["filter_spec"]["method"] == "simultaneous_regression"
    assert design["filter_spec"]["n_passband"] == 104
    assert design["bandpass_hz"] == [0.008, 0.2]
    assert result["qc_decision"]["passed"] is True
    assert result["windows"] == []  # out_dir=None 이면 쓰지 않는다


def test_process_run_regresses_the_combined_design(driver, tmp_path, monkeypatch):
    """개정 P9 — 잔차 계산이 DOF 판정과 같은 결합 설계(nuisance + 차단대역)를 쓴다.

    nuisance 만으로 회귀해도 DOF 수치는 맞게 나오므로, 회귀에 들어간 설계를
    직접 붙잡아 확인한다.
    """
    seen = []
    original = E.regress_out

    def spy(data, design):
        seen.append(design.shape)
        return original(data, design)

    monkeypatch.setattr(driver.E, "regress_out", spy)
    paths = _write_run(tmp_path)
    result = driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", {}, None)
    assert result["status"] == "ok"
    n_stop = result["design"]["filter_spec"]["n_stopband"]
    assert seen == [(N_FRAMES, len(result["design"]["nuisance_columns"]) + n_stop)]
    assert n_stop == 30


def test_process_run_writes_four_windows(driver, tmp_path):
    paths = _write_run(tmp_path)
    out = tmp_path / "out"
    result = driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", {}, out)
    assert result["status"] == "ok"
    assert len(result["windows"]) == 4
    for i, entry in enumerate(result["windows"]):
        assert entry["shape"] == [P.SAMPLES_PER_WINDOW, 100]
        assert entry["start_sec"] == P.WINDOW_STARTS[i]
        assert len(entry["sha256"]) == 64
        assert np.load(entry["path"]).shape == (P.SAMPLES_PER_WINDOW, 100)


def test_process_run_collects_all_qc_reasons(driver, tmp_path):
    """한 창에 spike 를 몰아 넣으면 사유가 둘 이상 모인다 (§3.3)."""
    paths = _write_run(tmp_path, spikes=tuple(range(100, 112)))
    result = driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", {}, None)
    assert result["status"] == "excluded"
    assert len(result["reason"]) >= 2, result["reason"]
    assert result["primary_reason"] == result["reason"][0]


def test_process_run_skips_when_a_file_is_missing(driver, tmp_path):
    paths = _write_run(tmp_path)
    paths["confounds"].unlink()
    result = driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", {}, None)
    assert result["status"] == "skipped"
    assert "confounds" in result["reason"]


def test_atlas_with_missing_parcel_is_rejected(driver, tmp_path):
    """ROI 를 임의 삭제하지 않는다 — 결손 parcel 은 실패다."""
    paths = _write_run(tmp_path, n_labels=90)
    with pytest.raises(E.ExtractError, match="parcel 결손"):
        driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", {}, None)


def test_run_paths_are_constructed_not_globbed(driver, tmp_path):
    paths = driver.run_paths(tmp_path / "w1", tmp_path / "w2",
                             "ds002785", "sub-0042", "emomatching")
    assert paths["bold"].name == (
        "sub-0042_task-emomatching_acq-seq_space-MNI152NLin2009cAsym"
        "_desc-preproc_bold.nii.gz")
    assert paths["confounds"].name.endswith("desc-confounds_regressors.tsv")
    assert "*" not in str(paths["bold"])


def test_resting_state_acquisition_entity_differs_by_dataset(driver):
    assert driver.ACQ["ds002785"]["restingstate"] == "mb3"
    assert driver.ACQ["ds002790"]["restingstate"] == "seq"


def test_atlas_cache_reused_for_same_grid(driver, tmp_path):
    paths = _write_run(tmp_path)
    cache = {}
    driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", cache, None)
    assert len(cache) == 1
    driver.process_run(paths, NATIVE_TR, tmp_path / "atlas.nii.gz", cache, None)
    assert len(cache) == 1, "같은 격자인데 다시 재표본화했다"
