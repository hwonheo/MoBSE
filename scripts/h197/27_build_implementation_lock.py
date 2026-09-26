#!/usr/bin/env python3
"""구현 잠금 파일을 만들거나 검증한다 — 지침서 WI-06 / gate G2 (결정 21 명세 4).

WI-06 출력 문장 "runnable CLI와 실제 `--help`, acceptance 결과, 환경 lock,
code/config hashes, `locks/implementation_lock.json`" 을 필드로 옮긴다.

- ``environment``: python·platform·torch·CUDA·GPU 이름, ``pip freeze`` 전체와 sha256
- ``code``: ``mobse/v2/*.py`` code_hash (측정 잠금과 같은 정의) + 모듈별 sha256
- ``configs``: ``configs/redesign_v1/*.yaml`` 파일 sha256 + config_hash
- ``cli``: 하위 명령 목록과 최상위·하위 명령별 실제 ``--help`` 출력 (COLUMNS=100 고정) 과 sha256
- ``acceptance``: T01–T16 대응표 (release ``reports/acceptance_map_t01_t16_v2.json``) +
  pytest junit (``--pytest-junit``) 의 합계와, 대응표가 이름 붙인 시험이 전부 통과했는지
- ``pilot_end_to_end``: gate evidence ``decision21_pilot_e2e_rev69.data_root_outputs`` 의
  sha256 을 data root 에서 **다시 재어** 대조 (하나라도 다르면 만들지 않는다) +
  ``run_all.log`` 의 ``ALL_RC=0``
- ``measurement_lock``: 측정 잠금 lock_hash 와 파일 sha256 (참조만)
- ``t10_gpu_reload``: 이 판에서는 하지 않음 (구현 선택, 기록)

구현 선택 (표시): 생성과 검증을 한 스크립트에 둔다 (``--verify``). 검증은 git HEAD 를
대조하지 않는다 — 잠금 파일을 커밋하면 HEAD 가 바뀌기 때문이다 (기록만).
pytest 는 이 스크립트가 돌리지 않는다 — 마감 1단계를 ``--junitxml`` 로 돌린 결과를 받는다.

Usage:
    python scripts/h197/27_build_implementation_lock.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset --repo-root . \
        --release results/redesign_v1/20260917_3c458d507e82_nocfg \
        --pytest-junit <data root 아래 junit xml> --reason "..."
    python scripts/h197/27_build_implementation_lock.py --verify \
        --data-root ... --repo-root . --release ...

기존 잠금 파일은 덮어쓰지 않는다 (``--overwrite`` 없음 — 새 판이 필요하면 이 스크립트를 고친다).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import locks as L                                    # noqa: E402
from mobse.v2.cli import SUBCOMMANDS                               # noqa: E402
from mobse.v2.config import config_hash, load_config               # noqa: E402
from mobse.v2.manifests import code_hash, sha256_file              # noqa: E402

SCHEMA = "implementation_lock_v1"
LOCK_NAME = "implementation_lock.json"
MAP_REL = "reports/acceptance_map_t01_t16_v2.json"
E2E_BLOCK = "decision21_pilot_e2e_rev69"
HELP_COLUMNS = "100"


def sha256_text(text: str) -> str:
    """문자열 UTF-8 sha256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_junit(path: Path) -> Dict[str, Any]:
    """pytest junit xml 을 (합계, 시험별 결과) 로 읽는다.

    시험별 키는 ``tests/v2/<file>.py::<name>`` (parametrize 괄호는 뗀다),
    값은 그 이름의 모든 경우 결과 집합 {"passed","skipped","failed"}.
    """
    root = ET.parse(path).getroot()
    counts = {"passed": 0, "skipped": 0, "failed": 0}
    outcomes: Dict[str, set] = {}
    for tc in root.iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            res = "failed"
        elif tc.find("skipped") is not None:
            res = "skipped"
        else:
            res = "passed"
        counts[res] += 1
        cls = tc.get("classname", "")
        name = tc.get("name", "").split("[", 1)[0]
        key = cls.replace(".", "/") + ".py::" + name
        outcomes.setdefault(key, set()).add(res)
    return {"counts": counts, "outcomes": outcomes}


