#!/usr/bin/env python3
"""학습 변동 측정 — 결정 35 (2026-10-02). T4 곡선 점 넷을 다시 학습해 A−C 가 그대로인지 본다.

T4 의 bootstrap CI 는 "어떤 test subject 가 뽑혔나" 의 변동만 담는다 (계획서 §8 한계).
이 구동기는 빠진 변동 두 가지를 직접 잰다.

* ``seed``  — model seed 세 쌍을 바꾼다. 부분표집 · inner 선택은 본 실행 그대로.
* ``sub``   — 부분표집 seed 바탕 (``curve.subsample_seed_base``) 을 바꾼다. seed 42–44 · 선택은 그대로.

`mobse/v3` 와 v3 잠금은 그대로 둔다. 잠긴 두 값은 **이 프로세스 안에서만** 덮는다
(``--as-cli``: config 스키마의 ``locked_to`` 를 바꾼 뒤 `mobse.v3.cli.main` 을 부른다) —
결정 26 (WI-09) 이 null seed 를 덮은 방식과 같다. 변형 config 는 ``meta.name`` 과 덮은 값만
다르므로 config_hash 가 따로 나오고, 본 실행 산출물과 섞이지 않는다.

Usage (h197, 저장소 사본 루트):
    PYTHONPATH=. python -B scripts/exploratory_v2/run_variability.py --root <out> \
        --main-root <T4 본 실행 root>
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import statistics as stats
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MAIN_CFG = ROOT / "configs/exploratory_v2/main.yaml"
#: 결정 35 의 대상 점 — 점마다 97.5% CI 가 0 을 벗어난 점 중 구조 · 방향을 고루 덮는 넷.
POINTS = [("embedding", 10), ("embedding", 70), ("readout", 20), ("readout", 100)]
SEED_VARIANTS = {"seed1": (45, 46, 47), "seed2": (48, 49, 50),
                 "seed3": (51, 52, 53), "seed4": (54, 55, 56)}
SUB_VARIANTS = {"sub1": 40100, "sub2": 40200, "sub3": 40300, "sub4": 40400}
#: 부분표집 반복을 하지 않는 수준 — 학습 pool 100–101 명에서 최대 1 명만 달라진다.
NO_SUB_LEVELS = {100}
OUTER_INNER_FOLD = 9
THREAD_ENV = {k: "2" for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                               "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_cli(variant_path: str, argv: List[str]) -> int:
    """잠긴 두 값을 프로세스 안에서만 덮고 v3 CLI 를 부른다."""
    from mobse.v3 import cli
    from mobse.v3 import config as C
    var = json.loads(Path(variant_path).read_text(encoding="utf-8"))
    C.SCHEMA["train.model_seeds"] = dataclasses.replace(
        C.SCHEMA["train.model_seeds"], locked_to=tuple(var["model_seeds"]))
    C.SCHEMA["curve.subsample_seed_base"] = dataclasses.replace(
        C.SCHEMA["curve.subsample_seed_base"], locked_to=int(var["subsample_seed_base"]))
    return cli.main(argv)


class Runner:
    def __init__(self, args):
        import yaml
        self.args = args
        self.root = Path(args.root)
        self.main_root = Path(args.main_root)
        d, v = Path(args.data_root), Path(args.data_root) / "derivatives_v3"
        self.p = {"splits": v / "splits_piop1_p7/folds.json",
                  "subjects": v / "cohort_piop1/subjects.jsonl",
                  "windows": v / "windows_piop1.jsonl",
                  "rest": v / "wi02_ds002785_restingstate.jsonl",
                  "tasks": [v / "wi02_ds002785_emomatching.jsonl",
                            v / "wi02_ds002785_workingmemory.jsonl"]}
        (self.root / "configs").mkdir(parents=True, exist_ok=True)
        (self.root / "logs").mkdir(exist_ok=True)
        raw = yaml.safe_load(MAIN_CFG.read_text(encoding="utf-8"))
        self.cells = list(raw["cells"]["names"])
        self.variants: Dict[str, Dict[str, Any]] = {}
        for name, seeds in SEED_VARIANTS.items():
            self.variants[name] = {"model_seeds": list(seeds),
                                   "subsample_seed_base": raw["curve"]["subsample_seed_base"]}
        for name, base in SUB_VARIANTS.items():
            self.variants[name] = {"model_seeds": list(raw["train"]["model_seeds"]),
                                   "subsample_seed_base": base}
        for name, var in self.variants.items():
            r = json.loads(json.dumps(raw))
            r["meta"]["name"] = f"exploratory_v2_variability_{name}"
            r["train"]["model_seeds"] = var["model_seeds"]
            r["curve"]["subsample_seed_base"] = var["subsample_seed_base"]
            cp = self.root / "configs" / f"{name}.yaml"
            jp = self.root / "configs" / f"{name}.json"
            if not cp.exists():
                cp.write_text(yaml.safe_dump(r, allow_unicode=True, sort_keys=False),
                              encoding="utf-8")
                jp.write_text(json.dumps(var), encoding="utf-8")
            var["cfg"], var["json"] = cp, jp
        self.rc_all = 0

    def log(self, msg: str) -> None:
        line = f"{now()} {msg}"
        print(line, flush=True)
        with (self.root / "driver.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def selection(self, s: str, o: int) -> Path:
        return self.main_root / "select" / f"o{o}" / f"selection_{s}.json"

    def run(self, name: str, var: Dict[str, Any], cli_args: List[str], out: Path,
            final: str) -> Dict[str, Any]:
        if (out / final).is_file():
            return {"name": name, "rc": 0, "skipped": True}
        if out.exists() and final == "fit_report.json":
            dest = self.root / "partial" / f"{name.replace('/', '__')}_{int(time.time())}"
            dest.parent.mkdir(exist_ok=True)
            out.rename(dest)
        env = {**os.environ, **THREAD_ENV, "PYTHONPATH": str(ROOT),
               "PYTHONDONTWRITEBYTECODE": "1"}
        t0 = time.time()
        proc = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                               "--as-cli", str(var["json"]), "--", *cli_args],
                              cwd=str(ROOT), env=env, capture_output=True, text=True)
        rec = {"name": name, "rc": proc.returncode, "wall_s": round(time.time() - t0, 2),
               "stdout": proc.stdout.strip().splitlines()[-1:],
               "stderr_tail": proc.stderr.strip().splitlines()[-5:] if proc.returncode else []}
        (self.root / "logs" / f"{name.replace('/', '__')}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return rec

    def jobs(self) -> List[tuple]:
        out = []
        for vname, var in self.variants.items():
            for s, L in POINTS:
                if vname.startswith("sub") and L in NO_SUB_LEVELS:
                    continue
                for o in range(5):
                    sel = self.selection(s, o)
                    cfg_id = json.loads(sel.read_text(encoding="utf-8"))["config_id"]
                    for c in self.cells:
                        for seed in var["model_seeds"]:
                            d = self.root / "outer" / vname / s / f"n{L}" / f"o{o}" / f"{c}_s{seed}"
                            args = ["fit", "--config", str(var["cfg"]),
                                    "--splits", str(self.p["splits"]),
                                    "--subjects", str(self.p["subjects"]),
                                    "--windows", str(self.p["windows"]),
                                    "--rest-manifest", str(self.p["rest"]),
                                    "--task-manifests", *map(str, self.p["tasks"]),
                                    "--cell", c, "--roi-structure", s,
                                    "--n-train-level", str(L), "--outer-fold", str(o),
                                    "--inner-fold", str(OUTER_INNER_FOLD),
                                    "--config-id", str(cfg_id), "--model-seed", str(seed),
                                    "--selection", str(sel), "--device", self.args.device,
                                    "--output-dir", str(d)]
                            out.append((f"{vname}/{s}/n{L}/o{o}/{c}_s{seed}", var, args, d,
                                        "fit_report.json"))
        return out

    def batch(self, label: str, jobs: List[tuple], k: int) -> None:
        self.log(f"== {label}: {len(jobs)} 작업 (k={k}) ==")
        done = fail = skip = 0
        walls: List[float] = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=k) as ex:
            for f in as_completed([ex.submit(self.run, *j) for j in jobs]):
                r = f.result()
                done += 1
                if r.get("skipped"):
                    skip += 1
                elif r["rc"]:
                    fail += 1
                    self.rc_all = 1
                    self.log(f"[fail] {r['name']} rc={r['rc']} {r['stdout']} {r['stderr_tail']}")
                else:
                    walls.append(r["wall_s"])
                if done % 100 == 0 or done == len(jobs):
                    m = sum(walls) / len(walls) if walls else 0
                    self.log(f"   {label} {done}/{len(jobs)} (실패 {fail}, 건너뜀 {skip}, "
                             f"fit 평균 {m:.1f} s, 경과 {time.time() - t0:.0f} s)")
        if fail:
            raise SystemExit(f"{label}: 실패 {fail}")

    def evaluate(self) -> None:
        jobs = []
        for vname, var in self.variants.items():
            for s, L in POINTS:
                if vname.startswith("sub") and L in NO_SUB_LEVELS:
                    continue
                dirs = [str(self.root / "outer" / vname / s / f"n{L}" / f"o{o}" / f"{c}_s{seed}")
                        for o in range(5) for c in self.cells for seed in var["model_seeds"]]
                out = self.root / "evaluate" / vname
                jobs.append((f"evaluate/{vname}/{s}_n{L}", var,
                             ["evaluate", "--config", str(var["cfg"]),
                              "--subjects", str(self.p["subjects"]),
                              "--output-dir", str(out), "--fit-dirs", *dirs],
                             out, f"curve_point_{s}_n{L}.json"))
        self.batch("evaluate", jobs, 1)

    def summarize(self) -> None:
        rows: List[Dict[str, Any]] = []
        for s, L in POINTS:
            def read(p: Path) -> Dict[str, Any]:
                r = json.loads(p.read_text(encoding="utf-8"))
                c = r["contrasts"]
                return {"A": r["cell_balanced_accuracy"]["A"],
                        "C": r["cell_balanced_accuracy"]["C"],
                        "A_minus_C": c["H2_A_minus_C"]["point_estimate"],
                        "A_minus_C_ci": [c["H2_A_minus_C"]["ci_lo"], c["H2_A_minus_C"]["ci_hi"]],
                        "A_minus_B": c["H1_A_minus_B"]["point_estimate"]}
            orig = read(self.main_root / "evaluate" / f"curve_point_{s}_n{L}.json")
            runs = {"original": orig}
            for vname in self.variants:
                p = self.root / "evaluate" / vname / f"curve_point_{s}_n{L}.json"
                if p.is_file():
                    runs[vname] = read(p)
            seed_vals = [orig["A_minus_C"]] + [runs[v]["A_minus_C"] for v in SEED_VARIANTS
                                               if v in runs]
            sub_vals = [orig["A_minus_C"]] + [runs[v]["A_minus_C"] for v in SUB_VARIANTS
                                              if v in runs]
            half = (orig["A_minus_C_ci"][1] - orig["A_minus_C_ci"][0]) / 2
            row = {"roi_structure": s, "n_train_level": L, "runs": runs,
                   "a_minus_c_seed": {"values": seed_vals,
                                      "sd": stats.stdev(seed_vals) if len(seed_vals) > 1 else None,
                                      "range": [min(seed_vals), max(seed_vals)]},
                   "a_minus_c_sub": ({"values": sub_vals, "sd": stats.stdev(sub_vals),
                                      "range": [min(sub_vals), max(sub_vals)]}
                                     if len(sub_vals) > 1 else None),
                   "bootstrap_halfwidth_97_5": half,
                   "sign_original": (1 if orig["A_minus_C_ci"][0] > 0 else
                                     -1 if orig["A_minus_C_ci"][1] < 0 else 0),
                   "n_repeats_same_sign_ci": sum(
                       1 for v, rr in runs.items() if v != "original" and (
                           (orig["A_minus_C_ci"][0] > 0 and rr["A_minus_C_ci"][0] > 0) or
                           (orig["A_minus_C_ci"][1] < 0 and rr["A_minus_C_ci"][1] < 0))),
                   "n_repeats": len(runs) - 1}
            rows.append(row)
            sub = row["a_minus_c_sub"]
            self.log(f"   {s} n{L}: 원판 {orig['A_minus_C']:+.4f} | seed 판 SD "
                     f"{row['a_minus_c_seed']['sd']:.4f} 범위 [{min(seed_vals):+.4f}, "
                     f"{max(seed_vals):+.4f}] | 부분표집 SD "
                     f"{'—' if sub is None else format(sub['sd'], '.4f')} | bootstrap 반폭 "
                     f"{half:.4f} | 같은 방향으로 0 을 벗어난 반복 "
                     f"{row['n_repeats_same_sign_ci']}/{row['n_repeats']}")
        payload = {"schema_version": "v3-variability-0.1", "created_utc": now(),
                   "decision": "결정 35 (2026-10-02)", "points": rows,
                   "variants": {k: {kk: vv for kk, vv in v.items() if kk in
                                    ("model_seeds", "subsample_seed_base")}
                                for k, v in self.variants.items()},
                   "fixed": "inner 선택 (config · 공통 E) 은 본 실행의 것을 그대로 쓴다",
                   "main_root": str(self.main_root)}
        out = self.root / "variability_summary.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log(f"   요약 → {out}")


def main(argv: List[str]) -> int:
    if len(argv) > 1 and argv[1] == "--as-cli":
        sep = argv.index("--")
        return as_cli(argv[2], argv[sep + 1:])
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--main-root", required=True)
    ap.add_argument("--data-root", default="/mnt/data/mp2026/MoBSE_dataset")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=None, help="smoke: fit 앞 N 개만")
    args = ap.parse_args(argv[1:])
    r = Runner(args)
    me = Path(__file__).resolve()
    r.log(f"START k={args.k} limit={args.limit} driver_sha256="
          f"{hashlib.sha256(me.read_bytes()).hexdigest()[:16]}")
    jobs = r.jobs()
    if args.limit:
        r.batch("fit (smoke)", jobs[:args.limit], args.k)
        r.log(f"ALL_RC={r.rc_all}")
        return r.rc_all
    r.batch("fit", jobs, args.k)
    r.evaluate()
    r.summarize()
    r.log(f"ALL_RC={r.rc_all}")
    r.log("== DONE ==")
    return r.rc_all


if __name__ == "__main__":
    sys.exit(main(sys.argv))
