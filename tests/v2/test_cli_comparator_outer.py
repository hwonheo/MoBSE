"""구조 비교 outer fit 산출물 → 보조 비교 집계 helper (남은 작업 2-c, 09-25 14:15).

`cli._load_comparator_outer` 가 선택 기록 outer 계획·outer fit manifest·이웃 파일을
검사하고 `evaluate.aggregate_comparison_runs` 로 run 을 만드는지 합성 자료로 본다.
실자료 fit 은 없다 (main pool 미소비).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from mobse.v2 import cli
from mobse.v2 import evaluate as EV
from mobse.v2.config import config_hash, load_config
from mobse.v2.evaluate import CLASSIFICATION_TASKS

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "redesign_v1" / "main.yaml"
SEEDS = (42, 43, 44)
SPLIT_HASH = "d" * 64
CID, E = 3, 297

pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _canon(i: int) -> str:
    return f"ds002785:sub-{i:04d}"


def _run_key(subject: str, task: str) -> str:
    return f"ds002785/{subject.split(':')[1]}/na/{task}/na/seq"


def _prob(subject: str, task: str, window: int, seed: int) -> float:
    """sub 짝수의 WM 은 틀린다 (0.3 쪽), 나머지는 맞힌다."""
    truth = CLASSIFICATION_TASKS.index(task)
    wrong = task == "workingmemory" and int(subject[-4:]) % 2 == 0
    base = 0.8 if (truth == 1) != wrong else 0.2
    return round(base + 0.01 * (window - 1.5) + 0.005 * (seed - 43), 6)


def _selection(structure, of, cfg_hash, *, seeds=SEEDS):
    return {"schema_version": cli.SELECTION_SCHEMA, "structure": structure,
            "outer_fold": of, "split_hash": SPLIT_HASH, "config_hash": cfg_hash,
            "selected_config_id": CID, "outer_epochs": E,
            "outer_plan": [{"structure": structure, "config_id": CID, "model_seed": s,
                            "epochs_exact": E, "outer_fold": of, "inner_fold": 9}
                           for s in seeds]}


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
    manifests = []
    for fold in outer:
        of = fold["outer_fold"]
        for seed in SEEDS:
            d = tmp_path / "fits" / f"NG_o{of}_s{seed}"
            d.mkdir(parents=True)
            ckpt = d / "checkpoint.pt"
            ckpt.write_bytes(f"NG{of}{seed}".encode())
            sha = hashlib.sha256(ckpt.read_bytes()).hexdigest()
            fid = f"outer-NG-o{of}i9s{seed}-{sha[:12]}"
            man = {"schema_version": "wi05-fit-manifest-0.1", "fit_id": fid,
                   "parent_release": "synthetic", "role": "outer", "cell": "NG",
                   "folds": {"outer_fold": of, "inner_fold": 9,
                             "n_train_subjects": len(fold["train_subjects"]),
                             "n_eval_subjects": len(fold["test_subjects"]),
                             "eval_role": "outer_test"},
                   "model_seed": seed, "bank_seed": 1, "null_seed": 2,
                   "fit_subjects": fold["train_subjects"],
                   "scaler_id": "s", "pca_id": "s", "bank_id": "b",
                   "code_hash": "c" * 64, "env_hash": "e" * 64,
                   "config_hash": cfg_hash, "source_hash": "f" * 64,
                   "split_hash": SPLIT_HASH}
            (d / "fit_manifest.json").write_text(json.dumps(man), encoding="utf-8")
            (d / "fit_report.json").write_text(json.dumps(
                {"fit_id": fid, "config_id": CID, "epochs_run": E,
                 "checkpoint_sha256": sha}), encoding="utf-8")
            rows = []
            for s in fold["test_subjects"]:
                for t in CLASSIFICATION_TASKS:
                    rk = _run_key(s, t)
                    for w in range(4):
                        rows.append({
                            "schema_version": "wi05-window-predictions-0.1",
                            "canonical_subject": s, "group_id": s, "run_key": rk,
                            "window_key": f"{rk}#win-{w}",
                            "truth": CLASSIFICATION_TASKS.index(t),
                            "p_class1": _prob(s, t, w, seed), "cell": "NG",
                            "model_seed": seed, "scope": "outer_test",
                            "checkpoint_sha256": sha, "fit_id": fid})
            (d / "window_predictions.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            manifests.append(d / "fit_manifest.json")
    sels = {f["outer_fold"]: _selection("NG", f["outer_fold"], cfg_hash) for f in outer}
    return {"folds": folds, "cfg_hash": cfg_hash, "manifests": manifests, "sels": sels,
            "pool": pool}


def _load(ws, *, manifests=None, sels=None, structure="NG", folds=None, cfg_hash=None):
    return cli._load_comparator_outer(
        [str(m) for m in (manifests or ws["manifests"])], structure=structure,
        folds=folds or ws["folds"], cfg_hash=cfg_hash or ws["cfg_hash"],
        selections=ws["sels"] if sels is None else sels)


def _rewrite_json(path: Path, fn) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d), encoding="utf-8")


def _rewrite_rows(path: Path, fn) -> None:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
    rows = fn(rows)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_full_grid_hand_checked(ws):
    got = _load(ws)
    runs = got["runs"]
    assert len(runs) == len(ws["pool"]) * 2
    rec = runs[("NG", _canon(3), "emomatching")]
    assert rec["p"] == pytest.approx(0.2) and rec["n_seeds"] == 3 and rec["n_windows"] == 4
    assert rec["truth"] == 0 and rec["correct"]
    scores = EV.subject_scores(runs, "NG")
    # 짝수 subject 는 WM 을 틀림 → b=0.5, 홀수 → 1.0 (4명씩)
    assert scores[_canon(4)] == pytest.approx(0.5) and scores[_canon(3)] == 1.0
    assert EV.cell_balanced_accuracy(runs, "NG") == pytest.approx(0.75)
    assert set(got["seeds_by_subject"]) == set(ws["pool"])
    assert all(v == SEEDS for v in got["seeds_by_subject"].values())
    assert len(got["fits"]) == 6


def test_structure_must_be_comparator(ws):
    with pytest.raises(cli.CLIError, match="구조 비교가 아니다"):
        _load(ws, structure="A")


def test_selection_for_every_outer_fold(ws):
    with pytest.raises(cli.CLIError, match="빠진 fold 없이"):
        _load(ws, sels={0: ws["sels"][0]})


@pytest.mark.parametrize("field,value,match", [
    ("schema_version", "x", "선택 기록 스키마"),
    ("structure", "SG", "선택 기록 구조"),
    ("outer_fold", 1, "선택 기록 outer_fold"),
    ("split_hash", "a" * 64, "선택 기록 split_hash"),
    ("config_hash", "a" * 64, "선택 기록 config_hash"),
    ("external_split_hash", "a" * 64, "외부 선택 기록"),
])
def test_selection_record_guards(ws, field, value, match):
    sels = copy.deepcopy(ws["sels"])
    sels[0][field] = value
    with pytest.raises(cli.CLIError, match=match):
        _load(ws, sels=sels)


def test_plan_seed_must_match_locked(ws):
    sels = copy.deepcopy(ws["sels"])
    sels[1] = _selection("NG", 1, ws["cfg_hash"], seeds=(42, 43, 45))
    with pytest.raises(cli.CLIError, match="잠긴"):
        _load(ws, sels=sels)


def test_plan_seed_duplicate_refused(ws):
    sels = copy.deepcopy(ws["sels"])
    sels[1]["outer_plan"][2]["model_seed"] = 43
    with pytest.raises(cli.CLIError, match="비었거나 중복"):
        _load(ws, sels=sels)


def test_plan_row_config_mismatch_refused(ws):
    sels = copy.deepcopy(ws["sels"])
    sels[0]["outer_plan"][1]["epochs_exact"] = E + 1
    with pytest.raises(cli.CLIError, match="config/E"):
        _load(ws, sels=sels)


def test_cell_must_be_structure(ws):
    _rewrite_json(ws["manifests"][0], lambda d: d.update(cell="SG"))
    with pytest.raises(cli.CLIError, match="다른 칸을 섞지"):
        _load(ws)


def test_inner_fit_refused(ws):
    _rewrite_json(ws["manifests"][0], lambda d: d.update(role="inner"))
    with pytest.raises(cli.CLIError, match="outer 최종 적합이 아니다"):
        _load(ws)


def test_external_fit_refused(ws):
    _rewrite_json(ws["manifests"][0], lambda d: d.update(external_folds_sha256="a" * 64))
    with pytest.raises(cli.CLIError, match="외부 분할 기록이 있는 fit"):
        _load(ws)


def test_fit_split_and_config_hash(ws):
    _rewrite_json(ws["manifests"][0], lambda d: d.update(split_hash="a" * 64))
    with pytest.raises(cli.CLIError, match="split_hash 가 --splits"):
        _load(ws)
    _rewrite_json(ws["manifests"][0], lambda d: d.update(split_hash=SPLIT_HASH,
                                                         config_hash="a" * 64))
    with pytest.raises(cli.CLIError, match="config_hash 가 --config"):
        _load(ws)


def test_seed_outside_plan_refused(ws):
    _rewrite_json(ws["manifests"][0], lambda d: d.update(model_seed=45))
    with pytest.raises(cli.CLIError, match="계획"):
        _load(ws)


def test_duplicate_slot_and_fit_id(ws):
    with pytest.raises(cli.CLIError, match="fit_id 중복"):
        _load(ws, manifests=ws["manifests"] + [ws["manifests"][0]])
    _rewrite_json(ws["manifests"][1], lambda d: d.update(model_seed=42))
    with pytest.raises(cli.CLIError, match="fit 이 둘이다"):
        _load(ws)


def test_missing_plan_fit_refused(ws):
    with pytest.raises(cli.CLIError, match="fit 이 빠졌다"):
        _load(ws, manifests=ws["manifests"][1:])


@pytest.mark.parametrize("name", cli.COMPARATOR_OUTER_NEIGHBOURS)
def test_neighbour_file_required(ws, name):
    (ws["manifests"][0].parent / name).unlink()
    with pytest.raises(cli.CLIError, match="대체 탐색하지 않는다"):
        _load(ws)


@pytest.mark.parametrize("field,value,match", [
    ("fit_id", "other", "fit_report 의 fit_id"),
    ("config_id", CID + 1, "≠ 선택"),
    ("epochs_run", E - 1, "outer E"),
    ("checkpoint_sha256", "a" * 64, "fit_report 와 다르다"),
])
def test_fit_report_guards(ws, field, value, match):
    _rewrite_json(ws["manifests"][0].parent / "fit_report.json",
                  lambda d: d.update({field: value}))
    with pytest.raises(cli.CLIError, match=match):
        _load(ws)


def _row_edit(ws, fn):
    _rewrite_rows(ws["manifests"][0].parent / "window_predictions.jsonl", fn)


def test_row_fit_id_guard(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], fit_id="x")] + rs[1:])
    with pytest.raises(cli.CLIError, match="fit_id 'x'"):
        _load(ws)


def test_row_cell_guard(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], cell="SG")] + rs[1:])
    with pytest.raises(cli.CLIError, match="cell/seed"):
        _load(ws)


def test_row_seed_guard(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], model_seed=43)] + rs[1:])
    with pytest.raises(cli.CLIError, match="cell/seed"):
        _load(ws)


def test_row_scope_guard(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], scope="inner_validation")] + rs[1:])
    with pytest.raises(cli.CLIError, match="outer test 만"):
        _load(ws)


def test_row_checkpoint_guard(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], checkpoint_sha256="a" * 64)] + rs[1:])
    with pytest.raises(cli.CLIError, match="checkpoint.pt 와 다르다"):
        _load(ws)


def test_row_training_subject_leak(ws):
    leak = ws["folds"]["outer_folds"][0]["train_subjects"][0]
    _row_edit(ws, lambda rs: [dict(rs[0], canonical_subject=leak)] + rs[1:])
    with pytest.raises(cli.CLIError, match="test 누설"):
        _load(ws)


def test_row_subject_outside_test(ws):
    _row_edit(ws, lambda rs: [dict(rs[0], canonical_subject=_canon(1))] + rs[1:])
    with pytest.raises(cli.CLIError, match="test subject 가 아니다"):
        _load(ws)


def test_fit_must_cover_outer_test(ws):
    s0 = ws["folds"]["outer_folds"][0]["test_subjects"][0]
    _row_edit(ws, lambda rs: [r for r in rs if r["canonical_subject"] != s0])
    with pytest.raises(cli.CLIError, match="test 와 다르다"):
        _load(ws)


def test_code_hash_uniform(ws):
    _rewrite_json(ws["manifests"][2], lambda d: d.update(code_hash="0" * 64))
    with pytest.raises(cli.CLIError, match="code_hash 가 다르다"):
        _load(ws)


def test_two_runs_for_subject_task_refused(ws):
    def fn(rs):
        rk2 = rs[0]["run_key"].replace("/seq", "/seq2")
        return [dict(r, run_key=rk2, window_key=r["window_key"].replace(r["run_key"], rk2))
                if r["run_key"] == rs[0]["run_key"] else r for r in rs]
    _row_edit(ws, fn)
    with pytest.raises(cli.CLIError, match="run 이 여럿"):
        _load(ws)


def test_incomplete_window_grid_refused(ws):
    _row_edit(ws, lambda rs: rs[1:])
    with pytest.raises(cli.CLIError, match="무결성 검사 실패"):
        _load(ws)


def test_rows_are_comparison_predictions_not_ad(ws):
    got = _load(ws)
    assert all(isinstance(p, EV.ComparisonWindowPrediction) for p in got["predictions"])
    with pytest.raises(EV.EvaluationError):
        EV.aggregate_runs(got["predictions"])


def test_fit_outer_fold_without_selection_refused(ws):
    _rewrite_json(ws["manifests"][0], lambda d: d["folds"].update(outer_fold=5))
    with pytest.raises(cli.CLIError, match="선택 기록이 없다"):
        _load(ws)


def test_sg_cell_runs_keyed_by_structure(ws):
    for m in ws["manifests"]:
        _rewrite_json(m, lambda d: d.update(cell="SG"))
        _rewrite_rows(m.parent / "window_predictions.jsonl",
                      lambda rs: [dict(r, cell="SG") for r in rs])
    sels = {of: _selection("SG", of, ws["cfg_hash"]) for of in ws["sels"]}
    runs = _load(ws, sels=sels, structure="SG")["runs"]
    assert {k[0] for k in runs} == {"SG"}
    assert EV.cell_balanced_accuracy(runs, "SG") == pytest.approx(0.75)
