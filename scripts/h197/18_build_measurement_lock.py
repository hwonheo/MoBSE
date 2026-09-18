#!/usr/bin/env python3
"""측정 잠금 파일을 만든다 — 지침서 WI-03 / gate G1.

h197 의 자료 디렉터리와 저장소를 함께 읽어 `locks/measurement_lock.json` 을
만든다. 코호트·분할·창 manifest·atlas 는 자료 쪽, 계획서·지침서·config·코드는
저장소 쪽이다.

Usage:
    python scripts/h197/18_build_measurement_lock.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset \
        --repo-root . \
        --release results/redesign_v1/20260917_3c458d507e82_nocfg \
        [--overwrite]

기존 잠금 파일은 `--overwrite` 없이는 덮어쓰지 않는다. 덮어쓸 때는 구본을
`locks/superseded/` 로 옮기고 새 잠금에 `supersedes` 를 남긴다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import locks as L                                    # noqa: E402
from mobse.v2.config import config_hash, load_config               # noqa: E402
from mobse.v2.manifests import code_hash, sha256_file              # noqa: E402

TASKS = ("emomatching", "workingmemory", "restingstate")

COHORTS = {
    "piop1": {
        "dataset": "ds002785",
        "role": "primary (pilot + main pool)",
        "deriv": "derivatives_v2",
        "cohort_dir": "derivatives_v2/cohort_piop1",
        "windows": "derivatives_v2/windows_piop1.jsonl",
        "splits": "derivatives_v2/splits_piop1_p7",
    },
    "piop2": {
        "dataset": "ds002790",
        "role": "external hold-out (계획서 §9)",
        "deriv": "derivatives_v2_piop2",
        "cohort_dir": "derivatives_v2_piop2/cohort_piop2",
        "windows": "derivatives_v2_piop2/windows_piop2.jsonl",
        "splits": None,
    },
}


def _count_status(path: Path) -> Dict[str, int]:
    """manifest 의 run status 분포."""
    counts: Dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("record_type") == "run":
            counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    return dict(sorted(counts.items()))


def _atlas_record(data_root: Path, manifest: Path) -> Dict[str, Any]:
    """manifest 헤더가 가리키는 atlas 를 잠금 레코드로 만든다."""
    header = json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])
    atlas = Path(header["atlas"])
    rec = L.file_record(atlas, base=data_root,
                        atlas_sha256_in_header=header["atlas_sha256"],
                        space=header["space"])
    if rec["sha256"] != header["atlas_sha256"]:
        raise SystemExit(f"atlas 해시가 manifest 헤더와 다르다: {atlas}")
    return rec


def build_cohort(data_root: Path, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """코호트 하나의 잠금 절을 만든다."""
    deriv = data_root / spec["deriv"]
    manifests: Dict[str, Any] = {}
    for task in TASKS:
        p = deriv / f"wi02_{spec['dataset']}_{task}.jsonl"
        counts = _count_status(p)
        manifests[task] = L.file_record(p, base=data_root, status_counts=counts,
                                        n_runs=sum(counts.values()),
                                        n_ok=counts.get("ok", 0))

    cohort_dir = data_root / spec["cohort_dir"]
    summary = json.loads((cohort_dir / "cohort_summary.json").read_text(encoding="utf-8"))
    subjects_path = cohort_dir / "subjects.jsonl"
    eligible = [json.loads(l)["canonical_subject"]
                for l in subjects_path.read_text(encoding="utf-8").splitlines()
                if l.strip() and json.loads(l).get("eligible")]

    windows_path = data_root / spec["windows"]
    n_windows = sum(1 for l in windows_path.read_text(encoding="utf-8").splitlines() if l.strip())

    out: Dict[str, Any] = {
        "dataset": spec["dataset"],
        "role": spec["role"],
        "n_subjects": summary["n_subjects"],
        "n_eligible": summary["n_eligible"],
        "required_tasks": list(summary["required_tasks"]),
        "rule_version": summary["rule_version"],
        "group_id_policy": summary["group_id_policy"],
        "manifests": manifests,
        "atlas": _atlas_record(data_root, deriv / f"wi02_{spec['dataset']}_restingstate.jsonl"),
        "subjects": L.file_record(subjects_path, base=data_root,
                                  n_records=summary["subjects_artifact"]["n_records"],
                                  n_eligible=len(eligible)),
        "exclusions": L.file_record(cohort_dir / "exclusions.jsonl", base=data_root,
                                    n_records=summary["exclusions_artifact"]["n_records"]),
        "cohort_summary": L.file_record(cohort_dir / "cohort_summary.json", base=data_root),
        "windows": L.file_record(windows_path, base=data_root, n_records=n_windows),
        "folds": None,
    }

    if len(eligible) != summary["n_eligible"]:
        raise SystemExit(f"{name}: subjects.jsonl 의 적격 수와 summary 가 다르다")

    if spec["splits"] is None:
        out["no_split_reason"] = (
            "계획서 §9 — PIOP2 는 held-out 외부 코호트다. fold 를 만들지 않는다.")
        return out

    folds_path = data_root / spec["splits"] / "folds.json"
    folds = json.loads(folds_path.read_text(encoding="utf-8"))
    inv = L.fold_invariants(folds, eligible)
    bad = L.failed_invariants(inv)
    if bad:
        raise SystemExit(f"{name}: 잠글 수 없다 — 불변식 실패 {bad}")
    out["folds"] = L.file_record(
        folds_path, base=data_root,
        split_hash=folds["split_hash"], config_hash=folds["config_hash"],
        seeds=folds["seeds"], invariants=inv,
        subjects_manifest_sha256=folds["subjects_manifest_sha256"])
    return out


def build_environment(repo_root: Path) -> Dict[str, Any]:
    """계획서·지침서·config·코드 절."""
    docs = repo_root / "docs/experiments"
    cfg_dir = repo_root / "configs/redesign_v1"
    module_paths = sorted((repo_root / "mobse/v2").glob("*.py"))

    configs: Dict[str, Any] = {}
    for p in sorted(cfg_dir.glob("*.yaml")):
        configs[p.stem] = L.file_record(p, base=repo_root,
                                        config_hash=config_hash(load_config(p)))

    return {
        "protocol": L.file_record(docs / "mobse_redesign_protocol_2026-09-17.md",
                                  base=repo_root),
        "instructions": L.file_record(docs / "mobse_redesign_work_instructions_2026-09-17.md",
                                      base=repo_root),
        "configs": configs,
        "code": {
            "code_hash": code_hash(module_paths),
            "modules": {p.name: sha256_file(p) for p in module_paths},
        },
    }


CHANGE_POLICY = {
    "why": ("개정 P7 로 적격자가 153→157 로 4명 늘자 pilot 31명 중 24명이 교체되고 "
            "공통 main pool subject 의 outer fold 가 65% 바뀌었다(보고서 부록 U.3.1). "
            "seed 를 고정해도 그룹 목록이 바뀌면 배정이 전부 바뀐다."),
    "rules": [
        "잠긴 항목이 하나라도 바뀌면 이 잠금은 무효다. 새 잠금 파일을 만들고 "
        "supersedes 에 구 lock_hash 와 변경 사유를 남긴다. 구 파일은 지우지 않는다.",
        "잠금이 무효가 되면 그 잠금에 의존해 적합된 산출물은 **다시 만든다.** "
        "부분 갱신하지 않는다.",
        "main OOF 평가를 한 번이라도 수행한 뒤에는 δ 와 분석 N 을 바꾸지 않는다 (계획서 §8).",
        "pilot 은 모든 main/final fit 에서 제외된다. verify 가 매번 재확인한다.",
        "PIOP2 는 fold 를 만들지 않는다. 외부 평가 전에 fit·선택·calibration 에 쓰지 않는다 (§9).",
    ],
    "verify_command": "python scripts/h197/19_verify_measurement_lock.py --data-root <...> --repo-root <...> --release <...>",
}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--release", required=True, type=Path,
                    help="repo-root 기준 release 디렉터리")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--reason", default=None,
                    help="구 잠금을 무효화한 사유. --overwrite 시 필수다")
    args = ap.parse_args(argv[1:])

    data_root = args.data_root.resolve()
    repo_root = args.repo_root.resolve()
    release = (repo_root / args.release).resolve()
    out_path = release / "locks" / "measurement_lock.json"

    prior = None
    if out_path.exists():
        if not args.overwrite:
            raise SystemExit(f"이미 존재한다: {out_path}. --overwrite 를 명시하라")
        if not args.reason:
            raise SystemExit(
                "--overwrite 에는 --reason 이 필요하다. 변경 정책이 '새 잠금에 "
                "supersedes 와 사유를 남긴다'고 정한다 — 사유 없는 무효화는 없다")
        prior = json.loads(out_path.read_text(encoding="utf-8"))

    body: Dict[str, Any] = {
        "schema_version": L.SCHEMA_VERSION,
        "release_id": release.name,
        "locked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gate": "G1 Measurement lock",
        "work_instruction": "WI-03",
        "roots": {"data_root": str(data_root), "repo_root": "<repository root>"},
        "cohorts": {name: build_cohort(data_root, name, spec)
                    for name, spec in COHORTS.items()},
        "environment": build_environment(repo_root),
        "change_policy": CHANGE_POLICY,
    }

    p1 = body["cohorts"]["piop1"]
    body["endpoint"] = {
        "statistical_unit": "subject (group = subject, 개정 P4)",
        "n_primary_oof": p1["folds"]["invariants"]["n_main_pool"],
        "n_pilot_excluded": p1["folds"]["invariants"]["n_pilot"],
        "n_external": body["cohorts"]["piop2"]["n_eligible"],
        "delta": 0.02,
        "bootstrap": {"seed": 9001, "n_boot": 10000,
                      "primary_pct": [1.25, 98.75], "secondary_pct": [2.5, 97.5]},
        "note": ("주 contrast 의 N 은 pooled out-of-fold main pool 이다. "
                 "outer test 한 fold 의 25~26 이 아니다. 계획서 §8 이 "
                 "'window·seed·fold 수를 N 으로 세지 않는다'고 정한다."),
    }
    n = body["endpoint"]["n_primary_oof"]
    body["wi07_completion_targets"] = {
        "window_prediction_rows": n * 2 * 4 * 3 * 4,
        "run_prediction_rows": n * 2 * 4,
        "checkpoints": 4 * 5 * 3,
        "formula": f"{n} subjects x 2 tasks x 4 windows x 3 seeds x 4 cells",
    }

    if prior is not None:
        body["supersedes"] = {
            "lock_hash": prior.get("lock_hash"),
            "locked_at_utc": prior.get("locked_at_utc"),
            "reason": args.reason,
        }
        sup = out_path.parent / "superseded"
        sup.mkdir(parents=True, exist_ok=True)
        shutil.move(str(out_path),
                    str(sup / f"measurement_lock_{prior.get('locked_at_utc','unknown')}.json"))

    body["lock_hash"] = L.lock_hash(body)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(json.dumps({
        "lock": str(out_path),
        "lock_hash": body["lock_hash"],
        "n_primary_oof": body["endpoint"]["n_primary_oof"],
        "n_external": body["endpoint"]["n_external"],
        "split_hash": p1["folds"]["split_hash"],
        "code_hash": body["environment"]["code"]["code_hash"][:16],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
