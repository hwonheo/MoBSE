"""Shared paths and helpers for the ds005270 n-back preprocessing pilot."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO / "configs" / "ds005270" / "protocol_v1.json"
LOCK_PATH = REPO / "results" / "ds005270" / "locks" / "preproc_pilot_lock.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def raw_root(cfg: dict) -> Path:
    return REPO / cfg["dataset"]["raw_root_rel"]


def work_dir(cfg: dict, sub: str) -> Path:
    return REPO / cfg["pilot"]["work_root_rel"] / sub


def deriv_dir(cfg: dict, sub: str) -> Path:
    return REPO / cfg["pilot"]["derivatives_root_rel"] / sub


def input_rel_paths(cfg: dict, sub: str) -> list[str]:
    return [p.replace("<sub>", sub) for p in cfg["pilot"]["inputs_per_subject"]]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def window_starts(B: float, E: float, start_buffer: float, end_buffer: float,
                  tr: float, n_windows: int, window_s: float) -> dict:
    """Return the first-n-windows rule on the TR grid (protocol section 4)."""
    s0 = tr * math.ceil((B + start_buffer) / tr)
    starts = [s0 + window_s * k for k in range(n_windows)]
    end_needed = starts[-1] + window_s
    limit = E - end_buffer
    return {
        "s0": s0,
        "starts_s": starts,
        "first_volume": [int(round(s / tr)) for s in starts],
        "end_needed_s": end_needed,
        "limit_s": limit,
        "fits": bool(end_needed <= limit + 1e-9),
    }
