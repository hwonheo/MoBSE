"""PIOP2 확증 (결정 78) — 분할 · 블록 · 분석 시험. 자료가 필요한 시험은 Mac I3 자료 루트가 있을 때만 돈다."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "piop2_confirm"))
sys.path.insert(0, str(ROOT / "scripts" / "i3"))
import core  # noqa: E402
import p2  # noqa: E402

P1 = [f"sub-{i:04d}" for i in range(1, 158)]
P2 = [f"sub-{i:04d}" for i in range(1, 190)]
I3_ROOT = ROOT / "data" / "h1h2_scope" / "aomic"


def test_main_split_sizes_and_disjoint():
    sp = p2.make_split(P1, P2, smoke=False)
    assert (len(sp["train"]), len(sp["val"]), len(sp["test"])) == (126, 31, 189)
    assert {d for d, _ in sp["train"] + sp["val"]} == {"ds002785"}
    assert {d for d, _ in sp["test"]} == {"ds002790"}
    assert not ({s for _, s in sp["train"]} & {s for _, s in sp["val"]})


def test_smoke_split_never_uses_piop2():
    sp = p2.make_split(P1, [], smoke=True)
    assert (len(sp["train"]), len(sp["val"]), len(sp["test"])) == (100, 31, 26)
    assert {d for r in ("train", "val", "test") for d, _ in sp[r]} == {"ds002785"}
    keys = [{s for _, s in sp[r]} for r in ("train", "val", "test")]
    assert not (keys[0] & keys[1] or keys[0] & keys[2] or keys[1] & keys[2])


def test_split_is_deterministic_and_val_shared_with_smoke():
    a, b = p2.make_split(P1, P2, smoke=False), p2.make_split(P1, P2, smoke=False)
    assert a == b
    assert a["val"] == p2.make_split(P1, [], smoke=True)["val"]


@pytest.mark.skipif(not (I3_ROOT / "full_ts").exists(), reason="Mac I3 자료 루트 없음")
def test_subject_blocks_equals_i3_task_blocks():
    s = (I3_ROOT / "pilot_ids.txt").read_text().split()[0]
    a = p2.subject_blocks(I3_ROOT, "ds002785", s)
    b = core.task_blocks(I3_ROOT, s)
    for x, y in zip(a, b):
        assert np.array_equal(x, y)


def _write_fake_run(run: Path, n_subj: int = 40, seed: int = 0, seeds=p2.SEEDS):
    rng = np.random.default_rng(seed)
    run.mkdir(parents=True, exist_ok=True)
    (run / "run_config.json").write_text(json.dumps({"seeds": list(seeds)}))
    subs = [f"ds002790:sub-{i:04d}" for i in range(n_subj)]
    labels = {s: [0, 1] * 4 for s in subs}
    good = lambda y: 0.9 if y == 1 else 0.1  # noqa: E731
    for name in [core.cell_name(*c) for c in p2.CELLS]:
        for sd in seeds:
            d = run / "fits" / name / "outer0" / f"seed{sd}"
            d.mkdir(parents=True, exist_ok=True)
            rows = []
            for s in subs:
                for b, y in enumerate(labels[s]):
                    p = good(y) if name == "B_embedding" else float(rng.uniform(0.2, 0.8))
                    rows.append(json.dumps({"subject": s, "block": b, "label": y, "p1": p}))
            (d / "predictions.jsonl").write_text("\n".join(rows) + "\n")
    s_dir = run / "s" / "outer0"
    s_dir.mkdir(parents=True, exist_ok=True)
    for name in ("S_fc_logistic", "REF_activation_logistic"):
        rows = [json.dumps({"subject": s, "block": b, "label": y, "p1": float(rng.uniform(0.2, 0.8))})
                for s in subs for b, y in enumerate(labels[s])]
        (s_dir / f"{name}.jsonl").write_text("\n".join(rows) + "\n")


def test_analyze_confirms_when_b_is_perfect(tmp_path):
    _write_fake_run(tmp_path)
    res = p2.analyze(tmp_path)
    assert res["n_subjects"] == 40 and res["n_blocks"] == 320
    assert res["accuracy"]["B_embedding"]["all"] == 1.0
    assert [c["claim"] for c in res["claims"]] == ["P1", "P2"]
    assert all(c["confirmed"] for c in res["claims"])
    assert all(c["ci_level"] == 97.5 for c in res["claims"])
    assert len(res["null_sensitivity"]) == 2 and "confirmed" in res["null_sensitivity"][0]


def test_analyze_refuses_missing_cell(tmp_path):
    _write_fake_run(tmp_path)
    for f in (tmp_path / "fits" / "D_embedding_spin").rglob("predictions.jsonl"):
        f.unlink()
    with pytest.raises(SystemExit):
        p2.analyze(tmp_path)


def test_analyze_uses_run_config_seeds(tmp_path):
    _write_fake_run(tmp_path, seeds=(42,))
    res = p2.analyze(tmp_path)
    assert res["seeds"] == [42] and all(c["confirmed"] for c in res["claims"])
