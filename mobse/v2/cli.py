"""명시적 CLI — 지침서 WI-06.

모든 경로를 **필수 인자**로 받는다. 기존 코드가 mtime 최신 파일이나 glob 최후
항목으로 checkpoint·template 을 대신 찾던 동작(차단 항목 U20,
`mobse/io.py:10-14`, `mobse/evaluate.py:94`)을 이 계층에서 원천 차단한다.

하위 명령은 역할이 겹치지 않는다:

* ``validate``  — manifest 스키마와 split 경계만 검사한다. 학습·평가하지 않는다.
* ``prepare``   — 시간축·window·QC 를 산출한다.
* ``split``     — pilot 과 outer/inner fold 를 만든다.
* ``fit``       — 지정한 fold·cell·seed 하나를 학습한다.
* ``evaluate``  — 저장된 outer test 예측을 run·subject·cell 로 집계한다. **분류만.**
  부트스트랩·gate 판정은 하지 않는다 (``report`` 의 몫).
* ``report``    — 통계와 gate evidence 를 낸다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from mobse.v2.config import ConfigError, config_hash, load_config
from mobse.v2.manifests import ManifestError, assert_no_glob_fallback, validate_record

SUBCOMMANDS = ("validate", "prepare", "split", "fit", "evaluate", "report")

#: 하위 명령별 필수 경로 인자. 하나라도 비면 실행하지 않는다.
REQUIRED_PATHS: Dict[str, Sequence[str]] = {
    "validate": ("config", "source_runs"),
    "prepare": ("config", "source_runs", "output_dir"),
    "split": ("config", "subjects", "output_dir"),
    "fit": ("config", "splits", "subjects", "windows", "rest_manifest", "output_dir"),
    "evaluate": ("config", "splits", "predictions", "fit_manifest", "output_dir"),
    "report": ("config", "predictions", "output_dir"),
}


#: 여러 경로를 받는 (하위 명령, 인자). release 하나는 cell × outer fold × seed
#: 개의 fit 으로 이루어지므로 evaluate 는 그 산출물을 전부 명시적으로 받는다.
MULTI_PATHS = frozenset({("evaluate", "predictions"), ("evaluate", "fit_manifest")})


class CLIError(RuntimeError):
    """CLI 사용 규칙 위반."""


def build_parser() -> argparse.ArgumentParser:
    """모든 경로가 required 인 parser 를 만든다."""
    ap = argparse.ArgumentParser(
        prog="mobse-v2",
        description="MoBSE 재설계 v2 — 경로를 모두 명시해야 한다 (glob fallback 없음)")
    subs = ap.add_subparsers(dest="command", required=True)

    common = {
        "config": "runtime config YAML 경로",
        "source_runs": "source_runs.jsonl 경로",
        "subjects": "subjects.jsonl 경로",
        "splits": "folds.json 경로",
        "windows": "windows.jsonl 경로",
        "predictions": "window_predictions.jsonl 경로",
        "fit_manifest": "fit_manifest.json 경로",
        "rest_manifest": "WI-02 restingstate 추출 manifest 경로 (bank 적합용)",
        "output_dir": "산출 디렉터리",
    }
    for name in SUBCOMMANDS:
        p = subs.add_parser(name, help=f"{name} 단계")
        for arg in REQUIRED_PATHS[name]:
            many = (name, arg) in MULTI_PATHS
            p.add_argument(f"--{arg.replace('_', '-')}", type=Path, required=True,
                           nargs="+" if many else None,
                           help=common[arg] + (" (fit 마다 하나, 여러 개)" if many else ""))
        if name == "fit":
            p.add_argument("--cell", required=True, choices=list("ABCD"))
            p.add_argument("--outer-fold", type=int, required=True)
            p.add_argument("--inner-fold", type=int, required=True,
                           help="inner fold 번호. 9 는 outer 최종 적합이다")
            p.add_argument("--model-seed", type=int, required=True)
            p.add_argument("--config-id", type=int, required=True,
                           help="공통 grid 의 config 번호 0–7 (계획서 §7)")
            p.add_argument("--epochs", type=int, required=True,
                           help="inner 은 최대 epoch, outer 은 공통 E 로 정확히 이만큼")
            p.add_argument("--task-manifests", type=Path, nargs="+", required=True,
                           help="WI-02 target task 추출 manifest. 창 경로의 유일한 출처다")
            p.add_argument("--device", default="cpu")
            p.add_argument("--skip-hash-verify", action="store_true",
                           help="창 sha256 대조를 건너뛴다. 기본은 대조한다")
        if name == "evaluate":
            p.add_argument("--tasks", nargs="+", required=True,
                           help="평가할 분류 task. 학습하지 않은 task 는 거부된다")
        p.add_argument("--dry-run", action="store_true",
                       help="경로와 스키마만 검사하고 실행하지 않는다")
    return ap


def resolve_paths(command: str, namespace: argparse.Namespace) -> Dict[str, Any]:
    """필수 경로가 모두 주어졌는지 확인한다.

    Raises:
        CLIError: 알 수 없는 명령.
        ManifestError: 비어 있는 경로가 있으면 (U20).
    """
    if command not in REQUIRED_PATHS:
        raise CLIError(f"알 수 없는 하위 명령: {command!r}. 허용: {list(SUBCOMMANDS)}")
    def _norm(value: Any) -> Any:
        if not value:
            return None
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        return str(value)

    resolved = {k: _norm(getattr(namespace, k, None)) for k in REQUIRED_PATHS[command]}
    assert_no_glob_fallback(resolved)
    return {k: v for k, v in resolved.items() if v is not None}


def check_inputs_exist(paths: Dict[str, Any], *, skip: Sequence[str] = ("output_dir",)
                       ) -> None:
    """입력 경로가 실제로 존재하는지 확인한다. 없으면 대체 탐색하지 않고 실패한다."""
    missing = [k for k, v in paths.items() if k not in skip and
               not all(Path(x).exists() for x in (v if isinstance(v, list) else [v]))]
    if missing:
        raise CLIError(
            f"입력 경로가 없다: {missing}. 다른 파일로 대체 탐색하지 않는다 (U20)")



#: WI-01 감사 manifest 의 schema_version. release schema 와 **다른 artifact** 다.
AUDIT_SCHEMA_VERSION = "wi01-source-runs-0.1"

#: 감사 manifest 에서 null 이 허용되는 필드. 단, 그 줄의 `unresolved` 가
#: 이유를 담고 있어야 한다 (계획서의 null_policy). 조용한 null 은 없다.
AUDIT_NULLABLE = (
    "group_id", "source_bold_path", "source_bold_sha256",
    "sidecar_json_path", "sidecar_json_sha256", "confounds_path",
    "confounds_sha256", "events_path", "events_sha256", "native_tr",
    "derivative_start_sec", "discarded_volumes", "event_origin",
    "atlas_id", "atlas_hash", "roi_order_hash",
)


def _sha256(path: Path) -> str:
    """파일 해시. manifests.sha256_file 과 같은 정의를 쓴다."""
    from mobse.v2.manifests import sha256_file

    return sha256_file(path)


def _validate_audit_record(record: Mapping[str, Any], lineno: int) -> List[Dict[str, Any]]:
    """WI-01 감사 레코드 한 줄을 검사한다.

    감사 manifest 는 원자료가 없는 상태의 기록이므로 null 이 정상이다. 대신
    **모든 null 에 이유가 붙어 있어야 한다**. 이유 없는 null 이 바로 조용한
    default 가 들어설 자리다 (T02).

    Returns:
        문제 목록. 빈 리스트면 통과.
    """
    problems: List[Dict[str, Any]] = []
    run_key = record.get("run_key")
    reasons = " ".join(record.get("unresolved") or [])
    for field in AUDIT_NULLABLE:
        if field not in record:
            problems.append({"line": lineno, "run_key": run_key,
                             "error": f"감사 스키마 필드 누락: {field}"})
            continue
        if record[field] is None:
            stem = field.split("_")[0]
            if stem not in reasons and field not in reasons:
                problems.append({
                    "line": lineno, "run_key": run_key,
                    "error": f"{field} 가 null 인데 unresolved 에 이유가 없다 "
                             "(이유 없는 null = 조용한 default 자리)"})
    if not record.get("usable_for_primary_analysis") and not record.get("usable_reason"):
        problems.append({"line": lineno, "run_key": run_key,
                         "error": "usable_for_primary_analysis=false 인데 사유가 없다"})
    return problems


def run_validate(paths: Dict[str, str]) -> Dict[str, Any]:
    """config 와 source_runs manifest 를 검사한다. 학습·평가하지 않는다.

    원자료(BOLD) 없이 완결되는 유일한 하위 명령이다. manifest 는 두 종류를
    구분해 처리한다 — WI-01 **감사** manifest 와 release **산출** manifest 는
    이름이 같아도 스키마가 다르다. 감사본을 release 스키마로 검사하면 "아직
    내려받지 않은 파일"이 전부 스키마 위반으로 보고돼 쓸모가 없다.

    Args:
        paths: `resolve_paths` 가 돌려준 {인자명: 경로} 매핑.

    Returns:
        검사 결과 요약. 레코드 단위 실패는 `record_errors` 에 모아 담는다 —
        첫 실패에서 멈추면 한 번에 하나씩만 고치게 된다.

    Raises:
        CLIError: config 가 스키마를 위반하거나 manifest 를 읽을 수 없을 때.
    """
    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc

    source_path = Path(paths["source_runs"])
    try:
        lines = [ln for ln in source_path.read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
    except OSError as exc:
        raise CLIError(f"source_runs 를 읽을 수 없다: {source_path}: {exc}") from exc
    if not lines:
        raise CLIError(f"source_runs 가 비어 있다: {source_path}")

    record_errors: List[Dict[str, Any]] = []
    header: Dict[str, Any] = {}
    datasets: Dict[str, int] = {}
    tasks: Dict[str, int] = {}
    tr_by_task: Dict[str, set] = {}
    run_keys: Dict[str, int] = {}
    usable = 0
    n_records = 0

    for lineno, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            record_errors.append({"line": lineno, "error": f"JSON 파싱 실패: {exc}"})
            continue
        if record.get("record_type") == "header" or "run_key" not in record:
            if lineno == 1:
                header = record
                continue
            record_errors.append({"line": lineno, "error": "run_key 없는 비헤더 줄"})
            continue

        n_records += 1
        mode = header.get("schema_version") or record.get("schema_version")
        if mode == AUDIT_SCHEMA_VERSION:
            record_errors.extend(_validate_audit_record(record, lineno))
        else:
            try:
                validate_record("source_runs", record)
            except ManifestError as exc:
                record_errors.append({"line": lineno, "run_key": record.get("run_key"),
                                      "error": str(exc)})
                continue

        datasets[record.get("dataset", "?")] = datasets.get(record.get("dataset", "?"), 0) + 1
        tasks[record.get("task", "?")] = tasks.get(record.get("task", "?"), 0) + 1
        run_keys[record["run_key"]] = run_keys.get(record["run_key"], 0) + 1
        if record.get("usable_for_primary_analysis"):
            usable += 1
        tr = record.get("native_tr")
        if tr is not None:
            tr_by_task.setdefault(
                f"{record.get('dataset','?')}/{record.get('task','?')}", set()
            ).add(float(tr))

    duplicates = sorted(k for k, n in run_keys.items() if n > 1)
    if duplicates:
        record_errors.append({"error": f"run_key 중복 {len(duplicates)}건",
                              "examples": duplicates[:5]})

    # TR 충돌은 조용히 평균 내지 않는다 (T02).
    conflicts = {k: sorted(v) for k, v in tr_by_task.items() if len(v) > 1}
    if conflicts:
        record_errors.append({"error": "task 내 native TR 충돌", "detail": conflicts})

    schema_version = header.get("schema_version", "unknown")
    return {
        "config_path": paths["config"],
        "config_hash": config_hash(cfg),
        "config_fields": len(cfg),
        "source_runs_path": str(source_path),
        "source_runs_sha256": _sha256(source_path),
        "manifest_schema_version": schema_version,
        "manifest_stage": ("WI-01 감사본 (원자료 미확보 상태의 기록)"
                           if schema_version == AUDIT_SCHEMA_VERSION
                           else "release 산출본"),
        "records": n_records,
        "datasets": dict(sorted(datasets.items())),
        "tasks": dict(sorted(tasks.items())),
        "native_tr_by_dataset_task": {k: sorted(v) for k, v in sorted(tr_by_task.items())},
        "unique_run_keys": len(run_keys),
        "usable_for_primary_analysis": usable,
        "required_coverage_sec": cfg["timing.analysis_end_s"],
        "record_errors": record_errors,
        "verdict": "pass" if not record_errors else "fail",
    }


def run_split(paths: Dict[str, str]) -> Dict[str, Any]:
    """subjects manifest → grouped nested CV 분할.

    분할 알고리즘·seed 는 `splits.py` 가 단일 출처다. 이 함수는 입력을 읽고,
    **적격 subject 만** 넘기고, 결과를 검증해 파일로 쓴다.

    적격 판정은 여기서 다시 하지 않는다 — `cohort.py` 가 계획서 §3.3 기준으로
    이미 매긴 `eligible` 을 그대로 쓴다. 두 곳에서 판정하면 어긋난다.

    Args:
        paths: `resolve_paths` 가 돌려준 매핑. config/subjects/output_dir 필수.

    Returns:
        요약 dict. 상세 분할은 `folds.json` 에 쓴다.

    Raises:
        CLIError: config 위반, subjects 읽기 실패, 적격 subject 0명,
            분할 결과가 disjoint 하지 않을 때.
    """
    from mobse.v2.splits import build_folds, make_groups, verify_disjoint

    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc

    subjects_path = Path(paths["subjects"])
    if not subjects_path.is_file():
        raise CLIError(f"subjects manifest 가 없다: {subjects_path} "
                       "(자동 탐색하지 않는다 — U20)")
    records: List[Dict[str, Any]] = []
    for lineno, line in enumerate(subjects_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CLIError(f"{subjects_path}:{lineno} JSON 파싱 실패: {exc}") from exc
        try:
            validate_record("subjects", record)
        except ManifestError as exc:
            raise CLIError(f"{subjects_path}:{lineno} 스키마 위반: {exc}") from exc
        records.append(record)

    eligible = [r for r in records if r["eligible"]]
    if not eligible:
        raise CLIError(
            f"적격 subject 가 0명이다 ({len(records)}명 중). 분할하지 않는다 — "
            "임의 증원 대신 제한을 보고한다 (지침서 WI-03)")

    # group_id 는 cohort 가 정한 것을 그대로 쓴다. 관계 metadata 가 없으면
    # subject 와 같다 (개정 P4 / U10).
    subject_to_group = {r["canonical_subject"]: r["group_id"] for r in eligible}
    groups = make_groups(subject_to_group=subject_to_group)
    folds = build_folds(
        groups,
        n_outer=int(cfg["splits.n_outer_folds"]),
        n_inner=int(cfg["splits.n_inner_folds"]),
        pilot_seed=int(cfg["splits.pilot_seed"]),
        outer_seed=int(cfg["splits.outer_seed"]),
        inner_seed_base=int(cfg["splits.inner_seed_base"]),
    )

    # pilot 은 main·final fit 에서도 제외된다 (계획서 §4-2). 실제로 겹치지
    # 않는지 확인한다 — 문서로만 두지 않는다.
    verify_disjoint({"pilot": folds["pilot"]["subjects"],
                     "main_pool": folds["main_pool"]["subjects"]})
    for outer in folds["outer_folds"]:
        verify_disjoint({f"outer{outer['outer_fold']}_test": outer["test_subjects"],
                         f"outer{outer['outer_fold']}_train": outer["train_subjects"]})
        for inner in outer["inner"]:
            verify_disjoint({
                f"o{outer['outer_fold']}i{inner['inner_fold']}_val": inner["val_subjects"],
                f"o{outer['outer_fold']}i{inner['inner_fold']}_train": inner["train_subjects"],
                f"outer{outer['outer_fold']}_test": outer["test_subjects"]})

    out_dir = Path(paths["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    folds_path = out_dir / "folds.json"
    if folds_path.exists():
        raise CLIError(f"이미 존재한다: {folds_path}. 같은 release 결과를 "
                       "덮어쓰지 않는다 (지침서 §2)")
    payload = dict(folds)
    payload["config_hash"] = config_hash(cfg)
    payload["subjects_manifest"] = str(subjects_path)
    payload["subjects_manifest_sha256"] = _sha256(subjects_path)
    folds_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    return {
        "config_hash": payload["config_hash"],
        "subjects_total": len(records),
        "subjects_eligible": len(eligible),
        "n_groups": folds["n_groups_total"],
        "pilot_n": folds["pilot"]["n"],
        "pilot_target": folds["pilot"]["target"],
        "main_pool_n": folds["main_pool"]["n_subjects"],
        "outer_test_sizes": [len(o["test_subjects"]) for o in folds["outer_folds"]],
        "split_hash": folds["split_hash"],
        "folds_path": str(folds_path),
        "folds_sha256": _sha256(folds_path),
        "verdict": "pass",
    }


def _env_hash() -> str:
    """실행 환경의 해시. 버전이 바뀌면 fit_manifest 가 달라진다."""
    import platform

    import numpy as np

    payload = {"python": platform.python_version(), "numpy": np.__version__}
    try:
        import torch

        payload["torch"] = torch.__version__
    except Exception:                                          # pragma: no cover
        payload["torch"] = "absent"
    try:
        import sklearn

        payload["sklearn"] = sklearn.__version__
    except Exception:                                          # pragma: no cover
        payload["sklearn"] = "absent"
    from mobse.v2.manifests import sha256_obj

    return sha256_obj(payload)


def run_fit(paths: Dict[str, str], args: argparse.Namespace) -> Dict[str, Any]:
    """fold·cell·config·seed 하나를 학습한다 (계획서 §4–§7, 지침서 WI-04~WI-06).

    한 번의 호출이 **하나의 fit** 이다. 계획서 §7 의 비용표가 그 단위로 세어져
    있고, 이 함수는 그 한 칸을 채운다.

    출력은 넷이다 — `fit_manifest.json`, `checkpoint.pt`,
    `window_predictions.jsonl`, `fit_report.json`.
    **run 단위 예측은 여기서 쓰지 않는다.** 계획서 §8 은 세 seed 의 창 확률을
    먼저 평균하라고 정하므로, run 집계는 `evaluate` 의 몫이다. 여기서 n_seeds=1
    짜리 run 예측을 내면 최종 산출물과 혼동된다.

    Raises:
        CLIError: 입력이 어긋나거나 산출물을 덮어쓰게 될 때.
    """
    from mobse.v2 import fitting as FIT
    from mobse.v2 import templates as TPL
    from mobse.v2.manifests import code_hash, fit_id, sha256_file, write_jsonl
    from mobse.v2.models import save_checkpoint

    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc

    task_manifests = [Path(p) for p in args.task_manifests]
    missing = [str(p) for p in task_manifests if not p.exists()]
    if missing:
        raise CLIError(f"task manifest 가 없다: {missing}. 대체 탐색하지 않는다 (U20)")

    out_dir = Path(paths["output_dir"])
    for name in ("fit_manifest.json", "checkpoint.pt", "window_predictions.jsonl"):
        if (out_dir / name).exists():
            raise CLIError(f"이미 존재한다: {out_dir / name}. 같은 release 결과를 "
                           "덮어쓰지 않는다 (지침서 §2)")

    folds = json.loads(Path(paths["splits"]).read_text(encoding="utf-8"))
    fold = FIT.resolve_fold_subjects(folds, int(args.outer_fold), int(args.inner_fold))

    group_of = {}
    for line in Path(paths["subjects"]).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            group_of[rec["canonical_subject"]] = rec["group_id"]
    unknown = sorted((set(fold.train) | set(fold.evaluate)) - set(group_of))
    if unknown:
        raise CLIError(f"subjects.jsonl 에 없는 subject: {unknown[:5]}")

    verify = not bool(getattr(args, "skip_hash_verify", False))
    task_refs: List[Any] = []
    for mp in task_manifests:
        task_refs += FIT.refs_from_extract_manifest(mp, labelled=True)
    FIT.crosscheck_with_windows_manifest(task_refs, Path(paths["windows"]))
    rest_refs = FIT.refs_from_extract_manifest(Path(paths["rest_manifest"]),
                                               labelled=False)

    bank_seed = TPL.bank_seed(int(args.outer_fold), int(args.inner_fold))
    transform = FIT.fit_fold_transform(
        rest_refs, fold.train, bank_seed=bank_seed,
        null_seed=int(cfg["bank.null_seed"]),
        n_components=int(cfg["bank.pca_components"]),
        k=int(cfg["bank.k"]), density=float(cfg["bank.edge_density"]),
        verify=verify)

    train_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.train),
                                   transform, verify=verify)
    eval_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.evaluate),
                                  transform, verify=verify)

    is_inner = fold.role == FIT.ROLE_INNER
    result, model = FIT.train_fold(
        train_set, eval_set, transform, cell=args.cell,
        config_id=int(args.config_id), model_seed=int(args.model_seed), fold=fold,
        device=str(getattr(args, "device", "cpu")),
        max_epochs=int(args.epochs) if is_inner else int(cfg["train.max_epochs"]),
        batch_size=int(cfg["train.batch_size"]),
        patience=int(cfg["train.patience"]),
        min_delta=float(cfg["train.min_delta"]),
        grad_clip=float(cfg["train.grad_clip"]),
        epochs_exact=None if is_inner else int(args.epochs),
        min_updates=int(cfg["train.min_updates"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / "checkpoint.pt"
    save_checkpoint(model, ckpt_path)
    ckpt_sha = sha256_file(ckpt_path)

    cfg_hash = config_hash(cfg)
    module_dir = Path(__file__).resolve().parent
    fid = fit_id(role=fold.role, cell=args.cell, outer_fold=int(args.outer_fold),
                 inner_fold=int(args.inner_fold), model_seed=int(args.model_seed),
                 split_hash=folds["split_hash"], config_hash=cfg_hash)

    rows = []
    for ref in eval_set.refs:
        rows.append({
            "schema_version": "wi05-window-predictions-0.1",
            "canonical_subject": ref.canonical_subject,
            "group_id": group_of[ref.canonical_subject],
            "run_key": ref.run_key, "window_key": ref.window_key,
            "truth": int(ref.label),
            "p_class1": float(result.eval_window_probs[ref.window_key]),
            "cell": args.cell, "model_seed": int(args.model_seed),
            "scope": fold.eval_role, "checkpoint_sha256": ckpt_sha, "fit_id": fid,
        })
    written = write_jsonl(out_dir / "window_predictions.jsonl",
                          "window_predictions", rows)

    manifest = {
        "schema_version": "wi05-fit-manifest-0.1", "fit_id": fid,
        "parent_release": str(Path(paths["config"]).parent),
        "role": fold.role, "cell": args.cell,
        "folds": {"outer_fold": int(args.outer_fold),
                  "inner_fold": int(args.inner_fold),
                  "n_train_subjects": len(fold.train),
                  "n_eval_subjects": len(fold.evaluate),
                  "eval_role": fold.eval_role},
        "model_seed": int(args.model_seed), "bank_seed": bank_seed,
        "null_seed": int(cfg["bank.null_seed"]),
        "fit_subjects": list(fold.train),
        "scaler_id": transform.frozen.artifact_id,
        "pca_id": transform.frozen.artifact_id,
        "bank_id": transform.brain.bank_id,
        "code_hash": code_hash(sorted(module_dir.glob("*.py"))),
        "env_hash": _env_hash(), "config_hash": cfg_hash,
        "source_hash": sha256_file(Path(paths["windows"])),
        "split_hash": folds["split_hash"],
    }
    validate_record("fit_manifest", manifest)
    (out_dir / "fit_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    from mobse.v2.train import build_grid as _grid
    gc = {g.config_id: g for g in _grid()}[int(args.config_id)]
    report = {
        "fit_id": fid, "config_id": int(args.config_id),
        "config": gc.as_dict(),
        "epochs_run": result.epochs_run, "best_epoch": result.best_epoch,
        "min_epoch": result.min_epoch, "updates_per_epoch": result.updates_per_epoch,
        "updates_run": result.updates_run, "min_updates": int(cfg["train.min_updates"]),
        "val_losses": result.val_losses, "eval_loss": result.eval_loss,
        "eval_balanced_accuracy": result.eval_balanced_accuracy,
        "eval_role": fold.eval_role, "transform": result.transform,
        "timing": result.timing, "memory": result.memory,
        "encoder_init_hash": result.encoder_init_hash, "rng_note": result.rng_note,
        "n_train_windows": len(train_set), "n_eval_windows": len(eval_set),
        "checkpoint_sha256": ckpt_sha,
    }
    (out_dir / "fit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "verdict": "pass", "fit_id": fid, "role": fold.role, "cell": args.cell,
        "outer_fold": int(args.outer_fold), "inner_fold": int(args.inner_fold),
        "config_id": int(args.config_id), "model_seed": int(args.model_seed),
        "best_epoch": result.best_epoch, "epochs_run": result.epochs_run,
        "min_epoch": result.min_epoch, "updates_run": result.updates_run,
        "eval_role": fold.eval_role, "eval_loss": result.eval_loss,
        "eval_balanced_accuracy": result.eval_balanced_accuracy,
        "n_train_windows": len(train_set), "n_eval_windows": len(eval_set),
        "window_predictions": written, "bank_seed": bank_seed,
        "timing": result.timing, "memory": result.memory,
        "output_dir": str(out_dir),
    }


#: evaluate 산출물. 둘 중 하나라도 있으면 실행하지 않는다 (지침서 §2).
EVALUATE_OUTPUTS = ("run_predictions.jsonl", "evaluation.json")

#: run_predictions 의 schema_version. WI-06 CLI 가 쓰는 artifact 다.
RUN_PREDICTIONS_SCHEMA = "wi06-run-predictions-0.1"


def _window_index(run_key: str, window_key: str) -> int:
    """``<run_key>#win-<n>`` 에서 n 을 꺼낸다. 접두가 run_key 와 다르면 실패한다."""
    prefix, sep, tail = window_key.rpartition("#win-")
    if not sep or prefix != run_key or not tail.isdigit():
        raise CLIError(f"window_key 가 run_key 와 맞지 않는다: {window_key!r} / {run_key!r}")
    return int(tail)


