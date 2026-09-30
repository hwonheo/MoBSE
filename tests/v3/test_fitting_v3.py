"""v3 fold 적합 — `mobse/v3/fitting.py` (결정 28-2·31-1·32).

v2 의 `train_fold` 와 무엇이 달라야 하는지를 검사한다. 합성 자료는
`tests/v2/test_fitting.py` 와 같은 모양으로 여기서 다시 만든다 — `tests/v2` 는
패키지가 아니라 import 할 수 없고, v2 는 동결이라 그쪽을 바꾸지도 않는다.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from mobse.v2 import templates as T
from mobse.v2 import fitting as FIT2
from mobse.v2.labels import window_key
from mobse.v2.train import TrainError
from mobse.v3 import fitting as FIT
from mobse.v3 import train as TR3

N_ROI = 100
N_SAMPLES = 30
TASKS = ("emomatching", "workingmemory")


def _write_window(path, rng) -> str:
    arr = rng.standard_normal((N_SAMPLES, N_ROI)).astype(np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_key(sub: str, task: str) -> str:
    return f"ds002785/{sub}/na/{task}/na/seq"


@pytest.fixture
def synthetic(tmp_path):
    """subject 20 명 × (2 task + rest) × 4 창."""
    rng = np.random.default_rng(7)
    subs = [f"sub-{i:04d}" for i in range(1, 21)]
    canon = [f"ds002785:{s}" for s in subs]

    def build(tasks, labelled):
        records = []
        for sub in subs:
            for task in tasks:
                wins = []
                for w in range(4):
                    p = tmp_path / "deriv" / sub / f"{sub}_{task}_win-{w}.npy"
                    wins.append({"path": str(p), "sha256": _write_window(p, rng),
                                 "shape": [N_SAMPLES, N_ROI],
                                 "start_sec": 12.0 + 60 * w,
                                 "source_frame_range": [w, w + N_SAMPLES]})
                records.append({"record_type": "run", "run_key": _run_key(sub, task),
                                "canonical_subject": f"ds002785:{sub}",
                                "status": "ok", "windows": wins})
        return records

    def dump(name, records):
        p = tmp_path / name
        with p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"record_type": "header"}) + "\n")
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return p

    task_paths = [dump(f"wi02_{t}.jsonl", build([t], True)) for t in TASKS]
    rest_path = dump("wi02_rest.jsonl", build(["restingstate"], False))

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

    folds = {
        "pilot": {"subjects": canon[:4]},
        "main_pool": {"subjects": canon[4:]},
        "outer_folds": [{
            "outer_fold": 0,
            "test_subjects": canon[4:8],
            "train_subjects": canon[8:],
            "inner": [{"inner_fold": 0, "val_subjects": canon[8:12],
                       "train_subjects": canon[12:]}],
        }],
    }
    return {"task_paths": task_paths, "rest_path": rest_path, "folds": folds}


def _sets(synthetic, outer=0, inner=0):
    fold = FIT.resolve_fold_subjects(synthetic["folds"], outer, inner)
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    tr = FIT.fit_fold_transform(rest, fold.train,
                                bank_seed=T.bank_seed(outer, min(inner, 9)))
    task_refs = []
    for tp in synthetic["task_paths"]:
        task_refs += FIT.refs_from_extract_manifest(tp, labelled=True)
    train_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.train), tr)
    eval_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.evaluate), tr)
    return fold, tr, train_set, eval_set


# --------------------------------------------------------------------------- #
# v2 는 손대지 않았다
# --------------------------------------------------------------------------- #


def test_importing_v3_does_not_change_the_frozen_v2_rule():
    """v3 를 import 해도 v2 의 잠긴 상수는 그대로다 (잠금 9b7b11cf 가 v2 를 해시한다)."""
    from mobse.v2 import train as TR2
    assert TR2.MIN_UPDATES == 5000
    assert TR2.MAX_EPOCHS == 400
    assert FIT2.train_fold is not FIT.train_fold


# --------------------------------------------------------------------------- #
# 결정 31-1 — epoch 상한은 상수가 아니라 예산에서 나온다
# --------------------------------------------------------------------------- #


def test_inner_fit_ceiling_comes_from_the_update_budget(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    budget = 12
    res, _ = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                            model_seed=42, fold=fold, update_budget=budget)
    expected = TR3.epochs_for_budget(len(train_set), update_budget=budget)
    assert res.epoch_ceiling == expected
    assert res.update_budget == budget
    assert 1 <= res.epochs_run <= expected
    assert res.updates_run == res.updates_per_epoch * res.epochs_run


def test_a_tiny_training_set_gets_a_ceiling_v1_would_have_refused(synthetic):
    """v1 은 MAX_EPOCHS 400 이 상한이라 이 구간을 아예 돌 수 없었다 (결정 32 의 동기)."""
    _, _, train_set, _ = _sets(synthetic)
    ceiling = TR3.epochs_for_budget(len(train_set), update_budget=TR3.UPDATE_BUDGET)
    assert ceiling > 400


def test_budget_must_be_positive(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    with pytest.raises(TrainError, match="양수"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                       model_seed=42, fold=fold, update_budget=0)


# --------------------------------------------------------------------------- #
# 결정 32 — best checkpoint 에 최소 epoch 결합이 없다
# --------------------------------------------------------------------------- #


def test_best_epoch_may_be_the_first_epoch(synthetic, monkeypatch):
    """검증 손실이 계속 나빠지면 best 는 epoch 1 이다 — v1 은 고를 수 없던 값이다."""
    fold, tr, train_set, eval_set = _sets(synthetic)
    seq = iter([0.1 * (i + 1) for i in range(50)])
    monkeypatch.setattr(FIT, "subject_equal_loss", lambda _rows: next(seq))
    res, _ = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                            model_seed=42, fold=fold, update_budget=200)
    assert res.best_epoch == 1
    assert res.eval_epoch == 1
    # patience 만큼만 더 돌고 멈춘다.
    assert res.epochs_run == 1 + FIT.PATIENCE


def test_returned_model_is_the_best_checkpoint_not_the_last(synthetic, monkeypatch):
    """best 가 epoch 1 이면 돌아오는 가중치도 epoch 1 것이어야 한다 (결정 12·32).

    같은 seed 로 1 epoch 만 돈 판(outer 경로)과 state_dict 를 대조한다. 두 판이
    같다는 것이 "마지막 epoch 가 아니라 best 를 실어 돌려준다" 의 증거다.
    """
    import torch

    fold, tr, train_set, eval_set = _sets(synthetic)
    seq = iter([0.1 * (i + 1) for i in range(50)])
    monkeypatch.setattr(FIT, "subject_equal_loss", lambda _rows: next(seq))
    res, model = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                                model_seed=42, fold=fold, update_budget=200)
    assert res.best_epoch == 1
    assert res.epochs_run > res.best_epoch          # 마지막 epoch 가 아니다

    one, _ = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                            model_seed=42, fold=fold, early_stopping=False,
                            epochs_exact=1, update_budget=200)
    assert one.epochs_run == 1
    ref = _one_epoch_state(synthetic, tr, fold, train_set, eval_set)
    got = model.state_dict()
    assert set(got) == set(ref)
    for k in got:
        assert torch.equal(got[k], ref[k]), k


def _one_epoch_state(synthetic, tr, fold, train_set, eval_set):
    """같은 seed·같은 자료로 1 epoch 만 돈 모델의 state_dict."""
    _, m = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                          model_seed=42, fold=fold, early_stopping=False,
                          epochs_exact=1, update_budget=200)
    return {k: v.detach().clone() for k, v in m.state_dict().items()}


# --------------------------------------------------------------------------- #
# 예산은 상한이다 — outer 로 옮길 때 조용히 자르지 않는다
# --------------------------------------------------------------------------- #


def test_outer_fit_refuses_an_E_above_the_budget_ceiling(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    ceiling = TR3.epochs_for_budget(len(train_set), update_budget=50)
    with pytest.raises(FIT.FitError, match="예산 상한"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                       model_seed=42, fold=fold, early_stopping=False,
                       epochs_exact=ceiling + 1, update_budget=50)


def test_outer_fit_runs_exactly_E_epochs_within_the_budget(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    res, _ = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                            model_seed=42, fold=fold, early_stopping=False,
                            epochs_exact=2, update_budget=200)
    assert res.epochs_run == 2
    assert res.best_epoch == 2 and res.eval_epoch == 2
    assert res.val_losses == []


def test_outer_fit_still_refuses_early_stopping(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    outer = FIT.FoldSubjects(role=FIT.ROLE_OUTER, outer_fold=fold.outer_fold,
                             inner_fold=9, train=fold.train, evaluate=fold.evaluate,
                             eval_role="outer_test")
    with pytest.raises(FIT.FitError, match="early stopping"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                       model_seed=42, fold=outer, early_stopping=True,
                       epochs_exact=2, update_budget=200)


# --------------------------------------------------------------------------- #
# 결정 28-2 — ROI 정체 구조
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("structure", FIT.ROI_STRUCTURES)
def test_every_roi_structure_runs_and_is_recorded(synthetic, structure):
    fold, tr, train_set, eval_set = _sets(synthetic)
    res, model = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                                model_seed=42, fold=fold, roi_structure=structure,
                                update_budget=12)
    assert res.roi_structure == structure
    assert model.roi_structure == structure


def test_unknown_roi_structure_is_refused(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    with pytest.raises(FIT.FitError, match="roi_structure"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                       model_seed=42, fold=fold, roi_structure="pca",
                       update_budget=12)


def test_v3_has_no_structure_comparators(synthetic):
    """NG·SG 는 v1 의 §6 구조 비교다. v3 의 칸은 A–D × ROI 구조뿐이다 (결정 33)."""
    fold, tr, train_set, eval_set = _sets(synthetic)
    for cell in ("NG", "SG"):
        with pytest.raises(FIT.FitError, match="cell"):
            FIT.train_fold(train_set, eval_set, tr, cell=cell, config_id=0,
                           model_seed=42, fold=fold, update_budget=12)


def test_build_fit_model_picks_the_bank_by_cell(synthetic):
    _, tr, train_set, _ = _sets(synthetic)
    from mobse.v2.models import ModelConfig
    cfg = ModelConfig(n_roi=N_ROI, n_samples=N_SAMPLES, pca_dim=10, dropout=0.1)
    brain = FIT.build_fit_model("A", cfg, tr)
    null = FIT.build_fit_model("C", cfg, tr)
    assert np.allclose(brain.template_bank.numpy(), tr.brain.templates)
    assert np.allclose(null.template_bank.numpy(), tr.null.templates)
    assert brain.routing == "dynamic"
    assert FIT.build_fit_model("B", cfg, tr).routing == "fixed"
