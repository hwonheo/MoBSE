#!/usr/bin/env python3
"""측정 잠금이 여전히 참인지 확인한다 — 지침서 WI-03 / gate G1.

잠금 파일이 기록한 모든 해시를 다시 계산하고, folds 의 파생 불변식을 다시
계산한다. **기록된 참은 참이 아니다.**

`--data-root` 를 주지 않으면 코호트 절은 검사할 수 없으므로 `skipped` 로
보고하고 **실패로 처리한다.** 검사하지 못한 것을 통과로 세지 않는다.

Usage:
    python scripts/h197/19_verify_measurement_lock.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset \
        --repo-root . \
        --release results/redesign_v1/20260917_3c458d507e82_nocfg
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import locks as L                                    # noqa: E402


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--release", required=True, type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv[1:])

    repo_root = args.repo_root.resolve()
    lock_path = (repo_root / args.release / "locks" / "measurement_lock.json").resolve()
    if not lock_path.is_file():
        print(f"잠금 파일이 없다: {lock_path}")
        return 2
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    roots = {"repo_root": repo_root}
    if args.data_root is not None:
        roots["data_root"] = args.data_root.resolve()

    result = L.verify_lock(lock, roots=roots)
    for kind in ("mismatch", "missing", "invariant", "skipped"):
        for line in result[kind]:
            print(f"[{kind.upper()}] {line}")
    if not args.quiet:
        for line in result["ok"]:
            print(f"[ok] {line}")

    total = sum(len(v) for v in result.values())
    print(f"잠금 {lock.get('lock_hash','?')[:12]} — 검사 {total}건: "
          f"일치 {len(result['ok'])}, 불일치 {len(result['mismatch'])}, "
          f"파일없음 {len(result['missing'])}, 불변식실패 {len(result['invariant'])}, "
          f"미검사 {len(result['skipped'])}")
    return 0 if L.lock_is_clean(result) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
