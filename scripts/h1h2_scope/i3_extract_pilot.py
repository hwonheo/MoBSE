#!/usr/bin/env python3
"""I3 범위 확인 (결정 67 ①) — pilot 31 명 emomatching 을 **전체 길이** parcel 시계열로 다시 뽑는다.

잠긴 추출 (WI-02, ``scripts/h197/10_wi02_extract.py`` · ``mobse.v2.extract``) 과 같은 단계를 그대로 밟는다:
confounds → nuisance 설계 + 차단대역 DCT 동시 회귀 (0.008–0.2 Hz, 개정 P9) → Schaefer-100 parcel 평균 → 잔차 →
ROI z-score. 다른 점은 하나 — 60 s 창 4 개로 자르지 않고 **원 TR 의 전체 시계열과 frame 시각**을 저장한다
(과제 블록 30 s 에 맞춘 창을 나중에 자르기 위해). QC 판정 (run · 60 s 창 기준) 은 기록만 하고 거르지 않는다.

잠긴 코드는 import 만 한다. 산출은 저장소 밖 ``data/`` (gitignore).

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/i3_extract_pilot.py --root data/h1h2_scope/aomic \
        --ids data/h1h2_scope/aomic/pilot_ids.txt --out data/h1h2_scope/aomic/full_ts
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


def one(root: Path, subject: str, cache: dict, out: Path) -> dict:
    import nibabel as nib

    paths = W.run_paths(root / "raw/aomic_wave1", root / "raw/aomic_wave2", "ds002785", subject, "emomatching")
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
    return {"subject": subject, "status": "ok", "native_tr": native_tr, "n_frames": n_frames,
            "start_sec": start_sec, "residual_dof": report.residual_dof,
            "qc_passed_wi02": bool(decision["passed"]), "qc_reasons": decision["all_reasons"],
            "fd_mean": run_qc.get("mean_fd"), "bold_sha12": W.sha256_file(paths["bold"])[:12]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--ids", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cache: dict = {}
    rows = []
    t0 = time.perf_counter()
    for s in a.ids.read_text().split():
        r = one(a.root, s, cache, a.out)
        rows.append(r)
        print(json.dumps({k: r.get(k) for k in ("subject", "status", "n_frames", "qc_passed_wi02", "reason")},
                         ensure_ascii=False), flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "manifest.json").write_text(json.dumps(
        {"schema": "h1h2-scope-i3-extract-0.1", "seconds": time.perf_counter() - t0, "runs": rows},
        ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
