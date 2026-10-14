"""ADHD-200 입력 (결정 62–64) 의 규칙 시험 — 라벨 읽기 · 시계열 머리 · 가장 작은 parcel 고르기 · 좌표 대조."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/i1_adhd200"))
import build_inputs  # noqa: E402
import inventory  # noqa: E402


def test_dx_label_maps_bids_and_nitrc_codes():
    assert inventory.dx_label("Typically Developing Children") == 0
    assert inventory.dx_label("0") == 0
    for v in ("ADHD-Combined", "ADHD-Inattentive", "ADHD-Hyperactive/Impulsive", "1", "3"):
        assert inventory.dx_label(v) == 1
    assert inventory.dx_label("withheld") is None and inventory.dx_label("") is None


def test_read_tc_and_header_labels(tmp_path):
    p = tmp_path / "x_cc200_TCs.1D"
    p.write_text("File\tSub-brick\tMean_1  \tMean_3  \tMean_7  \n"
                 "a.nii[0]\t0\t1.0\t2.0\t3.0\n"
                 "a.nii[1]\t1\t4.0\t5.0\t6.0\n")
    ts = inventory.read_tc(p)
    assert ts.shape == (2, 3) and ts[1, 2] == 6.0
    assert build_inputs.header_labels(p) == [1, 3, 7]


def _atlas(tmp_path, sizes: dict):
    nib = pytest.importorskip("nibabel")
    data = np.zeros((20, 10, 10), dtype=np.int16)
    x = 0
    for lab, n in sizes.items():          # label 마다 n voxel 을 x 축으로 이어 붙인다
        flat = np.zeros(data.size, dtype=bool)
        flat[x:x + n] = True
        data[flat.reshape(data.shape)] = lab
        x += n
    aff = np.diag([-2.0, 2.0, 2.0, 1.0])
    aff[0, 3] = 19.0                       # x 가 양수 · 음수 양쪽에 걸치게
    p = tmp_path / "atlas.nii.gz"
    nib.save(nib.Nifti1Image(data, aff), str(p))
    return p


def test_smallest_labels_rule_and_tie_stop(tmp_path):
    p = _atlas(tmp_path, {1: 30, 3: 5, 4: 12, 9: 40})
    assert build_inputs.smallest_labels(p, [1, 3, 4, 9], 2) == [3, 4]
    q = _atlas(tmp_path, {1: 30, 3: 5, 4: 12, 9: 12})
    with pytest.raises(SystemExit):
        build_inputs.smallest_labels(q, [1, 3, 4, 9], 2)


def test_coords_requires_kept_plus_dropped_to_equal_atlas(tmp_path):
    p = _atlas(tmp_path, {1: 30, 3: 5, 4: 12, 9: 40})
    c = build_inputs.coords(p, [1, 9], [3, 4])
    assert c["n_roi"] == 2 and c["roi_labels"] == [1, 9] and len(c["is_left"]) == 2
    with pytest.raises(SystemExit):
        build_inputs.coords(p, [1, 9], [3])
