"""R2T 상태 혼합 합성 세계 (결정 84) — 참 상태 수 · 상태별 공분산을 안다.

* n_states = 1 이면 상태 없는 단일 분포 null, > 1 이면 상태가 구별되는 positive control.
* 창마다 상태 하나 (task run 은 창 경계에서만 상태가 바뀜 — 창 단위 추론에 유리한 단순화이며 실제 BOLD 를 대표하지 않음).
* 원 신호 규칙은 `synth.World` 와 같다 (기저 강도 × 이득 × (1 + 0.01 z) + 창마다 선형 drift, z 는 AR(1)).
* 상태 라벨은 oracle (상한 진단) 에만 쓰며 모델 적합 · 예측 함수에는 주지 않는다.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

import synth as S


@dataclass
class MixSpec:
    n_roi: int = 50
    n_factors: int = 4
    n_states: int = 3
    length: int = 15
    rho: float = 0.5
    n_rest_windows: int = 8
    n_task_windows: int = 9
    seed: int = 0


class MixWorld:
    def __init__(self, spec: MixSpec):
        self.spec = spec
        rng = np.random.default_rng(spec.seed)
        self.covs = np.stack([S.make_cov(spec.n_roi, spec.n_factors, rng) for _ in range(spec.n_states)])
        self.chols = np.stack([np.linalg.cholesky(c) for c in self.covs])
        self.base = rng.uniform(400.0, 1200.0, spec.n_roi)
        self.left = np.zeros(spec.n_roi, bool)
        self.left[: spec.n_roi // 2] = True

    def _window(self, state: int, gain: float, rng: np.random.Generator) -> np.ndarray:
        s = self.spec
        z = S.ar1(s.length, self.chols[state], s.rho, rng)
        raw = self.base * gain * (1 + 0.01 * z)
        return raw + np.outer(np.arange(s.length), rng.normal(0, 0.5, s.n_roi))

    def subject(self, sid: str) -> Dict[str, object]:
        s = self.spec
        rng = np.random.default_rng([s.seed, zlib.crc32(sid.encode())])
        gain = rng.uniform(0.7, 1.3)
        rs = rng.integers(0, s.n_states, s.n_rest_windows)
        ts = rng.integers(0, s.n_states, s.n_task_windows)
        return {"rest": [self._window(k, gain, rng) for k in rs], "task": [self._window(k, gain, rng) for k in ts],
                "rest_states": rs, "task_states": ts}

    def oracle_B(self, state: int, obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
        D = np.diag(self.base)
        Sg = D @ self.covs[state] @ D
        return np.linalg.solve(Sg[np.ix_(obs, obs)], Sg[np.ix_(msk, obs)].T).T

    def pooled_B(self, obs: np.ndarray, msk: np.ndarray) -> np.ndarray:
        """상태를 모르고 평균 공분산을 쓰는 참 K=1 기준 (상태 없는 최선)."""
        D = np.diag(self.base)
        Sg = D @ self.covs.mean(0) @ D
        return np.linalg.solve(Sg[np.ix_(obs, obs)], Sg[np.ix_(msk, obs)].T).T
