#!/usr/bin/env python3
"""I3 G-b 검정력 simulation (결정 67 · 68) — 학습 없음. 기준값을 두지 않는다 (결정 29: 보고 장치).

I3 의 평가 단위는 **블록** (피험자당 8 개, control 4 · emotion 4) 이고, 두 칸 (예: A 와 C) 의 차이는 test 블록 전체의
정확도 차이 (클래스가 블록마다 4:4 로 균형이라 BA 와 같다) 다. CI 는 **피험자 단위 bootstrap** (블록은 사람 안에서 묶임).

생성 모형 (구현 선택):
* 블록마다 두 칸의 판정은 네 가지 — 둘 다 맞음 · A 만 맞음 · C 만 맞음 · 둘 다 틀림. 판정이 갈리는 비율 π 와 차이 δ 로
  P(A 만) = (π + δ) / 2, P(C 만) = (π − δ) / 2.
* 사람마다 δ_i ~ N(δ, τ²) (사람 사이 이질성; τ 0 · 0.05 · 0.10), 확률이 [0, π] 를 벗어나면 잘라 냄.
* 추정치 = 사람별 (A 만 − C 만) 블록 평균의 평균. CI = 사람 재표집 percentile. 주 contrast 2 개 (H1 · H2) 를
  Bonferroni 로 묶은 v1 규칙 97.5 % (1.25–98.75) 와 참고용 95 % 를 함께 낸다.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/h1h2_scope/i3_gb_power.py --out <dir>/i3_gb_power.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

N_SUBJ = 126
N_BLOCK = 8
PIS = (0.10, 0.20, 0.30, 0.40)
DELTAS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
TAUS = (0.0, 0.05, 0.10)


def simulate(pi: float, delta: float, tau: float, rng, n_rep: int, n_boot: int) -> dict:
    lo975, lo95 = [], []
    W = rng.multinomial(N_SUBJ, np.full(N_SUBJ, 1 / N_SUBJ), size=n_boot) / N_SUBJ      # (n_boot, N) 재표집 가중치
    for _ in range(n_rep):
        di = np.clip(rng.normal(delta, tau, N_SUBJ), -pi, pi)
        pa, pc = (pi + di) / 2, (pi - di) / 2
        u = rng.random((N_SUBJ, N_BLOCK))
        d = ((u < pa[:, None]).astype(float) - ((u >= pa[:, None]) & (u < (pa + pc)[:, None]))).mean(axis=1)
        boot = W @ d
        lo975.append(np.percentile(boot, 1.25))
        lo95.append(np.percentile(boot, 2.5))
    return {"p_lower_gt0_975": float(np.mean(np.array(lo975) > 0)), "p_lower_gt0_95": float(np.mean(np.array(lo95) > 0))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-rep", type=int, default=1000)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261016)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    t0 = time.perf_counter()
    grid = []
    for pi in PIS:
        for tau in TAUS:
            for delta in DELTAS:
                if delta > pi:
                    continue
                r = {"pi": pi, "tau": tau, "delta": delta, **simulate(pi, delta, tau, rng, a.n_rep, a.n_boot)}
                grid.append(r)
                print(json.dumps(r), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"schema": "h1h2-scope-i3-gb-0.1", "n_subjects": N_SUBJ, "n_blocks": N_BLOCK,
                                 "n_rep": a.n_rep, "n_boot": a.n_boot, "seed": a.seed,
                                 "seconds": time.perf_counter() - t0, "grid": grid}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
