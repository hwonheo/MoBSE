#!/usr/bin/env python3
"""R2T T1 F4R1 실행 · 저장 · 엄격 검증 (패치 0.3, **합성 자료만**). 판 하나라도 검증 실패 · 예외면 exit 1.

세계 지정은 `eval_t1_rel.py` 와 같다. 판마다 <out-dir>/<이름>.json · .npz, 검증 결과는 <out-dir>/verify.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_t1_rel as ER  # noqa: E402
import t1  # noqa: E402
import t1_rel1 as T1  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--worlds", nargs="+", required=True)
    ap.add_argument("--n-roi", type=int, default=100)
    ap.add_argument("--n-subjects", type=int, default=31)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "r2t" / "t1_pilot_rel.json")
    a = ap.parse_args(argv)
    cfg = t1.load_config(a.config)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for w in a.worlds:
        prefix = a.out_dir / re.sub(r"[^0-9A-Za-z]+", "_", w)
        rec = {"world": w, "prefix": str(prefix)}
        try:
            ids, rest, task, left, spec = ER.make_world(w, a.n_roi, a.n_subjects)
            spec["tag"] = a.tag
            t0 = time.perf_counter()
            res = T1.run_pipeline(rest, task, ids, cfg, left)
            spec["seconds"] = time.perf_counter() - t0
            T1.save_run1(prefix, res, spec, cfg)
            _, _, task2, _, _ = ER.make_world(w, a.n_roi, a.n_subjects)
            rec.update(T1.verify_prefix(prefix, task2, a.n_roi))
        except Exception as e:                                             # 저장 · 검증 예외도 실패로 기록
            rec.update(ok=False, problems=[f"예외: {type(e).__name__}: {e}"], traceback=traceback.format_exc())
        failed += not rec["ok"]
        with open(a.out_dir / "verify.jsonl", "a") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{w}: 검증 {'통과' if rec['ok'] else '실패'} {rec['problems'][:3]}", file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
