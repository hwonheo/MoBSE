"""`mobse-v2 fit` 본체 — 지침서 WI-05/WI-06, 계획서 §4–§7."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mobse.v2 import templates as T
from mobse.v2.cli import CLIError, build_parser, resolve_paths, run_fit

N_ROI, N_SAMPLES = 100, 30
TASKS = ("emomatching", "workingmemory")
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def min_updates_spy(monkeypatch):
    """CLI 는 config 의 잠긴 최소 update(1,500)를 넘겨야 한다 (P8).

    합성 자료는 창이 적어 1,500 update 면 수백 epoch 이므로, 넘겨받은 값을 기록한
    뒤 실제 학습은 0 으로 돌린다. 값 전달은 ``test_cli_passes_locked_min_updates``
    가 확인한다.
    """
    from mobse.v2 import fitting as FIT

    seen = []
    real = FIT.train_fold

    def spy(*a, **kw):
        seen.append(kw.get("min_updates"))
        kw["min_updates"] = 0
        return real(*a, **kw)

    monkeypatch.setattr(FIT, "train_fold", spy)
    return seen


@pytest.fixture
def workspace(tmp_path):
    rng = np.random.default_rng(11)
    subs = [f"sub-{i:04d}" for i in range(1, 21)]
    canon = [f"ds002785:{s}" for s in subs]

    def win(sub, task, w):
        p = tmp_path / "deriv" / sub / f"{sub}_{task}_win-{w}.npy"
        p.parent.mkdir(parents=True, exist_ok=True)
        np.save(p, rng.standard_normal((N_SAMPLES, N_ROI)))
        return {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "shape": [N_SAMPLES, N_ROI], "start_sec": 12.0 + 60 * w,
                "source_frame_range": [w, w + N_SAMPLES]}

    def dump(name, tasks):
        p = tmp_path / name
        with p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"record_type": "header"}) + "\n")
            for sub in subs:
                for task in tasks:
                    fh.write(json.dumps({
                        "record_type": "run",
                        "run_key": f"ds002785/{sub}/na/{task}/na/seq",
                        "canonical_subject": f"ds002785:{sub}", "status": "ok",
                        "windows": [win(sub, task, w) for w in range(4)]}) + "\n")
        return p

    task_paths = [dump(f"wi02_{t}.jsonl", [t]) for t in TASKS]
    rest_path = dump("wi02_rest.jsonl", ["restingstate"])

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
        "split_hash": "d" * 64,
        "pilot": {"subjects": canon[:4]},
        "main_pool": {"subjects": canon[4:]},
        "outer_folds": [{"outer_fold": 0, "test_subjects": canon[4:8],
                         "train_subjects": canon[8:],
                         "inner": [{"inner_fold": 0, "val_subjects": canon[8:12],
                                    "train_subjects": canon[12:]}]}],
    }), encoding="utf-8")

    return {"tmp": tmp_path, "task_paths": task_paths, "rest": rest_path,
            "windows": win_path, "subjects": subj_path, "folds": folds_path}


def _args(ws, out, **over):
    argv = ["fit",
            "--config", str(REPO / "configs/redesign_v1/main.yaml"),
            "--splits", str(ws["folds"]), "--subjects", str(ws["subjects"]),
            "--windows", str(ws["windows"]), "--rest-manifest", str(ws["rest"]),
            "--output-dir", str(out),
            "--cell", over.get("cell", "A"),
            "--outer-fold", str(over.get("outer", 0)),
            "--inner-fold", str(over.get("inner", 0)),
            "--model-seed", str(over.get("seed", 42)),
            "--config-id", str(over.get("config_id", 0)),
            "--epochs", str(over.get("epochs", 2)),
            "--task-manifests"] + [str(p) for p in ws["task_paths"]]
    ns = build_parser().parse_args(argv)
    return ns


def test_required_paths_include_the_new_inputs():
    from mobse.v2.cli import REQUIRED_PATHS
    assert {"config", "splits", "subjects", "windows", "rest_manifest",
            "output_dir"} == set(REQUIRED_PATHS["fit"])


def test_inner_fit_writes_all_four_artifacts(workspace):
    out = workspace["tmp"] / "fit0"
    ns = _args(workspace, out)
    res = run_fit(resolve_paths("fit", ns), ns)
    assert res["verdict"] == "pass"
    assert res["role"] == "inner" and res["eval_role"] == "inner_validation"
    assert res["bank_seed"] == T.bank_seed(0, 0)
    for name in ("fit_manifest.json", "checkpoint.pt",
                 "window_predictions.jsonl", "fit_report.json"):
        assert (out / name).is_file(), name
    rows = [json.loads(l) for l in (out / "window_predictions.jsonl").read_text().splitlines()]
    assert len(rows) == 4 * 2 * 4          # val subject 4명 × 2 task × 4 창
    assert {r["scope"] for r in rows} == {"inner_validation"}
    assert all(0.0 <= r["p_class1"] <= 1.0 for r in rows)
    assert len({r["fit_id"] for r in rows}) == 1


def test_fit_manifest_records_the_boundary(workspace):
    out = workspace["tmp"] / "fit1"
    ns = _args(workspace, out)
    run_fit(resolve_paths("fit", ns), ns)
    man = json.loads((out / "fit_manifest.json").read_text())
    assert man["role"] == "inner"
    assert man["folds"]["n_train_subjects"] == 8
    assert man["folds"]["n_eval_subjects"] == 4
    assert len(man["fit_subjects"]) == 8
    assert man["split_hash"] == "d" * 64
    assert man["bank_seed"] == 30000 and man["null_seed"] == 1729
    assert len(man["code_hash"]) == 64 and len(man["env_hash"]) == 64


def test_outer_fit_runs_exact_epochs(workspace):
    out = workspace["tmp"] / "fit2"
    ns = _args(workspace, out, inner=T.OUTER_FIT_INNER_FOLD, epochs=2)
    res = run_fit(resolve_paths("fit", ns), ns)
    assert res["role"] == "outer" and res["eval_role"] == "outer_test"
    assert res["epochs_run"] == 2 and res["best_epoch"] == 2
    rep = json.loads((out / "fit_report.json").read_text())
    assert rep["val_losses"] == []


def test_existing_outputs_are_not_overwritten(workspace):
    out = workspace["tmp"] / "fit3"
    ns = _args(workspace, out)
    run_fit(resolve_paths("fit", ns), ns)
    with pytest.raises(CLIError, match="덮어쓰지 않는다"):
        run_fit(resolve_paths("fit", ns), ns)


def test_missing_task_manifest_fails_without_searching(workspace):
    out = workspace["tmp"] / "fit4"
    ns = _args(workspace, out)
    ns.task_manifests = [workspace["tmp"] / "nope.jsonl"]
    with pytest.raises(CLIError, match="U20"):
        run_fit(resolve_paths("fit", ns), ns)


def test_subject_missing_from_subjects_manifest_fails(workspace):
    out = workspace["tmp"] / "fit5"
    ns = _args(workspace, out)
    trimmed = workspace["tmp"] / "short_subjects.jsonl"
    lines = workspace["subjects"].read_text().splitlines()
    trimmed.write_text("\n".join(lines[:5]) + "\n", encoding="utf-8")
    paths = resolve_paths("fit", ns)
    paths["subjects"] = str(trimmed)
    with pytest.raises(CLIError, match="subjects.jsonl 에 없는"):
        run_fit(paths, ns)


def test_config_id_is_recorded_and_used(workspace):
    out = workspace["tmp"] / "fit6"
    ns = _args(workspace, out, config_id=5)
    run_fit(resolve_paths("fit", ns), ns)
    rep = json.loads((out / "fit_report.json").read_text())
    assert rep["config_id"] == 5
    assert rep["config"]["learning_rate"] == 0.0003
    assert rep["config"]["dropout"] == 0.1
    assert rep["config"]["weight_decay"] == 0.001


def test_cli_passes_locked_min_updates(workspace, min_updates_spy):
    out = workspace["tmp"] / "fit7"
    ns = _args(workspace, out)
    run_fit(resolve_paths("fit", ns), ns)
    assert min_updates_spy == [5000]
    rep = json.loads((out / "fit_report.json").read_text())
    assert rep["min_updates"] == 5000
    assert rep["updates_run"] == rep["updates_per_epoch"] * rep["epochs_run"]


def test_fit_report_records_applied_determinism(workspace):
    """E22 — 결정성 설정이 적용된 상태를 fit_report 에 남긴다."""
    out = workspace["tmp"] / "fit8"
    ns = _args(workspace, out)
    run_fit(resolve_paths("fit", ns), ns)
    rep = json.loads((out / "fit_report.json").read_text())
    det = rep["determinism"]
    assert det["use_deterministic_algorithms"] is True
    assert det["cudnn_deterministic"] is True and det["cudnn_benchmark"] is False
    assert det["cublas_workspace_config"] in (":4096:8", ":16:8")


@pytest.mark.parametrize("seed", [0, 41, 45])
def test_model_seed_outside_locked_set_is_rejected(workspace, seed):
    """잠긴 ``train.model_seeds`` (계획서 §5 seed 42–44) 밖의 seed 는 fit 전에 거부한다.

    rev38 이전에는 이 키가 잠금 검사만 받고 어디서도 소비되지 않았다.
    """
    out = workspace["tmp"] / f"fit_seed{seed}"
    ns = _args(workspace, out, seed=seed)
    with pytest.raises(CLIError, match="train.model_seeds"):
        run_fit(resolve_paths("fit", ns), ns)
    assert not out.exists() or not any(out.iterdir())


# --------------------------------------------------------------------------- #
# 결정 14 4단계 — §6 구조 비교(NG·SG)를 같은 `fit` 으로 학습
# --------------------------------------------------------------------------- #

def test_fit_cell_choices_are_cells_then_comparators():
    from mobse.v2.baselines import COMPARATOR_ORDER
    from mobse.v2.cli import FIT_CELL_CHOICES
    from mobse.v2.train import CELLS
    assert FIT_CELL_CHOICES == tuple(CELLS) + tuple(COMPARATOR_ORDER)
    with pytest.raises(SystemExit):
        build_parser().parse_args(["fit", "--cell", "E"])


@pytest.mark.parametrize("cell", ["NG", "SG"])
def test_comparator_inner_fit_writes_all_four_artifacts(workspace, cell):
    out = workspace["tmp"] / f"fit_{cell}"
    ns = _args(workspace, out, cell=cell)
    res = run_fit(resolve_paths("fit", ns), ns)
    assert res["verdict"] == "pass" and res["cell"] == cell
    for name in ("fit_manifest.json", "checkpoint.pt",
                 "window_predictions.jsonl", "fit_report.json"):
        assert (out / name).is_file(), name
    man = json.loads((out / "fit_manifest.json").read_text())
    assert man["cell"] == cell and man["fit_id"].startswith(f"inner-{cell}-o0i0s42-")
    rows = [json.loads(l) for l in (out / "window_predictions.jsonl").read_text().splitlines()]
    assert len(rows) == 4 * 2 * 4 and {r["cell"] for r in rows} == {cell}
    rep = json.loads((out / "fit_report.json").read_text())
    assert rep["config_id"] == 0 and rep["min_updates"] == 5000


def test_only_sg_fit_records_its_training_rest_graph(workspace):
    """SG 만 fold 의 training-rest single graph 를 만들고 그 출처를 manifest·report 에 남긴다."""
    got = {}
    for cell in ("A", "NG", "SG"):
        out = workspace["tmp"] / f"fit_graph_{cell}"
        ns = _args(workspace, out, cell=cell)
        run_fit(resolve_paths("fit", ns), ns)
        got[cell] = (json.loads((out / "fit_manifest.json").read_text()),
                     json.loads((out / "fit_report.json").read_text()))
    for cell in ("A", "NG"):
        man, rep = got[cell]
        assert "single_graph_id" not in man and "single_graph_id" not in rep["transform"]
    man, rep = got["SG"]
    assert man["single_graph_id"] == rep["transform"]["single_graph_id"]
    assert man["single_graph_fingerprint"] == rep["transform"]["single_graph_fingerprint"]
    # bank 는 셋 모두 같은 fold 변환에서 나온다 (구조 비교가 다른 bank 를 쓰지 않음).
    assert len({got[c][0]["bank_id"] for c in got}) == 1


@pytest.mark.parametrize("cell", ["NG", "SG"])
def test_comparator_outer_fit_runs_exact_epochs(workspace, cell):
    out = workspace["tmp"] / f"fit_outer_{cell}"
    ns = _args(workspace, out, cell=cell, inner=T.OUTER_FIT_INNER_FOLD, epochs=2)
    res = run_fit(resolve_paths("fit", ns), ns)
    assert res["role"] == "outer" and res["eval_role"] == "outer_test"
    assert res["epochs_run"] == 2 and res["best_epoch"] == 2


@pytest.mark.parametrize("seed", [0, 45])
def test_comparator_seed_outside_locked_set_is_rejected(workspace, seed):
    out = workspace["tmp"] / f"fit_ng_seed{seed}"
    ns = _args(workspace, out, cell="NG", seed=seed)
    with pytest.raises(CLIError, match="train.model_seeds"):
        run_fit(resolve_paths("fit", ns), ns)


def test_evaluate_grid_rejects_comparator_fits():
    """구조 비교 fit 을 2×2 evaluate 에 섞으면 알 수 없는 칸으로 거부한다."""
    from mobse.v2.cli import _check_fit_grid
    from mobse.v2.train import CELLS, MODEL_SEEDS
    folds = {"outer_folds": [{"outer_fold": 0}]}
    fits = {f"{c}{s}": {"slot": (c, 0, s)} for c in CELLS for s in MODEL_SEEDS}
    assert _check_fit_grid(fits, folds)["n_fits"] == 12
    fits["NG42"] = {"slot": ("NG", 0, 42)}
    with pytest.raises(CLIError, match="알 수 없는 칸"):
        _check_fit_grid(fits, folds)


@pytest.mark.parametrize("cell", ["NG", "SG"])
def test_written_window_predictions_reproduce_inner_eval_loss(workspace, cell):
    """select-comparator 는 창 예측 → run 확률을 다시 계산해 fit_report 와 대조한다.

    실제 `run_fit` 산출물(float32 forward → float 기록)이 그 허용 차이 안에 드는지
    확인한다 (결정 14 4b). fit_id 는 config_id 로 구별된다 (rev42).
    """
    from pathlib import Path as _P

    from mobse.v2 import baselines as BL
    from mobse.v2 import fitting as FIT
    from mobse.v2.cli import SELECTION_LOSS_TOL

    ids = []
    for cid in (0, 1):
        out = workspace["tmp"] / f"fit_loss_{cell}_{cid}"
        ns = _args(workspace, out, cell=cell, config_id=cid)
        run_fit(resolve_paths("fit", ns), ns)
        rep = json.loads((out / "fit_report.json").read_text())
        rows = [json.loads(l) for l in (out / "window_predictions.jsonl").read_text().splitlines()]
        refs = [FIT.WindowRef(window_key=r["window_key"], run_key=r["run_key"],
                              canonical_subject=r["canonical_subject"],
                              task=FIT.task_of(r["run_key"]), path=_P(""), sha256="",
                              label=r["truth"]) for r in rows]
        loss = BL.inner_loss(FIT.run_probabilities(refs, [r["p_class1"] for r in rows]))
        assert abs(loss - rep["eval_loss"]) <= SELECTION_LOSS_TOL
        ids.append(rep["fit_id"])
    assert ids[0] != ids[1]


@pytest.mark.parametrize("cell", ["A", "D"])
def test_ad_window_predictions_reproduce_inner_loss_and_ba(workspace, cell):
    """select-ad 는 창 예측으로 inner 손실·BA 를 다시 계산해 fit_report 와 대조한다.

    실제 A–D `run_fit` 산출물이 그 허용 차이 안에 드는지 확인한다 (WI-07 select-ad).
    """
    from pathlib import Path as _P

    from mobse.v2 import fitting as FIT
    from mobse.v2 import train as TR
    from mobse.v2.cli import SELECTION_LOSS_TOL

    out = workspace["tmp"] / f"fit_ad_{cell}"
    ns = _args(workspace, out, cell=cell, config_id=2)
    run_fit(resolve_paths("fit", ns), ns)
    rep = json.loads((out / "fit_report.json").read_text())
    rows = [json.loads(l) for l in (out / "window_predictions.jsonl").read_text().splitlines()]
    refs = [FIT.WindowRef(window_key=r["window_key"], run_key=r["run_key"],
                          canonical_subject=r["canonical_subject"],
                          task=FIT.task_of(r["run_key"]), path=_P(""), sha256="",
                          label=r["truth"]) for r in rows]
    rp = FIT.run_probabilities(refs, [r["p_class1"] for r in rows])
    loss = TR.subject_equal_loss(FIT.subject_run_true_probs(rp))
    assert abs(loss - rep["eval_loss"]) <= SELECTION_LOSS_TOL
    assert abs(FIT._balanced_accuracy_from_runs(rp) - rep["eval_balanced_accuracy"]) \
        <= SELECTION_LOSS_TOL
