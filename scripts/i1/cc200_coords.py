#!/usr/bin/env python3
"""I1 사전 작업 — CC200 parcel 중심 좌표와 반구 판정 (계획서 초안 §9, 결정 39).

D2 의 N2 (피험자별 spin) 가 쓴다. 중심 좌표는 v3 와 같은 함수 ``mobse.v3.templates.roi_centroids`` 로 잰다
(voxel 평균 → affine, 반구 = x < 0). ``mobse/v3`` 는 import 만 한다 — 고치지 않으므로 v3 잠금과 무관하다.

함께 남기는 것:
* PCP 의 ``CC200_ROI_labels.csv`` 에 적힌 center of mass 와의 차 (교차 확인).
* parcel 마다 반대쪽 반구에 놓인 voxel 비율 — 정중선을 걸친 parcel 은 반구 안 회전에서 한쪽으로만 배정된다.
* ROI 순서: ABIDE ``rois_cc200.1D`` 의 열 머리 ``#1 … #200`` 이 atlas label 1..200 과 같은 순서라는 가정을 머리 줄로 확인한다.

Usage (h197, venv-i1):
    PYTHONPATH=. python scripts/i1/cc200_coords.py --atlas <cc200_roi_atlas.nii.gz> --labels <CC200_ROI_labels.csv> \\
        --one-d <아무 rois_cc200.1D> --out <json>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_centres(path: Path) -> dict:
    out = {}
    with path.open(newline="") as fh:
        rows = csv.reader(fh)
        next(rows)
        for row in rows:
            m = re.match(r"\s*\(([-\d.]+);([-\d.]+);([-\d.]+)\)", row[2])
            out[int(row[0])] = [float(m.group(k)) for k in (1, 2, 3)]
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument("--labels", required=True, type=Path)
    ap.add_argument("--one-d", required=True, type=Path, help="열 머리 확인용 ABIDE rois_cc200.1D 하나")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv[1:])

    import nibabel as nib
    from mobse.v3.templates import roi_centroids

    coords, is_left = roi_centroids(args.atlas)
    n = len(coords)

    header = args.one_d.read_text().splitlines()[0].split()
    header_ok = header == [f"#{k}" for k in range(1, n + 1)]

    img = nib.load(str(args.atlas))
    data = np.asarray(img.dataobj)
    cross = np.zeros(n)
    for i in range(n):
        x = nib.affines.apply_affine(img.affine, np.argwhere(data == i + 1))[:, 0]
        cross[i] = float(np.mean(x >= 0) if is_left[i] else np.mean(x < 0))

    ref = csv_centres(args.labels)
    diff = np.array([np.linalg.norm(coords[i] - np.array(ref[i + 1])) for i in range(n)])

    rec = {
        "schema_version": "i1-cc200-coords-0.1",
        "atlas_sha256": sha256(args.atlas), "labels_sha256": sha256(args.labels),
        "atlas_shape": list(img.shape), "atlas_axcodes": "".join(nib.aff2axcodes(img.affine)),
        "n_roi": n, "n_left": int(is_left.sum()), "n_right": int((~is_left).sum()),
        "one_d_header_matches_labels_1_to_n": header_ok, "one_d_file": args.one_d.name,
        "centre_vs_pcp_csv_mm": {"max": float(diff.max()), "median": float(np.median(diff))},
        "cross_hemisphere_voxel_frac": {"max": float(cross.max()), "n_over_0.10": int((cross > 0.10).sum()),
                                        "n_over_0.25": int((cross > 0.25).sum())},
        "min_abs_x_mm": float(np.abs(coords[:, 0]).min()),
        "coords_mm": np.round(coords, 3).tolist(), "is_left": is_left.tolist(),
        "cross_frac": np.round(cross, 3).tolist(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k not in ("coords_mm", "is_left", "cross_frac")},
                     ensure_ascii=False, indent=1))
    return 0 if header_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
