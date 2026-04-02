from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
from nilearn.connectome import ConnectivityMeasure
from nilearn.datasets import fetch_atlas_msdl, fetch_atlas_schaefer_2018
from nilearn.decomposition import CanICA, DictLearning
from nilearn.image import mean_img
from nilearn.maskers import NiftiLabelsMasker, NiftiMapsMasker, NiftiMasker, NiftiSpheresMasker
from nilearn.plotting import plot_connectome, plot_prob_atlas, plot_stat_map
from nilearn.regions import RegionExtractor

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)


def _collect_subject_runs(fmriprep_root: Path, max_subjects: int) -> List[Dict[str, Path]]:
    records: List[Dict[str, Path]] = []
    for sub_dir in sorted(p for p in fmriprep_root.glob("sub-*") if p.is_dir()):
        func_dir = sub_dir / "func"
        bolds = sorted(func_dir.glob("*_desc-preproc_bold.nii.gz"))
        if not bolds:
            continue
        bold = bolds[0]
        prefix = bold.name.split("_space-")[0]
        conf = next(iter(sorted(func_dir.glob(prefix + "*desc-confounds_timeseries.tsv"))), None)
        records.append(
            {
                "subject_id": sub_dir.name,
                "bold_path": bold,
                "confounds_path": conf if conf is not None else Path(""),
            }
        )
        if len(records) >= max_subjects:
            break
    if not records:
        raise RuntimeError(f"No preproc BOLD found under {fmriprep_root}")
    return records


