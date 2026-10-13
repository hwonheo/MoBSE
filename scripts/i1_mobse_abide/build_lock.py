#!/usr/bin/env python3
"""ABIDE MoBSE 팔 잠금 (결정 59) — 만들거나 (기본) 검증한다 (``--verify``). I1 잠금과 같은 방식, I1 잠금은 건드리지 않는다.

담는 것 (전부 sha256):
* ``document`` — 잠금 문서 (``--doc``).
* ``code`` — ``scripts/i1_mobse_abide/*.py`` · import 하는 ``mobse/v2/*.py`` · ``mobse/v3/*.py`` 전체 · ``scripts/i1/analyze.py``,
  그리고 참조 잠금의 ``lock_hash`` (I1 · v3 — 그 잠금들이 같은 코드를 해시하므로 어긋나면 드러난다).
* ``data`` — 원판 ``abide.npy`` · ``abide.json`` · ``folds_draw0.json`` · I1 본 실행의 입력 뒤섞기 11 판 (n0 k0 · n1 k0–4 · n2 k0–4).
* ``public_predictions`` — 963 명 재분석에 쓰는 I1 공개 모델 ABIDE 예측 파일 (BQN · BNT · Han 각 255) 의 묶음 해시.
* ``environment`` — venv-mobse-v2 의 ``pip freeze`` 와 python · torch · CUDA · GPU.

``lock_hash`` = ``created_at_utc`` · ``reason`` · ``lock_hash`` 를 뺀 내용의 정규 JSON sha256. 검증은 다시 만들어 항목별 대조, 다르면 rc 1.

Usage (h197, 저장소 사본 루트 — PYTHONPATH 를 내보내지 말 것):
    python -B scripts/i1_mobse_abide/build_lock.py --repo-root . --data-root <D> \
        --doc docs/experiments/i1_mobse_abide_lock_v1.md --out results/i1_mobse_abide/locks/lock.json --reason "…"
    python -B scripts/i1_mobse_abide/build_lock.py --verify …(같은 인자)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "i1-mobse-abide-lock-0.1"
REF_LOCKS = {"i1": "results/i1/locks/i1_lock.json", "v3": "results/exploratory_v2/locks/v3_lock.json"}
I1_RUN = "i1/main/20261005_ac3bad06_a2"
DATA_FILES = ["i1/data/abide_noglobal_braingb/abide.npy", "i1/data/abide_noglobal_braingb/abide.json",
              "i1/data/folds_draw0.json", f"{I1_RUN}/inputs/abide/n0_k0/abide.npy"] + [
    f"{I1_RUN}/inputs/abide/{c}_k{k}/abide.npy" for c in ("n1", "n2") for k in range(5)]
VENV = "venv-mobse-v2"


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
    files = sorted(p.relative_to(repo).as_posix() for g in ("scripts/i1_mobse_abide", "mobse/v2", "mobse/v3")
                   for p in (repo / g).glob("*.py")) + ["scripts/i1/analyze.py"]
    code = {p: sha(repo / p) for p in files}
    refs = {k: json.loads((repo / v).read_text())["lock_hash"] for k, v in REF_LOCKS.items()}
    data = {p: sha(d / p) for p in DATA_FILES}
    preds = sorted((d / I1_RUN / "abide").glob("*/*/k*/r*/f*/predictions.jsonl"))
    preds = [p for p in preds if p.parts[-6] in ("bqn", "bnt", "han")]
    pub = {str(p.relative_to(d)): sha(p) for p in preds}
    freeze = subprocess.run([str(d / VENV / "bin/pip"), "freeze"], capture_output=True, text=True).stdout
    info = subprocess.run([str(d / VENV / "bin/python"), "-c",
                           "import sys, torch, json; print(json.dumps({'python': sys.version.split()[0], "
                           "'torch': torch.__version__, 'cuda': torch.version.cuda, "
                           "'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"],
                          capture_output=True, text=True).stdout
    return {
        "schema_version": SCHEMA,
        "document": {"path": a.doc.as_posix(), "sha256": sha(repo / a.doc)},
        "code": {"files": code, "code_hash": sha_text("".join(f"{p}:{h}\n" for p, h in code.items())),
                 "ref_lock_hashes": refs},
        "data": {"root_relative": data, "data_hash": sha_text("".join(f"{p}:{h}\n" for p, h in data.items()))},
        "public_predictions": {"n_files": len(pub), "per_model": {m: sum(1 for p in pub if f"/abide/{m}/" in p)
                                                                 for m in ("bqn", "bnt", "han")},
                               "bundle_hash": sha_text("".join(f"{p}:{h}\n" for p, h in sorted(pub.items())))},
        "environment": {"venv": VENV, "pip_freeze_sha256": sha_text(freeze), "pip_freeze": freeze.splitlines(),
                        **json.loads(info or "{}")},
    }


def lock_hash(body: dict) -> str:
    return sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def problems(body: dict) -> list:
    out = []
    if body["public_predictions"]["per_model"] != {"bqn": 255, "bnt": 255, "han": 255}:
        out.append(f"공개 모델 예측 수가 255 가 아니다: {body['public_predictions']['per_model']}")
    if any(l.startswith("mobse") for l in body["environment"]["pip_freeze"]):
        out.append("pip freeze 에 mobse 가 있다 — PYTHONPATH 를 내보낸 채 돌렸는가 (I1 a1 사고)")
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
    print(json.dumps({"lock_hash": h, "code_hash": body["code"]["code_hash"], "data_hash": body["data"]["data_hash"],
                      "public_bundle": body["public_predictions"]["bundle_hash"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
