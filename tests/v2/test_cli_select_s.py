"""`mobse-v2 select-s` — 결정 14 4c-ii (S 후보 inner 산출물 → 선택 기록).

합성 inner ``fit-s`` 디렉터리(`run_fit_s` 와 같은 세 파일)로 경계·무결성·선택 규칙
전달을 확인한다. 학습은 하지 않는다 — 선택 규칙 자체는 `test_baselines.py` 가 덮는다.
끝의 시험 하나는 실제 `fit_s` 손실이 CLI 의 재집계 함수와 같은지 본다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mobse.v2 import baselines as BL
from mobse.v2 import fitting as FIT
from mobse.v2 import templates as TPL
from mobse.v2 import train as TR
from mobse.v2.cli import (CLIError, REQUIRED_PATHS, S_FIT_SCHEMA, S_PRED_SCHEMA,
                          S_SELECTION_OUTPUT, SUBCOMMANDS, build_parser, resolve_paths,
                          run_select_s)
from mobse.v2.config import config_hash, load_config
from mobse.v2.manifests import s_fit_id

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs/redesign_v1/main.yaml"
TASKS = ("emomatching", "workingmemory")
S1, S2, S3, S4 = BL.CANDIDATE_ORDER
BEST = (S3, "C=1")          # 합성 자료에서 가장 좋은 후보/설정


def _canon(i: int) -> str:
    return f"ds002785:sub-{i:04d}"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def ws(tmp_path):
    pilot = [_canon(i) for i in range(1, 3)]
    test = [_canon(i) for i in range(3, 7)]
    train = [_canon(i) for i in range(7, 19)]
    inner = [{"inner_fold": f, "val_subjects": train[4 * f:4 * f + 4],
              "train_subjects": [s for s in train if s not in train[4 * f:4 * f + 4]]}
             for f in range(3)]
    folds = {"split_hash": "d" * 64, "pilot": {"subjects": pilot},
             "main_pool": {"subjects": test + train},
             "outer_folds": [{"outer_fold": 0, "test_subjects": test,
                              "train_subjects": train, "inner": inner}]}
    fp = tmp_path / "folds.json"
    fp.write_text(json.dumps(folds), encoding="utf-8")
    return {"tmp": tmp_path, "folds": fp, "folds_obj": folds,
            "cfg_hash": config_hash(load_config(CONFIG))}


def _p_true(cand, setting, fold, subject, task, w, best=BEST) -> float:
    key = repr((cand, setting, fold, subject, task, w)).encode()
    rng = np.random.default_rng(int(hashlib.sha256(key).hexdigest()[:8], 16))
    rank = BL.s_settings(cand)[setting][0]
    base = 0.92 if (cand, setting) == best else 0.8 - 0.01 * rank - 0.02 * BL.CANDIDATE_ORDER.index(cand)
    return float(np.clip(base + rng.uniform(-0.04, 0.04), 0.01, 0.99))


def make_fit(ws, *, cand=S1, setting="C=0.001", fold=0, seed="auto", best_epoch=None,
             converged=True, best=BEST, mutate=None, name=None):
    """`run_fit_s` 와 같은 세 파일. ``mutate(rep, rows)`` 로 어긋남을 넣는다."""
    folds = ws["folds_obj"]
    inner = folds["outer_folds"][0]["inner"][fold]
    is_log = cand in BL.LOGISTIC_CANDIDATES
    if seed == "auto":
        seed = None if is_log else TR.INNER_SEED
    sid = s_fit_id(role="inner", candidate=cand, setting_id=setting, outer_fold=0,
                   inner_fold=fold, model_seed=seed, split_hash=folds["split_hash"],
                   config_hash=ws["cfg_hash"])
    d = ws["tmp"] / "fits" / (name or sid)
    d.mkdir(parents=True, exist_ok=False)
    model = d / "s_model.npz"
    model.write_bytes(b"model-" + sid.encode())
    rows, run_p = [], {}
    for s in inner["val_subjects"]:
        sub = s.split(":")[1]
        for task in TASKS:
            rk = f"ds002785/{sub}/na/{task}/na/seq"
            truth = FIT.class_index(task)
            ps = []
            for w in range(4):
                pt = _p_true(cand, setting, fold, s, task, w, best)
                p1 = pt if truth == 1 else 1.0 - pt
                ps.append(p1)
                rows.append({"schema_version": S_PRED_SCHEMA, "canonical_subject": s,
                             "group_id": s, "run_key": rk, "window_key": f"{rk}#win-{w}",
                             "truth": truth, "p_class1": p1, "candidate": cand,
                             "setting_id": setting, "scope": "inner_validation",
                             "model_sha256": _sha(model), "s_fit_id": sid})
            run_p[rk] = float(np.mean(ps))
    rep = {"schema_version": S_FIT_SCHEMA, "s_fit_id": sid, "candidate": cand,
           "feature": BL.CANDIDATE_FEATURE[cand], "setting_id": setting,
           "setting_rank": BL.s_settings(cand)[setting][0], "role": "inner",
           "eval_role": "inner_validation",
           "folds": {"outer_fold": 0, "inner_fold": fold,
                     "n_train_subjects": len(inner["train_subjects"]), "n_eval_subjects": 4},
           "model_seed": seed, "converged": converged,
           "best_epoch": None if is_log else (best_epoch or 300 + fold),
           "eval_loss": BL.inner_loss(run_p), "fit_subjects": list(inner["train_subjects"]),
           "model_sha256": _sha(model), "code_hash": "c" * 64, "env_hash": "e" * 64,
           "config_hash": ws["cfg_hash"], "source_hash": "s" * 64,
           "split_hash": folds["split_hash"]}
    if mutate:
        mutate(rep, rows)
    pred = d / "s_window_predictions.jsonl"
    pred.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    rep.setdefault("window_predictions_sha256", _sha(pred))
    (d / "s_fit_report.json").write_text(json.dumps(rep), encoding="utf-8")
    return d / "s_fit_report.json"


def full_grid(ws, skip=(), **kw):
    return [make_fit(ws, cand=c, setting=s, fold=f, **kw)
            for c in BL.CANDIDATE_ORDER for s in BL.s_settings(c)
            for f in range(3) if (c, s, f) not in skip]


def run(ws, reports, *, outer=0, out=None):
    out = out or ws["tmp"] / "sel_s"
    ns = build_parser().parse_args(
        ["select-s", "--config", str(CONFIG), "--splits", str(ws["folds"]),
         "--output-dir", str(out), "--outer-fold", str(outer),
         "--fit-report"] + [str(r) for r in reports])
    return run_select_s(resolve_paths("select-s", ns), ns), out


def _rec(out):
    return json.loads((out / S_SELECTION_OUTPUT).read_text())


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def test_subcommand_is_registered_with_required_paths():
    assert "select-s" in SUBCOMMANDS
    assert REQUIRED_PATHS["select-s"] == ("config", "splits", "fit_report", "output_dir")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["select-s"])


# --------------------------------------------------------------------------- #
# 정상 경로
# --------------------------------------------------------------------------- #

def test_selection_record_matches_library_selection(ws):
    res, out = run(ws, full_grid(ws))
    rec = _rec(out)
    assert res["verdict"] == "pass" and res["n_inputs"] == 96
    assert (rec["selected_candidate"], rec["selected_setting_id"]) == BEST
    assert rec["n_excluded"] == 0 and rec["excluded"] == []
    assert len(rec["table"]) == 32 and len({i["s_fit_id"] for i in rec["inputs"]}) == 96
    assert rec["rules"]["run_aggregation"].startswith("fitting.run_probabilities")


def test_logistic_outer_plan_is_single_fit_without_seed_or_epochs(ws):
    _, out = run(ws, full_grid(ws))
    rec = _rec(out)
    assert rec["best_epochs"] is None and rec["outer_epochs"] is None
    (p,) = rec["outer_plan"]
    assert p["model_seed"] is None and p["inner_fold"] == TPL.OUTER_FIT_INNER_FOLD
    assert "--model-seed" not in p["cli"] and "--epochs" not in p["cli"]
    ns = build_parser().parse_args(p["cli"] + [
        "--config", "c", "--splits", "s", "--subjects", "s", "--windows", "w",
        "--output-dir", "o", "--task-manifests", "t"])
    assert (ns.candidate, ns.setting_id, ns.inner_fold) == (S3, "C=1", 9)


def test_mlp_outer_plan_uses_locked_seeds_and_baseline_epochs(ws):
    best = (S4, "config=2")
    reps = [make_fit(ws, cand=c, setting=s, fold=f, best=best,
                     best_epoch=(310, 330, 320)[f] if (c, s) == best else None)
            for c in BL.CANDIDATE_ORDER for s in BL.s_settings(c) for f in range(3)]
    _, out = run(ws, reps)
    rec = _rec(out)
    assert (rec["selected_candidate"], rec["selected_setting_id"]) == best
    assert rec["best_epochs"] == [310, 330, 320]
    assert rec["outer_epochs"] == TR.baseline_epochs([310, 330, 320]) == 320
    assert [p["model_seed"] for p in rec["outer_plan"]] == list(TR.MODEL_SEEDS)
    for p in rec["outer_plan"]:
        ns = build_parser().parse_args(p["cli"] + [
            "--config", "c", "--splits", "s", "--subjects", "s", "--windows", "w",
            "--output-dir", "o", "--task-manifests", "t"])
        assert (ns.candidate, ns.setting_id, ns.epochs, ns.inner_fold) == (S4, "config=2",
                                                                          320, 9)


def test_outer_plan_seeds_follow_train_constant(ws, monkeypatch):
    best = (S2, "config=0")
    monkeypatch.setattr(TR, "MODEL_SEEDS", (42, 43))
    reps = [make_fit(ws, cand=c, setting=s, fold=f, best=best)
            for c in BL.CANDIDATE_ORDER for s in BL.s_settings(c) for f in range(3)]
    _, out = run(ws, reps)
    assert [p["model_seed"] for p in _rec(out)["outer_plan"]] == [42, 43]


def test_unconverged_setting_is_excluded_and_counted(ws):
    """최선 설정의 fold 하나가 미수렴이면 그 설정 전체가 빠지고 수가 기록된다 (P11)."""
    reps = full_grid(ws, skip={(S3, "C=1", 1)}) + [
        make_fit(ws, cand=S3, setting="C=1", fold=1, converged=False)]
    _, out = run(ws, reps)
    rec = _rec(out)
    assert rec["excluded"] == [f"{S3}/C=1"] and rec["n_excluded"] == 1
    assert (rec["selected_candidate"], rec["selected_setting_id"]) != BEST


def test_record_is_not_overwritten(ws):
    reps = full_grid(ws)
    _, out = run(ws, reps)
    with pytest.raises(CLIError, match="덮어쓰지 않는다"):
        run(ws, reps, out=out)


# --------------------------------------------------------------------------- #
# 경계·무결성 — 조용히 통과하면 안 되는 것
# --------------------------------------------------------------------------- #

def _swap(ws, key, **kw):
    c, s, f = key
    return full_grid(ws, skip={key}) + [make_fit(ws, cand=c, setting=s, fold=f, **kw)]


def test_incomplete_grid_is_refused(ws):
    with pytest.raises(CLIError, match="불완전한 grid"):
        run(ws, full_grid(ws, skip={(S2, "config=5", 2)}))


def test_duplicate_report_is_refused(ws):
    reps = full_grid(ws)
    with pytest.raises(CLIError, match="s_fit_id 중복"):
        run(ws, reps + [reps[0]])


def test_outer_fit_is_refused(ws):
    def m(rep, rows):
        rep["role"] = "outer"
    with pytest.raises(CLIError, match="inner fit 이 아니다"):
        run(ws, _swap(ws, (S1, "C=10", 0), mutate=m))


def test_wrong_outer_fold_is_refused(ws):
    with pytest.raises(CLIError, match="--outer-fold"):
        run(ws, full_grid(ws), outer=1)


def test_mlp_non_inner_seed_is_refused(ws):
    with pytest.raises(CLIError, match="inner seed"):
        run(ws, _swap(ws, (S2, "config=1", 1), seed=43))


def test_logistic_with_seed_is_refused(ws):
    def m(rep, rows):
        rep["model_seed"] = 42
    with pytest.raises(CLIError, match="logistic"):
        run(ws, _swap(ws, (S1, "C=1", 2), mutate=m))


def test_report_setting_must_match_fit_id(ws):
    """보고서의 setting_id 를 바꿔 치면 s_fit_id 재계산이 어긋나 거부된다."""
    def m(rep, rows):
        rep["setting_id"] = "C=100"
        rep["setting_rank"] = 5
        for r in rows:
            r["setting_id"] = "C=100"
    with pytest.raises(CLIError, match="s_fit_id 가 다르다"):
        run(ws, _swap(ws, (S1, "C=10", 0), mutate=m))


def test_setting_rank_mismatch_is_refused(ws):
    def m(rep, rows):
        rep["setting_rank"] = 0
    with pytest.raises(CLIError, match="setting_rank"):
        run(ws, _swap(ws, (S3, "C=10", 0), mutate=m))


def test_loss_mismatch_with_report_is_refused(ws):
    def m(rep, rows):
        rep["eval_loss"] += 1e-3
    with pytest.raises(CLIError, match="eval_loss"):
        run(ws, _swap(ws, (S4, "config=7", 2), mutate=m))


def test_missing_validation_subject_is_refused(ws):
    def m(rep, rows):
        drop = rows[0]["canonical_subject"]
        rows[:] = [r for r in rows if r["canonical_subject"] != drop]
    with pytest.raises(CLIError, match="inner validation subject"):
        run(ws, _swap(ws, (S1, "C=0.1", 1), mutate=m))


def test_outer_test_scope_row_is_refused(ws):
    def m(rep, rows):
        rows[3]["scope"] = "outer_test"
    with pytest.raises(CLIError, match="scope"):
        run(ws, _swap(ws, (S2, "config=3", 0), mutate=m))


def test_fit_subjects_must_match_folds(ws):
    def m(rep, rows):
        rep["fit_subjects"] = rep["fit_subjects"][:-1]
    with pytest.raises(CLIError, match="fit_subjects"):
        run(ws, _swap(ws, (S3, "C=0.01", 2), mutate=m))


def test_mixed_code_hash_is_refused(ws):
    def m(rep, rows):
        rep["code_hash"] = "f" * 64
    with pytest.raises(CLIError, match="code_hash"):
        run(ws, _swap(ws, (S4, "config=0", 1), mutate=m))


def test_missing_neighbour_file_is_refused_without_search(ws):
    reps = full_grid(ws)
    (reps[5].parent / "s_window_predictions.jsonl").unlink()
    with pytest.raises(CLIError, match="U20"):
        run(ws, reps)


def test_model_file_hash_mismatch_is_refused(ws):
    reps = full_grid(ws)
    (reps[7].parent / "s_model.npz").write_bytes(b"tampered")
    with pytest.raises(CLIError, match="s_model.npz"):
        run(ws, reps)


def test_prediction_file_hash_mismatch_is_refused(ws):
    def m(rep, rows):
        rep["window_predictions_sha256"] = "0" * 64
    with pytest.raises(CLIError, match="s_window_predictions.jsonl sha256"):
        run(ws, _swap(ws, (S1, "C=1000", 0), mutate=m))


def test_truth_must_follow_task(ws):
    def m(rep, rows):
        rows[0]["truth"] = 1 - rows[0]["truth"]
    with pytest.raises(CLIError, match="truth"):
        run(ws, _swap(ws, (S2, "config=6", 1), mutate=m))


def test_mlp_best_epoch_out_of_range_is_refused(ws):
    with pytest.raises(CLIError, match="best_epoch"):
        run(ws, _swap(ws, (S4, "config=4", 0), best_epoch=TR.MAX_EPOCHS + 1))


# --------------------------------------------------------------------------- #
# 라이브러리 — outer 계획, 실제 fit_s 손실과 CLI 재집계의 일치
# --------------------------------------------------------------------------- #

def test_s_outer_plan_guards():
    with pytest.raises(BL.BaselineError, match="logistic"):
        BL.s_outer_plan(S1, "C=1", [300, 300, 300])
    with pytest.raises(BL.BaselineError, match="3 개"):
        BL.s_outer_plan(S2, "config=0", [300, 300])
    with pytest.raises(BL.BaselineError, match="grid 밖"):
        BL.s_outer_plan(S2, "C=1", [300, 300, 300])
    assert BL.s_outer_plan(S1, "C=1") == [{"candidate": S1, "setting_id": "C=1",
                                           "model_seed": None, "epochs_exact": None}]


def test_s_outer_plan_refuses_each_best_epoch_out_of_range():
    """중앙값(outer E)이 범위 안이어도 inner best epoch 하나가 1–MAX_EPOCHS 밖이면 거부 (결정 16 재점검에서 보강).

    [1, 1, MAX+1] 과 [0, 300, 300] 은 중앙값 올림이 1·300 이라 outer E 범위 검사만으로는 통과한다.
    """
    for epochs in ([1, 1, TR.MAX_EPOCHS + 1], [0, 300, 300]):
        assert 1 <= TR.baseline_epochs(epochs) <= TR.MAX_EPOCHS
        with pytest.raises(BL.BaselineError, match="best epoch 가 1"):
            BL.s_outer_plan(S2, "config=0", epochs)


def test_real_fit_s_loss_matches_cli_run_aggregation():
    """`fit_s` 의 eval_loss 가 CLI 가 쓰는 `fitting.run_probabilities` 재집계와 같다."""
    rng = np.random.default_rng(5)
    keys, refs = [], []
    for i in range(6):
        for task in TASKS:
            rk = f"ds002785/sub-{i:04d}/na/{task}/na/seq"
            for w in range(4):
                keys.append(rk)
                refs.append(FIT.WindowRef(window_key=f"{rk}#win-{w}", run_key=rk,
                                          canonical_subject=f"ds002785:sub-{i:04d}",
                                          task=task, path=Path(""), sha256="",
                                          label=FIT.class_index(task)))
    y = np.array([r.label for r in refs])
    X = rng.standard_normal((len(refs), 10)) + y[:, None] * 0.7
    res = BL.fit_s(X, list(y), X, keys, candidate=S1, setting_id="C=1", role="inner")
    loss = BL.inner_loss(FIT.run_probabilities(refs, list(res.eval_window_p1)))
    assert abs(loss - res.eval_loss) < 1e-9
