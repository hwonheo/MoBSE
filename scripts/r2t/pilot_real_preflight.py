#!/usr/bin/env python3
"""R2T T1 실제 자료 pilot 사전 점검 (결정 91 후보) — 모델 적합 · 평가 없음. 실제 값은 점검에 필요한 만큼만 읽는다.

점검: (A) pilot 31 명 명단 · 파일-사람 대응 (B) 입력 파일 sha256 대 I3 잠금 (C) 원 BOLD sha 대 추출 manifest
(D) 추출 코드 sha 대 I3 잠금 (E) 값 수준 전처리 확인 (shape · 유한 · run 단위 z-score · 시각 격자)
(F) 분할 · inner · mask 누출 점검 (G) 자원.  결과는 --out (새 파일) 에 쓴다. 문제 하나라도 있으면 exit 1.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import r2t_lib as R  # noqa: E402
import t1  # noqa: E402


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs/r2t/t1_pilot_real.json")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"덮어쓰지 않는다: {a.out}")
    cfg = t1.load_config(a.config)
    A = ROOT / "data/h1h2_scope/aomic"
    lock = json.loads((ROOT / "results/i3/locks/lock.json").read_text())
    lf = {k: v for g in lock["data"]["groups"].values() for k, v in g["files"].items()}
    P, rep = [], {"config": str(a.config.relative_to(ROOT)), "config_sha256": sha(a.config),
                  "i3_lock": {"path": "results/i3/locks/lock.json", "lock_hash": lock["lock_hash"], "sha256": sha(ROOT / "results/i3/locks/lock.json")}}
    # (A) 명단
    subs = t1.pilot_subjects(cfg, ROOT)
    ids_txt = sorted(x.strip() for x in (A / "pilot_ids.txt").read_text().split() if x.strip())
    ids_txt = sorted(x.split(":")[-1] for x in ids_txt)
    man = {r["subject"]: r for r in json.loads((A / "full_ts/manifest.json").read_text())["runs"]}
    rep["A_subjects"] = {"n": len(subs), "pilot_ids_txt_equal": subs == ids_txt, "in_manifest": sum(s in man for s in subs)}
    if len(subs) != 31 or subs != ids_txt or rep["A_subjects"]["in_manifest"] != 31:
        P.append("A: pilot 명단 불일치")
    # (B) 입력 파일 sha 대 I3 잠금
    files = {"splits/folds.json": None, "full_ts/manifest.json": None}
    for s in subs:
        files[f"full_ts/{s}_emomatching.npz"] = None
        for i in range(4):
            files[f"rest_win/derivatives_v3/{s}/{s}_task-restingstate_acq-mb3_win-{i}.npy"] = None
    mism, missing = [], []
    for rel in files:
        p = A / rel
        if not p.is_file():
            missing.append(rel)
            continue
        files[rel] = sha(p)
        if rel not in lf:
            missing.append(f"I3 잠금에 없음: {rel}")
        elif lf[rel] != files[rel]:
            mism.append(rel)
    tsv = A / "atlas/tpl-MNI152NLin2009cAsym_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.tsv"
    rep["B_input_hashes"] = {"n_files": len(files), "n_match_i3_lock": len(files) - len(mism) - len(missing), "mismatch": mism, "missing": missing,
                             "atlas_tsv_sha256": sha(tsv)}
    if mism or missing:
        P.append(f"B: 입력 sha 불일치 {len(mism)} · 누락 {len(missing)}")
    # (C) 원 BOLD sha 대 manifest
    spec = importlib.util.spec_from_file_location("wi02", ROOT / "scripts/h197/10_wi02_extract.py")
    W = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(W)
    bold_ok, bold_bad = 0, []
    for s in subs:
        paths = W.run_paths(A / "raw/aomic_wave1", A / "raw/aomic_wave2", "ds002785", s, "emomatching")
        r = man[s]
        cond = r["status"] == "ok" and r["native_tr"] == 2.0 and r["n_frames"] == 135 and r["qc_passed_wi02"] and r["start_sec"] == 4.0
        if paths["bold"].is_file() and sha(paths["bold"])[:12] == r["bold_sha12"] and cond:
            bold_ok += 1
        else:
            bold_bad.append(s)
    rep["C_raw_bold"] = {"n_match_manifest_sha12_and_fields": bold_ok, "bad": len(bold_bad)}
    if bold_bad:
        P.append(f"C: 원 BOLD · manifest 조건 불일치 {len(bold_bad)} 명")
    # (D) 추출 코드
    code = {}
    for rel in ("mobse/v2/extract.py", "mobse/v2/preprocess.py", "scripts/h197/10_wi02_extract.py", "scripts/h1h2_scope/i3_extract_pilot.py"):
        cur = sha(ROOT / rel)
        code[rel] = {"current": cur, "i3_lock": lock["code"]["files"].get(rel), "match": cur == lock["code"]["files"].get(rel)}
    rep["D_extraction_code"] = code
    if not all(v["match"] for v in code.values()):
        P.append("D: 추출 코드 sha 가 I3 잠금과 다름")
    # (E) 값 수준
    tm, tsd, tstep, tstart, rshape, rfin, rmean = [], [], [], [], set(), True, []
    for s in subs:
        z = np.load(A / f"full_ts/{s}_emomatching.npz")
        x = z["ts"].astype(float)
        if x.shape != (135, 100) or not np.all(np.isfinite(x)):
            P.append(f"E: {s} task shape · 유한 실패")
        tm.append(np.abs(x.mean(0)).max())
        tsd.append(np.abs(x.std(0) - 1).max())
        tt = z["times"]
        tstep.append(float(np.unique(np.round(np.diff(tt), 6)).tolist()[0]) if len(np.unique(np.round(np.diff(tt), 6))) == 1 else -1)
        tstart.append(float(tt[0]))
        rw = [np.load(A / f"rest_win/derivatives_v3/{s}/{s}_task-restingstate_acq-mb3_win-{i}.npy").astype(float) for i in range(4)]
        for w in rw:
            rshape.add(w.shape)
            rfin &= bool(np.all(np.isfinite(w)))
        rmean.append(float(np.abs(np.concatenate(rw).mean(0)).max()))
    rep["E_values"] = {"task_max_abs_roi_mean": max(tm), "task_max_abs_roi_sd_minus_1": max(tsd), "task_time_step_s": sorted(set(tstep)),
                       "task_first_time_s": sorted(set(tstart)), "rest_shapes": sorted(map(str, rshape)), "rest_all_finite": rfin,
                       "rest_max_abs_roi_mean_over_4_windows": max(rmean),
                       "reading": "task: run 단위 ROI z-score (평균 0 · SD 1, 전체 135 frame) · 2 s 격자. rest: 원 TR 0.75 s run 단위 z-score 뒤 2 s 격자 선형 보간 · 4 창 (120 frame) — 창 평균은 정확히 0 이 아님"}
    if max(tm) > 1e-4 or max(tsd) > 1e-3 or sorted(set(tstep)) != [2.0] or rshape != {(30, 100)} or not rfin:
        P.append("E: 값 수준 전처리 확인 실패")
    # (F) 분할 · 누출
    left = t1.left_from_atlas_tsv(tsv)
    masks = R.make_masks(100, cfg["mask"]["frac"], cfg["mask"]["n_masks"], seed=cfg["mask"]["seed"], left=left)
    folds = t1.person_folds(subs, cfg["split"]["n_folds"], cfg["split"]["fold_seed"])
    flat = [s for f in folds for s in f]
    inner = []
    for f in folds:
        train = sorted(set(subs) - set(f))
        itr, iva = R.subject_split(train, cfg["split"]["inner_val_frac"], seed=cfg["split"]["inner_seed"])
        ok = not (set(itr) & set(f)) and not (set(iva) & set(f)) and not (set(itr) & set(iva)) and sorted(itr + iva) == train
        inner.append({"test": f, "inner_val": iva, "n_inner_train": len(itr), "disjoint": ok})
    rep["F_split"] = {"fold_sizes": [len(f) for f in folds], "each_person_once": sorted(flat) == subs and len(set(flat)) == 31,
                      "fold_seed": cfg["split"]["fold_seed"], "inner_seed": cfg["split"]["inner_seed"], "mask_seed": cfg["mask"]["seed"],
                      "n_masks": len(masks), "mask_sizes": sorted({len(m) for m in masks}),
                      "mask_hemisphere_balanced": all(int(left[m].sum()) == len(m) // 2 for m in masks),
                      "masks": [m.tolist() for m in masks], "folds": inner, "atlas_left": int(left.sum())}
    if not rep["F_split"]["each_person_once"] or not all(x["disjoint"] for x in inner) or rep["F_split"]["fold_sizes"] != [6, 6, 6, 6, 7] and sorted(rep["F_split"]["fold_sizes"]) != [6, 6, 6, 6, 7]:
        P.append("F: 분할 · inner 점검 실패")
    # (G) 자원
    rep["G_resources"] = {"host": platform.node(), "cpu": os.cpu_count(), "loadavg": os.getloadavg(), "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
                          "estimate": "합성 같은 규모 F4R (oracle 포함) 257 s · 299 MB [측정, 합성]; oracle 제외라 더 짧을 것 [추정]"}
    rep["problems"] = P
    rep["ok"] = not P
    rep["input_file_sha256"] = files
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("input_file_sha256", "F_split")}, ensure_ascii=False, indent=1)[:3000])
    print("F_split:", {k: v for k, v in rep["F_split"].items() if k not in ("masks", "folds")})
    return 0 if not P else 1


if __name__ == "__main__":
    raise SystemExit(main())
