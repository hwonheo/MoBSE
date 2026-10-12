#!/usr/bin/env python3
"""WI-02 재추출 드라이버 — fMRIPrep derivative → 고정 창 ROI 시계열.

계산은 전부 `mobse/v2/extract.py`·`preprocess.py` 의 순수 함수가 한다. 이 파일은
경로 해석·입출력·manifest 기록만 맡는다. 그래야 정확성을 합성 fixture 로 미리
검증할 수 있다.

경로는 **BIDS entity 로 직접 조립**한다. glob 최신 파일 탐색을 쓰지 않는다 (U20).

사용:
    python scripts/h197/10_wi02_extract.py \
        --wave1-root /path/aomic_wave1 --wave2-root /path/aomic_wave2 \
        --atlas /path/tpl-...dseg.nii.gz \
        --output-dir /path/derivatives_v2 \
        --dataset ds002785 --task emomatching [--limit 5] [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import extract as E  # noqa: E402
from mobse.v2 import preprocess as P  # noqa: E402

#: dataset -> task -> acquisition entity. Wave 1 파일명에서 확인한 값이다.
ACQ = {
    "ds002785": {"emomatching": "seq", "workingmemory": "seq", "restingstate": "mb3"},
    "ds002790": {"emomatching": "seq", "workingmemory": "seq", "restingstate": "seq"},
}
#: 스캐너가 버린 dummy volume 수 (U3, raw sidecar 1,295건 전수 조사).
DISCARDED_BY_SCANNER = 2
SPACE = "MNI152NLin2009cAsym"
N_ROI = 100


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_paths(wave1: Path, wave2: Path, dataset: str, subject: str,
              task: str) -> Dict[str, Path]:
    """BIDS entity 로 경로를 조립한다. 탐색하지 않는다."""
    acq = ACQ[dataset][task]
    stem = f"{subject}_task-{task}_acq-{acq}"
    fmri1 = wave1 / dataset / "fmriprep" / subject / "func"
    fmri2 = wave2 / dataset / "fmriprep" / subject / "func"
    return {
        "bold": fmri2 / f"{stem}_space-{SPACE}_desc-preproc_bold.nii.gz",
        "mask": fmri2 / f"{stem}_space-{SPACE}_desc-brain_mask.nii.gz",
        "confounds": fmri1 / f"{stem}_desc-confounds_regressors.tsv",
        "confounds_json": fmri1 / f"{stem}_desc-confounds_regressors.json",
        "raw_sidecar": wave1 / dataset / "raw" / subject / "func" / f"{stem}_bold.json",
    }


def load_atlas_on_grid(atlas_path: Path, reference, cache: Dict[Tuple, np.ndarray]
                       ) -> np.ndarray:
    """atlas 를 BOLD 격자로 nearest-neighbour 재표본화한다 (격자별 캐시)."""
    import nibabel as nib
    from nilearn.image import resample_to_img

    key = (reference.shape[:3], tuple(np.round(reference.affine.ravel(), 6)))
    if key in cache:
        return cache[key]
    ref = nib.Nifti1Image(np.zeros(reference.shape[:3]), reference.affine)
    resampled = resample_to_img(nib.load(str(atlas_path)), ref,
                                interpolation="nearest",
                                force_resample=True, copy_header=True)
    labels = np.asanyarray(resampled.dataobj).astype(np.int16)
    present = sorted(set(int(x) for x in np.unique(labels)) - {0})
    if present != list(range(1, N_ROI + 1)):
        missing = sorted(set(range(1, N_ROI + 1)) - set(present))
        raise E.ExtractError(
            f"재표본화 후 parcel 결손 {len(missing)}개: {missing[:10]} — "
            "ROI 를 임의 삭제하지 않는다")
    cache[key] = labels
    return labels


def roi_timeseries(bold4d: np.ndarray, labels: np.ndarray,
                   brain_mask: np.ndarray) -> np.ndarray:
    """parcel 평균 시계열 (n_frames, 100)."""
    out = np.empty((bold4d.shape[3], N_ROI), dtype=np.float64)
    for k in range(1, N_ROI + 1):
        selection = (labels == k) & brain_mask
        if not selection.any():
            # 계획서 §3.3 이 "100 ROI 불일치"를 **제외 사유로 명시**한다.
            # 이 subject 의 brain mask 가 해당 parcel 을 덮지 못한 것이므로
            # 코드 결함이 아니라 예상된 자료 조건이다.
            raise E.ExtractDataError(
                f"100 ROI 불일치: parcel {k} 가 이 subject 의 brain mask 안에서 비었다")
        out[:, k - 1] = bold4d[selection].mean(axis=0)
    if not np.all(np.isfinite(out)):
        raise E.ExtractError("ROI 시계열에 비유한값이 있다")
    return out


def process_run(paths: Dict[str, Path], native_tr: float, atlas_path: Path,
                atlas_cache: Dict[Tuple, np.ndarray],
                out_dir: Optional[Path]) -> Dict[str, Any]:
    """한 run 을 재추출한다. 실패는 사유와 함께 돌려준다 (예외로 전체를 멈추지 않는다)."""
    import nibabel as nib

    missing = [k for k, v in paths.items() if not v.is_file()]
    if missing:
        return {"status": "skipped", "reason": f"파일 없음: {missing}"}

    confounds = E.read_confounds_tsv(paths["confounds"])
    metadata = E.read_confounds_metadata(paths["confounds_json"])
    acompcor = E.select_acompcor(metadata)

    img = nib.load(str(paths["bold"]))
    n_frames = img.shape[3]
    nuisance, nuisance_names = E.build_design(confounds, acompcor_names=acompcor,
                                              n_frames=n_frames)
    # 개정 P9: nuisance 와 차단대역 DCT 기저를 한 설계행렬로 동시 회귀한다.
    # DOF 판정과 잔차 계산이 **같은 결합 설계**를 쓰게 여기서 한 번만 만든다.
    design, names = E.add_stopband(nuisance, nuisance_names, native_tr=native_tr)
    report = E.summarize_design(design, names, native_tr=native_tr)

    start_sec = DISCARDED_BY_SCANNER * native_tr
    if not P.supports_analysis_interval(n_frames, native_tr,
                                        derivative_start_sec=start_sec):
        return {"status": "excluded", "reason": "analysis_interval_unsupported",
                "design": report.to_record()}
    P.assert_antialiased(native_tr, lowpass_hz=E.BANDPASS_HIGH_HZ)

    fd = confounds["framewise_displacement"]
    run_qc = P.fd_quality(fd)
    windows = P.fixed_windows(native_tr, derivative_start_sec=start_sec)
    window_qc = [P.window_fd_quality(fd, w) for w in windows]
    # residual_dof 를 넘겨 QC 가 한 곳에서 판정하게 한다. 밖에서 다시 덧붙이면
    # 사유 수집 경로가 둘로 갈린다 (계획서 §3.3 은 "사유를 모두 저장").
    decision = P.qc_decision(run_qc, window_qc, residual_dof=report.residual_dof)

    if not decision["passed"]:
        return {"status": "excluded",
                "reason": decision["all_reasons"],
                "primary_reason": decision["primary_reason"],
                "design": report.to_record(), "run_qc": run_qc}

    labels = load_atlas_on_grid(atlas_path, img, atlas_cache)
    brain = np.asanyarray(nib.load(str(paths["mask"])).dataobj) > 0
    series = roi_timeseries(np.asanyarray(img.dataobj), labels, brain)
    residual = E.regress_out(series, design)
    standardized = E.zscore_rois(residual)
    original = P.original_times(n_frames, native_tr, derivative_start_sec=start_sec)
    gridded = P.resample_to_grid(standardized, original, P.target_times())
    cut = P.cut_windows(gridded)

    written: List[Dict[str, Any]] = []
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for window, block in zip(windows, cut):
            name = f"{paths['bold'].name.split('_space-')[0]}_win-{window.index}.npy"
            target = out_dir / name
            np.save(target, block.astype(np.float32))
            written.append({"path": str(target), "sha256": sha256_file(target),
                            "shape": list(block.shape),
                            "start_sec": window.start_sec,
                            "source_frame_range": list(window.source_frame_range)})

    return {
        "status": "ok",
        "native_tr": native_tr,
        "n_frames": n_frames,
        "derivative_start_sec": start_sec,
        "design": report.to_record(),
        "run_qc": run_qc,
        "window_qc": window_qc,
        "qc_decision": decision,
        "windows": written,
        "bold_sha256": sha256_file(paths["bold"]),
        "confounds_sha256": sha256_file(paths["confounds"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave1-root", type=Path, required=True)
    ap.add_argument("--wave2-root", type=Path, required=True)
    ap.add_argument("--atlas", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--dataset", required=True, choices=sorted(ACQ))
    ap.add_argument("--task", required=True)
    ap.add_argument("--native-tr", type=float, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help=".npy 를 쓰지 않고 검증만 한다")
    args = ap.parse_args()

    if args.task not in ACQ[args.dataset]:
        print(f"[error] {args.dataset} 에 task {args.task} 가 없다", file=sys.stderr)
        return 1
    for path in (args.wave1_root, args.wave2_root, args.atlas):
        if not path.exists():
            print(f"[error] 경로 없음: {path}", file=sys.stderr)
            return 1

    subjects = sorted(
        p.name for p in (args.wave2_root / args.dataset / "fmriprep").glob("sub-*")
        if p.is_dir())
    if args.limit:
        subjects = subjects[: args.limit]
    if not subjects:
        print("[error] subject 디렉터리가 0개다", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.output_dir / f"wi02_{args.dataset}_{args.task}.jsonl"
    atlas_cache: Dict[Tuple, np.ndarray] = {}
    counts = {"ok": 0, "excluded": 0, "skipped": 0, "error": 0}
    started = time.time()

    with manifest.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "record_type": "header",
            "schema_version": "wi02-extract-0.2",  # 0.2: P9 band-pass 적용, P10 DOF
            "dataset": args.dataset, "task": args.task,
            "native_tr": args.native_tr,
            "discarded_by_scanner": DISCARDED_BY_SCANNER,
            "space": SPACE,
            "atlas": str(args.atlas), "atlas_sha256": sha256_file(args.atlas),
            "analysis_interval_sec": [P.ANALYSIS_START, P.ANALYSIS_END],
            "bandpass_hz": [E.BANDPASS_LOW_HZ, E.BANDPASS_HIGH_HZ],
            "filter_method": "simultaneous_regression_dct_stopband (P9)",
            "dry_run": bool(args.dry_run),
        }, ensure_ascii=False) + "\n")

        for i, subject in enumerate(subjects, start=1):
            paths = run_paths(args.wave1_root, args.wave2_root, args.dataset,
                              subject, args.task)
            record: Dict[str, Any] = {
                "record_type": "run",
                "run_key": f"{args.dataset}/{subject}/na/{args.task}/na/"
                           f"{ACQ[args.dataset][args.task]}",
                "canonical_subject": f"{args.dataset}:{subject}",
            }
            try:
                result = process_run(
                    paths, args.native_tr, args.atlas, atlas_cache,
                    None if args.dry_run else args.output_dir / subject)
            except E.ExtractDataError as exc:
                # 계획서가 미리 정해 둔 자료 조건 — 결함이 아니라 예상된 제외다.
                result = {"status": "excluded",
                          "reason": [f"data_condition: {exc}"],
                          "primary_reason": f"data_condition: {type(exc).__name__}"}
            except Exception as exc:  # 한 run 의 실패가 전체를 멈추지 않게
                result = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
            record.update(result)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            if i % 20 == 0 or i == len(subjects):
                elapsed = time.time() - started
                print(f"  … {i}/{len(subjects)}  {counts}  {elapsed:.0f}s", flush=True)

    print(f"[done] {counts}  manifest={manifest}")
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
