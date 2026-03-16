from __future__ import annotations

import os
from pathlib import Path

from mobse.config import ExperimentConfig
from mobse.io import resolve_template_inputs


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ok")


def test_resolve_template_inputs_prefers_current_run(tmp_path):
    artifacts = tmp_path / "artifacts"
    cfg = ExperimentConfig()
    cfg.artifacts.root_dir = str(artifacts)
    cfg.artifacts.run_id = "target_run"
    cfg.model.num_nodes = 100
    cfg.template.default_sparsity = 0.2
    cfg.template.output_name = "template_bank.npz"

    key = "atlas100_sp20_template_bank.npz"
    other_template = artifacts / "other_run" / "templates" / key
    other_windows = artifacts / "other_run" / "templates" / "os_windows_nodes100.npz"
    target_template = artifacts / "target_run" / "templates" / key
    target_windows = artifacts / "target_run" / "templates" / "os_windows_nodes100.npz"

    _touch(other_template)
    _touch(other_windows)
    _touch(target_template)
    _touch(target_windows)

    # Make non-target run look newer; resolver should still use target_run.
    newer = target_template.stat().st_mtime + 1000
    other_template.touch()
    other_windows.touch()
    os.utime(other_template, (newer, newer))
    os.utime(other_windows, (newer, newer))

    template_path, windows_path = resolve_template_inputs(cfg)
    assert template_path == target_template
    assert windows_path == target_windows
