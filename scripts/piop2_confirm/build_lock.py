#!/usr/bin/env python3
"""PIOP2 확증 잠금 생성 · 검증 (결정 78). 잠금 문서 · 코드 · 자료 · 환경을 해시해 하나의 lock_hash 로 묶는다.

* ``document`` — `docs/experiments/piop2_confirm_lock_v1.md`.
* ``code`` — ``scripts/piop2_confirm/*.py`` · ``scripts/i3/core.py`` · ``scripts/i3/analyze.py`` · ``scripts/h197/10_wi02_extract.py`` ·
  ``mobse/v2/*.py`` · ``mobse/v3/*.py``.
* ``data`` — PIOP1 (root1) 의 ``all_ids.txt`` · full_ts 157 · rest 창 628 · events 157, PIOP2 (root2) 의 id 목록 ·
  full_ts 189 · events 189, 아틀라스. 파일마다 sha256, 묶음마다 bundle hash.
* ``environment`` — 실행 python 의 ``pip freeze`` 와 python · torch · CUDA.

Usage (h197, 저장소 사본 루트 — PYTHONPATH 를 내보내지 말 것):
    $VENV/bin/python -B scripts/piop2_confirm/build_lock.py --repo-root . --root1 <r1> --root2 <r2> \
        --piop2-ids <ids> --out <lock.json> [--reason "..."]
    ... --verify  (같은 인자) → 차이 · 문제를 JSON 으로 찍고 rc 0/1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "i3"))
import core  # noqa: E402
import p2  # noqa: E402

DOC = "docs/experiments/piop2_confirm_lock_v1.md"
EXTRA_CODE = ["scripts/i3/core.py", "scripts/i3/analyze.py", "scripts/h197/10_wi02_extract.py"]


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def bundle(files: dict) -> str:
    return sha_text("".join(f"{p}:{h}\n" for p, h in sorted(files.items())))


def build(repo: Path, r1: Path, r2: Path, ids2: Path) -> dict:
    code_files = sorted(p.relative_to(repo).as_posix() for g in ("scripts/piop2_confirm", "mobse/v2", "mobse/v3")
                        for p in (repo / g).glob("*.py")) + EXTRA_CODE
    code = {p: core.sha256(repo / p) for p in code_files}
    ids1 = (r1 / "all_ids.txt").read_text().split()
    ids2l = ids2.read_text().split()
    groups = {
        "piop1_ids": {"all_ids.txt": core.sha256(r1 / "all_ids.txt")},
        "piop1_full_ts": {core.FULL_TS.format(s=s): core.sha256(r1 / core.FULL_TS.format(s=s)) for s in ids1},
        "piop1_rest": {core.REST.format(s=s, i=i): core.sha256(r1 / core.REST.format(s=s, i=i))
                       for s in ids1 for i in range(4)},
        "piop1_events": {p2.EVENTS["ds002785"].format(s=s): core.sha256(r1 / p2.EVENTS["ds002785"].format(s=s))
                         for s in ids1},
        "piop2_ids": {ids2.name: core.sha256(ids2)},
        "piop2_full_ts": {core.FULL_TS.format(s=s): core.sha256(r2 / core.FULL_TS.format(s=s)) for s in ids2l},
        "piop2_events": {p2.EVENTS["ds002790"].format(s=s): core.sha256(r2 / p2.EVENTS["ds002790"].format(s=s))
                         for s in ids2l},
        "atlas": {core.ATLAS: core.sha256(r1 / core.ATLAS)},
    }
    data = {g: {"n_files": len(v), "bundle_hash": bundle(v)} for g, v in groups.items()}
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    import torch
    env = {"python": sys.version.split()[0], "torch": torch.__version__, "cuda": torch.version.cuda,
           "cuda_available": bool(torch.cuda.is_available()), "pip_freeze_sha256": sha_text(freeze),
           "pip_freeze": freeze.splitlines()}
    body = {"schema_version": "piop2-confirm-lock-0.1", "document": {DOC: core.sha256(repo / DOC)},
            "code": {"files": code, "code_hash": bundle(code)}, "data": data, "environment": env,
            "design": {"split_seed": p2.SPLIT_SEED, "n_val": p2.N_VAL, "cells": p2.CELLS, "seeds": list(p2.SEEDS),
                       "claims": p2.CLAIMS, "sens_null": p2.SENS_NULL, "boot_seed": p2.BOOT_SEED, "n_boot": p2.N_BOOT,
                       "lag_s": core.LAG_S, "config_id": core.CONFIG_ID, "null_seed": core.NULL_SEED}}
    return body


def problems(body: dict) -> list:
    out = []
    if any(l.lower().startswith("mobse") for l in body["environment"]["pip_freeze"]):
        out.append("pip freeze 에 mobse 가 있다 — PYTHONPATH 를 내보낸 채 돌렸는가")
    if not body["environment"]["cuda_available"]:
        out.append("CUDA 를 쓸 수 없다")
    return out


def lock_hash(body: dict) -> str:
    return sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--root1", type=Path, required=True)
    ap.add_argument("--root2", type=Path, required=True)
    ap.add_argument("--piop2-ids", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    body = build(a.repo_root.resolve(), a.root1, a.root2, a.piop2_ids)
    if a.verify:
        old = json.loads(a.out.read_text())
        diff = [k for k in body if json.dumps(body[k], sort_keys=True) != json.dumps(old.get(k), sort_keys=True)]
        pr = problems(body)
        ok = lock_hash(body) == old["lock_hash"] and not diff and not pr
        print(json.dumps({"lock_hash_matches": lock_hash(body) == old["lock_hash"], "differing_sections": diff,
                          "problems": pr}, ensure_ascii=False))
        return 0 if ok else 1
    pr = problems(body)
    if pr:
        raise SystemExit(f"잠금을 만들지 않음: {pr}")
    if a.out.exists():
        raise SystemExit(f"이미 있다: {a.out} — 덮어쓰지 않는다")
    full = {**body, "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reason": a.reason,
            "lock_hash": lock_hash(body)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    core.atomic_write(a.out, json.dumps(full, ensure_ascii=False, indent=1))
    print(full["lock_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
