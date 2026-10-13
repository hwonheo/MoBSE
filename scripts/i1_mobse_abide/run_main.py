#!/usr/bin/env python3
"""ABIDE MoBSE 팔 구동기 (결정 59) — 잠금 검증 → 준비 → 학습 → 분석.

* 맨 앞에서 ``build_lock.py --verify`` 와 같은 검증을 하고, 실패하면 아무것도 시작하지 않는다 (``--no-lock`` 은 구동기
  smoke 전용이며 산출에 ``smoke`` 표시를 남긴다).
* 단계: ``prep`` (입력 12 × fold 5 = 60, CPU) · ``fit`` (60 × 구조 2 × seed 3 = 360, GPU) · ``analyze`` (MoBSE 2 + 공개 모델 3,
  963 명). 작업마다 하위 프로세스 하나 — 실패는 **다시 돌리지 않고 센다** (I1 규칙). 이미 끝난 작업 (``prep.json`` ·
  ``summary.json`` 있음) 은 건너뛴다 (중단 뒤 이어 돌리기).
* 산출: ``<out>/cache/<cond>_k<k>/f<fold>/`` (준비물) · ``<out>/abide/mobse_<구조>/<cond>/k<k>/r<seed>/f<fold>/`` (I1 배치) ·
  ``<out>/analysis/*.json`` · ``status.txt`` · ``fails_<단계>.json`` · ``logs/``.

Usage (h197, 저장소 사본 루트, venv-mobse-v2):
    python -B scripts/i1_mobse_abide/run_main.py --data-root <D> --out <OUT> --phase {prep|fit|analyze} \
        --lock results/i1_mobse_abide/locks/lock.json --doc docs/experiments/i1_mobse_abide_lock_v1.md [--jobs N]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import core  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status(out: Path, msg: str) -> None:
    with (out / "status.txt").open("a") as fh:
        fh.write(f"{now()} {msg}\n")
    print(f"{now()} {msg}", flush=True)


def verify_lock(a) -> None:
    if a.no_lock:
        status(a.out, "LOCK_SKIPPED (smoke)")
        return
    r = subprocess.run([sys.executable, "-B", str(HERE / "build_lock.py"), "--verify", "--repo-root", str(ROOT),
                        "--data-root", str(a.data_root), "--doc", str(a.doc), "--out", str(a.lock)],
                       capture_output=True, text=True, cwd=ROOT)
    (a.out / "logs").mkdir(parents=True, exist_ok=True)
    (a.out / "logs" / f"lock_verify_{a.phase}.log").write_text(r.stdout + r.stderr)
    status(a.out, f"lock_verify {a.phase} rc={r.returncode}")
    if r.returncode != 0:
        raise SystemExit(f"잠금 검증 실패 — 시작하지 않음:\n{r.stdout}{r.stderr}")


def env(threads: int) -> dict:
    e = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        e[k] = str(threads)
    e["PYTHONPATH"] = str(ROOT)          # 구동기 하위 프로세스에만 (잠금의 pip freeze 에는 끼지 않음)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def run_jobs(a, phase: str, jobs: list, threads: int) -> None:
    logs = a.out / "logs" / phase
    logs.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not j["done"].exists()]
    status(a.out, f"BEGIN {phase} 작업 {len(jobs)} · 남은 것 {len(todo)} · 동시 {a.jobs}")
    fails, t0, n_done = [], time.time(), 0

    def one(j):
        with (logs / f"{j['name']}.log").open("w") as fh:
            return j, subprocess.run([sys.executable, "-B", str(HERE / "run_main.py"), "--one", json.dumps(j["args"])],
                                     stdout=fh, stderr=subprocess.STDOUT, env=env(threads), cwd=ROOT).returncode

    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for fut in as_completed([pool.submit(one, j) for j in todo]):
            j, rc = fut.result()
            n_done += 1
            if rc != 0 or not j["done"].exists():
                fails.append({"job": j["name"], "rc": rc})
            if n_done % 10 == 0 or n_done == len(todo):
                status(a.out, f"  {phase} {n_done}/{len(todo)} 실패 {len(fails)} 경과 {time.time() - t0:.0f} s")
    (a.out / f"fails_{phase}.json").write_text(json.dumps(fails, ensure_ascii=False, indent=1))
    status(a.out, f"END {phase} 실패 {len(fails)} 경과 {time.time() - t0:.0f} s")


def one(spec: dict) -> int:
    """하위 프로세스 작업 하나."""
    if spec["kind"] == "prep":
        folds = json.loads(Path(spec["folds"]).read_text())
        meta = core.prep_one(Path(spec["npy"]), folds, spec["fold"], spec["kept"], Path(spec["out"]))
        print(json.dumps(meta, ensure_ascii=False))
    else:
        s = core.fit_one(Path(spec["npy"]), Path(spec["prep"]), spec["structure"], spec["seed"], Path(spec["out"]),
                         device=spec.get("device", "cuda"))
        print(json.dumps(s, ensure_ascii=False))
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--one", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--data-root", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--phase", choices=("prep", "fit", "analyze"))
    ap.add_argument("--lock", type=Path, default=Path("results/i1_mobse_abide/locks/lock.json"))
    ap.add_argument("--doc", type=Path, default=Path("docs/experiments/i1_mobse_abide_lock_v1.md"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-lock", action="store_true", help="구동기 smoke 전용")
    ap.add_argument("--only", default=None, help="smoke: 'cond_k/fold' 목록 (쉼표)")
    ap.add_argument("--structures", default=",".join(core.STRUCTURES))
    ap.add_argument("--seeds", default=",".join(map(str, core.SEEDS)))
    a = ap.parse_args(argv[1:])
    if a.one:
        return one(json.loads(a.one))
    a.out.mkdir(parents=True, exist_ok=True)
    if a.no_lock:
        (a.out / "SMOKE_NOT_LOCKED").write_text("구동기 smoke — 잠금 없이 돌린 산출. 분석 · 보고에 쓰지 않는다.\n")
    verify_lock(a)
    kept_path = a.out / "kept_subjects.json"
    if not kept_path.exists():
        kept = core.kept_index(a.data_root)
        kept_path.write_text(json.dumps({"n_kept": len(kept), "kept": kept}))
    kept = json.loads(kept_path.read_text())["kept"]
    folds = a.data_root / core.FOLDS
    sel = None if not a.only else set(a.only.split(","))
    units = [(c, k, npy, f) for c, k, npy in core.inputs(a.data_root) for f in range(core.N_FOLDS)
             if sel is None or f"{c}_k{k}/{f}" in sel]
    cache = lambda c, k, f: a.out / "cache" / f"{c}_k{k}" / f"f{f}"  # noqa: E731

    if a.phase == "prep":
        jobs = [{"name": f"prep_{c}_k{k}_f{f}", "done": cache(c, k, f) / "prep.json",
                 "args": {"kind": "prep", "npy": str(npy), "folds": str(folds), "fold": f, "kept": kept,
                          "out": str(cache(c, k, f))}} for c, k, npy, f in units]
        run_jobs(a, "prep", jobs, threads=3)
    elif a.phase == "fit":
        jobs = []
        for c, k, npy, f in units:
            for st in a.structures.split(","):
                for r in map(int, a.seeds.split(",")):
                    od = a.out / "abide" / f"mobse_{st}" / c / f"k{k}" / f"r{r}" / f"f{f}"
                    jobs.append({"name": f"fit_{st}_{c}_k{k}_r{r}_f{f}", "done": od / "summary.json",
                                 "args": {"kind": "fit", "npy": str(npy), "prep": str(cache(c, k, f)),
                                          "structure": st, "seed": r, "out": str(od), "device": a.device}})
        missing = [j for j in jobs if not (Path(j["args"]["prep"]) / "prep.json").exists()]
        if missing:
            raise SystemExit(f"준비물이 없는 fit {len(missing)} 개 — prep 단계를 먼저")
        run_jobs(a, "fit", jobs, threads=2)
    else:
        r = subprocess.run([sys.executable, "-B", str(HERE / "analyze963.py"), "--data-root", str(a.data_root),
                            "--mobse-root", str(a.out / "abide"), "--kept", str(kept_path),
                            "--out", str(a.out / "analysis")], env=env(4), cwd=ROOT)
        status(a.out, f"analyze rc={r.returncode}")
        if r.returncode == 0:
            status(a.out, "ALL_DONE")
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
