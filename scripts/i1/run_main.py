#!/usr/bin/env python3
"""I1 본 실행 구동기 — **잠금 검증이 통과해야** 돈다 (결정 38-4 · 39 · 43). 이어 돌기 가능 (끝난 fit 은 건너뜀).

단계 (``--phase``):
* ``nulls``     — null 입력 생성 (``null_inputs.py``): n0 k0 · n1–n3 k0..K−1 (K 는 모델 최댓값 5). ABIDE 는 CC200 좌표,
                  AOMIC 은 Schaefer 좌표. n3 는 ``--n3-workers`` 병렬.
* ``fits``      — 공개 모델 (``run_fold.py``). 모델마다 K · R (결정 38-3: BrainGB K=3 · R=2, 나머지 K=5 · R=3), 조건 orig · n0 (k0) ·
                  n1–n3 (k0..K−1), seed r = 1..R, fold 0–4. D1 학습판용으로 orig · r=1 · fold 0–2 는 ``--save-last --d1`` (결정 43 §3.9 — 학습 끝 모델로 바로 잰다).
* ``site``      — site 민감도 (결정 43 §3.5): BQN · ``folds_site.json`` · orig + n1 (k0..4) · R=3. ABIDE 만.
* ``baselines`` — FC logistic · S1 (결정적이라 r=1 만) · FC-MLP (r=1..3), 원판만 (결정 43 §3.8).
* ``analyze``   — ``analyze.py`` 를 모델마다.

배치: ``<out>/<dataset>/<model>/<cond>/k<k>/r<r>/f<f>/`` (``analyze.py`` 가 읽는 형식), null 입력은 ``<out>/inputs/<dataset>/<cond>_k<k>/``.
MoBSE 팔은 ``mobse_arm.py`` 가 따로 돈다 (AOMIC 만).

Usage (h197, 저장소 사본 루트, venv-i1):
    PYTHONPATH=. python scripts/i1/run_main.py --data-root <D> --out <D>/i1/main/<run id> --dataset abide \\
        --phase fits --lock results/i1/locks/i1_lock.json --doc docs/experiments/<잠금 문서>.md [--models bqn bnt] [--k 2]
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

ROOT = Path(__file__).resolve().parents[2]
MODELS = ("bqn", "bnt", "han", "braingb")
KR = {"bqn": (5, 3), "bnt": (5, 3), "han": (5, 3), "braingb": (3, 2)}
NULLS = ("n1", "n2", "n3")
N_FOLDS = 5
D1_FOLDS = (0, 1, 2)
BASELINES = {"fc_logistic": (1,), "s1_logistic": (1,), "fc_mlp": (1, 2, 3)}
SITE = {"model": "bqn", "conds": ("orig", "n1"), "K": 5, "R": 3}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Main:
    def __init__(self, a):
        self.a, d = a, a.data_root
        self.py = str(d / "venv-i1/bin/python")
        if a.dataset == "abide":
            self.npy = d / "i1/data/abide_noglobal_braingb/abide.npy"
            self.folds = d / "i1/data/folds_draw0.json"
            self.coords = d / "i1/data/cc200_coords.json"
            self.n_items, self.samples = 1009, None
        else:
            base = d / "i1/data/aomic_win"
            self.npy, self.folds, self.coords = base / "abide.npy", base / "folds.json", base / "coords.json"
            self.n_items, self.samples = 1008, base / "samples.jsonl"
        self.out = a.out
        self.out.mkdir(parents=True, exist_ok=True)
        self.logf = self.out / f"driver_{a.dataset}.log"

    def log(self, msg: str) -> None:
        line = f"{now()} {msg}"
        print(line, flush=True)
        with self.logf.open("a") as fh:
            fh.write(line + "\n")

    def input_npy(self, cond: str, k: int) -> Path:
        return self.npy if cond == "orig" else self.out / "inputs" / self.a.dataset / f"{cond}_k{k}" / "abide.npy"

    def run_jobs(self, label: str, jobs: list, k: int) -> int:
        env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "WANDB_MODE": "disabled"}
        todo = [j for j in jobs if not (Path(j["done"]).exists())]
        self.log(f"== {label}: {len(jobs)} 작업 · 남은 것 {len(todo)} (k={k}) ==")
        (self.out / "logs").mkdir(exist_ok=True)
        fails, t0 = [], time.time()

        def one(j):
            with (self.out / "logs" / f"{j['name']}.log").open("w") as fh:
                return j, subprocess.run(j["cmd"], cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode

        with ThreadPoolExecutor(max_workers=k) as ex:
            for i, fut in enumerate(as_completed([ex.submit(one, j) for j in todo]), 1):
                j, rc = fut.result()
                if rc:                                   # 결정 43 §3.3: 프로세스 오류는 같은 seed 로 한 번 재시도
                    self.log(f"   rc={rc} {j['name']} — 한 번 재시도")
                    j, rc = one(j)
                    if rc:
                        fails.append(j["name"])
                if i % 20 == 0 or i == len(todo):
                    self.log(f"   {label} {i}/{len(todo)} 실패 {len(fails)} 경과 {time.time() - t0:.0f} s")
        (self.out / f"fails_{label}.json").write_text(json.dumps(fails, indent=1))
        return 1 if fails else 0

    def phase_nulls(self) -> int:
        kmax = max(K for K, _ in KR.values())
        jobs = []
        for cond in ("n0",) + NULLS:
            for k in (range(1) if cond == "n0" else range(kmax)):
                out = self.input_npy(cond, k).parent
                cmd = [self.py, "-B", "scripts/i1/null_inputs.py", "--npy", str(self.npy), "--coords", str(self.coords),
                       "--kind", cond, "--k", str(k), "--out", str(out), "--workers", str(self.a.n3_workers)]
                jobs.append({"name": f"null_{self.a.dataset}_{cond}_k{k}", "cmd": cmd, "done": str(out / "meta.json")})
        cheap = [j for j in jobs if "_n3_" not in j["name"]]
        rc = self.run_jobs("nulls", cheap, self.a.k)
        return rc | self.run_jobs("nulls_n3", [j for j in jobs if "_n3_" in j["name"]], 1)

    def fit_job(self, model, cond, k, r, f, folds=None, tag=None) -> dict:
        out = self.out / (tag or self.a.dataset) / model / cond / f"k{k}" / f"r{r}" / f"f{f}"
        cmd = [self.py, "-B", "scripts/i1/run_fold.py", "--model", model, "--repos", str(self.a.data_root / "i1/repos"),
               "--npy", str(self.input_npy(cond, k)), "--folds", str(folds or self.folds), "--fold", str(f),
               "--seed", str(r), "--out", str(out)]
        if cond == "orig" and r == 1 and f in D1_FOLDS and tag is None:
            cmd += ["--save-last", "--d1"]
        return {"name": f"{tag or self.a.dataset}_{model}_{cond}_k{k}_r{r}_f{f}", "cmd": cmd,
                "done": str(out / "summary.json")}

    def phase_fits(self) -> int:
        rc = 0
        for model in self.a.models:
            K, R = KR[model]
            jobs = [self.fit_job(model, cond, k, r, f)
                    for cond in ("orig", "n0") + NULLS for k in (range(1) if cond in ("orig", "n0") else range(K))
                    for r in range(1, R + 1) for f in range(N_FOLDS)]
            rc |= self.run_jobs(f"fits_{model}", jobs, self.a.k)
        return rc

    def phase_site(self) -> int:
        if self.a.dataset != "abide":
            raise SystemExit("site 민감도는 ABIDE 만")
        folds = self.a.data_root / "i1/data/folds_site.json"
        jobs = [self.fit_job(SITE["model"], cond, k, r, f, folds=folds, tag="abide_site")
                for cond in SITE["conds"] for k in (range(1) if cond == "orig" else range(SITE["K"]))
                for r in range(1, SITE["R"] + 1) for f in range(N_FOLDS)]
        return self.run_jobs("site", jobs, self.a.k)

    def phase_baselines(self) -> int:
        jobs = []
        for kind, seeds in BASELINES.items():
            for r in seeds:
                for f in range(N_FOLDS):
                    out = self.out / self.a.dataset / kind / "orig/k0" / f"r{r}" / f"f{f}"
                    cmd = [self.py, "-B", "scripts/i1/baselines.py", "--kind", kind, "--npy", str(self.npy),
                           "--folds", str(self.folds), "--fold", str(f), "--seed", str(r), "--out", str(out)]
                    jobs.append({"name": f"{self.a.dataset}_{kind}_r{r}_f{f}", "cmd": cmd, "done": str(out / "summary.json")})
        return self.run_jobs("baselines", jobs, self.a.k)

    def phase_analyze(self) -> int:
        rc = 0
        tags = [self.a.dataset] + (["abide_site"] if self.a.dataset == "abide" else [])
        for tag in tags:
            base = self.out / tag
            if not base.exists():
                continue
            for model_dir in sorted(p for p in base.iterdir() if p.is_dir()):
                cmd = [self.py, "-B", "scripts/i1/analyze.py", "--root", str(base), "--model", model_dir.name,
                       "--out", str(self.out / "analysis" / tag / f"{model_dir.name}.json"),
                       "--n-items", str(self.n_items), "--n-boot", "2000"]
                if self.samples:
                    cmd += ["--samples", str(self.samples)]
                rc |= subprocess.run(cmd, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}).returncode
        return rc


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dataset", required=True, choices=("abide", "aomic"))
    ap.add_argument("--phase", required=True, choices=("nulls", "fits", "site", "baselines", "analyze"))
    ap.add_argument("--lock", required=True, type=Path)
    ap.add_argument("--doc", required=True, type=Path)
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=MODELS)
    ap.add_argument("--k", type=int, default=2, help="동시 작업 수")
    ap.add_argument("--n3-workers", type=int, default=8)
    a = ap.parse_args(argv[1:])
    v = subprocess.run([sys.executable, "-B", "scripts/i1/build_lock.py", "--verify", "--repo-root", str(ROOT),
                        "--data-root", str(a.data_root), "--doc", str(a.doc), "--out", str(a.lock)],
                       cwd=ROOT, capture_output=True, text=True)
    if v.returncode != 0:
        print(f"잠금 검증 실패 — 실행하지 않는다:\n{v.stdout}{v.stderr}", file=sys.stderr)
        return 3
    m = Main(a)
    m.log(f"START dataset={a.dataset} phase={a.phase} lock={json.loads(a.lock.read_text())['lock_hash'][:12]} "
          f"verify={v.stdout.strip()}")
    rc = getattr(m, f"phase_{a.phase}")()
    m.log(f"END phase={a.phase} rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
