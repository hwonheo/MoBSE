from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _run(cmd: List[str], cwd: Path) -> None:
    print("[run]", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run train/eval/report for a multiseed follow-up config")
    ap.add_argument("--config", required=True, help="YAML config path")
    ap.add_argument("--no-progress", action="store_true", help="Disable CLI progress output")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = Path(args.config).resolve()
    cfg = _load_yaml(cfg_path)

    train_cfg = cfg.get("train") or {}
    artifacts_cfg = cfg.get("artifacts") or {}
    model_cfg = cfg.get("model") or {}

    seeds = [int(seed) for seed in train_cfg.get("seeds", [])]
    if not seeds:
        raise ValueError("Config must define train.seeds with at least one seed.")

    run_id = str(artifacts_cfg.get("run_id", "")).strip()
    root_dir = str(artifacts_cfg.get("root_dir", "artifacts")).strip()
    arch = str(model_cfg.get("arch", "mobse")).strip()
    if not run_id:
        raise ValueError("Config must define artifacts.run_id.")

    run_root = repo_root / root_dir / run_id
    logs_dir = run_root / "logs"
    no_progress = ["--no-progress"] if args.no_progress else []

    _run([sys.executable, "-m", "mobse.cli", "train", "--config", str(cfg_path), *no_progress], cwd=repo_root)

    for seed in seeds:
        ckpt = run_root / "checkpoints" / f"model_seed{seed}_best.pt"
        if not ckpt.exists():
            raise FileNotFoundError(f"Missing checkpoint for seed {seed}: {ckpt}")
        _run(
            [
                sys.executable,
                "-m",
                "mobse.cli",
                "evaluate",
                "--config",
                str(cfg_path),
                "--checkpoint",
                str(ckpt),
                *no_progress,
            ],
            cwd=repo_root,
        )
        src = logs_dir / f"eval_{arch}.json"
        dst = logs_dir / f"eval_seed{seed}_{arch}.json"
        shutil.copyfile(src, dst)

    _run(
        [
            sys.executable,
            "-m",
            "mobse.cli",
            "report",
            "--config",
            str(cfg_path),
            "--eval-glob",
            f"{root_dir}/{run_id}/logs/eval_seed*_{arch}.json",
            *no_progress,
        ],
        cwd=repo_root,
    )


if __name__ == "__main__":
    main()
