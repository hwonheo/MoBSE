#!/usr/bin/env python3
"""exploratory v2 (코드 모듈 ``v3``) 구현 잠금을 만들거나 검증한다.

v1 의 `27_build_implementation_lock.py` 를 쓸 수 없다. 그 스크립트는 `mobse/v2`
만 해시하고, v1 의 acceptance 대응표·pilot end-to-end 기록을 필수로 요구한다.
v3 는 해시 범위도 다르고 (설계안 §5.3.2 구현 선택: ``mobse/v3/*.py`` 와
``mobse/v2/*.py`` 를 **함께** 해시한다) 그 두 기록이 아직 없다.

**측정 잠금은 새로 만들지 않는다.** v3 는 v1 과 같은 자료 (derivatives_v3 ·
splits_piop1_p7) 를 쓰므로, 그 사실을 v1 측정 잠금 ``lock_hash`` 참조로 적는다.
자료가 바뀌면 그때 측정 잠금을 새로 만든다.

담는 것
-------
* ``environment`` — python · platform · torch · CUDA · GPU, ``pip freeze`` 와 sha256
* ``code`` — ``mobse/v3/*.py`` + ``mobse/v2/*.py`` 의 code_hash 와 모듈별 sha256
* ``configs`` — ``configs/exploratory_v2/*.yaml`` 의 sha256 과 v3 config_hash
* ``cli`` — v3 하위 명령과 실제 ``--help`` 출력 (COLUMNS 고정) 의 sha256
* ``tests`` — 마감 1 단계 junit 요약 (``--pytest-junit``, 선택)
* ``measurement_lock`` — v1 측정 잠금 참조 (새로 만들지 않는다)

구현 선택 (표시): 생성과 검증을 한 스크립트에 둔다 (``--verify``). git HEAD 는
대조하지 않는다 — 잠금을 커밋하면 HEAD 가 바뀐다 (기록만 한다).

Usage:
    python scripts/h197/29_build_v3_lock.py --repo-root . \
        --out results/exploratory_v2/locks/v3_lock.json \
        --measurement-lock results/redesign_v1/<release>/locks/measurement_lock.json \
        --reason "..."
    python scripts/h197/29_build_v3_lock.py --verify --repo-root . \
        --out results/exploratory_v2/locks/v3_lock.json
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
from typing import Any, Dict, List, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2.manifests import sha256_file                      # noqa: E402
from mobse.v3.cli import SUBCOMMANDS                             # noqa: E402
from mobse.v3.config import config_hash, load_config             # noqa: E402

#: 해시 대상. 순서가 code_hash 에 들어가므로 바꾸지 않는다.
CODE_DIRS = ("mobse/v3", "mobse/v2")
CONFIG_DIR = "configs/exploratory_v2"
HELP_COLUMNS = "100"
SCHEMA = "v3-implementation-lock-0.1"


def sha256_text(text: str) -> str:
    """문자열의 sha256 hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def v3_code_hash(repo_root: Path, paths: List[Path]) -> str:
    """``mobse/v3`` 와 ``mobse/v2`` 를 함께 해시한다 — **상대 경로 기준**.

    v1 의 `mobse.v2.manifests.code_hash` 를 쓸 수 없다. 그 함수는 파일명이 겹치면
    거부하는데 (같은 이름이 둘이면 어느 쪽인지 알 수 없으므로 옳은 규칙이다), v3 는
    `cli.py`·`config.py`·`fitting.py`·`models.py`·`templates.py`·`train.py`·
    `__init__.py` 일곱 개를 v2 와 같은 이름으로 쓴다. 그래서 **디렉터리를 포함한
    상대 경로**를 키로 삼아 여기서 따로 정의한다.

    정의: ``{상대경로: 파일 sha256}`` 을 키 정렬한 canonical JSON 의 sha256.
    """
    payload = {str(p.relative_to(repo_root)): sha256_file(p) for p in paths}
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")))


