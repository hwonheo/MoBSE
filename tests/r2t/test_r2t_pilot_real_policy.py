"""R2T 실제 자료 pilot 실행 wrapper 의 수치 오류 정책 시험 — **합성 자료만** (실제 자료 없음).

정책: 수치 실패 restart 가 한 건이라도 → 즉시 중단 (위치 · 원인 기록, 결과 없음). F4R1 의 R5 (경고 후 진행) 를 쓰지 않는다.
정상 비수렴 · 점유율 실패만 고정 fallback. 수치 실패가 없으면 결과는 F4R1 `run_pipeline` 과 같다.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import mix as M  # noqa: E402
import run_t1_pilot_real as RP  # noqa: E402
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg4 as F4  # noqa: E402
import t1_rel1 as T1  # noqa: E402

CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_real.json")


def world():
    return ST.make(n_subjects=15, n_roi=20, n_states=3, seed=61)


def test_pilot_config_excludes_oracle_and_keeps_records():
    assert CFG["reliability"]["selection_audit"] is False and CFG["reliability"]["keep_predictions"] is True
    assert CFG["reliability"]["best_tuned"] is True and CFG["primary"]["metric"] == "BEST-T − F4R (31 명, 공정성)"
    assert CFG["output"]["dir"].startswith("data/")


def test_no_numeric_failure_equals_f4r1():
    ids, rest, task, left = world()
    res, stop = RP.run_with_numeric_stop(rest, task, ids, CFG, left)
    ref = T1.run_pipeline(rest, task, ids, CFG, left)
    assert stop is None and res["per_subject_nmse"] == ref["per_subject_nmse"] and res["deltas"] == ref["deltas"]
    assert F4._one_run4.__module__ == "t1_reg4" and T1.run_fold.__module__ == "t1_rel1"      # 감싼 함수 복원


def test_single_numeric_restart_stops_immediately_with_location(monkeypatch):
    """F4R1 단독이면 R5 경고로 진행할 상황 — pilot wrapper 는 멈춘다."""
    ids, rest, task, left = world()
    orig = F4._one_run4
    calls = {"n": 0}

    def one_bad(Xw, K, seed, *a):
        calls["n"] += 1
        if calls["n"] == 3:                                                 # 첫 후보의 세 번째 restart 만 수치 실패
            return M.MixFit(K, np.empty((0,)), np.empty((0,)), -np.inf, 0, False, "numerical", "LinAlgError('주입: 비 SPD')",
                            np.empty((0,)), np.empty((0,)))
        return orig(Xw, K, seed, *a)
    monkeypatch.setattr(F4, "_one_run4", one_bad)
    evals = {"n": 0}
    orig_eval = T1.eval_keep

    def count_eval(*a, **k):
        evals["n"] += 1
        return orig_eval(*a, **k)
    monkeypatch.setattr(T1, "eval_keep", count_eval)
    res, stop = RP.run_with_numeric_stop(rest, task, ids, CFG, left)
    assert res is None and stop["fold"] == 0 and stop["stage"] == "inner" and stop["em_a"] is None
    assert stop["restart_seed"] == CFG["mix"]["em_seed"] + 2 and stop["status"] == "numerical" and "주입: 비 SPD" in stop["reason"]
    assert calls["n"] == 3                                                  # 수치 실패 restart 직후 멈춤 — 남은 restart · 다른 후보 · fold 없음
    assert evals["n"] == 2                                                  # fold 0 의 BEST · BEST-T test 평가뿐 (F4R1 평가 · 다른 fold 없음)
    assert F4._one_run4 is one_bad and T1.run_fold.__module__ == "t1_rel1"   # wrapper 가 감싼 함수를 되돌림


def test_nonfinite_ok_restart_also_stops(monkeypatch):
    ids, rest, task, left = world()
    orig = F4._one_run4

    def nan_ok(Xw, K, seed, *a):
        f = orig(Xw, K, seed, *a)
        if f.status == "ok":
            f.loglik = float("nan")
        return f
    monkeypatch.setattr(F4, "_one_run4", nan_ok)
    res, stop = RP.run_with_numeric_stop(rest, task, ids, CFG, left)
    assert res is None and stop["status"] == "nonfinite" and stop["restart_seed"] == CFG["mix"]["em_seed"]


def test_normal_failure_uses_fixed_fallback_not_stop():
    ids, rest, task, left = world()
    c = copy.deepcopy(CFG)
    c["mix"]["min_occupancy"] = 0.5
    res, stop = RP.run_with_numeric_stop(rest, task, ids, c, left)
    assert stop is None and res["verdict"]["fold_status"] == ["fallback"] * 5 and not res["verdict"]["stop"]
    d = res["deltas"]["BEST-T − F4R (31 명, 공정성)"]
    assert d["n"] == 15                                                     # fallback 사람도 분모에 포함
    best, bt = res["per_subject_nmse"]["BEST"], res["per_subject_nmse"]["BEST-T"]
    assert all(np.isclose(d["per_subject"][s], bt[s] - best[s], atol=0) for s in ids)   # fallback Δ = BEST-T − BEST


def test_numeric_failure_in_train_refit_stage_located(monkeypatch):
    ids, rest, task, left = world()
    orig = F4._one_run4
    n_train = 12 * 8

    def bad_train(Xw, K, seed, *a):
        if Xw.shape[0] == n_train:
            return M.MixFit(K, np.empty((0,)), np.empty((0,)), -np.inf, 0, False, "numerical", "FloatingPointError('주입')",
                            np.empty((0,)), np.empty((0,)))
        return orig(Xw, K, seed, *a)
    monkeypatch.setattr(F4, "_one_run4", bad_train)
    res, stop = RP.run_with_numeric_stop(rest, task, ids, CFG, left)
    assert res is None and stop["fold"] == 0 and stop["stage"] == "train" and stop["restart_seed"] == CFG["mix"]["em_seed"]


def test_finalization_order_log_then_manifest():
    import inspect
    src = inspect.getsource(RP.run)
    assert src.index('note(event="완료"') < src.index("files = [prefix.with_suffix")
    tail = src[src.index("mp.write_text"):src.index("except Exception")]
    assert "note(" not in tail and 'state["finalized"] = True' in tail     # manifest 뒤 정상 경로에서 로그 쓰기 없음
    exc = src[src.index("except Exception"):]
    assert exc.index('if state["finalized"]') < exc.index("note(")           # 예외 경로도 manifest 뒤에는 로그에 안 씀
