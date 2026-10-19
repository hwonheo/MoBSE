#!/usr/bin/env python3
"""R2T T1 실행 전 검토 기록 (결정 87) — 계획 · 설계 · 설정 · 코드 · 시험 · 메타데이터의 sha256 과 preflight (헤더만) 를 남긴다.
**잠금이 아니다** (잠금 생성은 별도 승인). 실제 신호 값은 읽지 않는다.

Usage:
    PYTHONPATH=. .venv/bin/python -B scripts/r2t/t1_review_record.py --out results/r2t/t1_prerun/review_record.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import t1  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg_path = ROOT / "configs" / "r2t" / "t1_pilot.json"
    cfg = t1.load_config(cfg_path)
    docs = [cfg["plan_doc"], cfg["design_doc"]]
    code = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scripts" / "r2t").glob("*.py"))
    tests = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests" / "r2t").glob("*.py"))
    upstream = ["mobse/v2/extract.py", "mobse/v2/preprocess.py", "scripts/h197/10_wi02_extract.py",
                "scripts/h1h2_scope/i3_extract_pilot.py"]
    meta = [cfg["subjects"]["source"], cfg["data"]["task_manifest"], cfg["data"]["atlas_tsv"]]
    rec = {"schema": "r2t-t1-review-record-0.1", "decision": 87, "is_lock": False,
           "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "note": "실행 전 검토용 해시 기록. 잠금 · 실제 값 적재 · pilot 실행은 별도 승인",
           "config": {str(cfg_path.relative_to(ROOT)): sha(cfg_path)},
           "docs": {d: sha(ROOT / d) for d in docs},
           "code": {c: sha(ROOT / c) for c in code}, "tests": {t: sha(ROOT / t) for t in tests},
           "upstream_extraction_code": {u: sha(ROOT / u) for u in upstream},
           "metadata": {m: sha(ROOT / m) for m in meta},
           "preflight": t1.preflight(cfg, ROOT)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, ensure_ascii=False, indent=1)
    a.out.write_text(text)
    print(json.dumps({"out": str(a.out), "sha12": hashlib.sha256(text.encode()).hexdigest()[:12],
                      "preflight_problems": len(rec["preflight"]["problems"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