def named_test_results(amap: Mapping[str, Any],
                       outcomes: Mapping[str, set]) -> Dict[str, Any]:
    """대응표 항목마다 이름 붙은 시험의 결과. 빠진 시험·실패·skip 은 따로 센다."""
    per_item: Dict[str, Any] = {}
    missing: List[str] = []
    not_passed: List[str] = []
    for item in amap["items"]:
        tests = list(item["tests"])
        bad = []
        for t in tests:
            res = outcomes.get(t)
            if res is None:
                missing.append(t)
                bad.append(t)
            elif res != {"passed"}:
                not_passed.append(t)
                bad.append(t)
        per_item[item["id"]] = {"coverage": item["coverage"], "n_tests": len(tests),
                                "all_passed": not bad}
    return {"per_item": per_item, "missing": sorted(set(missing)),
            "not_passed": sorted(set(not_passed))}


def cli_help(repo_root: Path) -> Dict[str, Any]:
    """최상위와 하위 명령별 실제 ``--help`` 출력. 폭은 COLUMNS 로 고정한다."""
    env = dict(os.environ, COLUMNS=HELP_COLUMNS, PYTHONDONTWRITEBYTECODE="1")
    out: Dict[str, Any] = {}
    for sub in ("",) + tuple(SUBCOMMANDS):
        argv = [sys.executable, "-B", "-m", "mobse.v2.cli"] + ([sub] if sub else []) + ["--help"]
        proc = subprocess.run(argv, cwd=repo_root, env=env, capture_output=True,
                              text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(f"--help 실패 ({sub or '<top>'}): rc={proc.returncode} {proc.stderr[-300:]}")
        out[sub or "<top>"] = {"sha256": sha256_text(proc.stdout), "text": proc.stdout}
    return {"columns": int(HELP_COLUMNS), "subcommands": list(SUBCOMMANDS), "help": out}


def environment() -> Dict[str, Any]:
    """실행 환경. torch 가 없으면 실패한다 (구현 잠금은 학습 환경을 기록해야 한다)."""
    import torch  # noqa: PLC0415
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"],
                            capture_output=True, text=True, check=True).stdout
    lines = sorted(ln for ln in freeze.splitlines() if ln.strip())
    gpus = ([torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
            if torch.cuda.is_available() else [])
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cuda_available": bool(torch.cuda.is_available()),
        "cudnn": torch.backends.cudnn.version() if torch.cuda.is_available() else None,
        "gpus": gpus,
        "pip_freeze": {"sha256": sha256_text("\n".join(lines) + "\n"),
                       "n": len(lines), "lines": lines},
    }


