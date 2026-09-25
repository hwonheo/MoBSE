"""S outer fit 산출물 → 보조 비교 집계 helper (남은 작업 2-c, 09-25 15:15).

`cli._load_s_outer` 가 outer fold 별 `s_selection.json` outer 계획 (fold 마다 후보가
다를 수 있음 — logistic 1 fit / MLP seed 3 fit)·`s_fit_report.json`·이웃 파일을
검사하고 `evaluate.aggregate_comparison_runs(cell="S")` 로 run 을 만드는지 합성 자료로
본다. 실자료 fit 은 없다 (main pool 미소비).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from mobse.v2 import baselines as BL
from mobse.v2 import cli
from mobse.v2 import evaluate as EV
from mobse.v2 import train as TR
from mobse.v2.config import config_hash, load_config
from mobse.v2.evaluate import CLASSIFICATION_TASKS
from mobse.v2.manifests import s_fit_id

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "redesign_v1" / "main.yaml"
SEEDS = (42, 43, 44)
SPLIT_HASH = "d" * 64
LOGI, MLP = BL.CANDIDATE_ORDER[0], BL.CANDIDATE_ORDER[1]
LOGI_SET, MLP_SET = "C=0.1", "config=3"
E = 297

pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _canon(i: int) -> str:
    return f"ds002785:sub-{i:04d}"


def _run_key(subject: str, task: str) -> str:
    return f"ds002785/{subject.split(':')[1]}/na/{task}/na/seq"


def _prob(subject: str, task: str, window: int, seed) -> float:
    """sub 짝수의 WM 은 틀린다 (0.3 쪽), 나머지는 맞힌다."""
    truth = CLASSIFICATION_TASKS.index(task)
    wrong = task == "workingmemory" and int(subject[-4:]) % 2 == 0
    base = 0.8 if (truth == 1) != wrong else 0.2
    s = 43 if seed is None else seed
    return round(base + 0.01 * (window - 1.5) + 0.005 * (s - 43), 6)


def _plan_row(cand, setting, of, seed, e):
    return {"candidate": cand, "setting_id": setting, "model_seed": seed,
            "epochs_exact": e, "outer_fold": of, "inner_fold": 9}


def _selection(of, cfg_hash, cand, *, seeds=SEEDS):
    if cand in BL.LOGISTIC_CANDIDATES:
        rows, e, setting = [_plan_row(cand, LOGI_SET, of, None, None)], None, LOGI_SET
    else:
        rows = [_plan_row(cand, MLP_SET, of, s, E) for s in seeds]
        e, setting = E, MLP_SET
    return {"schema_version": cli.S_SELECTION_SCHEMA, "outer_fold": of,
            "split_hash": SPLIT_HASH, "config_hash": cfg_hash,
            "selected_candidate": cand, "selected_setting_id": setting,
            "outer_epochs": e, "outer_plan": rows}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write_rows(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _make_fit(root: Path, fold, cand, setting, seed, cfg_hash) -> Path:
    of = fold["outer_fold"]
    d = root / f"S_o{of}_s{seed}"
    d.mkdir(parents=True)
    model = d / "s_model.npz"
    model.write_bytes(f"S{of}{seed}".encode())
    msha = _sha(model)
    sid = s_fit_id(role="outer", candidate=cand, setting_id=setting, outer_fold=of,
                   inner_fold=9, model_seed=seed, split_hash=SPLIT_HASH,
                   config_hash=cfg_hash)
    rows = []
    for s in fold["test_subjects"]:
        for t in CLASSIFICATION_TASKS:
            rk = _run_key(s, t)
            for w in range(4):
                rows.append({"schema_version": cli.S_PRED_SCHEMA, "canonical_subject": s,
                             "group_id": s, "run_key": rk, "window_key": f"{rk}#win-{w}",
                             "truth": CLASSIFICATION_TASKS.index(t),
                             "p_class1": _prob(s, t, w, seed), "candidate": cand,
                             "setting_id": setting, "scope": "outer_test",
                             "model_sha256": msha, "s_fit_id": sid})
    pred = d / "s_window_predictions.jsonl"
    _write_rows(pred, rows)
    fit = ({"kind": "logistic", "converged": True} if seed is None
           else {"kind": "mlp", "epochs_run": E, "best_epoch": E})
    rep = {"schema_version": cli.S_FIT_SCHEMA, "s_fit_id": sid, "candidate": cand,
           "setting_id": setting, "role": "outer", "eval_role": "outer_test",
           "folds": {"outer_fold": of, "inner_fold": 9,
                     "n_train_subjects": len(fold["train_subjects"]),
                     "n_eval_subjects": len(fold["test_subjects"])},
           "model_seed": seed, "converged": True, "best_epoch": None, "fit": fit,
           "fit_subjects": fold["train_subjects"], "model_sha256": msha,
           "window_predictions_sha256": _sha(pred), "code_hash": "c" * 64,
           "env_hash": "e" * 64, "config_hash": cfg_hash, "source_hash": "f" * 64,
           "split_hash": SPLIT_HASH, "outer_fit_inner_fold": 9}
    (d / "s_fit_report.json").write_text(json.dumps(rep), encoding="utf-8")
    return d / "s_fit_report.json"


@pytest.fixture()
def ws(tmp_path):
    subjects = [_canon(i) for i in range(1, 11)]
    pool = subjects[2:]
    outer = [{"outer_fold": 0, "test_subjects": pool[:4], "train_subjects": pool[4:],
              "inner": []},
             {"outer_fold": 1, "test_subjects": pool[4:], "train_subjects": pool[:4],
              "inner": []}]
    folds = {"split_hash": SPLIT_HASH, "pilot": {"subjects": subjects[:2]},
             "main_pool": {"subjects": pool}, "outer_folds": outer}
    cfg_hash = config_hash(load_config(CONFIG))
    reports = [_make_fit(tmp_path / "fits", outer[0], LOGI, LOGI_SET, None, cfg_hash)]
    reports += [_make_fit(tmp_path / "fits", outer[1], MLP, MLP_SET, s, cfg_hash)
                for s in SEEDS]
    sels = {0: _selection(0, cfg_hash, LOGI), 1: _selection(1, cfg_hash, MLP)}
    return {"folds": folds, "cfg_hash": cfg_hash, "reports": reports, "sels": sels,
            "pool": pool, "outer": outer, "root": tmp_path / "fits"}


def _load(ws, *, reports=None, sels=None, folds=None, cfg_hash=None):
    return cli._load_s_outer(
        [str(r) for r in (ws["reports"] if reports is None else reports)],
        folds=folds or ws["folds"], cfg_hash=cfg_hash or ws["cfg_hash"],
        selections=ws["sels"] if sels is None else sels)


def _rewrite_json(path: Path, fn) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d), encoding="utf-8")


def _row_edit(ws, fn, idx=1, *, fix_sha=True) -> None:
    """보고서 idx 의 예측 행을 고치고 (기본) 보고서 sha 도 맞춘다."""
    rep = ws["reports"][idx]
    pred = rep.parent / "s_window_predictions.jsonl"
    rows = [json.loads(x) for x in pred.read_text(encoding="utf-8").splitlines() if x]
    _write_rows(pred, fn(rows))
    if fix_sha:
        _rewrite_json(rep, lambda d: d.update(window_predictions_sha256=_sha(pred)))


def _raises(ws, match, **kw):
    with pytest.raises(cli.CLIError, match=match):
        _load(ws, **kw)


# --------------------------------------------------------------------------- #
# 정상 경로·손계산
# --------------------------------------------------------------------------- #


def test_mixed_candidates_hand_checked(ws):
    got = _load(ws)
    runs = got["runs"]
    assert len(runs) == len(ws["pool"]) * 2 and {k[0] for k in runs} == {"S"}
    lo = runs[("S", _canon(3), "emomatching")]      # outer 0 — logistic, seed 없음
    assert lo["p"] == pytest.approx(0.2) and lo["n_seeds"] == 1 and lo["n_windows"] == 4
    ml = runs[("S", _canon(7), "workingmemory")]    # outer 1 — MLP seed 3
    assert ml["p"] == pytest.approx(0.8) and ml["n_seeds"] == 3
    assert runs[("S", _canon(8), "workingmemory")]["correct"] is False
    scores = EV.subject_scores(runs, "S")
    assert scores[_canon(4)] == pytest.approx(0.5) and scores[_canon(7)] == 1.0
    assert EV.cell_balanced_accuracy(runs, "S") == pytest.approx(0.75)
    sb = got["seeds_by_subject"]
    assert set(sb) == set(ws["pool"])
    assert all(sb[s] == (None,) for s in ws["outer"][0]["test_subjects"])
    assert all(sb[s] == SEEDS for s in ws["outer"][1]["test_subjects"])
    assert len(got["fits"]) == 4
    assert got["plans"][0]["candidate"] == LOGI and got["plans"][1]["epochs"] == E


def test_rows_seed_comes_from_report(ws):
    got = _load(ws)
    seeds = {(p.canonical_subject, p.model_seed) for p in got["predictions"]}
    assert (_canon(3), None) in seeds and (_canon(7), 44) in seeds
    assert all(isinstance(p, EV.ComparisonWindowPrediction) for p in got["predictions"])
    with pytest.raises(EV.EvaluationError):
        EV.aggregate_runs(got["predictions"])


def test_outer_logistic_convergence_recorded_not_refused(ws):
    _rewrite_json(ws["reports"][0], lambda d: d.update(converged=False))
    got = _load(ws)
    assert got["fits"][json.loads(ws["reports"][0].read_text())["s_fit_id"]][
        "converged"] is False


def test_both_folds_mlp(ws):
    extra = [_make_fit(ws["root"] / "b", ws["outer"][0], MLP, MLP_SET, s, ws["cfg_hash"])
             for s in SEEDS]
    sels = {0: _selection(0, ws["cfg_hash"], MLP), 1: ws["sels"][1]}
    got = _load(ws, reports=extra + ws["reports"][1:], sels=sels)
    assert all(v == SEEDS for v in got["seeds_by_subject"].values())


# --------------------------------------------------------------------------- #
# 선택 기록 가드
# --------------------------------------------------------------------------- #


def test_selection_for_every_outer_fold(ws):
    _raises(ws, "빠진 fold 없이", sels={0: ws["sels"][0]})


def test_folds_without_outer_refused(ws):
    _raises(ws, "outer fold 가 없다", folds={"split_hash": SPLIT_HASH, "outer_folds": []})


@pytest.mark.parametrize("field,value,match", [
    ("schema_version", "x", "S 선택 기록 스키마"),
    ("outer_fold", 5, "S 선택 기록 outer_fold"),
    ("split_hash", "a" * 64, "S 선택 기록 split_hash"),
    ("config_hash", "a" * 64, "S 선택 기록 config_hash"),
    ("external_split_hash", "a" * 64, "외부 S 선택 기록"),
    ("selected_candidate", "S9", "S 후보가 아니다"),
])
def test_selection_record_guards(ws, field, value, match):
    for of in (0, 1):
        ws["sels"][of][field] = value
    _raises(ws, match)


def test_plan_row_candidate_mismatch(ws):
    ws["sels"][1]["outer_plan"][0]["setting_id"] = "config=4"
    _raises(ws, "후보/설정이 선택 기록과 다르다")


def test_plan_row_fold_mismatch(ws):
    ws["sels"][1]["outer_plan"][2]["inner_fold"] = 0
    _raises(ws, "outer 계획 행의 fold")


@pytest.mark.parametrize("edit", [
    lambda s: s["outer_plan"][0].update(model_seed=42),
    lambda s: s["outer_plan"][0].update(epochs_exact=10),
    lambda s: s.update(outer_epochs=10),
    lambda s: s["outer_plan"].append(dict(s["outer_plan"][0])),
])
def test_logistic_plan_is_single_seedless_row(ws, edit):
    edit(ws["sels"][0])
    _raises(ws, "seed·epoch 없는")


@pytest.mark.parametrize("seeds", [(42, 43, None), (42, 42, 43), ()])
def test_mlp_plan_seed_none_dup_empty(ws, seeds):
    ws["sels"][1] = _selection(1, ws["cfg_hash"], MLP, seeds=seeds)
    _raises(ws, "비었거나 중복·None")


def test_mlp_plan_seed_must_match_locked(ws):
    ws["sels"][1] = _selection(1, ws["cfg_hash"], MLP, seeds=(42, 43, 45))
    _raises(ws, "잠긴")


def test_mlp_plan_seed_follows_locked_at_call_time(ws, monkeypatch):
    monkeypatch.setattr(TR, "MODEL_SEEDS", (42, 43))
    _raises(ws, "잠긴")


@pytest.mark.parametrize("e", [None, 0, 401])
def test_mlp_outer_e_range(ws, e):
    ws["sels"][1]["outer_epochs"] = e
    _raises(ws, "MLP outer E")


def test_mlp_plan_row_e_mismatch(ws):
    ws["sels"][1]["outer_plan"][1]["epochs_exact"] = E - 1
    _raises(ws, "outer 계획 행의 E")


# --------------------------------------------------------------------------- #
# 보고서 가드
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("edit,match", [
    (lambda d: d.update(schema_version="x"), "스키마"),
    (lambda d: d.update(role="inner"), "S outer 최종 적합이 아니다"),
    (lambda d: d.update(eval_role="inner_validation"), "S outer 최종 적합이 아니다"),
    (lambda d: d.update(external_split_hash="a" * 64), "외부 분할 기록이 있는 S fit"),
    (lambda d: d.update(external_folds_sha256="a" * 64), "외부 분할 기록이 있는 S fit"),
    (lambda d: d.update(split_hash="a" * 64), "S fit split_hash"),
    (lambda d: d.update(config_hash="a" * 64), "S fit config_hash"),
    (lambda d: d["folds"].update(inner_fold=0), "inner_fold 0"),
    (lambda d: d["folds"].update(outer_fold=5), "S 선택 기록이 없다"),
    (lambda d: d.update(setting_id="config=4"), "후보/설정 "),
    (lambda d: d.update(model_seed=45), "S 계획"),
    (lambda d: d["fit"].update(epochs_run=E - 1), "epochs_run"),
    (lambda d: d.update(fit={"kind": "mlp"}), "epochs_run"),
    (lambda d: d.update(model_sha256="a" * 64), "s_model.npz sha256"),
    (lambda d: d.update(window_predictions_sha256="a" * 64), "s_window_predictions sha256"),
    (lambda d: d.update(code_hash="b" * 64), "code_hash 가 다르다"),
    (lambda d: d.update(env_hash="b" * 64), "env_hash 가 다르다"),
    (lambda d: d.update(source_hash="b" * 64), "source_hash 가 다르다"),
])
def test_report_guards(ws, edit, match):
    _rewrite_json(ws["reports"][1], edit)
    _raises(ws, match)


def test_logistic_report_with_seed_refused(ws):
    _rewrite_json(ws["reports"][0], lambda d: d.update(model_seed=42))
    _raises(ws, "S 계획")


def test_s_fit_id_recomputed(ws):
    fake = "s-outer-S2-o1i9s42-000000000000"
    _rewrite_json(ws["reports"][1], lambda d: d.update(s_fit_id=fake))
    _row_edit(ws, lambda rs: [dict(r, s_fit_id=fake) for r in rs])
    _raises(ws, "다시 만든 s_fit_id")


def test_duplicate_s_fit_id(ws):
    _raises(ws, "s_fit_id 중복", reports=ws["reports"] + [ws["reports"][1]])


def test_duplicate_outer_seed_slot(ws):
    d2 = ws["root"] / "dup"
    shutil.copytree(ws["reports"][1].parent, d2)
    _rewrite_json(d2 / "s_fit_report.json", lambda d: d.update(s_fit_id="s-other"))
    _raises(ws, "같은 \\(outer, seed\\)", reports=ws["reports"] + [d2 / "s_fit_report.json"])


def test_missing_plan_fit_refused(ws):
    _raises(ws, "S outer 계획의 fit 이 빠졌다", reports=ws["reports"][:3])


def test_missing_logistic_fit_refused(ws):
    _raises(ws, "S outer 계획의 fit 이 빠졌다", reports=ws["reports"][1:])


@pytest.mark.parametrize("name", cli.S_OUTER_NEIGHBOURS)
def test_neighbour_file_required(ws, name):
    (ws["reports"][1].parent / name).unlink()
    _raises(ws, f"{name} 가 없다")


def test_model_file_swapped_after_fit(ws):
    (ws["reports"][1].parent / "s_model.npz").write_bytes(b"other")
    _raises(ws, "s_model.npz sha256")


# --------------------------------------------------------------------------- #
# 예측 행 가드
# --------------------------------------------------------------------------- #


def test_prediction_file_edited_after_fit(ws):
    _row_edit(ws, lambda rs: [dict(r, p_class1=0.5) for r in rs], fix_sha=False)
    _raises(ws, "s_window_predictions sha256")


def test_row_schema_violation(ws):
    _row_edit(ws, lambda rs: [{k: v for k, v in r.items() if k != "truth"} for r in rs])
    _raises(ws, "s_window_predictions 스키마 위반")


@pytest.mark.parametrize("field,value,match", [
    ("s_fit_id", "s-other", "s_fit_id 's-other'"),
    ("candidate", LOGI, "후보/설정이 보고서와 다르다"),
    ("setting_id", "config=4", "후보/설정이 보고서와 다르다"),
    ("scope", "inner_validation", "S outer test 만"),
    ("model_sha256", "a" * 64, "model_sha256 이 s_model.npz"),
])
def test_row_guards(ws, field, value, match):
    _row_edit(ws, lambda rs: [dict(rs[0], **{field: value})] + rs[1:])
    _raises(ws, match)


def test_row_training_subject_leak(ws):
    leak = ws["outer"][1]["train_subjects"][0]
    _row_edit(ws, lambda rs: [dict(rs[0], canonical_subject=leak)] + rs[1:])
    _raises(ws, "test 누설")


def test_row_subject_outside_test(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], canonical_subject=_canon(1))] + rs[1:])
    _raises(ws, "test subject 가 아니다")


def test_fit_must_cover_outer_test(ws):
    drop = ws["outer"][1]["test_subjects"][0]
    _row_edit(ws, lambda rs: [r for r in rs if r["canonical_subject"] != drop])
    _raises(ws, "S 예측 subject 가")


def test_two_runs_for_subject_task_refused(ws):
    def fn(rs):
        rk2 = rs[0]["run_key"].replace("/seq", "/seq2")
        return [dict(r, run_key=rk2, window_key=r["window_key"].replace(r["run_key"], rk2))
                if r["run_key"] == rs[0]["run_key"] else r for r in rs]
    _row_edit(ws, fn)
    _raises(ws, "run 이 여럿")


def test_incomplete_window_grid_refused(ws):
    _row_edit(ws, lambda rs: rs[1:])
    _raises(ws, "S 무결성 검사 실패")


def test_row_probability_out_of_range(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], p_class1=1.5)] + rs[1:])
    _raises(ws, "확률")
