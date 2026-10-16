#!/usr/bin/env python3
"""PIOP2 확증 검정력 (결정 77, 학습 없음 · PIOP2 성능 값 안 봄) — I3 본 실행의 피험자별 차이를 PIOP2 규모로 다시 뽑는다.

대조: B_embedding − S_fc_logistic, B_embedding − D_embedding_spin, B_embedding − D_embedding (순열).
피험자별 차이 d_i (블록 8 개 정확도 차, seed 3 평균 확률) 의 분포를 I3 126 명에서 가져와, 참 효과를 θ 로 옮긴 뒤
(d_i − mean(d) + θ) 189 명을 복원 추출 → 피험자 bootstrap percentile CI (2 주장 Bonferroni 97.5 % · 참고 95 %) 의 하한 > 0 비율.
θ 는 I3 점추정 · 그 절반 · 0 (보정). 첫 짝 제외 판도 같이 낸다. I3 점추정은 결과를 보고 고른 대조라 낙관적이다 (winner's curse).

Usage:
    PYTHONPATH=. .venv/bin/python -B scripts/piop2_confirm/power.py --run data/i3/main/20261016_1bc3622d_a1 --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i3"))
import analyze  # noqa: E402

PAIRS = [("B_embedding", "S_fc_logistic"), ("B_embedding", "D_embedding_spin"), ("B_embedding", "D_embedding")]
N_TARGET, N_SIM, N_BOOT, SEED = 189, 2000, 1000, 20261016


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg = json.loads((a.run / "run_config.json").read_text())
    names = sorted({p for pair in PAIRS for p in pair} - {"S_fc_logistic"})
    preds = {n: analyze.load_cell(a.run, n, cfg["n_outer"], cfg["seeds"]) for n in names}
    preds["S_fc_logistic"] = analyze.load_s(a.run, "S_fc_logistic", cfg["n_outer"])
    keys = sorted(preds[names[0]])
    subjects = sorted({s for s, _ in keys})
    rng = np.random.default_rng(SEED)
    out = {"n_target": N_TARGET, "n_sim": N_SIM, "n_boot": N_BOOT, "seed": SEED, "source_run": str(a.run), "pairs": {}}
    for x, y in PAIRS:
        for tag, keep in (("all", lambda b: True), ("no_first_pair", lambda b: b >= 2)):
            d = []
            for s in subjects:
                ks = [k for k in keys if k[0] == s and keep(k[1])]
                acc = lambda n: np.mean([(preds[n][k][1] > 0.5) == (preds[n][k][0] == 1) for k in ks])  # noqa: E731
                d.append(acc(x) - acc(y))
            d = np.array(d)
            res = {"i3_mean": float(d.mean()), "i3_sd": float(d.std(ddof=1)), "power": {}}
            for lab, theta in (("theta_i3", d.mean()), ("theta_half", d.mean() / 2), ("theta_0", 0.0)):
                base = d - d.mean() + theta
                hit975, hit95 = 0, 0
                for _ in range(N_SIM):
                    smp = rng.choice(base, size=N_TARGET, replace=True)
                    bm = smp[rng.integers(0, N_TARGET, size=(N_BOOT, N_TARGET))].mean(1)
                    hit975 += np.percentile(bm, 1.25) > 0
                    hit95 += np.percentile(bm, 2.5) > 0
                res["power"][lab] = {"theta": float(theta), "p_lo_gt0_97.5": hit975 / N_SIM, "p_lo_gt0_95": hit95 / N_SIM}
            out["pairs"][f"{x}-{y}:{tag}"] = res
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    for k, v in out["pairs"].items():
        print(k, f"mean {v['i3_mean']:+.3f} sd {v['i3_sd']:.3f}",
              {l: (round(p['theta'], 3), p['p_lo_gt0_97.5']) for l, p in v["power"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