def code_and_configs(repo_root: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """code_hash (측정 잠금과 같은 정의) 와 config 기록."""
    module_paths = sorted((repo_root / L.CODE_DIR).glob("*.py"))
    code = {"code_hash": code_hash(module_paths),
            "modules": {p.name: sha256_file(p) for p in module_paths}}
    configs: Dict[str, Any] = {}
    for p in sorted((repo_root / "configs/redesign_v1").glob("*.yaml")):
        configs[p.stem] = L.file_record(p, base=repo_root,
                                        config_hash=config_hash(load_config(p)))
    return code, configs


def pilot_e2e(data_root: Path, gate: Mapping[str, Any]) -> Dict[str, Any]:
    """gate 가 기록한 pilot end-to-end 산출물 sha 를 다시 잰다. 다르면 멈춘다."""
    block = gate[E2E_BLOCK]
    expected: Mapping[str, str] = block["data_root_outputs"]
    measured: Dict[str, str] = {}
    bad = []
    for rel, sha in sorted(expected.items()):
        p = data_root / rel
        if not p.is_file():
            bad.append(f"없음: {rel}")
            continue
        measured[rel] = sha256_file(p)
        if measured[rel] != sha:
            bad.append(f"sha 다름: {rel}")
    run_dir = data_root / Path(sorted(expected)[0]).parts[0] / Path(sorted(expected)[0]).parts[1]
    run_all = run_dir / "run_all.log"
    all_rc0 = run_all.is_file() and "ALL_RC=0" in run_all.read_text(encoding="utf-8", errors="replace")
    if not all_rc0:
        bad.append(f"ALL_RC=0 없음: {run_all}")
    if bad:
        raise SystemExit("pilot end-to-end 대조 실패 — 잠금을 만들지 않는다:\n  " + "\n  ".join(bad))
    logs = {n: sha256_file(run_dir / n) for n in ("run_all.log", "driver.log", "env.txt")
            if (run_dir / n).is_file()}
    return {"gate_block": E2E_BLOCK, "run_dir": str(run_dir.relative_to(data_root)),
            "outputs": measured, "outputs_match_gate": True, "all_rc_0": True,
            "log_sha256": logs, "scope": block.get("scope")}


def git_state(repo_root: Path) -> Dict[str, Any]:
    """HEAD 와 작업트리 깨끗함 (기록용 — 검증에서는 대조하지 않는다)."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root,
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root,
                           capture_output=True, text=True, check=True).stdout.strip()
    return {"head": head, "clean": dirty == ""}


def acceptance(repo_root: Path, release: Path, data_root: Path,
               junit: Path) -> Dict[str, Any]:
    """대응표 + junit. 실패 0·대응표 명명 시험 전부 통과가 아니면 멈춘다."""
    map_path = repo_root / release / MAP_REL
    amap = json.loads(map_path.read_text(encoding="utf-8"))
    j = parse_junit(junit)
    named = named_test_results(amap, j["outcomes"])
    problems = []
    if j["counts"]["failed"]:
        problems.append(f"실패 {j['counts']['failed']}")
    if named["missing"]:
        problems.append(f"대응표 시험이 junit 에 없음 {named['missing'][:5]}")
    if named["not_passed"]:
        problems.append(f"대응표 시험이 통과 아님 {named['not_passed'][:5]}")
    if amap["summary"]["partial"] or amap["summary"]["none"]:
        problems.append("대응표에 부분·없음 항목이 있다")
    if problems:
        raise SystemExit("acceptance 실패 — 잠금을 만들지 않는다: " + "; ".join(problems))
    try:
        junit_rec = L.file_record(junit, base=data_root)
    except ValueError:
        raise SystemExit(f"junit 은 data root 아래에 둔다 (/tmp 금지): {junit}")
    return {"map": L.file_record(map_path, base=repo_root / release),
            "map_summary": {k: len(v) for k, v in amap["summary"].items()},
            "junit": junit_rec, "pytest_counts": j["counts"],
            "named_tests": named["per_item"],
            "all_named_tests_passed": True}


def measurement_ref(repo_root: Path, release: Path) -> Dict[str, Any]:
    """측정 잠금 참조."""
    p = repo_root / release / "locks" / "measurement_lock.json"
    lock = json.loads(p.read_text(encoding="utf-8"))
    rec = L.file_record(p, base=repo_root / release)
    rec["lock_hash"] = lock["lock_hash"]
    return rec


def build(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    gate = json.loads((repo_root / args.release / "gate_evidence.json").read_text(encoding="utf-8"))
    git = git_state(repo_root)
    if not git["clean"]:
        raise SystemExit("작업트리가 깨끗하지 않다 — 잠금을 만들지 않는다")
    code, configs = code_and_configs(repo_root)
    body: Dict[str, Any] = {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": args.reason,
        "decision": "결정 21 (가) — 명세 4",
        "git": git,
        "gate_revision_at_build": gate.get("revision"),
        "environment": environment(),
        "code": code,
        "configs": configs,
        "cli": cli_help(repo_root),
        "acceptance": acceptance(repo_root, args.release, data_root, args.pytest_junit.resolve()),
        "pilot_end_to_end": pilot_e2e(data_root, gate),
        "measurement_lock": measurement_ref(repo_root, args.release),
        "t10_gpu_reload": {"status": "not_done",
                           "note": "CLI evaluate 는 checkpoint 를 재로드하지 않는다 (sha 만). "
                                   "GPU 저장 → 재로드 대조는 이 판에 넣지 않음 (구현 선택)."},
        "verify_command": "python scripts/h197/27_build_implementation_lock.py --verify "
                          "--data-root <...> --repo-root <...> --release <...>",
    }
    body["lock_hash"] = L.lock_hash(body)
    return body


def verify(lock: Mapping[str, Any], args: argparse.Namespace) -> Dict[str, List[str]]:
    """기록된 값을 다시 잰다. git HEAD 는 대조하지 않는다 (docstring)."""
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    res: Dict[str, List[str]] = {"ok": [], "mismatch": []}

    def check(name: str, rec: Any, now: Any) -> None:
        (res["ok"] if rec == now else res["mismatch"]).append(name)

    check("lock_hash", lock.get("lock_hash"), L.lock_hash(lock))
    code, configs = code_and_configs(repo_root)
    check("code.code_hash", lock["code"]["code_hash"], code["code_hash"])
    for stem, rec in lock["configs"].items():
        now = configs.get(stem, {})
        check(f"configs.{stem}.sha256", rec["sha256"], now.get("sha256"))
        check(f"configs.{stem}.config_hash", rec["config_hash"], now.get("config_hash"))
    check("configs.set", sorted(lock["configs"]), sorted(configs))
    helps = cli_help(repo_root)["help"]
    check("cli.set", sorted(lock["cli"]["help"]), sorted(helps))
    for sub, rec in lock["cli"]["help"].items():
        check(f"cli.help.{sub}", rec["sha256"], helps.get(sub, {}).get("sha256"))
    env = environment()
    for k in ("python", "torch", "cuda", "cuda_available"):
        check(f"environment.{k}", lock["environment"][k], env[k])
    check("environment.pip_freeze", lock["environment"]["pip_freeze"]["sha256"],
          env["pip_freeze"]["sha256"])
    acc = lock["acceptance"]
    check("acceptance.map", acc["map"]["sha256"],
          sha256_file(repo_root / args.release / acc["map"]["path"]))
    jp = data_root / acc["junit"]["path"]
    check("acceptance.junit", acc["junit"]["sha256"], sha256_file(jp) if jp.is_file() else None)
    for rel, sha in lock["pilot_end_to_end"]["outputs"].items():
        p = data_root / rel
        check(f"pilot_e2e.{rel}", sha, sha256_file(p) if p.is_file() else None)
    m = measurement_ref(repo_root, args.release)
    check("measurement_lock.sha256", lock["measurement_lock"]["sha256"], m["sha256"])
    check("measurement_lock.lock_hash", lock["measurement_lock"]["lock_hash"], m["lock_hash"])
    return res


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--release", required=True, type=Path)
    ap.add_argument("--pytest-junit", type=Path, default=None)
    ap.add_argument("--reason", default=None)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv[1:])

    out = (args.repo_root / args.release / "locks" / LOCK_NAME).resolve()
    if args.verify:
        if not out.is_file():
            print(f"잠금 파일이 없다: {out}")
            return 2
        lock = json.loads(out.read_text(encoding="utf-8"))
        res = verify(lock, args)
        for line in res["mismatch"]:
            print(f"[MISMATCH] {line}")
        print(f"구현 잠금 {lock.get('lock_hash', '?')[:12]} — 검사 "
              f"{len(res['ok']) + len(res['mismatch'])}건: 일치 {len(res['ok'])}, "
              f"불일치 {len(res['mismatch'])}")
        return 0 if not res["mismatch"] else 1

    if args.pytest_junit is None or not args.reason:
        ap.error("생성에는 --pytest-junit 과 --reason 이 필요하다")
    if out.exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {out}")
        return 2
    body = build(args)
    out.write_text(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"구현 잠금 {body['lock_hash'][:12]} → {out}")
    print(f"code_hash {body['code']['code_hash'][:12]} · pytest {body['acceptance']['pytest_counts']} "
          f"· cli help {len(body['cli']['help'])} · pilot e2e {len(body['pilot_end_to_end']['outputs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
