"""`mobse-v2 select-ad` — A–D inner 산출물 → 공동 선택 기록 (WI-07, 계획서 §7).

합성 inner fit 디렉터리(`run_fit` 과 같은 세 파일)로 경계·무결성·선택 규칙 전달을
확인한다. 학습은 하지 않는다 — 선택 규칙 자체는 `test_train.py` 가 덮는다.
inner validation 크기를 4/4/3 으로 두어 OOF 가중(rev46)이 CLI 로 전달되는지 본다.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from mobse.v2 import fitting as FIT
from mobse.v2 import templates as TPL
from mobse.v2 import train as TR
from mobse.v2.cli import (AD_SELECTION_OUTPUT, CLIError, MULTI_PATHS, REQUIRED_PATHS,
                          SUBCOMMANDS, build_parser, resolve_paths, run_select_ad)
from mobse.v2.config import config_hash, load_config
from mobse.v2.manifests import fit_id

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs/redesign_v1/main.yaml"
TASKS = ("emomatching", "workingmemory")
H = "a" * 64
VAL_SIZES = (4, 4, 3)


def _canon(i: int) -> str:
    return f"ds002785:sub-{i:04d}"


@pytest.fixture
def ws(tmp_path):
    pilot = [_canon(i) for i in range(1, 3)]
    test = [_canon(i) for i in range(3, 7)]
    train = [_canon(i) for i in range(7, 7 + sum(VAL_SIZES))]
    inner, start = [], 0
    for f, n in enumerate(VAL_SIZES):
        val = train[start:start + n]
        start += n
        inner.append({"inner_fold": f, "val_subjects": val,
                      "train_subjects": [s for s in train if s not in val]})
    folds = {"split_hash": "d" * 64, "pilot": {"subjects": pilot},
             "main_pool": {"subjects": test + train},
             "outer_folds": [{"outer_fold": 0, "test_subjects": test,
                              "train_subjects": train, "inner": inner}]}
    fp = tmp_path / "folds.json"
    fp.write_text(json.dumps(folds), encoding="utf-8")
    return {"tmp": tmp_path, "folds": fp, "folds_obj": folds,
            "cfg_hash": config_hash(load_config(CONFIG))}


def _p_true(cell: str, cid: int, fold: int, subject: str, task: str, w: int) -> float:
    """정답 class 확률. config 3 이 가장 좋고 나머지는 config 가 클수록 나빠진다."""
    key = repr((cell, cid, fold, subject, task, w)).encode()
    rng = np.random.default_rng(int(hashlib.sha256(key).hexdigest()[:8], 16))
    base = 0.9 if cid == 3 else 0.8 - 0.02 * cid
    return float(np.clip(base + rng.uniform(-0.05, 0.05), 0.01, 0.99))


def _best_epoch(cell: str, cid: int, fold: int) -> int:
    return 300 + 10 * cid + 3 * fold + ("A", "B", "C", "D", "NG", "SG").index(cell)


def make_fit(ws, *, cell="A", cid=0, fold=0, seed=42, mutate=None, name=None):
    """`run_fit` 과 같은 세 파일을 쓴다. ``mutate(man, rep, rows)`` 로 어긋남을 넣는다."""
    folds = ws["folds_obj"]
    inner = folds["outer_folds"][0]["inner"][fold]
    fid = fit_id(role="inner", cell=cell, outer_fold=0, inner_fold=fold,
                 model_seed=seed, config_id=cid, split_hash=folds["split_hash"],
                 config_hash=ws["cfg_hash"])
    rows, run_p = [], {}
    for s in inner["val_subjects"]:
        sub = s.split(":")[1]
        for task in TASKS:
            rk = f"ds002785/{sub}/na/{task}/na/seq"
            truth = FIT.class_index(task)
            ps = []
            for w in range(4):
                pt = _p_true(cell, cid, fold, s, task, w)
                p1 = pt if truth == 1 else 1.0 - pt
                ps.append(p1)
                rows.append({"schema_version": "wi05-window-predictions-0.1",
                             "canonical_subject": s, "group_id": s, "run_key": rk,
                             "window_key": f"{rk}#win-{w}", "truth": truth,
                             "p_class1": p1, "cell": cell, "model_seed": seed,
                             "scope": "inner_validation", "checkpoint_sha256": H,
                             "fit_id": fid})
            run_p[rk] = float(np.mean(ps))
    man = {"schema_version": "wi05-fit-manifest-0.1", "fit_id": fid,
           "parent_release": "r", "role": "inner", "cell": cell,
           "folds": {"outer_fold": 0, "inner_fold": fold,
                     "n_train_subjects": len(inner["train_subjects"]),
                     "n_eval_subjects": len(inner["val_subjects"]),
                     "eval_role": "inner_validation"},
           "model_seed": seed, "bank_seed": 1, "null_seed": 1729,
           "fit_subjects": list(inner["train_subjects"]), "scaler_id": "x",
           "pca_id": "x", "bank_id": "x", "code_hash": "c" * 64, "env_hash": "e" * 64,
           "config_hash": ws["cfg_hash"], "source_hash": "s" * 64,
           "split_hash": folds["split_hash"]}
    rep = {"fit_id": fid, "config_id": cid, "best_epoch": _best_epoch(cell, cid, fold),
           "eval_loss": TR.subject_equal_loss(FIT.subject_run_true_probs(run_p)),
           "eval_balanced_accuracy": FIT._balanced_accuracy_from_runs(run_p),
           "checkpoint_sha256": H}
    if mutate:
        mutate(man, rep, rows)
    d = ws["tmp"] / "fits" / (name or f"{cell}_c{cid}_i{fold}_s{seed}")
    d.mkdir(parents=True, exist_ok=False)
    (d / "fit_manifest.json").write_text(json.dumps(man), encoding="utf-8")
    (d / "fit_report.json").write_text(json.dumps(rep), encoding="utf-8")
    (d / "window_predictions.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return d / "fit_manifest.json", run_p


def full_grid(ws, skip=(), **kw):
    return [make_fit(ws, cell=c, cid=k, fold=f, **kw)[0]
            for c in TR.CELLS for k in range(8) for f in range(3) if (c, k, f) not in skip]


def run(ws, manifests, *, outer=0, out=None):
    out = out or ws["tmp"] / "sel_ad"
    ns = build_parser().parse_args(
        ["select-ad", "--config", str(CONFIG), "--splits", str(ws["folds"]),
         "--output-dir", str(out), "--outer-fold", str(outer),
         "--fit-manifest"] + [str(m) for m in manifests])
    return run_select_ad(resolve_paths("select-ad", ns), ns), out


def _one_bad(ws, cell, cid, fold, mutate, **kw):
    """(cell, cid, fold) 하나만 어긋난 완전 grid."""
    return full_grid(ws, skip={(cell, cid, fold)}) + \
        [make_fit(ws, cell=cell, cid=cid, fold=fold, mutate=mutate, **kw)[0]]


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def test_subcommand_is_registered_with_required_paths():
    assert "select-ad" in SUBCOMMANDS
    assert REQUIRED_PATHS["select-ad"] == ("config", "splits", "fit_manifest", "output_dir")
    assert ("select-ad", "fit_manifest") in MULTI_PATHS
    with pytest.raises(SystemExit):
        build_parser().parse_args(["select-ad"])


# --------------------------------------------------------------------------- #
# 정상 경로
# --------------------------------------------------------------------------- #

def test_selection_record_matches_plan_rule(ws):
    res, out = run(ws, full_grid(ws))
    rec = json.loads((out / AD_SELECTION_OUTPUT).read_text())
    assert res["verdict"] == "pass" and res["n_inputs"] == 96
    assert rec["selected_config_id"] == 3
    epochs = sorted(_best_epoch(c, 3, f) for c in TR.CELLS for f in range(3))
    assert sorted(e["best_epoch"] for e in rec["best_epochs"]) == epochs
    assert len(rec["best_epochs"]) == 12
    s = sorted(epochs)
    assert rec["common_epochs"] == math.ceil((s[5] + s[6]) / 2)
    assert [r["config_id"] for r in rec["table"]] == list(range(8))
    assert len({i["fit_id"] for i in rec["inputs"]}) == 96
    assert rec["inner_fold_n_subjects"] == {"0": 4, "1": 4, "2": 3}


def test_joint_loss_is_oof_merged_per_cell_then_equal_cells(ws):
    """cell 안 OOF 병합(fold 크기 4/4/3) → 네 cell 같은 가중 — 손계산과 같다."""
    mans, oof = [], {}
    for c in TR.CELLS:
        for k in range(8):
            for f in range(3):
                m, rp = make_fit(ws, cell=c, cid=k, fold=f)
                mans.append(m)
                oof.setdefault((k, c), {}).update(rp)
    _, out = run(ws, mans)
    rec = json.loads((out / AD_SELECTION_OUTPUT).read_text())
    for row in rec["table"]:
        k = row["config_id"]
        hand = np.mean([TR.subject_equal_loss(FIT.subject_run_true_probs(oof[(k, c)]))
                        for c in TR.CELLS])
        assert abs(row["joint_loss"] - hand) < 1e-12
        fold_mean = np.mean([np.mean([
            json.loads((m.parent / "fit_report.json").read_text())["eval_loss"]
            for m in mans if f"{c}_c{k}_" in m.parent.name]) for c in TR.CELLS])
        assert abs(row["joint_loss"] - fold_mean) > 1e-9      # fold 평균이 아니다


def test_outer_plan_is_four_cells_by_locked_seeds_at_common_e(ws):
    _, out = run(ws, full_grid(ws))
    rec = json.loads((out / AD_SELECTION_OUTPUT).read_text())
    plan = rec["outer_plan"]
    assert [(p["cell"], p["model_seed"]) for p in plan] == \
        [(c, s) for c in TR.CELLS for s in TR.MODEL_SEEDS]
    for p in plan:
        assert p["inner_fold"] == TPL.OUTER_FIT_INNER_FOLD
        assert p["epochs_exact"] == rec["common_epochs"] and p["config_id"] == 3
        ns = build_parser().parse_args(p["cli"] + [
            "--config", "c", "--splits", "s", "--subjects", "s", "--windows", "w",
            "--rest-manifest", "r", "--output-dir", "o", "--task-manifests", "t"])
        assert (ns.cell, ns.inner_fold, ns.config_id, ns.epochs, ns.model_seed) == \
            (p["cell"], 9, 3, rec["common_epochs"], p["model_seed"])


def test_outer_seeds_are_read_at_call_time(ws, monkeypatch):
    monkeypatch.setattr(TR, "MODEL_SEEDS", (42, 43, 44, 45))
    _, out = run(ws, full_grid(ws))
    plan = json.loads((out / AD_SELECTION_OUTPUT).read_text())["outer_plan"]
    assert len(plan) == 16 and {p["model_seed"] for p in plan} == {42, 43, 44, 45}


def test_record_is_not_overwritten(ws):
    mans = full_grid(ws)
    _, out = run(ws, mans)
    with pytest.raises(CLIError, match="덮어쓰지 않는다"):
        run(ws, mans, out=out)


# --------------------------------------------------------------------------- #
# 경계·무결성 — 조용히 통과하면 안 되는 것
# --------------------------------------------------------------------------- #

def test_incomplete_grid_is_refused(ws):
    with pytest.raises(CLIError, match="불완전한 grid"):
        run(ws, full_grid(ws, skip={("C", 5, 2)}))


def test_comparator_cell_is_refused(ws):
    mans = full_grid(ws, skip={("A", 0, 0)}) + [make_fit(ws, cell="NG", cid=0, fold=0)[0]]
    with pytest.raises(CLIError, match="다른 칸을"):
        run(ws, mans)


def test_non_inner_seed_is_refused(ws):
    with pytest.raises(CLIError, match="inner seed"):
        run(ws, _one_bad(ws, "B", 2, 1, None, seed=43))


def test_outer_fit_is_refused(ws):
    def m(man, rep, rows):
        man["role"] = "outer"
    with pytest.raises(CLIError, match="inner fit 이 아니다"):
        run(ws, _one_bad(ws, "A", 0, 0, m))


def test_wrong_outer_fold_is_refused(ws):
    with pytest.raises(CLIError, match="--outer-fold"):
        run(ws, full_grid(ws), outer=1)


def test_report_config_id_must_match_manifest_fit(ws):
    def m(man, rep, rows):
        rep["config_id"] = 6
    with pytest.raises(CLIError, match="다른 fit 이다"):
        run(ws, _one_bad(ws, "D", 1, 0, m))


def test_duplicate_manifest_is_refused(ws):
    mans = full_grid(ws)
    with pytest.raises(CLIError, match="fit_id 중복"):
        run(ws, mans + [mans[0]])


def test_loss_mismatch_with_fit_report_is_refused(ws):
    def m(man, rep, rows):
        rep["eval_loss"] += 1e-3
    with pytest.raises(CLIError, match="eval_loss"):
        run(ws, _one_bad(ws, "C", 4, 2, m))


def test_ba_mismatch_with_fit_report_is_refused(ws):
    def m(man, rep, rows):
        rep["eval_balanced_accuracy"] -= 0.25
    with pytest.raises(CLIError, match="eval_balanced_accuracy"):
        run(ws, _one_bad(ws, "B", 3, 1, m))


def test_missing_validation_subject_is_refused(ws):
    def m(man, rep, rows):
        drop = rows[0]["canonical_subject"]
        rows[:] = [r for r in rows if r["canonical_subject"] != drop]
    with pytest.raises(CLIError, match="inner validation subject"):
        run(ws, _one_bad(ws, "A", 0, 1, m))


def test_outer_test_scope_row_is_refused(ws):
    def m(man, rep, rows):
        rows[3]["scope"] = "outer_test"
    with pytest.raises(CLIError, match="scope"):
        run(ws, _one_bad(ws, "D", 7, 0, m))


def test_fit_subjects_must_match_folds(ws):
    def m(man, rep, rows):
        man["fit_subjects"] = man["fit_subjects"][:-1]
    with pytest.raises(CLIError, match="fit_subjects"):
        run(ws, _one_bad(ws, "C", 3, 0, m))


def test_mixed_code_hash_is_refused(ws):
    def m(man, rep, rows):
        man["code_hash"] = "f" * 64
    with pytest.raises(CLIError, match="code_hash"):
        run(ws, _one_bad(ws, "B", 6, 1, m))


def test_missing_neighbour_file_is_refused_without_search(ws):
    mans = full_grid(ws)
    (mans[5].parent / "window_predictions.jsonl").unlink()
    with pytest.raises(CLIError, match="U20"):
        run(ws, mans)


def test_checkpoint_hash_mismatch_is_refused(ws):
    def m(man, rep, rows):
        rows[0]["checkpoint_sha256"] = "b" * 64
    with pytest.raises(CLIError, match="checkpoint"):
        run(ws, _one_bad(ws, "A", 2, 2, m))


def test_truth_must_follow_task(ws):
    def m(man, rep, rows):
        rows[0]["truth"] = 1 - rows[0]["truth"]
    with pytest.raises(CLIError, match="truth"):
        run(ws, _one_bad(ws, "D", 1, 1, m))


def test_best_epoch_above_cap_is_refused(ws):
    def m(man, rep, rows):
        rep["best_epoch"] = TR.MAX_EPOCHS + 1
    with pytest.raises(CLIError, match="best_epoch"):
        run(ws, _one_bad(ws, "C", 0, 2, m))


def test_row_of_other_cell_is_refused(ws):
    def m(man, rep, rows):
        rows[1]["cell"] = "B"
    with pytest.raises(CLIError, match="fit_id/cell/seed"):
        run(ws, _one_bad(ws, "A", 5, 0, m))
