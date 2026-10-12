#!/usr/bin/env python3
"""I1 MoBSE 팔 (외부 prior 형) — AOMIC 만 (결정 43 · 44).

* **mean (등변) 구조** — 결정 44: 새 학습 없이 v1 결과를 쓴다. 원판 = v1 main OOF 의 A, null = C (순열 prior) —
  null seed 1729 (main) 과 1730–1733 (WI-09) 이 k0–k4. model seed 42–44 · outer fold 0–4. spin · rewire 는 v1 에 없다.
* **embedding 구조** — v3 잠금 (``c0c8ed77db50``) 의 CLI 를 그대로 부른다. 원판 = v3 본 실행 N=100 의 A,
  null = C 의 ``permutation`` · ``spin`` · ``rewire`` 각 index 0–4 (K=5) × model seed 42–44 (R=3) × outer fold 0–4.
  이미 있는 fit (본 실행 outer 의 C = permutation 0, G-c 의 fold 0 · seed 42) 은 다시 돌리지 않고 쓴다.
  설정은 본 실행의 구조별 선택 (``select/o{o}/selection_embedding.json``) · outer fit 표시 inner 9 — ``run_t4.py`` 와 같은 명령.

분석 배치로 옮길 때 cond 이름: ``orig`` · ``prior_permutation`` · ``prior_spin`` · ``prior_rewire`` (공개 모델의 n0–n3 과 다른 null 이라
이름을 달리 둔다). 예측은 창 단위 ``window_key`` 로 AOMIC ``samples.jsonl`` 의 index 에 맞춘다.

하위 명령:
    collect-mean      --main <v1 main_oof root> --sens <WI-09 root> --samples <samples.jsonl> --out <analysis root>
    plan-embedding    --v3-root <v3 본 실행 root> --out <work root>            (돌릴 fit 목록만 쓴다)
    run-embedding     --v3-root … --data-root <D> --out <work root> [--only N] [--k 4] [--device cuda]
    collect-embedding --v3-root … --work <work root> --samples … --out <analysis root>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (42, 43, 44)
N_OUTER = 5
K = 5
KINDS = ("permutation", "spin", "rewire")
V1_NULL_SEEDS = (1729, 1730, 1731, 1732, 1733)
OUTER_INNER_FOLD = 9
GC_OUTER_FOLD, GC_SEED = 0, 42
THREAD_ENV = {k: "2" for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
V3_CONFIG = ROOT / "configs/exploratory_v2/main.yaml"


def key_index(samples_path: Path) -> dict:
    return {json.loads(x)["window_key"]: json.loads(x)["index"]
            for x in samples_path.read_text().splitlines() if x.strip()}


def convert(src: Path, dst: Path, kidx: dict, expect: dict) -> int:
    """v1 · v3 window_predictions.jsonl → 분석 배치 predictions.jsonl. expect 는 표시값 (cell 등) 대조."""
    rows = [json.loads(x) for x in src.read_text().splitlines() if x.strip()]
    for k, v in expect.items():
        bad = {r.get(k) for r in rows} - {v}
        if bad:
            raise SystemExit(f"{src}: {k} 가 {v} 가 아니다 ({bad})")
    if any(r["scope"] != "outer_test" for r in rows):
        raise SystemExit(f"{src}: outer_test 가 아닌 행이 있다")
    dst.mkdir(parents=True, exist_ok=True)
    with (dst / "predictions.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps({"subject_index": kidx[r["window_key"]], "label": int(r["truth"]),
                                 "p1": float(r["p_class1"])}) + "\n")
    (dst / "source.json").write_text(json.dumps({"source": str(src)}, ensure_ascii=False))
    return len(rows)


def collect_mean(a) -> int:
    kidx = key_index(a.samples)
    n = 0
    for o in range(N_OUTER):
        for s in SEEDS:
            n += convert(a.main / "fits/outer" / f"o{o}" / f"A_s{s}" / "window_predictions.jsonl",
                         a.out / "mobse_mean/orig/k0" / f"r{s}" / f"f{o}", kidx, {"cell": "A", "model_seed": s})
            for k, ns in enumerate(V1_NULL_SEEDS):
                base = a.main / "fits/outer" if ns == 1729 else a.sens / "fits" / f"s{ns}"
                n += convert(base / f"o{o}" / f"C_s{s}" / "window_predictions.jsonl",
                             a.out / "mobse_mean/prior_permutation" / f"k{k}" / f"r{s}" / f"f{o}", kidx,
                             {"cell": "C", "model_seed": s})
    print(f"mean: 창 예측 {n} 행 → {a.out / 'mobse_mean'}")
    return 0


def existing_v3(v3: Path, kind: str, idx: int, o: int, s: int):
    """이미 있는 v3 fit 의 폴더 (없으면 None)."""
    if (kind, idx) == ("permutation", 0):
        return v3 / "outer/embedding/n100" / f"o{o}" / f"C_s{s}"
    if (o, s) == (GC_OUTER_FOLD, GC_SEED):
        return v3 / "gc/embedding" / f"C_{kind}{idx:02d}"
    return None


def plan(v3: Path, work: Path):
    jobs = []
    for kind in KINDS:
        for idx in range(K):
            for o in range(N_OUTER):
                for s in SEEDS:
                    if existing_v3(v3, kind, idx, o, s) is None:
                        jobs.append({"kind": kind, "idx": idx, "outer": o, "seed": s,
                                     "out": str(work / "fits" / f"C_{kind}{idx:02d}" / f"o{o}" / f"s{s}")})
    return jobs


def fit_cmd(a, job: dict) -> list:
    d = a.data_root / "derivatives_v3"
    sel = a.v3_root / "select" / f"o{job['outer']}" / "selection_embedding.json"
    cfg_id = json.loads(sel.read_text())["config_id"]
    cmd = [sys.executable, "-B", "-m", "mobse.v3.cli", "fit", "--config", str(V3_CONFIG),
           "--splits", str(d / "splits_piop1_p7/folds.json"), "--subjects", str(d / "cohort_piop1/subjects.jsonl"),
           "--windows", str(d / "windows_piop1.jsonl"), "--rest-manifest", str(d / "wi02_ds002785_restingstate.jsonl"),
           "--task-manifests", str(d / "wi02_ds002785_emomatching.jsonl"), str(d / "wi02_ds002785_workingmemory.jsonl"),
           "--cell", "C", "--roi-structure", "embedding", "--n-train-level", "100",
           "--outer-fold", str(job["outer"]), "--inner-fold", str(OUTER_INNER_FOLD), "--config-id", str(cfg_id),
           "--model-seed", str(job["seed"]), "--device", a.device, "--output-dir", job["out"], "--selection", str(sel)]
    if (job["kind"], job["idx"]) != ("permutation", 0):
        cmd += ["--null-kind", job["kind"], "--null-index", str(job["idx"])]
        if job["kind"] == "spin":
            cmd += ["--atlas", str(a.data_root / "atlas_2009c" /
                                   "tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz")]
    return cmd


def run_embedding(a) -> int:
    jobs = plan(a.v3_root, a.out)
    if a.only is not None:
        jobs = jobs[:a.only]
    env = {**os.environ, **THREAD_ENV, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    (a.out / "logs").mkdir(parents=True, exist_ok=True)
    t0, fails = time.time(), []

    def one(job):
        out = Path(job["out"])
        if (out / "fit_report.json").exists():
            return job, 0, "skip"
        name = f"C_{job['kind']}{job['idx']:02d}_o{job['outer']}_s{job['seed']}"
        with (a.out / "logs" / f"{name}.log").open("w") as fh:
            rc = subprocess.run(fit_cmd(a, job), cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode
        return job, rc, name

    with ThreadPoolExecutor(max_workers=a.k) as ex:
        for i, fut in enumerate(as_completed([ex.submit(one, j) for j in jobs]), 1):
            job, rc, name = fut.result()
            if rc:
                fails.append(name)
            if i % 20 == 0 or i == len(jobs):
                print(f"{i}/{len(jobs)} 실패 {len(fails)} 경과 {time.time() - t0:.0f} s", flush=True)
    (a.out / "run_embedding.json").write_text(json.dumps({"n_jobs": len(jobs), "fails": fails,
                                                         "wall_s": round(time.time() - t0, 1)}, indent=1))
    return 1 if fails else 0


def collect_embedding(a) -> int:
    kidx = key_index(a.samples)
    n = 0
    for o in range(N_OUTER):
        for s in SEEDS:
            n += convert(a.v3_root / "outer/embedding/n100" / f"o{o}" / f"A_s{s}" / "window_predictions.jsonl",
                         a.out / "mobse_embedding/orig/k0" / f"r{s}" / f"f{o}", kidx,
                         {"cell": "A", "model_seed": s, "roi_structure": "embedding", "n_train_level": 100})
            for kind in KINDS:
                for idx in range(K):
                    src = existing_v3(a.v3_root, kind, idx, o, s) or a.work / "fits" / f"C_{kind}{idx:02d}" / f"o{o}" / f"s{s}"
                    n += convert(src / "window_predictions.jsonl",
                                 a.out / "mobse_embedding" / f"prior_{kind}" / f"k{idx}" / f"r{s}" / f"f{o}", kidx,
                                 {"cell": "C", "model_seed": s, "roi_structure": "embedding", "null_kind": kind,
                                  "null_index": idx, "n_train_level": 100})
    print(f"embedding: 창 예측 {n} 행 → {a.out / 'mobse_embedding'}")
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("collect-mean")
    p.add_argument("--main", required=True, type=Path)
    p.add_argument("--sens", required=True, type=Path)
    p.add_argument("--samples", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("plan-embedding")
    p.add_argument("--v3-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("run-embedding")
    p.add_argument("--v3-root", required=True, type=Path)
    p.add_argument("--data-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--only", type=int, default=None, help="smoke — 앞 N 개만")
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--device", default="cuda")
    p = sub.add_parser("collect-embedding")
    p.add_argument("--v3-root", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path)
    p.add_argument("--samples", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv[1:])
    if a.cmd == "collect-mean":
        return collect_mean(a)
    if a.cmd == "plan-embedding":
        jobs = plan(a.v3_root, a.out)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "plan.json").write_text(json.dumps(jobs, indent=1))
        print(f"새 fit {len(jobs)} 개 (이미 있는 것 제외) → {a.out / 'plan.json'}")
        return 0
    if a.cmd == "run-embedding":
        return run_embedding(a)
    return collect_embedding(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
