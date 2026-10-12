#!/usr/bin/env python3
"""`gate_evidence.json` 이 기록한 모든 해시를 실제 파일과 대조한다.

증거 파일을 갱신한 **직후 마지막 단계로** 돌린다. rev21 은 P7·E15 수정이
닿은 8개 파일의 해시를 갱신하지 않은 채 마감됐다(E17).

이 검증기는 두 가지를 본다.

1. 기록된 해시가 실제 파일과 같은가.
2. 해시를 모으는 디렉터리에 **기록되지 않은 파일이 있는가** — rev21 의
   `h197_scripts` 는 21개 중 11개만 담고 있었고, 1번만으로는 잡히지 않았다.

Usage:
    python scripts/h197/17_verify_gate_hashes.py results/redesign_v1/<release>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SHA_RE = re.compile(r"^[0-9a-f]{64}$")

#: gate_evidence 의 블록 이름 → 그 블록의 키가 가리키는 디렉터리(repo 기준).
DIR_BLOCKS: Dict[str, str] = {
    "v2_module_hashes": "mobse/v2",
    "v2_test_hashes": "tests/v2",
    "h197_scripts": "scripts/h197",
}

#: 블록별로 해시 대상에서 제외할 이름.
DIR_IGNORE = {"__pycache__", ".pytest_cache", ".DS_Store"}

#: release 디렉터리 기준으로 푸는 블록.
REL_DIR_BLOCKS: Dict[str, str] = {
    "h197_imported_artifacts": "provenance/h197_wave1",
}

#: (블록, 필드) → repo 기준 경로. 단일 해시 필드.
SINGLE_FIELDS: List[Tuple[Tuple[str, str], str]] = [
    (("script_contract_guard", "guard_sha256"), "tests/v2/test_h197_scripts.py"),
    (("wi03_cohort", "builder_script_sha256"), "scripts/h197/15_build_subjects.py"),
    (("wi02_piop2", "watcher_script_sha256"), "scripts/h197/16_watch_and_process_piop2.sh"),
    (("protocol_amendments", "protocol_sha256"),
     "docs/experiments/mobse_redesign_protocol_2026-09-17.md"),
    (("protocol_amendments", "instructions_sha256"),
     "docs/experiments/mobse_redesign_work_instructions_2026-09-17.md"),
]


def sha256_file(path: Path) -> str:
    """파일의 SHA256 hex."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(path: Path, expect: str, where: str, acc: Dict[str, List[str]]) -> None:
    if not path.is_file():
        acc["missing"].append(f"{where}: 파일 없음 {path}")
        return
    got = sha256_file(path)
    if got != expect:
        acc["mismatch"].append(f"{where}: 기대 {expect[:12]} 실제 {got[:12]}  {path}")
    else:
        acc["ok"].append(where)


def verify(release_dir: Path, repo: Path) -> Dict[str, List[str]]:
    """검증 결과를 ``{"ok","mismatch","missing","unrecorded"}`` 로 돌려준다."""
    evidence = json.loads((release_dir / "gate_evidence.json").read_text(encoding="utf-8"))
    acc: Dict[str, List[str]] = {"ok": [], "mismatch": [], "missing": [], "unrecorded": []}

    for block, rel in DIR_BLOCKS.items():
        base = repo / rel
        recorded = evidence.get(block) or {}
        for name, expect in recorded.items():
            _check(base / name, expect, f"{block}/{name}", acc)
        for p in sorted(base.iterdir()) if base.is_dir() else []:
            if p.is_file() and p.name not in recorded and p.name not in DIR_IGNORE:
                acc["unrecorded"].append(f"{block}: 미기록 {p.name}")

    for block, rel in REL_DIR_BLOCKS.items():
        base = release_dir / rel
        for name, expect in (evidence.get(block) or {}).items():
            _check(base / name, expect, f"{block}/{name}", acc)

    for (block, field), rel in SINGLE_FIELDS:
        if block in evidence and field in evidence[block]:
            _check(repo / rel, evidence[block][field], f"{block}.{field}", acc)

    for gate in evidence.get("gates", []):
        for name, expect in (gate.get("artifact_hashes") or {}).items():
            _check(release_dir / name, expect, f"{gate['gate']}/{name}", acc)

    for block, payload in evidence.items():
        arts = payload.get("artifacts") if isinstance(payload, dict) else None
        if isinstance(arts, dict):
            for name, expect in arts.items():
                if isinstance(expect, str) and SHA_RE.match(expect):
                    _check(release_dir / name, expect, f"{block}.artifacts/{name}", acc)

    return acc


def main(argv: List[str]) -> int:
    release_dir = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    repo = release_dir.parents[2]
    acc = verify(release_dir, repo)
    for kind in ("mismatch", "missing", "unrecorded"):
        for line in acc[kind]:
            print(f"[{kind.upper()}] {line}")
    total = sum(len(v) for v in acc.values())
    print(f"검사 {total}건: 일치 {len(acc['ok'])}, 불일치 {len(acc['mismatch'])}, "
          f"파일없음 {len(acc['missing'])}, 미기록 {len(acc['unrecorded'])}")
    return 1 if (acc["mismatch"] or acc["missing"] or acc["unrecorded"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
