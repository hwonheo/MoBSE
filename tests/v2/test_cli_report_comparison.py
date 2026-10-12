"""report-comparison 하위 명령 (남은 작업 2-c, 09-25 16:15) — 보조 비교 S·NG·SG 의
칸별 BA 와 A−S 를 95% 기술적 CI 로 낸다 (계획서 §6·§8).

evaluate 시험의 합성 release (A–D, main pool 10명, outer 2) 를 evaluate 로 돌린 뒤,
같은 folds 로 S (outer 0 logistic / outer 1 MLP)·NG·SG outer fit 을 합성한다.
실자료 fit 은 없다 (main pool 미소비).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("yaml")

from mobse.v2 import cli
from mobse.v2.config import config_hash, load_config
from mobse.v2.evaluate import CLASSIFICATION_TASKS


def _module(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_mobse_rc_{name}", Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ev = _module("test_cli_evaluate")
_so = _module("test_cli_s_outer")
_co = _module("test_cli_comparator_outer")
CONFIG, _argv, release = _ev.CONFIG, _ev._argv, _ev.release
SEEDS, SPLIT_HASH = (42, 43, 44), _ev.SPLIT_HASH

pytestmark = pytest.mark.skipif(not CONFIG.is_file(), reason="배포 config 없음")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _cmp_prob(structure, subject, task, window, seed) -> float:
    """NG 는 모두 맞힌다. SG 는 짝수 subject 의 EM 을 틀린다."""
    truth = CLASSIFICATION_TASKS.index(task)
    wrong = structure == "SG" and task == "emomatching" and int(subject[-4:]) % 2 == 0
    base = 0.8 if (truth == 1) != wrong else 0.2
    return round(base + 0.01 * (window - 1.5) + 0.005 * (seed - 43), 6)


def _make_cmp(root: Path, structure, fold, seed, cfg_hash) -> Path:
    of = fold["outer_fold"]
    d = root / f"{structure}_o{of}_s{seed}"
    d.mkdir(parents=True)
    ckpt = d / "checkpoint.pt"
    ckpt.write_bytes(f"{structure}{of}{seed}".encode())
    sha = _sha(ckpt)
    fid = f"outer-{structure}-o{of}i9s{seed}-{sha[:12]}"
    man = {"schema_version": "wi05-fit-manifest-0.1", "fit_id": fid,
           "parent_release": "synthetic", "role": "outer", "cell": structure,
           "folds": {"outer_fold": of, "inner_fold": 9,
                     "n_train_subjects": len(fold["train_subjects"]),
                     "n_eval_subjects": len(fold["test_subjects"]),
                     "eval_role": "outer_test"},
           "model_seed": seed, "bank_seed": 1, "null_seed": 2,
           "fit_subjects": fold["train_subjects"], "scaler_id": "s", "pca_id": "s",
           "bank_id": "b", "code_hash": "c" * 64, "env_hash": "e" * 64,
           "config_hash": cfg_hash, "source_hash": "f" * 64, "split_hash": SPLIT_HASH}
    (d / "fit_manifest.json").write_text(json.dumps(man), encoding="utf-8")
    (d / "fit_report.json").write_text(json.dumps(
        {"fit_id": fid, "config_id": _co.CID, "epochs_run": _co.E,
         "checkpoint_sha256": sha}), encoding="utf-8")
    rows = []
    for s in fold["test_subjects"]:
        for t in CLASSIFICATION_TASKS:
            rk = _ev._run_key(s, t)
            for w in range(4):
                rows.append({"schema_version": "wi05-window-predictions-0.1",
                             "canonical_subject": s, "group_id": s, "run_key": rk,
                             "window_key": f"{rk}#win-{w}",
                             "truth": CLASSIFICATION_TASKS.index(t),
                             "p_class1": _cmp_prob(structure, s, t, w, seed),
                             "cell": structure, "model_seed": seed, "scope": "outer_test",
                             "checkpoint_sha256": sha, "fit_id": fid})
    (d / "window_predictions.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return d / "fit_manifest.json"


def _subjects(path: Path, pool, *, group=None) -> Path:
    group = group or {}
    rows = [{"schema_version": "t", "canonical_subject": s, "group_id": group.get(s, s),
             "cohort": "ds002785", "eligible": True, "assignment": "main",
             "assignment_reason": "t"} for s in pool]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


@pytest.fixture()
def rc(release):  # noqa: F811
    ev = release["tmp"] / "ev"
    assert cli.main(_argv(release, ev)) == 0
    tmp = release["tmp"]
    folds = json.loads(release["folds"].read_text(encoding="utf-8"))
    outer = folds["outer_folds"]
    cfg_hash = config_hash(load_config(CONFIG))
    root = tmp / "cmp"
    s_reports = [_so._make_fit(root, outer[0], _so.LOGI, _so.LOGI_SET, None, cfg_hash)]
    s_reports += [_so._make_fit(root, outer[1], _so.MLP, _so.MLP_SET, s, cfg_hash)
                  for s in SEEDS]
    sel_dir = tmp / "sel"
    sel_dir.mkdir()

    def _write(name, rec):
        p = sel_dir / name
        p.write_text(json.dumps(rec), encoding="utf-8")
        return p

    s_sel = [_write("s_o0.json", _so._selection(0, cfg_hash, _so.LOGI)),
             _write("s_o1.json", _so._selection(1, cfg_hash, _so.MLP))]
    cmp_fits, cmp_sel = {}, {}
    for st in ("NG", "SG"):
        cmp_fits[st] = [_make_cmp(root, st, f, s, cfg_hash) for f in outer for s in SEEDS]
        cmp_sel[st] = [_write(f"{st}_o{f['outer_fold']}.json",
                              _co._selection(st, f["outer_fold"], cfg_hash)) for f in outer]
    subj = _subjects(tmp / "subjects.jsonl", release["pool"])
    return {**release, "ev": ev, "subjects": subj, "s_reports": s_reports, "s_sel": s_sel,
            "cmp_fits": cmp_fits, "cmp_sel": cmp_sel, "outer": outer, "sel_dir": sel_dir}


def _cargv(r, out, **over):
    args = {"config": [CONFIG], "splits": [r["folds"]],
            "evaluation": [r["ev"] / "evaluation.json"],
            "predictions": [r["ev"] / "run_predictions.jsonl"],
            "subjects": [r["subjects"]], "s-selection": r["s_sel"],
            "s-fit-report": r["s_reports"], "ng-selection": r["cmp_sel"]["NG"],
            "ng-fit-manifest": r["cmp_fits"]["NG"], "sg-selection": r["cmp_sel"]["SG"],
            "sg-fit-manifest": r["cmp_fits"]["SG"], "output-dir": [out]}
    args.update(over)
    argv = ["report-comparison"]
    for k, v in args.items():
        if v is None:
            continue
        argv += [f"--{k}"] + [str(x) for x in v]
    return argv


def _raises(r, match, **over):
    with pytest.raises(cli.CLIError, match=match):
        cli.main(_cargv(r, r["tmp"] / "rc_bad", **over))


def _hand_ci(vec, n, pct, seed=9001, n_boot=10_000):
    rng = np.random.Generator(np.random.PCG64(seed))
    draws = rng.integers(0, n, size=(n_boot, n))
    stats = np.asarray(vec)[draws].mean(axis=1)
    return tuple(float(x) for x in np.percentile(stats, pct))


# --------------------------------------------------------------------------- #
# 정상 경로·손계산
# --------------------------------------------------------------------------- #


def test_registered_with_required_inputs():
    assert "report-comparison" in cli.SUBCOMMANDS
    need = cli.REQUIRED_PATHS["report-comparison"]
    for arg in ("s_selection", "s_fit_report", "ng_selection", "ng_fit_manifest",
                "sg_selection", "sg_fit_manifest", "evaluation", "predictions", "splits"):
        assert arg in need
        if arg.endswith(("selection", "fit_report", "fit_manifest")):
            assert ("report-comparison", arg) in cli.MULTI_PATHS


def test_hand_checked(rc):
    out = rc["tmp"] / "rc"
    assert cli.main(_cargv(rc, out)) == 0
    st = json.loads((out / "comparison_statistics.json").read_text(encoding="utf-8"))
    assert st["schema_version"] == cli.COMPARISON_REPORT_SCHEMA
    pool = sorted(rc["pool"])
    even = [int(s[-4:]) % 2 == 0 for s in pool]
    # A 는 모두 맞힌다 (b=1). S 는 짝수 WM 을 틀린다 (b=0.5). NG 모두 맞힘, SG 짝수 EM 틀림.
    assert st["subject_scores"]["S"] == {s: (0.5 if e else 1.0) for s, e in zip(pool, even)}
    ba = st["cell_balanced_accuracy"]
    assert ba["S"]["point_estimate"] == pytest.approx(0.75)
    assert ba["NG"]["point_estimate"] == pytest.approx(1.0)
    assert ba["SG"]["point_estimate"] == pytest.approx(0.75)
    s_vec = [0.5 if e else 1.0 for e in even]
    assert (ba["S"]["ci_lo"], ba["S"]["ci_hi"]) == pytest.approx(
        _hand_ci(s_vec, 10, (2.5, 97.5)))
    ams = st["auxiliary_contrasts"]["A_minus_S"]
    vec = [0.5 if e else 0.0 for e in even]
    assert ams["point_estimate"] == pytest.approx(0.25)
    assert (ams["ci_lo"], ams["ci_hi"]) == pytest.approx(_hand_ci(vec, 10, (2.5, 97.5)))
    assert ams["percentiles"] == [2.5, 97.5]
    assert ams["primary"] is False and ams["role"] == "auxiliary"
    # [개정 P12] (결정 18): NG 는 모두 맞힘 → A−NG = 0; SG 짝수 EM 틀림 → A−SG = A−S 벡터.
    amng = st["auxiliary_contrasts"]["A_minus_NG"]
    assert amng["point_estimate"] == pytest.approx(0.0)
    assert (amng["ci_lo"], amng["ci_hi"]) == pytest.approx((0.0, 0.0))
    amsg = st["auxiliary_contrasts"]["A_minus_SG"]
    assert amsg["point_estimate"] == pytest.approx(0.25)
    assert (amsg["ci_lo"], amsg["ci_hi"]) == pytest.approx(_hand_ci(vec, 10, (2.5, 97.5)))
    for name in ("A_minus_NG", "A_minus_SG"):
        c = st["auxiliary_contrasts"][name]
        assert c["primary"] is False and c["role"] == "auxiliary"
        assert c["percentiles"] == [2.5, 97.5]
    assert list(st["auxiliary_contrasts"]) == ["A_minus_S", "A_minus_NG", "A_minus_SG"]
    assert st["not_reported"] == {
        "parameter_and_cost": "이 명령 범위 밖 (계획서 §6 — 별도 조각)"}
    assert st["bootstrap"]["seed"] == 9001 and st["bootstrap"]["n_boot"] == 10_000
    assert st["bootstrap"]["n_subjects"] == 10
    assert st["s_selected_by_outer_fold"]["0"]["candidate"] == _so.LOGI
    assert st["s_selected_by_outer_fold"]["1"]["outer_epochs"] == _so.E
    assert set(st["inputs"]["fits"]) == {"S", "NG", "SG"}
    assert len(st["inputs"]["fits"]["S"]) == 4 and len(st["inputs"]["fits"]["NG"]) == 6


def test_same_bootstrap_as_report(rc):
    """같은 입력이면 report 의 index 와 같다 — A−B 를 report 로, A−S 를 여기서."""
    rep = rc["tmp"] / "rep"
    assert cli.main(["report", "--config", str(CONFIG),
                     "--evaluation", str(rc["ev"] / "evaluation.json"),
                     "--predictions", str(rc["ev"] / "run_predictions.jsonl"),
                     "--subjects", str(rc["subjects"]), "--output-dir", str(rep)]) == 0
    out = rc["tmp"] / "rc"
    assert cli.main(_cargv(rc, out)) == 0
    a = json.loads((rep / "statistics.json").read_text(encoding="utf-8"))
    b = json.loads((out / "comparison_statistics.json").read_text(encoding="utf-8"))
    # B 와 S 는 같은 subject b 를 가진다 (짝수 WM 틀림) → 같은 index 면 같은 95% 구간.
    assert b["cell_balanced_accuracy"]["S"]["ci_lo"] == a["cell_balanced_accuracy"]["B"]["ci_lo"]
    assert b["cell_balanced_accuracy"]["S"]["ci_hi"] == a["cell_balanced_accuracy"]["B"]["ci_hi"]
    assert b["bootstrap"]["n_groups"] == a["bootstrap"]["n_groups"]


# --------------------------------------------------------------------------- #
# 가드
# --------------------------------------------------------------------------- #


def test_overwrite_refused(rc):
    out = rc["tmp"] / "rc"
    assert cli.main(_cargv(rc, out)) == 0
    with pytest.raises(cli.CLIError, match="덮어쓰지 않는다"):
        cli.main(_cargv(rc, out))


@pytest.mark.parametrize("arg", ["s-selection", "s-fit-report", "ng-selection",
                                 "ng-fit-manifest", "sg-selection", "sg-fit-manifest"])
def test_every_cell_input_required(rc, arg):
    with pytest.raises(SystemExit):
        cli.main(_cargv(rc, rc["tmp"] / "rc_bad", **{arg: None}))


def test_duplicate_selection_fold_refused(rc):
    _raises(rc, "S 선택 기록 outer fold 0 가 두 번",
            **{"s-selection": [rc["s_sel"][0], rc["s_sel"][0], rc["s_sel"][1]]})


def test_selection_without_outer_fold_refused(rc):
    p = rc["sel_dir"] / "ng_bad.json"
    rec = json.loads(rc["cmp_sel"]["NG"][0].read_text(encoding="utf-8"))
    del rec["outer_fold"]
    p.write_text(json.dumps(rec), encoding="utf-8")
    _raises(rc, "NG 선택 기록 .*outer_fold 없음",
            **{"ng-selection": [p, rc["cmp_sel"]["NG"][1]]})


def test_swapped_structure_selection_refused(rc):
    with pytest.raises(cli.CLIError):
        cli.main(_cargv(rc, rc["tmp"] / "rc_bad",
                        **{"ng-selection": rc["cmp_sel"]["SG"]}))


def test_evaluation_split_hash_must_match_folds(rc):
    p = rc["tmp"] / "folds_other.json"
    d = json.loads(rc["folds"].read_text(encoding="utf-8"))
    d["split_hash"] = "a" * 64
    p.write_text(json.dumps(d), encoding="utf-8")
    _raises(rc, "evaluation.json 의 split_hash 가 --splits", splits=[p])


def test_run_predictions_sha_checked(rc):
    p = rc["tmp"] / "rp_copy.jsonl"
    p.write_text((rc["ev"] / "run_predictions.jsonl").read_text(encoding="utf-8") + "\n",
                 encoding="utf-8")
    _raises(rc, "같은 evaluate 산출물이 아니다", predictions=[p])


def test_truth_must_match_a_run(rc):
    subj = rc["outer"][1]["test_subjects"][0]
    for r in rc["s_reports"][1:]:
        pred = r.parent / "s_window_predictions.jsonl"
        rows = [json.loads(x) for x in pred.read_text(encoding="utf-8").splitlines() if x]
        for row in rows:
            if row["canonical_subject"] == subj and "emomatching" in row["run_key"]:
                row["truth"] = 1 - row["truth"]
        pred.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
        d = json.loads(r.read_text(encoding="utf-8"))
        d["window_predictions_sha256"] = _sha(pred)
        r.write_text(json.dumps(d), encoding="utf-8")
    _raises(rc, "truth 가 A run 과 다르다")


def test_group_must_match_subjects(rc):
    subj = rc["outer"][0]["test_subjects"][0]
    other = _subjects(rc["tmp"] / "subjects_g.jsonl", rc["pool"], group={subj: "fam-1"})
    _raises(rc, "group_id 가 subjects.jsonl 과 다르다", subjects=[other])


def test_comparison_run_absent_from_a_refused(rc, monkeypatch):
    real = cli._load_s_outer

    def extra(*a, **k):
        got = real(*a, **k)
        key = next(iter(got["runs"]))
        got["runs"][("S", "ds002785:sub-0099", key[2])] = dict(got["runs"][key])
        return got

    monkeypatch.setattr(cli, "_load_s_outer", extra)
    _raises(rc, "A 에 없는 run")


def test_comparison_subject_set_must_equal_a(rc, monkeypatch):
    real = cli._load_comparator_outer
    drop = sorted(rc["pool"])[0]

    def fewer(*a, **k):
        got = real(*a, **k)
        got["runs"] = {k2: v for k2, v in got["runs"].items() if k2[1] != drop}
        return got

    monkeypatch.setattr(cli, "_load_comparator_outer", fewer)
    _raises(rc, "NG 의 subject 집합이 A 와 다르다")


def test_incomplete_comparison_subject_refused(rc, monkeypatch):
    real = cli._load_comparator_outer
    drop = sorted(rc["pool"])[0]

    def half(*a, **k):
        got = real(*a, **k)
        got["runs"] = {k2: v for k2, v in got["runs"].items()
                       if not (k2[1] == drop and k2[2] == "emomatching")}
        return got

    monkeypatch.setattr(cli, "_load_comparator_outer", half)
    _raises(rc, "NG: .*complete-case")


@pytest.fixture()
def a_wrong(monkeypatch):
    """A 가 홀수 subject 의 EM 을 틀리게 (release 를 만들기 전에 적용)."""
    real = _ev._prob

    def prob(cell, subject, task, window, seed):
        if cell == "A" and task == "emomatching" and int(subject[-4:]) % 2 == 1:
            return round(1.0 - real(cell, subject, task, window, seed), 6)
        return real(cell, subject, task, window, seed)

    monkeypatch.setattr(_ev, "_prob", prob)


def test_a_minus_s_uses_a_run_correctness(a_wrong, rc):
    out = rc["tmp"] / "rc"
    assert cli.main(_cargv(rc, out)) == 0
    st = json.loads((out / "comparison_statistics.json").read_text(encoding="utf-8"))
    pool = sorted(rc["pool"])
    # A: 홀수 b=0.5, 짝수 1.0 / S: 홀수 1.0, 짝수 0.5 → A−S = −0.5 / +0.5
    vec = [0.5 if int(s[-4:]) % 2 == 0 else -0.5 for s in pool]
    ams = st["auxiliary_contrasts"]["A_minus_S"]
    assert ams["point_estimate"] == pytest.approx(0.0)
    assert (ams["ci_lo"], ams["ci_hi"]) == pytest.approx(_hand_ci(vec, 10, (2.5, 97.5)))


def test_a_minus_s_uses_s_runs_not_other_cell(rc, monkeypatch):
    """A−S 에 NG run 을 넣으면 (b=1) 점추정이 0 이 된다 — S 여야 0.25."""
    out = rc["tmp"] / "rc"
    assert cli.main(_cargv(rc, out)) == 0
    st = json.loads((out / "comparison_statistics.json").read_text(encoding="utf-8"))
    assert st["auxiliary_contrasts"]["A_minus_S"]["point_estimate"] == pytest.approx(0.25)
    assert st["cell_balanced_accuracy"]["SG"]["ci_lo"] < 1.0


@pytest.fixture()
def sg_all_em_wrong(monkeypatch):
    """SG 가 모든 subject 의 EM 을 틀리게 (rc 를 만들기 전에 적용) — S·SG 벡터를 가른다."""
    real = _cmp_prob

    def prob(structure, subject, task, window, seed):
        if structure == "SG" and task == "emomatching":
            return round(0.8 + 0.01 * (window - 1.5) + 0.005 * (seed - 43), 6)  # EM truth 0 → 틀림
        return real(structure, subject, task, window, seed)

    monkeypatch.setitem(globals(), "_cmp_prob", prob)


def test_each_structure_contrast_uses_its_own_cell(sg_all_em_wrong, rc):
    out = rc["tmp"] / "rc"
    assert cli.main(_cargv(rc, out)) == 0
    st = json.loads((out / "comparison_statistics.json").read_text(encoding="utf-8"))
    aux = st["auxiliary_contrasts"]
    # A b=1 / S 짝수 0.5 / NG 1 / SG 전부 0.5
    assert aux["A_minus_S"]["point_estimate"] == pytest.approx(0.25)
    assert aux["A_minus_NG"]["point_estimate"] == pytest.approx(0.0)
    assert aux["A_minus_SG"]["point_estimate"] == pytest.approx(0.5)
    assert (aux["A_minus_SG"]["ci_lo"], aux["A_minus_SG"]["ci_hi"]) == pytest.approx(
        (0.5, 0.5))
    assert set(st["subject_scores"]["SG"].values()) == {0.5}


def test_all_cells_and_contrasts_share_one_index(rc, monkeypatch):
    from mobse.v2 import statistics as ST
    seen = []
    real = ST.paired_bootstrap

    def spy(values, group_of, *, indices, seed, n_boot, pct):
        seen.append((id(indices), list(values), seed, n_boot, tuple(pct)))
        return real(values, group_of, indices=indices, seed=seed, n_boot=n_boot, pct=pct)

    monkeypatch.setattr(ST, "paired_bootstrap", spy)
    assert cli.main(_cargv(rc, rc["tmp"] / "rc")) == 0
    # 칸 BA 3 + contrast 3 (A−S·A−NG·A−SG) = 6 호출, 모두 같은 index 객체·같은 subject 순서
    assert len(seen) == 6
    assert len({s[0] for s in seen}) == 1
    assert all(s[1] == sorted(rc["pool"]) and s[2:] == (9001, 10_000, (2.5, 97.5))
               for s in seen)


def test_bootstrap_indices_built_once_from_locked_config(rc, monkeypatch):
    from mobse.v2 import statistics as ST
    calls = []
    real = ST.bootstrap_indices

    def spy(group_of, subjects, *, seed, n_boot):
        calls.append((list(subjects), seed, n_boot))
        return real(group_of, subjects, seed=seed, n_boot=n_boot)

    monkeypatch.setattr(ST, "bootstrap_indices", spy)
    assert cli.main(_cargv(rc, rc["tmp"] / "rc")) == 0
    assert calls == [(sorted(rc["pool"]), 9001, 10_000)]
