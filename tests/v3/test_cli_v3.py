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


def test_level_cuts_the_outer_pool_then_splits_inside_it(bed, stub_train):
    """수준은 **outer 학습 pool** 을 자르고, inner 는 그 안에서 다시 그어진다."""
    out = bed["tmp"] / "out"
    assert CLI.main(_argv(bed, out)) == 0
    man = json.loads((out / "fit_manifest.json").read_text(encoding="utf-8"))
    pool_n = man["curve"]["n_train_subjects_in_level_pool"]
    assert pool_n == 10
    used = man["curve"]["n_train_subjects_used"]
    # inner 3-fold 이므로 학습은 pool 의 약 2/3 다. pool 보다 작아야 한다.
    assert 0 < used < pool_n
    assert len(man["fit_subjects"]) == used
    # pool 은 outer 학습 집합 안에서 나온다 — test·pilot 에 닿지 않는다.
    assert set(man["fit_subjects"]) <= set(bed["canon"][8:])
    assert set(man["fit_subjects"]).isdisjoint(bed["canon"][4:8])   # outer test
    assert set(man["fit_subjects"]).isdisjoint(bed["canon"][:4])    # pilot


def test_pools_are_nested_and_an_oversized_level_is_refused(bed, stub_train, capsys):
    """작은 수준의 pool 은 큰 수준 pool 의 부분집합이고, pool 보다 큰 수준은 거부된다."""
    out10, out20, out40 = (bed["tmp"] / "o10", bed["tmp"] / "o20", bed["tmp"] / "o40")
    assert CLI.main(_argv(bed, out10, n_train_level=10)) == 0
    assert CLI.main(_argv(bed, out20, n_train_level=20)) == 0
    pool10 = SUB.subsample_train(bed["canon"][8:], 10, outer_fold=0, seed_base=40000)
    pool20 = SUB.subsample_train(bed["canon"][8:], 20, outer_fold=0, seed_base=40000)
    assert set(pool10) < set(pool20), "작은 수준이 큰 수준의 부분집합이 아니다"
    capsys.readouterr()
    assert CLI.main(_argv(bed, out40, n_train_level=40)) == 2   # pool 이 22 명뿐이다
    assert "보다 크다" in json.loads(capsys.readouterr().out)["error"]


def test_inner_folds_partition_the_level_pool(bed, stub_train):
    """같은 수준의 inner fold 셋이 pool 을 겹침 없이 덮는다."""
    pool = SUB.subsample_train(bed["canon"][8:], 20, outer_fold=0, seed_base=40000)
    parts = SUB.inner_split_within(pool, outer_fold=0, n_inner_folds=3)
    vals = [set(p["val_subjects"]) for p in parts]
    assert set().union(*vals) == set(pool)
    assert sum(len(v) for v in vals) == len(pool), "val 조각이 겹친다"
    for part, val in zip(parts, vals):
        assert set(part["train_subjects"]) == set(pool) - val


def test_outer_role_trains_on_the_whole_level_pool(bed, stub_train):
    sel = bed["tmp"] / "sel.json"
    sel.write_text(json.dumps({"common_epochs": 5, "inner_train_windows": 80}),
                   encoding="utf-8")
    out = bed["tmp"] / "outer_pool"
    assert CLI.main(_argv(bed, out, inner_fold=9, selection=sel,
                          n_train_level=20)) == 0
    man = json.loads((out / "fit_manifest.json").read_text(encoding="utf-8"))
    assert man["curve"]["n_train_subjects_used"] == 20       # pool 전체
    assert man["folds"]["n_eval_subjects"] == 4              # outer test 는 불변


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


# --------------------------------------------------------------------------- #
# select — 구조마다 A-D 공동 (2026-10-01 승인)
# --------------------------------------------------------------------------- #


def _fake_fit_dir(root, *, structure, cell, inner_fold, config_id, loss, ba,
                  best_epoch=4, ceiling=9, n_eval=4, n_train_windows=104,
                  level=20, role="inner"):
    d = root / f"{structure}_{cell}_c{config_id}_i{inner_fold}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "fit_manifest.json").write_text(json.dumps({
        "role": role, "cell": cell, "roi_structure": structure,
        "curve": {"n_train_level": level},
        "folds": {"inner_fold": inner_fold, "n_eval_subjects": n_eval}}),
        encoding="utf-8")
    (d / "fit_report.json").write_text(json.dumps({
        "config_id": config_id, "eval_loss": loss, "eval_balanced_accuracy": ba,
        "best_epoch": best_epoch, "epoch_ceiling": ceiling,
        "n_train_windows": n_train_windows}), encoding="utf-8")
    return d


