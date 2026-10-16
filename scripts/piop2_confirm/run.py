#!/usr/bin/env python3
"""PIOP2 확증 구동기 (결정 77 · 78) — prep → fit → s → analyze. tmux 세션에서 띄운다.

* ``--mode smoke``: PIOP1 만 (PIOP2 를 읽지 않음). seed 42 하나 · 칸 4 개.
* ``--mode main``: 잠금 검증 (``build_lock.py --verify``) 이 rc 0 일 때만 시작. 평가 = PIOP2 189 명. seed 42 · 43 · 44.
* 이어 하기: ``summary.json`` 이 있는 fit 은 건너뛴다. 산출: ``<out-root>/<mode>/<run_id>/``.

Usage (h197, 저장소 사본 루트):
    PYTHONPATH=. $VENV/bin/python -B scripts/piop2_confirm/run.py --mode smoke --root1 <PIOP1 root> \
        --root2 <PIOP2 root> --piop2-ids <ids> --out-root <dir> --run-id <id> --device cuda [--jobs 2]
    (main 은 --lock <lock.json> 추가)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "i3"))
import core  # noqa: E402
import p2  # noqa: E402

PY = sys.executable


def log(run: Path, msg: str) -> None:
    with (run / "status.log").open("a") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "fit-one"))
    ap.add_argument("--mode", choices=("smoke", "main"))
    ap.add_argument("--root1", type=Path)
    ap.add_argument("--root2", type=Path)
    ap.add_argument("--piop2-ids", type=Path)
    ap.add_argument("--out-root", type=Path)
    ap.add_argument("--run-id")
    ap.add_argument("--lock", type=Path, default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--prep", type=Path)
    ap.add_argument("--cell"), ap.add_argument("--structure"), ap.add_argument("--null-kind")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    if a.cmd == "fit-one":
        # CUDA 는 기본 설정에서 같은 seed 도 학습 경로가 갈린다 (smoke_a1 재실행: 확률 최대 차 0.41, 선택 epoch 116 대 111).
        # v1 과 같은 결정론 설정을 학습 전에 켜고, 그 상태를 fit 폴더에 남긴다 (잠긴 I3 core 는 고치지 않음).
        from mobse.v2.fitting import apply_determinism
        state = apply_determinism()
        a.out.mkdir(parents=True, exist_ok=True)
        core.atomic_write(a.out / "determinism.json", json.dumps(state, indent=1))
        core.fit_one(a.prep, a.cell, a.structure, a.null_kind, a.seed, a.out, device=a.device)
        return 0

    if a.mode == "main":
        if a.lock is None:
            raise SystemExit("main 은 --lock 이 필요하다")
        v = subprocess.run([PY, "-B", str(HERE / "build_lock.py"), "--verify", "--repo-root", ".", "--root1", str(a.root1),
                            "--root2", str(a.root2), "--piop2-ids", str(a.piop2_ids), "--out", str(a.lock)],
                           capture_output=True, text=True)
        if v.returncode != 0:
            raise SystemExit(f"잠금 검증 실패 — 아무것도 시작하지 않음: {v.stdout.strip()} {v.stderr.strip()[-500:]}")
        lock_hash = json.loads(a.lock.read_text())["lock_hash"]
    else:
        lock_hash = None
    smoke = a.mode == "smoke"
    piop1 = (a.root1 / "all_ids.txt").read_text().split()
    piop2 = [] if smoke else a.piop2_ids.read_text().split()
    split = p2.make_split(piop1, piop2, smoke=smoke)
    seeds = [core.SEEDS[0]] if smoke else list(core.SEEDS)
    run = a.out_root / a.mode / a.run_id
    run.mkdir(parents=True, exist_ok=True)
    cfg = {"mode": a.mode, "lock_hash": lock_hash, "root1": str(a.root1), "root2": None if smoke else str(a.root2),
           "seeds": seeds, "cells": p2.CELLS, "device": a.device, "split_seed": p2.SPLIT_SEED,
           "n": {r: len(split[r]) for r in ("train", "val", "test")}, "python": PY}
    cfg_path = run / "run_config.json"
    if cfg_path.exists() and json.loads(cfg_path.read_text()) != json.loads(json.dumps(cfg)):
        raise SystemExit("run_config.json 이 지금 설정과 다르다 — 새 run-id 를 쓸 것")
    core.atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=1))
    core.atomic_write(run / "split.json", json.dumps(split, indent=1))
    log(run, f"start mode={a.mode} lock={lock_hash}")

    prep_dir = run / "prep" / "outer0"
    if not (prep_dir / "prep.json").exists():
        roots = {"ds002785": a.root1} if smoke else {"ds002785": a.root1, "ds002790": a.root2}
        m = p2.prep(roots, split, prep_dir)
        log(run, f"prep ok {m['n_blocks']} {m['seconds']:.1f}s")
    jobs = [(c, s, nk, sd) for (c, s, nk) in p2.CELLS for sd in seeds
            if not (run / "fits" / core.cell_name(c, s, nk) / "outer0" / f"seed{sd}" / "summary.json").exists()]
    log(run, f"fit {len(jobs)} to do, jobs={a.jobs}")

    def one(j):
        c, s, nk, sd = j
        out = run / "fits" / core.cell_name(c, s, nk) / "outer0" / f"seed{sd}"
        out.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([PY, "-B", str(Path(__file__).resolve()), "fit-one", "--prep", str(prep_dir), "--cell", c,
                            "--structure", s, "--null-kind", str(nk), "--seed", str(sd), "--out", str(out),
                            "--device", a.device], capture_output=True, text=True)
        (out / "log.txt").write_text(r.stdout + r.stderr)
        return j, r.returncode

    fails, t0 = [], time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for i, fut in enumerate(as_completed([ex.submit(one, j) for j in jobs]), 1):
            j, rc = fut.result()
            if rc != 0:
                fails.append({"job": list(j), "rc": rc})
            log(run, f"fit {i}/{len(jobs)} {core.cell_name(*j[:3])} s{j[3]} rc={rc} elapsed={time.perf_counter() - t0:.0f}s")
    core.atomic_write(run / "fails_fit.json", json.dumps(fails, indent=1))
    if fails:
        log(run, "fit FAIL")
        return 1
    core.fit_s(prep_dir, run / "s" / "outer0")
    log(run, "s rc=0")
    res = p2.analyze(run)
    (run / "analysis").mkdir(exist_ok=True)
    core.atomic_write(run / "analysis" / "analysis.json", json.dumps(res, ensure_ascii=False, indent=1))
    log(run, f"analyze rc=0 sha12={core.sha256(run / 'analysis' / 'analysis.json')[:12]}")
    log(run, "ALL_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
