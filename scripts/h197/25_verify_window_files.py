#!/usr/bin/env python3
"""잠금이 가리키는 추출 manifest 의 창 파일을 전부 역참조해 확인한다.

19_verify_measurement_lock.py 는 manifest **파일 자체**의 해시만 대조한다.
manifest 안의 `windows[].path` 가 가리키는 `.npy` 는 열어 보지 않는다. 그래서
manifest 가 휘발성 경로(`/tmp/...`)를 가리키거나 파일 일부가 빠져도 잠금은
24/24 로 통과한다 (2026-09-23 사고: PIOP1 workingmemory 704창이
`/tmp/wm_rerun2/` 를 가리킨 채 재부팅으로 소실, 잠금·해시·인용·시험 모두 통과).

검사 (status == "ok" 인 run 의 모든 창):
  1. 경로가 `--data-root` 아래인가 — 아니면 `outside_root` (휘발성 경로 차단)
  2. 파일이 존재하는가            — 아니면 `missing`
  3. sha256 이 기록과 같은가       — 아니면 `mismatch`
  4. ok run 에 창이 하나 이상인가  — 아니면 `empty_ok_run`

manifest 목록은 잠금 파일에서 읽는다. glob 으로 찾지 않는다.

Usage:
    python scripts/h197/25_verify_window_files.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset \
        --lock results/redesign_v1/<release>/locks/measurement_lock.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

FAIL_KINDS: Tuple[str, ...] = ("outside_root", "missing", "mismatch", "empty_ok_run")


def sha256_file(path: Path) -> str:
    """파일의 sha256 hex digest.

    Args:
        path: 대상 파일.

    Returns:
        64자 hex 문자열.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def manifests_from_lock(lock: Dict[str, Any]) -> List[Tuple[str, str]]:
    """잠금의 cohorts/*/manifests 에서 (라벨, 상대경로) 목록을 만든다.

    Args:
        lock: measurement_lock.json 본문.

    Returns:
        [(\"piop1/workingmemory\", \"derivatives_v2/...jsonl\"), ...]

    Raises:
        ValueError: manifest 가 하나도 없으면.
    """
    out = [(f"{cname}/{task}", rec["path"])
           for cname, cohort in sorted(lock.get("cohorts", {}).items())
           for task, rec in sorted(cohort.get("manifests", {}).items())]
    if not out:
        raise ValueError("잠금에 manifest 가 없다")
    return out


def iter_ok_runs(manifest: Path) -> Iterator[Dict[str, Any]]:
    """manifest 의 status == ok 인 run 레코드."""
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("record_type") == "run" and rec.get("status") == "ok":
            yield rec


def check_manifest(manifest: Path, data_root: Path) -> Dict[str, Any]:
    """한 manifest 의 모든 창을 검사한다.

    Args:
        manifest: 추출 manifest (.jsonl).
        data_root: 창 파일이 있어야 하는 최상위 경로.

    Returns:
        {"n_windows", "ok", 실패 종류별 개수, "examples": [...]}.
    """
    root = data_root.resolve()
    res: Dict[str, Any] = {"n_windows": 0, "ok": 0, **{k: 0 for k in FAIL_KINDS},
                           "examples": []}

    def fail(kind: str, detail: str) -> None:
        res[kind] += 1
        if len(res["examples"]) < 10:
            res["examples"].append(f"{kind}: {detail}")

    for run in iter_ok_runs(manifest):
        windows = run.get("windows") or []
        if not windows:
            fail("empty_ok_run", run.get("run_key", "?"))
        for w in windows:
            res["n_windows"] += 1
            p = Path(w["path"])
            p = p if p.is_absolute() else data_root / p
            try:
                p.resolve().relative_to(root)
            except ValueError:
                fail("outside_root", str(p))
                continue
            if not p.is_file():
                fail("missing", str(p))
            elif sha256_file(p) != w["sha256"]:
                fail("mismatch", str(p))
            else:
                res["ok"] += 1
    return res


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--lock", required=True, type=Path)
    args = ap.parse_args(argv)

    if not args.data_root.is_dir():
        print(f"[error] data-root 없음: {args.data_root}", file=sys.stderr)
        return 2
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    failed = 0
    total = 0
    for label, rel in manifests_from_lock(lock):
        mpath = args.data_root / rel
        if not mpath.is_file():
            print(f"[FAIL] {label}: manifest 없음 {mpath}")
            failed += 1
            continue
        r = check_manifest(mpath, args.data_root)
        bad = sum(r[k] for k in FAIL_KINDS)
        total += r["n_windows"]
        tag = "ok" if bad == 0 and r["n_windows"] > 0 else "FAIL"
        counts = " ".join(f"{k}={r[k]}" for k in FAIL_KINDS)
        print(f"[{tag}] {label}: 창 {r['n_windows']} 일치 {r['ok']} {counts}")
        for ex in r["examples"]:
            print(f"        {ex}")
        failed += tag == "FAIL"
    print(f"잠금 {lock.get('lock_hash', '?')[:12]} — manifest 실패 {failed}건, 창 {total}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