def _grid_dirs(root, structure, *, winner, n_configs=8, cells=("A", "B", "C", "D")):
    """이긴 config 만 손실이 낮은 완전한 grid 를 만든다."""
    dirs = []
    for c in range(n_configs):
        for cell in cells:
            for f in range(3):
                loss = 0.30 if c == winner else 0.70
                dirs.append(_fake_fit_dir(root, structure=structure, cell=cell,
                                          inner_fold=f, config_id=c, loss=loss,
                                          ba=0.9 if c == winner else 0.5))
    return dirs


def test_select_picks_a_config_per_structure(bed, tmp_path, capsys):
    """구조마다 따로 고른다 — 한 config 가 다른 구조에 최악일 수 있기 때문이다."""
    root = tmp_path / "fits"
    dirs = _grid_dirs(root, "embedding", winner=0) + _grid_dirs(root, "readout", winner=5)
    out = tmp_path / "sel"
    rc = CLI.main(["select", "--config", str(bed["cfg"]), "--output-dir", str(out),
                   "--fit-dirs", *[str(d) for d in dirs]])
    assert rc == 0, capsys.readouterr().out
    emb = json.loads((out / "selection_embedding.json").read_text(encoding="utf-8"))
    rdt = json.loads((out / "selection_readout.json").read_text(encoding="utf-8"))
    assert emb["config_id"] == 0 and rdt["config_id"] == 5
    assert emb["roi_structure"] == "embedding"
    assert emb["common_epochs"] >= 1
    assert emb["inner_train_windows"] == 104
    assert "구조별 분리" in emb["selection_scope"]


def test_select_refuses_a_mixed_level(bed, tmp_path, capsys):
    root = tmp_path / "fits"
    dirs = _grid_dirs(root, "embedding", winner=0)
    dirs.append(_fake_fit_dir(root, structure="embedding", cell="A", inner_fold=0,
                              config_id=0, loss=0.3, ba=0.9, level=40))
    rc = CLI.main(["select", "--config", str(bed["cfg"]),
                   "--output-dir", str(tmp_path / "s2"),
                   "--fit-dirs", *[str(d) for d in dirs]])
    assert rc == 2
    assert "수준이 섞였다" in json.loads(capsys.readouterr().out)["error"]


def test_select_refuses_an_outer_fit(bed, tmp_path, capsys):
    root = tmp_path / "fits"
    d = _fake_fit_dir(root, structure="embedding", cell="A", inner_fold=9,
                      config_id=0, loss=0.3, ba=0.9, role="outer")
    rc = CLI.main(["select", "--config", str(bed["cfg"]),
                   "--output-dir", str(tmp_path / "s3"), "--fit-dirs", str(d)])
    assert rc == 2
    assert "inner fit 이 아니다" in json.loads(capsys.readouterr().out)["error"]


def test_select_uses_the_tightest_ceiling(bed, tmp_path, capsys):
    """inner fold 마다 학습 크기가 달라 상한이 다르면 가장 빡빡한 쪽을 쓴다."""
    root = tmp_path / "fits"
    dirs = _grid_dirs(root, "embedding", winner=0)
    # 한 fold 의 상한만 낮추고, 그보다 큰 best epoch 를 가진 fit 을 넣는다.
    bad = _fake_fit_dir(root, structure="embedding", cell="A", inner_fold=1,
                        config_id=0, loss=0.3, ba=0.9, best_epoch=8, ceiling=5)
    rc = CLI.main(["select", "--config", str(bed["cfg"]),
                   "--output-dir", str(tmp_path / "s4"),
                   "--fit-dirs", *[str(d) for d in dirs], str(bad)])
    assert rc == 2
    assert "가장 빡빡한" in json.loads(capsys.readouterr().out)["error"]


def test_selection_file_feeds_the_outer_fit(bed, tmp_path, stub_train):
    """select 가 쓴 파일을 fit --selection 이 그대로 받는다."""
    root = tmp_path / "fits"
    dirs = _grid_dirs(root, "embedding", winner=0)
    out = tmp_path / "sel"
    assert CLI.main(["select", "--config", str(bed["cfg"]), "--output-dir", str(out),
                     "--fit-dirs", *[str(d) for d in dirs]]) == 0
    sel = out / "selection_embedding.json"
    assert CLI.main(_argv(bed, tmp_path / "o", inner_fold=9, selection=sel,
                          n_train_level=20)) == 0


# --------------------------------------------------------------------------- #
# evaluate — endpoint 정의는 v1 과 같다 (2026-10-01 승인)
# --------------------------------------------------------------------------- #


