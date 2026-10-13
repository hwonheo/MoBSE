"""ABIDE MoBSE 팔 (결정 59) 의 누설 · 배치 · 963 명 재매김 시험 — 작은 합성 자료로."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/i1_mobse_abide"))
import core  # noqa: E402


def synth(tmp: Path, n: int = 40, roi: int = 12, n_const: int = 2):
    rng = np.random.default_rng(0)
    ts = rng.normal(size=(n, roi, 100))
    ts[:, :4] += rng.normal(size=(n, 1, 100))          # 묶음 구조 조금
    for i in range(n_const):                            # 상수 영역 피험자
        ts[i, 3, 30:60] = 0.0
    label = np.array([i % 2 for i in range(n)])
    npy = tmp / "abide.npy"
    np.save(npy, {"timeseires": ts, "label": label}, allow_pickle=True)
    idx = rng.permutation(n)
    folds = {"folds": [{"fold": 0, "test": idx[:8].tolist(), "val": idx[8:14].tolist(), "train": idx[14:].tolist()}]}
    return npy, folds, ts


def test_constant_subjects_found(tmp_path):
    _, _, ts = synth(tmp_path)
    mask = core.constant_subjects(core.windows(ts))
    assert mask.tolist()[:2] == [True, True] and mask.sum() == 2


def test_prep_fits_on_train_only_and_rejects_mismatch(tmp_path):
    npy, folds, ts = synth(tmp_path)
    kept = [int(i) for i in np.flatnonzero(~core.constant_subjects(core.windows(ts)))]
    meta = core.prep_one(npy, folds, 0, kept, tmp_path / "prep")
    assert meta["fit_subjects_are_train_only"]
    z = np.load(tmp_path / "prep" / "prep.npz")
    tr, va, te = (set(z[f"idx_{r}"].tolist()) for r in ("train", "val", "test"))
    assert not (tr & va or tr & te or va & te)
    assert not ({0, 1} & (tr | va | te))                # 상수 영역 피험자는 어디에도 없음
    assert z["pca_train"].shape == (3 * len(tr), 10)
    with pytest.raises(SystemExit):
        core.prep_one(npy, folds, 0, kept[1:], tmp_path / "prep2")


def test_fit_writes_test_predictions_in_i1_layout(tmp_path, monkeypatch):
    npy, folds, ts = synth(tmp_path)
    kept = [int(i) for i in np.flatnonzero(~core.constant_subjects(core.windows(ts)))]
    core.prep_one(npy, folds, 0, kept, tmp_path / "prep")
    import mobse.v3.train as v3t
    monkeypatch.setattr(v3t, "UPDATE_BUDGET", 60)       # 시험 속도만 — 규칙 자체는 잠긴 상수
    s = core.fit_one(npy, tmp_path / "prep", "embedding", 1, tmp_path / "fit", device="cpu")
    rows = [json.loads(x) for x in (tmp_path / "fit" / "predictions.jsonl").read_text().splitlines()]
    test = sorted(set(folds["folds"][0]["test"]) & set(kept))
    assert sorted(r["subject_index"] for r in rows) == test
    assert all(0.0 <= r["p1"] <= 1.0 for r in rows)
    assert 0 <= s["selected_epoch"] < s["n_epochs"]


def test_analyze963_remaps_to_kept(tmp_path):
    spec = importlib.util.spec_from_file_location("a963", ROOT / "scripts/i1_mobse_abide/analyze963.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    A = m.i1_analyze()
    n, kept = 30, [i for i in range(30) if i not in (4, 9)]
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, n)
    y[:2] = [0, 1]
    for cond, shift in (("orig", 1.0), ("n1", 0.0)):
        ks = (0,) if cond == "orig" else (0, 1)
        for k in ks:
            for r in (1, 2):
                for f in range(5):
                    d = tmp_path / "model" / cond / f"k{k}" / f"r{r}" / f"f{f}"
                    d.mkdir(parents=True)
                    idx = [i for i in range(n) if i % 5 == f]
                    p = 1 / (1 + np.exp(-(shift * (2 * y[idx] - 1) + rng.normal(size=len(idx)))))
                    d.joinpath("predictions.jsonl").write_text("".join(
                        json.dumps({"subject_index": i, "label": int(y[i]), "p1": float(q)}) + "\n" for i, q in zip(idx, p)))
    res = m.run(tmp_path / "model", "model", kept, 50, 7, A)
    assert res["incomplete_units"] == []
    assert res["all"]["n_items"] == len(kept)
    assert res["all"]["conditions"]["n1"]["n_pairs"] == 4
