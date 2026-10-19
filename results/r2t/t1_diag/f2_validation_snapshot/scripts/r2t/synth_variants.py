"""R2T 합성 변형 세계 (결정 85) — 사전에 정한 소규모 회귀시험용. `synth_mix.MixWorld` 는 바꾸지 않고 상속한다.

* state_probs: 상태 빈도 (희박 상태 시험). None 이면 균등.
* overlap: 상태 1 의 공분산을 상태 0 과 거의 같게 (성분 중복 시험).
* task_bank_seed: task 창을 rest 와 **다른** 상태 공분산 묶음에서 만든다 (잘못된 state bank 시험).
실제 BOLD 를 대표하지 않는다.
"""
from __future__ import annotations

import zlib
from typing import Dict, Optional, Sequence

import numpy as np

import synth as S
import synth_mix as SM


class VariantWorld(SM.MixWorld):
    def __init__(self, spec: SM.MixSpec, state_probs: Optional[Sequence[float]] = None, overlap: bool = False,
                 task_bank_seed: Optional[int] = None):
        super().__init__(spec)
        self.state_probs = None if state_probs is None else np.asarray(state_probs, float)
        if overlap and spec.n_states >= 2:
            rng = np.random.default_rng(spec.seed + 991)
            E = rng.normal(size=self.covs[0].shape) * 0.01
            C = self.covs[0] + (E + E.T) / 2
            d = np.sqrt(np.diag(C))
            self.covs[1] = C / np.outer(d, d)
            self.chols[1] = np.linalg.cholesky(self.covs[1])
        self.task_chols = self.chols
        if task_bank_seed is not None:
            rng = np.random.default_rng(task_bank_seed)
            tc = np.stack([S.make_cov(spec.n_roi, spec.n_factors, rng) for _ in range(spec.n_states)])
            self.task_covs = tc
            self.task_chols = np.stack([np.linalg.cholesky(c) for c in tc])

    def _draw(self, rng, n):
        s = self.spec
        if self.state_probs is None:
            return rng.integers(0, s.n_states, n)
        return rng.choice(s.n_states, size=n, p=self.state_probs)

    def _window_c(self, chol, gain, rng):
        s = self.spec
        z = S.ar1(s.length, chol, s.rho, rng)
        raw = self.base * gain * (1 + 0.01 * z)
        return raw + np.outer(np.arange(s.length), rng.normal(0, 0.5, s.n_roi))

    def subject(self, sid: str) -> Dict[str, object]:
        s = self.spec
        rng = np.random.default_rng([s.seed, zlib.crc32(sid.encode()), 7])
        gain = rng.uniform(0.7, 1.3)
        rs, ts = self._draw(rng, s.n_rest_windows), self._draw(rng, s.n_task_windows)
        return {"rest": [self._window_c(self.chols[k], gain, rng) for k in rs],
                "task": [self._window_c(self.task_chols[k], gain, rng) for k in ts],
                "rest_states": rs, "task_states": ts}
