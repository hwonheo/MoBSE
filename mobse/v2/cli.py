"""명시적 CLI — 지침서 WI-06.

모든 경로를 **필수 인자**로 받는다. 기존 코드가 mtime 최신 파일이나 glob 최후
항목으로 checkpoint·template 을 대신 찾던 동작(차단 항목 U20,
`mobse/io.py:10-14`, `mobse/evaluate.py:94`)을 이 계층에서 원천 차단한다.

하위 명령은 역할이 겹치지 않는다:

* ``validate``  — manifest 스키마와 split 경계만 검사한다. 학습·평가하지 않는다.
* ``prepare``   — WI-02 추출 manifest(시간축·window·QC 가 이미 계산된 기록)를
  ``windows.jsonl``·``subjects.jsonl``·``exclusions.jsonl`` 로 접는다. 원자료를
  읽는 추출 자체는 ``scripts/h197/10_wi02_extract.py`` 의 몫이다.
* ``split``     — pilot 과 outer/inner fold 를 만든다.
* ``fit``       — 지정한 fold·cell·seed 하나를 학습한다.
* ``fit-s``     — §6 S 후보(S1–S4) 하나·설정 하나를 fold 하나에 학습한다 (결정 14 4c-i).
* ``select-comparator`` — §6 구조 비교(NG·SG) 하나의 inner fit 산출물로 config·
  outer E 를 고르고 선택 기록을 쓴다 (결정 14 4b). 학습하지 않는다.
* ``evaluate``  — 저장된 outer test 예측을 run·subject·cell 로 집계한다. **분류만.**
  부트스트랩·gate 판정은 하지 않는다 (``report`` 의 몫).
* ``report``    — evaluate 산출물로 paired group bootstrap 구간과 G3 완전성·정합성
  판정을 낸다. 유의성은 gate 가 아니다 (계획서 §8).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from mobse.v2.config import ConfigError, config_hash, load_config
from mobse.v2.manifests import ManifestError, assert_no_glob_fallback, validate_record

SUBCOMMANDS = ("validate", "prepare", "split", "fit", "fit-s", "select-comparator",
               "evaluate", "report")

#: 하위 명령별 필수 경로 인자. 하나라도 비면 실행하지 않는다.
REQUIRED_PATHS: Dict[str, Sequence[str]] = {
    "validate": ("config", "source_runs"),
    # prepare 는 WI-02 추출 manifest(한 dataset 의 세 task)를 받아 windows·subjects 를
    # 만든다. 추출(fMRIPrep → ROI 창)은 scripts/h197/10 이 한다 — 원자료 경로·atlas 가
    # 필요하고 209 GiB 를 읽으므로 CLI 에 넣지 않는다 (구현 선택, 보고서 부록 AE).
    "prepare": ("config", "extract_manifests", "output_dir"),
    "split": ("config", "subjects", "output_dir"),
    "fit": ("config", "splits", "subjects", "windows", "rest_manifest", "output_dir"),
    # fit-s 는 S 후보 한 칸이다 (결정 14 4c-i). raw ROI 창에서 feature 를 만들므로
    # bank·PCA 가 없다 — rest manifest 를 받지 않는다.
    "fit-s": ("config", "splits", "subjects", "windows", "output_dir"),
    # select-comparator 는 구조 하나·outer fold 하나의 inner fit_manifest 24 개(8 config
    # × 3 inner fold)를 받는다. fit_report.json·window_predictions.jsonl 은 각 manifest
    # 옆의 고정 이름이다 — 명시한 경로에서 결정되므로 탐색이 아니다 (U20).
    "select-comparator": ("config", "splits", "fit_manifest", "output_dir"),
    "evaluate": ("config", "splits", "predictions", "fit_manifest", "output_dir"),
    # report 는 evaluate 산출물(evaluation.json·run_predictions.jsonl)과 group 매핑의
    # 출처인 subjects.jsonl 을 받는다. run_predictions 에는 group_id 가 없다.
    "report": ("config", "evaluation", "predictions", "subjects", "output_dir"),
}


#: 여러 경로를 받는 (하위 명령, 인자). release 하나는 cell × outer fold × seed
#: 개의 fit 으로 이루어지므로 evaluate 는 그 산출물을 전부 명시적으로 받는다.
MULTI_PATHS = frozenset({("evaluate", "predictions"), ("evaluate", "fit_manifest"),
                         ("select-comparator", "fit_manifest"),
                         ("prepare", "extract_manifests")})


#: `fit --cell` 선택지 — A–D 다음 구조 비교 순서 (결정 14 4단계).
FIT_CELL_CHOICES: Tuple[str, ...] = ("A", "B", "C", "D", "NG", "SG")

#: `fit-s --candidate` 선택지 — `baselines.CANDIDATE_ORDER` 와 같다 (시험 고정).
S_CANDIDATE_CHOICES: Tuple[str, ...] = ("S1_roi_mean_var_logreg", "S2_roi_mean_var_mlp",
                                        "S3_fc_fisher_z_logreg", "S4_fc_fisher_z_mlp")


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
        "predictions": "예측 JSONL 경로 (evaluate: window_predictions, report: run_predictions)",
        "evaluation": "evaluate 가 쓴 evaluation.json 경로",
        "extract_manifests": "WI-02 추출 manifest (한 dataset 의 emomatching·workingmemory·restingstate 셋)",
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
            # 결정 14 4단계 — §6 구조 비교(NG·SG)도 같은 `fit` 으로 한 칸씩 학습한다.
            # 별도 하위 명령을 두지 않는 것은 구현 선택이다: 학습 규칙이 A–D 와 같은
            # `train_fold` 한 경로이므로 입력·산출물 계약도 하나로 둔다.
            p.add_argument("--cell", required=True, choices=FIT_CELL_CHOICES,
                           help="A–D (2×2) 또는 §6 구조 비교 NG·SG")
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
        if name == "fit-s":
            # 결정 14 4c-i. `fit` 과 입력 계약이 다르다 (raw 창 feature, bank 없음,
            # logistic 은 seed·epoch 없음) — 그래서 별도 하위 명령이다 (구현 선택).
            p.add_argument("--candidate", required=True, choices=S_CANDIDATE_CHOICES,
                           help="S 후보 (계획서 §6 표)")
            p.add_argument("--setting-id", required=True,
                           help="logistic 은 'C=<값>', MLP 는 'config=<0–7>'")
            p.add_argument("--outer-fold", type=int, required=True)
            p.add_argument("--inner-fold", type=int, required=True,
                           help="inner fold 번호. 9 는 outer 최종 적합이다")
            p.add_argument("--model-seed", type=int, default=None,
                           help="MLP 만. logistic 에 주면 거부한다")
            p.add_argument("--epochs", type=int, default=None,
                           help="MLP outer 만 — 정확히 이만큼. inner·logistic 에 주면 거부")
            p.add_argument("--task-manifests", type=Path, nargs="+", required=True,
                           help="WI-02 target task 추출 manifest. 창 경로의 유일한 출처다")
            p.add_argument("--device", default="cpu")
            p.add_argument("--skip-hash-verify", action="store_true",
                           help="창 sha256 대조를 건너뛴다. 기본은 대조한다")
        if name == "select-comparator":
            p.add_argument("--structure", required=True, choices=FIT_CELL_CHOICES[4:],
                           help="§6 구조 비교 NG 또는 SG — 구조별 독립 선택 (결정 14 (가))")
            p.add_argument("--outer-fold", type=int, required=True)
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

    locked_seeds = tuple(int(s) for s in cfg["train.model_seeds"])
    if int(args.model_seed) not in locked_seeds:
        raise CLIError(f"--model-seed {args.model_seed} 는 잠긴 train.model_seeds "
                       f"{locked_seeds} 밖이다 (계획서 §5)")

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
        verify=verify, single_graph=(args.cell == "SG"))

    train_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.train),
                                   transform, verify=verify)
    eval_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.evaluate),
                                  transform, verify=verify)

    if cfg["runtime.deterministic"] is not True:
        raise CLIError("runtime.deterministic 은 True 여야 한다 (E22)")
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
                 config_id=int(args.config_id),
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
    if transform.single is not None:
        # SG 의 graph 는 이 fit 의 training-rest 로 만든 것이다 — 출처를 manifest 에 남긴다.
        manifest["single_graph_id"] = transform.single.graph_id
        manifest["single_graph_fingerprint"] = transform.single.fingerprint()
    validate_record("fit_manifest", manifest)
    (out_dir / "fit_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    from mobse.v2.train import build_grid as _grid
    gc = {g.config_id: g for g in _grid()}[int(args.config_id)]
    report = {
        "fit_id": fid, "config_id": int(args.config_id),
        "config": gc.as_dict(),
        "epochs_run": result.epochs_run, "best_epoch": result.best_epoch,
        "eval_epoch": result.eval_epoch,
        "min_epoch": result.min_epoch, "updates_per_epoch": result.updates_per_epoch,
        "updates_run": result.updates_run, "min_updates": int(cfg["train.min_updates"]),
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


#: fit-s 산출물. 하나라도 있으면 실행하지 않는다 (지침서 §2).
S_FIT_OUTPUTS = ("s_fit_report.json", "s_window_predictions.jsonl", "s_model.npz")
S_FIT_SCHEMA = "d14-s-fit-report-0.1"
S_PRED_SCHEMA = "d14-s-window-predictions-0.1"


def run_fit_s(paths: Dict[str, str], args: argparse.Namespace) -> Dict[str, Any]:
    """S 후보 하나·설정 하나를 fold 하나에 학습한다 (결정 14 4c-i, 계획서 §6).

    feature 는 raw ROI 창에서 `baselines.feature_matrix` 로 만든다 (S1·S2 ROI
    mean/variance 200, S3·S4 signed Fisher-z FC 4,950). StandardScaler 는 이 fit 의
    training 창에만 맞춘다 (`fit_logistic`·`fit_mlp` 안). bank·PCA 는 쓰지 않는다.

    산출물 셋 — ``s_fit_report.json`` (식별자·provenance·fit 기록·평가 손실),
    ``s_window_predictions.jsonl`` (평가 집합 창 확률), ``s_model.npz`` (scaler 와
    parameter 배열). run 확률은 쓰지 않는다: 선택은 inner 산출물을 모아 따로 한다
    (4c-ii), outer 예측 집계도 fit 단위가 아니다.

    구현 선택 (결정 아님, 보고서에 표시): 하위 명령을 `fit` 과 나눈 것 (입력 계약이
    다르다), logistic 에 seed·epoch 인자를 받지 않는 것, MLP inner 에 ``--epochs`` 를
    받지 않는 것 (상한은 호출 시점 `train.MAX_EPOCHS`), 모델을 npz 배열로 저장하는 것.

    Raises:
        CLIError: 입력이 어긋나거나 산출물을 덮어쓰게 될 때, 하위 fit 규칙 위반.
    """
    import numpy as np

    from mobse.v2 import baselines as BL
    from mobse.v2 import fitting as FIT
    from mobse.v2 import templates as TPL
    from mobse.v2.manifests import code_hash, s_fit_id, sha256_file, write_jsonl

    candidate = str(args.candidate)
    if candidate not in BL.CANDIDATE_ORDER:
        raise CLIError(f"--candidate {candidate!r} 는 S 후보가 아니다: {BL.CANDIDATE_ORDER}")
    is_logistic = candidate in BL.LOGISTIC_CANDIDATES
    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc
    if cfg["runtime.deterministic"] is not True:
        raise CLIError("runtime.deterministic 은 True 여야 한다 (E22)")

    seed = args.model_seed
    if is_logistic:
        if seed is not None or args.epochs is not None:
            raise CLIError(f"{candidate} 는 logistic 이다 — --model-seed·--epochs 를 받지 "
                           "않는다 (결정적 lbfgs)")
    else:
        if seed is None:
            raise CLIError(f"{candidate} 는 MLP 다 — --model-seed 가 필요하다 (계획서 §5)")
        locked = tuple(int(s) for s in cfg["train.model_seeds"])
        if int(seed) not in locked:
            raise CLIError(f"--model-seed {seed} 는 잠긴 train.model_seeds {locked} 밖이다 "
                           "(계획서 §5)")
        seed = int(seed)
    settings = BL.s_settings(candidate)
    if args.setting_id not in settings:
        raise CLIError(f"--setting-id {args.setting_id!r} 는 {candidate} grid 밖이다. "
                       f"허용: {list(settings)}")

    task_manifests = [Path(p) for p in args.task_manifests]
    missing = [str(p) for p in task_manifests if not p.exists()]
    if missing:
        raise CLIError(f"task manifest 가 없다: {missing}. 대체 탐색하지 않는다 (U20)")
    out_dir = Path(paths["output_dir"])
    for name in S_FIT_OUTPUTS:
        if (out_dir / name).exists():
            raise CLIError(f"이미 존재한다: {out_dir / name}. 같은 release 결과를 "
                           "덮어쓰지 않는다 (지침서 §2)")

    folds = json.loads(Path(paths["splits"]).read_text(encoding="utf-8"))
    outer_fold, inner_fold = int(args.outer_fold), int(args.inner_fold)
    fold = FIT.resolve_fold_subjects(folds, outer_fold, inner_fold)
    is_inner = fold.role == FIT.ROLE_INNER
    if not is_logistic:
        if is_inner and args.epochs is not None:
            raise CLIError("MLP inner fit 은 --epochs 를 받지 않는다 — early stopping 이다 "
                           "(상한은 train.MAX_EPOCHS)")
        if not is_inner and args.epochs is None:
            raise CLIError("MLP outer fit 은 --epochs (선택 설정 inner best epochs 중앙값 "
                           "올림) 가 필요하다 (계획서 §7)")

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
    train_refs = FIT.select_refs(task_refs, fold.train)
    eval_refs = FIT.select_refs(task_refs, fold.evaluate)
    if not train_refs or not eval_refs:
        raise CLIError(f"창이 없다: train {len(train_refs)}, eval {len(eval_refs)}")
    kind = BL.CANDIDATE_FEATURE[candidate]
    try:
        X_train = BL.feature_matrix([FIT.read_window(r, verify=verify) for r in train_refs],
                                    kind)
        X_eval = BL.feature_matrix([FIT.read_window(r, verify=verify) for r in eval_refs],
                                   kind)
        res = BL.fit_s(X_train, [int(r.label) for r in train_refs], X_eval,
                       [r.run_key for r in eval_refs], candidate=candidate,
                       setting_id=str(args.setting_id), role=fold.role,
                       model_seed=seed,
                       epochs_exact=None if (is_logistic or is_inner) else int(args.epochs),
                       min_updates=None if is_logistic else int(cfg["train.min_updates"]),
                       device=str(getattr(args, "device", "cpu")))
    except (BL.BaselineError, FIT.FitError) as exc:
        raise CLIError(f"S fit 실패: {exc}") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "s_model.npz"
    with model_path.open("wb") as fh:
        np.savez(fh, **res.arrays)
    model_sha = sha256_file(model_path)

    cfg_hash = config_hash(cfg)
    sid = s_fit_id(role=fold.role, candidate=candidate, setting_id=res.setting_id,
                   outer_fold=outer_fold, inner_fold=inner_fold, model_seed=res.model_seed,
                   split_hash=folds["split_hash"], config_hash=cfg_hash)
    rows = [{
        "schema_version": S_PRED_SCHEMA, "canonical_subject": r.canonical_subject,
        "group_id": group_of[r.canonical_subject], "run_key": r.run_key,
        "window_key": r.window_key, "truth": int(r.label), "p_class1": float(p),
        "candidate": candidate, "setting_id": res.setting_id, "scope": fold.eval_role,
        "model_sha256": model_sha, "s_fit_id": sid,
    } for r, p in zip(eval_refs, res.eval_window_p1)]
    written = write_jsonl(out_dir / "s_window_predictions.jsonl", "s_window_predictions", rows)

    module_dir = Path(__file__).resolve().parent
    report = {
        "schema_version": S_FIT_SCHEMA, "s_fit_id": sid, "candidate": candidate,
        "feature": kind, "setting_id": res.setting_id, "setting_rank": res.setting_rank,
        "role": fold.role, "eval_role": fold.eval_role,
        "folds": {"outer_fold": outer_fold, "inner_fold": inner_fold,
                  "n_train_subjects": len(fold.train),
                  "n_eval_subjects": len(fold.evaluate)},
        "model_seed": res.model_seed, "converged": res.converged,
        "best_epoch": res.best_epoch, "eval_loss": res.eval_loss,
        "eval_balanced_accuracy": FIT._balanced_accuracy_from_runs(res.eval_run_probs),
        "fit": res.record, "n_train_windows": len(train_refs),
        "n_eval_windows": len(eval_refs), "n_features": int(X_train.shape[1]),
        "fit_subjects": list(fold.train), "model_sha256": model_sha,
        "window_predictions_sha256": written["sha256"],
        "code_hash": code_hash(sorted(module_dir.glob("*.py"))),
        "env_hash": _env_hash(), "config_hash": cfg_hash,
        "source_hash": sha256_file(Path(paths["windows"])),
        "split_hash": folds["split_hash"],
        "outer_fit_inner_fold": TPL.OUTER_FIT_INNER_FOLD,
    }
    (out_dir / "s_fit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"verdict": "pass", "s_fit_id": sid, "candidate": candidate,
            "setting_id": res.setting_id, "role": fold.role, "outer_fold": outer_fold,
            "inner_fold": inner_fold, "model_seed": res.model_seed,
            "converged": res.converged, "best_epoch": res.best_epoch,
            "eval_role": fold.eval_role, "eval_loss": res.eval_loss,
            "n_train_windows": len(train_refs), "n_eval_windows": len(eval_refs),
            "window_predictions": written, "output_dir": str(out_dir)}


#: select-comparator 산출물. 있으면 실행하지 않는다 (지침서 §2).
SELECTION_OUTPUT = "comparator_selection.json"
SELECTION_SCHEMA = "d14-comparator-selection-0.1"
#: fit_report 의 eval_loss 와 창 예측으로 다시 계산한 inner 손실의 허용 차이.
#: 창 확률은 float32 forward 를 float 로 옮겨 적은 값이라 평균 순서만 다르다.
SELECTION_LOSS_TOL = 1e-6


def run_select_comparator(paths: Dict[str, Any], args: argparse.Namespace
                          ) -> Dict[str, Any]:
    """구조 비교 하나의 inner fit 산출물로 config·outer E 를 고른다 (결정 14 4b).

    입력은 한 구조·한 outer fold 의 inner fit 디렉터리들(각 ``fit_manifest.json``
    와 그 옆의 ``fit_report.json``·``window_predictions.jsonl``)이다. 창 확률은
    ``fitting.run_probabilities`` 로 run 확률이 된다 — ``train_fold`` 가 inner
    ``eval_loss`` 를 계산한 것과 **같은 함수**이고, 그 값과 다시 대조한다.
    ``evaluate.aggregate_runs`` 는 쓰지 않는다: 그것은 seed 3 개 × 창 4 개 격자를
    요구하는 outer test 집계이며, inner fit 은 seed 42 하나다 (계획서 §7).

    선택 규칙은 ``baselines.select_comparator`` 다 (rev40, 구현 선택 표시). 이 함수는
    학습하지 않으며, outer fit 은 기록된 계획대로 ``fit --cell <구조> --inner-fold 9
    --config-id <선택> --epochs <E>`` 를 seed 마다 부른다.

    하위 명령 이름·입력 형식(manifest 목록 + 고정 이웃 파일)은 구현 선택이다.

    Raises:
        CLIError: 입력 경계·무결성이 어긋나거나 산출물을 덮어쓰게 될 때.
    """
    from mobse.v2 import baselines as BL
    from mobse.v2 import fitting as FIT
    from mobse.v2 import templates as TPL
    from mobse.v2 import train as TR
    from mobse.v2.manifests import code_hash, fit_id, read_jsonl, sha256_file

    structure = str(args.structure)
    if structure not in BL.COMPARATOR_ORDER:
        raise CLIError(f"--structure {structure!r} 는 구조 비교가 아니다: {BL.COMPARATOR_ORDER}")
    outer_fold = int(args.outer_fold)
    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc
    cfg_hash = config_hash(cfg)

    out_dir = Path(paths["output_dir"])
    if (out_dir / SELECTION_OUTPUT).exists():
        raise CLIError(f"이미 존재한다: {out_dir / SELECTION_OUTPUT}. 같은 release 결과를 "
                       "덮어쓰지 않는다 (지침서 §2)")
    folds = json.loads(Path(paths["splits"]).read_text(encoding="utf-8"))
    split_hash = folds["split_hash"]

    results: List[Any] = []
    inputs: List[Dict[str, Any]] = []
    seen_ids: Dict[str, str] = {}
    for mp in _as_list(paths["fit_manifest"]):
        path = Path(mp)
        man = json.loads(path.read_text(encoding="utf-8"))
        try:
            validate_record("fit_manifest", man)
        except ManifestError as exc:
            raise CLIError(f"{path}: fit_manifest 스키마 위반 — {exc}") from exc
        fid = man["fit_id"]
        if fid in seen_ids:
            raise CLIError(f"fit_id 중복: {fid} ({seen_ids[fid]} 와 {path})")
        seen_ids[fid] = str(path)
        if man["cell"] != structure:
            raise CLIError(f"{fid}: cell {man['cell']!r} — {structure} 선택에 다른 칸을 "
                           "섞지 않는다 (결정 14 (가) 구조별 독립 선택)")
        if man["role"] != FIT.ROLE_INNER or \
                man["folds"].get("eval_role") != FIT.EVAL_ROLE[FIT.ROLE_INNER]:
            raise CLIError(f"{fid}: inner fit 이 아니다 (role={man['role']!r}). 선택은 "
                           "inner validation 결과로만 한다 (계획서 §7)")
        if int(man["folds"]["outer_fold"]) != outer_fold:
            raise CLIError(f"{fid}: outer fold {man['folds']['outer_fold']} ≠ --outer-fold "
                           f"{outer_fold}")
        if man["split_hash"] != split_hash:
            raise CLIError(f"{fid}: split_hash 가 --splits 와 다르다")
        if man["config_hash"] != cfg_hash:
            raise CLIError(f"{fid}: config_hash 가 --config 와 다르다")

        rep_path = path.parent / "fit_report.json"
        pred_path = path.parent / "window_predictions.jsonl"
        for need in (rep_path, pred_path):
            if not need.is_file():
                raise CLIError(f"{fid}: {need.name} 가 없다 {need}. 대체 탐색하지 않는다 (U20)")
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        if rep.get("fit_id") != fid:
            raise CLIError(f"{rep_path}: fit_id {rep.get('fit_id')!r} ≠ manifest {fid}")
        inner_fold = int(man["folds"]["inner_fold"])
        cid = int(rep["config_id"])
        expect = fit_id(role=man["role"], cell=structure, outer_fold=outer_fold,
                        inner_fold=inner_fold, model_seed=int(man["model_seed"]),
                        config_id=cid, split_hash=split_hash, config_hash=cfg_hash)
        if expect != fid:
            raise CLIError(f"{fid}: fit_report config_id {cid} 로 다시 만든 fit_id 가 다르다 "
                           f"({expect}) — 보고서와 manifest 가 다른 fit 이다")

        fold = FIT.resolve_fold_subjects(folds, outer_fold, inner_fold)
        if sorted(man["fit_subjects"]) != sorted(fold.train):
            raise CLIError(f"{fid}: fit_subjects 가 folds.json 의 inner train 과 다르다")
        try:
            rows = read_jsonl(pred_path, "window_predictions")
        except ManifestError as exc:
            raise CLIError(f"{pred_path}: window_predictions 스키마 위반 — {exc}") from exc
        refs, probs = [], []
        for i, r in enumerate(rows):
            if r["fit_id"] != fid or r["cell"] != structure or \
                    int(r["model_seed"]) != int(man["model_seed"]):
                raise CLIError(f"{pred_path}:{i + 1}: fit_id/cell/seed 가 manifest 와 다르다")
            if r["scope"] != FIT.EVAL_ROLE[FIT.ROLE_INNER]:
                raise CLIError(f"{pred_path}:{i + 1}: scope {r['scope']!r} — inner validation "
                               "만 선택에 쓴다")
            if r["checkpoint_sha256"] != rep.get("checkpoint_sha256"):
                raise CLIError(f"{pred_path}:{i + 1}: checkpoint hash 가 fit_report 와 다르다")
            _window_index(r["run_key"], r["window_key"])
            if int(r["truth"]) != FIT.class_index(FIT.task_of(r["run_key"])):
                raise CLIError(f"{pred_path}:{i + 1}: truth 가 run_key 의 task 와 다르다")
            refs.append(FIT.WindowRef(
                window_key=r["window_key"], run_key=r["run_key"],
                canonical_subject=r["canonical_subject"], task=FIT.task_of(r["run_key"]),
                path=Path(""), sha256="", label=int(r["truth"])))
            probs.append(float(r["p_class1"]))
        got_subjects = {r["canonical_subject"] for r in rows}
        if got_subjects != set(fold.evaluate):
            raise CLIError(f"{fid}: 예측 subject 가 inner validation subject 와 다르다 "
                           f"(누락 {sorted(set(fold.evaluate) - got_subjects)[:3]}, "
                           f"여분 {sorted(got_subjects - set(fold.evaluate))[:3]})")
        try:
            run_probs = FIT.run_probabilities(refs, probs)
        except FIT.FitError as exc:
            raise CLIError(f"{pred_path}: {exc}") from exc
        loss = BL.inner_loss(run_probs)
        if abs(loss - float(rep["eval_loss"])) > SELECTION_LOSS_TOL:
            raise CLIError(f"{fid}: 창 예측으로 다시 계산한 inner 손실 {loss:.9f} ≠ "
                           f"fit_report eval_loss {float(rep['eval_loss']):.9f}")
        results.append(BL.ComparatorInner(
            structure=structure, config_id=cid, inner_fold=inner_fold,
            model_seed=int(man["model_seed"]), run_probs=run_probs,
            best_epoch=int(rep["best_epoch"])))
        inputs.append({"fit_id": fid, "config_id": cid, "inner_fold": inner_fold,
                       "fit_manifest": str(path), "fit_manifest_sha256": sha256_file(path),
                       "fit_report_sha256": sha256_file(rep_path),
                       "window_predictions_sha256": sha256_file(pred_path),
                       "checkpoint_sha256": rep.get("checkpoint_sha256"),
                       "best_epoch": int(rep["best_epoch"]), "inner_loss": loss})

    for field in ("code_hash", "env_hash", "source_hash"):
        values = sorted({json.loads(Path(i["fit_manifest"]).read_text(encoding="utf-8"))[field]
                         for i in inputs})
        if len(values) != 1:
            raise CLIError(f"inner fit 사이에 {field} 가 다르다 {[v[:12] for v in values]}")
    try:
        sel = BL.select_comparator(results, structure=structure)
    except BL.BaselineError as exc:
        raise CLIError(f"선택 실패: {exc}") from exc

    plan = [{**row, "outer_fold": outer_fold,
             "inner_fold": TPL.OUTER_FIT_INNER_FOLD,
             "cli": ["fit", "--cell", structure, "--outer-fold", str(outer_fold),
                     "--inner-fold", str(TPL.OUTER_FIT_INNER_FOLD),
                     "--config-id", str(sel.config_id),
                     "--epochs", str(sel.outer_epochs),
                     "--model-seed", str(row["model_seed"])]}
            for row in sel.outer_plan()]
    record = {
        "schema_version": SELECTION_SCHEMA, "structure": structure,
        "outer_fold": outer_fold, "split_hash": split_hash, "config_hash": cfg_hash,
        "selected_config_id": sel.config_id, "outer_epochs": sel.outer_epochs,
        "inner_loss": sel.loss, "inner_balanced_accuracy": sel.balanced_accuracy,
        "tie_rule": sel.tie_rule, "best_epochs": list(sel.best_epochs),
        "table": [{**r, "best_epochs": list(r["best_epochs"])} for r in sel.table],
        "outer_plan": plan,
        "rules": {"loss": "config 별 3 inner fold OOF 병합 subject 동일 가중 log loss",
                  "tie": f"차이 ≤ {TR.TIE_TOLERANCE} → OOF BA → 작은 config_id",
                  "outer_epochs": "선택 config 3 inner best epoch 중앙값 올림 (계획서 §7 baseline)",
                  "run_aggregation": "fitting.run_probabilities (train_fold inner 와 같은 함수)",
                  "status": "구현 선택 — 결정 14 가 세부를 정하지 않음"},
        "fit_code_hash": json.loads(Path(inputs[0]["fit_manifest"]).read_text(
            encoding="utf-8"))["code_hash"],
        "selector_code_hash": code_hash(sorted(Path(__file__).resolve().parent.glob("*.py"))),
        "inputs": sorted(inputs, key=lambda i: (i["config_id"], i["inner_fold"])),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SELECTION_OUTPUT).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"verdict": "pass", "structure": structure, "outer_fold": outer_fold,
            "selected_config_id": sel.config_id, "outer_epochs": sel.outer_epochs,
            "inner_loss": sel.loss, "tie_rule": sel.tie_rule, "n_inputs": len(inputs),
            "output": str(out_dir / SELECTION_OUTPUT)}


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
    from mobse.v2.train import MODEL_SEEDS

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
    locked = tuple(sorted(int(s) for s in MODEL_SEEDS))
    if tuple(int(s) for s in next(iter(seed_sets))) != locked:
        raise CLIError(f"fit 격자의 seed 집합 {sorted(seed_sets)[0]} 가 잠긴 "
                       f"train.model_seeds {locked} 와 다르다 (계획서 §5)")
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


REPORT_OUTPUTS = ("statistics.json",)
REPORT_SCHEMA = "wi06-statistics-0.1"
#: 주 contrast (97.5% family-wise CI) 와 보조 지표 (95% 기술적 CI). 계획서 §8.
PRIMARY_CONTRASTS = ("H1_A_minus_B", "H2_A_minus_C")
AUXILIARY_CONTRASTS = ("interaction",)


def _recompute_subject_scores(rows: Sequence[Mapping[str, Any]], *, threshold: float
                              ) -> Dict[str, Dict[str, float]]:
    """run_predictions 행에서 cell 별 subject ``b_i`` 를 다시 계산한다.

    evaluate 의 값을 그대로 믿지 않고 run 행만으로 재계산해 evaluation.json 과
    대조한다. 불완전한 subject 는 실패한다 (complete-case, 계획서 §8).

    Raises:
        CLIError: 임계 규칙 위반, 중복 run, 불완전 subject, cell 간 subject 불일치.
    """
    from mobse.v2 import evaluate as EV
    from mobse.v2 import fitting as FIT
    from mobse.v2.statistics import classify, subject_score

    got: Dict[str, Dict[str, Dict[str, bool]]] = {c: {} for c in EV.CELLS}
    for i, r in enumerate(rows):
        if r["cell"] not in got:
            raise CLIError(f"run_predictions:{i + 1}: 알 수 없는 cell {r['cell']!r}")
        if float(r["threshold"]) != threshold:
            raise CLIError(f"run_predictions:{i + 1}: threshold {r['threshold']} ≠ {threshold}")
        if int(r["prediction"]) != classify(float(r["ensemble_p"]), threshold):
            raise CLIError(f"run_predictions:{i + 1}: prediction 이 ensemble_p 의 "
                           "임계 판정과 다르다 (동일값은 class 1)")
        if (int(r["n_windows"]), int(r["n_seeds"])) != (EV.N_WINDOWS, EV.N_SEEDS):
            raise CLIError(f"run_predictions:{i + 1}: window×seed "
                           f"{r['n_windows']}×{r['n_seeds']} — 불완전 평균")
        task = FIT.task_of(r["run_key"])
        if task not in EV.CLASSIFICATION_TASKS:
            raise CLIError(f"run_predictions:{i + 1}: 분류 task 가 아니다: {task}")
        slot = got[r["cell"]].setdefault(r["canonical_subject"], {})
        if task in slot:
            raise CLIError(f"run_predictions:{i + 1}: {r['cell']}/"
                           f"{r['canonical_subject']}/{task} 중복")
        slot[task] = int(r["prediction"]) == int(r["truth"])

    scores: Dict[str, Dict[str, float]] = {}
    for cell, by_subject in got.items():
        bad = sorted(s for s, t in by_subject.items()
                     if set(t) != set(EV.CLASSIFICATION_TASKS))
        if bad or not by_subject:
            raise CLIError(f"cell {cell}: 두 task 를 모두 갖지 않은 subject {bad[:5]} "
                           f"또는 행 없음 — complete-case 만 집계한다")
        scores[cell] = {s: subject_score(t[EV.CLASSIFICATION_TASKS[0]],
                                         t[EV.CLASSIFICATION_TASKS[1]])
                        for s, t in sorted(by_subject.items())}
    ref = set(scores[EV.CELLS[0]])
    for cell in EV.CELLS[1:]:
        if set(scores[cell]) != ref:
            raise CLIError(f"cell {cell} 의 subject 집합이 {EV.CELLS[0]} 와 다르다 — paired 불가")
    return scores


def run_report(paths: Dict[str, Any]) -> Dict[str, Any]:
    """evaluate 산출물로 paired bootstrap 구간과 G3 정합성 판정을 낸다 (계획서 §8·§10).

    * run 행으로 subject ``b_i`` 를 재계산해 ``evaluation.json`` 과 정확히 대조한다.
    * seed 9001·10,000회 group 재표집 index 를 **한 번** 만들어 모든 cell·contrast 에
      공유한다. 주 contrast 2개는 97.5% CI, interaction·cell BA 는 95% 기술적 CI.
    * 판정은 완전성·정합성뿐이다. **유의성은 실행 gate 가 아니다** — 구간 해석은
      `statistics.interpret` 문자열로만 기록한다.

    Raises:
        CLIError: 입력 무결성·정합성 위반 또는 덮어쓰기 시도.
    """
    from mobse.v2 import evaluate as EV
    from mobse.v2 import statistics as ST
    from mobse.v2.manifests import code_hash, read_jsonl, sha256_file

    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc
    cfg_hash = config_hash(cfg)

    out_dir = Path(paths["output_dir"])
    for name in REPORT_OUTPUTS:
        if (out_dir / name).exists():
            raise CLIError(f"이미 존재한다: {out_dir / name}. 같은 release 결과를 "
                           "덮어쓰지 않는다 (지침서 §2)")

    ev_path = Path(paths["evaluation"])
    evaluation = json.loads(ev_path.read_text(encoding="utf-8"))
    if evaluation.get("config_hash") != cfg_hash:
        raise CLIError("evaluation.json 의 config_hash 가 주어진 config 와 다르다")
    pred_path = Path(paths["predictions"])
    pred_sha = sha256_file(pred_path)
    recorded = evaluation.get("run_predictions", {}).get("sha256")
    if pred_sha != recorded:
        raise CLIError(f"run_predictions sha256 {pred_sha[:12]} 가 evaluation.json 기록 "
                       f"{str(recorded)[:12]} 와 다르다 — 같은 evaluate 산출물이 아니다")
    try:
        rows = read_jsonl(pred_path, "run_predictions")
    except ManifestError as exc:
        raise CLIError(f"{pred_path}: run_predictions 스키마 위반 — {exc}") from exc

    threshold = float(cfg["stats.threshold"])
    scores = _recompute_subject_scores(rows, threshold=threshold)
    if {c: dict(v) for c, v in scores.items()} != evaluation.get("subject_scores"):
        raise CLIError("run 행으로 재계산한 subject b_i 가 evaluation.json 과 다르다")

    try:
        subj_rows = read_jsonl(Path(paths["subjects"]), "subjects")
    except ManifestError as exc:
        raise CLIError(f"subjects 스키마 위반 — {exc}") from exc
    group_of = {r["canonical_subject"]: r["group_id"] for r in subj_rows}
    eligible = {r["canonical_subject"] for r in subj_rows if r["eligible"]}
    subjects = sorted(scores[EV.CELLS[0]])
    missing = [s for s in subjects if s not in group_of]
    if missing:
        raise CLIError(f"subjects.jsonl 에 group 이 없는 subject: {missing[:5]}")
    ineligible = [s for s in subjects if s not in eligible]
    if ineligible:
        raise CLIError(f"부적격 subject 가 평가에 들어 있다: {ineligible[:5]}")
    if len(subjects) != int(evaluation.get("counts", {}).get("subjects", -1)):
        raise CLIError("subject 수가 evaluation.json counts 와 다르다")

    seed, n_boot = int(cfg["stats.bootstrap_seed"]), int(cfg["stats.n_bootstrap"])
    fw = tuple(float(x) for x in cfg["stats.familywise_pct"])
    nom = tuple(float(x) for x in cfg["stats.nominal_pct"])
    delta = float(cfg["stats.delta"])
    idx = ST.bootstrap_indices(group_of, subjects, seed=seed, n_boot=n_boot)

    def _ci(values: Mapping[str, float], pct: Tuple[float, float]) -> Dict[str, Any]:
        res = ST.paired_bootstrap({s: values[s] for s in subjects}, group_of,
                                  indices=idx, seed=seed, n_boot=n_boot, pct=pct)
        return {**res.as_dict(), "interpretation": ST.interpret(res, delta=delta),
                "lower_gt_0": res.lo > 0, "lower_gt_delta": res.lo > delta}

    diffs = {
        "H1_A_minus_B": {s: scores["A"][s] - scores["B"][s] for s in subjects},
        "H2_A_minus_C": {s: scores["A"][s] - scores["C"][s] for s in subjects},
        "interaction": {s: (scores["A"][s] - scores["B"][s]) -
                           (scores["C"][s] - scores["D"][s]) for s in subjects},
    }
    if {k: dict(sorted(v.items())) for k, v in diffs.items()} != \
            evaluation.get("subject_differences"):
        raise CLIError("재계산한 subject 차이가 evaluation.json 과 다르다")

    primary = {k: _ci(diffs[k], fw) for k in PRIMARY_CONTRASTS}
    auxiliary = {k: _ci(diffs[k], nom) for k in AUXILIARY_CONTRASTS}
    cell_ba = {c: _ci(scores[c], nom) for c in EV.CELLS}
    for c in EV.CELLS:
        if abs(cell_ba[c]["point_estimate"] -
               float(evaluation["balanced_accuracy"][c])) > 1e-12:
            raise CLIError(f"cell {c} BA 가 evaluation.json 과 다르다")

    both = all(primary[k]["lower_gt_0"] for k in PRIMARY_CONTRASTS)
    summary = {
        "schema_version": REPORT_SCHEMA,
        "config_hash": cfg_hash, "split_hash": evaluation.get("split_hash"),
        "fit_code_hash": evaluation.get("fit_code_hash"),
        "evaluator_code_hash": evaluation.get("evaluator_code_hash"),
        "report_code_hash": code_hash(sorted(Path(__file__).resolve().parent.glob("*.py"))),
        "bootstrap": {"seed": seed, "n_boot": n_boot, "shared_across_cells": True,
                      "unit": "group", "n_subjects": len(subjects),
                      "n_groups": len({group_of[s] for s in subjects})},
        "delta": delta, "threshold": threshold,
        "primary_contrasts": primary, "auxiliary_contrasts": auxiliary,
        "cell_balanced_accuracy": cell_ba,
        "both_primary_lower_gt_0": both,
        "g3_verdict": {"completeness_and_consistency": "pass",
                       "significance_is_gate": False,
                       "checks": ["run_predictions sha256 = evaluation.json 기록",
                                  "run 행 재계산 b_i = evaluation.json subject_scores",
                                  "재계산 subject 차이 = evaluation.json",
                                  "cell BA = evaluation.json",
                                  "complete-case, cell 간 subject 동일, 부적격 0"]},
        "inputs": {"config": str(paths["config"]),
                   "evaluation": {"path": str(ev_path), "sha256": sha256_file(ev_path)},
                   "run_predictions": {"path": str(pred_path), "sha256": pred_sha,
                                       "n_rows": len(rows)},
                   "subjects": {"path": str(paths["subjects"]),
                                "sha256": sha256_file(Path(paths["subjects"]))}},
        "caveat": "내부 OOF bootstrap 은 고정된 학습 결과에 조건부이며 training-set "
                  "변동을 완전히 반영하지 않는다 (계획서 §8)",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "statistics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"verdict": "pass", "n_subjects": len(subjects),
            "primary": {k: [v["point_estimate"], v["ci_lo"], v["ci_hi"]]
                        for k, v in primary.items()},
            "both_primary_lower_gt_0": both, "output_dir": str(out_dir)}


PREPARE_OUTPUTS = ("windows.jsonl", "subjects.jsonl", "exclusions.jsonl",
                   "cohort_summary.json", "prepare_report.json")

#: 받는 WI-02 추출 manifest 판. 0.2 = P9 band-pass 동시 회귀·P10 DOF 적용판.
EXTRACT_SCHEMA_VERSION = "wi02-extract-0.2"


def _check_extract_header(header: Mapping[str, Any], path: str,
                          cfg: Mapping[str, Any]) -> None:
    """추출 manifest 헤더가 잠긴 config·코드 상수와 같은 조건에서 나왔는지 본다.

    헤더에 기록만 되고 대조되지 않는 값이 없게 한다 (E21·E22 재발 방지).

    Raises:
        CLIError: 판·분석 구간·통과대역·dry-run·atlas 해시 중 하나라도 어긋나면.
    """
    from mobse.v2 import extract as EX

    problems: List[str] = []
    if header.get("schema_version") != EXTRACT_SCHEMA_VERSION:
        problems.append(f"schema_version {header.get('schema_version')!r} != "
                        f"{EXTRACT_SCHEMA_VERSION!r}")
    interval = [float(x) for x in header.get("analysis_interval_sec") or []]
    want = [float(cfg["timing.analysis_start_s"]), float(cfg["timing.analysis_end_s"])]
    if interval != want:
        problems.append(f"analysis_interval_sec {interval} != config {want}")
    band = [float(x) for x in header.get("bandpass_hz") or []]
    if band != [EX.BANDPASS_LOW_HZ, EX.BANDPASS_HIGH_HZ]:
        problems.append(f"bandpass_hz {band} != 코드 "
                        f"{[EX.BANDPASS_LOW_HZ, EX.BANDPASS_HIGH_HZ]}")
    if header.get("dry_run") is not False:
        problems.append(f"dry_run={header.get('dry_run')!r} — 실추출 manifest 가 아니다")
    atlas = str(header.get("atlas_sha256") or "")
    if len(atlas) != 64 or any(c not in "0123456789abcdef" for c in atlas):
        problems.append("atlas_sha256 가 SHA256 hex 가 아니다")
    if not header.get("dataset"):
        problems.append("dataset 없음")
    if problems:
        raise CLIError(f"{path}: 추출 manifest 헤더가 잠긴 조건과 다르다 — "
                       + "; ".join(problems))


def run_prepare(paths: Dict[str, Any]) -> Dict[str, Any]:
    """WI-02 추출 manifest 셋을 windows·subjects·exclusions 로 접는다 (WI-02·WI-03).

    ``scripts/h197/12_build_windows_manifest.py`` 와 ``15_build_subjects.py`` 가
    하던 일을 같은 라이브러리 함수로 한 번에 한다. 새 계산은 없다 — 같은 입력에서
    두 스크립트와 바이트 단위로 같은 ``windows.jsonl``·``subjects.jsonl``·
    ``exclusions.jsonl`` 을 내야 한다 (h197 대조, 보고서 부록 AE).

    * 한 dataset 의 세 task(두 target + rest)를 정확히 하나씩 요구한다. rest 가
      빠지면 전원이 부적격이 되므로 조용히 진행하지 않는다.
    * 창은 target task 만, ``cohort.TARGET_TASKS`` 순서로 만든다 (인자 순서 무관).
    * 적격 subject 마다 두 task × 4 창이 모두 있는지 대조한다.

    Raises:
        CLIError: 헤더·task 구성·dataset·atlas 불일치, 창 누락, 덮어쓰기 시도.
    """
    from mobse.v2 import cohort as CO
    from mobse.v2.labels import LabelError, build_window_records
    from mobse.v2.manifests import sha256_file, write_jsonl
    from mobse.v2.preprocess import WINDOW_STARTS

    try:
        cfg = load_config(Path(paths["config"]))
    except ConfigError as exc:
        raise CLIError(f"config 검증 실패: {exc}") from exc
    cfg_hash = config_hash(cfg)

    out_dir = Path(paths["output_dir"])
    for name in PREPARE_OUTPUTS:
        if (out_dir / name).exists():
            raise CLIError(f"이미 존재한다: {out_dir / name}. 같은 release 결과를 "
                           "덮어쓰지 않는다 (지침서 §2)")

    by_task: Dict[str, Tuple[Mapping[str, Any], List[Dict[str, Any]], str]] = {}
    for p in _as_list(paths["extract_manifests"]):
        try:
            header, runs = CO.read_extract_manifest(Path(p))
        except CO.CohortError as exc:
            raise CLIError(str(exc)) from exc
        task = str(header.get("task") or "")
        if task not in CO.REQUIRED_TASKS:
            raise CLIError(f"{p}: task {task!r} 는 허용되지 않는다. "
                           f"허용: {list(CO.REQUIRED_TASKS)}")
        if task in by_task:
            raise CLIError(f"task {task!r} manifest 가 두 번 주어졌다: "
                           f"{by_task[task][2]}, {p}")
        _check_extract_header(header, p, cfg)
        by_task[task] = (header, runs, p)

    missing = [t for t in CO.REQUIRED_TASKS if t not in by_task]
    if missing:
        raise CLIError(f"task manifest 누락: {missing}. 적격 기준(계획서 §3.3)이 세 "
                       "task 를 모두 요구하므로 빠진 채로 진행하지 않는다")
    datasets = sorted({str(by_task[t][0]["dataset"]) for t in CO.REQUIRED_TASKS})
    if len(datasets) != 1:
        raise CLIError(f"dataset 이 섞였다: {datasets}. prepare 는 dataset 단위다")
    atlases = sorted({str(by_task[t][0]["atlas_sha256"]) for t in CO.REQUIRED_TASKS})
    if len(atlases) != 1:
        raise CLIError(f"task 마다 atlas_sha256 가 다르다: {[a[:12] for a in atlases]}")

    windows: List[Dict[str, Any]] = []
    for task in CO.TARGET_TASKS:
        header, runs, p = by_task[task]
        try:
            windows.extend(build_window_records(header, runs))
        except LabelError as exc:
            raise CLIError(f"{p}: {exc}") from exc

    try:
        subjects = CO.build_subjects([by_task[t][:2] for t in CO.REQUIRED_TASKS])
    except CO.CohortError as exc:
        raise CLIError(f"코호트 구성 실패: {exc}") from exc
    records = CO.subjects_to_records(subjects)
    exclusions = CO.exclusion_records(subjects)

    subject_of = {str(r["run_key"]): str(r["canonical_subject"])
                  for t in CO.TARGET_TASKS for r in by_task[t][1]}
    per_subject: Dict[str, int] = {}
    for w in windows:
        s = subject_of.get(str(w["run_key"]))
        if s is None:
            raise CLIError(f"창 {w['window_key']} 의 run 이 manifest 에 없다")
        per_subject[s] = per_subject.get(s, 0) + 1
    need = len(CO.TARGET_TASKS) * len(WINDOW_STARTS)
    short = sorted(r["canonical_subject"] for r in records
                   if r["eligible"] and per_subject.get(r["canonical_subject"], 0) != need)
    if short:
        raise CLIError(f"적격 subject {len(short)}명의 창이 {need}개가 아니다: {short[:5]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        w_art = write_jsonl(out_dir / "windows.jsonl", "windows", windows)
        s_art = write_jsonl(out_dir / "subjects.jsonl", "subjects", records)
        e_art = (write_jsonl(out_dir / "exclusions.jsonl", "exclusions", exclusions)
                 if exclusions else None)
    except ManifestError as exc:
        raise CLIError(f"기록 실패: {exc}") from exc

    summary: Dict[str, Any] = CO.summarize(subjects)
    summary["subjects_artifact"] = s_art
    if e_art:
        summary["exclusions_artifact"] = e_art
    summary["dataset"] = datasets[0]
    summary["source_manifests"] = [by_task[t][2] for t in CO.REQUIRED_TASKS]
    (out_dir / "cohort_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    n_eligible = sum(1 for r in records if r["eligible"])
    report = {
        "schema_version": "wi06-prepare-0.1",
        "config_hash": cfg_hash,
        "dataset": datasets[0],
        "atlas_sha256": atlases[0],
        "inputs": {t: {"path": by_task[t][2], "sha256": sha256_file(Path(by_task[t][2])),
                       "n_runs": len(by_task[t][1]),
                       "n_ok": sum(1 for r in by_task[t][1] if r.get("status") == "ok")}
                   for t in CO.REQUIRED_TASKS},
        "outputs": {"windows": w_art, "subjects": s_art, "exclusions": e_art},
        "n_subjects": len(records), "n_eligible": n_eligible,
        "n_windows": len(windows),
        "checks": ["헤더 schema·분석 구간·통과대역·dry_run·atlas = 잠긴 조건",
                   "세 task 각 하나, dataset·atlas 단일",
                   f"적격 subject 마다 창 {need}개"],
        "equivalent_scripts": ["scripts/h197/12_build_windows_manifest.py",
                               "scripts/h197/15_build_subjects.py"],
    }
    (out_dir / "prepare_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"verdict": "pass", "dataset": datasets[0], "n_subjects": len(records),
            "n_eligible": n_eligible, "n_windows": len(windows),
            "windows_sha256": w_art["sha256"], "subjects_sha256": s_art["sha256"],
            "exclusions_sha256": e_art["sha256"] if e_art else None,
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

    if args.command == "fit-s":
        result = run_fit_s(paths, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "select-comparator":
        result = run_select_comparator(paths, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "evaluate":
        result = run_evaluate(paths, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "report":
        result = run_report(paths)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    if args.command == "prepare":
        result = run_prepare(paths)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verdict"] == "pass" else 1

    raise CLIError(f"본체 없는 하위 명령: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
