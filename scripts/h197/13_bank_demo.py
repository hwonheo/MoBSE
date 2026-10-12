#!/usr/bin/env python3
"""WI-04 소규모 시연 — 실제 rest 창으로 frozen transform 과 graph bank 를 적합한다.

**이것은 주분석이 아니다.** pilot 분리 전이고 fold 도 없으므로, 여기서 나오는
bank 는 어떤 결과에도 쓰이지 않는다. 목적은 하나다 — 계획서 §5 의 파이프라인이
합성 fixture 가 아니라 **실제 BOLD 에서 끝까지 도는지**, 그리고 bank 가 만족해야
할 성질(대칭·유한·비음·self-loop 정규화 일치)이 실자료에서도 성립하는지 확인한다.

joint ROI permutation null 도 같이 만들어 T05 가 요구하는 "spectrum 과 bank 거리
보존"을 실자료에서 확인한다.

사용:
    python scripts/h197/13_bank_demo.py \
        --manifest /tmp/wi02_rest/wi02_ds002785_restingstate.jsonl \
        --report /tmp/bank_demo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2.cohort import read_extract_manifest  # noqa: E402
from mobse.v2.features import fit_transform_on_training_rest, stack_window_features  # noqa: E402
from mobse.v2.templates import (  # noqa: E402
    bank_seed,
    build_bank,
    make_null_bank,
)
from mobse.v2.templates import NULL_SEED_PRIMARY  # noqa: E402


def load_rest_windows(manifest: Path) -> tuple[List[np.ndarray], List[str]]:
    """QC 를 통과한 rest run 의 창 배열을 모은다."""
    _header, runs = read_extract_manifest(manifest)
    windows: List[np.ndarray] = []
    subjects: List[str] = []
    for run in runs:
        if run.get("status") != "ok":
            continue
        subject = str(run["canonical_subject"])
        for entry in run.get("windows", []):
            array = np.load(entry["path"])
            windows.append(np.asarray(array, dtype=np.float64))
            subjects.append(subject)
    return windows, subjects


def bank_properties(templates: np.ndarray) -> Dict[str, Any]:
    """bank 가 만족해야 할 성질을 수치로 확인한다 (T05)."""
    return {
        "shape": list(templates.shape),
        "all_finite": bool(np.all(np.isfinite(templates))),
        "symmetric_max_asymmetry": float(
            np.max(np.abs(templates - np.transpose(templates, (0, 2, 1))))),
        "min_value": float(templates.min()),
        "nonnegative": bool(templates.min() >= 0.0),
        "row_sum_min": float(templates.sum(axis=2).min()),
        "row_sum_max": float(templates.sum(axis=2).max()),
        "diagonal_min": float(np.min([np.diag(t).min() for t in templates])),
        "offdiag_density": [
            float((t[~np.eye(t.shape[0], dtype=bool)] > 0).mean()) for t in templates
        ],
        "spectral_radius": [float(np.abs(np.linalg.eigvalsh(t)).max()) for t in templates],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    windows, subjects = load_rest_windows(args.manifest)
    if not windows:
        print("[error] QC 를 통과한 rest 창이 없다", file=sys.stderr)
        return 1
    unique_subjects = sorted(set(subjects))
    print(f"[load] 창 {len(windows)}개, subject {len(unique_subjects)}명")

    correlations, features = stack_window_features(windows)
    print(f"[feat] correlations {correlations.shape}, Fisher-z {features.shape}")

    transform = fit_transform_on_training_rest(
        features, unique_subjects, allowed_subjects=set(unique_subjects))
    pca_features = transform.transform(features)
    print(f"[pca ] {pca_features.shape}  fingerprint {transform.fingerprint()[:16]}…")

    seed = bank_seed(0, 9)  # outer fold 0 의 outer fit 규약
    bank = build_bank(correlations, pca_features, unique_subjects, seed=seed, k=args.k)
    null = make_null_bank(bank, seed=NULL_SEED_PRIMARY)
    print(f"[bank] seed {seed}, K={bank.k}, fingerprint {bank.fingerprint()[:16]}…")

    real = bank_properties(bank.templates)
    fake = bank_properties(null.templates)

    # T05 — joint permutation 은 spectrum 을 보존해야 한다.
    spectrum_diff = float(np.max(np.abs(
        np.array(real["spectral_radius"]) - np.array(fake["spectral_radius"]))))
    assignment_counts = np.bincount(bank.assignment, minlength=args.k).tolist()

    report = {
        "purpose": "WI-04 파이프라인의 실자료 동작 확인. 주분석이 아니며 결과에 쓰이지 않는다.",
        "manifest": str(args.manifest),
        "n_windows": len(windows),
        "n_subjects": len(unique_subjects),
        "correlations_shape": list(correlations.shape),
        "features_shape": list(features.shape),
        "pca_shape": list(pca_features.shape),
        "transform_fingerprint": transform.fingerprint(),
        "bank_seed": seed,
        "bank_fingerprint": bank.fingerprint(),
        "null_seed": NULL_SEED_PRIMARY,
        "null_fingerprint": null.fingerprint(),
        "cluster_sizes": assignment_counts,
        "bank_properties": real,
        "null_properties": fake,
        "spectrum_max_abs_diff": spectrum_diff,
        "density_stats": bank.density_stats,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    print(f"[prop] 대칭 최대 오차 {real['symmetric_max_asymmetry']:.2e}, "
          f"최소값 {real['min_value']:.4f}, 비음 {real['nonnegative']}")
    print(f"[prop] off-diagonal 밀도 {[round(d, 4) for d in real['offdiag_density']]}")
    print(f"[prop] spectral radius 실제 {[round(v, 4) for v in real['spectral_radius']]}")
    print(f"[prop] spectral radius null {[round(v, 4) for v in fake['spectral_radius']]}")
    print(f"[T05 ] spectrum 최대 차이 {spectrum_diff:.3e} (joint permutation 은 보존해야 한다)")
    print(f"[bank] 군집 크기 {assignment_counts}")
    print(f"보고서: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
