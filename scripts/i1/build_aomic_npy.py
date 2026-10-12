#!/usr/bin/env python3
"""I1 AOMIC 팔 입력 — v3 추출 창을 공개 모델 입력 형식 (``abide.npy`` 와 같은 키) 으로 묶는다 (결정 43, 잠금 초안 §3.6 (가)).

* 표본 = **창** (30 시점 × Schaefer-100). 대상 = v1 main pool 126 명 × 2 task × 창 4 = 1,008 창.
  창 목록은 ``derivatives_v3/windows_piop1.jsonl`` 이고, 창 파일마다 그 ``data_sha256`` 과 대조한다.
* label: emomatching = 0 · workingmemory = 1 (v1 과 같음). ``site`` 에는 피험자 id 를 넣는다 (저장소는 분할에만 쓰는데 wrapper 가 분할을 바꾼다).
* ``corr``: ABIDE 표준 파일과 같은 방식 — nilearn ``ConnectivityMeasure(kind="correlation")`` (기본 Ledoit-Wolf) → arctanh → inf 를 0 으로.
* ``timeseires``: (창, ROI, 시점) — 창 파일 (시점, ROI) 을 전치.
* fold: **v1 outer fold 그대로** (``splits_piop1_p7/folds.json``, split_hash ``ace5f4a4…``) — MoBSE 팔 (v3) 과 같은 test 피험자.
  안쪽 val = train 피험자의 10 % (결정 42 와 같은 비율, 피험자 단위로 묶음). 출력 fold 는 ``make_folds.py`` 와 같은 형식 (표본 index).
* 좌표: Schaefer-100 2009c atlas 에서 v3 ``roi_centroids`` 로 (N2 spin 용, ``cc200_coords.json`` 과 같은 키).

산출 (``--out`` 아래): ``abide.npy`` · ``samples.jsonl`` (표본 index → 피험자 · task · 창 · run) · ``folds.json`` · ``coords.json`` · ``build.json``.
이미 있으면 멈춘다.

Usage (h197, venv-i1):
    PYTHONPATH=. python scripts/i1/build_aomic_npy.py --deriv <derivatives_v3> \\
        --atlas <…Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz> --out <i1/data/aomic_win>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

TASK_LABEL = {"emomatching": 0, "workingmemory": 1}
VAL_SEED = 20261005
VAL_FRAC = 0.10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deriv", required=True, type=Path)
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv[1:])
    if (a.out / "abide.npy").exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {a.out}", file=sys.stderr)
        return 2
    from nilearn import __version__ as nilearn_version
    from nilearn.connectome import ConnectivityMeasure
    from mobse.v3.templates import roi_centroids

    folds_path = a.deriv / "splits_piop1_p7/folds.json"
    v1 = json.loads(folds_path.read_text())
    main_subj = list(v1["main_pool"]["subjects"])
    if len(main_subj) != 126:
        raise SystemExit(f"main pool 이 126 명이 아니다: {len(main_subj)}")
    win_path = a.deriv / "windows_piop1.jsonl"
    wins = [json.loads(line) for line in win_path.read_text().splitlines() if line.strip()]
    by_key = {}
    for w in wins:
        _, sub, _, task, _, acq = w["run_key"].split("/")
        by_key.setdefault((f"ds002785:{sub}", task), []).append((w, sub, acq))

    samples, series = [], []
    for subj in main_subj:
        for task in ("emomatching", "workingmemory"):
            rows = sorted(by_key.get((subj, task), []), key=lambda r: r[0]["window_key"])
            if len(rows) != 4:
                raise SystemExit(f"{subj} {task}: 창이 4 개가 아니다 ({len(rows)})")
            for w, sub, acq in rows:
                k = int(w["window_key"].rsplit("#win-", 1)[1])
                f = a.deriv / sub / f"{sub}_task-{task}_acq-{acq}_win-{k}.npy"
                if sha256(f) != w["data_sha256"]:
                    raise SystemExit(f"sha 불일치: {f}")
                x = np.load(f).astype(np.float64)
                if x.shape != (30, 100):
                    raise SystemExit(f"모양이 (30, 100) 이 아니다: {f} {x.shape}")
                samples.append({"index": len(samples), "subject": subj, "task": task, "label": TASK_LABEL[task],
                                "window": k, "run_key": w["run_key"], "window_key": w["window_key"]})
                series.append(x)

    corr = ConnectivityMeasure(kind="correlation").fit_transform(series)
    with np.errstate(divide="ignore"):
        corr = np.arctanh(corr)
    corr[np.isinf(corr)] = 0
    ts = np.stack([s.T for s in series])                         # (창, ROI, 시점)
    label = np.array([s["label"] for s in samples])
    site = np.array([s["subject"] for s in samples])

    subj_of = np.array([s["subject"] for s in samples])
    folds = []
    for f in v1["outer_folds"]:
        test_s, train_s = sorted(f["test_subjects"]), sorted(f["train_subjects"])
        rng = np.random.Generator(np.random.PCG64(int(np.random.SeedSequence([VAL_SEED, f["outer_fold"]]).generate_state(1)[0])))
        val_s = sorted(rng.choice(train_s, size=int(round(VAL_FRAC * len(train_s))), replace=False).tolist())
        fit_s = sorted(set(train_s) - set(val_s))
        idx = lambda ss: np.flatnonzero(np.isin(subj_of, ss)).tolist()   # noqa: E731
        fd = {"fold": f["outer_fold"], "train": idx(fit_s), "val": idx(val_s), "test": idx(test_s),
              "n_subjects": [len(fit_s), len(val_s), len(test_s)], "val_subjects": val_s, "test_subjects": test_s}
        fd["n"] = [len(fd["train"]), len(fd["val"]), len(fd["test"])]
        folds.append(fd)
    assert sorted(i for fd in folds for i in fd["test"]) == list(range(len(samples)))

    a.out.mkdir(parents=True, exist_ok=True)
    np.save(a.out / "abide.npy", {"timeseires": ts, "corr": corr, "label": label, "site": site}, allow_pickle=True)
    with (a.out / "samples.jsonl").open("w") as fh:
        for s in samples:
            fh.write(json.dumps(s) + "\n")
    npy_sha = sha256(a.out / "abide.npy")
    (a.out / "folds.json").write_text(json.dumps({
        "schema_version": "i1-folds-0.1", "draw": 0, "source": "v1 outer folds (splits_piop1_p7)",
        "v1_split_hash": v1["split_hash"], "val_seed": VAL_SEED, "val_frac": VAL_FRAC, "group": "subject",
        "npy_sha256": npy_sha, "n_subj": len(samples), "unit": "window", "folds": folds}, indent=1))
    coords, is_left = roi_centroids(a.atlas)
    (a.out / "coords.json").write_text(json.dumps({
        "schema_version": "i1-schaefer-coords-0.1", "atlas_sha256": sha256(a.atlas), "n_roi": len(coords),
        "n_left": int(is_left.sum()), "coords_mm": np.round(coords, 3).tolist(), "is_left": is_left.tolist()}, indent=1))
    build = {"schema_version": "i1-aomic-npy-0.1", "nilearn": nilearn_version, "n_samples": len(samples),
             "n_subjects": len(main_subj), "label_counts": {str(k): int((label == k).sum()) for k in (0, 1)},
             "shapes": {"timeseires": list(ts.shape), "corr": list(corr.shape)}, "npy_sha256": npy_sha,
             "windows_manifest_sha256": sha256(win_path), "v1_folds_sha256": sha256(folds_path),
             "fold_sizes": [fd["n"] for fd in folds], "fold_subjects": [fd["n_subjects"] for fd in folds]}
    (a.out / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=1))
    print(json.dumps(build, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
