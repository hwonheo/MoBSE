from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List


def _run(cmd: List[str], cwd: Path) -> None:
    print("[run]", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env.setdefault("NILEARN_DATA", str(cwd / "data" / "_nilearn_cache"))
    Path(env["NILEARN_DATA"]).mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run prepare_data -> build_templates -> multiseed follow-up")
    ap.add_argument("--config", required=True, help="YAML config path")
    ap.add_argument("--mode", default="openneuro", help="prepare_data mode")
    ap.add_argument("--subjects", type=int, default=300, help="prepare_data subjects")
    ap.add_argument("--min-age", type=int, default=18, help="OpenNeuro minimum age")
    ap.add_argument("--diagnosis", default="", help="Optional diagnosis/group filter")
    ap.add_argument("--openneuro-datasets", default="", help="Comma-separated OpenNeuro dataset ids")
    ap.add_argument("--openneuro-task", default="rest,restingstate", help="Comma-separated task names")
    ap.add_argument("--openneuro-snapshot", default="", help="Optional OpenNeuro snapshot tag")
    ap.add_argument("--no-progress", action="store_true", help="Disable CLI progress output")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = Path(args.config).resolve()
    no_progress = ["--no-progress"] if args.no_progress else []

    prepare_cmd = [
        sys.executable,
        "-m",
        "mobse.cli",
        "prepare_data",
        "--config",
        str(cfg_path),
        "--mode",
        args.mode,
        "--subjects",
        str(args.subjects),
        "--min-age",
        str(args.min_age),
        "--openneuro-task",
        args.openneuro_task,
        *no_progress,
    ]
    if args.diagnosis:
        prepare_cmd.extend(["--diagnosis", args.diagnosis])
    if args.openneuro_datasets:
        prepare_cmd.extend(["--openneuro-datasets", args.openneuro_datasets])
    if args.openneuro_snapshot:
        prepare_cmd.extend(["--openneuro-snapshot", args.openneuro_snapshot])

    _run(prepare_cmd, cwd=repo_root)
    _run([sys.executable, "-m", "mobse.cli", "build_templates", "--config", str(cfg_path), *no_progress], cwd=repo_root)
    _run([sys.executable, "scripts/run_multiseed_followup.py", "--config", str(cfg_path), *no_progress], cwd=repo_root)


if __name__ == "__main__":
    main()