def module_paths(repo_root: Path) -> List[Path]:
    """해시할 파이썬 모듈 경로. 디렉터리 순서는 고정이고 그 안에서는 이름순이다."""
    out: List[Path] = []
    for d in CODE_DIRS:
        found = sorted((repo_root / d).glob("*.py"))
        if not found:
            raise SystemExit(f"해시할 모듈이 없다: {repo_root / d}")
        out += found
    return out


def environment() -> Dict[str, Any]:
    """실행 환경. torch 가 없으면 실패한다 — 잠금은 학습 환경을 기록해야 한다."""
    import torch

    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"],
                            capture_output=True, text=True, check=True).stdout
    lines = sorted(s.strip() for s in freeze.splitlines()
                   if s.strip() and s.split("==", 1)[0].split(" @ ", 1)[0]
                   .strip().lower() != "mobse")
    gpus = ([torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
            if torch.cuda.is_available() else [])
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cuda_available": bool(torch.cuda.is_available()),
        "gpus": gpus,
        "pip_freeze": {"sha256": sha256_text("\n".join(lines) + "\n"),
                       "n": len(lines), "lines": lines},
    }


def code_section(repo_root: Path) -> Dict[str, Any]:
    """v3 와 v2 를 **함께** 해시한다 (설계안 구현 선택)."""
    paths = module_paths(repo_root)
    return {
        "dirs": list(CODE_DIRS),
        "code_hash": v3_code_hash(repo_root, paths),
        "n_modules": len(paths),
        "modules": {str(p.relative_to(repo_root)): sha256_file(p) for p in paths},
        "note": "v2 는 v1 release 로 동결됐다. 이 참조는 흔들리지 않는다",
    }


def config_section(repo_root: Path) -> Dict[str, Any]:
    """`configs/exploratory_v2/*.yaml` 을 검증하고 해시한다."""
    out: Dict[str, Any] = {}
    for p in sorted((repo_root / CONFIG_DIR).glob("*.yaml")):
        out[p.stem] = {"path": str(p.relative_to(repo_root)),
                       "sha256": sha256_file(p),
                       "config_hash": config_hash(load_config(p))}
    if not out:
        raise SystemExit(f"config 가 없다: {repo_root / CONFIG_DIR}")
    return out


