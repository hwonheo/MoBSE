"""evaluate 하위 명령 본체 (WI-06, 계획서 §8) — 합성 release 로 끝까지 돈다.

실자료 fit 은 없다. 잠긴 main pool 을 소비하지 않고, cell × outer fold × seed
격자를 합성해 집계·무결성 규칙만 확인한다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from mobse.v2 import cli
from mobse.v2.config import config_hash, load_config
from mobse.v2.evaluate import CELLS, CLASSIFICATION_TASKS

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "redesign_v1" / "main.yaml"
SEEDS = (42, 43, 44)
SPLIT_HASH = "d" * 64

pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _canon(i: int) -> str:
    return f"ds002785:sub-{i:04d}"


def _run_key(subject: str, task: str) -> str:
    return f"ds002785/{subject.split(':')[1]}/na/{task}/na/seq"


def _prob(cell: str, subject: str, task: str, window: int, seed: int) -> float:
    """정답 class 에 가깝지만 cell·subject 마다 다른 확률. B 는 짝수 subject 의 WM 을 틀린다."""
    truth = CLASSIFICATION_TASKS.index(task)
    idx = int(subject[-4:])
    wrong = cell == "B" and task == "workingmemory" and idx % 2 == 0
    base = 0.8 if (truth == 1) != wrong else 0.2
    return round(base + 0.01 * (window - 1.5) + 0.005 * (seed - 43), 6)


@pytest.fixture()
def release(tmp_path):
    """outer fold 2개 × cell 4 × seed 3 = 24 fit 의 합성 release."""
    subjects = [_canon(i) for i in range(1, 13)]
    pilot, pool = subjects[:2], subjects[2:]
    outer = [{"outer_fold": 0, "test_subjects": pool[:5], "train_subjects": pool[5:],
              "inner": []},
             {"outer_fold": 1, "test_subjects": pool[5:], "train_subjects": pool[:5],
              "inner": []}]
    folds_path = tmp_path / "folds.json"
    folds_path.write_text(json.dumps({"split_hash": SPLIT_HASH,
                                      "pilot": {"subjects": pilot},
                                      "main_pool": {"subjects": pool},
                                      "outer_folds": outer}), encoding="utf-8")
    cfg_hash = config_hash(load_config(CONFIG))

    manifests, predictions = [], []
    for cell in CELLS:
        for fold in outer:
            for seed in SEEDS:
                d = tmp_path / "fits" / f"{cell}_o{fold['outer_fold']}_s{seed}"
                d.mkdir(parents=True)
                ckpt = d / "checkpoint.pt"
                ckpt.write_bytes(f"{cell}{fold['outer_fold']}{seed}".encode())
                sha = hashlib.sha256(ckpt.read_bytes()).hexdigest()
                fid = f"outer-{cell}-o{fold['outer_fold']}i9s{seed}-{sha[:12]}"
                man = {"schema_version": "wi05-fit-manifest-0.1", "fit_id": fid,
                       "parent_release": "synthetic", "role": "outer", "cell": cell,
                       "folds": {"outer_fold": fold["outer_fold"], "inner_fold": 9,
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
                                "p_class1": _prob(cell, s, t, w, seed), "cell": cell,
                                "model_seed": seed, "scope": "outer_test",
                                "checkpoint_sha256": sha, "fit_id": fid})
                (d / "window_predictions.jsonl").write_text(
                    "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
                manifests.append(d / "fit_manifest.json")
                predictions.append(d / "window_predictions.jsonl")
    return {"tmp": tmp_path, "folds": folds_path, "manifests": manifests,
            "predictions": predictions, "pool": pool}


def _argv(rel, out, *, tasks=CLASSIFICATION_TASKS, manifests=None, predictions=None):
    return (["evaluate", "--config", str(CONFIG), "--splits", str(rel["folds"]),
             "--predictions"] + [str(p) for p in (predictions or rel["predictions"])] +
            ["--fit-manifest"] + [str(p) for p in (manifests or rel["manifests"])] +
            ["--output-dir", str(out), "--tasks"] + list(tasks))


def _rewrite(path: Path, fn) -> None:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
    rows = fn(rows)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_evaluate_aggregates_full_grid_hand_checked(release, capsys):
    out = release["tmp"] / "eval"
    assert cli.main(_argv(release, out)) == 0
    summary = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    n = len(release["pool"])
    assert summary["counts"] == {"window_rows": n * 2 * 4 * 3 * 4,
                                 "run_rows": n * 2 * 4, "subjects": n}
    assert summary["fit_grid"] == {"outer_folds": [0, 1], "seeds": list(SEEDS),
                                   "n_fits": 24}
    # A·C·D 는 전부 맞고, B 는 짝수 subject 의 WM 만 틀린다 -> b = 0.5
    n_even = sum(1 for s in release["pool"] if int(s[-4:]) % 2 == 0)
    assert summary["balanced_accuracy"]["A"] == pytest.approx(1.0)
    assert summary["balanced_accuracy"]["B"] == pytest.approx(1 - 0.5 * n_even / n)
    assert summary["mean_differences"]["H1_A_minus_B"] == pytest.approx(0.5 * n_even / n)
    assert summary["mean_differences"]["H2_A_minus_C"] == pytest.approx(0.0)
    runs = [json.loads(x) for x in
            (out / "run_predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(runs) == n * 2 * 4
    one = next(r for r in runs if r["cell"] == "A" and
               r["run_key"] == _run_key(release["pool"][0], "workingmemory"))
    # seed 평균 뒤 window 평균: 0.8 + 0.01*mean(w-1.5) + 0.005*mean(s-43) = 0.8
    assert one["ensemble_p"] == pytest.approx(0.8) and one["prediction"] == 1
    assert '"verdict": "pass"' in capsys.readouterr().out


def test_evaluate_refuses_to_overwrite(release):
    out = release["tmp"] / "eval"
    assert cli.main(_argv(release, out)) == 0
    with pytest.raises(cli.CLIError, match="덮어쓰지 않는다"):
        cli.main(_argv(release, out))


def test_evaluate_requires_both_tasks(release):
    with pytest.raises(cli.CLIError, match="두 task"):
        cli.main(_argv(release, release["tmp"] / "e", tasks=["emomatching"]))


def test_evaluate_rejects_untrained_task(release):
    with pytest.raises(cli.CLIError, match="학습하지 않은 task"):
        cli.main(_argv(release, release["tmp"] / "e",
                       tasks=["emomatching", "workingmemory", "etth1"]))


def test_missing_fit_in_grid_fails(release):
    with pytest.raises(cli.CLIError, match="격자"):
        cli.main(_argv(release, release["tmp"] / "e",
                       manifests=release["manifests"][1:],
                       predictions=release["predictions"][1:]))


def test_predictions_without_manifest_fail(release):
    with pytest.raises(cli.CLIError, match="격자|fit_manifest 가 주어지지 않은"):
        cli.main(_argv(release, release["tmp"] / "e",
                       manifests=release["manifests"][1:]))


def test_missing_predictions_file_fails_checkpoint_integrity(release):
    with pytest.raises(cli.CLIError, match="checkpoint 누락"):
        cli.main(_argv(release, release["tmp"] / "e",
                       predictions=release["predictions"][1:]))


def test_changed_checkpoint_fails(release):
    (release["manifests"][0].parent / "checkpoint.pt").write_bytes(b"tampered")
    with pytest.raises(cli.CLIError, match="checkpoint hash 불일치"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_missing_checkpoint_file_fails_without_search(release):
    (release["manifests"][0].parent / "checkpoint.pt").unlink()
    with pytest.raises(cli.CLIError, match="U20"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_inner_fit_is_rejected(release):
    p = release["manifests"][0]
    man = json.loads(p.read_text(encoding="utf-8"))
    man["role"], man["folds"]["eval_role"] = "inner", "inner_validation"
    p.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(cli.CLIError, match="outer 최종 적합이 아니다"):
        cli.main(_argv(release, release["tmp"] / "e"))


@pytest.mark.parametrize("field,message", [("split_hash", "split_hash"),
                                           ("config_hash", "config_hash")])
def test_boundary_hash_mismatch_fails(release, field, message):
    p = release["manifests"][0]
    man = json.loads(p.read_text(encoding="utf-8"))
    man[field] = "0" * 64
    p.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(cli.CLIError, match=message):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_mixed_code_hash_fails(release):
    p = release["manifests"][0]
    man = json.loads(p.read_text(encoding="utf-8"))
    man["code_hash"] = "9" * 64
    p.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(cli.CLIError, match="code_hash"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_dropped_window_fails_rather_than_partial_mean(release):
    _rewrite(release["predictions"][0], lambda rows: rows[1:])
    with pytest.raises(cli.CLIError, match="무결성|행 수|격자"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_train_subject_prediction_is_leakage(release):
    fold0_train = json.loads(release["manifests"][0].read_text())["fit_subjects"][0]

    def leak(rows):
        rows[0] = dict(rows[0], canonical_subject=fold0_train)
        return rows
    _rewrite(release["predictions"][0], leak)
    with pytest.raises(cli.CLIError, match="누설"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_inner_scope_row_is_rejected(release):
    _rewrite(release["predictions"][0],
             lambda rows: [dict(rows[0], scope="inner_validation")] + rows[1:])
    with pytest.raises(cli.CLIError, match="outer test 만"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_window_key_must_belong_to_run_key(release):
    _rewrite(release["predictions"][0],
             lambda rows: [dict(rows[0], window_key="ds002785/sub-9999/na/"
                                "emomatching/na/seq#win-0")] + rows[1:])
    with pytest.raises(cli.CLIError, match="window_key"):
        cli.main(_argv(release, release["tmp"] / "e"))


def test_parser_takes_many_fit_paths(release):
    ns = cli.build_parser().parse_args(_argv(release, release["tmp"] / "e"))
    paths = cli.resolve_paths("evaluate", ns)
    assert len(paths["fit_manifest"]) == 24 and len(paths["predictions"]) == 24
    cli.check_inputs_exist(paths)
    ns = cli.build_parser().parse_args(
        _argv(release, release["tmp"] / "e",
              predictions=[release["tmp"] / "nope.jsonl"]))
    with pytest.raises(cli.CLIError, match="U20"):
        cli.check_inputs_exist(cli.resolve_paths("evaluate", ns))