def _outer_pred_dir(root, *, structure, level, outer_fold, subjects, correct_cells,
                    seeds=(42, 43, 44)):
    """outer fit 하나의 산출물을 만든다. `correct_cells` 의 칸만 정답을 낸다."""
    from mobse.v2.labels import window_key
    d = root / f"{structure}_n{level}_o{outer_fold}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "fit_manifest.json").write_text(json.dumps({
        "role": "outer", "cell": "A", "roi_structure": structure,
        "curve": {"n_train_level": level},
        "folds": {"outer_fold": outer_fold, "inner_fold": 9, "n_eval_subjects":
                  len(subjects)}}), encoding="utf-8")
    rows = []
    for sub in subjects:
        for task, truth in (("emomatching", 0), ("workingmemory", 1)):
            rk = f"ds002785/{sub}/na/{task}/na/seq"
            for cell in ("A", "B", "C", "D"):
                good = cell in correct_cells
                p1 = (0.9 if truth == 1 else 0.1) if good else (0.1 if truth == 1 else 0.9)
                for seed in seeds:
                    for w in range(4):
                        rows.append({"canonical_subject": sub, "group_id": sub,
                                     "run_key": rk, "window_key": window_key(rk, w),
                                     "truth": truth, "p_class1": p1, "cell": cell,
                                     "model_seed": seed})
    with (d / "window_predictions.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return d


def _curve_dirs(root, *, structure="embedding", level=20, n_folds=5,
                correct_cells=("A", "B")):
    dirs, k = [], 0
    for f in range(n_folds):
        subs = [f"ds002785:sub-{i:04d}" for i in range(k, k + 4)]
        k += 4
        dirs.append(_outer_pred_dir(root, structure=structure, level=level,
                                    outer_fold=f, subjects=subs,
                                    correct_cells=correct_cells))
    return dirs


def _subjects_file(root, dirs):
    subs = set()
    for d in dirs:
        for line in (d / "window_predictions.jsonl").read_text(encoding="utf-8").splitlines():
            subs.add(json.loads(line)["canonical_subject"])
    p = root / "subjects.jsonl"
    p.write_text("".join(json.dumps({"canonical_subject": s, "group_id": s}) + "\n"
                         for s in sorted(subs)), encoding="utf-8")
    return p


def test_evaluate_pools_all_outer_folds(bed, tmp_path, capsys):
    root = tmp_path / "ev"
    dirs = _curve_dirs(root)
    subj = _subjects_file(root, dirs)
    out = tmp_path / "curve"
    rc = CLI.main(["evaluate", "--config", str(bed["cfg"]), "--subjects", str(subj),
                   "--output-dir", str(out), "--fit-dirs", *[str(d) for d in dirs]])
    assert rc == 0, capsys.readouterr().out
    rec = json.loads((out / "curve_point_embedding_n20.json").read_text(encoding="utf-8"))
    assert rec["n_outer_folds"] == 5
    assert rec["n_subjects"] == 20
    # A·B 만 정답을 내게 만들었으므로 BA 가 갈린다.
    assert rec["cell_balanced_accuracy"]["A"] == 1.0
    assert rec["cell_balanced_accuracy"]["C"] == 0.0
    # H2 (A-C) 는 97.5% CI, interaction 은 95% CI 를 쓴다.
    assert rec["contrasts"]["H2_A_minus_C"]["pct"] == [1.25, 98.75]
    assert rec["contrasts"]["interaction"]["pct"] == [2.5, 97.5]
    assert rec["delta"] == 0.02


def test_evaluate_refuses_a_missing_outer_fold(bed, tmp_path, capsys):
    """빠진 fold 를 0 으로 세지 않는다 — endpoint 는 pooled 다."""
    root = tmp_path / "ev2"
    dirs = _curve_dirs(root, n_folds=4)
    subj = _subjects_file(root, dirs)
    rc = CLI.main(["evaluate", "--config", str(bed["cfg"]), "--subjects", str(subj),
                   "--output-dir", str(tmp_path / "c2"),
                   "--fit-dirs", *[str(d) for d in dirs]])
    assert rc == 2
    assert "fold" in json.loads(capsys.readouterr().out)["error"]


def test_evaluate_refuses_mixed_structures(bed, tmp_path, capsys):
    root = tmp_path / "ev3"
    dirs = _curve_dirs(root) + _curve_dirs(tmp_path / "ev3b", structure="readout")
    subj = _subjects_file(root, dirs)
    rc = CLI.main(["evaluate", "--config", str(bed["cfg"]), "--subjects", str(subj),
                   "--output-dir", str(tmp_path / "c3"),
                   "--fit-dirs", *[str(d) for d in dirs]])
    assert rc == 2
    assert "섞였다" in json.loads(capsys.readouterr().out)["error"]


def test_evaluate_refuses_an_inner_fit(bed, tmp_path, capsys):
    root = tmp_path / "ev4"
    d = _fake_fit_dir(root, structure="embedding", cell="A", inner_fold=0,
                      config_id=0, loss=0.3, ba=0.9)
    (d / "window_predictions.jsonl").write_text("", encoding="utf-8")
    rc = CLI.main(["evaluate", "--config", str(bed["cfg"]),
                   "--subjects", str(bed["subjects"]),
                   "--output-dir", str(tmp_path / "c4"), "--fit-dirs", str(d)])
    assert rc == 2
    assert "outer fit 이 아니다" in json.loads(capsys.readouterr().out)["error"]
