"""25_verify_window_files.py 자기시험 — 네 가지 결함을 각각 실제로 잡는가."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "verify_window_files",
    Path(__file__).resolve().parents[2] / "scripts/h197/25_verify_window_files.py")
G = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(G)  # type: ignore[union-attr]


def _write(p: Path, data: bytes) -> str:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _manifest(path: Path, runs: List[Dict[str, Any]]) -> None:
    lines = [{"record_type": "header"}] + [{"record_type": "run", **r} for r in runs]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def _lock(root: Path, tmp: Path) -> Path:
    lock = {"lock_hash": "0" * 64,
            "cohorts": {"c": {"manifests": {"t": {"path": "m.jsonl"}}}}}
    p = tmp / "lock.json"
    p.write_text(json.dumps(lock), encoding="utf-8")
    return p


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "data"
    r.mkdir()
    return r


def test_clean_passes(root: Path, tmp_path: Path) -> None:
    s = _write(root / "a.npy", b"a")
    _manifest(root / "m.jsonl", [{"status": "ok", "run_key": "r",
                                  "windows": [{"path": str(root / "a.npy"), "sha256": s}]}])
    assert G.main(["--data-root", str(root), "--lock", str(_lock(root, tmp_path))]) == 0


@pytest.mark.parametrize("kind", ["outside_root", "missing", "mismatch", "empty_ok_run"])
def test_each_defect_fails(kind: str, root: Path, tmp_path: Path) -> None:
    s = _write(root / "a.npy", b"a")
    outside = tmp_path / "volatile" / "a.npy"
    s_out = _write(outside, b"a")
    windows = {
        "outside_root": [{"path": str(outside), "sha256": s_out}],
        "missing": [{"path": str(root / "gone.npy"), "sha256": s}],
        "mismatch": [{"path": str(root / "a.npy"), "sha256": "f" * 64}],
        "empty_ok_run": [],
    }[kind]
    _manifest(root / "m.jsonl", [{"status": "ok", "run_key": "r", "windows": windows}])
    res = G.check_manifest(root / "m.jsonl", root)
    assert res[kind] >= 1
    assert G.main(["--data-root", str(root), "--lock", str(_lock(root, tmp_path))]) == 1


def test_non_ok_runs_ignored(root: Path, tmp_path: Path) -> None:
    s = _write(root / "a.npy", b"a")
    _manifest(root / "m.jsonl", [
        {"status": "ok", "run_key": "r1", "windows": [{"path": str(root / "a.npy"), "sha256": s}]},
        {"status": "excluded", "run_key": "r2", "windows": []}])
    assert G.main(["--data-root", str(root), "--lock", str(_lock(root, tmp_path))]) == 0


def test_lock_without_manifests_rejected() -> None:
    with pytest.raises(ValueError):
        G.manifests_from_lock({"cohorts": {}})
