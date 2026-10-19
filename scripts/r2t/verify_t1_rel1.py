#!/usr/bin/env python3
"""R2T T1 기존 F4R · F4R1 결과 읽기 검증 (패치 0.3, **합성 자료만**). 생성기 + seed 로 정답만 재생성 — 모델 적합 · 성능 평가 없음.

판 하나라도 실패면 exit 1. 보고서 (--report) 는 새 파일로만 쓴다 (있으면 거부).

Usage:
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/r2t/verify_t1_rel1.py --runs results/r2t/t1_rel/val/*.json --report <새 경로>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_t1_rel as ER  # noqa: E402
import t1_rel1 as T1  # noqa: E402


def spec_to_world(spec: dict) -> str:
    if spec["generator"] == "eval_t1_worlds.world":
        return f"{spec['kind']}:{spec['seed']}"
    p = spec["params"]
    return f"sep={p['sep']},dwell={p['dwell']},phase={p['phase']},rho={p['rho']},ns={p['ns']},wrong={p['wrong']}:{spec['seed']}"


def verify_file(json_path: Path) -> dict:
    prefix = json_path.with_suffix("")
    rec = {"run": str(json_path)}
    try:
        doc = json.loads(json_path.read_text())
        spec = doc["spec"]
        w = spec_to_world(spec)
        _, _, task, _, spec2 = ER.make_world(w, spec["n_roi"], spec["n_subjects"])
        for k in ("generator", "seed", "n_roi", "n_subjects"):
            if spec2[k] != spec[k]:
                raise ValueError(f"재생성 spec 불일치: {k}")
        rec["world"] = w
        rec.update(T1.verify_prefix(prefix, task, spec["n_roi"]))
        has_oracle = any("oracle_refits" in f.get("F4R", {}) for f in doc["folds"])
        rec["oracle_refit_records"] = "보존" if has_oracle else "미보존 (이 판의 oracle 재적합 실패 원인은 저장되지 않았음 — 추정하지 않음)"
    except Exception as e:
        rec.update(ok=False, problems=[f"예외: {type(e).__name__}: {e}"])
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", nargs="+", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.report.exists():
        raise SystemExit(f"덮어쓰지 않는다: {a.report}")
    recs = [verify_file(p) for p in sorted(a.runs)]
    n_bad = sum(not r["ok"] for r in recs)
    out = {"schema": "r2t-t1-rel1-verify-0.1", "synthetic_only": True, "model_fit_or_eval_rerun": False,
           "truth": "생성기 + seed 로 재생성", "n_runs": len(recs), "n_failed": n_bad,
           "n_arrays_checked": sum(r.get("n_arrays_checked", 0) for r in recs),
           "n_subject_scores_rechecked": sum(r.get("n_subject_scores_rechecked", 0) for r in recs), "runs": recs}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for r in recs:
        print(f"{r.get('world', r['run'])}: {'통과' if r['ok'] else '실패'} {r['problems'][:2]}", file=sys.stderr)
    return 1 if n_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
