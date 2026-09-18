"""fold 범위 적합 — `mobse/v2/fitting.py` (계획서 §4·§5·§6·§7)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mobse.v2 import fitting as FIT
from mobse.v2 import templates as T
from mobse.v2.features import FeatureError
from mobse.v2.train import TrainError

N_ROI = 100
N_SAMPLES = 30
TASKS = ("emomatching", "workingmemory")


# --------------------------------------------------------------------------- #
# 합성 자료
# --------------------------------------------------------------------------- #


def _write_window(path: Path, rng) -> str:
    arr = rng.standard_normal((N_SAMPLES, N_ROI)).astype(np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_key(sub: str, task: str) -> str:
    return f"ds002785/{sub}/na/{task}/na/seq"


@pytest.fixture
def synthetic(tmp_path):
    """subject 20명 × (2 task + rest) × 4창 을 만든다."""
    rng = np.random.default_rng(7)
    subs = [f"sub-{i:04d}" for i in range(1, 21)]
    canon = [f"ds002785:{s}" for s in subs]

    def build(tasks, labelled):
        records = []
        for sub in subs:
            for task in tasks:
                rk = _run_key(sub, task)
                wins = []
                for w in range(4):
                    p = tmp_path / "deriv" / sub / f"{sub}_{task}_win-{w}.npy"
                    wins.append({"path": str(p), "sha256": _write_window(p, rng),
                                 "shape": [N_SAMPLES, N_ROI], "start_sec": 12.0 + 60 * w,
                                 "source_frame_range": [w, w + N_SAMPLES]})
                records.append({"record_type": "run", "run_key": rk,
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

    # 창 manifest (label 원천)
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
                        "window_key": FIT.window_key(rec["run_key"], i),
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
    return {"tmp": tmp_path, "task_paths": task_paths, "rest_path": rest_path,
            "windows": win_path, "folds": folds, "canon": canon}


# --------------------------------------------------------------------------- #
# 참조·검증
# --------------------------------------------------------------------------- #


def test_refs_and_crosscheck_agree(synthetic):
    refs = []
    for tp in synthetic["task_paths"]:
        refs += FIT.refs_from_extract_manifest(tp, labelled=True)
    assert len(refs) == 20 * 2 * 4
    assert FIT.crosscheck_with_windows_manifest(refs, synthetic["windows"])["n_windows"] == len(refs)


def test_crosscheck_catches_a_label_mismatch(synthetic, tmp_path):
    refs = []
    for tp in synthetic["task_paths"]:
        refs += FIT.refs_from_extract_manifest(tp, labelled=True)
    bad = tmp_path / "bad_windows.jsonl"
    lines = synthetic["windows"].read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["observed_label"] = "workingmemory" if first["observed_label"] == "emomatching" else "emomatching"
    bad.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(FIT.FitError, match="label"):
        FIT.crosscheck_with_windows_manifest(refs, bad)


def test_crosscheck_catches_a_hash_mismatch(synthetic, tmp_path):
    refs = []
    for tp in synthetic["task_paths"]:
        refs += FIT.refs_from_extract_manifest(tp, labelled=True)
    bad = tmp_path / "bad2.jsonl"
    lines = synthetic["windows"].read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0]); first["data_sha256"] = "0" * 64
    bad.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(FIT.FitError, match="해시"):
        FIT.crosscheck_with_windows_manifest(refs, bad)


def test_read_window_verifies_the_hash(synthetic):
    refs = FIT.refs_from_extract_manifest(synthetic["task_paths"][0], labelled=True)
    tampered = FIT.WindowRef(**{**refs[0].__dict__, "sha256": "1" * 64})
    with pytest.raises(FIT.FitError, match="해시"):
        FIT.read_window(tampered)
    assert FIT.read_window(refs[0]).shape == (N_SAMPLES, N_ROI)


def test_rest_manifest_refs_carry_no_label(synthetic):
    refs = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    assert refs and all(r.label is None for r in refs)


def test_labelled_manifest_rejects_rest(synthetic):
    with pytest.raises(FIT.FitError, match="분류 대상이 아닌"):
        FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=True)


# --------------------------------------------------------------------------- #
# fold 해석
# --------------------------------------------------------------------------- #


def test_inner_fold_resolves_to_validation(synthetic):
    f = FIT.resolve_fold_subjects(synthetic["folds"], 0, 0)
    assert f.role == FIT.ROLE_INNER and f.eval_role == "inner_validation"
    assert len(f.train) == 8 and len(f.evaluate) == 4
    assert not set(f.train) & set(f.evaluate)


def test_outer_fit_uses_the_reserved_inner_number(synthetic):
    f = FIT.resolve_fold_subjects(synthetic["folds"], 0, T.OUTER_FIT_INNER_FOLD)
    assert f.role == FIT.ROLE_OUTER and f.eval_role == "outer_test"
    assert len(f.train) == 12 and len(f.evaluate) == 4


def test_pilot_leaking_into_a_fold_is_rejected(synthetic):
    folds = json.loads(json.dumps(synthetic["folds"]))
    folds["outer_folds"][0]["train_subjects"].append(folds["pilot"]["subjects"][0])
    with pytest.raises(FIT.FitError, match="pilot"):
        FIT.resolve_fold_subjects(folds, 0, T.OUTER_FIT_INNER_FOLD)


def test_unknown_fold_numbers_fail(synthetic):
    with pytest.raises(FIT.FitError, match="outer fold"):
        FIT.resolve_fold_subjects(synthetic["folds"], 3, 0)
    with pytest.raises(FIT.FitError, match="inner fold"):
        FIT.resolve_fold_subjects(synthetic["folds"], 0, 2)


# --------------------------------------------------------------------------- #
# 변환·bank 경계 (T03 / T04)
# --------------------------------------------------------------------------- #


def test_transform_is_fit_only_on_training_subjects(synthetic):
    fold = FIT.resolve_fold_subjects(synthetic["folds"], 0, 0)
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    tr = FIT.fit_fold_transform(rest, fold.train, bank_seed=T.bank_seed(0, 0))
    assert set(tr.fit_subjects) == set(fold.train)
    assert not set(tr.fit_subjects) & set(fold.evaluate)
    assert tr.n_rest_windows == len(fold.train) * 4


def test_allowed_subjects_is_actually_passed_through(synthetic, monkeypatch):
    """T03 의 방어선은 인자다. 넘기지 않으면 경계가 사라진다."""
    seen = {}
    import mobse.v2.features as Fmod
    real = Fmod.fit_transform_on_training_rest

    def spy(rest_features, fit_subjects, **kw):
        seen.update(kw)
        seen["n_fit_subjects"] = len(set(fit_subjects))
        return real(rest_features, fit_subjects, **kw)

    monkeypatch.setattr(FIT.F, "fit_transform_on_training_rest", spy)
    fold = FIT.resolve_fold_subjects(synthetic["folds"], 0, 0)
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    FIT.fit_fold_transform(rest, fold.train, bank_seed=T.bank_seed(0, 0))
    assert set(seen["allowed_subjects"]) == set(fold.train)


def test_transform_fingerprint_is_stable_across_transforms(synthetic):
    """T04 — transform 호출이 상태를 바꾸지 않는다."""
    fold = FIT.resolve_fold_subjects(synthetic["folds"], 0, 0)
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    tr = FIT.fit_fold_transform(rest, fold.train, bank_seed=T.bank_seed(0, 0))
    before = tr.frozen.fingerprint()
    for _ in range(3):
        tr.frozen.transform(np.zeros((2, tr.frozen.n_features)))
    assert tr.frozen.fingerprint() == before


def test_bank_seed_is_fold_scoped(synthetic):
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    fold = FIT.resolve_fold_subjects(synthetic["folds"], 0, 0)
    a = FIT.fit_fold_transform(rest, fold.train, bank_seed=T.bank_seed(0, 0))
    b = FIT.fit_fold_transform(rest, fold.train, bank_seed=T.bank_seed(0, 1))
    assert a.brain.seed != b.brain.seed
    assert a.provenance()["bank_seed"] == 30000
    assert b.provenance()["bank_seed"] == 30001


def test_empty_training_rest_fails_rather_than_falling_back(synthetic):
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    with pytest.raises(FIT.FitError, match="training-rest"):
        FIT.fit_fold_transform(rest, ["ds002785:sub-9999"], bank_seed=T.bank_seed(0, 0))


# --------------------------------------------------------------------------- #
# 학습 루프
# --------------------------------------------------------------------------- #


def _sets(synthetic, outer=0, inner=0):
    fold = FIT.resolve_fold_subjects(synthetic["folds"], outer, inner)
    rest = FIT.refs_from_extract_manifest(synthetic["rest_path"], labelled=False)
    tr = FIT.fit_fold_transform(rest, fold.train, bank_seed=T.bank_seed(outer, min(inner, 9)))
    task_refs = []
    for tp in synthetic["task_paths"]:
        task_refs += FIT.refs_from_extract_manifest(tp, labelled=True)
    train_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.train), tr)
    eval_set = FIT.encode_windows(FIT.select_refs(task_refs, fold.evaluate), tr)
    return fold, tr, train_set, eval_set


def test_encoding_shapes_and_transposition(synthetic):
    _, tr, train_set, _ = _sets(synthetic)
    assert train_set.x.shape == (8 * 2 * 4, N_ROI, N_SAMPLES), train_set.x.shape
    assert train_set.pca.shape == (8 * 2 * 4, 10)
    assert set(np.unique(train_set.y)) <= {0, 1}
    # .npy 는 (n_samples, n_roi) 다. 모델은 (B, n_roi, T) 를 받는다.
    raw = FIT.read_window(train_set.refs[0])
    assert np.allclose(train_set.x[0], raw.T.astype(np.float32))


def test_run_probability_requires_four_windows():
    refs = [FIT.WindowRef(window_key=f"k{i}", run_key="ds002785/sub-0001/na/emomatching/na/seq",
                          canonical_subject="ds002785:sub-0001", task="emomatching",
                          path=Path("/x"), sha256="0" * 64, label=0) for i in range(3)]
    with pytest.raises(FIT.FitError, match="4개가 아니다"):
        FIT.run_probabilities(refs, [0.5, 0.5, 0.5])


def test_subject_run_true_probs_uses_the_task_as_truth():
    rp = {"ds002785/sub-0001/na/emomatching/na/seq": 0.2,
          "ds002785/sub-0001/na/workingmemory/na/seq": 0.9}
    out = FIT.subject_run_true_probs(rp)
    # emomatching = class 0 → 정답 확률은 1 - p1
    assert out["ds002785:sub-0001"] == pytest.approx([0.8, 0.9])


def test_inner_fit_runs_and_reports_a_valid_best_epoch(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    res, model = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                                model_seed=42, fold=fold, max_epochs=4)
    assert res.role == FIT.ROLE_INNER
    assert 1 <= res.best_epoch <= res.epochs_run <= 4
    assert len(res.val_losses) == res.epochs_run
    assert set(res.eval_window_probs) == {r.window_key for r in eval_set.refs}
    assert len(res.eval_run_probs) == len(fold.evaluate) * 2
    assert 0.0 <= res.eval_balanced_accuracy <= 1.0
    assert res.transform["bank_seed"] == 30000
    assert res.timing["train_seconds"] > 0


def test_outer_fit_refuses_early_stopping(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic, inner=T.OUTER_FIT_INNER_FOLD)
    with pytest.raises(FIT.FitError, match="early stopping"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0, model_seed=42,
                       fold=fold, early_stopping=True, epochs_exact=2)


def test_outer_fit_requires_an_exact_epoch_count(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic, inner=T.OUTER_FIT_INNER_FOLD)
    with pytest.raises(FIT.FitError, match="공통 E"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                       model_seed=42, fold=fold)


def test_outer_fit_runs_exactly_e_epochs_without_validation(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic, inner=T.OUTER_FIT_INNER_FOLD)
    res, _ = FIT.train_fold(train_set, eval_set, tr, cell="B", config_id=3,
                            model_seed=43, fold=fold, epochs_exact=3)
    assert res.role == FIT.ROLE_OUTER
    assert res.epochs_run == 3 and res.best_epoch == 3
    assert res.val_losses == [], "outer fit 은 평가 집합으로 loss 를 재지 않는다"


def test_bad_config_id_is_rejected(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    with pytest.raises(FIT.FitError, match="config_id"):
        FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=8,
                       model_seed=42, fold=fold, max_epochs=1)


def test_encoder_init_is_shared_across_cells_at_the_same_seed(synthetic):
    """계획서 §7 — 같은 seed 의 공통 encoder 초기화를 맞추고 RNG 차이를 기록한다."""
    fold, tr, train_set, eval_set = _sets(synthetic)
    hashes = {}
    for cell in ("A", "B", "C", "D"):
        res, _ = FIT.train_fold(train_set, eval_set, tr, cell=cell, config_id=0,
                                model_seed=42, fold=fold, max_epochs=1)
        hashes[cell] = res.encoder_init_hash
    assert len(set(hashes.values())) == 1, hashes
    assert "RNG" in res.rng_note


def test_a_and_c_differ_only_by_the_bank(synthetic):
    """A 는 brain bank, C 는 null bank 를 쓴다. 같은 seed·config 에서 예측이 달라야 한다."""
    fold, tr, train_set, eval_set = _sets(synthetic)
    a, _ = FIT.train_fold(train_set, eval_set, tr, cell="A", config_id=0,
                          model_seed=42, fold=fold, max_epochs=2)
    c, _ = FIT.train_fold(train_set, eval_set, tr, cell="C", config_id=0,
                          model_seed=42, fold=fold, max_epochs=2)
    assert a.encoder_init_hash == c.encoder_init_hash
    assert a.eval_window_probs != c.eval_window_probs


def test_fit_is_reproducible_at_the_same_seed(synthetic):
    fold, tr, train_set, eval_set = _sets(synthetic)
    kw = dict(cell="A", config_id=1, model_seed=42, fold=fold, max_epochs=2)
    a, _ = FIT.train_fold(train_set, eval_set, tr, **kw)
    b, _ = FIT.train_fold(train_set, eval_set, tr, **kw)
    assert a.eval_window_probs == b.eval_window_probs
    assert a.val_losses == b.val_losses
