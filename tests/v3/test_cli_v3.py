"""v3 CLI — `mobse/v3/cli.py`. 배선을 본다 (학습 자체는 test_fitting_v3 가 본다).

무거운 학습은 `train_fold` 를 대역으로 바꿔 건너뛴다. 이 시험이 지키는 것은
**CLI 가 config 의 잠긴 값을 실제로 강제하는가**, **저표본 수준이 학습 집합에만
적용되는가**, **outer fit 이 공통 E 를 update 로 옮기는가**, **식별자가 구조와
수준을 구분하는가** 다.
"""
from __future__ import annotations

import hashlib
import json
import types

import numpy as np
import pytest
import yaml

from mobse.v3 import cli as CLI
from mobse.v3 import fitting as FIT
from mobse.v3 import subsample as SUB
from mobse.v3.train import carry_epochs_to_outer

N_ROI, N_SAMPLES = 100, 30
TASKS = ("emomatching", "workingmemory")
SMOKE = CLI.Path(__file__).resolve().parents[2] / "configs" / "exploratory_v2" / "smoke.yaml"


def _win(path, rng):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, rng.standard_normal((N_SAMPLES, N_ROI)))
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def bed(tmp_path):
    """subject 30 명. inner fold 0 의 학습 집합이 18 명이라 수준 10 을 쓸 수 있다."""
    from mobse.v2.labels import window_key
    rng = np.random.default_rng(11)
    subs = [f"sub-{i:04d}" for i in range(1, 31)]
    canon = [f"ds002785:{s}" for s in subs]

    def build(tasks):
        recs = []
        for sub in subs:
            for task in tasks:
                wins = [{"path": str(tmp_path / "d" / sub / f"{sub}_{task}_{w}.npy"),
                         "sha256": _win(tmp_path / "d" / sub / f"{sub}_{task}_{w}.npy", rng),
                         "shape": [N_SAMPLES, N_ROI], "start_sec": 12.0 + 60 * w,
                         "source_frame_range": [w, w + N_SAMPLES]} for w in range(4)]
                recs.append({"record_type": "run",
                             "run_key": f"ds002785/{sub}/na/{task}/na/seq",
                             "canonical_subject": f"ds002785:{sub}",
                             "status": "ok", "windows": wins})
        return recs

    def dump(name, recs):
        p = tmp_path / name
        with p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"record_type": "header"}) + "\n")
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        return p

    task_paths = [dump(f"t_{t}.jsonl", build([t])) for t in TASKS]
    rest_path = dump("rest.jsonl", build(["restingstate"]))

    win_path = tmp_path / "windows.jsonl"
    with win_path.open("w", encoding="utf-8") as fh:
        for tp in task_paths:
            for line in tp.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("record_type") != "run":
                    continue
                task = FIT.task_of(rec["run_key"])
                for i, w in enumerate(rec["windows"]):
                    fh.write(json.dumps({
                        "schema_version": "wi02-windows-0.1",
                        "window_key": window_key(rec["run_key"], i),
                        "run_key": rec["run_key"], "data_sha256": w["sha256"],
                        "observed_label": task, "label_source": "task_metadata",
                        "n_roi": N_ROI, "n_samples": N_SAMPLES,
                        "start_sec": w["start_sec"], "end_sec": w["start_sec"] + 60,
                        "source_frame_range": w["source_frame_range"],
                        "target_grid": 2.0, "qc_flags": []}) + "\n")

    splits = tmp_path / "folds.json"
    splits.write_text(json.dumps({
        "split_hash": "a" * 12,
        "pilot": {"subjects": canon[:4]},
        "main_pool": {"subjects": canon[4:]},
        "outer_folds": [{"outer_fold": 0, "test_subjects": canon[4:8],
                         "train_subjects": canon[8:],
                         "inner": [{"inner_fold": 0, "val_subjects": canon[8:12],
                                    "train_subjects": canon[12:]}]}],
    }), encoding="utf-8")

    subjects = tmp_path / "subjects.jsonl"
    subjects.write_text("".join(
        json.dumps({"canonical_subject": c, "group_id": c}) + "\n" for c in canon),
        encoding="utf-8")

    raw = yaml.safe_load(SMOKE.read_text(encoding="utf-8"))
    raw["runtime"]["device"] = "cpu"
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    return {"tmp": tmp_path, "cfg": cfg_path, "splits": splits, "subjects": subjects,
            "windows": win_path, "rest": rest_path, "tasks": task_paths,
            "canon": canon}


