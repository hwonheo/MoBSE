from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from mobse.artifacts import ArtifactPaths
from mobse.config import ExperimentConfig
from mobse.data.os_data import (
    build_os_windows,
    build_state_templates,
    discover_os_timeseries,
    extract_timeseries_from_manifest,
)
from mobse.progress import ProgressReporter


def _resolve_timeseries_dir(base_dir: Path, num_nodes: int) -> Path:
    node_specific = base_dir / str(num_nodes)
    return node_specific if node_specific.exists() else base_dir


def _serialize_templates(
    templates: Dict[str, np.ndarray],
    output_path: Path,
    metadata: Dict[str, object],
) -> None:
    payload = {f"template::{k}": v for k, v in templates.items()}
    payload["metadata_json"] = np.array([str(metadata)], dtype=object)
    np.savez_compressed(output_path, **payload)


def build_template_bank(
    cfg: ExperimentConfig,
    paths: ArtifactPaths,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, Path]:
    states = cfg.data.os.states
    base_timeseries_dir = Path(cfg.data.os.timeseries_dir)
    generated: Dict[str, Path] = {}

    primary_windows_written = False

    total_jobs = len(cfg.template.atlas_nodes_options) * len(cfg.template.sparsity_levels)
    done_jobs = 0

    for node_idx, num_nodes in enumerate(cfg.template.atlas_nodes_options, start=1):
        if progress:
            progress.update(
                stage="build_templates:atlas",
                current=node_idx,
                total=len(cfg.template.atlas_nodes_options),
                message=f"num_nodes={num_nodes}",
            )
        ts_dir = _resolve_timeseries_dir(base_timeseries_dir, num_nodes)
        if (not ts_dir.exists() or not any(ts_dir.glob("*/*.npy"))) and cfg.data.os.nifti_manifest:
            ts_dir.mkdir(parents=True, exist_ok=True)
            extract_timeseries_from_manifest(
                manifest_csv=cfg.data.os.nifti_manifest,
                output_root=ts_dir,
                states=states,
                num_nodes=num_nodes,
                tr=cfg.data.os.tr,
                nuisance_include_compcor=cfg.data.os.nuisance_include_compcor,
                nuisance_compcor_components=cfg.data.os.nuisance_compcor_components,
                nuisance_include_gsr=cfg.data.os.nuisance_include_gsr,
                nuisance_add_derivatives=cfg.data.os.nuisance_add_derivatives,
                nuisance_add_quadratic=cfg.data.os.nuisance_add_quadratic,
                nuisance_detrend=cfg.data.os.nuisance_detrend,
                nuisance_high_pass=cfg.data.os.nuisance_high_pass,
                nuisance_low_pass=cfg.data.os.nuisance_low_pass,
            )
        records = discover_os_timeseries(
            timeseries_dir=ts_dir,
            states=states,
            subjects_limit=cfg.data.os.subjects_limit,
            num_nodes=num_nodes,
        )

        for sparsity in cfg.template.sparsity_levels:
            templates = build_state_templates(
                records=records,
                states=states,
                keep_ratio=sparsity,
                fisher_z=cfg.template.fisher_z_average,
            )
            key = f"atlas{num_nodes}_sp{int(sparsity * 100)}"
            output_path = paths.templates / f"{key}_{cfg.template.output_name}"
            metadata = {
                "states": states,
                "num_nodes": num_nodes,
                "sparsity": sparsity,
                "subjects_limit": cfg.data.os.subjects_limit,
            }
            _serialize_templates(templates=templates, output_path=output_path, metadata=metadata)
            generated[key] = output_path
            done_jobs += 1
            if progress:
                progress.update(
                    stage="build_templates:template",
                    current=done_jobs,
                    total=total_jobs,
                    message=f"saved={output_path.name}",
                )

            should_make_windows = (
                not primary_windows_written
                and num_nodes == cfg.model.num_nodes
                and np.isclose(sparsity, cfg.template.default_sparsity)
            )
            if should_make_windows:
                state_to_label = {state: idx for idx, state in enumerate(states)}
                x, y, subject_ids = build_os_windows(
                    records=records,
                    state_to_label=state_to_label,
                    window_len=cfg.data.os.window_len,
                    stride=cfg.data.os.stride,
                )
                # Save the new os_windows filename and a legacy alias for compatibility.
                np.savez_compressed(
                    paths.templates / f"os_windows_nodes{num_nodes}.npz",
                    x=x,
                    y=y,
                    subject_ids=subject_ids,
                    labels=np.array(states, dtype=object),
                )
                np.savez_compressed(
                    paths.templates / f"hcp_windows_nodes{num_nodes}.npz",
                    x=x,
                    y=y,
                    subject_ids=subject_ids,
                    labels=np.array(states, dtype=object),
                )
                primary_windows_written = True
                if progress:
                    progress.update(
                        stage="build_templates:windows",
                        message=f"saved=os_windows_nodes{num_nodes}.npz ({x.shape[0]} windows)",
                    )

    if not primary_windows_written:
        raise RuntimeError(
            "Could not build primary OS windows. Ensure model.num_nodes and template.default_sparsity "
            "are included in template atlas/sparsity settings."
        )

    return generated


def load_template_bank(path: str | Path, states: List[str]) -> np.ndarray:
    pack = np.load(path, allow_pickle=True)
    templates = []
    for state in states:
        key = f"template::{state}"
        if key not in pack:
            raise KeyError(f"State template missing in bank file: {state}")
        templates.append(pack[key].astype(np.float32))
    return np.stack(templates, axis=0)
