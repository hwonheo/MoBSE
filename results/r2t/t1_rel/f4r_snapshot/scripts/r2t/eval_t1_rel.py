#!/usr/bin/env python3
"""R2T T1 F4R 판 실행 · 저장 · 왕복 확인 (신뢰성 보완, **합성 자료만**).

세계 지정: 기존 세계 "pos:12001" · "null:12101" · "wrong:12201", 어려운 세계 "sep=0.3:12301" (eval_t1_hard 형식).
판마다 <out-dir>/<세계>_<seed>.json · .npz 를 쓰고, 저장 직후 생성기 + seed 로 정답을 재생성해 왕복 확인한 결과를
<out-dir>/roundtrip.jsonl 에 남긴다. 이미 있는 파일은 덮어쓰지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_t1_hard as EH  # noqa: E402
import eval_t1_worlds as EW  # noqa: E402
import synth_t1_hard as H  # noqa: E402
import t1  # noqa: E402
import t1_rel as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def make_world(spec_str: str, n_roi: int, n_subjects: int):
    kind, seed = spec_str.rsplit(":", 1)
    if kind in ("pos", "null", "wrong"):
        ids, rest, task, left = EW.world(kind, int(seed), n_roi, n_subjects)
        spec = {"generator": "eval_t1_worlds.world", "kind": kind, "seed": int(seed), "n_roi": n_roi, "n_subjects": n_subjects}
    else:
        kw, sd = EH.parse(spec_str)
        ids, rest, task, left, _ = H.make(n_subjects=n_subjects, seed=sd, n_roi=n_roi, n_states=kw["ns"], sep=kw["sep"],
                                          dwell=kw["dwell"], phase=kw["phase"], rho=kw["rho"],
                                          task_bank_seed=sd + 10000 if kw["wrong"] else None)
        spec = {"generator": "synth_t1_hard.make", "params": kw, "seed": sd, "n_roi": n_roi, "n_subjects": n_subjects,
                "task_bank_seed": sd + 10000 if kw["wrong"] else None}
    return ids, rest, task, left, spec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--worlds", nargs="+", required=True)
    ap.add_argument("--n-roi", type=int, default=100)
    ap.add_argument("--n-subjects", type=int, default=31)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    cfg = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_rel.json")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for w in a.worlds:
        prefix = a.out_dir / re.sub(r"[^0-9A-Za-z]+", "_", w)   # 점도 바꿈 (with_suffix 가 확장자로 오인)
        ids, rest, task, left, spec = make_world(w, a.n_roi, a.n_subjects)
        spec["tag"] = a.tag
        t0 = time.perf_counter()
        res = T.run_pipeline(rest, task, ids, cfg, left)
        spec["seconds"] = time.perf_counter() - t0
        T.save_run(prefix, res, spec, cfg)
        doc, arr = T.load_run(prefix)
        _, _, task2, _, _ = make_world(w, a.n_roi, a.n_subjects)
        chk = T.verify_roundtrip(doc, arr, task2, a.n_roi)
        with open(a.out_dir / "roundtrip.jsonl", "a") as fh:
            fh.write(json.dumps({"world": w, **chk}, ensure_ascii=False) + "\n")
        d = res["deltas"]
        g = lambda k: (f"{d[k]['mean']:+.4f} [{d[k]['ci'][1]:+.4f}, {d[k]['ci'][2]:+.4f}] sd {d[k]['sd']:.4f}" if k in d else "—")
        print(f"{w} | BEST−F4R {g('BEST − F4R (31 명, 주지표)')} | BEST-T−F4R {g('BEST-T − F4R (31 명, 공정성)')} | "
              f"status {res['verdict']['fold_status']} | roundtrip 문제 {len(chk['problems'])} | {spec['seconds']:.0f}s",
              file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
