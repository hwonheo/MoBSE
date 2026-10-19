"""R2T T1 합성 자료 (결정 87) — 기존 추출처럼 run 마다 ROI z-score 한 뒤 15 frame 창으로 자른다. 실제 BOLD 를 대표하지 않는다.

rest: 사람마다 상태 창 8 개 (15 frame) 를 이어 한 run (120 frame) 으로 z-score → 8 창.
task: 상태 창 9 개를 이어 한 run (135 frame) 으로 z-score → 9 창.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

import synth_mix as SM
import synth_variants as SV


def _z(run: np.ndarray) -> np.ndarray:
    return (run - run.mean(0)) / run.std(0)


def make(n_subjects: int = 31, n_roi: int = 40, n_states: int = 3, rho: float = 0.5, seed: int = 0, **variant
         ) -> Tuple[List[str], Dict[str, List[np.ndarray]], Dict[str, List[np.ndarray]], np.ndarray]:
    w = SV.VariantWorld(SM.MixSpec(n_roi=n_roi, n_states=n_states, rho=rho, seed=seed, length=15,
                                   n_rest_windows=8, n_task_windows=9), **variant)
    ids = [f"p{i:03d}" for i in range(n_subjects)]
    rest, task = {}, {}
    for s in ids:
        d = w.subject(s)
        r, t = _z(np.concatenate(d["rest"])), _z(np.concatenate(d["task"]))
        rest[s] = [r[i:i + 15] for i in range(0, 120, 15)]
        task[s] = [t[i:i + 15] for i in range(0, 135, 15)]
    return ids, rest, task, w.left
