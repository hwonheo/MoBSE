#!/usr/bin/env python3
"""PIOP2 확증 (결정 77 · 78) — emomatching 전체 길이 parcel 시계열 추출. 성능 값은 만들지 않는다.

`scripts/h1h2_scope/i3_extract_pilot.py` 의 ``one`` 과 같은 단계 (confounds → nuisance + 차단대역 DCT 동시 회귀 →
Schaefer-100 parcel 평균 → 잔차 → ROI z-score, 원 TR 전체 시계열 · frame 시각 저장) 를 밟되 **dataset 을 인자로 받는다**.
I3 추출 스크립트는 I3 잠금에 들어 있어 고치지 않고 이 파일에 옮겼다 — ``--dataset ds002785`` 로 돌리면 I3 산출과
바이트 동일해야 한다 (smoke 에서 확인).

Usage (h197, 저장소 사본 루트):
    PYTHONPATH=. $VENV/bin/python -B scripts/piop2_confirm/extract.py --root <root> --dataset ds002790 \
        --ids <ids.txt> --out <root>/full_ts
<root> 아래에 ``raw/aomic_wave1`` · ``raw/aomic_wave2`` · ``atlas/<Schaefer-100 2009c>`` 가 있어야 한다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

from mobse.v2 import extract as E
from mobse.v2 import preprocess as P

_spec = importlib.util.spec_from_file_location(
    "wi02", Path(__file__).resolve().parents[1] / "h197" / "10_wi02_extract.py")
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)

ATLAS = "atlas/tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz"


def one(root: Path, dataset: str, subject: str, cache: dict, out: Path) -> dict:
    import nibabel as nib

    paths = W.run_paths(root / "raw/aomic_wave1", root / "raw/aomic_wave2", dataset, subject, "emomatching")
    missing = [k for k, v in paths.items() if not v.is_file()]
    if missing:
        return {"subject": subject, "status": "skipped", "reason": f"파일 없음: {missing}"}
    native_tr = float(json.loads(paths["raw_sidecar"].read_text())["RepetitionTime"])
    confounds = E.read_confounds_tsv(paths["confounds"])
    acompcor = E.select_acompcor(E.read_confounds_metadata(paths["confounds_json"]))
    img = nib.load(str(paths["bold"]))
    n_frames = img.shape[3]
    nuisance, names = E.build_design(confounds, acompcor_names=acompcor, n_frames=n_frames)
    design, names = E.add_stopband(nuisance, names, native_tr=native_tr)
    report = E.summarize_design(design, names, native_tr=native_tr)
    start_sec = W.DISCARDED_BY_SCANNER * native_tr
    fd = confounds["framewise_displacement"]
    run_qc = P.fd_quality(fd)
    window_qc = [P.window_fd_quality(fd, w) for w in P.fixed_windows(native_tr, derivative_start_sec=start_sec)]
    decision = P.qc_decision(run_qc, window_qc, residual_dof=report.residual_dof)

    labels = W.load_atlas_on_grid(root / ATLAS, img, cache)
    brain = np.asanyarray(nib.load(str(paths["mask"])).dataobj) > 0
    try:
        series = W.roi_timeseries(np.asanyarray(img.dataobj), labels, brain)
    except E.ExtractDataError as e:
        return {"subject": subject, "status": "excluded", "reason": str(e)}
    z = E.zscore_rois(E.regress_out(series, design))
    times = P.original_times(n_frames, native_tr, derivative_start_sec=start_sec)
    out.mkdir(parents=True, exist_ok=True)
    np.savez(out / f"{subject}_emomatching.npz", ts=z.astype(np.float32), times=times,
             fd=np.asarray(fd, dtype=float))
    return {"subject": subject, "status": "ok", "dataset": dataset, "native_tr": native_tr, "n_frames": n_frames,
            "start_sec": start_sec, "residual_dof": report.residual_dof,
            "qc_passed_wi02": bool(decision["passed"]), "qc_reasons": decision["all_reasons"],
            "fd_mean": run_qc.get("mean_fd"), "bold_sha12": W.sha256_file(paths["bold"])[:12]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--dataset", required=True, choices=("ds002785", "ds002790"))
    ap.add_argument("--ids", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cache: dict = {}
    rows = []
    t0 = time.perf_counter()
    for s in a.ids.read_text().split():
        r = one(a.root, a.dataset, s, cache, a.out)
        rows.append(r)
        print(json.dumps({k: r.get(k) for k in ("subject", "status", "n_frames", "qc_passed_wi02", "reason")},
                         ensure_ascii=False), flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "manifest.json").write_text(json.dumps(
        {"schema": "piop2-confirm-extract-0.1", "dataset": a.dataset, "seconds": time.perf_counter() - t0,
         "runs": rows}, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
