#!/usr/bin/env python3
"""U3 — 폐기 volume 수를 raw sidecar 로 전수 조사한다 (표준 라이브러리만 사용).

WI-01 시점에는 "로컬에 기록이 없어 판정 불가"로 남겼던 항목이다. Wave 1 로
raw sidecar 를 확보했으므로 이제 직접 읽는다. 계획서 §3.1 이 요구하는
`discarded_volumes` 와 `derivative_start_sec` 의 근거가 여기서 나온다.

조사 대상 키:
    NumberOfVolumesDiscardedByScanner  — 스캐너가 버려 파일에 없는 volume
    NumberOfVolumesDiscardedByUser     — 변환 단계에서 버린 volume

한 조합 안에서 값이 갈리면 **평균 내지 않고 충돌로 보고한다** (T02).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ENTITY = re.compile(r"(?:^|_)(?P<key>[a-zA-Z]+)-(?P<value>[a-zA-Z0-9]+)")


def entities(name: str) -> Dict[str, str]:
    """BIDS 파일명에서 entity 를 뽑는다."""
    return {m.group("key"): m.group("value") for m in ENTITY.finditer(name)}


def survey(roots: List[Path]) -> Dict[str, Any]:
    """raw sidecar 를 훑어 dataset×task 별 분포를 만든다."""
    by_combo: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "scanner": defaultdict(int), "user": defaultdict(int),
                 "tr": defaultdict(int), "examples": []})
    n_files = 0
    unreadable: List[Dict[str, str]] = []

    for root in roots:
        for path in sorted(root.rglob("*_bold.json")):
            if "fmriprep" in path.parts or "derivatives" in path.parts:
                continue
            n_files += 1
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                unreadable.append({"path": str(path), "error": str(exc)})
                continue
            ent = entities(path.name)
            dataset = next((p for p in path.parts if p.startswith("ds00")), "unknown")
            combo = f"{dataset}/{ent.get('task', '?')}"
            rec = by_combo[combo]
            rec["n"] += 1
            rec["scanner"][repr(meta.get("NumberOfVolumesDiscardedByScanner"))] += 1
            rec["user"][repr(meta.get("NumberOfVolumesDiscardedByUser"))] += 1
            rec["tr"][repr(meta.get("RepetitionTime"))] += 1
            if len(rec["examples"]) < 2:
                rec["examples"].append(str(path))

    combos: Dict[str, Any] = {}
    conflicts: List[Dict[str, Any]] = []
    for combo, rec in sorted(by_combo.items()):
        entry = {
            "n": rec["n"],
            "discarded_by_scanner": dict(sorted(rec["scanner"].items())),
            "discarded_by_user": dict(sorted(rec["user"].items())),
            "repetition_time": dict(sorted(rec["tr"].items())),
            "examples": rec["examples"],
        }
        for field in ("discarded_by_scanner", "discarded_by_user", "repetition_time"):
            if len(entry[field]) > 1:
                conflicts.append({"combo": combo, "field": field,
                                  "values": entry[field]})
        combos[combo] = entry

    return {
        "sidecar_files_read": n_files,
        "unreadable": unreadable,
        "combos": combos,
        "conflicts": conflicts,
        "verdict": "resolved" if (n_files and not conflicts and not unreadable)
                   else "conflict" if conflicts else "incomplete",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, nargs="+", required=True,
                    help="raw BIDS 트리 루트 (여러 개 가능)")
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    result = survey([Path(r) for r in args.root])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    print(f"[scan] raw sidecar {result['sidecar_files_read']}개")
    for combo, rec in result["combos"].items():
        print(f"  {combo:28s} n={rec['n']:4d} "
              f"scanner={dict(rec['discarded_by_scanner'])} "
              f"user={dict(rec['discarded_by_user'])} "
              f"TR={dict(rec['repetition_time'])}")
    if result["conflicts"]:
        print("[FAIL] 조합 내 값 충돌:")
        for c in result["conflicts"]:
            print(f"  - {c['combo']} {c['field']}: {c['values']}")
        return 1
    if result["unreadable"]:
        print(f"[FAIL] 읽지 못한 파일 {len(result['unreadable'])}건")
        return 1
    print(f"[{result['verdict'].upper()}] 조합 내 분산 없음 — U3 판정 가능")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
