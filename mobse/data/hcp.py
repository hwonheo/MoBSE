from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from mobse.data.nuisance import build_paper_nuisance_confounds


@dataclass
class OSStateRecord:
    subject_id: str
    state: str
    path: Path


def extract_timeseries_from_manifest(
    manifest_csv: str | Path,
    output_root: str | Path,
    states: List[str],
    num_nodes: int,
    tr: float,
    nuisance_include_compcor: bool = True,
    nuisance_compcor_components: int = 5,
    nuisance_include_gsr: bool = True,
    nuisance_add_derivatives: bool = True,
    nuisance_add_quadratic: bool = True,
    nuisance_detrend: bool = True,
    nuisance_high_pass: float = 0.008,
    nuisance_low_pass: float = 0.1,
) -> None:
    """Extract ROI time-series from NIfTI scans using Schaefer parcellation.

    Manifest CSV columns:
    - subject_id
    - state
    - nifti_path
    - confounds_path (optional)
    """

    try:
        from nilearn.datasets import fetch_atlas_schaefer_2018
        from nilearn.maskers import NiftiLabelsMasker
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "nilearn is required for NIfTI extraction. Install with `pip install .[neuro]`."
        ) from exc

    manifest = pd.read_csv(manifest_csv)
    required = {"subject_id", "state", "nifti_path"}
    if not required.issubset(set(manifest.columns)):
        raise ValueError(f"Manifest must include columns: {sorted(required)}")

    atlas = fetch_atlas_schaefer_2018(n_rois=num_nodes)
    masker = NiftiLabelsMasker(
        labels_img=atlas.maps,
        standardize="zscore_sample",
        t_r=tr,
        detrend=nuisance_detrend,
        high_pass=(nuisance_high_pass if nuisance_high_pass > 0 else None),
        low_pass=(nuisance_low_pass if nuisance_low_pass > 0 else None),
    )
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    state_set = set(states)

    for _, row in manifest.iterrows():
        state = str(row["state"]).lower()
        if state not in state_set:
            continue
        subject_id = str(row["subject_id"])
        nifti_path = str(row["nifti_path"])
        confounds_path = row.get("confounds_path", None)
        confounds = str(confounds_path) if isinstance(confounds_path, str) else None

        nuisance = build_paper_nuisance_confounds(
            bold_path=nifti_path,
            tr=tr,
            external_confounds=confounds,
            include_compcor=nuisance_include_compcor,
            compcor_components=nuisance_compcor_components,
            include_gsr=nuisance_include_gsr,
            add_derivatives=nuisance_add_derivatives,
            add_quadratic=nuisance_add_quadratic,
        )
        ts = masker.fit_transform(nifti_path, confounds=nuisance)
        subject_dir = output_root / subject_id
        subject_dir.mkdir(parents=True, exist_ok=True)
        np.save(subject_dir / f"{state}.npy", ts.astype(np.float32))


def discover_os_timeseries(
    timeseries_dir: str | Path,
    states: List[str],
    subjects_limit: int,
    num_nodes: int,
) -> List[OSStateRecord]:
    timeseries_path = Path(timeseries_dir)
    if not timeseries_path.exists():
        raise FileNotFoundError(
            f"Open-source timeseries directory not found: {timeseries_path}. "
            "Run `python -m mobse.cli prepare_data --config <config> --mode public_proxy --subjects 30` first."
        )

    state_set = set(states)
    records: List[OSStateRecord] = []
    subjects = sorted([p for p in timeseries_path.iterdir() if p.is_dir()])
    for subject_dir in subjects[:subjects_limit]:
        for npy_file in sorted(subject_dir.glob("*.npy")):
            state = npy_file.stem.lower()
            if state not in state_set:
                continue
            ts = np.load(npy_file, mmap_mode="r")
            if ts.ndim != 2 or ts.shape[1] != num_nodes:
                continue
            records.append(OSStateRecord(subject_id=subject_dir.name, state=state, path=npy_file))
    if not records:
        raise RuntimeError(
            "No usable open-source timeseries files found. Expected <timeseries_dir>/<subject>/<state>.npy "
            f"with shape [time, {num_nodes}]"
        )
    return records


