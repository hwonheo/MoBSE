#!/usr/bin/env python3
"""ADHD-200 I1 잠금 (결정 62 · 63) — 만들거나 (기본) 검증한다 (``--verify``). I1 · ABIDE MoBSE 잠금은 건드리지 않는다.

담는 것 (전부 sha256):
* ``document`` — 잠금 문서.
* ``code`` — ``scripts/i1_adhd200/*.py`` · ``scripts/i1/*.py`` · ``scripts/i1_mobse_abide/*.py`` · ``mobse/v2/*.py`` ·
  ``mobse/v3/*.py``, 그리고 참조 잠금 (I1 · v3 · ABIDE MoBSE) 의 ``lock_hash``.
* ``data`` — 받은 원자료 (NITRC tar · 표현형 tar · nvols · 공개 participants.tsv), 범위 확인 목록, 원판 ``abide.npy`` ·
  ``abide.json`` · ``folds_draw0.json`` · ``coords.json``.
* ``repos`` — 공개 저장소 clone 의 HEAD 가 I1 기록 (``i1/repos_commits.txt``) 과 같은지 · 고쳐지지 않았는지 (I1 잠금과 같은 검사).
* ``environment`` — venv-i1 · venv-mobse-v2 의 ``pip freeze`` 와 python · torch · CUDA · GPU.

``lock_hash`` = ``created_at_utc`` · ``reason`` · ``lock_hash`` 를 뺀 내용의 정규 JSON sha256. 검증은 다시 만들어 항목별 대조.

Usage (h197, 저장소 사본 루트 — PYTHONPATH 를 내보내지 말 것):
    python -B scripts/i1_adhd200/build_lock.py --repo-root . --data-root <D> \\
        --doc docs/experiments/i1_adhd200_lock_v1.md --out results/i1_adhd200/locks/lock.json --reason "…"
    python -B scripts/i1_adhd200/build_lock.py --verify …(같은 인자)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "i1-adhd200-lock-0.1"
REF_LOCKS = {"i1": "results/i1/locks/i1_lock.json", "v3": "results/exploratory_v2/locks/v3_lock.json",
             "i1_mobse_abide": "results/i1_mobse_abide/locks/lock.json"}
CODE_DIRS = ("scripts/i1_adhd200", "scripts/i1", "scripts/i1_mobse_abide", "mobse/v2", "mobse/v3")
DATA_FILES = ["adhd200/nitrc/ADHD200_CC200_TCs_filtfix.tar.gz", "adhd200/nitrc/ADHD200_training_pheno.tar",
              "adhd200/nitrc/ADHD200_testing_pheno.tar", "adhd200/nitrc/nvols.csv",
              "adhd200/scoping_20261014/inventory.json",
              "adhd200/i1data/abide.npy", "adhd200/i1data/abide.json", "adhd200/i1data/folds_draw0.json",
              "adhd200/i1data/coords.json"]
PHENO_GLOB = "adhd200/raw/pheno/*/participants.tsv"
PUBLIC_REPOS = ("BrainNetworkTransformer", "BQN-demo", "RethinkingBCA")
VENVS = ("venv-i1", "venv-mobse-v2")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build(a) -> dict:
    repo, d = a.repo_root.resolve(), a.data_root
    files = sorted(p.relative_to(repo).as_posix() for g in CODE_DIRS for p in (repo / g).glob("*.py"))
    code = {p: sha(repo / p) for p in files}
    refs = {k: json.loads((repo / v).read_text())["lock_hash"] for k, v in REF_LOCKS.items()}
    data_paths = DATA_FILES + sorted(str(p.relative_to(d)) for p in d.glob(PHENO_GLOB))
    data = {p: sha(d / p) for p in data_paths}
    recorded = dict(l.split() for l in (d / "i1/repos_commits.txt").read_text().splitlines() if l.strip())
    repos = {}
    for name in PUBLIC_REPOS:
        rd = d / "i1/repos" / name
        head = subprocess.run(["git", "-C", str(rd), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(rd), "status", "--porcelain"], capture_output=True, text=True).stdout
        repos[name] = {"head": head, "matches_record": head == recorded.get(name), "clean": dirty.strip() == ""}
    env = {}
    for v in VENVS:
        freeze = subprocess.run([str(d / v / "bin/pip"), "freeze"], capture_output=True, text=True).stdout
        info = subprocess.run([str(d / v / "bin/python"), "-c",
                               "import sys, torch, json; print(json.dumps({'python': sys.version.split()[0], "
                               "'torch': torch.__version__, 'cuda': torch.version.cuda, "
                               "'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"],
                              capture_output=True, text=True).stdout
        env[v] = {"pip_freeze_sha256": sha_text(freeze), "pip_freeze": freeze.splitlines(), **json.loads(info or "{}")}
    return {
        "schema_version": SCHEMA,
        "document": {"path": a.doc.as_posix(), "sha256": sha(repo / a.doc)},
        "code": {"files": code, "code_hash": sha_text("".join(f"{p}:{h}\n" for p, h in code.items())),
                 "ref_lock_hashes": refs},
        "data": {"root_relative": data, "data_hash": sha_text("".join(f"{p}:{h}\n" for p, h in data.items()))},
        "repos": repos,
        "environment": env,
    }


def lock_hash(body: dict) -> str:
    return sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def problems(body: dict) -> list:
    out = [f"저장소 {n}: commit 기록과 다름" for n, r in body["repos"].items() if not r["matches_record"]]
    out += [f"저장소 {n}: clone 이 고쳐져 있음" for n, r in body["repos"].items() if not r["clean"]]
    for v, e in body["environment"].items():
        if any(l.startswith("mobse") for l in e["pip_freeze"]):
            out.append(f"{v} pip freeze 에 mobse 가 있다 — PYTHONPATH 를 내보낸 채 돌렸는가 (I1 a1 사고)")
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--doc", required=True, type=Path, help="저장소 상대 경로")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--reason", default=None)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv[1:])
    body = build(a)
    bad = problems(body)
    if a.verify:
        old = json.loads(a.out.read_text())
        diffs = [k for k in body if json.dumps(body[k], sort_keys=True) != json.dumps(old.get(k), sort_keys=True)]
        ok = lock_hash(body) == old.get("lock_hash")
        print(json.dumps({"lock_hash_matches": ok, "differing_sections": diffs, "problems": bad}, ensure_ascii=False))
        return 0 if ok and not diffs and not bad else 1
    if a.out.exists():
        raise SystemExit(f"잠금이 이미 있다 — 덮어쓰지 않음: {a.out}")
    if bad:
        raise SystemExit(f"잠금을 만들 수 없음: {bad}")
    if not a.reason:
        raise SystemExit("--reason 이 필요하다")
    h = lock_hash(body)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({**body, "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "reason": a.reason, "lock_hash": h}, ensure_ascii=False, indent=1))
    print(json.dumps({"lock_hash": h, "code_hash": body["code"]["code_hash"], "data_hash": body["data"]["data_hash"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