def _load_numeric_confounds(path: Path, n_scans: int) -> np.ndarray | None:
    if not path or not path.exists():
        return None
    df = pd.read_csv(path, sep="\t")
    num = df.apply(pd.to_numeric, errors="coerce")
    num = num.loc[:, num.notna().any(axis=0)]
    if num.shape[1] == 0:
        return None
    arr = np.nan_to_num(num.to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if arr.shape[0] > n_scans:
        arr = arr[:n_scans]
    elif arr.shape[0] < n_scans:
        pad = np.zeros((n_scans - arr.shape[0], arr.shape[1]), dtype=np.float32)
        arr = np.vstack([arr, pad])
    return arr


def _subject_timeseries_schaefer(records: List[Dict[str, Path]], n_rois: int = 100) -> Tuple[List[np.ndarray], object]:
    atlas = fetch_atlas_schaefer_2018(n_rois=n_rois)
    ts_list: List[np.ndarray] = []
    for rec in records:
        n_scans = int(nib.load(str(rec["bold_path"])).shape[-1])
        conf = _load_numeric_confounds(rec["confounds_path"], n_scans=n_scans)
        tr = float(nib.load(str(rec["bold_path"])).header.get_zooms()[3])
        masker = NiftiLabelsMasker(
            labels_img=atlas.maps,
            standardize="zscore_sample",
            detrend=True,
            high_pass=0.008,
            low_pass=0.1,
            t_r=tr,
        )
        ts = masker.fit_transform(str(rec["bold_path"]), confounds=conf)
        ts_list.append(ts)
    return ts_list, atlas


def _signal_extraction_step(records: List[Dict[str, Path]], out_dir: Path) -> Dict[str, str]:
    ts_list, atlas = _subject_timeseries_schaefer(records, n_rois=100)
    rows = []
    for rec, ts in zip(records, ts_list):
        rows.append(
            {
                "subject_id": rec["subject_id"],
                "n_timepoints": int(ts.shape[0]),
                "n_rois": int(ts.shape[1]),
                "mean_abs_signal": float(np.mean(np.abs(ts))),
                "std_signal": float(np.std(ts)),
            }
        )
    df = pd.DataFrame(rows)
    csv_path = out_dir / "signal_extraction_summary.csv"
    df.to_csv(csv_path, index=False)

    fig_path = out_dir / "signal_extraction_subject0_timeseries.png"
    plt.figure(figsize=(10, 3))
    plt.plot(ts_list[0][:, :10], linewidth=0.6)
    plt.title("Subject0 Schaefer-100 ROI Signals (first 10 ROIs)")
    plt.xlabel("time")
    plt.ylabel("z-score")
    plt.tight_layout()
    plt.savefig(fig_path, dpi=150)
    plt.close()

    return {"summary_csv": str(csv_path), "timeseries_plot": str(fig_path), "atlas_map": str(atlas.maps)}


def _probabilistic_atlas_step(records: List[Dict[str, Path]], out_dir: Path) -> Dict[str, str]:
    atlas = fetch_atlas_msdl()
    tr = float(nib.load(str(records[0]["bold_path"])).header.get_zooms()[3])
    maps_masker = NiftiMapsMasker(
        maps_img=atlas.maps,
        standardize="zscore_sample",
        detrend=True,
        high_pass=0.008,
        low_pass=0.1,
        t_r=tr,
    )

    rows = []
    for rec in records:
        n_scans = int(nib.load(str(rec["bold_path"])).shape[-1])
        conf = _load_numeric_confounds(rec["confounds_path"], n_scans=n_scans)
        ts = maps_masker.fit_transform(str(rec["bold_path"]), confounds=conf)
        rows.append(
            {
                "subject_id": rec["subject_id"],
                "n_timepoints": int(ts.shape[0]),
                "n_maps": int(ts.shape[1]),
                "mean_abs_signal": float(np.mean(np.abs(ts))),
            }
        )

    csv_path = out_dir / "probabilistic_atlas_extraction_summary.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    fig = plt.figure(figsize=(8, 4))
    display = plot_prob_atlas(atlas.maps, title="MSDL probabilistic atlas")
    fig_path = out_dir / "probabilistic_atlas_maps.png"
    display.savefig(fig_path)
    display.close()
    plt.close(fig)

    return {"summary_csv": str(csv_path), "atlas_plot": str(fig_path), "atlas_maps": str(atlas.maps)}


def _inverse_covariance_step(records: List[Dict[str, Path]], out_dir: Path) -> Dict[str, str]:
    ts_list, atlas = _subject_timeseries_schaefer(records, n_rois=100)
    conn = ConnectivityMeasure(kind="partial correlation", standardize="zscore_sample")
    mats = conn.fit_transform(ts_list)
    group_mat = np.mean(np.stack(mats, axis=0), axis=0)
    np.fill_diagonal(group_mat, 0.0)

    mat_path = out_dir / "inverse_covariance_group_matrix.npy"
    np.save(mat_path, group_mat)

    # approximate node coordinates using atlas labels centers is not directly available; use evenly sampled coords for plotting
    n = group_mat.shape[0]
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    coords = np.c_[40 * np.cos(angles), 40 * np.sin(angles), np.zeros(n)]
    fig = plt.figure(figsize=(8, 6))
    display = plot_connectome(group_mat, coords, title="Group Partial Correlation (Schaefer-100)")
    fig_path = out_dir / "inverse_covariance_connectome.png"
    display.savefig(fig_path)
    display.close()
    plt.close(fig)

    return {"group_matrix_npy": str(mat_path), "connectome_plot": str(fig_path), "atlas_map": str(atlas.maps)}


def _compare_decomposition_step(records: List[Dict[str, Path]], out_dir: Path, n_components: int) -> Dict[str, str]:
    imgs = [str(rec["bold_path"]) for rec in records]
    canica = CanICA(
        n_components=n_components,
        smoothing_fwhm=6.0,
        memory_level=1,
        threshold=2.0,
        random_state=42,
        standardize="zscore_sample",
    )
    canica.fit(imgs)
    canica_maps = canica.components_img_

    dict_learning = DictLearning(
        n_components=n_components,
        smoothing_fwhm=6.0,
        random_state=42,
        memory_level=1,
        n_epochs=1,
        standardize="zscore_sample",
    )
    dict_learning.fit(imgs)
    dict_maps = dict_learning.components_img_

    canica_path = out_dir / "compare_decomposition_canica_components.nii.gz"
    dict_path = out_dir / "compare_decomposition_dictlearning_components.nii.gz"
    canica_maps.to_filename(canica_path)
    dict_maps.to_filename(dict_path)

    mean_canica = mean_img(canica_maps)
    mean_dict = mean_img(dict_maps)
    fig1 = plt.figure(figsize=(8, 4))
    d1 = plot_stat_map(mean_canica, title="CanICA mean component map", colorbar=True)
    fig1_path = out_dir / "compare_decomposition_canica_mean.png"
    d1.savefig(fig1_path)
    d1.close()
    plt.close(fig1)

    fig2 = plt.figure(figsize=(8, 4))
    d2 = plot_stat_map(mean_dict, title="DictLearning mean component map", colorbar=True)
    fig2_path = out_dir / "compare_decomposition_dictlearning_mean.png"
    d2.savefig(fig2_path)
    d2.close()
    plt.close(fig2)

    return {
        "canica_components": str(canica_path),
        "dictlearning_components": str(dict_path),
        "canica_plot": str(fig1_path),
        "dictlearning_plot": str(fig2_path),
    }


def _seed_to_voxel_step(record: Dict[str, Path], out_dir: Path, seed_coords: Tuple[float, float, float]) -> Dict[str, str]:
    bold = str(record["bold_path"])
    img = nib.load(bold)
    n_scans = int(img.shape[-1])
    conf = _load_numeric_confounds(record["confounds_path"], n_scans=n_scans)

    seed_masker = NiftiSpheresMasker([seed_coords], radius=8, detrend=True, standardize="zscore_sample")
    seed_ts = seed_masker.fit_transform(bold, confounds=conf)

    brain_masker = NiftiMasker(detrend=True, standardize="zscore_sample")
    brain_ts = brain_masker.fit_transform(bold, confounds=conf)
    seed = seed_ts[:, 0]
    seed = (seed - seed.mean()) / (seed.std() + 1e-8)
    brain_z = (brain_ts - brain_ts.mean(axis=0, keepdims=True)) / (brain_ts.std(axis=0, keepdims=True) + 1e-8)
    corr = brain_z.T @ seed / max(1, len(seed) - 1)
    corr_img = brain_masker.inverse_transform(corr[np.newaxis, :])

    nii_path = out_dir / "seed_to_voxel_corr_subject0.nii.gz"
    corr_img.to_filename(nii_path)

    fig = plt.figure(figsize=(8, 4))
    d = plot_stat_map(corr_img, title=f"Seed-to-voxel correlation {record['subject_id']}", threshold=0.1, colorbar=True)
    fig_path = out_dir / "seed_to_voxel_corr_subject0.png"
    d.savefig(fig_path)
    d.close()
    plt.close(fig)
    return {"corr_map_nii": str(nii_path), "corr_map_plot": str(fig_path)}


def _dict_region_extraction_step(records: List[Dict[str, Path]], out_dir: Path, n_components: int) -> Dict[str, str]:
    imgs = [str(rec["bold_path"]) for rec in records]
    dict_learning = DictLearning(
        n_components=n_components,
        smoothing_fwhm=6.0,
        random_state=42,
        memory_level=1,
        n_epochs=1,
        standardize="zscore_sample",
    )
    dict_learning.fit(imgs)
    maps = dict_learning.components_img_
    extractor = RegionExtractor(maps, threshold=1.5, thresholding_strategy="ratio_n_voxels", extractor="local_regions")
    extractor.fit()
    regions_img = extractor.regions_img_
    indices = extractor.index_

    regions_path = out_dir / "dictlearning_extracted_regions.nii.gz"
    regions_img.to_filename(regions_path)
    index_path = out_dir / "dictlearning_extracted_region_index.csv"
    pd.DataFrame({"region_idx": np.arange(len(indices)), "source_component": indices}).to_csv(index_path, index=False)

    fig = plt.figure(figsize=(8, 4))
    d = plot_prob_atlas(regions_img, title="Extracted regions from DictLearning maps")
    fig_path = out_dir / "dictlearning_extracted_regions.png"
    d.savefig(fig_path)
    d.close()
    plt.close(fig)
    return {"regions_nii": str(regions_path), "region_index_csv": str(index_path), "regions_plot": str(fig_path)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Run resting-state Nilearn connectivity analyses on ds000243 fMRIPrep outputs.")
    ap.add_argument(
        "--fmriprep-root",
        default="data/current_canonical/openneuro_ds000243/derivatives/fmriprep",
        help="Path to fMRIPrep derivative root",
    )
    ap.add_argument(
        "--out-dir",
        default="artifacts/current_canonical/ds000243_nilearn_rest_suite_20260402/reports",
        help="Output report directory",
    )
    ap.add_argument("--max-subjects", type=int, default=6, help="Number of subjects to include")
    ap.add_argument("--n-components", type=int, default=8, help="Components for decomposition methods")
    ap.add_argument("--seed", default="0,-52,26", help="MNI seed coord as x,y,z")
    args = ap.parse_args()

    fmriprep_root = Path(args.fmriprep_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_coords = tuple(float(x.strip()) for x in args.seed.split(","))

    records = _collect_subject_runs(fmriprep_root=fmriprep_root, max_subjects=args.max_subjects)

    outputs = {}
    outputs["signal_extraction"] = _signal_extraction_step(records, out_dir)
    outputs["probabilistic_atlas_extraction"] = _probabilistic_atlas_step(records, out_dir)
    outputs["inverse_covariance_connectome"] = _inverse_covariance_step(records, out_dir)
    outputs["compare_decomposition"] = _compare_decomposition_step(records, out_dir, n_components=args.n_components)
    outputs["seed_to_voxel_correlation"] = _seed_to_voxel_step(records[0], out_dir, seed_coords=seed_coords)
    outputs["extract_regions_dictlearning_maps"] = _dict_region_extraction_step(
        records, out_dir, n_components=args.n_components
    )

    dataset_rows = [
        {
            "subject_id": rec["subject_id"],
            "bold_path": str(rec["bold_path"]),
            "confounds_path": str(rec["confounds_path"]) if rec["confounds_path"] else "",
        }
        for rec in records
    ]
    dataset_csv = out_dir / "input_subjects.csv"
    pd.DataFrame(dataset_rows).to_csv(dataset_csv, index=False)

    manifest = {
        "dataset": "openneuro_ds000243",
        "input_type": "fMRIPrep derivatives (preprocessed)",
        "fmriprep_root": str(fmriprep_root),
        "subjects_used": len(records),
        "seed_coords_mni": seed_coords,
        "outputs": outputs,
        "input_subjects_csv": str(dataset_csv),
    }
    manifest_path = out_dir / "nilearn_rest_suite_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    md_lines = [
        "# ds000243 Nilearn Rest Suite",
        "",
        "- Input type: fMRIPrep derivatives (already preprocessed)",
        f"- Subjects used: {len(records)}",
        f"- fMRIPrep root: `{fmriprep_root}`",
        f"- Seed (MNI): `{seed_coords}`",
        "",
        "## Outputs",
    ]
    for key, val in outputs.items():
        md_lines.append(f"- {key}:")
        for k, v in val.items():
            md_lines.append(f"  - {k}: `{v}`")
    md_lines.append("")
    md_lines.append(f"- input_subjects_csv: `{dataset_csv}`")
    md_lines.append(f"- manifest_json: `{manifest_path}`")
    md_path = out_dir / "nilearn_rest_suite_report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"manifest": str(manifest_path), "report": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