def _load_fit_manifests(manifest_paths: Sequence[str], *, split_hash: str,
                        cfg_hash: str) -> Dict[str, Dict[str, Any]]:
    """outer 최종 적합의 fit_manifest 를 읽고 경계를 검사한다.

    checkpoint 는 manifest 옆의 고정 이름 ``checkpoint.pt`` 다 — 명시한 manifest
    경로에서 결정되므로 glob·mtime 탐색이 아니다 (U20). 해시는 다시 계산한다.

    Raises:
        CLIError: 스키마·split·config 불일치, inner fit, 중복, checkpoint 누락.
    """
    from mobse.v2 import fitting as FIT
    from mobse.v2.manifests import sha256_file

    fits: Dict[str, Dict[str, Any]] = {}
    slots: Dict[tuple, str] = {}
    for mp in manifest_paths:
        path = Path(mp)
        man = json.loads(path.read_text(encoding="utf-8"))
        try:
            validate_record("fit_manifest", man)
        except ManifestError as exc:
            raise CLIError(f"{path}: fit_manifest 스키마 위반 — {exc}") from exc
        fid = man["fit_id"]
        if fid in fits:
            raise CLIError(f"fit_id 중복: {fid} ({fits[fid]['path']} 와 {path})")
        if man["role"] != FIT.ROLE_OUTER or \
                man["folds"].get("eval_role") != FIT.EVAL_ROLE[FIT.ROLE_OUTER]:
            raise CLIError(f"{fid}: outer 최종 적합이 아니다 (role={man['role']!r}). "
                           "evaluate 는 outer test 예측만 집계한다 (계획서 §8)")
        if man["split_hash"] != split_hash:
            raise CLIError(f"{fid}: split_hash 가 --splits 와 다르다")
        if man["config_hash"] != cfg_hash:
            raise CLIError(f"{fid}: config_hash 가 --config 와 다르다")
        slot = (man["cell"], int(man["folds"]["outer_fold"]), int(man["model_seed"]))
        if slot in slots:
            raise CLIError(f"같은 (cell, outer_fold, seed) {slot} 의 fit 이 둘이다: "
                           f"{slots[slot]}, {fid}")
        slots[slot] = fid
        ckpt = path.parent / "checkpoint.pt"
        if not ckpt.is_file():
            raise CLIError(f"{fid}: checkpoint 가 없다 {ckpt}. 대체 탐색하지 않는다 (U20)")
        fits[fid] = {"path": str(path), "manifest": man, "slot": slot,
                     "manifest_sha256": sha256_file(path),
                     "checkpoint_sha256": sha256_file(ckpt)}

    for field in ("code_hash", "env_hash", "source_hash"):
        values = sorted({f["manifest"][field] for f in fits.values()})
        if len(values) != 1:
            raise CLIError(f"fit 사이에 {field} 가 다르다 {[v[:12] for v in values]}. "
                           "한 release 에 다른 코드·환경·입력을 섞지 않는다")
    return fits


