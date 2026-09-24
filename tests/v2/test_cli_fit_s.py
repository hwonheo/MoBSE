"""`mobse-v2 fit-s` — §6 S 후보 한 칸 fit (결정 14 4c-i). 합성 자료만."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mobse.v2 import baselines as BL
from mobse.v2 import fitting as FIT
from mobse.v2 import manifests as M
from mobse.v2.cli import (REQUIRED_PATHS, S_CANDIDATE_CHOICES, SUBCOMMANDS, CLIError,
                          build_parser, resolve_paths, run_fit_s)

N_ROI, N_SAMPLES = 12, 30
TASKS = ("emomatching", "workingmemory")
REPO = Path(__file__).resolve().parents[2]
S1, S2, S3, S4 = BL.CANDIDATE_ORDER


@pytest.fixture(autouse=True)
def min_updates_spy(monkeypatch):
    """CLI 는 config 의 잠긴 최소 update 를 MLP 에 넘겨야 한다 (P8). 실제 학습은 0."""
    seen = []
    real = BL.fit_mlp

    def spy(*a, **kw):
        seen.append(kw.get("min_updates"))
        kw["min_updates"] = 0
        return real(*a, **kw)

    monkeypatch.setattr(BL, "fit_mlp", spy)
    return seen


@pytest.fixture
def ws(tmp_path):
    rng = np.random.default_rng(23)
    subs = [f"sub-{i:04d}" for i in range(1, 21)]
    canon = [f"ds002785:{s}" for s in subs]

    def win(sub, task, w):
        p = tmp_path / "deriv" / sub / f"{sub}_{task}_win-{w}.npy"
        p.parent.mkdir(parents=True, exist_ok=True)
        base = rng.standard_normal((N_SAMPLES, N_ROI))
        if task == "workingmemory":
            base[:, :3] += 0.8                   # 분리 가능한 신호 (mean feature)
        np.save(p, base)
        return {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "shape": [N_SAMPLES, N_ROI], "start_sec": 12.0 + 60 * w,
                "source_frame_range": [w, w + N_SAMPLES]}

    def dump(name, task):
        p = tmp_path / name
        with p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"record_type": "header"}) + "\n")
            for sub in subs:
                fh.write(json.dumps({
                    "record_type": "run", "run_key": f"ds002785/{sub}/na/{task}/na/seq",
                    "canonical_subject": f"ds002785:{sub}", "status": "ok",
                    "windows": [win(sub, task, w) for w in range(4)]}) + "\n")
        return p

    task_paths = [dump(f"wi02_{t}.jsonl", t) for t in TASKS]
    win_path = tmp_path / "windows.jsonl"
    with win_path.open("w", encoding="utf-8") as fh:
        for tp in task_paths:
            for line in tp.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("record_type") != "run":
                    continue
                task = rec["run_key"].split("/")[3]
                for i, w in enumerate(rec["windows"]):
                    fh.write(json.dumps({
                        "schema_version": "wi02-windows-0.1",
                        "window_key": f"{rec['run_key']}#win-{i}",
                        "run_key": rec["run_key"], "data_sha256": w["sha256"],
                        "observed_label": task, "label_source": "task_metadata",
                        "n_roi": N_ROI, "n_samples": N_SAMPLES,
                        "start_sec": w["start_sec"], "end_sec": w["start_sec"] + 60,
                        "source_frame_range": w["source_frame_range"],
                        "target_grid": 2.0, "qc_flags": []}) + "\n")
    subj_path = tmp_path / "subjects.jsonl"
    subj_path.write_text("".join(
        json.dumps({"schema_version": "wi03-subjects-0.1", "canonical_subject": c,
                    "group_id": c, "cohort": "ds002785", "eligible": True,
                    "assignment": "main", "assignment_reason": "ok"}) + "\n"
        for c in canon), encoding="utf-8")
    folds_path = tmp_path / "folds.json"
    folds_path.write_text(json.dumps({
        "split_hash": "d" * 64, "pilot": {"subjects": canon[:4]},
        "main_pool": {"subjects": canon[4:]},
        "outer_folds": [{"outer_fold": 0, "test_subjects": canon[4:8],
                         "train_subjects": canon[8:],
                         "inner": [{"inner_fold": 0, "val_subjects": canon[8:12],
                                    "train_subjects": canon[12:]}]}],
    }), encoding="utf-8")
    return {"tmp": tmp_path, "task_paths": task_paths, "windows": win_path,
            "subjects": subj_path, "folds": folds_path}


def _ns(ws, out, *, cand=S1, setting="C=1", inner=0, seed=None, epochs=None):
    argv = ["fit-s", "--config", str(REPO / "configs/redesign_v1/main.yaml"),
            "--splits", str(ws["folds"]), "--subjects", str(ws["subjects"]),
            "--windows", str(ws["windows"]), "--output-dir", str(out),
            "--candidate", cand, "--setting-id", setting, "--outer-fold", "0",
            "--inner-fold", str(inner)]
    if seed is not None:
        argv += ["--model-seed", str(seed)]
    if epochs is not None:
        argv += ["--epochs", str(epochs)]
    argv += ["--task-manifests"] + [str(p) for p in ws["task_paths"]]
    return build_parser().parse_args(argv)


def _run(ws, name, **kw):
    ns = _ns(ws, ws["tmp"] / name, **kw)
    return run_fit_s(resolve_paths("fit-s", ns), ns), ws["tmp"] / name


def _xy(ws, subjects, kind):
    refs = []
    for mp in ws["task_paths"]:
        refs += FIT.refs_from_extract_manifest(mp, labelled=True)
    sel = FIT.select_refs(refs, subjects)
    return (BL.feature_matrix([FIT.read_window(r) for r in sel], kind),
            [int(r.label) for r in sel], sel)


def _fold(ws, inner):
    return FIT.resolve_fold_subjects(json.loads(ws["folds"].read_text()), 0, inner)


# ---------------------------------------------------------------- 등록·이름 --


def test_registered_with_required_paths_and_no_rest_manifest():
    assert "fit-s" in SUBCOMMANDS
    assert set(REQUIRED_PATHS["fit-s"]) == {"config", "splits", "subjects", "windows",
                                            "output_dir"}


def test_candidate_names_agree_in_three_places():
    assert S_CANDIDATE_CHOICES == BL.CANDIDATE_ORDER == M.S_CANDIDATES


def test_s_settings_match_grid_strings():
    assert list(BL.s_settings(S1)) == [s for c, s, _ in BL.logistic_settings() if c == S1]
    assert list(BL.s_settings(S4)) == [f"config={i}" for i in range(8)]
    assert BL.s_settings(S2)["config=3"] == (3, 3)
    assert BL.s_settings(S3)["C=0.1"] == (2, 0.1)
    with pytest.raises(BL.BaselineError):
        BL.s_settings("A")


# ---------------------------------------------------------------- logistic --


def test_logistic_inner_writes_three_artifacts_and_matches_library(ws):
    res, out = _run(ws, "s1")
    assert res["verdict"] == "pass" and res["role"] == "inner"
    assert res["model_seed"] is None and res["best_epoch"] is None
    for name in ("s_fit_report.json", "s_window_predictions.jsonl", "s_model.npz"):
        assert (out / name).is_file()
    fold = _fold(ws, 0)
    Xt, yt, _ = _xy(ws, fold.train, BL.FEATURE_ROI_MEAN_VAR)
    Xe, _, erefs = _xy(ws, fold.evaluate, BL.FEATURE_ROI_MEAN_VAR)
    lib = BL.fit_s(Xt, yt, Xe, [r.run_key for r in erefs], candidate=S1,
                   setting_id="C=1", role="inner")
    rows = M.read_jsonl(out / "s_window_predictions.jsonl", "s_window_predictions")
    assert len(rows) == len(fold.evaluate) * 2 * 4
    got = {r["window_key"]: r["p_class1"] for r in rows}
    for r, p in zip(erefs, lib.eval_window_p1):
        assert got[r.window_key] == pytest.approx(float(p), abs=1e-12)
    rep = json.loads((out / "s_fit_report.json").read_text())
    assert rep["eval_loss"] == pytest.approx(lib.eval_loss, abs=1e-12)
    assert rep["converged"] is True and rep["fit"]["kind"] == "logistic"


def test_separable_signal_is_learned_in_the_right_direction(ws):
    """합성 자료는 workingmemory 창의 ROI 0–2 평균을 올렸다 — 확률 방향이 맞아야 한다."""
    _, out = _run(ws, "sep", setting="C=1")
    rep = json.loads((out / "s_fit_report.json").read_text())
    assert rep["eval_balanced_accuracy"] >= 0.75
    rows = M.read_jsonl(out / "s_window_predictions.jsonl", "s_window_predictions")
    hi = np.mean([r["p_class1"] for r in rows if r["truth"] == 1])
    lo = np.mean([r["p_class1"] for r in rows if r["truth"] == 0])
    assert hi > lo


def test_recomputed_loss_from_rows_equals_report(ws):
    _, out = _run(ws, "s3", cand=S3, setting="C=0.1")
    rows = M.read_jsonl(out / "s_window_predictions.jsonl", "s_window_predictions")
    refs = [FIT.WindowRef(window_key=r["window_key"], run_key=r["run_key"],
                          canonical_subject=r["canonical_subject"],
                          task=FIT.task_of(r["run_key"]), path=Path(""), sha256="",
                          label=int(r["truth"])) for r in rows]
    loss = BL.inner_loss(FIT.run_probabilities(refs, [r["p_class1"] for r in rows]))
    rep = json.loads((out / "s_fit_report.json").read_text())
    assert abs(loss - rep["eval_loss"]) <= 1e-9
    assert rep["n_features"] == N_ROI * (N_ROI - 1) // 2


def test_scaler_is_fit_on_training_windows_only(ws):
    _, out = _run(ws, "s1sc")
    fold = _fold(ws, 0)
    Xt, _, _ = _xy(ws, fold.train, BL.FEATURE_ROI_MEAN_VAR)
    Xall, _, _ = _xy(ws, list(fold.train) + list(fold.evaluate), BL.FEATURE_ROI_MEAN_VAR)
    with np.load(out / "s_model.npz") as z:
        mean = z["scaler_mean"]
    assert np.allclose(mean, Xt.mean(axis=0))
    assert not np.allclose(mean, Xall.mean(axis=0))


def test_logistic_refuses_seed_and_epochs(ws):
    with pytest.raises(CLIError, match="logistic"):
        _run(ws, "x1", seed=42)
    with pytest.raises(CLIError, match="logistic"):
        _run(ws, "x2", epochs=3)


def test_setting_outside_grid_is_refused(ws):
    for cand, setting in ((S1, "C=5"), (S1, "config=0"), (S2, "config=8"), (S2, "C=1")):
        with pytest.raises(CLIError, match="grid 밖"):
            _run(ws, f"bad_{cand[:2]}_{setting}", cand=cand, setting=setting,
                 seed=None if cand in BL.LOGISTIC_CANDIDATES else 42)


def test_outputs_are_not_overwritten(ws):
    _run(ws, "dup")
    with pytest.raises(CLIError, match="덮어쓰지"):
        _run(ws, "dup")


def test_tampered_window_is_refused(ws):
    fold = _fold(ws, 0)
    _, _, refs = _xy(ws, fold.train, BL.FEATURE_ROI_MEAN_VAR)
    np.save(refs[0].path, np.zeros((N_SAMPLES, N_ROI)))
    with pytest.raises(CLIError, match="해시"):
        _run(ws, "tamper")


# ---------------------------------------------------------------- MLP --


def test_mlp_inner_requires_locked_seed_and_no_epochs(ws):
    with pytest.raises(CLIError, match="model-seed"):
        _run(ws, "m0", cand=S2, setting="config=0")
    with pytest.raises(CLIError, match="train.model_seeds"):
        _run(ws, "m1", cand=S2, setting="config=0", seed=7)
    with pytest.raises(CLIError, match="early stopping"):
        _run(ws, "m2", cand=S2, setting="config=0", seed=42, epochs=3)


def test_mlp_inner_runs_and_passes_locked_min_updates(ws, min_updates_spy):
    res, out = _run(ws, "m3", cand=S2, setting="config=1", seed=42)
    assert min_updates_spy == [1500]
    rep = json.loads((out / "s_fit_report.json").read_text())
    assert rep["model_seed"] == 42 and rep["fit"]["kind"] == "mlp"
    assert rep["best_epoch"] == rep["fit"]["best_epoch"] >= 1
    with np.load(out / "s_model.npz") as z:
        assert any(k.startswith("state.") for k in z.files)


def test_mlp_outer_requires_epochs_and_trains_exactly(ws):
    with pytest.raises(CLIError, match="--epochs"):
        _run(ws, "o0", cand=S4, setting="config=0", seed=43, inner=9)
    res, out = _run(ws, "o1", cand=S4, setting="config=0", seed=43, inner=9, epochs=3)
    rep = json.loads((out / "s_fit_report.json").read_text())
    assert rep["role"] == "outer" and rep["eval_role"] == "outer_test"
    assert rep["fit"]["epochs_run"] == 3 and rep["best_epoch"] == 3
    assert rep["folds"]["n_eval_subjects"] == 4
    rows = M.read_jsonl(out / "s_window_predictions.jsonl", "s_window_predictions")
    assert {r["scope"] for r in rows} == {"outer_test"}


# ---------------------------------------------------------------- 식별자·경계 --


def test_s_fit_id_separates_settings_seeds_and_candidates():
    base = dict(role="inner", outer_fold=0, inner_fold=0, split_hash="d" * 64,
                config_hash="e" * 64)
    ids = {M.s_fit_id(candidate=S1, setting_id=f"C={c:g}", model_seed=None, **base)
           for c in BL.LOGISTIC_CS}
    ids |= {M.s_fit_id(candidate=S2, setting_id="config=0", model_seed=s, **base)
            for s in (42, 43, 44)}
    ids.add(M.s_fit_id(candidate=S3, setting_id="C=1", model_seed=None, **base))
    assert len(ids) == 8 + 3 + 1
    with pytest.raises(M.ManifestError):
        M.s_fit_id(candidate="A", setting_id="C=1", model_seed=None, **base)


def test_s_rows_cannot_enter_window_predictions_or_evaluate(ws):
    _, out = _run(ws, "leak")
    row = M.read_jsonl(out / "s_window_predictions.jsonl")[0]
    with pytest.raises(M.ManifestError):
        M.validate_record("window_predictions", row)


def test_s_window_predictions_schema_checks_hash_and_key():
    rec = {"schema_version": "x", "canonical_subject": "ds002785:sub-0001",
           "group_id": "g", "run_key": "ds002785/sub-0001/na/emomatching/na/seq",
           "window_key": "k", "truth": 0, "p_class1": 0.5, "candidate": S1,
           "setting_id": "C=1", "scope": "inner_validation", "model_sha256": "0" * 64,
           "s_fit_id": "s"}
    M.validate_record("s_window_predictions", rec)
    with pytest.raises(M.ManifestError):
        M.validate_record("s_window_predictions", {**rec, "model_sha256": "nothex"})
    assert M._primary_key_fields("s_window_predictions") == (
        "candidate", "setting_id", "window_key")