def _argv(bed, out, **over):
    args = ["fit", "--config", str(bed["cfg"]), "--splits", str(bed["splits"]),
            "--subjects", str(bed["subjects"]), "--windows", str(bed["windows"]),
            "--rest-manifest", str(bed["rest"]), "--output-dir", str(out),
            "--task-manifests", *[str(p) for p in bed["tasks"]],
            "--cell", "A", "--roi-structure", "embedding", "--n-train-level", "10",
            "--outer-fold", "0", "--inner-fold", "0", "--config-id", "0",
            "--model-seed", "42"]
    for key, value in over.items():
        flag = "--" + key.replace("_", "-")
        if value is None:
            i = args.index(flag)
            del args[i:i + 2]
        elif flag in args:
            args[args.index(flag) + 1] = str(value)
        else:
            args += [flag, str(value)]
    return args


@pytest.fixture
def stub_train(monkeypatch):
    """train_fold 를 대역으로 바꾼다. 받은 인자를 기록한다."""
    seen = {}

    def fake(train_set, eval_set, transform, **kw):
        seen.update(kw)
        seen["n_train_windows"] = len(train_set)
        probs = {r.window_key: 0.5 for r in eval_set.refs}
        result = FIT.FitResult(
            role=kw["fold"].role, cell=kw["cell"], outer_fold=kw["fold"].outer_fold,
            inner_fold=kw["fold"].inner_fold, config_id=kw["config_id"],
            model_seed=kw["model_seed"], roi_structure=kw["roi_structure"],
            epochs_run=3, best_epoch=2, epoch_ceiling=9,
            update_budget=kw["update_budget"], updates_per_epoch=6, updates_run=18,
            val_losses=[0.7, 0.6, 0.65], eval_run_probs={}, eval_window_probs=probs,
            eval_loss=0.6, eval_balanced_accuracy=0.5,
            transform=transform.provenance(), timing={"train_seconds": 0.1},
            memory={"device": "cpu"}, encoder_init_hash="0" * 64, rng_note="stub",
            determinism={}, eval_epoch=2)

        # 저장 경로가 실제 모델을 요구하므로 **만들기만** 한다 (학습은 건너뛴다).
        from mobse.v2.models import ModelConfig
        mcfg = ModelConfig(n_roi=int(train_set.x.shape[1]),
                           n_samples=int(train_set.x.shape[2]),
                           pca_dim=int(train_set.pca.shape[1]), dropout=0.1)
        model = FIT.build_fit_model(kw["cell"], mcfg, transform,
                                    roi_structure=kw["roi_structure"])
        return result, model

    monkeypatch.setattr(FIT, "train_fold", fake)
    monkeypatch.setattr(CLI.FIT, "train_fold", fake)
    return seen


# --------------------------------------------------------------------------- #
# 식별자
# --------------------------------------------------------------------------- #


def test_fit_id_separates_structure_and_level():
    base = dict(role="inner", cell="A", roi_structure="embedding", n_train_level=10,
                outer_fold=0, inner_fold=0, model_seed=42, config_id=0,
                split_hash="x", cfg_hash="y")
    a = CLI.fit_id(**base)
    b = CLI.fit_id(**{**base, "roi_structure": "readout"})
    c = CLI.fit_id(**{**base, "n_train_level": 20})
    assert len({a, b, c}) == 3, "구조·수준이 다른 fit 이 같은 식별자를 갖는다"


def test_fit_id_refuses_unknown_names():
    base = dict(role="inner", cell="A", roi_structure="embedding", n_train_level=10,
                outer_fold=0, inner_fold=0, model_seed=42, config_id=0,
                split_hash="x", cfg_hash="y")
    with pytest.raises(CLI.CLIError, match="cell"):
        CLI.fit_id(**{**base, "cell": "NG"})
    with pytest.raises(CLI.CLIError, match="roi_structure"):
        CLI.fit_id(**{**base, "roi_structure": "pca"})


# --------------------------------------------------------------------------- #
# config 의 잠긴 값을 CLI 가 강제한다
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("over,message", [
    ({"model_seed": 7}, "train.model_seeds"),
    ({"roi_structure": "mean"}, "config 가 고른"),
    ({"n_train_level": 33}, "curve.levels"),
])
def test_cli_refuses_values_outside_the_locked_config(bed, over, message, capsys):
    rc = CLI.main(_argv(bed, bed["tmp"] / "out", **over))
    assert rc == 2
    assert message in json.loads(capsys.readouterr().out)["error"]


def test_missing_input_path_is_not_searched(bed, capsys):
    rc = CLI.main(_argv(bed, bed["tmp"] / "out", splits=bed["tmp"] / "없다.json"))
    assert rc == 2
    assert "대체 탐색하지 않는다" in json.loads(capsys.readouterr().out)["error"]


# --------------------------------------------------------------------------- #
# 저표본 수준
# --------------------------------------------------------------------------- #