def _check_fit_grid(fits: Mapping[str, Mapping[str, Any]], folds: Mapping[str, Any]
                    ) -> Dict[str, Any]:
    """cell × outer fold × seed 격자가 빠짐없이 채워졌는지 확인한다."""
    from mobse.v2.evaluate import CELLS
    from mobse.v2.statistics import N_SEEDS

    outer_ids = sorted(int(o["outer_fold"]) for o in folds.get("outer_folds") or [])
    if not outer_ids:
        raise CLIError("folds.json 에 outer fold 가 없다")
    by_cf: Dict[tuple, set] = {}
    for f in fits.values():
        cell, of, seed = f["slot"]
        by_cf.setdefault((cell, of), set()).add(seed)
    seed_sets = set()
    missing = []
    for cell in CELLS:
        for of in outer_ids:
            seeds = by_cf.get((cell, of), set())
            if len(seeds) != N_SEEDS:
                missing.append((cell, of, len(seeds)))
            seed_sets.add(tuple(sorted(seeds)))
    extra = sorted(set(by_cf) - {(c, o) for c in CELLS for o in outer_ids})
    if missing or extra:
        raise CLIError(f"fit 격자가 비었거나 넘친다 — 부족 (cell, fold, seed 수) "
                       f"{missing[:5]}, 알 수 없는 칸 {extra[:5]}")
    if len(seed_sets) != 1:
        raise CLIError(f"칸마다 seed 집합이 다르다: {sorted(seed_sets)[:3]}")
    return {"outer_folds": outer_ids, "seeds": list(seed_sets.pop()),
            "n_fits": len(fits)}


