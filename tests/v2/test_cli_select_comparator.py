"""`mobse-v2 select-comparator` — 결정 14 4b (구조 비교 inner 산출물 → 선택 기록).

합성 inner fit 디렉터리(`run_fit` 과 같은 세 파일)로 경계·무결성·선택 규칙 전달을
확인한다. 학습은 하지 않는다 — 선택 규칙 자체는 `test_baselines.py` 가 덮는다.
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
from mobse.v2.cli import (CLIError, REQUIRED_PATHS, SELECTION_OUTPUT, SUBCOMMANDS,
                          build_parser, resolve_paths, run_select_comparator)
from mobse.v2.config import config_hash, load_config
from mobse.v2.manifests import fit_id

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs/redesign_v1/main.yaml"
TASKS = ("emomatching", "workingmemory")
H = "a" * 64


def _canon(i: int) -> str:
    return f"ds002785:sub-{i:04d}"


@pytest.fixture
def ws(tmp_path):
    pilot = [_canon(i) for i in range(1, 3)]
    test = [_canon(i) for i in range(3, 7)]
    train = [_canon(i) for i in range(7, 19)]          # 12명 → inner 3 fold × val 4
    inner = [{"inner_fold": f, "val_subjects": train[4 * f:4 * f + 4],
              "train_subjects": [s for s in train if s not in train[4 * f:4 * f + 4]]}
             for f in range(3)]
    folds = {"split_hash": "d" * 64, "pilot": {"subjects": pilot},
             "main_pool": {"subjects": test + train},
             "outer_folds": [{"outer_fold": 0, "test_subjects": test,
                              "train_subjects": train, "inner": inner}]}
    fp = tmp_path / "folds.json"
    fp.write_text(json.dumps(folds), encoding="utf-8")
    cfg_hash = config_hash(load_config(CONFIG))
    return {"tmp": tmp_path, "folds": fp, "folds_obj": folds, "cfg_hash": cfg_hash}


def _p_true(structure: str, cid: int, fold: int, subject: str, task: str, w: int) -> float:
    """정답 class 확률. config 가 클수록(0→7) 조금씩 나빠지게, 단 config 3 이 가장 좋다."""
    key = repr((structure, cid, fold, subject, task, w)).encode()
    rng = np.random.default_rng(int(hashlib.sha256(key).hexdigest()[:8], 16))
    base = 0.9 if cid == 3 else 0.8 - 0.02 * cid
    return float(np.clip(base + rng.uniform(-0.05, 0.05), 0.01, 0.99))


def make_fit(ws, *, structure="NG", cid=0, fold=0, seed=42, best_epoch=None,
             mutate=None, name=None):
    """`run_fit` 과 같은 세 파일을 쓴다. ``mutate(man, rep, rows)`` 로 어긋남을 넣는다."""
    folds = ws["folds_obj"]
    inner = folds["outer_folds"][0]["inner"][fold]
    fid = fit_id(role="inner", cell=structure, outer_fold=0, inner_fold=fold,
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
                pt = _p_true(structure, cid, fold, s, task, w)
                p1 = pt if truth == 1 else 1.0 - pt
                ps.append(p1)
                rows.append({"schema_version": "wi05-window-predictions-0.1",
                             "canonical_subject": s, "group_id": s, "run_key": rk,
                             "window_key": f"{rk}#win-{w}", "truth": truth,
                             "p_class1": p1, "cell": structure, "model_seed": seed,
                             "scope": "inner_validation", "checkpoint_sha256": H,
                             "fit_id": fid})
            run_p[rk] = float(np.mean(ps))
    man = {"schema_version": "wi05-fit-manifest-0.1", "fit_id": fid,
           "parent_release": "r", "role": "inner", "cell": structure,
           "folds": {"outer_fold": 0, "inner_fold": fold,
                     "n_train_subjects": len(inner["train_subjects"]),
                     "n_eval_subjects": 4, "eval_role": "inner_validation"},
           "model_seed": seed, "bank_seed": 1, "null_seed": 1729,
           "fit_subjects": list(inner["train_subjects"]), "scaler_id": "x",
           "pca_id": "x", "bank_id": "x", "code_hash": "c" * 64, "env_hash": "e" * 64,
           "config_hash": ws["cfg_hash"], "source_hash": "s" * 64,
           "split_hash": folds["split_hash"]}
    rep = {"fit_id": fid, "config_id": cid,
           "best_epoch": best_epoch if best_epoch is not None else 10 + cid + fold,
           "eval_loss": BL.inner_loss(run_p), "checkpoint_sha256": H}
    if mutate:
        mutate(man, rep, rows)
    d = ws["tmp"] / "fits" / (name or f"{structure}_c{cid}_i{fold}_s{seed}")
    d.mkdir(parents=True, exist_ok=False)
    (d / "fit_manifest.json").write_text(json.dumps(man), encoding="utf-8")
    (d / "fit_report.json").write_text(json.dumps(rep), encoding="utf-8")
    (d / "window_predictions.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return d / "fit_manifest.json"


def full_grid(ws, structure="NG", skip=(), **kw):
    return [make_fit(ws, structure=structure, cid=c, fold=f, **kw)
            for c in range(8) for f in range(3) if (c, f) not in skip]


def run(ws, manifests, *, structure="NG", outer=0, out=None):
    out = out or ws["tmp"] / f"sel_{structure}"
    ns = build_parser().parse_args(
        ["select-comparator", "--config", str(CONFIG), "--splits", str(ws["folds"]),
         "--output-dir", str(out), "--structure", structure, "--outer-fold", str(outer),
         "--fit-manifest"] + [str(m) for m in manifests])
    return run_select_comparator(resolve_paths("select-comparator", ns), ns), out


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def test_subcommand_is_registered_with_required_paths():
    assert "select-comparator" in SUBCOMMANDS
    assert REQUIRED_PATHS["select-comparator"] == ("config", "splits", "fit_manifest",
                                                   "output_dir")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["select-comparator"])


def test_structure_choices_are_exactly_the_comparators(ws):
    assert tuple(build_parser()._subparsers._group_actions[0]
                 .choices["select-comparator"]._option_string_actions["--structure"]
                 .choices) == BL.COMPARATOR_ORDER
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["select-comparator", "--config", "c", "--splits", "s", "--output-dir", "o",
             "--structure", "A", "--outer-fold", "0", "--fit-manifest", "m"])


# --------------------------------------------------------------------------- #
# 정상 경로
# --------------------------------------------------------------------------- #

def test_selection_record_matches_library_selection(ws):
    mans = full_grid(ws)
    res, out = run(ws, mans)
    rec = json.loads((out / SELECTION_OUTPUT).read_text())
    assert res["verdict"] == "pass" and res["n_inputs"] == 24
    assert rec["selected_config_id"] == 3                 # 합성 자료에서 가장 좋은 config
    assert rec["best_epochs"] == [13, 14, 15]
    assert rec["outer_epochs"] == TR.baseline_epochs([13, 14, 15]) == 14
    assert [r["config_id"] for r in rec["table"]] == list(range(8))
    assert len(rec["inputs"]) == 24 and len({i["fit_id"] for i in rec["inputs"]}) == 24
    assert rec["rules"]["run_aggregation"].startswith("fitting.run_probabilities")


def test_outer_plan_uses_locked_seeds_and_exact_epochs(ws):
    _, out = run(ws, full_grid(ws))
    plan = json.loads((out / SELECTION_OUTPUT).read_text())["outer_plan"]
    assert [p["model_seed"] for p in plan] == list(TR.MODEL_SEEDS)
    for p in plan:
        assert p["inner_fold"] == TPL.OUTER_FIT_INNER_FOLD
        assert p["epochs_exact"] == 14 and p["config_id"] == 3
        ns = build_parser().parse_args(p["cli"] + [
            "--config", "c", "--splits", "s", "--subjects", "s", "--windows", "w",
            "--rest-manifest", "r", "--output-dir", "o", "--task-manifests", "t"])
        assert (ns.cell, ns.inner_fold, ns.config_id, ns.epochs) == ("NG", 9, 3, 14)


def test_sg_is_selected_independently(ws):
    res, _ = run(ws, full_grid(ws, structure="SG"), structure="SG")
    assert res["structure"] == "SG" and res["selected_config_id"] == 3


def test_record_is_not_overwritten(ws):
    mans = full_grid(ws)
    _, out = run(ws, mans)
    with pytest.raises(CLIError, match="덮어쓰지 않는다"):
        run(ws, mans, out=out)


def test_recomputed_loss_equals_library_inner_loss(ws):
    """CLI 가 창 → run 을 train_fold 와 같은 함수로 접는지: fit_report 값과 대조된다."""
    mans = full_grid(ws)
    _, out = run(ws, mans)
    rec = json.loads((out / SELECTION_OUTPUT).read_text())
    for i in rec["inputs"]:
        rep = json.loads((Path(i["fit_manifest"]).parent / "fit_report.json").read_text())
        assert abs(i["inner_loss"] - rep["eval_loss"]) < 1e-12


# --------------------------------------------------------------------------- #
# 경계·무결성 — 조용히 통과하면 안 되는 것
# --------------------------------------------------------------------------- #

def test_incomplete_grid_is_refused(ws):
    with pytest.raises(CLIError, match="불완전한 grid"):
        run(ws, full_grid(ws, skip={(5, 2)}))


def test_other_structure_is_refused(ws):
    mans = full_grid(ws, skip={(0, 0)}) + [make_fit(ws, structure="SG", cid=0, fold=0)]
    with pytest.raises(CLIError, match="다른 칸을"):
        run(ws, mans)


def test_outer_fit_is_refused(ws):
    def m(man, rep, rows):
        man["role"] = "outer"
    mans = full_grid(ws, skip={(0, 0)}) + [make_fit(ws, cid=0, fold=0, mutate=m)]
    with pytest.raises(CLIError, match="inner fit 이 아니다"):
        run(ws, mans)


def test_wrong_outer_fold_is_refused(ws):
    with pytest.raises(CLIError, match="--outer-fold"):
        run(ws, full_grid(ws), outer=1)


def test_non_inner_seed_is_refused(ws):
    mans = full_grid(ws, skip={(2, 1)}) + [make_fit(ws, cid=2, fold=1, seed=43)]
    with pytest.raises(CLIError, match="inner seed"):
        run(ws, mans)


def test_report_config_id_must_match_manifest_fit(ws):
    """fit_report 의 config_id 를 바꿔 치면 fit_id 재계산이 어긋나 거부된다."""
    def m(man, rep, rows):
        rep["config_id"] = 6
    mans = full_grid(ws, skip={(1, 0)}) + [make_fit(ws, cid=1, fold=0, mutate=m)]
    with pytest.raises(CLIError, match="다른 fit 이다"):
        run(ws, mans)


def test_duplicate_manifest_is_refused(ws):
    mans = full_grid(ws)
    with pytest.raises(CLIError, match="fit_id 중복"):
        run(ws, mans + [mans[0]])


def test_loss_mismatch_with_fit_report_is_refused(ws):
    def m(man, rep, rows):
        rep["eval_loss"] += 1e-3
    mans = full_grid(ws, skip={(4, 2)}) + [make_fit(ws, cid=4, fold=2, mutate=m)]
    with pytest.raises(CLIError, match="eval_loss"):
        run(ws, mans)


def test_missing_validation_subject_is_refused(ws):
    def m(man, rep, rows):
        drop = rows[0]["canonical_subject"]
        rows[:] = [r for r in rows if r["canonical_subject"] != drop]
    mans = full_grid(ws, skip={(0, 1)}) + [make_fit(ws, cid=0, fold=1, mutate=m)]
    with pytest.raises(CLIError, match="inner validation subject"):
        run(ws, mans)


def test_outer_test_scope_row_is_refused(ws):
    def m(man, rep, rows):
        rows[3]["scope"] = "outer_test"
    mans = full_grid(ws, skip={(7, 0)}) + [make_fit(ws, cid=7, fold=0, mutate=m)]
    with pytest.raises(CLIError, match="scope"):
        run(ws, mans)


def test_fit_subjects_must_match_folds(ws):
    def m(man, rep, rows):
        man["fit_subjects"] = man["fit_subjects"][:-1]
    mans = full_grid(ws, skip={(3, 0)}) + [make_fit(ws, cid=3, fold=0, mutate=m)]
    with pytest.raises(CLIError, match="fit_subjects"):
        run(ws, mans)


def test_mixed_code_hash_is_refused(ws):
    def m(man, rep, rows):
        man["code_hash"] = "f" * 64
    mans = full_grid(ws, skip={(6, 1)}) + [make_fit(ws, cid=6, fold=1, mutate=m)]
    with pytest.raises(CLIError, match="code_hash"):
        run(ws, mans)


def test_missing_neighbour_file_is_refused_without_search(ws):
    mans = full_grid(ws)
    (mans[5].parent / "fit_report.json").unlink()
    with pytest.raises(CLIError, match="U20"):
        run(ws, mans)


def test_checkpoint_hash_mismatch_is_refused(ws):
    def m(man, rep, rows):
        rows[0]["checkpoint_sha256"] = "b" * 64
    mans = full_grid(ws, skip={(2, 2)}) + [make_fit(ws, cid=2, fold=2, mutate=m)]
    with pytest.raises(CLIError, match="checkpoint"):
        run(ws, mans)


def test_truth_must_follow_task(ws):
    def m(man, rep, rows):
        rows[0]["truth"] = 1 - rows[0]["truth"]
    mans = full_grid(ws, skip={(1, 1)}) + [make_fit(ws, cid=1, fold=1, mutate=m)]
    with pytest.raises(CLIError, match="truth"):
        run(ws, mans)
