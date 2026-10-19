"""R2T T1 검증기 패치 F4R1 시험 — 합성 자료만. 사전 규칙: `docs/experiments/r2t_t1_rel1_patch_2026-10-17.md` 0 절.

* 엄격 검증: 누락 · 여분 · shape · dtype · 비유한 · 손상 npz · npz 없음 · 재계산 불일치 · 기록 누락 · Δ 변조 → 명시적 실패
* 상태별 예상 배열: fallback (F4R = BEST), 중단 (F4R 없어야 함)
* 실행기 · 읽기 검증 종료 코드 (실패 → 1)
* oracle 재적합 실패 기록 · F4R 과의 동치
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "r2t"))
import mix as M  # noqa: E402
import synth_t1 as ST  # noqa: E402
import t1  # noqa: E402
import t1_reg4 as F4  # noqa: E402
import t1_rel as T  # noqa: E402
import t1_rel1 as T1  # noqa: E402

CFG = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_rel.json")
SPEC = {"generator": "eval_t1_worlds.world", "kind": "pos", "seed": 61, "n_roi": 20, "n_subjects": 15}
PY = str(ROOT / ".venv" / "bin" / "python")


def world():
    return ST.make(n_subjects=15, n_roi=20, n_states=3, seed=61)        # = eval_t1_worlds.world("pos", 61, 20, 15)


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    ids, rest, task, left = world()
    out = {"ok": T1.run_pipeline(rest, task, ids, CFG, left)}
    c = copy.deepcopy(CFG)
    c["mix"]["min_occupancy"] = 0.5
    out["fallback"] = (T1.run_pipeline(rest, task, ids, c, left), c)
    with pytest.MonkeyPatch.context() as mp:
        def boom(*a, **k):
            raise np.linalg.LinAlgError("주입: 비 SPD")
        mp.setattr(F4, "_m", boom)
        c2 = copy.deepcopy(CFG)
        c2["reliability"]["selection_audit"] = False
        out["stop"] = (T1.run_pipeline(rest, task, ids, c2, left), c2)
    d = tmp_path_factory.mktemp("rel1")
    T1.save_run1(d / "ok", out["ok"], SPEC, CFG)
    T1.save_run1(d / "fallback", out["fallback"][0], SPEC, out["fallback"][1])
    T1.save_run1(d / "stop", out["stop"][0], SPEC, out["stop"][1])
    return out, d, task


def clone(d: Path, name: str, tmp: Path) -> Path:
    for ext in (".json", ".npz"):
        shutil.copy(d / f"{name}{ext}", tmp / f"{name}{ext}")
    return tmp / name


def rewrite_npz(prefix: Path, fn):
    arr = dict(np.load(prefix.with_suffix(".npz")))
    fn(arr)
    prefix.with_suffix(".npz").unlink()
    np.savez_compressed(prefix.with_suffix(".npz"), **arr)


def problems(prefix, task):
    r = T1.verify_prefix(prefix, task, 20)
    assert r["ok"] == (not r["problems"])
    return r["problems"]


# ---------------------------------------------------------------- 정상 판 · 상태별 예상 배열

def test_clean_runs_pass_all_states(runs):
    _, d, task = runs
    for name, n_arr in (("ok", 15), ("fallback", 15), ("stop", 10)):
        r = T1.verify_prefix(d / name, task, 20)
        assert r["ok"] and r["problems"] == [] and r["n_arrays_checked"] == n_arr, (name, r["problems"][:3])
    doc = json.loads((d / "stop.json").read_text())
    assert set(doc["verdict"]["fold_status"]) == {"stop_numerical"}
    assert not any(k.endswith("__F4R") for k in np.load(d / "stop.npz").files)


def test_old_verifier_lets_missing_array_pass(runs, tmp_path):
    """결함 재현 (0.1-1): F4R 의 `verify_roundtrip` 은 배열이 없으면 넘어간다. F4R1 은 실패시킨다."""
    _, d, task = runs
    p = clone(d, "ok", tmp_path)
    rewrite_npz(p, lambda a: a.pop("fold0__F4R"))
    doc, arr = T.load_run(p)
    assert T.verify_roundtrip(doc, arr, task, 20)["problems"] == []
    assert any("F4R 예측 배열 누락" in x for x in problems(p, task))


# ---------------------------------------------------------------- 주입 → 명시적 실패

@pytest.mark.parametrize("label,mutate,expect", [
    ("누락", lambda a: a.pop("fold2__BEST-T"), "BEST-T 예측 배열 누락"),
    ("shape", lambda a: a.__setitem__("fold1__BEST", a["fold1__BEST"][:, :, :, :, :-1]), "shape"),
    ("비유한", lambda a: a["fold3__F4R"].__setitem__((0, 0, 0, 0, 0), np.nan), "비유한 값"),
    ("dtype", lambda a: a.__setitem__("fold0__BEST", a["fold0__BEST"].astype(np.int64)), "dtype"),
    ("재계산", lambda a: a["fold4__F4R"].__setitem__((1, 2, 3, 4, 0), a["fold4__F4R"][1, 2, 3, 4, 0] + 1e-9), "재계산"),
    ("여분", lambda a: a.__setitem__("fold0__EXTRA", np.zeros(3)), "예상하지 않은 배열"),
])
def test_injected_array_defects_fail(runs, tmp_path, label, mutate, expect):
    _, d, task = runs
    p = clone(d, "ok", tmp_path)
    rewrite_npz(p, mutate)
    pr = problems(p, task)
    assert pr and any(expect in x for x in pr), (label, pr[:3])


def test_corrupted_or_missing_npz_fails_without_exception(runs, tmp_path):
    _, d, task = runs
    p = clone(d, "ok", tmp_path)
    b = p.with_suffix(".npz").read_bytes()
    p.with_suffix(".npz").write_bytes(b[: len(b) // 2])
    pr = problems(p, task)
    assert any("npz 읽기 실패" in x for x in pr)
    p.with_suffix(".npz").unlink()
    assert problems(p, task) == ["npz 파일 없음"]
    p.with_suffix(".json").write_text("{깨진")
    assert any("json 읽기 실패" in x for x in problems(p, task))


def test_record_side_defects_fail(runs, tmp_path):
    _, d, task = runs
    p = clone(d, "ok", tmp_path)
    doc = json.loads(p.with_suffix(".json").read_text())
    good = copy.deepcopy(doc)
    doc["folds"][1]["nmse"].pop("F4R")
    p.with_suffix(".json").write_text(json.dumps(doc, ensure_ascii=False))
    assert any("기록 누락" in x for x in problems(p, task))
    doc = copy.deepcopy(good)
    doc["deltas"]["BEST − F4R (31 명, 주지표)"]["sd"] += 1e-6
    p.with_suffix(".json").write_text(json.dumps(doc, ensure_ascii=False))
    assert any("Δ 재계산 불일치" in x for x in problems(p, task))
    doc = copy.deepcopy(good)
    doc["deltas"].pop("BEST-T − F4R (31 명, 공정성)")
    p.with_suffix(".json").write_text(json.dumps(doc, ensure_ascii=False))
    assert any("Δ 기록 누락" in x for x in problems(p, task))
    doc = copy.deepcopy(good)
    doc["folds"][0]["F4R"]["fold_status"] = "weird"
    p.with_suffix(".json").write_text(json.dumps(doc, ensure_ascii=False))
    assert any("알 수 없는 상태" in x for x in problems(p, task))


def test_fallback_and_stop_state_rules(runs, tmp_path):
    _, d, task = runs
    p = clone(d, "fallback", tmp_path)
    rewrite_npz(p, lambda a: a.__setitem__("fold0__F4R", a["fold0__F4R"] * 1.0001))
    pr = problems(p, task)
    assert any("fallback 인데 F4R 배열 ≠ BEST" in x for x in pr)
    p = clone(d, "fallback", tmp_path)
    rewrite_npz(p, lambda a: a.pop("fold3__F4R"))
    assert any("F4R 예측 배열 누락" in x for x in problems(p, task))
    p = clone(d, "stop", tmp_path)
    rewrite_npz(p, lambda a: a.__setitem__("fold2__F4R", a["fold2__BEST"]))
    assert any("상태 stop_numerical 인데 F4R 배열이 있음" in x for x in problems(p, task))


# ---------------------------------------------------------------- 종료 코드

def test_verify_script_exit_codes(runs, tmp_path):
    _, d, task = runs
    good = tmp_path / "good"
    good.mkdir()
    clone(d, "ok", good)
    rep = tmp_path / "rep_good.json"
    r = subprocess.run([PY, "-B", str(ROOT / "scripts/r2t/verify_t1_rel1.py"), "--runs", str(good / "ok.json"), "--report", str(rep)],
                       capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "2", "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr[-500:]
    assert json.loads(rep.read_text())["n_failed"] == 0
    bad = tmp_path / "bad"
    bad.mkdir()
    p = clone(d, "ok", bad)
    rewrite_npz(p, lambda a: a.pop("fold0__BEST"))
    rep2 = tmp_path / "rep_bad.json"
    r = subprocess.run([PY, "-B", str(ROOT / "scripts/r2t/verify_t1_rel1.py"), "--runs", str(p.with_suffix(".json")), "--report", str(rep2)],
                       capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "2", "PATH": "/usr/bin:/bin"})
    assert r.returncode == 1 and json.loads(rep2.read_text())["n_failed"] == 1
    r = subprocess.run([PY, "-B", str(ROOT / "scripts/r2t/verify_t1_rel1.py"), "--runs", str(p.with_suffix(".json")), "--report", str(rep2)],
                       capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    assert r.returncode != 0 and "덮어쓰지 않는다" in r.stderr


def test_runner_propagates_failure_as_exit_1(runs, tmp_path, monkeypatch):
    import eval_t1_rel1 as ER1
    out, d, task = runs
    good = copy.deepcopy(out["ok"])
    monkeypatch.setattr(ER1.T1, "run_pipeline", lambda *a, **k: copy.deepcopy(good))
    assert ER1.main(["--worlds", "pos:61", "--n-roi", "20", "--n-subjects", "15", "--tag", "시험", "--out-dir", str(tmp_path / "g")]) == 0
    broken = copy.deepcopy(good)
    broken["folds"][0]["pred"].pop("F4R")
    monkeypatch.setattr(ER1.T1, "run_pipeline", lambda *a, **k: copy.deepcopy(broken))
    assert ER1.main(["--worlds", "pos:61", "--n-roi", "20", "--n-subjects", "15", "--tag", "시험", "--out-dir", str(tmp_path / "b")]) == 1
    rec = json.loads((tmp_path / "b" / "verify.jsonl").read_text().splitlines()[0])
    assert not rec["ok"] and any("F4R 예측 배열 누락" in x for x in rec["problems"])

    def raise_(*a, **k):
        raise RuntimeError("주입 예외")
    monkeypatch.setattr(ER1.T1, "run_pipeline", raise_)
    assert ER1.main(["--worlds", "pos:61", "--n-roi", "20", "--n-subjects", "15", "--tag", "시험", "--out-dir", str(tmp_path / "e")]) == 1
    rec = json.loads((tmp_path / "e" / "verify.jsonl").read_text().splitlines()[0])
    assert "주입 예외" in rec["problems"][0]


# ---------------------------------------------------------------- oracle 기록 · 동치

def test_same_as_f4r_plus_oracle_records(runs):
    out, d, task = runs
    ids, rest, task0, left = world()
    old = T.run_pipeline(rest, task0, ids, CFG, left)
    new = out["ok"]
    assert old["per_subject_nmse"] == new["per_subject_nmse"]
    for fo, fn in zip(old["folds"], new["folds"]):
        for k in ("pick", "inner_scores", "test_scores", "inner_fits", "train_fit", "fold_status"):
            assert fo["F4R"][k] == fn["F4R"][k], k
        for lab in ("BEST", "BEST-T"):
            assert fo[lab] == fn[lab]
        assert "oracle_refits" in fn["F4R"] and "oracle_refits" not in fo["F4R"]
        assert fn["F4R"]["oracle_refits"][fn["F4R"]["pick"].split("|")[0][2:]]["same_as"] == "train_fit"


def test_oracle_refit_failures_are_recorded(monkeypatch):
    ids, rest, task, left = world()
    orig = T1.fit_candidate
    state = {"seen_train": False}
    n_train = 12 * 8

    def wrapper(Xw, K, a, kw):
        if Xw.shape[0] != n_train:
            state["seen_train"] = False
            return orig(Xw, K, a, kw)
        if not state["seen_train"]:                                        # fold 의 선택 a 재적합 (첫 train 크기 호출)
            state["seen_train"] = True
            return orig(Xw, K, a, kw)
        rec = {"status": "failed", "counts": {"numerical": 10}, "numeric_failures": 10,
               "restarts": [{"seed": 1 + i, "status": "numerical", "reason": "LinAlgError('주입 oracle')", "n_iter": 0,
                             "loglik": None, "occupancy": None} for i in range(10)]}
        return None, rec
    monkeypatch.setattr(T1, "fit_candidate", wrapper)
    res = T1.run_pipeline(rest, task, ids, CFG, left)
    for f, aud in zip(res["folds"], res["selection_audit"]):
        mr = f["F4R"]
        assert mr["fold_status"] == "ok"                                   # 진단 실패는 선택 · 판정에 영향 없음
        of = mr["oracle_failures"]
        assert of["n_failed_a"] >= 1 and of["n_numeric_restarts"] == 10 * of["n_failed_a"] and of["candidate_set_reduced"]
        for a in of["failed_a"]:
            assert "주입 oracle" in mr["oracle_refits"][a]["restarts"][0]["reason"]
        assert aud["F4R"]["oracle_candidate_set_reduced"] is True
        assert all(not name.startswith(tuple(f"a={a}|" for a in of["failed_a"])) for name, _ in mr["test_scores"])
