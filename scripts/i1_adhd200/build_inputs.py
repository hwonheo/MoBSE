#!/usr/bin/env python3
"""ADHD-200 I1 입력 (결정 62 · 63) — I1 표준 ``abide.npy`` 형식의 원판과 영역 좌표를 만든다.

대상 (결정 63): ``inventory.json`` 에서 라벨이 있고 · 시점 100 이상 · 상수 영역 없음 · **정상군만 있는 Pittsburgh ·
WashU 를 뺀** 사람 (A1 · A2). 행 순서는 (기관, ID) 오름차순.

``abide.npy`` 는 I1 ABIDE 판 (``scripts/i1/build_abide_npy.py``) 과 같은 정의다:
* ``corr`` · ``pcorr``: nilearn ``ConnectivityMeasure`` (correlation · partial correlation) 를 **전체 시점**에 적용 → arctanh →
  inf 를 0 으로.
* ``timeseires`` (원 철자): (ROI, 시점) 로 전치하고 앞 100 시점.
* ``label``: TD = 0 · ADHD (세 아형) = 1. ``site``: 기관 이름.
파일 이름이 ``abide.npy`` 인 것은 공개 저장소의 읽기 경로 때문이다 (I1 AOMIC 판과 같음).

``coords.json`` 은 I1 ``cc200_coords.json`` 과 같은 키 (``n_roi`` · ``coords_mm`` · ``is_left`` · ``cross_frac`` …) 를 쓴다.
Athena CC200 의 label 은 1–200 중 190 개라 연속이 아니어서 ``mobse.v3.templates.roi_centroids`` 를 쓸 수 없다 — 같은 규칙
(voxel 평균 → affine, 반구 = x < 0) 을 **시계열 열 머리 (Mean_<label>) 순서**로 다시 계산한다.
결정 64: BNT 의 주의 헤드 4 때문에 voxel 수가 가장 작은 parcel 2 개 (label 14 · 41) 를 모든 팔에서 빼 188 영역으로 쓴다.

Usage (h197, venv-i1):
    python scripts/i1_adhd200/build_inputs.py --data-root <D> --out <D>/adhd200/i1data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory  # noqa: E402

DROP_SITES = ("Pittsburgh", "WashU")       # 결정 63 A1
MIN_T = 100                                # 결정 63 A2
ATLAS = "adhd200/nitrc/x/templates/ADHD200_parcellate_200.nii.gz"
N_DROP = 2                                 # 결정 64: voxel 수가 가장 작은 parcel 2 개를 뺀다 (BNT 주의 헤드 4 — 190 → 188)
EXPECT_DROP = (14, 41)                     # 범위 확인에서 잰 값 (45 · 107 voxel). 규칙이 다른 label 을 고르면 멈춘다


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def header_labels(path: Path) -> list:
    head = path.read_text().splitlines()[0].split("\t")
    return [int(h.strip().replace("Mean_", "")) for h in head[2:]]


def smallest_labels(atlas: Path, labels: list, n: int) -> list:
    """voxel 수가 가장 작은 label n 개 (라벨 · 결과와 무관한 규칙). n 번째와 n+1 번째가 같으면 멈춘다."""
    import nibabel as nib
    data = np.asarray(nib.load(str(atlas)).dataobj)
    cnt = sorted((int((data == l).sum()), l) for l in labels)
    if cnt[n - 1][0] == cnt[n][0]:
        raise SystemExit(f"{n} 번째와 {n + 1} 번째 parcel 의 voxel 수가 같다: {cnt[:n + 1]}")
    return sorted(l for _, l in cnt[:n])


def coords(atlas: Path, labels: list, dropped: list) -> dict:
    import nibabel as nib
    img = nib.load(str(atlas))
    data = np.asarray(img.dataobj)
    present = sorted(int(v) for v in np.unique(data) if v > 0)
    if sorted(labels + dropped) != present:
        raise SystemExit(f"쓰는 label + 뺀 label 이 atlas label 과 다르다 ({len(labels)} + {len(dropped)} 대 {len(present)})")
    xyz = np.zeros((len(labels), 3))
    cross = np.zeros(len(labels))
    for i, lab in enumerate(labels):
        ijk = np.argwhere(data == lab)
        mm = nib.affines.apply_affine(img.affine, ijk)
        xyz[i] = nib.affines.apply_affine(img.affine, ijk.mean(0))
        left = xyz[i, 0] < 0
        cross[i] = float(np.mean(mm[:, 0] >= 0) if left else np.mean(mm[:, 0] < 0))
    if np.any(xyz[:, 0] == 0):
        raise SystemExit("x = 0 인 parcel 이 있다 — 반구를 정할 수 없다")
    is_left = xyz[:, 0] < 0
    return {"schema_version": "i1-adhd200-coords-0.1", "atlas_sha256": sha(atlas), "atlas_shape": list(img.shape),
            "atlas_axcodes": "".join(nib.aff2axcodes(img.affine)), "roi_labels": labels, "n_roi": len(labels),
            "n_left": int(is_left.sum()), "n_right": int((~is_left).sum()),
            "cross_hemisphere_voxel_frac": {"max": float(cross.max()), "n_over_0.10": int((cross > 0.10).sum()),
                                            "n_over_0.25": int((cross > 0.25).sum())},
            "min_abs_x_mm": float(np.abs(xyz[:, 0]).min()),
            "coords_mm": np.round(xyz, 3).tolist(), "is_left": is_left.tolist(), "cross_frac": np.round(cross, 3).tolist()}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv[1:])
    D, out = a.data_root, a.out
    npy = out / "abide.npy"
    if npy.exists():
        raise SystemExit(f"이미 존재한다: {npy}")
    from nilearn import __version__ as nilearn_version
    from nilearn.connectome import ConnectivityMeasure

    inv = json.loads((D / "adhd200/scoping_20261014/inventory.json").read_text())["subjects"]
    keep = [s for s in inv if s["y"] is not None and s["T"] >= MIN_T and s["const_roi_all"] == 0
            and (s["const_roi_win_max"] or 0) == 0 and s["site"] not in DROP_SITES]
    keep.sort(key=lambda s: (s["site"], s["id"]))
    labels_all = header_labels(D / keep[0]["path"])
    drop = smallest_labels(D / ATLAS, labels_all, N_DROP)
    if tuple(drop) != EXPECT_DROP:
        raise SystemExit(f"뺄 parcel 이 범위 확인 때와 다르다: {drop} ≠ {EXPECT_DROP}")
    cols = [i for i, l in enumerate(labels_all) if l not in drop]
    labels0 = [labels_all[i] for i in cols]
    series = []
    for s in keep:
        p = D / s["path"]
        if header_labels(p) != labels_all:
            raise SystemExit(f"열 머리 순서가 다르다: {p}")
        series.append(inventory.read_tc(p)[:, cols])       # (시점, ROI 188)
    corr = ConnectivityMeasure(kind="correlation").fit_transform(series)
    pcorr = ConnectivityMeasure(kind="partial correlation").fit_transform(series)
    with np.errstate(divide="ignore"):
        corr, pcorr = np.arctanh(corr), np.arctanh(pcorr)
    corr[np.isinf(corr)] = 0
    pcorr[np.isinf(pcorr)] = 0
    times = np.stack([ts.T[:, :MIN_T] for ts in series])
    y = np.array([s["y"] for s in keep], dtype=int)
    site = np.array([s["site"] for s in keep])
    data = {"timeseires": times, "label": y, "corr": corr, "pcorr": pcorr, "site": site}
    out.mkdir(parents=True, exist_ok=True)
    np.save(npy, data)
    meta = {"schema_version": "i1-adhd200-npy-0.1", "nilearn": nilearn_version, "n_kept": len(keep),
            "rule": "라벨 있음 · 시점 ≥ 100 · 상수 영역 없음 · Pittsburgh · WashU 제외 (결정 63 A1 · A2)",
            "label_rule": "TD = 0, ADHD (복합 · 과잉행동 · 부주의) = 1",
            "label_counts": {"TD(0)": int((y == 0).sum()), "ADHD(1)": int((y == 1).sum())},
            "site_counts": {k: int((site == k).sum()) for k in sorted(set(site))},
            "shapes": {k: list(v.shape) for k, v in data.items()}, "roi_labels": labels0,
            "dropped_labels": drop, "drop_rule": f"voxel 수가 가장 작은 parcel {N_DROP} 개 (결정 64)",
            "source_tar_sha256": sha(D / "adhd200/nitrc/ADHD200_CC200_TCs_filtfix.tar.gz"),
            "sha256": sha(npy), "kept_sub_ids": [str(s["id"]) for s in keep]}
    (out / "abide.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    c = coords(D / ATLAS, labels0, drop)
    (out / "coords.json").write_text(json.dumps(c, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k not in ("kept_sub_ids", "roi_labels")}, ensure_ascii=False))
    print(json.dumps({k: v for k, v in c.items() if k not in ("coords_mm", "is_left", "cross_frac", "roi_labels")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
