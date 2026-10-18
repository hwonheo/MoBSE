"""Build or verify the ds005270 preprocessing pilot lock.

The lock hashes the protocol config, lock document, pilot scripts, atlas,
template, the six subjects' input files, and records tool versions. --verify
recomputes everything and exits 1 on any difference (run_pilot.sh calls it
before each subject).

Usage: .venv/bin/python -I scripts/ds005270/build_lock.py [--verify]
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

DOC = common.REPO / "docs" / "experiments" / "ds005270_protocol_lock_v1_2026-10-17.md"
SCRIPTS = ["common.py", "00_reference.py", "01_prepare_inputs.py", "02_afni_subject.sh",
           "03_extract_qc.py", "04_pilot_summary.py", "build_lock.py", "run_pilot.sh",
           "no_snapshot_bin/@chauffeur_afni", "no_snapshot_bin/@snapshot_volreg"]
TEMPLATE = Path("/Users/hwon/abin/MNI152_2009_template_SSW.nii.gz")


def tool_versions() -> dict:
    def out(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[0]
        except Exception as exc:  # noqa: BLE001
            return f"unavailable: {exc}"
    import matplotlib, nibabel, nilearn, numpy, scipy, sklearn  # noqa: E401
    return {
        "afni": out(["/Users/hwon/abin/afni", "-ver"]),
        "afni_proc": out(["/Users/hwon/abin/afni_proc.py", "-ver"]),
        "python_venv": sys.version.split()[0],
        "nibabel": nibabel.__version__, "nilearn": nilearn.__version__, "numpy": numpy.__version__,
        "scipy": scipy.__version__, "matplotlib": matplotlib.__version__, "sklearn": sklearn.__version__,
    }


def content() -> dict:
    cfg = common.load_config()
    raw = common.raw_root(cfg)
    inputs = {}
    for sub in cfg["pilot"]["subjects"]:
        for rel in common.input_rel_paths(cfg, sub):
            inputs[f"{sub}/{rel}"] = common.sha256_file(raw / sub / rel)
    here = Path(__file__).resolve().parent
    return {
        "lock_name": "ds005270_preproc_pilot_lock_v1",
        "protocol_version": cfg["protocol_version"],
        "config": {"path": str(common.CONFIG_PATH.relative_to(common.REPO)), "sha256": common.sha256_file(common.CONFIG_PATH)},
        "document": {"path": str(DOC.relative_to(common.REPO)), "sha256": common.sha256_file(DOC)},
        "scripts": {f"scripts/ds005270/{s}": common.sha256_file(here / s) for s in SCRIPTS},
        "atlas_sha256": common.sha256_file(common.REPO / cfg["preprocessing"]["atlas"]["file_rel"]),
        "atlas_lut_sha256": common.sha256_file(common.REPO / cfg["preprocessing"]["atlas"]["lut_rel"]),
        "template_sha256": common.sha256_file(TEMPLATE),
        "inputs_sha256": inputs,
        "tools": tool_versions(),
    }


def digest(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def main() -> int:
    now = content()
    if "--verify" in sys.argv:
        lock = json.loads(common.LOCK_PATH.read_text())
        old = lock["content"]
        if digest(old) != lock["lock_hash"]:
            print("lock file content does not match its lock_hash", file=sys.stderr)
            return 1
        if digest(now) != lock["lock_hash"]:
            diff = [k for k in now if now[k] != old.get(k)]
            print(f"lock mismatch in: {diff}", file=sys.stderr)
            return 1
        print(f"lock ok {lock['lock_hash'][:12]}")
        return 0
    if common.LOCK_PATH.exists() and "--overwrite" not in sys.argv:
        print("lock exists; refusing to overwrite", file=sys.stderr)
        return 1
    import datetime as dt
    lock = {"locked_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lock_hash": digest(now), "content": now}
    common.write_json(common.LOCK_PATH, lock)
    print(f"lock written {lock['lock_hash'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