def run_evaluate(paths: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """outer test 창 예측을 run·subject·cell 로 집계한다 (계획서 §8, 지침서 WI-06).

    **분류만** 다룬다(T16). 부트스트랩·gate 판정은 ``report`` 의 몫이다. 이
    함수는 무결성(T15)을 확인한 뒤 run 예측과 cell 별 BA·subject 차이를 쓴다.

    Raises:
        CLIError: 입력 무결성이 어긋나거나 산출물을 덮어쓰게 될 때.
    """
    from mobse.v2 import evaluate as EV
    from mobse.v2 import fitting as FIT
    from mobse.v2.manifests import code_hash, read_jsonl, sha256_file, write_jsonl
    from mobse.v2.statistics import THRESHOLD, balanced_accuracy

    try:
        tasks = EV.assert_classification_only(args.tasks)
    except EV.EvaluationError as exc:
        raise CLIError(str(exc)) from exc
    if sorted(tasks) != sorted(EV.CLASSIFICATION_TASKS) or len(tasks) != 2:
        raise CLIError(f"두 task 를 모두 지정해야 한다: {list(EV.CLASSIFICATION_TASKS)}. "
                       f"b_i 는 complete-case 로만 정의된다 (계획서 §8). 받은 값 {list(tasks)}")
    tasks = EV.CLASSIFICATION_TASKS

    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc
    cfg_hash = config_hash(cfg)

    out_dir = Path(paths["output_dir"])
    for name in EVALUATE_OUTPUTS:
        if (out_dir / name).exists():
            raise CLIError(f"이미 존재한다: {out_dir / name}. 같은 release 결과를 "
                           "덮어쓰지 않는다 (지침서 §2)")

    folds = json.loads(Path(paths["splits"]).read_text(encoding="utf-8"))
    split_hash = folds["split_hash"]
    fits = _load_fit_manifests(_as_list(paths["fit_manifest"]),
                               split_hash=split_hash, cfg_hash=cfg_hash)
    grid = _check_fit_grid(fits, folds)
    test_of = {int(o["outer_fold"]): set(o["test_subjects"])
               for o in folds["outer_folds"]}
    expected_subjects = set().union(*test_of.values())

    preds: List[Any] = []
    used: Dict[str, str] = {}
    run_key_of: Dict[tuple, set] = {}
    inputs = []
    for pp in _as_list(paths["predictions"]):
        try:
            rows = read_jsonl(Path(pp), "window_predictions")
        except ManifestError as exc:
            raise CLIError(f"{pp}: window_predictions 스키마 위반 — {exc}") from exc
        inputs.append({"path": str(pp), "sha256": sha256_file(Path(pp)),
                       "n_rows": len(rows)})
        for i, r in enumerate(rows):
            fid = r["fit_id"]
            if fid not in fits:
                raise CLIError(f"{pp}:{i + 1}: fit_manifest 가 주어지지 않은 fit_id {fid}")
            fit = fits[fid]
            cell, of, seed = fit["slot"]
            if (r["cell"], int(r["model_seed"])) != (cell, seed):
                raise CLIError(f"{pp}:{i + 1}: cell/seed 가 fit_manifest 와 다르다")
            if r["scope"] != FIT.EVAL_ROLE[FIT.ROLE_OUTER]:
                raise CLIError(f"{pp}:{i + 1}: scope {r['scope']!r} — outer test 만 집계한다")
            if r["canonical_subject"] in fit["manifest"]["fit_subjects"]:
                raise CLIError(f"{pp}:{i + 1}: {r['canonical_subject']} 가 {fid} 의 "
                               "학습 subject 다 — test 누설")
            if r["canonical_subject"] not in test_of[of]:
                raise CLIError(f"{pp}:{i + 1}: {r['canonical_subject']} 는 outer fold {of} "
                               "의 test subject 가 아니다")
            prev = used.setdefault(fid, r["checkpoint_sha256"])
            if prev != r["checkpoint_sha256"]:
                raise CLIError(f"{fid}: 한 fit 의 예측에 checkpoint hash 가 둘이다")
            task = FIT.task_of(r["run_key"])
            run_key_of.setdefault((r["canonical_subject"], task), set()).add(r["run_key"])
            try:
                preds.append(EV.WindowPrediction(
                    canonical_subject=r["canonical_subject"], group_id=r["group_id"],
                    task=task, window_index=_window_index(r["run_key"], r["window_key"]),
                    model_seed=int(r["model_seed"]), cell=r["cell"],
                    truth=int(r["truth"]), p_class1=float(r["p_class1"])))
            except EV.EvaluationError as exc:
                raise CLIError(f"{pp}:{i + 1}: {exc}") from exc

    multi = sorted(k for k, v in run_key_of.items() if len(v) != 1)
    if multi:
        raise CLIError(f"subject·task 하나에 run 이 여럿이다: {multi[:3]}. "
                       "run 선택 규칙 없이 섞지 않는다")
    try:
        EV.verify_checkpoint_integrity(
            used, {fid: f["checkpoint_sha256"] for fid, f in fits.items()})
        counts = EV.verify_release_completeness(preds, expected_subjects)
        runs = EV.aggregate_runs(preds)
        scores = {c: EV.subject_scores(runs, c, tasks=tasks) for c in EV.CELLS}
        contrasts = EV.primary_contrasts(runs)
    except EV.EvaluationError as exc:
        raise CLIError(f"무결성 검사 실패: {exc}") from exc

    run_rows = []
    for (cell, subject, task), rec in sorted(runs.items()):
        run_rows.append({
            "schema_version": RUN_PREDICTIONS_SCHEMA, "canonical_subject": subject,
            "run_key": next(iter(run_key_of[(subject, task)])),
            "truth": int(rec["truth"]), "ensemble_p": float(rec["p"]),
            "n_windows": int(rec["n_windows"]), "n_seeds": int(rec["n_seeds"]),
            "threshold": float(THRESHOLD), "prediction": int(rec["prediction"]),
            "cell": cell,
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    written = write_jsonl(out_dir / "run_predictions.jsonl", "run_predictions", run_rows)

    ba = {c: balanced_accuracy(list(scores[c].values())) for c in EV.CELLS}
    summary = {
        "schema_version": "wi06-evaluation-0.1",
        "tasks": list(tasks), "threshold": float(THRESHOLD),
        "split_hash": split_hash, "config_hash": cfg_hash,
        "fit_code_hash": next(iter(fits.values()))["manifest"]["code_hash"],
        "evaluator_code_hash": code_hash(sorted(Path(__file__).resolve().parent.glob("*.py"))),
        "fit_grid": grid, "counts": counts,
        "balanced_accuracy": ba,
        "mean_differences": {k: float(sum(v.values()) / len(v))
                             for k, v in contrasts.items()},
        "subject_scores": {c: dict(sorted(scores[c].items())) for c in EV.CELLS},
        "subject_differences": {k: dict(sorted(v.items())) for k, v in contrasts.items()},
        "inputs": {"predictions": inputs,
                   "fit_manifests": [{"fit_id": fid, "path": f["path"],
                                      "sha256": f["manifest_sha256"],
                                      "checkpoint_sha256": f["checkpoint_sha256"]}
                                     for fid, f in sorted(fits.items())]},
        "run_predictions": written,
        "not_here": "paired bootstrap 구간과 gate 판정은 report 단계가 낸다",
    }
    (out_dir / "evaluation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"verdict": "pass", "n_fits": grid["n_fits"],
            "window_rows": counts["window_rows"], "run_rows": written["n_records"],
            "subjects": counts["subjects"], "balanced_accuracy": ba,
            "mean_differences": summary["mean_differences"],
            "output_dir": str(out_dir)}


def _as_list(value: Any) -> List[str]:
    """경로 인자를 목록으로. nargs='+' 인자와 단일 경로를 같게 다룬다."""
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    paths = resolve_paths(args.command, args)
    check_inputs_exist(paths)
    print(json.dumps({"command": args.command, "paths": paths,
                      "dry_run": bool(getattr(args, "dry_run", False))},
                     indent=2, ensure_ascii=False))
    if getattr(args, "dry_run", False):
        return 0

    if args.command == "validate":
        result = run_validate(paths)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "split":
        result = run_split(paths)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "fit":
        result = run_fit(paths, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "evaluate":
        result = run_evaluate(paths, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    raise NotImplementedError(
        f"{args.command} 의 실행 본체는 아직 구현되지 않았다 — WI-02 재추출 "
        "산출물을 입력으로 받는다. 이 CLI 는 경로 계약과 하위 명령 경계를 "
        "고정한다. 본체가 있는 명령은 validate·split·fit·evaluate 다 (지침서 WI-06)")


if __name__ == "__main__":
    raise SystemExit(main())
