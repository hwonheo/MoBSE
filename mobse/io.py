from __future__ import annotations

import glob
from pathlib import Path
from typing import Tuple

from mobse.config import ExperimentConfig


def _latest_match(pattern: str) -> Path:
    files = sorted((Path(p) for p in glob.glob(pattern)), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No files found for pattern: {pattern}")
    return files[-1]


def resolve_template_inputs(cfg: ExperimentConfig) -> Tuple[Path, Path]:
    if cfg.model.template_bank_path:
        template_path = Path(cfg.model.template_bank_path)
    else:
        key = f"atlas{cfg.model.num_nodes}_sp{int(cfg.template.default_sparsity * 100)}_{cfg.template.output_name}"
        run_local = Path(cfg.artifacts.root_dir) / str(cfg.artifacts.run_id) / "templates" / key
        if run_local.exists():
            template_path = run_local
        else:
            pattern = f"{cfg.artifacts.root_dir}/*/templates/{key}"
            try:
                template_path = _latest_match(pattern)
            except FileNotFoundError as exc:
                raise FileNotFoundError(
                    f"{exc} -- Build templates first: `python -m mobse.cli build_templates --config <config>`"
                ) from exc

    if cfg.model.os_windows_path:
        windows_path = Path(cfg.model.os_windows_path)
    else:
        primary = f"{cfg.artifacts.root_dir}/*/templates/os_windows_nodes{cfg.model.num_nodes}.npz"
        legacy = f"{cfg.artifacts.root_dir}/*/templates/hcp_windows_nodes{cfg.model.num_nodes}.npz"
        run_templates = Path(cfg.artifacts.root_dir) / str(cfg.artifacts.run_id) / "templates"
        run_primary = run_templates / f"os_windows_nodes{cfg.model.num_nodes}.npz"
        run_legacy = run_templates / f"hcp_windows_nodes{cfg.model.num_nodes}.npz"
        if run_primary.exists():
            windows_path = run_primary
        elif run_legacy.exists():
            windows_path = run_legacy
        else:
            try:
                windows_path = _latest_match(primary)
            except FileNotFoundError as exc:
                try:
                    windows_path = _latest_match(legacy)
                except FileNotFoundError:
                    raise FileNotFoundError(
                        f"{exc} -- Build templates first: `python -m mobse.cli build_templates --config <config>`"
                    ) from exc

    if not template_path.exists():
        raise FileNotFoundError(f"Template bank not found: {template_path}")
    if not windows_path.exists():
        raise FileNotFoundError(f"OS windows file not found: {windows_path}")
    return template_path, windows_path