def cli_section(repo_root: Path) -> Dict[str, Any]:
    """최상위와 하위 명령별 실제 ``--help``. 폭을 고정해 sha 가 흔들리지 않게 한다."""
    env = dict(os.environ, COLUMNS=HELP_COLUMNS, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(repo_root))
    helps: Dict[str, Any] = {}
    for sub in ("",) + tuple(SUBCOMMANDS):
        argv = ([sys.executable, "-B", "-m", "mobse.v3.cli"]
                + ([sub] if sub else []) + ["--help"])
        proc = subprocess.run(argv, cwd=repo_root, env=env, capture_output=True,
                              text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(f"--help 실패 ({sub or '<top>'}): rc={proc.returncode} "
                             f"{proc.stderr[-300:]}")
        helps[sub or "<top>"] = {"sha256": sha256_text(proc.stdout), "text": proc.stdout}
    return {"columns": int(HELP_COLUMNS), "subcommands": list(SUBCOMMANDS),
            "help": helps}


def tests_section(junit: Path | None) -> Dict[str, Any]:
    """마감 1 단계 junit 요약. 주지 않으면 `not_reported` 로 남긴다 — 0 으로 세지 않는다."""
    if junit is None:
        return {"status": "not_reported",
                "note": "--pytest-junit 를 주지 않았다. 통과 수를 0 으로 세지 않는다"}
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    total = {k: 0 for k in ("tests", "failures", "errors", "skipped")}
    for s in suites:
        for k in total:
            total[k] += int(s.get(k, 0))
    return {"status": "reported", "sha256": sha256_file(junit), **total,
            "passed": total["tests"] - total["failures"] - total["errors"]
            - total["skipped"]}


def measurement_ref(path: Path | None) -> Dict[str, Any]:
    """v1 측정 잠금 참조. v3 는 같은 자료를 쓰므로 새로 만들지 않는다."""
    if path is None:
        return {"status": "not_reported",
                "note": "--measurement-lock 를 주지 않았다"}
    lock = json.loads(path.read_text(encoding="utf-8"))
    return {"status": "referenced", "path": str(path),
            "file_sha256": sha256_file(path),
            "lock_hash": lock.get("lock_hash"),
            "note": "v3 는 v1 과 같은 자료를 쓴다 — 자료가 바뀌면 그때 새로 만든다"}


def build(args: argparse.Namespace) -> Dict[str, Any]:
    """잠금 내용을 만든다. 저장은 호출자가 한다."""
    repo_root = args.repo_root.resolve()
    payload = {
        "schema_version": SCHEMA,
        "design_version": "exploratory_v2",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": args.reason,
        "environment": environment(),
        "code": code_section(repo_root),
        "configs": config_section(repo_root),
        "cli": cli_section(repo_root),
        "tests": tests_section(args.pytest_junit),
        "measurement_lock": measurement_ref(args.measurement_lock),
    }
    payload["lock_hash"] = sha256_text(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return payload


def verify(lock: Mapping[str, Any], args: argparse.Namespace) -> List[str]:
    """잠금이 여전히 참인지 다시 **재어** 본다. 기록된 참은 참이 아니다."""
    repo_root = args.repo_root.resolve()
    problems: List[str] = []

    paths = module_paths(repo_root)
    now = {str(p.relative_to(repo_root)): sha256_file(p) for p in paths}
    was = dict(lock["code"]["modules"])
    for name in sorted(set(was) - set(now)):
        problems.append(f"code: 사라진 모듈 {name}")
    for name in sorted(set(now) - set(was)):
        problems.append(f"code: 기록되지 않은 모듈 {name}")
    for name in sorted(set(now) & set(was)):
        if now[name] != was[name]:
            problems.append(f"code: {name} 해시 불일치")
    if v3_code_hash(repo_root, paths) != lock["code"]["code_hash"]:
        problems.append("code: code_hash 불일치")

    for stem, rec in lock["configs"].items():
        p = repo_root / rec["path"]
        if not p.is_file():
            problems.append(f"config: 파일 없음 {rec['path']}")
            continue
        if sha256_file(p) != rec["sha256"]:
            problems.append(f"config: {stem} 파일 해시 불일치")
        if config_hash(load_config(p)) != rec["config_hash"]:
            problems.append(f"config: {stem} config_hash 불일치")

    if list(lock["cli"]["subcommands"]) != list(SUBCOMMANDS):
        problems.append(f"cli: 하위 명령이 바뀌었다 {lock['cli']['subcommands']} "
                        f"→ {list(SUBCOMMANDS)}")
    else:
        now_cli = cli_section(repo_root)["help"]
        for key, rec in lock["cli"]["help"].items():
            if now_cli[key]["sha256"] != rec["sha256"]:
                problems.append(f"cli: --help 가 바뀌었다 ({key})")
    return problems


def main(argv: List[str]) -> int:
    """CLI 진입점."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--measurement-lock", type=Path, default=None)
    ap.add_argument("--pytest-junit", type=Path, default=None)
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv[1:])

    if args.verify:
        if not args.out.is_file():
            print(f"잠금 파일이 없다: {args.out}")
            return 2
        lock = json.loads(args.out.read_text(encoding="utf-8"))
        problems = verify(lock, args)
        for p in problems:
            print(f"[MISMATCH] {p}")
        print(f"v3 잠금 {str(lock.get('lock_hash'))[:12]} — 검사 "
              f"{len(lock['code']['modules']) + 2 * len(lock['configs']) + 1 + len(lock['cli']['help'])}건: "
              f"불일치 {len(problems)}건")
        return 1 if problems else 0

    if args.out.exists():
        print(f"이미 존재한다: {args.out}. 같은 잠금을 덮어쓰지 않는다")
        return 2
    if not args.reason:
        print("--reason 이 필요하다 — 왜 이 판을 만드는지 적는다")
        return 2
    payload = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"v3 잠금 생성: {args.out} — lock_hash {payload['lock_hash'][:12]}, "
          f"모듈 {payload['code']['n_modules']}, config {len(payload['configs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
