"""명시적 CLI — 지침서 WI-06.

모든 경로를 **필수 인자**로 받는다. 기존 코드가 mtime 최신 파일이나 glob 최후
항목으로 checkpoint·template 을 대신 찾던 동작(차단 항목 U20,
`mobse/io.py:10-14`, `mobse/evaluate.py:94`)을 이 계층에서 원천 차단한다.

하위 명령은 역할이 겹치지 않는다:

* ``validate``  — manifest 스키마와 split 경계만 검사한다. 학습·평가하지 않는다.
* ``prepare``   — 시간축·window·QC 를 산출한다.
* ``split``     — pilot 과 outer/inner fold 를 만든다.
* ``fit``       — 지정한 fold·cell·seed 하나를 학습한다.
* ``evaluate``  — 저장된 예측을 집계한다. **분류만.**
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
    "fit": ("config", "splits", "windows", "output_dir"),
    "evaluate": ("config", "splits", "predictions", "fit_manifest", "output_dir"),
    "report": ("config", "predictions", "output_dir"),
}


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
        "output_dir": "산출 디렉터리",
    }
    for name in SUBCOMMANDS:
        p = subs.add_parser(name, help=f"{name} 단계")
        for arg in REQUIRED_PATHS[name]:
            p.add_argument(f"--{arg.replace('_', '-')}", type=Path, required=True,
                           help=common[arg])
        if name == "fit":
            p.add_argument("--cell", required=True, choices=list("ABCD"))
            p.add_argument("--outer-fold", type=int, required=True)
            p.add_argument("--inner-fold", type=int, required=True)
            p.add_argument("--model-seed", type=int, required=True)
            p.add_argument("--epochs", type=int, required=True)
        if name == "evaluate":
            p.add_argument("--tasks", nargs="+", required=True,
                           help="평가할 분류 task. 학습하지 않은 task 는 거부된다")
        p.add_argument("--dry-run", action="store_true",
                       help="경로와 스키마만 검사하고 실행하지 않는다")
    return ap


def resolve_paths(command: str, namespace: argparse.Namespace) -> Dict[str, str]:
    """필수 경로가 모두 주어졌는지 확인한다.

    Raises:
        CLIError: 알 수 없는 명령.
        ManifestError: 비어 있는 경로가 있으면 (U20).
    """
    if command not in REQUIRED_PATHS:
        raise CLIError(f"알 수 없는 하위 명령: {command!r}. 허용: {list(SUBCOMMANDS)}")
    resolved = {k: (str(getattr(namespace, k)) if getattr(namespace, k, None) else None)
                for k in REQUIRED_PATHS[command]}
    assert_no_glob_fallback(resolved)
    return {k: v for k, v in resolved.items() if v is not None}


def check_inputs_exist(paths: Dict[str, str], *, skip: Sequence[str] = ("output_dir",)
                       ) -> None:
    """입력 경로가 실제로 존재하는지 확인한다. 없으면 대체 탐색하지 않고 실패한다."""
    missing = [k for k, v in paths.items() if k not in skip and not Path(v).exists()]
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

    raise NotImplementedError(
        f"{args.command} 의 실행 본체는 아직 구현되지 않았다 — WI-02 재추출 "
        "산출물을 입력으로 받는다. 이 CLI 는 경로 계약과 하위 명령 경계를 "
        "고정하며, validate 만 원자료 없이 완결된다 (지침서 WI-06)")


if __name__ == "__main__":
    raise SystemExit(main())
