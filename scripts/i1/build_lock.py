#!/usr/bin/env python3
"""I1 사전등록 잠금 — 만들거나 (기본) 검증한다 (``--verify``). 결정 38-4 (저장소 내 잠금 문서 + 잠금 해시).

담는 것 (전부 sha256):
* ``document`` — 잠금 문서 (``--doc``).
* ``code`` — ``scripts/i1/*.py`` (경로순) 와 I1 이 import 하는 v2 · v3 모듈 (``mobse/v2/baselines.py`` · ``mobse/v3/templates.py``),
  그리고 MoBSE embedding 팔이 부르는 v3 CLI 의 잠금 참조 (``results/exploratory_v2/locks/v3_lock.json`` 의 ``lock_hash``).
* ``data`` — 입력 자료 · fold · 좌표 · atlas · AOMIC 창 목록과 v1 분할.
* ``v1_sources`` — MoBSE mean 팔이 재사용하는 v1 창 예측 파일 90 개 (결정 44) 의 해시 목록과 묶음 해시.
* ``repos`` — 공개 저장소 clone 마다 ``git rev-parse HEAD`` 가 ``repos_commits.txt`` 와 같은지, ``git status --porcelain`` 이 비었는지
  (wrapper 는 저장소 파일을 고치지 않는다 — 결정 41-1).
* ``environment`` — venv-i1 의 ``pip freeze`` 전체와 sha256, 10-02 저장본 (``venv_i1_freeze.txt``) 대비 더해지거나 빠진 줄,
  python · torch · CUDA · GPU. (저장본 뒤 10-02 17:47 에 bctpy 0.6.1 이 설치됐다 — 일치를 요구하지 않고 차이를 기록한다.)

``lock_hash`` = ``created_at_utc`` · ``reason`` · ``lock_hash`` 를 뺀 내용의 정규 JSON sha256. 검증은 같은 내용을 다시 만들어
항목별로 대조하고, 하나라도 다르면 rc 1.

Usage (h197, 저장소 사본 루트):
    python scripts/i1/build_lock.py --repo-root . --data-root <D> --doc docs/experiments/<잠금 문서>.md \\
        --out results/i1/locks/i1_lock.json --reason "…"
    python scripts/i1/build_lock.py --verify --repo-root . --data-root <D> --doc … --out results/i1/locks/i1_lock.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "i1-lock-0.1"
EXTRA_CODE = ("mobse/v2/baselines.py", "mobse/v3/templates.py")
V3_LOCK = "results/exploratory_v2/locks/v3_lock.json"
PUBLIC_REPOS = ("BrainNetworkTransformer", "BQN-demo", "RethinkingBCA", "BrainGB")
DATA_FILES = (
    "i1/data/abide_noglobal_braingb/abide.npy", "i1/data/abide_noglobal_braingb/abide.json",
    "i1/data/folds_draw0.json", "i1/data/folds_site.json", "i1/data/cc200_coords.json",
    "abide_pcp/resources/cc200_roi_atlas.nii.gz", "abide_pcp/resources/CC200_ROI_labels.csv",
    "i1/data/aomic_win/abide.npy", "i1/data/aomic_win/folds.json", "i1/data/aomic_win/samples.jsonl",
    "i1/data/aomic_win/coords.json", "derivatives_v3/windows_piop1.jsonl", "derivatives_v3/splits_piop1_p7/folds.json",
    "atlas_2009c/tpl-MNI152NLin2009cAsym_res-02_atlas-Schaefer2018_desc-100Parcels7Networks_dseg.nii.gz",
)
V1_MAIN = "main_oof/20260928_1cd4054_main_a2"
V1_SENS = "null_sens/20260929_97e434a_a1"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def v1_source_paths(d: Path):
    out = []
    for o in range(5):
        for s in (42, 43, 44):
            out.append(d / V1_MAIN / "fits/outer" / f"o{o}" / f"A_s{s}" / "window_predictions.jsonl")
            out.append(d / V1_MAIN / "fits/outer" / f"o{o}" / f"C_s{s}" / "window_predictions.jsonl")
            for ns in (1730, 1731, 1732, 1733):
                out.append(d / V1_SENS / "fits" / f"s{ns}" / f"o{o}" / f"C_s{s}" / "window_predictions.jsonl")
    return out


def build(a) -> dict:
    repo, d = a.repo_root.resolve(), a.data_root
    code_files = sorted(p.relative_to(repo).as_posix() for p in (repo / "scripts/i1").glob("*.py")) + list(EXTRA_CODE)
    code = {p: sha(repo / p) for p in code_files}
    v3 = json.loads((repo / V3_LOCK).read_text())
    data = {p: sha(d / p) for p in DATA_FILES}
    v1 = {str(p.relative_to(d)): sha(p) for p in v1_source_paths(d)}
    recorded = dict(line.split() for line in (d / "i1/repos_commits.txt").read_text().splitlines() if line.strip())
    repos = {}
    for name in PUBLIC_REPOS:
        rd = d / "i1/repos" / name
        head = subprocess.run(["git", "-C", str(rd), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(rd), "status", "--porcelain"], capture_output=True, text=True).stdout
        repos[name] = {"head": head, "recorded": recorded.get(name), "matches_record": head == recorded.get(name),
                       "clean": dirty.strip() == "", "dirty_lines": len(dirty.splitlines())}
    py = d / "venv-i1/bin/python"
    freeze = subprocess.run([str(d / "venv-i1/bin/pip"), "freeze"], capture_output=True, text=True).stdout
    saved = (d / "i1/venv_i1_freeze.txt").read_text()
    info = subprocess.run([str(py), "-c", "import sys, torch, json; print(json.dumps({'python': sys.version.split()[0], "
                           "'torch': torch.__version__, 'cuda': torch.version.cuda, "
                           "'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"],
                          capture_output=True, text=True).stdout
    body = {
        "schema_version": SCHEMA,
        "document": {"path": a.doc.as_posix(), "sha256": sha(repo / a.doc)},
        "code": {"files": code, "code_hash": sha_text("".join(f"{p}:{h}\n" for p, h in code.items())),
                 "v3_lock_hash": v3["lock_hash"]},
        "data": {"root_relative": data, "data_hash": sha_text("".join(f"{p}:{h}\n" for p, h in data.items()))},
        "v1_sources": {"n_files": len(v1), "bundle_hash": sha_text("".join(f"{p}:{h}\n" for p, h in sorted(v1.items()))),
                       "files": v1},
        "repos": repos,
        "environment": {"pip_freeze_sha256": sha_text(freeze), "pip_freeze": freeze.splitlines(),
                        "added_since_saved_freeze": sorted(set(freeze.splitlines()) - set(saved.splitlines())),
                        "removed_since_saved_freeze": sorted(set(saved.splitlines()) - set(freeze.splitlines())),
                        **json.loads(info or "{}")},
    }
    return body


def lock_hash(body: dict) -> str:
    return sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def problems(body: dict) -> list:
    out = [f"저장소 {n}: commit 기록과 다름" for n, r in body["repos"].items() if not r["matches_record"]]
    out += [f"저장소 {n}: clone 이 고쳐져 있음 ({r['dirty_lines']} 줄)" for n, r in body["repos"].items() if not r["clean"]]
    if body["environment"]["removed_since_saved_freeze"]:
        out.append(f"venv-i1 에서 저장본의 패키지가 빠지거나 바뀜: {body['environment']['removed_since_saved_freeze']}")
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
        ok_hash = lock_hash(body) == old.get("lock_hash")
        print(json.dumps({"lock_hash_matches": ok_hash, "differing_sections": diffs, "problems": bad}, ensure_ascii=False))
        return 0 if ok_hash and not diffs and not bad else 1
    if a.out.exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {a.out}", file=sys.stderr)
        return 2
    if bad:
        print(json.dumps({"problems": bad}, ensure_ascii=False), file=sys.stderr)
        return 1
    if not a.reason:
        raise SystemExit("--reason 이 필요하다")
    rec = {**body, "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "reason": a.reason,
           "lock_hash": lock_hash(body)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print(json.dumps({"lock_hash": rec["lock_hash"], "code_hash": body["code"]["code_hash"],
                      "data_hash": body["data"]["data_hash"], "v1_bundle": body["v1_sources"]["bundle_hash"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