def test_level_is_applied_to_training_only(bed, stub_train):
    out = bed["tmp"] / "out"
    assert CLI.main(_argv(bed, out)) == 0
    man = json.loads((out / "fit_manifest.json").read_text(encoding="utf-8"))
    assert man["curve"]["n_train_subjects_used"] == 10
    assert man["curve"]["n_train_subjects_available"] == 18
    # 평가 집합은 줄지 않는다.
    assert man["folds"]["n_eval_subjects"] == 4
    assert len(man["fit_subjects"]) == 10
    assert set(man["fit_subjects"]) <= set(bed["canon"][12:])


def test_levels_are_nested(bed, stub_train, capsys):
    """작은 수준은 큰 수준의 부분집합이고, 학습 집합보다 큰 수준은 거부된다."""
    out10, out20 = bed["tmp"] / "o10", bed["tmp"] / "o20"
    assert CLI.main(_argv(bed, out10, n_train_level=10)) == 0
    capsys.readouterr()
    assert CLI.main(_argv(bed, out20, n_train_level=20)) == 2   # 18 명뿐이라 거부
    assert "보다 크다" in json.loads(capsys.readouterr().out)["error"]
    small = json.loads((out10 / "fit_manifest.json").read_text(encoding="utf-8"))
    full = SUB.subsample_train(bed["canon"][12:], 18, outer_fold=0, seed_base=40000)
    assert set(small["fit_subjects"]) <= set(full)


# --------------------------------------------------------------------------- #
# inner / outer
# --------------------------------------------------------------------------- #


def test_inner_fit_takes_no_selection(bed, stub_train, capsys):
    sel = bed["tmp"] / "sel.json"
    sel.write_text(json.dumps({"common_epochs": 3, "inner_train_windows": 80}),
                   encoding="utf-8")
    rc = CLI.main(_argv(bed, bed["tmp"] / "out", selection=sel))
    assert rc == 2
    assert "--selection 을 받지 않는다" in json.loads(capsys.readouterr().out)["error"]


def test_outer_fit_requires_a_selection(bed, stub_train, capsys):
    rc = CLI.main(_argv(bed, bed["tmp"] / "out", inner_fold=9))
    assert rc == 2
    assert "--selection 이 필요하다" in json.loads(capsys.readouterr().out)["error"]


def test_outer_fit_carries_the_common_epochs_as_updates(bed, stub_train):
    sel = bed["tmp"] / "sel.json"
    sel.write_text(json.dumps({"common_epochs": 40, "inner_train_windows": 80}),
                   encoding="utf-8")
    out = bed["tmp"] / "outer"
    assert CLI.main(_argv(bed, out, inner_fold=9, selection=sel)) == 0
    man = json.loads((out / "fit_manifest.json").read_text(encoding="utf-8"))
    expected = carry_epochs_to_outer(40, 80, stub_train["n_train_windows"],
                                     batch_size=32, update_budget=5000)
    assert man["budget"]["epochs_exact"] == expected
    assert man["budget"]["carry_unit"] == "update"
    assert stub_train["epochs_exact"] == expected


@pytest.mark.parametrize("bad", [
    {"common_epochs": 0, "inner_train_windows": 80},
    {"common_epochs": 3},
])
def test_selection_file_must_carry_both_values(bed, stub_train, bad, capsys):
    sel = bed["tmp"] / "sel.json"
    sel.write_text(json.dumps(bad), encoding="utf-8")
    rc = CLI.main(_argv(bed, bed["tmp"] / "out", inner_fold=9, selection=sel))
    assert rc == 2
    assert "selection" in json.loads(capsys.readouterr().out)["error"]


# --------------------------------------------------------------------------- #
# 산출물
# --------------------------------------------------------------------------- #


def test_outputs_are_not_overwritten(bed, stub_train, capsys):
    out = bed["tmp"] / "out"
    assert CLI.main(_argv(bed, out)) == 0
    capsys.readouterr()                      # 첫 판의 출력을 비운다
    rc = CLI.main(_argv(bed, out))
    assert rc == 2
    assert "덮어쓰지 않는다" in json.loads(capsys.readouterr().out)["error"]


def test_predictions_record_structure_and_level(bed, stub_train):
    out = bed["tmp"] / "out"
    assert CLI.main(_argv(bed, out)) == 0
    rows = [json.loads(l) for l in
            (out / "window_predictions.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip() and "window_key" in l]
    assert rows, "예측 행이 비었다"
    assert {r["roi_structure"] for r in rows} == {"embedding"}
    assert {r["n_train_level"] for r in rows} == {10}
    # 평가 집합 4 명 × 2 task × 4 창
    assert len(rows) == 4 * 2 * 4


def test_report_records_the_budget_not_a_min_epoch(bed, stub_train):
    out = bed["tmp"] / "out"
    assert CLI.main(_argv(bed, out)) == 0
    rep = json.loads((out / "fit_report.json").read_text(encoding="utf-8"))
    assert rep["update_budget"] == 5000
    assert "epoch_ceiling" in rep
    assert "min_epoch" not in rep and "min_updates" not in rep
