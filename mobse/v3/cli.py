"""exploratory v2 CLI — 저표본 곡선 한 fit 을 돌린다 (결정 30·31·32·33).

지금 있는 하위 명령은 ``fit`` **하나**다. 4 단계 (저표본 1 fit 실측) 에 필요한
것이 그것뿐이고, ``select``·``evaluate``·``report`` 는 endpoint 해상도가 정해진
뒤에 붙인다. 미리 만들어 두면 정해지지 않은 값이 코드에 박힌다.

v1 CLI 와 다른 곳
----------------
* ``--roi-structure`` 가 필수다. config 의 `cells.roi_structures` 안에 있어야
  한다 — 8 칸은 A–D 와 이 축의 곱이다 (결정 33).
* ``--n-train-level`` 이 필수다. config 의 `curve.levels` 안에 있어야 하고,
  `mobse.v3.subsample` 이 그 수만큼 학습 subject 를 줄인다 (결정 30).
* inner fit 은 **epoch 수를 받지 않는다.** 상한이 update 예산에서 나온다.
* outer fit 은 ``--selection`` 으로 inner 의 결과를 받고, 그 공통 E 를
  **update 단위로** outer epoch 으로 옮긴다 (설계안 §5.3.2 구현 선택).
  epoch 수를 직접 받지 않는 이유다 — 직접 받으면 그 규칙을 건너뛸 수 있다.

경로는 전부 명시한다. glob fallback 은 없다 (U20).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from mobse.v2.manifests import sha256_file, write_jsonl
from mobse.v2.templates import bank_seed as _bank_seed  # 동결된 v1 규칙
from mobse.v3 import fitting as FIT
from mobse.v3 import subsample as SUB
from mobse.v3.config import ConfigError, config_hash, load_config
from mobse.v3.subsample import SubsampleError
from mobse.v3.models import ROI_STRUCTURES
from mobse.v3.train import TrainError, carry_epochs_to_outer

__all__ = ["CLIError", "SUBCOMMANDS", "build_parser", "fit_id", "main", "run_fit"]

SUBCOMMANDS = ("fit",)

#: 하위 명령별 필수 경로. v1 과 같은 규약이다.
REQUIRED_PATHS: Dict[str, Sequence[str]] = {
    "fit": ("config", "splits", "subjects", "windows", "rest_manifest", "output_dir"),
}

#: fit 산출물. 하나라도 있으면 실행하지 않는다 — 같은 결과를 덮어쓰지 않는다.
FIT_OUTPUTS = ("fit_manifest.json", "checkpoint.pt", "window_predictions.jsonl",
               "fit_report.json")


class CLIError(RuntimeError):
    """CLI 사용 규칙 위반."""


def fit_id(*, role: str, cell: str, roi_structure: str, n_train_level: int,
           outer_fold: int, inner_fold: int, model_seed: int, config_id: int,
           split_hash: str, cfg_hash: str) -> str:
    """재현 가능한 v3 fit 식별자.

    v1 의 `manifests.fit_id` 를 쓸 수 없다. 그 payload 에는 ``roi_structure`` 와
    ``n_train_level`` 이 없어서, 구조가 다르거나 학습 subject 수가 다른 fit 이
    **같은 식별자를 갖는다.** v1 이 rev42 에서 `config_id` 를 빠뜨려 겪은 것과
    같은 종류의 충돌이다.
    """
    if cell not in FIT.CELLS:
        raise CLIError(f"알 수 없는 cell: {cell!r}")
    if roi_structure not in ROI_STRUCTURES:
        raise CLIError(f"알 수 없는 roi_structure: {roi_structure!r}")
    payload = {"role": role, "cell": cell, "roi_structure": roi_structure,
               "n_train_level": int(n_train_level), "outer_fold": int(outer_fold),
               "inner_fold": int(inner_fold), "model_seed": int(model_seed),
               "config_id": int(config_id), "split_hash": split_hash,
               "config_hash": cfg_hash}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:12]
    return (f"{role}-{cell}{roi_structure[0].upper()}-n{int(n_train_level)}"
            f"-o{int(outer_fold)}i{int(inner_fold)}s{int(model_seed)}-{digest}")


def build_parser() -> argparse.ArgumentParser:
    """모든 경로가 required 인 parser."""
    parser = argparse.ArgumentParser(prog="mobse.v3.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fit = sub.add_parser("fit", help="저표본 곡선의 fit 하나를 학습한다")
    for name in REQUIRED_PATHS["fit"]:
        fit.add_argument(f"--{name.replace('_', '-')}", required=True)
    fit.add_argument("--task-manifests", nargs="+", required=True)
    fit.add_argument("--cell", required=True, choices=sorted(FIT.CELLS))
    fit.add_argument("--roi-structure", required=True, choices=list(ROI_STRUCTURES))
    fit.add_argument("--n-train-level", required=True, type=int)
    fit.add_argument("--outer-fold", required=True, type=int)
    fit.add_argument("--inner-fold", required=True, type=int)
    fit.add_argument("--config-id", required=True, type=int)
    fit.add_argument("--model-seed", required=True, type=int)
    fit.add_argument("--selection", default=None,
                     help="outer fit 전용. inner 선택 결과 JSON "
                          "(common_epochs · inner_train_windows)")
    fit.add_argument("--device", default="cpu")
    fit.add_argument("--skip-hash-verify", action="store_true")
    return parser


def resolve_paths(command: str, namespace: argparse.Namespace) -> Dict[str, str]:
    """필수 경로가 모두 주어졌는지 확인한다."""
    if command not in REQUIRED_PATHS:
        raise CLIError(f"알 수 없는 하위 명령: {command!r} (허용: {list(SUBCOMMANDS)})")
    out: Dict[str, str] = {}
    for name in REQUIRED_PATHS[command]:
        value = getattr(namespace, name, None)
        if not value:
            raise CLIError(f"{command}: --{name.replace('_', '-')} 가 필요하다")
        out[name] = str(value)
    return out


def check_inputs_exist(paths: Mapping[str, str], *,
                       skip: Sequence[str] = ("output_dir",)) -> None:
    """입력 경로가 실제로 있는지 본다. 없으면 대체 탐색하지 않고 실패한다 (U20)."""
    missing = [f"{k}={v}" for k, v in paths.items()
               if k not in skip and not Path(v).exists()]
    if missing:
        raise CLIError(f"입력 경로가 없다: {missing}. 대체 탐색하지 않는다 (U20)")


def _read_selection(path: str) -> Dict[str, int]:
    """outer fit 이 쓸 inner 선택 결과를 읽는다.

    Raises:
        CLIError: 파일이 없거나 필요한 두 값이 없을 때.
    """
    p = Path(path)
    if not p.is_file():
        raise CLIError(f"--selection 파일이 없다: {p}")
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CLIError(f"--selection 파싱 실패: {p}: {exc}") from exc
    out: Dict[str, int] = {}
    for key in ("common_epochs", "inner_train_windows"):
        if key not in rec:
            raise CLIError(f"--selection 에 {key!r} 가 없다: {p}")
        value = rec[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise CLIError(f"--selection 의 {key} 는 1 이상의 정수여야 한다: {value!r}")
        out[key] = value
    return out


def run_fit(paths: Dict[str, str], args: argparse.Namespace) -> Dict[str, Any]:
    """저표본 곡선의 fit 하나를 학습하고 네 산출물을 쓴다.

    `fit_manifest.json` · `checkpoint.pt` · `window_predictions.jsonl` ·
    `fit_report.json`. run 단위 집계는 하지 않는다 — v1 과 같은 이유로
    (세 seed 의 창 확률을 먼저 평균해야 한다) `evaluate` 의 몫이다.

    Raises:
        CLIError: 입력이 어긋나거나 산출물을 덮어쓰게 될 때.
    """
    from mobse.v3.models import save_checkpoint   # roi_structure 를 함께 적는다

    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc

    locked_seeds = tuple(int(s) for s in cfg["train.model_seeds"])
    if int(args.model_seed) not in locked_seeds:
        raise CLIError(f"--model-seed {args.model_seed} 는 잠긴 train.model_seeds "
                       f"{locked_seeds} 밖이다")
    allowed_structures = tuple(cfg["cells.roi_structures"])
    if args.roi_structure not in allowed_structures:
        raise CLIError(f"--roi-structure {args.roi_structure!r} 는 이 config 가 고른 "
                       f"{list(allowed_structures)} 밖이다 (결정 33: 8 칸)")
    levels = tuple(int(v) for v in cfg["curve.levels"])
    if int(args.n_train_level) not in levels:
        raise CLIError(f"--n-train-level {args.n_train_level} 는 잠긴 curve.levels "
                       f"{list(levels)} 밖이다 (결정 30)")
    if cfg["runtime.deterministic"] is not True:
        raise CLIError("runtime.deterministic 은 True 여야 한다 (E22)")

    task_manifests = [Path(p) for p in args.task_manifests]
    missing = [str(p) for p in task_manifests if not p.exists()]
    if missing:
        raise CLIError(f"task manifest 가 없다: {missing}. 대체 탐색하지 않는다 (U20)")

    out_dir = Path(paths["output_dir"])
    for name in FIT_OUTPUTS:
        if (out_dir / name).exists():
            raise CLIError(f"이미 존재한다: {out_dir / name}. 같은 결과를 덮어쓰지 않는다")

    folds = json.loads(Path(paths["splits"]).read_text(encoding="utf-8"))
    # **먼저 자르고, 그 안에서 나눈다** (2026-10-01 구현 선택). v1 분할에서 outer
    # 경계만 가져오고, 그 학습 pool 을 수준만큼 줄인 뒤 inner 를 다시 긋는다.
    # 그래야 수준이 role 과 무관하게 같은 뜻이고, 가장 큰 수준에서 grid 를 한 번
    # 고르는 결정 33 이 성립한다.
    fold = SUB.curve_fold_subjects(
        folds, int(args.outer_fold), int(args.inner_fold), int(args.n_train_level),
        n_inner_folds=int(cfg["splits.n_inner_folds"]),
        subsample_seed_base=int(cfg["curve.subsample_seed_base"]),
        inner_split_seed_base=int(cfg["curve.inner_split_seed_base"]))
    is_inner = fold.role == FIT.ROLE_INNER
    kept = list(fold.train)

    group_of: Dict[str, Any] = {}
    for line in Path(paths["subjects"]).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            group_of[rec["canonical_subject"]] = rec["group_id"]
    unknown = sorted((set(kept) | set(fold.evaluate)) - set(group_of))
    if unknown:
        raise CLIError(f"subjects.jsonl 에 없는 subject: {unknown[:5]}")

    verify = not bool(getattr(args, "skip_hash_verify", False))
    task_refs: List[Any] = []
    for mp in task_manifests:
        task_refs += FIT.refs_from_extract_manifest(mp, labelled=True)
    FIT.crosscheck_with_windows_manifest(task_refs, Path(paths["windows"]))
    rest_refs = FIT.refs_from_extract_manifest(Path(paths["rest_manifest"]),
                                               labelled=False)

    bank_seed = _bank_seed(int(args.outer_fold), int(args.inner_fold))
    transform = FIT.fit_fold_transform(
        rest_refs, kept, bank_seed=bank_seed,
        null_seed=int(cfg["nulls.primary_seed"]),
        n_components=int(cfg["bank.pca_components"]),
        k=int(cfg["bank.k"]), density=float(cfg["bank.edge_density"]),
        verify=verify)

    train_set = FIT.encode_windows(FIT.select_refs(task_refs, kept), transform,
                                   verify=verify)
    eval_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.evaluate), transform,
                                  verify=verify)

    budget = int(cfg["train.update_budget"])
    epochs_exact = None
    carry: Dict[str, int] = {}
    if is_inner:
        if args.selection:
            raise CLIError("inner fit 은 --selection 을 받지 않는다 — 상한은 "
                           "update 예산에서 나온다")
    else:
        if not args.selection:
            raise CLIError("outer fit 은 --selection 이 필요하다 (공통 E 를 update "
                           "단위로 옮긴다 — 설계안 §5.3.2)")
        carry = _read_selection(args.selection)
        epochs_exact = carry_epochs_to_outer(
            carry["common_epochs"], carry["inner_train_windows"], len(train_set),
            batch_size=int(cfg["train.batch_size"]), update_budget=budget)

    result, model = FIT.train_fold(
        train_set, eval_set, transform, cell=args.cell,
        roi_structure=args.roi_structure, config_id=int(args.config_id),
        model_seed=int(args.model_seed), fold=fold,
        device=str(getattr(args, "device", "cpu")),
        batch_size=int(cfg["train.batch_size"]),
        patience=int(cfg["train.patience"]),
        min_delta=float(cfg["train.min_delta"]),
        grad_clip=float(cfg["train.grad_clip"]),
        epochs_exact=epochs_exact, update_budget=budget)

    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / "checkpoint.pt"
    save_checkpoint(model, ckpt_path)
    ckpt_sha = sha256_file(ckpt_path)

    cfg_hash = config_hash(cfg)
    fid = fit_id(role=fold.role, cell=args.cell, roi_structure=args.roi_structure,
                 n_train_level=int(args.n_train_level),
                 outer_fold=int(args.outer_fold), inner_fold=int(args.inner_fold),
                 model_seed=int(args.model_seed), config_id=int(args.config_id),
                 split_hash=folds["split_hash"], cfg_hash=cfg_hash)

    rows = []
    for ref in eval_set.refs:
        rows.append({
            "schema_version": "v3-window-predictions-0.1",
            "canonical_subject": ref.canonical_subject,
            "group_id": group_of[ref.canonical_subject],
            "run_key": ref.run_key, "window_key": ref.window_key,
            "truth": int(ref.label),
            "p_class1": float(result.eval_window_probs[ref.window_key]),
            "cell": args.cell, "roi_structure": args.roi_structure,
            "n_train_level": int(args.n_train_level),
            "model_seed": int(args.model_seed), "scope": fold.eval_role,
            "checkpoint_sha256": ckpt_sha, "fit_id": fid,
        })
    written = write_jsonl(out_dir / "window_predictions.jsonl",
                          "window_predictions", rows)

    manifest = {
        "schema_version": "v3-fit-manifest-0.1", "fit_id": fid,
        "design_version": str(cfg["meta.design_version"]),
        "role": fold.role, "cell": args.cell, "roi_structure": args.roi_structure,
        "curve": {"n_train_level": int(args.n_train_level),
                  "n_train_subjects_in_level_pool": int(args.n_train_level),
                  "n_train_subjects_used": len(kept),
                  "inner_split_seed_base": int(cfg["curve.inner_split_seed_base"]),
                  "subsample_seed": SUB.subsample_seed(
                      int(args.outer_fold),
                      seed_base=int(cfg["curve.subsample_seed_base"]))},
        "folds": {"outer_fold": int(args.outer_fold),
                  "inner_fold": int(args.inner_fold),
                  "n_eval_subjects": len(fold.evaluate),
                  "eval_role": fold.eval_role},
        "model_seed": int(args.model_seed), "bank_seed": bank_seed,
        "null_seed": int(cfg["nulls.primary_seed"]),
        "fit_subjects": list(kept),
        "bank_id": transform.brain.bank_id,
        "config_hash": cfg_hash,
        "source_hash": sha256_file(Path(paths["windows"])),
        "split_hash": folds["split_hash"],
        "budget": {"update_budget": budget,
                   "epoch_ceiling": result.epoch_ceiling,
                   "updates_per_epoch": result.updates_per_epoch,
                   "carry_unit": str(cfg["train.carry_unit"]),
                   "carried_from_inner": carry or None,
                   "epochs_exact": epochs_exact},
    }
    (out_dir / "fit_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    from mobse.v2.train import build_grid
    gc = {g.config_id: g for g in build_grid()}[int(args.config_id)]
    report = {
        "fit_id": fid, "config_id": int(args.config_id), "config": gc.as_dict(),
        "roi_structure": args.roi_structure,
        "n_train_level": int(args.n_train_level),
        "epochs_run": result.epochs_run, "best_epoch": result.best_epoch,
        "eval_epoch": result.eval_epoch, "epoch_ceiling": result.epoch_ceiling,
        "update_budget": result.update_budget,
        "updates_per_epoch": result.updates_per_epoch,
        "updates_run": result.updates_run,
        "val_losses": result.val_losses, "eval_loss": result.eval_loss,
        "eval_balanced_accuracy": result.eval_balanced_accuracy,
        "eval_role": fold.eval_role, "transform": result.transform,
        "timing": result.timing, "memory": result.memory,
        "encoder_init_hash": result.encoder_init_hash, "rng_note": result.rng_note,
        "determinism": result.determinism,
        "n_train_windows": len(train_set), "n_eval_windows": len(eval_set),
        "checkpoint_sha256": ckpt_sha,
    }
    (out_dir / "fit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "verdict": "pass", "fit_id": fid, "role": fold.role, "cell": args.cell,
        "roi_structure": args.roi_structure, "n_train_level": int(args.n_train_level),
        "n_train_subjects_used": len(kept),
        "epoch_ceiling": result.epoch_ceiling, "epochs_run": result.epochs_run,
        "best_epoch": result.best_epoch, "updates_run": result.updates_run,
        "eval_role": fold.eval_role, "eval_loss": result.eval_loss,
        "eval_balanced_accuracy": result.eval_balanced_accuracy,
        "n_train_windows": len(train_set), "n_eval_windows": len(eval_set),
        "window_predictions": written, "timing": result.timing,
        "memory": result.memory, "output_dir": str(out_dir),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 진입점. 결과 요약을 JSON 한 줄로 stdout 에 쓴다."""
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        paths = resolve_paths(args.command, args)
        check_inputs_exist(paths)
        summary = run_fit(paths, args)
    except (CLIError, FIT.FitError, SubsampleError, TrainError,
            ConfigError) as exc:
        # 규칙 위반은 traceback 이 아니라 판정으로 내보낸다 — 구동기가 읽는다.
        print(json.dumps({"verdict": "fail", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - 진입점
    sys.exit(main())
