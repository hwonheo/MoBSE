#!/usr/bin/env python3
"""I3 구동기 (결정 69) — prep → fit → s → analyze. tmux 세션에서 띄운다 (선생님 지시 "백그라운드 처리시 tmux 사용").

* ``--mode smoke``: pilot 31 명의 가짜 분할 (outer 1 · test 6 · train 19 · val 6) · seed 42 하나 · 칸 18 개 전부.
  **main 피험자를 읽지 않는다.** 잠금 전에 끝에서 끝까지 도는지 본다.
* ``--mode main``: 잠금 검증 (``build_lock.py --verify``) 이 rc 0 일 때만 시작. WI-03 outer 5 fold · seed 42 · 43 · 44 ·
  칸 18 개 (주 10 + null 민감도 8) = 270 fit.
* 이어 하기: ``summary.json`` 이 있는 fit 은 건너뛴다. 실패는 ``fails_<phase>.json`` 에 모으고 다음으로 넘어간다.
* 산출: ``<out-root>/<mode>/<run_id>/`` 아래 ``run_config.json`` · ``status.log`` · ``prep/`` · ``fits/`` · ``s/`` · ``analysis/``.

Usage (Mac, 저장소 루트):
    PYTHONPATH=. .venv/bin/python scripts/i3/run_main.py --mode smoke --data-root data/h1h2_scope/aomic --out-root data/i3
    PYTHONPATH=. .venv/bin/python scripts/i3/run_main.py --mode main --data-root data/h1h2_scope/aomic --out-root data/i3 \
        --lock results/i3/locks/lock.json --run-id <YYYYMMDD_lock8_aN> [--jobs 2]
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

HERE = Path(__file__).resolve().parent
PY = sys.executable


def log(run: Path, msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    with (run / "status.log").open("a") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def fit_cli(argv) -> int:
    """하위 프로세스 진입점: 한 fit."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep", type=Path, required=True)
    ap.add_argument("--cell", required=True)
    ap.add_argument("--structure", required=True)
    ap.add_argument("--null-kind", default=None)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="mps")
    a = ap.parse_args(argv)
    core.fit_one(a.prep, a.cell, a.structure, None if a.null_kind in (None, "None") else a.null_kind, a.seed, a.out,
                 device=a.device)
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "fit-one":
        return fit_cli(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("smoke", "main"), required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--lock", type=Path, default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--phase", default="all", choices=("all", "prep", "fit", "s", "analyze"))
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--device", default="mps")
    a = ap.parse_args()

    root = a.data_root
    if a.mode == "main":
        if a.lock is None or a.run_id is None:
            raise SystemExit("main 은 --lock · --run-id 가 필요하다")
        v = subprocess.run([PY, "-B", str(HERE / "build_lock.py"), "--verify", "--repo-root", ".", "--data-root",
                            str(root), "--doc", "docs/experiments/i3_lock_v1.md", "--out", str(a.lock)],
                           capture_output=True, text=True)
        if v.returncode != 0:
            raise SystemExit(f"잠금 검증 실패 — 아무것도 시작하지 않음: {v.stdout.strip()} {v.stderr.strip()[-500:]}")
        folds = json.loads((root / core.FOLDS).read_text())
        n_outer, seeds = core.N_OUTER, list(core.SEEDS)
        lock_hash = json.loads(a.lock.read_text())["lock_hash"]
        run = a.out_root / "main" / a.run_id
    else:
        folds = core.smoke_folds((root / "pilot_ids.txt").read_text().split())
        n_outer, seeds = 1, [core.SEEDS[0]]
        lock_hash = None
        run = a.out_root / "smoke" / (a.run_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    run.mkdir(parents=True, exist_ok=True)
    cfg_path = run / "run_config.json"
    cfg = {"mode": a.mode, "n_outer": n_outer, "seeds": seeds, "lock_hash": lock_hash, "data_root": str(root),
           "folds_sha256": core.sha256(root / core.FOLDS), "lag_s": core.LAG_S, "config_id": core.CONFIG_ID,
           "inner_fold": core.INNER_FOLD, "cells_main": core.MAIN_CELLS, "cells_sensitivity": core.SENS_CELLS,
           "device": a.device, "python": PY}
    if cfg_path.exists() and json.loads(cfg_path.read_text()) != json.loads(json.dumps(cfg)):
        raise SystemExit("run_config.json 이 지금 설정과 다르다 — 새 run-id 를 쓸 것")
    core.atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=1))
    if a.mode == "smoke":
        core.atomic_write(run / "smoke_folds.json", json.dumps(folds, indent=1))
    log(run, f"start mode={a.mode} phase={a.phase} lock={lock_hash}")

    if a.phase in ("all", "prep"):
        fails = []
        for k in range(n_outer):
            d = run / "prep" / f"outer{k}"
            if (d / "prep.json").exists():
                continue
            try:
                m = core.prep_one(root, folds, k, d)
                log(run, f"prep outer{k} ok {m['n_windows']} {m['seconds']:.1f}s")
            except Exception as e:                              # noqa: BLE001 — 사유를 남기고 다음으로
                fails.append({"outer": k, "error": repr(e)})
                log(run, f"prep outer{k} FAIL {e!r}")
        core.atomic_write(run / "fails_prep.json", json.dumps(fails, indent=1))
        log(run, f"prep rc={1 if fails else 0}")
        if fails:
            return 1

    if a.phase in ("all", "fit"):
        jobs = [(c, s, nk, k, sd) for (c, s, nk) in core.MAIN_CELLS + core.SENS_CELLS for k in range(n_outer)
                for sd in seeds]
        todo = [j for j in jobs if not (run / "fits" / core.cell_name(*j[:3]) / f"outer{j[3]}" / f"seed{j[4]}"
                                        / "summary.json").exists()]
        log(run, f"fit {len(jobs)} jobs, {len(todo)} to do, jobs={a.jobs}")
        fails = []

        def one(j):
            c, s, nk, k, sd = j
            out = run / "fits" / core.cell_name(c, s, nk) / f"outer{k}" / f"seed{sd}"
            out.mkdir(parents=True, exist_ok=True)
            r = subprocess.run([PY, "-B", str(HERE / "run_main.py"), "fit-one", "--prep", str(run / "prep" / f"outer{k}"),
                                "--cell", c, "--structure", s, "--null-kind", str(nk), "--seed", str(sd), "--out",
                                str(out), "--device", a.device], capture_output=True, text=True)
            (out / "log.txt").write_text(r.stdout + r.stderr)
            return j, r.returncode

        t0 = time.perf_counter()
        done = 0
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            for fut in as_completed([ex.submit(one, j) for j in todo]):
                j, rc = fut.result()
                done += 1
                if rc != 0:
                    fails.append({"job": list(j), "rc": rc})
                if done % 10 == 0 or rc != 0 or done == len(todo):
                    log(run, f"fit {done}/{len(todo)} last={core.cell_name(*j[:3])} o{j[3]} s{j[4]} rc={rc} "
                             f"elapsed={time.perf_counter() - t0:.0f}s fails={len(fails)}")
        core.atomic_write(run / "fails_fit.json", json.dumps(fails, indent=1))
        log(run, f"fit rc={1 if fails else 0}")
        if fails:
            return 1

    if a.phase in ("all", "s"):
        for k in range(n_outer):
            core.fit_s(run / "prep" / f"outer{k}", run / "s" / f"outer{k}")
        log(run, "s rc=0")

    if a.phase in ("all", "analyze"):
        r = subprocess.run([PY, "-B", str(HERE / "analyze.py"), "--run", str(run)], capture_output=True, text=True)
        (run / "analysis_log.txt").write_text(r.stdout + r.stderr)
        log(run, f"analyze rc={r.returncode}")
        if r.returncode != 0:
            return 1
    log(run, "ALL_DONE" if a.phase == "all" else f"{a.phase}_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
