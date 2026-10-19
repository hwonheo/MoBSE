#!/usr/bin/env python3
"""R2T T1 실제 자료 pilot 실행기 (결정 91 후보) — 잠금 대조 → 실제 자료 적재 → F4R1 → 저장 → 엄격 검증 → 결과 manifest.

* **pilot 수치 오류 정책 (wrapper, F4R1 고정본 불변)**: 적합 restart 에서 수치 실패 (numerical · nonfinite) 가 **한 건이라도**
  나오면 그 restart 직후 멈추고 (남은 restart · 다른 후보 · 후속 fold · 평가 없음) 위치 (fold · 단계 · EM a · restart seed) · 원인을 저장한다. F4R1 의 R5
  (일부 restart 수치 실패를 경고하고 진행) 는 이 pilot 에서 쓰지 않는다. 정상 비수렴 · 점유율 실패만 고정 fallback (R3).
  BEST · BEST-T 적합 중 예외도 중단 (원인 기록).
* `--make-lock`: 잠금만 만든다 (모델 적합 · 평가 없음). 이미 있으면 거부.
* 실행: 잠금의 코드 · 설정 · 설계 · 사전 점검 · 입력 파일 sha256 을 다시 대조해 하나라도 다르면 exit 2 (실행 안 함).
  검증 실패 · 판정 중단 (수치 오류) · 예외는 exit 1 과 원인 기록. 기존 출력이 있으면 거부.
설계: `docs/experiments/r2t_t1_pilot_real_design_2026-10-17.md`.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import numpy as np  # noqa: E402

import t1  # noqa: E402
import t1_rel1 as T1  # noqa: E402

CFG_PATH = ROOT / "configs/r2t/t1_pilot_real.json"
DESIGN = ROOT / "docs/experiments/r2t_t1_pilot_real_design_2026-10-17.md"
PREFLIGHT = ROOT / "results/r2t/t1_pilot_real/preflight_v2.json"
LOCK = ROOT / "results/r2t/t1_pilot_real/lock.json"
RUNNER_FILES = ("run_t1_pilot_real.py", "pilot_real_preflight.py")
TEST_FILE = ROOT / "tests/r2t/test_r2t_pilot_real_policy.py"


class NumericStop(RuntimeError):
    """pilot 정책: 수치 실패 restart 를 만나면 즉시 중단."""

    def __init__(self, record: dict):
        super().__init__("수치 실패 restart — pilot 정책으로 중단")
        self.record = record


def run_with_numeric_stop(rest, task, subjects, cfg, left):
    """F4R1 pipeline 을 그대로 돌리되 restart 함수 (`t1_reg4._one_run4`) 를 감싸, 수치 실패 restart 가 나오는 **즉시** NumericStop.

    restart 결과가 `numerical` 이거나 ok 인데 유한 · SPD 검사 (`t1_rel.fit_is_finite_spd`) 를 못 넘으면 그 restart 직후 멈춘다 —
    그 후보의 남은 restart · 다른 후보 · 후속 fold · 평가가 돌지 않는다. 반환 (결과 또는 None, 중단 기록 또는 None).
    모델 · F4R1 코드 파일은 바꾸지 않는다 (이 프로세스 안에서만 감싸고 끝나면 되돌림).
    """
    import t1_reg4 as F4
    orig_run, orig_fold = F4._one_run4, T1.run_fold
    ctx = {"fold": None, "train": None, "inner_train": None}

    def fold_wrapper(rest_, task_, train, test, masks, n_roi, cfg_, fold):
        import r2t_lib as R
        itr, _ = R.subject_split(train, cfg_["split"]["inner_val_frac"], seed=cfg_["split"]["inner_seed"])
        ctx.update(fold=fold, train=len(train), inner_train=len(itr))
        return orig_fold(rest_, task_, train, test, masks, n_roi, cfg_, fold)

    def restart_wrapper(Xw, K, seed, max_iter, tol, min_occupancy, eig_floor, a):
        r = orig_run(Xw, K, seed, max_iter, tol, min_occupancy, eig_floor, a)
        status, reason = r.status, r.reason
        if status == "ok":
            bad = T1.fit_is_finite_spd(r)
            if bad:
                status, reason = "nonfinite", bad
        if status in T1.NUMERIC:
            n_win = Xw.shape[0]
            stage = "inner" if n_win == ctx["inner_train"] * 8 else "train" if n_win == ctx["train"] * 8 else f"창 {n_win}"
            raise NumericStop({"fold": ctx["fold"], "stage": stage, "em_a": a, "restart_seed": int(seed), "status": status,
                               "reason": reason, "n_windows": int(n_win), "n_iter": int(r.n_iter)})
        return r

    F4._one_run4, T1.run_fold = restart_wrapper, fold_wrapper
    try:
        return T1.run_pipeline(rest, task, subjects, cfg, left), None
    except NumericStop as e:
        return None, e.record
    finally:
        F4._one_run4, T1.run_fold = orig_run, orig_fold
A = ROOT / "data/h1h2_scope/aomic"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_state() -> dict:
    d = ROOT / "scripts/r2t"
    pf = json.loads(PREFLIGHT.read_text())
    return {"code": {f: sha(d / f) for f in T1.CODE_FILES + RUNNER_FILES},
            "policy_test": {"path": str(TEST_FILE.relative_to(ROOT)), "sha256": sha(TEST_FILE)},
            "config": {"path": str(CFG_PATH.relative_to(ROOT)), "sha256": sha(CFG_PATH)},
            "design_doc": {"path": str(DESIGN.relative_to(ROOT)), "sha256": sha(DESIGN)},
            "preflight": {"path": str(PREFLIGHT.relative_to(ROOT)), "sha256": sha(PREFLIGHT), "ok": pf["ok"]},
            "inputs": {rel: sha(A / rel) for rel in sorted(pf["input_file_sha256"])},
            "atlas_tsv": sha(A / "atlas/tpl-MNI152NLin2009cAsym_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.tsv")}


def make_lock() -> int:
    if LOCK.exists():
        raise SystemExit(f"덮어쓰지 않는다: {LOCK}")
    st = current_state()
    pf = json.loads(PREFLIGHT.read_text())
    if not pf["ok"] or any(pf["input_file_sha256"][k] != v for k, v in st["inputs"].items()):
        raise SystemExit("사전 점검이 통과하지 않았거나 입력 해시가 사전 점검과 다르다 — 잠금 안 함")
    import numpy, scipy, sklearn
    body = {"schema": "r2t-t1-pilot-real-lock-0.1", "decision": 91, "is_lock": True,
            "created_kst": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S"),
            "scope": "PIOP1 pilot 31 명 · 사람 단위 5 fold · 15 frame 창 · ROI 20 % 가림 복원 · BEST-T 43 대 F4R1 고정 (탐색, 독립 확인 아님)",
            "primary_metric": json.loads(CFG_PATH.read_text())["primary"],
            "environment": {"python": sys.version.split()[0], "numpy": numpy.__version__, "scipy": scipy.__version__,
                            "sklearn": sklearn.__version__, "platform": platform.platform(), "OMP_NUM_THREADS": "2"},
            **st}
    canon = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
    body["lock_hash"] = hashlib.sha256(canon).hexdigest()
    LOCK.write_text(json.dumps(body, ensure_ascii=False, indent=1))
    print(f"잠금 생성 {body['lock_hash'][:12]}")
    return 0


def check_lock() -> tuple:
    lock = json.loads(LOCK.read_text())
    st = current_state()
    diff = [k for k in ("code", "policy_test", "config", "design_doc", "preflight", "inputs", "atlas_tsv") if lock[k] != st[k]]
    return lock, diff


def run() -> int:
    lock, diff = check_lock()
    if diff:
        print(f"잠금 불일치 — 실행 안 함: {diff}", file=sys.stderr)
        return 2
    cfg = t1.load_config(CFG_PATH)
    out_dir = ROOT / cfg["output"]["dir"]
    prefix = out_dir / cfg["output"]["prefix"]
    if prefix.with_suffix(".json").exists() or prefix.with_suffix(".npz").exists():
        print(f"덮어쓰지 않는다: {prefix}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "run_log.jsonl"

    def note(**kw):
        kw["kst"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%H:%M:%S")
        with open(log, "a") as fh:
            fh.write(json.dumps(kw, ensure_ascii=False) + "\n")
        print(json.dumps(kw, ensure_ascii=False), flush=True)

    state = {"finalized": False}                                            # 결과 manifest 를 쓴 뒤에는 로그에 쓰지 않는다
    note(event="시작", lock_hash=lock["lock_hash"])
    try:
        subs, rest, task = t1.load_real(cfg, ROOT, allow_real_data=True)
        left = t1.left_from_atlas_tsv(A / "atlas/tpl-MNI152NLin2009cAsym_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.tsv")
        shapes = {"task_windows": sorted({len(v) for v in task.values()}), "rest_windows": sorted({len(v) for v in rest.values()}),
                  "window_shape": sorted({w.shape for v in task.values() for w in v} | {w.shape for v in rest.values() for w in v})}
        note(event="적재", n_subjects=len(subs), **{k: str(v) for k, v in shapes.items()})
        if len(subs) != 31 or shapes["task_windows"] != [9] or shapes["rest_windows"] != [8] or shapes["window_shape"] != [(15, 100)]:
            note(event="중단", reason="적재 자료 모양이 설계와 다름")
            return 1
        t0 = time.perf_counter()
        res, stop = run_with_numeric_stop(rest, task, subs, cfg, left)
        sec = time.perf_counter() - t0
        if stop is not None:                                                # pilot 정책: 수치 실패 → 즉시 중단, 평가 · 저장 없음
            sp = out_dir / "numeric_stop.json"
            sp.write_text(json.dumps({"lock_hash": lock["lock_hash"], "seconds": sec, **stop}, ensure_ascii=False, indent=1, default=str))
            note(event="중단", reason="수치 실패 restart (pilot 정책)", where={k: stop[k] for k in ("fold", "stage", "em_a", "restart_seed")},
                 record=str(sp.relative_to(ROOT)))
            return 1
        note(event="적합 · 평가 끝", seconds=sec, verdict=res["verdict"])
        spec = {"generator": "real", "dataset": "ds002785 (PIOP1) emomatching", "lock_hash": lock["lock_hash"], "n_subjects": 31,
                "n_roi": 100, "seconds": sec}
        T1.save_run1(prefix, res, spec, cfg)
        _, _, task2 = t1.load_real(cfg, ROOT, allow_real_data=True)          # 검증은 실제 task 를 다시 읽어서
        chk = T1.verify_prefix(prefix, task2, 100)
        note(event="엄격 검증", ok=chk["ok"], n_arrays=chk["n_arrays_checked"], n_scores=chk["n_subject_scores_rechecked"],
             problems=chk["problems"][:10])
        ok = chk["ok"] and not res["verdict"]["stop"]
        note(event="완료", ok=ok, note="이 줄이 로그의 마지막 줄 — 결과 manifest 는 이 뒤에 로그를 포함해 만든다")
        files = [prefix.with_suffix(".json"), prefix.with_suffix(".npz"), log, LOCK]       # 로그를 다 쓴 뒤 해시 (순환 없음)
        man = {"schema": "r2t-t1-pilot-real-results-manifest-0.1", "lock_hash": lock["lock_hash"], "verify": chk,
               "files": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in files}}
        mp = ROOT / "results/r2t/t1_pilot_real/results_manifest.json"
        if mp.exists():
            print(f"덮어쓰지 않는다: {mp}", file=sys.stderr)
            return 1
        mp.write_text(json.dumps(man, ensure_ascii=False, indent=1))
        state["finalized"] = True
        print(f"결과 manifest {mp.relative_to(ROOT)} sha12 {sha(mp)[:12]}", flush=True)      # 로그에는 쓰지 않는다
        return 0 if ok else 1
    except Exception as e:
        if state["finalized"]:                                              # manifest 해시가 깨지지 않게 로그 대신 stderr
            print(f"manifest 작성 뒤 예외: {type(e).__name__}: {e}", file=sys.stderr)
        else:
            note(event="예외", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-2000:])
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--make-lock", action="store_true")
    a = ap.parse_args()
    return make_lock() if a.make_lock else run()


if __name__ == "__main__":
    raise SystemExit(main())
