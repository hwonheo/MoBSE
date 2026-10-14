#!/usr/bin/env python3
"""ADHD-200 I1 구동기 (결정 62 · 63) — **잠금 검증이 통과해야** 돈다.

잠긴 I1 코드는 고치지 않고 경로만 바꿔 쓴다:
* 공개 모델 · null · 기준선 · 분석: ``scripts/i1/run_main.Main`` 을 상속해 입력 경로 (``adhd200/i1data/``) 만 바꾼다.
  하위 작업 (``null_inputs.py`` · ``run_fold.py`` · ``baselines.py`` · ``analyze.py``) 은 venv-i1 로 그대로 부른다.
* MoBSE (mean · embedding): ``scripts/i1_mobse_abide/run_main.py`` 를 불러 ``core`` 의 입력 목록 · 원판 · fold 경로만 바꾼다.
  하위 작업은 이 프로세스의 python (venv-mobse-v2) 으로 돈다. n3 은 MoBSE 에 쓰지 않음 (결정 59 D2 와 같음).

단계 (``--phase``): ``nulls`` · ``fits`` · ``baselines`` · ``mobse_prep`` · ``mobse_fit`` · ``analyze``.
``fits`` 는 ``--conds`` 로 조건을 고를 수 있다 (결정 65: n3 생성 중에 orig · n0 · n1 · n2 를 먼저 학습).
배치: ``<out>/adhd200/<model>/<cond>/k<k>/r<r>/f<f>/`` · null 입력 ``<out>/inputs/adhd200/<cond>_k<k>/abide.npy`` ·
MoBSE ``<out>/mobse/abide/mobse_<구조>/…`` · 분석 ``<out>/analysis/adhd200/<model>.json``.

Usage (h197, 저장소 사본 루트, venv-mobse-v2 — PYTHONPATH 를 내보내지 말 것):
    python -B scripts/i1_adhd200/run_main.py --data-root <D> --out <D>/adhd200/main/<run id> --phase fits \\
        --lock results/i1_adhd200/locks/lock.json --doc docs/experiments/i1_adhd200_lock_v1.md [--k 2] [--no-lock]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = "adhd200/i1data"
STRUCTURES = ("mean", "embedding")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


I1 = load("i1_run_main", ROOT / "scripts/i1/run_main.py")


class AdhdMain(I1.Main):
    """I1 ``Main`` 과 같은 단계 · 같은 배치, 입력 경로만 ADHD-200."""

    def __init__(self, a):  # noqa: D107 — 부모 __init__ 의 abide/aomic 분기를 쓰지 않는다
        self.a, d = a, a.data_root
        self.py = str(d / "venv-i1/bin/python")
        self.npy, self.folds, self.coords = d / DATA / "abide.npy", d / DATA / "folds_draw0.json", d / DATA / "coords.json"
        self.n_items, self.samples = json.loads((d / DATA / "abide.json").read_text())["n_kept"], None
        self.out = a.out
        self.out.mkdir(parents=True, exist_ok=True)
        self.logf = self.out / "driver_adhd200.log"
        self.gpu_gate = threading.Lock()

    def phase_fits(self) -> int:
        """I1 ``phase_fits`` 와 같은 작업 목록을 ``--conds`` 로 좁힌다 (결정 65 — null 생성과 겹쳐 돌리기).

        고른 조건의 입력이 하나라도 없으면 시작하지 않는다 (없는 입력으로 학습이 실패로 세지지 않게).
        """
        conds = self.a.conds.split(",") if self.a.conds else ["orig", "n0", *I1.NULLS]
        rc = 0
        for model in self.a.models:
            K, R = I1.KR[model]
            units = [(c, k) for c in conds for k in (range(1) if c in ("orig", "n0") else range(K))]
            missing = [f"{c}_k{k}" for c, k in units if c != "orig" and not (self.input_npy(c, k).parent / "meta.json").exists()]
            if missing:
                raise SystemExit(f"null 입력이 없다: {missing} — nulls 단계를 먼저")
            jobs = [self.fit_job(model, c, k, r, f) for c, k in units for r in range(1, R + 1) for f in range(I1.N_FOLDS)]
            rc |= self.run_jobs(f"fits_{model}_{'-'.join(conds)}", jobs, self.a.k)
        return rc

    def mobse(self, phase: str) -> int:
        M = load("i1_mobse_run", ROOT / "scripts/i1_mobse_abide/run_main.py")
        d, out = self.a.data_root, self.out

        def inputs(_):
            rows = [("orig", 0, d / DATA / "abide.npy"), ("n0", 0, self.input_npy("n0", 0))]
            for c in ("n1", "n2"):
                rows += [(c, k, self.input_npy(c, k)) for k in range(M.core.K)]
            return rows

        M.core.ORIG_NPY, M.core.FOLDS, M.core.inputs = f"{DATA}/abide.npy", f"{DATA}/folds_draw0.json", inputs
        M.verify_lock = lambda a: M.status(a.out, f"lock_verify {a.phase} — ADHD 구동기가 시작 때 함")
        sel = None if not self.a.only else {u.split("/")[0] for u in self.a.only.split(",")}
        missing = [str(p) for c, k, p in inputs(None) if not p.exists() and (sel is None or f"{c}_k{k}" in sel)]
        if missing:
            raise SystemExit(f"null 입력이 없다 ({len(missing)}) — nulls 단계를 먼저")
        args = ["mobse", "--data-root", str(d), "--out", str(out / "mobse"), "--phase", phase.replace("mobse_", ""),
                "--jobs", str(self.a.mobse_jobs)]
        if self.a.no_lock:
            args.append("--no-lock")
        if self.a.only:
            args += ["--only", self.a.only, "--seeds", self.a.seeds]
        self.log(f"== {phase}: scripts/i1_mobse_abide 구동기 (경로만 ADHD-200) ==")
        return M.main(args)

    def phase_mobse_prep(self) -> int:
        return self.mobse("mobse_prep")

    def phase_mobse_fit(self) -> int:
        return self.mobse("mobse_fit")

    def phase_analyze(self) -> int:
        rc = super().phase_analyze()                       # 공개 모델 · 기준선 (adhd200/)
        base = self.out / "mobse/abide"
        for st in STRUCTURES:
            if not (base / f"mobse_{st}").exists():
                continue
            cmd = [self.py, "-B", "scripts/i1/analyze.py", "--root", str(base), "--model", f"mobse_{st}",
                   "--out", str(self.out / "analysis/adhd200" / f"mobse_{st}.json"),
                   "--n-items", str(self.n_items), "--n-boot", "2000"]
            rc |= subprocess.run(cmd, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}).returncode
        return rc


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--phase", required=True,
                    choices=("nulls", "fits", "baselines", "mobse_prep", "mobse_fit", "analyze"))
    ap.add_argument("--lock", type=Path, default=Path("results/i1_adhd200/locks/lock.json"))
    ap.add_argument("--doc", type=Path, default=Path("docs/experiments/i1_adhd200_lock_v1.md"))
    ap.add_argument("--models", nargs="+", default=list(I1.MODELS), choices=I1.MODELS)
    ap.add_argument("--k", type=int, default=2, help="공개 모델 · null 동시 작업 수")
    ap.add_argument("--mobse-jobs", type=int, default=4)
    ap.add_argument("--n3-workers", type=int, default=8)
    ap.add_argument("--no-lock", action="store_true", help="구동기 smoke 전용")
    ap.add_argument("--conds", default=None, help="fits: 쉼표로 고른 조건 (예: orig,n0,n1,n2) — 결정 65")
    ap.add_argument("--only", default=None, help="smoke: MoBSE 'cond_k/fold' 목록 (쉼표)")
    ap.add_argument("--seeds", default="1", help="smoke: --only 와 함께 쓸 MoBSE seed")
    a = ap.parse_args(argv[1:])
    a.dataset = "adhd200"
    a.out.mkdir(parents=True, exist_ok=True)
    if a.no_lock:
        (a.out / "SMOKE_NOT_LOCKED").write_text("구동기 smoke — 잠금 없이 돌린 산출. 분석 · 보고에 쓰지 않는다.\n")
        verify = "LOCK_SKIPPED (smoke)"
    else:
        v = subprocess.run([sys.executable, "-B", str(HERE / "build_lock.py"), "--verify", "--repo-root", str(ROOT),
                            "--data-root", str(a.data_root), "--doc", str(a.doc), "--out", str(a.lock)],
                           cwd=ROOT, capture_output=True, text=True)
        if v.returncode != 0:
            print(f"잠금 검증 실패 — 실행하지 않는다:\n{v.stdout}{v.stderr}", file=sys.stderr)
            return 3
        verify = v.stdout.strip()
    m = AdhdMain(a)
    m.log(f"START dataset=adhd200 phase={a.phase} verify={verify}")
    rc = getattr(m, f"phase_{a.phase}")()
    m.log(f"END phase={a.phase} rc={rc}")
    if a.phase == "analyze" and rc == 0:
        m.log("ALL_DONE")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
