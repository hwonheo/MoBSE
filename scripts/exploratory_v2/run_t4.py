#!/usr/bin/env python3
"""exploratory v2 실험 구동기 — G-c null 과 T4 저표본 곡선 (2026-10-01 실험 승인).

단계 (``--phase``, 차례대로 돈다)
--------------------------------
1. ``inner``   — 가장 큰 수준 (``curve.grid_selection_level``) 에서 A–D × 구조 2 ×
   config 8 × inner 3 × outer 5 (seed = inner seed 42). 결정 33.
2. ``select``  — outer fold 마다 ``select`` 한 번 (구조마다 A–D 공동 선택).
3. ``sinner``  — S logistic (S1 · S3) × C 8 × inner 3 × outer 5, 같은 수준.
4. ``sselect`` — outer fold 마다 ``select-s``.
5. ``gc``      — G-c null: outer fold 0 · 가장 큰 수준 · seed 42 에서 C·D × 구조 2 ×
   {순열 1..19 · spin 0..19 · rewire 0..19}. 순열 index 0 은 주 null = T4 의 같은 fit 이라
   이 단계가 그 기준 fit (A–D 네 칸) 을 먼저 만든다 (T4 가 나중에 그대로 쓴다).
6. ``gcsum``   — G-c 요약 (학습 없음).
7. ``outer``   — T4: 수준 5 × 구조 2 × A–D × outer 5 × seed 3, 그리고 S outer 수준 5 × 5.
8. ``evaluate``— 곡선 점 10 개 (구조 × 수준), 보조 A−S 포함.

규칙
----
* 하위 명령에 넘기는 값은 **코드 상수와 잠긴 config 에서만** 가져온다 (09-28 aux v1 이
  S 후보 이름을 줄여 써 480 호출이 rc=2 로 끝난 사고의 재발 방지).
* 끝난 fit (최종 산출물이 있는 디렉터리) 은 건너뛴다. 최종 산출물 없이 남은 디렉터리는
  지우지 않고 ``partial/`` 로 **옮긴** 뒤 다시 돈다.
* 프로세스당 스레드 2 · 동시 k (기본 4) — v1 main 과 같은 고정 (resource_budget 9.2).
* 결과는 data root 에만 쓴다. 저장소에는 쓰지 않는다.

Usage (h197, 저장소 사본 루트에서):
    PYTHONPATH=. python -B scripts/exploratory_v2/run_t4.py --root <out> --phase all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mobse.v2 import baselines as BL                 # noqa: E402
from mobse.v3 import fitting as FIT                  # noqa: E402
from mobse.v3 import templates as T3                 # noqa: E402
from mobse.v3 import train as TR3                    # noqa: E402
from mobse.v3.config import config_hash, load_config  # noqa: E402

PHASES = ("inner", "select", "sinner", "sselect", "gc", "gcsum", "outer", "evaluate")
INNER_SEED = 42           # v1 계획서 §7 Inner seed (mobse.v2.train.INNER_SEED)
GC_OUTER_FOLD = 0
GC_SEED = 42
OUTER_INNER_FOLD = 9      # outer fit 표시 (v1 규약, mobse.v2.templates.OUTER_FIT_INNER_FOLD)

THREAD_ENV = {k: "2" for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                               "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Runner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.root = Path(args.root)
        self.cfg_path = Path(args.config)
        self.cfg = load_config(self.cfg_path)
        self.cfg_hash = config_hash(self.cfg)
        d, v = Path(args.data_root), Path(args.data_root) / "derivatives_v3"
        self.paths = {
            "splits": v / "splits_piop1_p7/folds.json",
            "subjects": v / "cohort_piop1/subjects.jsonl",
            "windows": v / "windows_piop1.jsonl",
            "rest": v / "wi02_ds002785_restingstate.jsonl",
            "tasks": [v / "wi02_ds002785_emomatching.jsonl",
                      v / "wi02_ds002785_workingmemory.jsonl"],
            "atlas": d / "atlas_2009c" /
                     "tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz",
        }
        missing = [str(p) for k, p in self.paths.items()
                   for p in (p if isinstance(p, list) else [p]) if not Path(p).exists()]
        if missing:
            raise SystemExit(f"입력이 없다: {missing}")
        self.levels = [int(x) for x in self.cfg["curve.levels"]]
        self.top = int(self.cfg["curve.grid_selection_level"])
        self.structures = list(self.cfg["cells.roi_structures"])
        self.cells = list(self.cfg["cells.names"])
        self.seeds = [int(s) for s in self.cfg["train.model_seeds"]]
        self.n_outer = int(self.cfg["splits.n_outer_folds"])
        self.n_inner = int(self.cfg["splits.n_inner_folds"])
        self.config_ids = [g.config_id for g in TR3.build_grid()]
        self.null_kinds = list(self.cfg["nulls.kinds"])
        self.m = int(self.cfg["nulls.m_per_kind"])
        assert INNER_SEED in self.seeds
        assert tuple(self.cells) == tuple(FIT.CELLS)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "logs").mkdir(exist_ok=True)
        self.log_path = self.root / "driver.log"
        self.rc_all = 0

    # ------------------------------------------------------------------ #
    def log(self, msg: str) -> None:
        line = f"{now()} {msg}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def common(self) -> List[str]:
        p = self.paths
        return ["--config", str(self.cfg_path), "--splits", str(p["splits"]),
                "--subjects", str(p["subjects"]), "--windows", str(p["windows"])]

    def fit_cmd(self, out: Path, *, cell: str, structure: str, level: int, outer: int,
                inner: int, config_id: int, seed: int, selection: Path | None = None,
                null_kind: str = "permutation", null_index: int = 0) -> List[str]:
        cmd = ["fit", *self.common(), "--rest-manifest", str(self.paths["rest"]),
               "--task-manifests", *map(str, self.paths["tasks"]),
               "--cell", cell, "--roi-structure", structure, "--n-train-level", str(level),
               "--outer-fold", str(outer), "--inner-fold", str(inner),
               "--config-id", str(config_id), "--model-seed", str(seed),
               "--device", self.args.device, "--output-dir", str(out)]
        if selection is not None:
            cmd += ["--selection", str(selection)]
        if (null_kind, null_index) != ("permutation", 0):
            cmd += ["--null-kind", null_kind, "--null-index", str(null_index)]
            if null_kind == "spin":
                cmd += ["--atlas", str(self.paths["atlas"])]
        return cmd

    def fit_s_cmd(self, out: Path, *, level: int, outer: int, inner: int,
                  candidate: str | None = None, setting_id: str | None = None,
                  selection: Path | None = None) -> List[str]:
        cmd = ["fit-s", *self.common(), "--task-manifests", *map(str, self.paths["tasks"]),
               "--n-train-level", str(level), "--outer-fold", str(outer),
               "--inner-fold", str(inner), "--output-dir", str(out)]
        if selection is not None:
            cmd += ["--selection", str(selection)]
        else:
            cmd += ["--candidate", candidate, "--setting-id", setting_id]
        return cmd

    # ------------------------------------------------------------------ #
    def _one(self, name: str, cmd: List[str], out: Path, final: str,
             move_partial: bool = True) -> Dict[str, Any]:
        if (out / final).is_file():
            return {"name": name, "rc": 0, "skipped": True}
        if move_partial and out.exists():
            dest = self.root / "partial" / f"{name.replace('/', '__')}_{int(time.time())}"
            dest.parent.mkdir(exist_ok=True)
            shutil.move(str(out), str(dest))
            self.log(f"[partial] {name} → {dest}")
        env = {**os.environ, **THREAD_ENV, "PYTHONPATH": str(ROOT),
               "PYTHONDONTWRITEBYTECODE": "1"}
        t0 = time.time()
        proc = subprocess.run([sys.executable, "-B", "-m", "mobse.v3.cli", *cmd],
                              cwd=str(ROOT), env=env, capture_output=True, text=True)
        wall = time.time() - t0
        rec = {"name": name, "rc": proc.returncode, "wall_s": round(wall, 2),
               "stdout": proc.stdout.strip().splitlines()[-1:] if proc.stdout else [],
               "stderr_tail": proc.stderr.strip().splitlines()[-5:] if proc.returncode else []}
        (self.root / "logs" / f"{name.replace('/', '__')}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return rec

    def run_batch(self, label: str, jobs: Sequence[tuple]) -> None:
        """jobs: (name, cmd, out_dir, final_file[, move_partial])."""
        todo = len(jobs)
        self.log(f"== {label}: {todo} 작업 (k={self.args.k}) ==")
        done = fail = skip = 0
        walls: List[float] = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=self.args.k) as ex:
            futs = [ex.submit(self._one, *j) for j in jobs]
            for f in as_completed(futs):
                r = f.result()
                done += 1
                if r.get("skipped"):
                    skip += 1
                elif r["rc"] != 0:
                    fail += 1
                    self.rc_all = 1
                    self.log(f"[fail] {r['name']} rc={r['rc']} {r['stdout']} {r['stderr_tail']}")
                else:
                    walls.append(r["wall_s"])
                if done % 50 == 0 or done == todo:
                    mean = sum(walls) / len(walls) if walls else 0
                    self.log(f"   {label} {done}/{todo} (실패 {fail}, 건너뜀 {skip}, "
                             f"fit 평균 {mean:.1f} s, 경과 {time.time() - t0:.0f} s)")
        if fail:
            raise SystemExit(f"{label}: 실패 {fail} — 다음 단계로 가지 않는다")

    # ------------------------------------------------------------------ #
    def inner_dir(self, s, o, c, k, i) -> Path:
        return self.root / "inner" / s / f"o{o}" / f"{c}_c{k}_i{i}"

    def phase_inner(self) -> None:
        jobs = []
        for o in range(self.n_outer):
            for s in self.structures:
                for c in self.cells:
                    for k in self.config_ids:
                        for i in range(self.n_inner):
                            out = self.inner_dir(s, o, c, k, i)
                            jobs.append((f"inner/{s}/o{o}/{c}_c{k}_i{i}",
                                         self.fit_cmd(out, cell=c, structure=s,
                                                      level=self.top, outer=o, inner=i,
                                                      config_id=k, seed=INNER_SEED),
                                         out, "fit_report.json"))
        self.run_batch("inner", jobs)

    def selection(self, s: str, o: int) -> Dict[str, Any]:
        p = self.root / "select" / f"o{o}" / f"selection_{s}.json"
        return json.loads(p.read_text(encoding="utf-8")) | {"_path": str(p)}

    def phase_select(self) -> None:
        jobs = []
        for o in range(self.n_outer):
            out = self.root / "select" / f"o{o}"
            dirs = [str(self.inner_dir(s, o, c, k, i)) for s in self.structures
                    for c in self.cells for k in self.config_ids for i in range(self.n_inner)]
            final = f"selection_{sorted(self.structures)[-1]}.json"
            jobs.append((f"select/o{o}", ["select", "--config", str(self.cfg_path),
                                          "--output-dir", str(out), "--fit-dirs", *dirs],
                         out, final))
        self.run_batch("select", jobs)
        for o in range(self.n_outer):
            for s in self.structures:
                sel = self.selection(s, o)
                self.log(f"   select o{o} {s}: config {sel['config_id']} "
                         f"E {sel['common_epochs']} (inner 창 {sel['inner_train_windows']})")

    def sinner_dir(self, o, cand, sid, i) -> Path:
        return self.root / "sinner" / f"o{o}" / f"{cand}_{sid}_i{i}"

    def phase_sinner(self) -> None:
        jobs = []
        for o in range(self.n_outer):
            for cand, sid, _ in BL.logistic_settings():
                for i in range(self.n_inner):
                    out = self.sinner_dir(o, cand, sid, i)
                    jobs.append((f"sinner/o{o}/{cand}_{sid}_i{i}",
                                 self.fit_s_cmd(out, level=self.top, outer=o, inner=i,
                                                candidate=cand, setting_id=sid),
                                 out, "s_fit_report.json"))
        self.run_batch("sinner", jobs)

    def phase_sselect(self) -> None:
        jobs = []
        for o in range(self.n_outer):
            out = self.root / "sselect" / f"o{o}"
            dirs = [str(self.sinner_dir(o, c, sid, i)) for c, sid, _ in BL.logistic_settings()
                    for i in range(self.n_inner)]
            jobs.append((f"sselect/o{o}", ["select-s", "--config", str(self.cfg_path),
                                           "--outer-fold", str(o), "--output-dir", str(out),
                                           "--fit-dirs", *dirs],
                         out, f"selection_s_o{o}.json"))
        self.run_batch("sselect", jobs)
        for o in range(self.n_outer):
            p = self.root / "sselect" / f"o{o}" / f"selection_s_o{o}.json"
            rec = json.loads(p.read_text(encoding="utf-8"))
            self.log(f"   sselect o{o}: {rec['candidate']} {rec['setting_id']} "
                     f"(inner loss {rec['inner_loss']:.4f})")

    def outer_dir(self, s, level, o, c, seed) -> Path:
        return self.root / "outer" / s / f"n{level}" / f"o{o}" / f"{c}_s{seed}"

    def outer_job(self, s, level, o, c, seed) -> tuple:
        sel = self.selection(s, o)
        out = self.outer_dir(s, level, o, c, seed)
        return (f"outer/{s}/n{level}/o{o}/{c}_s{seed}",
                self.fit_cmd(out, cell=c, structure=s, level=level, outer=o,
                             inner=OUTER_INNER_FOLD, config_id=int(sel["config_id"]),
                             seed=seed, selection=Path(sel["_path"])),
                out, "fit_report.json")

    def gc_dir(self, s, c, kind, idx) -> Path:
        return self.root / "gc" / s / f"{c}_{kind}{idx:02d}"

    def phase_gc(self) -> None:
        o = GC_OUTER_FOLD
        ref = [self.outer_job(s, self.top, o, c, GC_SEED)
               for s in self.structures for c in self.cells]
        self.run_batch("gc-ref (T4 의 같은 fit)", ref)
        jobs = []
        for s in self.structures:
            sel = self.selection(s, o)
            for c in ("C", "D"):
                for kind in self.null_kinds:
                    for idx in range(self.m):
                        if (kind, idx) == ("permutation", 0):
                            continue              # 주 null — 위 기준 fit 이 그것이다
                        out = self.gc_dir(s, c, kind, idx)
                        jobs.append((f"gc/{s}/{c}_{kind}{idx:02d}",
                                     self.fit_cmd(out, cell=c, structure=s, level=self.top,
                                                  outer=o, inner=OUTER_INNER_FOLD,
                                                  config_id=int(sel["config_id"]),
                                                  seed=GC_SEED,
                                                  selection=Path(sel["_path"]),
                                                  null_kind=kind, null_index=idx),
                                     out, "fit_report.json"))
        self.run_batch("gc", jobs)

    def phase_gcsum(self) -> None:
        def rep(p: Path) -> Dict[str, Any]:
            r = json.loads((p / "fit_report.json").read_text(encoding="utf-8"))
            return {"ba": float(r["eval_balanced_accuracy"]), "loss": float(r["eval_loss"])}
        out: Dict[str, Any] = {"schema_version": "v3-gc-summary-0.1", "created_utc": now(),
                               "outer_fold": GC_OUTER_FOLD, "model_seed": GC_SEED,
                               "n_train_level": self.top, "config_hash": self.cfg_hash,
                               "unit": "outer fold 0 test 창 → run 확률 (seed 하나), "
                                       "fit_report 의 eval_balanced_accuracy · eval_loss",
                               "structures": {}}
        for s in self.structures:
            refs = {c: rep(self.outer_dir(s, self.top, GC_OUTER_FOLD, c, GC_SEED))
                    for c in self.cells}
            block: Dict[str, Any] = {"reference": refs, "null": {}}
            for c in ("C", "D"):
                block["null"][c] = {}
                for kind in self.null_kinds:
                    vals = []
                    for idx in range(self.m):
                        p = (self.outer_dir(s, self.top, GC_OUTER_FOLD, c, GC_SEED)
                             if (kind, idx) == ("permutation", 0) else self.gc_dir(s, c, kind, idx))
                        vals.append({"index": idx, **rep(p)})
                    bas = [v["ba"] for v in vals]
                    a_ba = refs["A" if c == "C" else "B"]["ba"]
                    a_loss = refs["A" if c == "C" else "B"]["loss"]
                    block["null"][c][kind] = {
                        "samples": vals, "ba_min": min(bas), "ba_max": max(bas),
                        "ba_mean": sum(bas) / len(bas),
                        "compare_to": "A" if c == "C" else "B",
                        "n_null_ba_ge_brain": sum(b >= a_ba for b in bas),
                        "n_null_loss_le_brain": sum(v["loss"] <= a_loss for v in vals),
                        "m": len(vals)}
            out["structures"][s] = block
        p = self.root / "gc_summary.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log(f"   gc 요약 → {p}")
        for s, b in out["structures"].items():
            for c in ("C", "D"):
                ref = "A" if c == "C" else "B"
                row = " · ".join(f"{k} {v['ba_min']:.3f}–{v['ba_max']:.3f} "
                                 f"(≥{ref} {v['n_null_ba_ge_brain']}/{v['m']})"
                                 for k, v in b["null"][c].items())
                self.log(f"   {s} {c}: {ref} {b['reference'][ref]['ba']:.3f} | {row}")

    def phase_outer(self) -> None:
        jobs = [self.outer_job(s, L, o, c, seed) for L in sorted(self.levels, reverse=True)
                for s in self.structures for o in range(self.n_outer)
                for c in self.cells for seed in self.seeds]
        sjobs = []
        for L in self.levels:
            for o in range(self.n_outer):
                out = self.root / "souter" / f"n{L}" / f"o{o}"
                sel = self.root / "sselect" / f"o{o}" / f"selection_s_o{o}.json"
                sjobs.append((f"souter/n{L}/o{o}",
                              self.fit_s_cmd(out, level=L, outer=o, inner=OUTER_INNER_FOLD,
                                             selection=sel),
                              out, "s_fit_report.json"))
        self.run_batch("outer", jobs)
        self.run_batch("souter", sjobs)

    def phase_evaluate(self) -> None:
        jobs = []
        for s in self.structures:
            for L in self.levels:
                dirs = [str(self.outer_dir(s, L, o, c, seed)) for o in range(self.n_outer)
                        for c in self.cells for seed in self.seeds]
                sdirs = [str(self.root / "souter" / f"n{L}" / f"o{o}")
                         for o in range(self.n_outer)]
                out = self.root / "evaluate"
                jobs.append((f"evaluate/{s}_n{L}",
                             ["evaluate", "--config", str(self.cfg_path),
                              "--subjects", str(self.paths["subjects"]),
                              "--output-dir", str(out), "--fit-dirs", *dirs,
                              "--s-fit-dirs", *sdirs],
                             out, f"curve_point_{s}_n{L}.json", False))
        # 곡선 점은 같은 디렉터리에 쓰이므로 한 번에 하나씩 (k=1) 돈다.
        k, self.args.k = self.args.k, 1
        try:
            self.run_batch("evaluate", jobs)
        finally:
            self.args.k = k
        for s in self.structures:
            for L in self.levels:
                rec = json.loads((self.root / "evaluate" / f"curve_point_{s}_n{L}.json")
                                 .read_text(encoding="utf-8"))
                h2 = rec["contrasts"]["H2_A_minus_C"]
                aux = (rec.get("auxiliary") or {}).get("A_minus_S") or {}
                ba = rec["cell_balanced_accuracy"]
                self.log(f"   {s} n{L}: A {ba['A']:.3f} C {ba['C']:.3f} | A−C "
                         f"{h2['point_estimate']:+.4f} [{h2['ci_lo']:+.4f}, {h2['ci_hi']:+.4f}]"
                         f" | A−S {aux.get('point_estimate', float('nan')):+.4f}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--data-root", default="/mnt/data/mp2026/MoBSE_dataset")
    ap.add_argument("--config", default=str(ROOT / "configs/exploratory_v2/main.yaml"))
    ap.add_argument("--phase", default="all", choices=("all",) + PHASES)
    ap.add_argument("--until", default=None, choices=PHASES,
                    help="all 일 때 이 단계까지만 돈다")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args(argv[1:])
    r = Runner(args)
    me = Path(__file__).resolve()
    r.log(f"START phase={args.phase} until={args.until} k={args.k} config_hash="
          f"{r.cfg_hash} driver_sha256={hashlib.sha256(me.read_bytes()).hexdigest()[:16]}")
    phases = PHASES if args.phase == "all" else (args.phase,)
    if args.until:
        phases = phases[:phases.index(args.until) + 1]
    for ph in phases:
        t0 = time.time()
        getattr(r, f"phase_{ph}")()
        r.log(f"-- {ph} 끝 ({time.time() - t0:.0f} s)")
    r.log(f"ALL_RC={r.rc_all}")
    r.log("== DONE ==")
    return r.rc_all


if __name__ == "__main__":
    sys.exit(main(sys.argv))
