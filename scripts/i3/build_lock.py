#!/usr/bin/env python3
"""I3 잠금 (결정 69) — 만들거나 (기본) 검증한다 (``--verify``). ABIDE MoBSE 팔 잠금과 같은 방식. 다른 잠금은 건드리지 않는다.

담는 것 (전부 sha256):
* ``document`` — 잠금 문서 (``--doc``).
* ``code`` — ``scripts/i3/*.py`` · ``mobse/v2/*.py`` · ``mobse/v3/*.py`` · 재추출 코드 (``scripts/h1h2_scope/i3_extract_pilot.py`` ·
  ``i3_extract_check.py``) · WI-02 추출 (``scripts/h197/10_wi02_extract.py``), 그리고 v3 잠금의 ``lock_hash``.
* ``data`` — ``--data-root`` 상대: ``folds.json`` · 아틀라스 · 재추출 시계열 157 개 (+ manifest) · events 157 개 · rest 창 628 개.
  묶음마다 bundle hash, 파일마다 sha256.
* ``environment`` — 실행 python 의 ``pip freeze`` 와 python · torch · MPS.

``lock_hash`` = ``created_at_utc`` · ``reason`` · ``lock_hash`` 를 뺀 내용의 정규 JSON sha256. 검증은 다시 만들어 항목별 대조, 다르면 rc 1.

Usage (Mac, 저장소 루트 — PYTHONPATH 를 내보내지 말 것):
    .venv/bin/python -B scripts/i3/build_lock.py --repo-root . --data-root data/h1h2_scope/aomic \
        --doc docs/experiments/i3_lock_v1.md --out results/i3/locks/lock.json --reason "…"
    .venv/bin/python -B scripts/i3/build_lock.py --verify …(같은 인자)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "i3-lock-0.1"
REF_LOCKS = {"v3": "results/exploratory_v2/locks/v3_lock.json"}
EXTRA_CODE = ["scripts/h1h2_scope/i3_extract_pilot.py", "scripts/h1h2_scope/i3_extract_check.py",
              "scripts/h197/10_wi02_extract.py"]
N_SUBJECTS = 157


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def bundle(files: dict) -> str:
    return sha_text("".join(f"{p}:{h}\n" for p, h in sorted(files.items())))


def build(a) -> dict:
    repo, d = a.repo_root.resolve(), a.data_root
    files = sorted(p.relative_to(repo).as_posix() for g in ("scripts/i3", "mobse/v2", "mobse/v3")
                   for p in (repo / g).glob("*.py")) + EXTRA_CODE
    code = {p: sha(repo / p) for p in files}
    refs = {k: json.loads((repo / v).read_text())["lock_hash"] for k, v in REF_LOCKS.items()}
    ids = (d / "pilot_ids.txt").read_text().split() + (d / "main_ids.txt").read_text().split()
    groups = {
        "folds": ["splits/folds.json"],
        "atlas": ["atlas/tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz"],
        "full_ts": ["full_ts/manifest.json"] + [f"full_ts/{s}_emomatching.npz" for s in ids],
        "events": [f"raw/aomic_wave1/ds002785/raw/{s}/func/{s}_task-emomatching_acq-seq_events.tsv" for s in ids],
        "rest_windows": [f"rest_win/derivatives_v3/{s}/{s}_task-restingstate_acq-mb3_win-{i}.npy"
                         for s in ids for i in range(4)],
        "id_lists": ["pilot_ids.txt", "main_ids.txt"],
    }
    data = {}
    for g, ps in groups.items():
        per = {p: sha(d / p) for p in ps}
        data[g] = {"n_files": len(per), "bundle_hash": bundle(per), "files": per}
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    import torch
    env = {"python": sys.version.split()[0], "executable_rel": Path(sys.executable).as_posix().split("/MoBSE/")[-1],
           "torch": torch.__version__, "mps": bool(torch.backends.mps.is_available()),
           "pip_freeze_sha256": sha_text(freeze), "pip_freeze": freeze.splitlines()}
    return {
        "schema_version": SCHEMA,
        "document": {"path": a.doc.as_posix(), "sha256": sha(repo / a.doc)},
        "code": {"files": code, "code_hash": bundle(code), "ref_lock_hashes": refs},
        "data": {"root": "data/h1h2_scope/aomic (Mac, gitignore)", "groups": data,
                 "data_hash": sha_text("".join(f"{g}:{v['bundle_hash']}\n" for g, v in sorted(data.items())))},
        "environment": env,
    }


def lock_hash(body: dict) -> str:
    return sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def problems(body: dict) -> list:
    out = []
    g = body["data"]["groups"]
    want = {"full_ts": N_SUBJECTS + 1, "events": N_SUBJECTS, "rest_windows": 4 * N_SUBJECTS}
    for k, n in want.items():
        if g[k]["n_files"] != n:
            out.append(f"{k} 파일 수 {g[k]['n_files']} ≠ {n}")
    if any(l.lower().startswith("mobse") for l in body["environment"]["pip_freeze"]):
        out.append("pip freeze 에 mobse 가 있다 — PYTHONPATH 를 내보낸 채 돌렸는가")
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