def compute_fc_matrix(timeseries: np.ndarray, fisher_z: bool = True) -> np.ndarray:
    corr = np.corrcoef(timeseries, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(corr, 0.0)
    if fisher_z:
        clipped = np.clip(corr, -0.999999, 0.999999)
        return np.arctanh(clipped)
    return corr


def inverse_fisher_z(matrix: np.ndarray) -> np.ndarray:
    return np.tanh(matrix)


def sparsify_fc(matrix: np.ndarray, keep_ratio: float) -> np.ndarray:
    if not 0.0 < keep_ratio <= 1.0:
        raise ValueError(f"keep_ratio must be in (0,1], got {keep_ratio}")

    n = matrix.shape[0]
    upper_idx = np.triu_indices(n=n, k=1)
    scores = np.abs(matrix[upper_idx])
    keep = max(1, int(np.ceil(len(scores) * keep_ratio)))
    thresh = np.partition(scores, -keep)[-keep]

    sparse = np.zeros_like(matrix)
    keep_mask = np.abs(matrix) >= thresh
    sparse[keep_mask] = matrix[keep_mask]
    sparse = np.triu(sparse, k=1)
    sparse = sparse + sparse.T
    np.fill_diagonal(sparse, 0.0)
    return sparse


def build_state_templates(
    records: List[OSStateRecord],
    states: List[str],
    keep_ratio: float,
    fisher_z: bool = True,
) -> Dict[str, np.ndarray]:
    grouped: Dict[str, List[np.ndarray]] = {state: [] for state in states}
    for record in records:
        ts = np.load(record.path)
        fc = compute_fc_matrix(ts, fisher_z=fisher_z)
        grouped[record.state].append(fc)

    templates: Dict[str, np.ndarray] = {}
    for state in states:
        matrices = grouped[state]
        if not matrices:
            raise RuntimeError(f"No data found for state: {state}")
        avg = np.mean(np.stack(matrices, axis=0), axis=0)
        if fisher_z:
            avg = inverse_fisher_z(avg)
        templates[state] = sparsify_fc(avg, keep_ratio=keep_ratio)
    return templates


def build_os_windows(
    records: List[OSStateRecord],
    state_to_label: Dict[str, int],
    window_len: int,
    stride: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    windows: List[np.ndarray] = []
    labels: List[int] = []
    subject_ids: List[str] = []

    for record in records:
        ts = np.load(record.path)
        label = state_to_label[record.state]
        t = ts.shape[0]
        if t < window_len:
            continue
        for start in range(0, t - window_len + 1, stride):
            window = ts[start : start + window_len]
            windows.append(window.astype(np.float32))
            labels.append(label)
            subject_ids.append(record.subject_id)

    if not windows:
        raise RuntimeError("No OS windows generated. Adjust window_len/stride or input data.")

    x = np.stack(windows, axis=0)
    y = np.array(labels, dtype=np.int64)
    subjects = np.array(subject_ids, dtype=object)
    return x, y, subjects


def split_indices(n: int, train_ratio: float, val_ratio: float, seed: int) -> Dict[str, np.ndarray]:
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be < 1")
    rng = np.random.default_rng(seed)
    idx = np.arange(n)
    rng.shuffle(idx)

    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    return {
        "train": idx[:train_end],
        "val": idx[train_end:val_end],
        "test": idx[val_end:],
    }


class OSClassificationDataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray):
        self.x = torch.tensor(x, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return int(self.x.shape[0])

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "x": self.x[idx],
            "y": self.y[idx],
            "task": torch.tensor(0, dtype=torch.long),
        }


def create_os_dataloaders(
    npz_path: str | Path,
    batch_size: int,
    train_ratio: float,
    val_ratio: float,
    seed: int,
    train_subject_prefixes: List[str] | None = None,
    val_subject_prefixes: List[str] | None = None,
    test_subject_prefixes: List[str] | None = None,
) -> Dict[str, DataLoader]:
    pack = np.load(npz_path, allow_pickle=True)
    x = pack["x"]
    y = pack["y"]
    subjects = pack["subject_ids"].astype(str) if "subject_ids" in pack else None

    train_subject_prefixes = train_subject_prefixes or []
    val_subject_prefixes = val_subject_prefixes or []
    test_subject_prefixes = test_subject_prefixes or []

    if train_subject_prefixes or val_subject_prefixes or test_subject_prefixes:
        if subjects is None:
            raise ValueError("Explicit subject-prefix split requested, but `subject_ids` is missing from the OS windows NPZ.")

        idx = np.arange(len(x))

        def prefix_mask(prefixes: List[str]) -> np.ndarray:
            if not prefixes:
                return np.zeros(len(subjects), dtype=bool)
            return np.array([any(subject.startswith(prefix) for prefix in prefixes) for subject in subjects], dtype=bool)

        train_mask = prefix_mask(train_subject_prefixes)
        val_mask = prefix_mask(val_subject_prefixes)
        test_mask = prefix_mask(test_subject_prefixes)

        if np.any(train_mask & val_mask) or np.any(train_mask & test_mask) or np.any(val_mask & test_mask):
            raise ValueError("Explicit subject-prefix splits overlap. Train/val/test subject sets must be disjoint.")

        if val_subject_prefixes:
            train_pool = idx[train_mask] if train_subject_prefixes else idx[~(val_mask | test_mask)]
            val_idx = idx[val_mask]
            train_idx = train_pool
        else:
            train_pool = idx[train_mask] if train_subject_prefixes else idx[~test_mask]
            if len(train_pool) == 0:
                raise ValueError("No samples matched the requested train subject prefixes.")
            val_fraction = val_ratio / max(train_ratio + val_ratio, 1e-8)
            rng = np.random.default_rng(seed)
            shuffled = np.array(train_pool, copy=True)
            rng.shuffle(shuffled)
            train_end = int(len(shuffled) * (1.0 - val_fraction))
            train_idx = shuffled[:train_end]
            val_idx = shuffled[train_end:]

        test_idx = idx[test_mask] if test_subject_prefixes else idx[~np.isin(idx, np.concatenate([train_idx, val_idx]))]

        if len(train_idx) == 0 or len(val_idx) == 0 or len(test_idx) == 0:
            raise ValueError(
                "Explicit subject-prefix split produced an empty split. "
                f"train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}"
            )

        splits = {"train": train_idx, "val": val_idx, "test": test_idx}
    else:
        splits = split_indices(len(x), train_ratio=train_ratio, val_ratio=val_ratio, seed=seed)
    datasets = {
        split: OSClassificationDataset(x[idx], y[idx])
        for split, idx in splits.items()
    }

    return {
        "train": DataLoader(datasets["train"], batch_size=batch_size, shuffle=True),
        "val": DataLoader(datasets["val"], batch_size=batch_size, shuffle=False),
        "test": DataLoader(datasets["test"], batch_size=batch_size, shuffle=False),
    }


# Backward compatibility aliases.
HCPStateRecord = OSStateRecord
discover_hcp_timeseries = discover_os_timeseries
build_hcp_windows = build_os_windows
HCPClassificationDataset = OSClassificationDataset
create_hcp_dataloaders = create_os_dataloaders
