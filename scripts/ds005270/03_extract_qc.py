"""Step 3: ROI extraction, nuisance regression and QC for one pilot subject.

Reads the afni_proc results (volreg output on the atlas 2 mm grid, masks,
motion file) and writes to the derivatives folder:
  roi_raw.npy (266 x 100, ROI mean signal), roi_clean.npy (266 x 100,
  PSC residual after the 28-column nuisance model), nuisance.npy, fd.tsv,
  qc.json, qc/*.png. No labels are used; no features or models are computed.

Usage: .venv/bin/python -I scripts/ds005270/03_extract_qc.py sub-001
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import nibabel as nib  # noqa: E402
import numpy as np  # noqa: E402

TEMPLATE = "/Users/hwon/abin/MNI152_2009_template_SSW.nii.gz"


def load(p: Path):
    img = nib.load(str(p))
    return img, np.asanyarray(img.dataobj)


def power_fd(dfile: np.ndarray) -> np.ndarray:
    """dfile columns: roll, pitch, yaw (deg), dS, dL, dP (mm)."""
    rot = np.deg2rad(dfile[:, :3]) * 50.0
    params = np.column_stack([rot, dfile[:, 3:6]])
    fd = np.zeros(len(params))
    fd[1:] = np.abs(np.diff(params, axis=0)).sum(axis=1)
    return fd


def psc(x: np.ndarray) -> np.ndarray:
    m = x.mean(axis=0)
    return 100.0 * (x / m - 1.0)


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


def montage(bg, contours, path: Path, title: str, overlay=None) -> None:
    """3 x 4 grid of axial / coronal / sagittal slices with contour lines."""
    fig, axes = plt.subplots(3, 4, figsize=(12, 9))
    shape = bg.shape
    for row, axis in enumerate((2, 1, 0)):
        idx = np.linspace(0.25, 0.75, 4) * shape[axis]
        for col, i in enumerate(idx.astype(int)):
            sl = [slice(None)] * 3
            sl[axis] = i
            ax = axes[row, col]
            ax.imshow(np.rot90(bg[tuple(sl)]), cmap="gray",
                      vmin=np.percentile(bg[bg > 0], 2) if (bg > 0).any() else 0,
                      vmax=np.percentile(bg[bg > 0], 98) if (bg > 0).any() else 1)
            if overlay is not None:
                ov = np.rot90(overlay[tuple(sl)]).astype(float)
                ax.imshow(np.ma.masked_where(ov == 0, ov), cmap="autumn", alpha=0.6)
            for vol, level, color in contours:
                ax.contour(np.rot90(vol[tuple(sl)]), levels=[level], colors=color, linewidths=0.6)
            ax.set_axis_off()
            ax.set_title(f"{'zyx'[row]}={i}", fontsize=8)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=80)
    plt.close(fig)


def main(sub: str) -> int:
    cfg = common.load_config()
    q = cfg["qc"]
    res = common.work_dir(cfg, sub) / "func" / f"{sub}.results"
    deriv = common.deriv_dir(cfg, sub)
    ref = common.REPO / cfg["pilot"]["derivatives_root_rel"] / "reference"
    failures: list[str] = []

    atlas_img, atlas = load(ref / "atlas_grid_master.nii.gz")
    atlas = atlas.astype(np.int64)
    vol_img, vol = load(res / f"pb02.{sub}.r01.volreg+tlrc.HEAD")
    vol = vol.astype(np.float32)
    if vol.shape[:3] != atlas.shape or not np.allclose(vol_img.affine, atlas_img.affine):
        print("volreg grid differs from the atlas grid", file=sys.stderr)
        return 1
    nvol = vol.shape[3]
    full = load(res / f"full_mask.{sub}+tlrc.HEAD")[1].squeeze() > 0
    extents = load(res / "mask_epi_extents+tlrc.HEAD")[1].squeeze() > 0
    wme = load(res / "mask_WMe_resam+tlrc.HEAD")[1].squeeze() > 0
    csfe = load(res / "mask_CSFe_resam+tlrc.HEAD")[1].squeeze() > 0
    tpl_mask = load(ref / "tpl_bmask_2mm.nii.gz")[1].squeeze() > 0
    tpl_brain = load(ref / "tpl_brain_2mm.nii.gz")[1].squeeze().astype(float)

    # ---- ROI extraction and coverage --------------------------------------
    labels = np.arange(1, cfg["features_spec_not_executed"]["rois"] + 1)
    roi_raw = np.full((nvol, len(labels)), np.nan)
    coverage, fov_cov, nvox = [], [], []
    for j, r in enumerate(labels):
        in_roi = atlas == r
        n = int(in_roi.sum())
        use = in_roi & full
        nvox.append(int(use.sum()))
        coverage.append(use.sum() / n)
        fov_cov.append((in_roi & extents).sum() / n)
        if use.any():
            roi_raw[:, j] = vol[use].mean(axis=0)
    coverage = np.array(coverage)
    fov_cov = np.array(fov_cov)
    low_cov = [int(labels[j]) for j in np.where(coverage < q["Q5_roi"]["fail_if_any_roi_coverage_lt"])[0]]
    raw_ok = bool(np.isfinite(roi_raw).all() and (roi_raw.std(axis=0) > 0).all())
    if low_cov:
        failures.append(f"Q5 ROI coverage < 0.90 in {len(low_cov)} ROIs")
    if not raw_ok:
        failures.append("Q5 raw ROI series non-finite or zero variance")

    # ---- motion ----------------------------------------------------------
    dfile = np.loadtxt(res / "dfile_rall.1D")
    if dfile.shape != (nvol, 6):
        print(f"dfile shape {dfile.shape}", file=sys.stderr)
        return 1
    fd = power_fd(dfile)
    mean_fd = float(fd[1:].mean())
    frac_fd = float((fd[1:] > 0.5).mean())
    spikes = np.where(fd > 0.5)[0]
    flagged = sorted({int(t + d) for t in spikes for d in (-1, 0, 1) if 0 <= t + d < nvol})
    if mean_fd > q["Q2_motion"]["exclude_if_mean_fd_gt_mm"]:
        failures.append(f"Q2 mean FD {mean_fd:.3f} > 0.3")
    if frac_fd > q["Q2_motion"]["exclude_if_fraction_fd_gt_0p5_mm_exceeds"]:
        failures.append(f"Q2 FD>0.5 fraction {frac_fd:.3f} > 0.20")

    # ---- windows ---------------------------------------------------------
    win = json.loads((deriv / "windows.json").read_text())
    F = cfg["windows"]["frames_per_window"]
    retention = {}
    for name in ("main", "sensitivity"):
        retention[name] = {}
        for cond, e in win["conditions"].items():
            kept = [all(v not in flagged for v in range(s, s + F)) for s in e[name]["first_volume"]]
            retention[name][cond] = {"kept": kept, "n_kept": int(sum(kept))}
    main_ok = all(v["n_kept"] >= q["Q3_windows"]["min_windows_per_condition"] for v in retention["main"].values())
    if not main_ok:
        failures.append("Q3 fewer than 3 of 4 main windows retained in a condition")

    # ---- nuisance regression --------------------------------------------
    wm_use, csf_use = wme & full, csfe & full
    wm_ts = vol[wm_use].mean(axis=0) if wm_use.any() else np.full(nvol, np.nan)
    csf_ts = vol[csf_use].mean(axis=0) if csf_use.any() else np.full(nvol, np.nan)
    nuis_ok = bool(wm_use.any() and csf_use.any() and np.isfinite(wm_ts).all() and np.isfinite(csf_ts).all()
                   and wm_ts.std() > 0 and csf_ts.std() > 0)
    if not nuis_ok:
        failures.append("Q6 WM/CSF nuisance series unusable")
    mot = dfile
    dmot = np.vstack([np.zeros((1, 6)), np.diff(mot, axis=0)])
    t = np.arange(nvol, dtype=float)
    X = np.column_stack([np.ones(nvol), (t - t.mean()) / t.std(), mot, dmot, mot ** 2, dmot ** 2,
                         psc(wm_ts[:, None])[:, 0], psc(csf_ts[:, None])[:, 0]])
    rank = int(np.linalg.matrix_rank(X))
    cond_no = float(np.linalg.cond((X - 0) / np.where(X.std(0) > 0, X.std(0), 1)))
    Y = psc(roi_raw)
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    clean = Y - X @ beta
    clean_ok = bool(np.isfinite(clean).all() and (clean.std(axis=0) > 0).all())
    if rank != X.shape[1]:
        failures.append(f"nuisance design rank {rank} < {X.shape[1]}")
    if not clean_ok:
        failures.append("Q5 cleaned ROI series non-finite or zero variance")

    # ---- descriptive: DVARS, tSNR, steady state -------------------------
    V = vol[full].astype(np.float64)
    vm = V.mean(axis=1)
    good = vm > 0
    P = 100.0 * V[good] / vm[good, None]
    dvars = np.sqrt((np.diff(P, axis=1) ** 2).mean(axis=0))
    tt = np.column_stack([np.ones(nvol), t])
    b, *_ = np.linalg.lstsq(tt, V.T, rcond=None)
    resid_sd = (V.T - tt @ b).std(axis=0, ddof=2)
    tsnr_vox = np.where(resid_sd > 0, vm / np.where(resid_sd > 0, resid_sd, 1), 0)
    tsnr_img = np.zeros(atlas.shape)
    tsnr_img[full] = tsnr_vox
    roi_tsnr = np.array([np.median(tsnr_img[(atlas == r) & full]) if ((atlas == r) & full).any() else np.nan
                         for r in labels])
    gm = V.mean(axis=0)
    del V, P

    # ---- registration numbers --------------------------------------------
    anat_img, anat = load(res / f"anat_final.{sub}+tlrc.HEAD")
    tpl_img = nib.load(TEMPLATE)
    # rev4 fix: the SSW template is stored 5D (x, y, z, 1, 5); index the last axis
    tpl_arr = np.asanyarray(tpl_img.dataobj)
    tpl_arr = tpl_arr.reshape(tpl_arr.shape[:3] + (-1,))
    tpl0 = tpl_arr[..., 0].astype(float)
    tplm1 = tpl_arr[..., 3] > 0
    anat = anat.squeeze().astype(float)
    r_anat = pearson(anat[tplm1], tpl0[tplm1]) if anat.shape == tpl0.shape else float("nan")
    epi_base = load(res / "final_epi_vr_base_min_outlier+tlrc.HEAD")[1].squeeze().astype(float)
    r_epi = pearson(epi_base[tpl_mask], tpl_brain[tpl_mask])
    dice = float(2 * (full & tpl_mask).sum() / (full.sum() + tpl_mask.sum()))
    flip = {"file": None, "text": None, "prefers_flip": None}
    for cand in sorted(res.glob("aea_checkflip*.txt")):
        txt = cand.read_text()
        flip["file"], flip["text"] = cand.name, txt.strip()[:2000]
        m = re.search(r"flip_guess\s*:\s*(\S+)", txt)
        if m:
            flip["prefers_flip"] = m.group(1).upper() != "NO_FLIP"
    if flip["prefers_flip"] is None:
        failures.append("Q4 check_flip result not found")
    elif flip["prefers_flip"]:
        failures.append("Q4 check_flip prefers the flipped EPI")
    ae_dice = None
    p = res / "out.mask_ae_dice.txt"
    if p.exists():
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", p.read_text())
        ae_dice = float(nums[-1]) if nums else None

    # ---- outputs -----------------------------------------------------------
    deriv.mkdir(parents=True, exist_ok=True)
    np.save(deriv / "roi_raw.npy", roi_raw)
    np.save(deriv / "roi_clean.npy", clean)
    np.save(deriv / "nuisance.npy", X)
    with open(deriv / "fd.tsv", "w") as f:
        f.write("volume\tfd_mm\tflagged\n")
        for i, v in enumerate(fd):
            f.write(f"{i}\t{v:.6f}\t{int(i in flagged)}\n")
    qcdir = deriv / "qc"
    tplm1f = tplm1.astype(float)
    wm_level = float(np.percentile(tpl0[tplm1], 75))
    montage(anat, [(tplm1f, 0.5, "r"), (tpl0, wm_level, "c")], qcdir / "anat_on_template.png",
            f"{sub} anatQQ (gray); template brain edge (red), template WM iso-line (cyan)")
    montage(epi_base, [(tpl_mask.astype(float), 0.5, "r"), (tpl_brain, float(np.percentile(tpl_brain[tpl_mask], 75)), "c")],
            qcdir / "epi_on_template.png",
            f"{sub} EPI base in template space (gray); template brain edge (red), WM iso-line (cyan)")
    cov_img = np.zeros(atlas.shape)
    for j, r in enumerate(labels):
        cov_img[atlas == r] = 2 if coverage[j] < 0.9 else 1
    montage(epi_base, [(full.astype(float), 0.5, "lime")], qcdir / "coverage.png",
            f"{sub} EPI full_mask (green); atlas ROIs with coverage < 0.90 (red/orange)",
            overlay=np.where(cov_img == 2, 1, 0))
    fig, ax = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    ax[0].plot(fd, lw=0.8)
    ax[0].axhline(0.5, color="r", lw=0.6)
    for cond, e in win["conditions"].items():
        for s in e["main"]["first_volume"]:
            ax[0].axvspan(s, s + F - 1, alpha=0.12, color="g")
    ax[0].set_ylabel("FD mm")
    ax[1].plot(np.r_[np.nan, dvars], lw=0.8)
    ax[1].set_ylabel("DVARS %")
    ax[1].set_xlabel("volume")
    fig.suptitle(f"{sub} motion (green = main windows, label-blind)")
    fig.tight_layout()
    fig.savefig(qcdir / "motion.png", dpi=80)
    plt.close(fig)

    qc = {
        "subject": sub, "order": win["order"], "n_volumes": nvol,
        "Q2_motion": {"mean_fd_mm": mean_fd, "max_fd_mm": float(fd.max()), "fraction_fd_gt_0p5": frac_fd,
                      "n_spikes": int(len(spikes)), "n_flagged_volumes": len(flagged)},
        "Q3_windows": {"main": retention["main"], "sensitivity": retention["sensitivity"], "main_pass": main_ok},
        "Q4_registration": {"check_flip": flip, "r_anat_template": r_anat, "r_epi_template": r_epi,
                            "dice_epi_mask_template_mask": dice, "dice_epi_anat_mask_afni": ae_dice,
                            "visual": "pending (recorded separately in visual_qc.json)"},
        "Q5_roi": {"min_coverage": float(coverage.min()), "n_roi_coverage_lt_0p90": len(low_cov),
                   "rois_coverage_lt_0p90": low_cov, "min_fov_coverage": float(fov_cov.min()),
                   "coverage": [round(float(c), 4) for c in coverage], "voxels_used_min": int(min(nvox)),
                   "raw_finite_nonzero_var": raw_ok, "clean_finite_nonzero_var": clean_ok},
        "Q6_nuisance": {"wm_voxels": int(wm_use.sum()), "csf_voxels": int(csf_use.sum()), "usable": nuis_ok,
                        "design_columns": int(X.shape[1]), "design_rank": rank,
                        "design_condition_number_scaled": cond_no},
        "Q7_descriptive": {"dvars_median": float(np.median(dvars)), "dvars_p95": float(np.percentile(dvars, 95)),
                           "dvars_max": float(dvars.max()), "tsnr_median_mask": float(np.median(tsnr_vox)),
                           "roi_tsnr_median": float(np.nanmedian(roi_tsnr)), "roi_tsnr_min": float(np.nanmin(roi_tsnr)),
                           "vol0_over_median_global": float(gm[0] / np.median(gm)),
                           "vol1_over_median_global": float(gm[1] / np.median(gm)),
                           "full_mask_voxels": int(full.sum())},
        "auto_failures": failures, "auto_pass": not failures,
        "outputs_sha256": {p.name: common.sha256_file(p) for p in sorted(deriv.glob("*.npy"))},
    }
    common.write_json(deriv / "qc.json", qc)
    print(json.dumps({"subject": sub, "auto_pass": not failures, "failures": failures,
                      "mean_fd": round(mean_fd, 3), "min_cov": round(float(coverage.min()), 3)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
