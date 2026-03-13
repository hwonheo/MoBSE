from __future__ import annotations

import argparse
from pathlib import Path

from mobse.artifacts import ArtifactManager
from mobse.config import load_config, save_config
from mobse.data import prepare_data
from mobse.evaluate import run_evaluation
from mobse.progress import ProgressReporter
from mobse.report import run_report
from mobse.templates import build_template_bank
from mobse.train import run_training
from mobse.utils import dump_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MoBSE PoC CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build_templates", help="Build open-source brain-state template bank")
    p_build.add_argument("--config", required=True, help="YAML config path")
    p_build.add_argument("--no-progress", action="store_true", help="Disable progress output")

    p_prepare = sub.add_parser("prepare_data", help="Download/prepare ETTh1 and open-source proxy data")
    p_prepare.add_argument("--config", required=True, help="YAML config path")
    p_prepare.add_argument("--no-progress", action="store_true", help="Disable progress output")
    p_prepare.add_argument(
        "--mode",
        default="openneuro_hc",
        choices=["openneuro_hc", "openneuro", "public_proxy", "synthetic"],
        help=(
            "openneuro_hc: OpenNeuro 성인 HC 필터(진단/나이 컬럼 필요), "
            "openneuro: OpenNeuro 일반 fMRI import, "
            "public_proxy: development_fmri, "
            "synthetic: synthetic open-source-like states"
        ),
    )
    p_prepare.add_argument(
        "--subjects",
        type=int,
        default=30,
        help="Number of subjects for proxy/synthetic OS data",
    )
    p_prepare.add_argument(
        "--etth1-url",
        default="https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTh1.csv",
        help="ETTh1 CSV download URL",
    )
    p_prepare.add_argument(
        "--min-age",
        type=int,
        default=18,
        help="Minimum age filter for OpenNeuro modes",
    )
    p_prepare.add_argument(
        "--diagnosis",
        default="",
        help=(
            "Diagnosis/group filter for OpenNeuro modes. "
            "If omitted, openneuro_hc defaults to CONTROL and openneuro applies no diagnosis filter."
        ),
    )
    p_prepare.add_argument(
        "--openneuro-dataset",
        default="ds000030",
        help="OpenNeuro dataset id, e.g. ds000030",
    )
    p_prepare.add_argument(
        "--openneuro-snapshot",
        default="",
        help="OpenNeuro snapshot tag (empty = latest public snapshot)",
    )
    p_prepare.add_argument(
        "--openneuro-task",
        default="rest",
        help="BIDS task name to import from func/*_task-<task>_*_bold.nii.gz",
    )
    p_prepare.add_argument(
        "--openneuro-api-url",
        default="https://openneuro.org/crn/graphql",
        help="OpenNeuro GraphQL endpoint",
    )

    p_train = sub.add_parser("train", help="Train model (single or dual-task)")
    p_train.add_argument("--config", required=True, help="YAML config path")
    p_train.add_argument("--no-progress", action="store_true", help="Disable progress output")

    p_eval = sub.add_parser("evaluate", help="Evaluate checkpoint and profile efficiency")
    p_eval.add_argument("--config", required=True, help="YAML config path")
    p_eval.add_argument("--checkpoint", default=None, help="Checkpoint path")
    p_eval.add_argument("--no-progress", action="store_true", help="Disable progress output")

    p_report = sub.add_parser("report", help="Build report tables and figures from eval outputs")
    p_report.add_argument("--config", required=True, help="YAML config path")
    p_report.add_argument(
        "--eval-glob",
        default="artifacts/*/logs/eval_*.json",
        help="Glob pattern for evaluation JSON files",
    )
    p_report.add_argument("--no-progress", action="store_true", help="Disable progress output")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = load_config(args.config)

    manager = ArtifactManager(cfg)
    paths = manager.ensure_dirs()
    save_config(cfg, paths.logs / "resolved_config.yaml")
    progress = ProgressReporter(
        paths.logs / f"progress_{args.command}.json",
        enabled=not getattr(args, "no_progress", False),
    )
    progress.update("start", message=f"command={args.command}")

    try:
        if args.command == "build_templates":
            generated = build_template_bank(cfg, paths, progress=progress)
            dump_json({k: str(v) for k, v in generated.items()}, paths.logs / "template_manifest.json")
            progress.done(f"Built template banks: {len(generated)}")
            print(f"Built template banks: {len(generated)}")
            return

        if args.command == "prepare_data":
            result = prepare_data(
                cfg,
                mode=args.mode,
                subjects=args.subjects,
                etth1_url=args.etth1_url,
                min_age=args.min_age,
                diagnosis=args.diagnosis,
                openneuro_dataset=args.openneuro_dataset,
                openneuro_snapshot=args.openneuro_snapshot,
                openneuro_task=args.openneuro_task,
                openneuro_api_url=args.openneuro_api_url,
                progress=progress,
            )
            dump_json(result, paths.logs / "prepare_data.json")
            progress.done("Data prepared")
            print(f"Data prepared: {result}")
            return

        if args.command == "train":
            result = run_training(cfg, paths, progress=progress)
            progress.done(f"Training complete. Checkpoints: {len(result['checkpoints'])}")
            print(f"Training complete. Checkpoints: {len(result['checkpoints'])}")
            return

        if args.command == "evaluate":
            result = run_evaluation(cfg, paths, checkpoint_path=args.checkpoint, progress=progress)
            out = paths.logs / f"{cfg.eval.output_prefix}_{cfg.model.arch}.json"
            progress.done(f"Evaluation complete: {out}")
            print(f"Evaluation complete: {out}")
            print(result)
            return

        if args.command == "report":
            manifest = run_report(cfg, paths, eval_glob=args.eval_glob, progress=progress)
            progress.done("Report generated")
            print(f"Report generated: {manifest}")
            return
    except Exception as exc:
        progress.fail(str(exc))
        raise


if __name__ == "__main__":
    main()
