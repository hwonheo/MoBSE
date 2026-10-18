"""Step 4: collect the pilot status, timing, disk and QC into one summary.

Reads run_status.tsv (driver), time_*.txt (/usr/bin/time -l), qc.json and
visual_qc.json per subject. Writes pilot_summary.json and pilot_summary.md in
the derivatives root. No labels or classification outputs are read.

Usage: .venv/bin/python -I scripts/ds005270/04_pilot_summary.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def rusage(p: Path) -> dict:
    if not p.exists():
        return {}
    txt = p.read_text()
    out = {}
    m = re.search(r"([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys", txt)
    if m:
        out.update(real_s=float(m.group(1)), user_s=float(m.group(2)), sys_s=float(m.group(3)))
    m = re.search(r"(\d+)\s+maximum resident set size", txt)
    if m:
        out["max_rss_gib"] = round(int(m.group(1)) / 2**30, 3)
    return out


def main() -> int:
    cfg = common.load_config()
    droot = common.REPO / cfg["pilot"]["derivatives_root_rel"]
    wroot = common.REPO / cfg["pilot"]["work_root_rel"]
    status = {}
    st = droot / "run_status.tsv"
    if st.exists():
        with open(st, newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                status.setdefault(r["subject"], []).append(r)
    rows = []
    for sub in cfg["pilot"]["subjects"]:
        d = droot / sub
        qc = json.loads((d / "qc.json").read_text()) if (d / "qc.json").exists() else None
        vis = json.loads((d / "visual_qc.json").read_text()) if (d / "visual_qc.json").exists() else None
        steps = status.get(sub, [])
        latest = {s["step"]: s for s in steps}  # rev4: a rerun step supersedes its failed attempt
        rc_ok = set(latest) >= {"01", "02", "03"} and all(latest[k]["rc"] == "0" for k in ("01", "02", "03"))
        row = {
            "subject": sub, "order": cfg["pilot"]["orders"][sub], "pipeline_rc_ok": rc_ok,
            "steps": [{k: s.get(k) for k in ("step", "rc", "start_kst", "seconds", "work_kib", "omp", "lock")}
                      for s in steps],
            "sswarper2": rusage(wroot / sub / "anat" / "time_sswarper2.txt"),
            "afni_proc": rusage(wroot / sub / "func" / "time_proc.txt"),
        }
        if qc:
            row.update(
                mean_fd=qc["Q2_motion"]["mean_fd_mm"], frac_fd_gt_0p5=qc["Q2_motion"]["fraction_fd_gt_0p5"],
                n_spikes=qc["Q2_motion"]["n_spikes"],
                windows_main={c: v["n_kept"] for c, v in qc["Q3_windows"]["main"].items()},
                windows_sens={c: v["n_kept"] for c, v in qc["Q3_windows"]["sensitivity"].items()},
                check_flip_prefers_flip=qc["Q4_registration"]["check_flip"]["prefers_flip"],
                r_anat_template=qc["Q4_registration"]["r_anat_template"],
                r_epi_template=qc["Q4_registration"]["r_epi_template"],
                dice_epi_template=qc["Q4_registration"]["dice_epi_mask_template_mask"],
                min_roi_coverage=qc["Q5_roi"]["min_coverage"],
                n_roi_cov_lt_0p90=qc["Q5_roi"]["n_roi_coverage_lt_0p90"],
                rois_cov_lt_0p90=qc["Q5_roi"]["rois_coverage_lt_0p90"],
                wm_voxels=qc["Q6_nuisance"]["wm_voxels"], csf_voxels=qc["Q6_nuisance"]["csf_voxels"],
                dvars_median=qc["Q7_descriptive"]["dvars_median"], tsnr_median=qc["Q7_descriptive"]["tsnr_median_mask"],
                roi_tsnr_min=qc["Q7_descriptive"]["roi_tsnr_min"],
                vol0_ratio=qc["Q7_descriptive"]["vol0_over_median_global"],
                auto_failures=qc["auto_failures"], auto_pass=qc["auto_pass"])
        row["visual_pass"] = vis.get("pass") if vis else None
        row["visual_notes"] = vis.get("notes") if vis else None
        row["qc_pass"] = bool(qc and qc["auto_pass"] and vis and vis.get("pass"))
        rows.append(row)
    n = len(rows)
    summary = {
        "protocol_version": cfg["protocol_version"],
        "n_subjects": n,
        "n_pipeline_ok": sum(r["pipeline_rc_ok"] for r in rows),
        "n_auto_pass": sum(bool(r.get("auto_pass")) for r in rows),
        "n_visual_pass": sum(bool(r.get("visual_pass")) for r in rows),
        "n_qc_pass": sum(r["qc_pass"] for r in rows),
        "subjects": rows,
    }
    common.write_json(droot / "pilot_summary.json", summary)
    lines = ["| subject | order | rc | sswarper2 min | proc min | max RSS GiB | mean FD | FD>0.5 | windows main | flip | r anat | r EPI | min cov | ROI<0.90 | tSNR | auto | visual |",
             "|---|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in rows:
        rss = max([x.get("max_rss_gib", 0) for x in (r["sswarper2"], r["afni_proc"])] or [0])
        lines.append("| {s} | {o} | {rc} | {a} | {b} | {rss} | {fd} | {ff} | {w} | {fl} | {ra} | {re} | {mc} | {nl} | {ts} | {ap} | {vp} |".format(
            s=r["subject"], o=r["order"], rc="ok" if r["pipeline_rc_ok"] else "FAIL",
            a=round(r["sswarper2"].get("real_s", float("nan")) / 60, 1), b=round(r["afni_proc"].get("real_s", float("nan")) / 60, 1),
            rss=rss, fd=f"{r.get('mean_fd', float('nan')):.3f}", ff=f"{r.get('frac_fd_gt_0p5', float('nan')):.3f}",
            w=",".join(str(v) for v in r.get("windows_main", {}).values()), fl=r.get("check_flip_prefers_flip"),
            ra=f"{r.get('r_anat_template', float('nan')):.3f}", re=f"{r.get('r_epi_template', float('nan')):.3f}",
            mc=f"{r.get('min_roi_coverage', float('nan')):.3f}", nl=r.get("n_roi_cov_lt_0p90"),
            ts=f"{r.get('tsnr_median', float('nan')):.1f}", ap=r.get("auto_pass"), vp=r.get("visual_pass")))
    (droot / "pilot_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
