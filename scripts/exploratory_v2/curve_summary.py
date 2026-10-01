#!/usr/bin/env python3
"""T4 곡선 요약 — 결정 34 (2026-10-01) 의 판독 장치. 학습하지 않는다.

``evaluate`` 가 쓴 곡선 점 10 개를 모아 한 표로 만들고, 두 가지를 더한다.

1. **10 점 동시 CI (참고값)** — 주 contrast (H1 · H2) 를 percentile 0.125–99.875 로 다시
   잰다 (곡선 10 점 × 주 contrast 2, Bonferroni). 주 판독은 잠긴 점마다 규칙 (1.25–98.75) 이다.
2. **점마다 MDE** — 그 점에서 실측한 불일치율 π 를 G-b 표 (``gb_power_curve.json``) 에 넣어
   50 % · 80 % 탐지에 필요한 효과를 보간한다 (ρ 0 · 0.5 두 값을 범위로).

`mobse/v3` 를 고치지 않는다 (v3 잠금 유지). 집계와 bootstrap 은 ``evaluate`` 와 **같은
함수** (`mobse.v2.evaluate` · `mobse.v2.statistics`) 와 같은 seed · 같은 index 로 다시 하고,
점마다 CI 를 ``curve_point_*.json`` 과 대조해 하나라도 다르면 멈춘다.

Usage (h197):
    PYTHONPATH=. python -B scripts/exploratory_v2/curve_summary.py --root <driver root> \
        --gb results/exploratory_v2/gb/20261001_gb_power_curve.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mobse.v2 import evaluate as EV                  # noqa: E402
from mobse.v2 import statistics as ST                # noqa: E402
from mobse.v3 import fitting as FIT                  # noqa: E402
from mobse.v3.config import config_hash, load_config  # noqa: E402

N_POINTS, N_PRIMARY = 10, 2
PRIMARY = ("H1_A_minus_B", "H2_A_minus_C")
#: π 를 잴 contrast → 비교 칸.
PI_OF = {"H1_A_minus_B": "B", "H2_A_minus_C": "C", "A_minus_S": "S"}
LABEL = {"H1_A_minus_B": "A−B", "H2_A_minus_C": "A−C", "A_minus_S": "A−S"}


def load_point(root: Path, s: str, level: int, cfg) -> Tuple[Dict, Dict]:
    preds = []
    for o in range(int(cfg["splits.n_outer_folds"])):
        for c in cfg["cells.names"]:
            for seed in cfg["train.model_seeds"]:
                d = root / "outer" / s / f"n{level}" / f"o{o}" / f"{c}_s{seed}"
                for line in (d / "window_predictions.jsonl").read_text(
                        encoding="utf-8").splitlines():
                    row = json.loads(line) if line.strip() else {}
                    if "window_key" not in row:
                        continue
                    preds.append(EV.WindowPrediction(
                        canonical_subject=row["canonical_subject"], group_id=row["group_id"],
                        task=FIT.task_of(row["run_key"]),
                        window_index=int(row["window_key"].rsplit("win-", 1)[1]),
                        model_seed=int(row["model_seed"]), cell=row["cell"],
                        truth=int(row["truth"]), p_class1=float(row["p_class1"])))
    runs = EV.aggregate_runs(preds, n_seeds=len(cfg["train.model_seeds"]))
    s_preds = []
    for o in range(int(cfg["splits.n_outer_folds"])):
        d = root / "souter" / f"n{level}" / f"o{o}"
        for line in (d / "s_window_predictions.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line) if line.strip() else {}
            if "window_key" not in row:
                continue
            s_preds.append(EV.ComparisonWindowPrediction(
                canonical_subject=row["canonical_subject"], group_id=row["group_id"],
                task=FIT.task_of(row["run_key"]),
                window_index=int(row["window_key"].rsplit("win-", 1)[1]), model_seed=None,
                cell="S", truth=int(row["truth"]), p_class1=float(row["p_class1"])))
    s_runs = EV.aggregate_comparison_runs(
        s_preds, cell="S", seeds_by_subject={p.canonical_subject: (None,) for p in s_preds})
    return runs, s_runs


def discordance(runs: Dict, s_runs: Dict, other: str) -> float:
    keys = [(subj, task) for (c, subj, task) in runs if c == "A"]
    src = s_runs if other == "S" else runs
    dis = [bool(runs[("A", k[0], k[1])]["correct"]) != bool(src[(other, k[0], k[1])]["correct"])
           for k in keys]
    return sum(dis) / len(dis)


def interp_mde(gb: Dict, pi: float, rule: str, target: float, rho: float) -> Any:
    rows = sorted((m["pi"], m["mde"]) for m in gb["minimum_detectable_effect"]
                  if m["rule"] == rule and m["target_power"] == target
                  and m["rho_latent"] == rho)
    if pi < rows[0][0]:
        return {"mde": rows[0][1], "note": f"π {pi:.3f} < grid 하한 {rows[0][0]} — 하한 값"}
    if pi > rows[-1][0]:
        return {"mde": None, "note": f"π {pi:.3f} > grid 상한 {rows[-1][0]}"}
    for (p0, m0), (p1, m1) in zip(rows, rows[1:]):
        if p0 <= pi <= p1:
            if m0 is None or m1 is None:
                return {"mde": None, "note": "grid 칸이 상한에 닿음"}
            w = 0.0 if p1 == p0 else (pi - p0) / (p1 - p0)
            return {"mde": m0 + w * (m1 - m0)}
    return {"mde": None}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/exploratory_v2/main.yaml")
    ap.add_argument("--subjects", type=Path, default=Path(
        "/mnt/data/mp2026/MoBSE_dataset/derivatives_v3/cohort_piop1/subjects.jsonl"))
    ap.add_argument("--gb", required=True, type=Path)
    args = ap.parse_args(argv[1:])
    out_path = args.root / "curve_summary.json"
    if out_path.exists():
        raise SystemExit(f"이미 존재한다: {out_path}")
    cfg = load_config(args.config)
    gb = json.loads(args.gb.read_text(encoding="utf-8"))
    group_of = {}
    for line in args.subjects.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            group_of[r["canonical_subject"]] = r["group_id"]
    seed, n_boot = int(cfg["stats.bootstrap_seed"]), int(cfg["stats.n_bootstrap"])
    fw = tuple(cfg["stats.familywise_pct"])
    alpha = 0.05 / (N_POINTS * N_PRIMARY)
    simul = (100 * alpha / 2, 100 * (1 - alpha / 2))

    points: List[Dict[str, Any]] = []
    mismatches: List[str] = []
    for s in cfg["cells.roi_structures"]:
        for L in cfg["curve.levels"]:
            cp = json.loads((args.root / "evaluate" / f"curve_point_{s}_n{L}.json")
                            .read_text(encoding="utf-8"))
            runs, s_runs = load_point(args.root, s, int(L), cfg)
            diffs = EV.primary_contrasts(runs)
            subjects = sorted(diffs["H2_A_minus_C"])
            sub_to_group = {x: group_of[x] for x in subjects}
            idx = ST.bootstrap_indices(sub_to_group, subjects, seed=seed, n_boot=n_boot)
            row: Dict[str, Any] = {"roi_structure": s, "n_train_level": int(L),
                                   "cell_balanced_accuracy": cp["cell_balanced_accuracy"],
                                   "S_balanced_accuracy":
                                       (cp.get("auxiliary") or {}).get("S_balanced_accuracy"),
                                   "contrasts": {}}
            for name in PRIMARY:
                per = ST.paired_bootstrap(diffs[name], sub_to_group, indices=idx, seed=seed,
                                          n_boot=n_boot, pct=fw)
                sim = ST.paired_bootstrap(diffs[name], sub_to_group, indices=idx, seed=seed,
                                          n_boot=n_boot, pct=simul)
                ref = cp["contrasts"][name]
                for key, val in (("point_estimate", per.point), ("ci_lo", per.lo),
                                 ("ci_hi", per.hi)):
                    if abs(float(ref[key]) - float(val)) > 1e-12:
                        mismatches.append(f"{s} n{L} {name} {key}: {ref[key]} vs {val}")
                pi = discordance(runs, s_runs, PI_OF[name])
                row["contrasts"][name] = {
                    "point_estimate": per.point,
                    "per_point_97_5": [per.lo, per.hi],
                    "simultaneous_99_75": [sim.lo, sim.hi],
                    "per_point_lower_gt_0": per.lo > 0,
                    "per_point_lower_gt_delta": per.lo > float(cfg["stats.delta"]),
                    "observed_pi": pi,
                    "mde_per_point": {f"power{int(t * 100)}": [
                        interp_mde(gb, pi, "per_point", t, r)["mde"] for r in (0.0, 0.5)]
                        for t in (0.5, 0.8)},
                }
            aux = (cp.get("auxiliary") or {}).get("A_minus_S")
            if aux:
                pi = discordance(runs, s_runs, "S")
                row["contrasts"]["A_minus_S"] = {
                    "point_estimate": aux["point_estimate"],
                    "nominal_95": [aux["ci_lo"], aux["ci_hi"]], "observed_pi": pi,
                    "role": "auxiliary"}
            row["interaction"] = cp["contrasts"]["interaction"]
            points.append(row)
            print(f"{s:9s} n{L:3d}  A {row['cell_balanced_accuracy']['A']:.3f} "
                  f"B {row['cell_balanced_accuracy']['B']:.3f} "
                  f"C {row['cell_balanced_accuracy']['C']:.3f} "
                  f"D {row['cell_balanced_accuracy']['D']:.3f} "
                  f"S {row['S_balanced_accuracy'] or float('nan'):.3f} | "
                  + " | ".join(f"{LABEL[n]} {v['point_estimate']:+.4f} "
                               f"[{v.get('per_point_97_5', v.get('nominal_95'))[0]:+.4f}, "
                               f"{v.get('per_point_97_5', v.get('nominal_95'))[1]:+.4f}] "
                               f"π {v['observed_pi']:.3f}"
                               for n, v in row["contrasts"].items()), flush=True)
    if mismatches:
        raise SystemExit(f"evaluate 산출과 다시 잰 CI 가 다르다: {mismatches[:3]}")
    payload = {"schema_version": "v3-curve-summary-0.1", "config_hash": config_hash(cfg),
               "rules": {"per_point": list(fw), "simultaneous_reference": list(simul)},
               "decision": "결정 34 — δ 0.02 유지, 점마다 97.5% 주 판독 + 10 점 동시 99.75% 참고",
               "gb_source": {"path": str(args.gb),
                             "sha256": hashlib.sha256(args.gb.read_bytes()).hexdigest()},
               "crosscheck": "점마다 CI 를 다시 계산해 curve_point_*.json 과 대조 — 불일치 0",
               "points": points}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
