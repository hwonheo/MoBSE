"""R2T 단계 0 합성 자료 — 참 공분산을 아는 K=1 자료 (결정 83).

원 신호 = ROI 기저 강도 × 피험자 이득 × (1 + 0.01 z) + 창마다 선형 drift.
z 는 공간 공분산 Σ (factor + 대각) 를 가진 정상 AR(1) 과정 (ρ) 이라 frame 사이 자기상관이 있다.
W-local 처리 뒤의 참 공분산은 D Σ D (D = 기저 강도 대각) 와 비례하므로 oracle 조건부 예측을 계산할 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass
import zlib
from typing import Dict, List

import numpy as np


@dataclass
class SynthSpec:
    n_roi: int = 100
    n_factors: int = 8
    length: int = 15
    rho: float = 0.5
    n_rest_windows: int = 8
    task_frames: int = 135
    seed: int = 0


def make_cov(n_roi: int, n_factors: int, rng: np.random.Generator) -> np.ndarray:
    F = rng.normal(size=(n_roi, n_factors))
    S = F @ F.T + np.diag(rng.uniform(0.5, 1.5, n_roi))
    d = np.sqrt(np.diag(S))
    return S / np.outer(d, d)


def ar1(n: int, chol: np.ndarray, rho: float, rng: np.random.Generator) -> np.ndarray:
    """정상 AR(1) — 주변 공분산 = chol chol^T."""
    e = rng.normal(size=(n, chol.shape[0])) @ chol.T
    z = np.empty_like(e)
    z[0] = e[0]
    a = np.sqrt(1 - rho ** 2)
    for t in range(1, n):
        z[t] = rho * z[t - 1] + a * e[t]
    return z


class World:
    """피험자 · 창을 만드는 합성 세계."""

    def __init__(self, spec: SynthSpec):
        self.spec = spec
        rng = np.random.default_rng(spec.seed)
        self.cov = make_cov(spec.n_roi, spec.n_factors, rng)
        self.chol = np.linalg.cholesky(self.cov)
        self.base = rng.uniform(400.0, 1200.0, spec.n_roi)
        self.left = np.zeros(spec.n_roi, bool)
        self.left[: spec.n_roi // 2] = True
        self._rng = rng

    def _raw(self, z: np.ndarray, gain: float, rng: np.random.Generator, drift_windows: int) -> np.ndarray:
        raw = self.base * gain * (1 + 0.01 * z)
        L = len(z) // drift_windows
        t = np.arange(L)
        for i in range(drift_windows):
            raw[i * L:(i + 1) * L] += np.outer(t, rng.normal(0, 0.5, z.shape[1]))
        return raw

    def subject(self, sid: str) -> Dict[str, object]:
        s = self.spec
        rng = np.random.default_rng([s.seed, zlib.crc32(sid.encode())])   # 프로세스와 무관한 결정론 seed
        gain = rng.uniform(0.7, 1.3)
        rest = []
        for _ in range(s.n_rest_windows):
            z = ar1(s.length, self.chol, s.rho, rng)
            rest.append(self._raw(z, gain, rng, 1))
        z = ar1(s.task_frames, self.chol, s.rho, rng)
        n_w = s.task_frames // s.length
        run = self._raw(z, gain, rng, n_w)
        return {"rest": rest, "run": run}

    def oracle_B(self, obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
        """W-local 처리 신호에서의 참 조건부 계수 (|M| × |O|)."""
        D = np.diag(self.base)
        S = D @ self.cov @ D
        return np.linalg.solve(S[np.ix_(obs, obs)], S[np.ix_(msk, obs)].T).T


def task_windows(run: np.ndarray, length: int) -> List[np.ndarray]:
    return [np.array(run[i:i + length]) for i in range(0, run.shape[0] - length + 1, length)]
