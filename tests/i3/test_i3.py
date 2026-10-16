"""I3 구동기 시험 (결정 69) — 블록 · 창 · 분할 · 분석 contrast. 실제 자료 없이 합성 자료로."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "i3"))
import core  # noqa: E402


def write_events(path: Path, start: float = 10.0, soa: float = 5.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["onset\tduration\ttrial_type"]
    t = start
    for b in range(8):
        cond = core.CONDS[b % 2]
        for _ in range(6):
            rows.append(f"{t}\t1.5\t{cond}")
            t += soa
    path.write_text("\n".join(rows) + "\n")


def write_subject(root: Path, s: str, rng) -> None:
    write_events(root / core.EVENTS.format(s=s))
    times = 4.0 + 2.0 * np.arange(135)
    (root / "full_ts").mkdir(parents=True, exist_ok=True)
    np.savez(root / core.FULL_TS.format(s=s), ts=rng.standard_normal((135, 100)).astype(np.float32), times=times)


def test_blocks_are_eight_30s_alternating(tmp_path):
    write_events(tmp_path / "e.tsv")
    blk = core.blocks(tmp_path / "e.tsv")
    assert len(blk) == 8
    assert [b["cond"] for b in blk] == ["control", "emotion"] * 4
    assert {round(b["end"] - b["start"], 6) for b in blk} == {30.0}
    assert all(b["n_trials"] == 6 for b in blk)


def test_blockz_removes_mean_and_scale():
    rng = np.random.default_rng(0)
    w = rng.standard_normal((15, 100)) * 3 + 7
    z = core.blockz(w)
    assert np.allclose(z.mean(0), 0, atol=1e-12)
    assert np.allclose(z.std(0), 1, atol=1e-12)
    w[:, 5] = 1.0
    with pytest.raises(ValueError):
        core.blockz(w)


def test_task_blocks_use_15_frames_after_lag(tmp_path):
    write_subject(tmp_path, "sub-0001", np.random.default_rng(1))
    bz, raw, y = core.task_blocks(tmp_path, "sub-0001")
    assert bz.shape == (8, 15, 100) and raw.shape == (8, 15, 100)
    assert y.tolist() == [0, 1] * 4
    z = np.load(tmp_path / core.FULL_TS.format(s="sub-0001"))
    first = (z["times"] >= 10.0 + core.LAG_S) & (z["times"] < 40.0 + core.LAG_S)
    assert np.allclose(raw[0], z["ts"][first])


def test_fold_parts_rejects_overlap():
    tag = lambda xs: [f"ds002785:{x}" for x in xs]  # noqa: E731
    good = {"outer_folds": [{"test_subjects": tag(["c"]), "train_subjects": tag(["a", "b"]),
                             "inner": [{"train_subjects": tag(["a"]), "val_subjects": tag(["b"])}]}]}
    assert core.fold_parts(good, 0) == {"train": ["a"], "val": ["b"], "test": ["c"]}
    bad = json.loads(json.dumps(good))
    bad["outer_folds"][0]["test_subjects"] = tag(["a"])
    with pytest.raises(SystemExit):
        core.fold_parts(bad, 0)


def test_smoke_folds_use_only_pilot_and_are_disjoint():
    pilot = [f"sub-{i:04d}" for i in range(31)]
    f = core.smoke_folds(pilot)
    p = core.fold_parts(f, 0)
    assert len(p["test"]) == 6 and len(p["val"]) == 6 and len(p["train"]) == 19
    assert set(p["train"]) | set(p["val"]) | set(p["test"]) == set(pilot)


def test_cell_names_cover_main_and_sensitivity():
    names = [core.cell_name(*c) for c in core.MAIN_CELLS + core.SENS_CELLS]
    assert len(names) == len(set(names)) == 18
    assert "A_mean" in names and "C_embedding_spin" in names and "NG" in names


def test_analyze_contrast_matches_known_difference(tmp_path):
    """A 는 모든 블록을 맞히고 B 는 홀수 블록만 틀리게 만들면 H1 = 0.5, 다른 칸은 A 와 같아 0."""
    run = tmp_path / "run"
    subs = [f"sub-{i:04d}" for i in range(20)]
    (run).mkdir()
    (run / "run_config.json").write_text(json.dumps({"n_outer": 1, "seeds": [42]}))
    labels = {(s, b): b % 2 for s in subs for b in range(8)}

    def write(path, wrong_odd):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps({"subject": s, "block": b, "label": y,
                                            "p1": float((1 - y) if (wrong_odd and b % 2) else y)}) + "\n"
                                for (s, b), y in labels.items()))

    for c in core.MAIN_CELLS + core.SENS_CELLS:
        n = core.cell_name(*c)
        write(run / "fits" / n / "outer0" / "seed42" / "predictions.jsonl", n == "B_mean")
        (run / "fits" / n / "outer0" / "seed42" / "summary.json").write_text(json.dumps(
            {"test_p_sd": 0.5, "val_p_sd": 0.5, "selected_epoch": 3, "seconds": 1.0}))
    for n in ("S_fc_logistic", "REF_activation_logistic"):
        write(run / "s" / "outer0" / f"{n}.jsonl", False)
    r = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/i3/analyze.py"), "--run", str(run), "--n-boot", "500"],
                       capture_output=True, text=True, env={"PYTHONPATH": str(ROOT)})
    assert r.returncode == 0, r.stderr
    res = json.loads((run / "analysis" / "analysis.json").read_text())
    pri = {(x["structure"], x["hypothesis"]): x for x in res["primary"]}
    assert pri[("mean", "H1")]["estimate"] == pytest.approx(0.5)
    assert pri[("mean", "H1")]["judgment"] == "하한 > δ"
    assert pri[("mean", "H2")]["estimate"] == 0.0
    assert pri[("embedding", "H1")]["estimate"] == 0.0
    nofirst = {(x["structure"], x["hypothesis"]): x for x in res["sensitivity_no_first_pair"]}
    assert nofirst[("mean", "H1")]["estimate"] == pytest.approx(0.5)
    assert res["n_blocks"] == 160 and res["fits"]["n"] == 18
