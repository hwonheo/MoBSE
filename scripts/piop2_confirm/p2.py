#!/usr/bin/env python3
"""PIOP2 확증 (결정 77 · 78) 의 핵심 — 분할 · 블록 · 준비 · 분석. 학습 한 판은 I3 의 ``core.fit_one`` · ``core.fit_s`` 를 그대로 쓴다.

설계 (잠금 문서 `docs/experiments/piop2_confirm_lock_v1.md`):
* 학습 PIOP1 126 명 · val PIOP1 31 명 (157 명에서 seed 20261017 무작위) → 평가 PIOP2 189 명 (적격 전원). 학습 한 번 (outer 하나).
* 블록 · 입력 · bank · null · 학습 규칙은 I3 와 같다 (lag 6 s · 30 s 블록 15 frame · blockz · K=3 · null seed 1729 ·
  update 예산 5,000 · val best checkpoint · config 0 · seed 42–44 확률 평균).
* 칸: B emb · D emb (순열 · spin · rewire) · S (blockz FC logistic) · 활성 참고값.
* 주장 P1 = B emb − S, P2 = B emb − D emb (순열). 2 주장 Bonferroni 97.5 % 피험자 bootstrap (seed 20261016, 10,000),
  **하한 > 0 이면 확증**. 8 블록 전체가 주 판정, 첫 짝 제외는 민감도, B − D spin · rewire 는 민감도 (판정에 쓰지 않음).
* smoke: PIOP1 만 (PIOP2 를 읽지 않음) — 같은 val 31 명, 학습 126 명 중 26 명을 가짜 test 로.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i3"))
import core  # noqa: E402  (I3 core — 잠긴 구현을 import 만 한다)

SPLIT_SEED = 20261017
N_VAL = 31
N_SMOKE_TEST = 26
CELLS = [("B", "embedding", "permutation"), ("D", "embedding", "permutation"), ("D", "embedding", "spin"),
         ("D", "embedding", "rewire")]
SEEDS = core.SEEDS
BOOT_SEED, N_BOOT = 20261016, 10000
CLAIMS = [("P1", "B_embedding", "S_fc_logistic"), ("P2", "B_embedding", "D_embedding")]
SENS_NULL = [("B_embedding", "D_embedding_spin"), ("B_embedding", "D_embedding_rewire")]
EVENTS = {"ds002785": "raw/aomic_wave1/ds002785/raw/{s}/func/{s}_task-emomatching_acq-seq_events.tsv",
          "ds002790": "raw/aomic_wave1/ds002790/raw/{s}/func/{s}_task-emomatching_acq-seq_events.tsv"}


def make_split(piop1_ids: List[str], piop2_ids: List[str], smoke: bool) -> dict:
    """{train, val, test} 피험자 (dataset, id). smoke 면 test 도 PIOP1 (PIOP2 를 쓰지 않음)."""
    order = list(np.random.default_rng(SPLIT_SEED).permutation(sorted(piop1_ids)))
    val, train = order[:N_VAL], order[N_VAL:]
    if smoke:
        test, train = train[:N_SMOKE_TEST], train[N_SMOKE_TEST:]
        test = [("ds002785", s) for s in sorted(test)]
    else:
        test = [("ds002790", s) for s in sorted(piop2_ids)]
    sp = {"train": [("ds002785", s) for s in sorted(train)], "val": [("ds002785", s) for s in sorted(val)],
          "test": test, "smoke": smoke}
    keys = {r: {tuple(x) for x in sp[r]} for r in ("train", "val", "test")}
    if keys["train"] & keys["val"] or keys["train"] & keys["test"] or keys["val"] & keys["test"]:
        raise SystemExit("train · val · test 가 겹친다")
    return sp


def subject_blocks(root: Path, dataset: str, subject: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``core.task_blocks`` 와 같은 계산을 dataset 별 events 경로로. (blockz (8,15,roi), 원 창, label)."""
    z = np.load(root / core.FULL_TS.format(s=subject))
    ts, t = z["ts"].astype(float), z["times"]
    blk = core.blocks(root / EVENTS[dataset].format(s=subject))
    if len(blk) != core.N_BLOCKS or [b["cond"] for b in blk] != list(core.CONDS) * (core.N_BLOCKS // 2):
        raise ValueError(f"{dataset}:{subject}: 블록 구조가 잠긴 형태 (c e × 4) 가 아니다")
    raw, bz, y = [], [], []
    for b in blk:
        m = (t >= b["start"] + core.LAG_S) & (t < b["end"] + core.LAG_S)
        if int(m.sum()) != core.BLOCK_FRAMES:
            raise ValueError(f"{dataset}:{subject}: 블록 창 frame 수 {int(m.sum())} ≠ {core.BLOCK_FRAMES}")
        raw.append(ts[m])
        bz.append(core.blockz(ts[m]))
        y.append(core.CONDS.index(b["cond"]))
    return np.stack(bz), np.stack(raw), np.array(y)


def prep(roots: Dict[str, Path], split: dict, out_dir: Path) -> dict:
    """I3 ``core.prep_one`` 과 같은 배열 이름 · 계산으로 prep.npz 를 쓴다 (``core.fit_one`` · ``fit_s`` 가 그대로 읽음)."""
    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    from mobse.v2.templates import bank_seed, build_bank, build_single_graph
    from mobse.v3.templates import make_null_bank, roi_centroids

    t0 = time.perf_counter()
    r1 = roots["ds002785"]
    train_ids = [s for _, s in split["train"]]
    rest = [w for s in train_ids for w in core.rest_windows(r1, s)]
    rest_subs = [s for s in train_ids for _ in range(4)]
    c_rest, z_rest = stack_window_features(rest)
    trans = fit_transform_on_training_rest(z_rest, rest_subs)
    bank = build_bank(c_rest, trans.transform(z_rest).astype(float), rest_subs, seed=bank_seed(0, core.INNER_FOLD),
                      allowed_subjects=train_ids)
    coords, is_left = roi_centroids(r1 / core.ATLAS)
    nulls = {"permutation": make_null_bank(bank, kind="permutation", seed=core.NULL_SEED),
             "spin": make_null_bank(bank, kind="spin", seed=core.NULL_SEED, coords=coords, is_left=is_left),
             "rewire": make_null_bank(bank, kind="rewire", seed=core.NULL_SEED)}
    single = build_single_graph(c_rest, rest_subs)
    arrays: Dict[str, np.ndarray] = {}
    for r in ("train", "val", "test"):
        bz, raw, y = zip(*(subject_blocks(roots[d], d, s) for d, s in split[r]))
        x = np.concatenate(bz)
        _, zf = stack_window_features(list(x))
        arrays[f"x_{r}"] = x.transpose(0, 2, 1).astype(np.float32)
        arrays[f"pca_{r}"] = trans.transform(zf).astype(np.float32)
        arrays[f"fcz_{r}"] = zf.astype(np.float32)
        arrays[f"act_{r}"] = np.concatenate(raw).mean(axis=1).astype(np.float32)
        arrays[f"y_{r}"] = np.concatenate(y)
        arrays[f"subj_{r}"] = np.repeat(np.array([f"{d}:{s}" for d, s in split[r]]), core.N_BLOCKS)
        arrays[f"block_{r}"] = np.tile(np.arange(core.N_BLOCKS), len(split[r]))
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "prep.tmp.npz", **arrays, bank=bank.templates.astype(np.float32),
             **{f"null_{k}": v.templates.astype(np.float32) for k, v in nulls.items()},
             single=single.template.astype(np.float32))
    (out_dir / "prep.tmp.npz").replace(out_dir / "prep.npz")
    meta = {"n_subjects": {r: len(split[r]) for r in ("train", "val", "test")},
            "n_blocks": {r: int(len(arrays[f"y_{r}"])) for r in ("train", "val", "test")},
            "test_datasets": sorted({d for d, _ in split["test"]}), "transform_id": trans.artifact_id,
            "bank_id": bank.bank_id, "null_ids": {k: v.bank_id for k, v in nulls.items()},
            "bank_cluster_sizes": np.bincount(bank.assignment, minlength=len(bank.templates)).tolist(),
            "seconds": time.perf_counter() - t0}
    core.atomic_write(out_dir / "prep.json", json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def analyze(run: Path) -> dict:
    """칸별 정확도 · P1 · P2 (97.5 %, 하한 > 0 이면 확증) · 첫 짝 제외 · null 민감도."""
    sys.path.insert(0, str(HERE.parent / "i3"))
    import analyze as A  # I3 analyze 의 load 함수

    seeds = json.loads((run / "run_config.json").read_text())["seeds"]
    names = [core.cell_name(*c) for c in CELLS]
    preds = {n: A.load_cell(run, n, 1, list(seeds)) for n in names}
    for n in ("S_fc_logistic", "REF_activation_logistic"):
        preds[n] = A.load_s(run, n, 1)
    missing = sorted(n for n, v in preds.items() if v is None)
    if missing:
        raise SystemExit(f"빠진 칸이 있다: {missing}")
    keys = sorted(preds[names[0]])
    if any(sorted(v) != keys for v in preds.values()):
        raise SystemExit("칸마다 블록 집합이 다르다")
    subjects = sorted({s for s, _ in keys})
    sidx = {s: i for i, s in enumerate(subjects)}
    sub = np.array([sidx[s] for s, _ in keys])
    blk = np.array([b for _, b in keys])
    correct = {n: np.array([(v[k][1] > 0.5) == (v[k][0] == 1) for k in keys], dtype=float) for n, v in preds.items()}
    N = len(subjects)
    W = np.random.default_rng(BOOT_SEED).multinomial(N, np.full(N, 1 / N), size=N_BOOT).astype(float)

    def boot(mask):
        cnt = np.bincount(sub[mask], minlength=N).astype(float)
        out = {}
        for n, c in correct.items():
            per = np.bincount(sub[mask], weights=c[mask], minlength=N)
            out[n] = (float(per.sum() / cnt.sum()), (W @ per) / (W @ cnt))
        return out

    def con(b, x, y, level=97.5):
        q = (100 - level) / 2
        d = b[x][1] - b[y][1]
        lo, hi = float(np.percentile(d, q)), float(np.percentile(d, 100 - q))
        return {"a": x, "b": y, "estimate": b[x][0] - b[y][0], "ci_level": level, "lo": lo, "hi": hi,
                "confirmed": bool(lo > 0)}

    ball, bnf = boot(np.ones(len(keys), bool)), boot(blk >= 2)
    res = {"schema": "piop2-confirm-analysis-0.1", "run": str(run), "seeds": seeds, "n_subjects": N, "n_blocks": len(keys),
           "label_counts": np.bincount([preds[names[0]][k][0] for k in keys]).tolist(),
           "boot_seed": BOOT_SEED, "n_boot": N_BOOT,
           "accuracy": {n: {"all": ball[n][0], "ci95": [float(np.percentile(ball[n][1], 2.5)),
                                                        float(np.percentile(ball[n][1], 97.5))],
                            "no_first_pair": bnf[n][0]} for n in preds},
           "claims": [{"claim": c, **con(ball, x, y)} for c, x, y in CLAIMS],
           "claims_no_first_pair": [{"claim": c, **con(bnf, x, y)} for c, x, y in CLAIMS],
           "null_sensitivity": [con(ball, x, y) for x, y in SENS_NULL],
           "null_sensitivity_no_first_pair": [con(bnf, x, y) for x, y in SENS_NULL]}
    return res
