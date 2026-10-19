"""R2T T1 어려운 합성 세계 (결정 88 · 실패 경계용) — 기존 `synth_t1` 세계와 섞지 않는다. 실제 BOLD 를 대표하지 않는다.

* sep: 상태 공분산 = corr((1 − sep) · 공통 + sep · 상태 고유). 1 이면 상태끼리 독립 (기존 세계와 같은 종류).
* dwell · phase: 상태 지속 frame 수와 시작 위상. aligned 는 15 frame 분석 창과 경계가 맞음, random 은 run 마다 위상 무작위.
* z 는 frame 마다 그 frame 상태의 Cholesky 를 쓰는 AR(1). 원 신호 = 기저 × 이득 × (1 + 0.01 z) + 15 frame 창마다 선형 drift.
* task_bank_seed: task 를 rest 와 **다른** 상태 공분산 묶음 (같은 sep 규칙, 다른 seed) 에서 만든다 (잘못된 state bank). None 이면 같은 묶음.
* run 마다 ROI z-score 뒤 15 frame 창 (rest 120 frame → 8 창, task 135 → 9 창). frame 별 참 상태는 진단용으로만 돌려준다.
"""
from __future__ import annotations

import zlib
from typing import Dict, List, Tuple

import numpy as np

import synth as S

WIN = 15


def _corr(C: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.diag(C))
    return C / np.outer(d, d)


class HardWorld:
    def __init__(self, n_roi=100, n_states=3, sep=1.0, dwell=15, phase="aligned", rho=0.5, seed=0, n_factors=4,
                 task_bank_seed=None):
        rng = np.random.default_rng([seed, 88])
        shared = S.make_cov(n_roi, n_factors, rng)
        own = [S.make_cov(n_roi, n_factors, rng) for _ in range(n_states)]
        self.covs = np.stack([_corr((1 - sep) * shared + sep * o) for o in own])
        self.chols = np.stack([np.linalg.cholesky(c) for c in self.covs])
        self.base = rng.uniform(400.0, 1200.0, n_roi)
        self.left = np.zeros(n_roi, bool)
        self.left[: n_roi // 2] = True
        self.task_chols = self.chols
        if task_bank_seed is not None:
            r2 = np.random.default_rng([task_bank_seed, 88])
            sh2 = S.make_cov(n_roi, n_factors, r2)
            tc = np.stack([_corr((1 - sep) * sh2 + sep * S.make_cov(n_roi, n_factors, r2)) for _ in range(n_states)])
            self.task_chols = np.stack([np.linalg.cholesky(c) for c in tc])
        self.n_roi, self.n_states, self.dwell, self.phase, self.rho, self.seed = n_roi, n_states, dwell, phase, rho, seed

    def _run(self, T: int, gain: float, rng, chols=None) -> Tuple[np.ndarray, np.ndarray]:
        chols = self.chols if chols is None else chols
        off = 0 if self.phase == "aligned" else int(rng.integers(0, self.dwell))
        seg = (np.arange(T) + off) // self.dwell
        st = rng.integers(0, self.n_states, seg.max() + 1)[seg]
        e = rng.normal(size=(T, self.n_roi))
        z = np.empty_like(e)
        a = np.sqrt(1 - self.rho ** 2)
        z[0] = chols[st[0]] @ e[0]
        for t in range(1, T):
            z[t] = self.rho * z[t - 1] + a * (chols[st[t]] @ e[t])
        raw = self.base * gain * (1 + 0.01 * z)
        for i in range(0, T, WIN):
            raw[i:i + WIN] += np.outer(np.arange(min(WIN, T - i)), rng.normal(0, 0.5, self.n_roi))
        return raw, st

    def subject(self, sid: str) -> Dict[str, object]:
        rng = np.random.default_rng([self.seed, zlib.crc32(sid.encode()), 11])
        gain = rng.uniform(0.7, 1.3)
        r, rs = self._run(120, gain, rng)
        t, ts = self._run(135, gain, rng, self.task_chols)
        return {"rest": r, "task": t, "rest_states": rs, "task_states": ts}


def _z(run):
    return (run - run.mean(0)) / run.std(0)


def make(n_subjects=31, seed=0, **kw):
    w = HardWorld(seed=seed, **kw)
    ids = [f"h{i:03d}" for i in range(n_subjects)]
    rest, task, states = {}, {}, {}
    for s in ids:
        d = w.subject(s)
        r, t = _z(d["rest"]), _z(d["task"])
        rest[s] = [r[i:i + WIN] for i in range(0, 120, WIN)]
        task[s] = [t[i:i + WIN] for i in range(0, 135, WIN)]
        states[s] = (d["rest_states"], d["task_states"])
    return ids, rest, task, w.left, states
