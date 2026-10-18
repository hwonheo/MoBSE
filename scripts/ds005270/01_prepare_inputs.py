"""Step 1: verify one subject's pilot inputs and fix the window table.

Checks input sha256 against the download verification record, the BOLD header
(TR, volume count), and the n-back events (3 complete conditions). Writes the
slice-timing file for 3dTshift and the window table (main and sensitivity).
Reads only; the raw dataset is never modified.

Usage: .venv/bin/python -I scripts/ds005270/01_prepare_inputs.py sub-001
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

import nibabel as nib  # noqa: E402

EXPECTED_ROWS = {"ZeroBack": 98, "OneBack": 98, "TwoBack": 98}


def main(sub: str) -> int:
    cfg = common.load_config()
    if sub not in cfg["pilot"]["subjects"]:
        print(f"{sub} is not a locked pilot subject", file=sys.stderr)
        return 2
    raw = common.raw_root(cfg)
    work = common.work_dir(cfg, sub)
    deriv = common.deriv_dir(cfg, sub)
    (work / "inputs").mkdir(parents=True, exist_ok=True)
    deriv.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    ver = json.loads((common.REPO / cfg["dataset"]["download_verification_rel"]).read_text())
    ver_map = {f["path"]: f for f in ver["files"]}
    hashes = {}
    for rel in common.input_rel_paths(cfg, sub):
        p = raw / sub / rel
        key = f"{sub}/{rel}"
        if not p.exists():
            failures.append(f"missing {key}")
            continue
        h = common.sha256_file(p)
        ref = ver_map.get(key, {}).get("sha256")
        hashes[key] = {"sha256": h, "matches_download_verification": h == ref, "bytes": p.stat().st_size}
        if h != ref:
            failures.append(f"sha256 mismatch {key}")

    bold_p = raw / sub / "func" / f"{sub}_task-nbk_bold.nii.gz"
    t1_p = raw / sub / "anat" / f"{sub}_T1w.nii.gz"
    bold = nib.load(bold_p)
    t1 = nib.load(t1_p)
    tr = float(bold.header.get_zooms()[3])
    nvol = int(bold.shape[3])
    if abs(tr - cfg["windows"]["tr_s"]) > 1e-6:
        failures.append(f"TR {tr}")
    if nvol != cfg["windows"]["n_volumes"]:
        failures.append(f"volumes {nvol}")

    sidecar = json.loads((raw / sub / "func" / f"{sub}_task-nbk_bold.json").read_text())
    st = sidecar["SliceTiming"]
    if len(st) != bold.shape[2]:
        failures.append(f"SliceTiming length {len(st)} vs slices {bold.shape[2]}")
    if abs(float(sidecar["RepetitionTime"]) - tr) > 1e-6:
        failures.append("JSON TR differs from header TR")
    if not all(0 <= t < tr for t in st):
        failures.append("SliceTiming outside [0, TR)")
    (work / "inputs" / "slice_times.1D").write_text(" ".join(f"{t:.4f}" for t in st) + "\n")

    with open(raw / sub / "func" / f"{sub}_task-nbk_events.tsv", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_cond: dict[str, list[dict]] = {}
    for r in rows:
        by_cond.setdefault(r["trial_type"].split("_")[0], []).append(r)
    counts = {c: len(v) for c, v in by_cond.items()}
    if counts != EXPECTED_ROWS:
        failures.append(f"event rows per condition {counts}")

    w = cfg["windows"]
    windows = {}
    for cond in cfg["task"]["conditions"]:
        rs = by_cond.get(cond, [])
        if not rs:
            continue
        B = min(float(r["onset"]) for r in rs)
        E = max(float(r["onset"]) + float(r["duration"]) for r in rs)
        entry = {"label": cfg["task"]["labels"][cond], "B_s": B, "E_s": E}
        for name in ("main", "sensitivity"):
            entry[name] = common.window_starts(
                B, E, w[name]["start_buffer_s"], w[name]["end_buffer_s"],
                w["tr_s"], w["n_windows_per_condition"], w["window_s"])
            last = entry[name]["first_volume"][-1] + w["frames_per_window"] - 1
            if not entry[name]["fits"] or last >= nvol:
                failures.append(f"{cond} {name} windows do not fit")
        windows[cond] = entry
    order = ">".join(sorted(windows, key=lambda c: windows[c]["B_s"]))
    if order != cfg["pilot"]["orders"][sub]:
        failures.append(f"order {order} differs from locked {cfg['pilot']['orders'][sub]}")

    common.write_json(deriv / "windows.json", {
        "subject": sub, "order": order, "tr_s": tr, "n_volumes": nvol,
        "time_origin": w["time_origin"], "conditions": windows})
    common.write_json(deriv / "prep_check.json", {
        "subject": sub,
        "inputs": hashes,
        "bold_shape": list(bold.shape), "bold_zooms": [float(z) for z in bold.header.get_zooms()],
        "t1_shape": list(t1.shape), "t1_zooms": [float(z) for z in t1.header.get_zooms()],
        "slice_timing_n": len(st), "event_rows": counts, "order": order,
        "failures": failures, "pass": not failures})
    print(json.dumps({"subject": sub, "order": order, "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
