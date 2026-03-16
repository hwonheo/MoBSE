from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd


def _timepoints_from_img(img: str | Path) -> int:
    try:
        from nilearn.image import load_img
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "nilearn is required for nuisance regression. Install with `pip install .[neuro]`."
        ) from exc
    return int(load_img(str(img)).shape[-1])


def _to_numeric_confounds(confounds: Any) -> Optional[np.ndarray]:
    if confounds is None:
        return None

    if isinstance(confounds, (str, Path)):
        path = Path(confounds)
        if not path.exists():
            return None
        sep = "\t" if path.suffix.lower() in {".tsv"} else ","
        df = pd.read_csv(path, sep=sep)
    elif isinstance(confounds, pd.DataFrame):
        df = confounds
    else:
        arr = np.asarray(confounds)
        if arr.ndim == 1:
            arr = arr[:, None]
        if arr.ndim != 2:
            return None
        arr = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        return arr if arr.size else None

    numeric = df.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.loc[:, numeric.notna().any(axis=0)]
    if numeric.shape[1] == 0:
        return None
    arr = numeric.to_numpy(dtype=np.float32)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr if arr.size else None


def _align_confounds_len(arr: np.ndarray, n_timepoints: int) -> np.ndarray:
    if arr.shape[0] == n_timepoints:
        return arr
    if arr.shape[0] > n_timepoints:
        warnings.warn(
            f"Confounds longer than BOLD ({arr.shape[0]} > {n_timepoints}); trimming.",
            RuntimeWarning,
        )
        return arr[:n_timepoints]

    warnings.warn(
        f"Confounds shorter than BOLD ({arr.shape[0]} < {n_timepoints}); zero-padding.",
        RuntimeWarning,
    )
    pad = np.zeros((n_timepoints - arr.shape[0], arr.shape[1]), dtype=arr.dtype)
    return np.vstack([arr, pad])


def expand_confounds(
    base_confounds: np.ndarray,
    *,
    add_derivatives: bool,
    add_quadratic: bool,
) -> np.ndarray:
    cols = [base_confounds]
    derivatives = None
    if add_derivatives:
        derivatives = np.vstack(
            [np.zeros((1, base_confounds.shape[1]), dtype=base_confounds.dtype), np.diff(base_confounds, axis=0)]
        )
        cols.append(derivatives)

    if add_quadratic:
        cols.append(base_confounds**2)
        if derivatives is not None:
            cols.append(derivatives**2)

    out = np.concatenate(cols, axis=1)
    out = np.nan_to_num(out.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    return out


def build_paper_nuisance_confounds(
    *,
    bold_path: str | Path,
    tr: float,
    external_confounds: Any = None,
    include_compcor: bool = True,
    compcor_components: int = 5,
    include_gsr: bool = True,
    add_derivatives: bool = True,
    add_quadratic: bool = True,
) -> Optional[np.ndarray]:
    """Build nuisance confounds inspired by recent fMRI denoising practice.

    When motion/physio confounds are unavailable (common for raw OpenNeuro snapshots),
    this uses data-driven components (high-variance confounds, CompCor-like) plus
    global signal, and optionally derivative/quadratic expansion.
    """
    n_timepoints = _timepoints_from_img(bold_path)
    blocks = []

    ext = _to_numeric_confounds(external_confounds)
    if ext is not None:
        blocks.append(_align_confounds_len(ext, n_timepoints))

    if include_compcor and compcor_components > 0:
        try:
            from nilearn.image import high_variance_confounds
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "nilearn is required for nuisance regression. Install with `pip install .[neuro]`."
            ) from exc
        comp = high_variance_confounds(
            str(bold_path),
            n_confounds=int(compcor_components),
            percentile=2.0,
            detrend=True,
        )
        comp = np.asarray(comp, dtype=np.float32)
        if comp.ndim == 1:
            comp = comp[:, None]
        if comp.size:
            blocks.append(_align_confounds_len(comp, n_timepoints))

    if include_gsr:
        try:
            from nilearn.maskers import NiftiMasker
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "nilearn is required for nuisance regression. Install with `pip install .[neuro]`."
            ) from exc
        whole_brain = NiftiMasker(mask_strategy="epi", standardize=False, detrend=False, t_r=tr).fit_transform(
            str(bold_path)
        )
        gs = np.mean(whole_brain, axis=1, keepdims=True).astype(np.float32)
        blocks.append(_align_confounds_len(gs, n_timepoints))

    if not blocks:
        return None

    base = np.column_stack(blocks).astype(np.float32)
    return expand_confounds(
        base_confounds=base,
        add_derivatives=add_derivatives,
        add_quadratic=add_quadratic,
    )
