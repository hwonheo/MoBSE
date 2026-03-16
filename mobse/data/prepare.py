from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from mobse.config import ExperimentConfig
from mobse.data.nuisance import build_paper_nuisance_confounds
from mobse.data.synthetic import generate_synthetic_hcp
from mobse.progress import ProgressReporter


DEFAULT_ETTH1_URL = "https://raw.githubusercontent.com/zhouhaoyi/ETDataset/main/ETT-small/ETTh1.csv"
DEFAULT_OPENNEURO_DATASET = "ds000030"
DEFAULT_OPENNEURO_TASK = "rest"
OPENNEURO_GRAPHQL_URL = "https://openneuro.org/crn/graphql"


@dataclass
class OpenNeuroFileEntry:
    relative_path: str
    url: str


def _parse_openneuro_dataset_ids(single_dataset: str, datasets_csv: str = "") -> List[str]:
    candidates: List[str] = []
    if datasets_csv.strip():
        candidates.extend([token.strip() for token in re.split(r"[,\s]+", datasets_csv) if token.strip()])
    elif single_dataset.strip():
        candidates.append(single_dataset.strip())

    # Keep order, drop duplicates.
    deduped = list(dict.fromkeys(candidates))
    if not deduped:
        raise ValueError("At least one OpenNeuro dataset id must be provided.")
    return deduped


def _compose_subject_key(dataset_id: str, participant_id: str) -> str:
    return f"{dataset_id}_{_normalize_subject_id(participant_id)}"


def _parse_task_names(task_value: str) -> List[str]:
    tokens = [token.strip().lower() for token in re.split(r"[,\s]+", str(task_value)) if token.strip()]
    deduped = list(dict.fromkeys(tokens))
    if not deduped:
        raise ValueError("At least one task name must be provided.")
    return deduped


def download_etth1(csv_path: str | Path, url: str = DEFAULT_ETTH1_URL, timeout: int = 60) -> Path:
    out_path = Path(csv_path)
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    out_path.write_bytes(response.content)
    return out_path


def _state_variants(base_ts: np.ndarray, states: List[str], seed: int) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t, n = base_ts.shape
    centered = base_ts - base_ts.mean(axis=0, keepdims=True)
    variants: Dict[str, np.ndarray] = {}

    for i, state in enumerate(states):
        if i == 0:
            ts = centered
        elif i == 1:
            ts = np.roll(centered, shift=2, axis=0)
        elif i == 2:
            trend = np.linspace(-0.3, 0.3, t, dtype=np.float32).reshape(-1, 1)
            ts = centered + trend * (rng.normal(size=(1, n)).astype(np.float32) * 0.2)
        elif i == 3:
            ts = centered * (1.0 + 0.15 * np.sin(np.linspace(0, 8, t)).reshape(-1, 1))
        else:
            noise = rng.normal(scale=0.05, size=centered.shape).astype(np.float32)
            ts = centered + noise
        variants[state] = ts.astype(np.float32)

    return variants


def prepare_public_fmri_proxy(
    timeseries_root: str | Path,
    states: List[str],
    atlas_nodes_options: List[int],
    n_subjects: int,
    tr: float,
    nuisance_include_compcor: bool,
    nuisance_compcor_components: int,
    nuisance_include_gsr: bool,
    nuisance_add_derivatives: bool,
    nuisance_add_quadratic: bool,
    nuisance_detrend: bool,
    nuisance_high_pass: float,
    nuisance_low_pass: float,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, int]:
    try:
        from nilearn.datasets import fetch_atlas_schaefer_2018, fetch_development_fmri
        from nilearn.maskers import NiftiLabelsMasker
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "nilearn is required for public fMRI proxy mode. Install with `pip install .[neuro]`."
        ) from exc

    data = fetch_development_fmri(n_subjects=n_subjects, reduce_confounds=True)
    funcs = getattr(data, "func", None)
    if funcs is None:
        funcs = getattr(data, "funcs", None)
    confounds = getattr(data, "confounds", None)
    if funcs is None or confounds is None:
        raise RuntimeError(
            "Unexpected nilearn fetch_development_fmri output schema. "
            "Expected fields `func`/`funcs` and `confounds`."
        )

    root = Path(timeseries_root)
    root.mkdir(parents=True, exist_ok=True)

    stats: Dict[str, int] = {}
    for node_idx, num_nodes in enumerate(atlas_nodes_options, start=1):
        if progress:
            progress.update(
                stage="prepare_data:proxy_atlas",
                current=node_idx,
                total=len(atlas_nodes_options),
                message=f"parcellation num_nodes={num_nodes}",
            )
        atlas = fetch_atlas_schaefer_2018(n_rois=num_nodes)
        masker = NiftiLabelsMasker(
            labels_img=atlas.maps,
            standardize="zscore_sample",
            t_r=tr,
            detrend=nuisance_detrend,
            high_pass=(nuisance_high_pass if nuisance_high_pass > 0 else None),
            low_pass=(nuisance_low_pass if nuisance_low_pass > 0 else None),
        )
        node_root = root / str(num_nodes)
        node_root.mkdir(parents=True, exist_ok=True)

        written = 0
        for idx, (func, conf) in enumerate(zip(funcs, confounds), start=1):
            nuisance = build_paper_nuisance_confounds(
                bold_path=func,
                tr=tr,
                external_confounds=conf,
                include_compcor=nuisance_include_compcor,
                compcor_components=nuisance_compcor_components,
                include_gsr=nuisance_include_gsr,
                add_derivatives=nuisance_add_derivatives,
                add_quadratic=nuisance_add_quadratic,
            )
            base_ts = masker.fit_transform(func, confounds=nuisance)
            variants = _state_variants(base_ts, states=states, seed=idx + num_nodes)

            subject_dir = node_root / f"sub-{idx - 1:04d}"
            subject_dir.mkdir(parents=True, exist_ok=True)
            for state, ts in variants.items():
                np.save(subject_dir / f"{state}.npy", ts)
            written += 1
            if progress:
                progress.update(
                    stage="prepare_data:proxy_subject",
                    current=idx,
                    total=len(funcs),
                    message=f"nodes={num_nodes} subject={subject_dir.name}",
                )

        stats[f"nodes_{num_nodes}"] = written

    return stats


def _openneuro_graphql_query(
    api_url: str,
    query: str,
    variables: Dict[str, object],
) -> Dict[str, object]:
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            response = requests.post(api_url, json={"query": query, "variables": variables}, timeout=60)
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(f"OpenNeuro GraphQL error: {payload['errors']}")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("OpenNeuro GraphQL response missing data payload")
            return data
        except Exception as exc:
            last_exc = exc
            if attempt >= 4:
                break
            time.sleep(1.0 * (2**attempt))
    assert last_exc is not None
    raise last_exc


def _resolve_openneuro_snapshot_tag(
    dataset_id: str,
    snapshot_tag: str | None,
    api_url: str,
) -> str:
    if snapshot_tag:
        return snapshot_tag

    query = """
    query($id: ID!) {
      dataset(id: $id) {
        latestSnapshot {
          tag
        }
      }
    }
    """
    data = _openneuro_graphql_query(
        api_url=api_url,
        query=query,
        variables={"id": dataset_id},
    )
    dataset = data.get("dataset")
    if not dataset or not dataset.get("latestSnapshot"):
        raise RuntimeError(f"Could not resolve latest snapshot for OpenNeuro dataset: {dataset_id}")

    tag = dataset["latestSnapshot"].get("tag")
    if not isinstance(tag, str) or not tag:
        raise RuntimeError(f"Invalid latest snapshot tag for OpenNeuro dataset: {dataset_id}")
    return tag


def _list_openneuro_files(
    dataset_id: str,
    snapshot_tag: str,
    api_url: str,
    progress: Optional[ProgressReporter] = None,
    recursive: bool = True,
    allowed_subjects: Optional[List[str]] = None,
) -> List[OpenNeuroFileEntry]:
    query = """
    query($datasetId: ID!, $tag: String!, $tree: String) {
      snapshot(datasetId: $datasetId, tag: $tag) {
        files(tree: $tree) {
          filename
          directory
          key
          urls
        }
      }
    }
    """

    allowed_subject_set = (
        {_normalize_subject_id(subject_id).lower() for subject_id in allowed_subjects}
        if allowed_subjects
        else None
    )
    stack: List[tuple[str, str]] = [("", "")]
    queued_keys = {""}
    visited_keys = set()
    flattened: List[OpenNeuroFileEntry] = []
    queried_dirs = 0

    while stack:
        tree_key, parent_path = stack.pop()
        queued_keys.discard(tree_key)
        if tree_key in visited_keys:
            continue
        visited_keys.add(tree_key)
        data = _openneuro_graphql_query(
            api_url=api_url,
            query=query,
            variables={
                "datasetId": dataset_id,
                "tag": snapshot_tag,
                "tree": tree_key,
            },
        )
        queried_dirs += 1
        files = (data.get("snapshot") or {}).get("files") or []

        if progress:
            progress.update(
                stage="prepare_data:openneuro_index",
                message=f"dataset={dataset_id} tag={snapshot_tag} tree_calls={queried_dirs}",
            )

        for item in files:
            name = str(item.get("filename", "")).strip()
            if not name:
                continue
            rel_path = f"{parent_path}/{name}" if parent_path else name
            is_dir = bool(item.get("directory"))
            if is_dir:
                if not recursive:
                    continue

                rel_lower = rel_path.lower()
                basename = name.lower()
                if basename in {"derivatives", "sourcedata", "stimuli"}:
                    continue

                # If subjects are preselected from participants.tsv, only traverse those.
                if parent_path == "" and allowed_subject_set is not None:
                    if not basename.startswith("sub-"):
                        continue
                    if _normalize_subject_id(name).lower() not in allowed_subject_set:
                        continue

                # Prune deep directory traversal for subject-restricted scans:
                # keep only subject -> (func | ses-*) -> func branches.
                if allowed_subject_set is not None:
                    parent_lower = parent_path.lower()
                    if re.fullmatch(r"sub-[^/]+", parent_lower):
                        if basename != "func" and not basename.startswith("ses-"):
                            continue
                    elif re.fullmatch(r"sub-[^/]+/ses-[^/]+", parent_lower):
                        if basename != "func":
                            continue
                    elif parent_lower.endswith("/func") or "/func/" in parent_lower:
                        # Do not recurse below func; files at this level are enough.
                        continue

                key = item.get("key")
                if (
                    isinstance(key, str)
                    and key
                    and key not in visited_keys
                    and key not in queued_keys
                ):
                    queued_keys.add(key)
                    stack.append((key, rel_path))
                continue

            urls = item.get("urls") or []
            if not urls:
                continue

            flattened.append(OpenNeuroFileEntry(relative_path=rel_path, url=str(urls[0])))

    flattened.sort(key=lambda x: x.relative_path)
    if not flattened:
        raise RuntimeError(f"No files indexed for OpenNeuro dataset={dataset_id}, tag={snapshot_tag}")
    return flattened


def _normalize_subject_id(raw: str) -> str:
    value = str(raw).strip()
    if not value:
        return value
    if value.startswith("sub-"):
        return value
    if value.startswith("sub"):
        suffix = value[3:].lstrip("-_")
        return f"sub-{suffix}"
    return f"sub-{value}"


def _pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    lookup = {str(col).lower(): str(col) for col in df.columns}
    for candidate in candidates:
        key = candidate.lower()
        if key in lookup:
            return lookup[key]
    return None


def _to_bool_mask(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y"})


def _normalize_text_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())


def _select_openneuro_subjects(
    participants_tsv_text: str,
    diagnosis: str,
    min_age: int,
    n_subjects: int,
    strict_hc: bool,
) -> Dict[str, object]:
    df = pd.read_csv(io.StringIO(participants_tsv_text), sep="\t", dtype=str)

    subject_col = _pick_column(df, ["participant_id", "subject_id", "participant", "subject"])
    if subject_col is None:
        raise RuntimeError("participants.tsv missing subject id column (expected participant_id or subject_id)")

    diagnosis_col = _pick_column(df, ["diagnosis", "group", "dx"])
    age_col = _pick_column(df, ["age", "age_years", "ageinyears"])
    rest_col = _pick_column(df, ["rest"])

    if strict_hc and diagnosis_col is None:
        raise RuntimeError("HC filtering requires diagnosis/group column in participants.tsv")
    if strict_hc and age_col is None:
        raise RuntimeError("HC filtering requires age column in participants.tsv")

    mask = np.ones(len(df), dtype=bool)
    filters_applied: Dict[str, object] = {}
    filters_skipped: List[str] = []

    if diagnosis:
        if diagnosis_col is None:
            filters_skipped.append("diagnosis")
        else:
            raw_tokens = [token.strip() for token in re.split(r"[|,]+", diagnosis) if token.strip()]
            diag_tokens = [_normalize_text_token(token) for token in raw_tokens]
            diag_tokens = [token for token in diag_tokens if token]
            if not diag_tokens:
                diag_tokens = [_normalize_text_token(diagnosis)]

            diag_values = df[diagnosis_col].astype(str).map(_normalize_text_token)
            diag_mask = pd.Series(False, index=df.index)
            for token in diag_tokens:
                # Allow exact match for short tokens (e.g., HC), relaxed contains for descriptive labels.
                if len(token) <= 2:
                    diag_mask = diag_mask | diag_values.eq(token)
                else:
                    diag_mask = diag_mask | diag_values.eq(token) | diag_values.str.contains(
                        token, regex=False
                    )
            mask = mask & diag_mask.to_numpy()
            filters_applied["diagnosis"] = raw_tokens[0] if len(raw_tokens) == 1 else raw_tokens

    if min_age > 0:
        if age_col is None:
            filters_skipped.append("age")
        else:
            age_mask = pd.to_numeric(df[age_col], errors="coerce").ge(float(min_age)).fillna(False)
            mask = mask & age_mask.to_numpy()
            filters_applied["min_age"] = int(min_age)

    if rest_col is not None:
        rest_mask = _to_bool_mask(df[rest_col]).fillna(False)
        mask = mask & rest_mask.to_numpy()
        filters_applied["rest_only"] = True

    ids = [_normalize_subject_id(s) for s in df.loc[mask, subject_col].astype(str).tolist()]
    unique_ids = list(dict.fromkeys([s for s in ids if s]))

    return {
        "participant_ids": unique_ids[:n_subjects],
        "filters_applied": filters_applied,
        "filters_skipped": filters_skipped,
        "rows": int(len(df)),
    }


def _extract_subject_id_from_relpath(rel_path: str) -> Optional[str]:
    match = re.search(r"(sub-[^/]+)/func/", rel_path, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def _select_openneuro_bold_entries(
    files: List[OpenNeuroFileEntry],
    participant_ids: List[str],
    task: str,
    n_subjects: int,
) -> Dict[str, object]:
    by_subject: Dict[str, List[OpenNeuroFileEntry]] = {}
    task_names = _parse_task_names(task)
    task_tokens = [f"_task-{name}_" for name in task_names]

    for entry in files:
        rel = entry.relative_path
        rel_lower = rel.lower()
        if "/derivatives/" in rel_lower:
            continue
        if "/func/" not in rel_lower:
            continue
        if not any(token in rel_lower for token in task_tokens):
            continue
        if not rel_lower.endswith("_bold.nii.gz"):
            continue

        subject_id = _extract_subject_id_from_relpath(rel)
        if subject_id is None:
            continue

        by_subject.setdefault(subject_id, []).append(entry)

    for subject_entries in by_subject.values():
        subject_entries.sort(key=lambda x: x.relative_path)

    if participant_ids:
        candidate_ids = [_normalize_subject_id(pid) for pid in participant_ids]
    else:
        candidate_ids = sorted(by_subject.keys())

    selected_ids: List[str] = []
    selected_entries: List[OpenNeuroFileEntry] = []
    missing_ids: List[str] = []

    for pid in candidate_ids:
        picks = by_subject.get(pid)
        if not picks:
            missing_ids.append(pid)
            continue

        selected_ids.append(pid)
        selected_entries.append(picks[0])
        if len(selected_ids) >= n_subjects:
            break

    if not selected_entries:
        joined_tasks = ",".join(task_names)
        raise RuntimeError(
            f"No task-{joined_tasks} BOLD NIfTI files matched selected participants. "
            "Check task name and dataset contents."
        )

    return {
        "participant_ids": selected_ids,
        "entries": selected_entries,
        "missing_ids": missing_ids,
        "available_subjects": len(by_subject),
    }


def _download_openneuro_files(
    dataset_id: str,
    snapshot_tag: str,
    entries: List[OpenNeuroFileEntry],
    cache_root: str | Path,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, Path]:
    base_dir = Path(cache_root) / dataset_id / snapshot_tag / "uncompressed"
    base_dir.mkdir(parents=True, exist_ok=True)

    resolved: Dict[str, Path] = {}
    for idx, entry in enumerate(entries, start=1):
        out_path = base_dir / entry.relative_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not (out_path.exists() and out_path.stat().st_size > 0):
            with requests.get(entry.url, timeout=120, stream=True) as response:
                response.raise_for_status()
                tmp_path = out_path.with_suffix(out_path.suffix + ".part")
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            f.write(chunk)
                tmp_path.replace(out_path)

        resolved[entry.relative_path] = out_path
        if progress:
            progress.update(
                stage="prepare_data:openneuro_download",
                current=idx,
                total=len(entries),
                message=f"saved={entry.relative_path}",
            )

    return resolved


def _download_openneuro_rest_bold(
    dataset_id: str,
    snapshot_tag: str | None,
    task: str,
    n_subjects: int,
    min_age: int,
    diagnosis: str,
    strict_hc: bool,
    api_url: str,
    cache_root: str | Path,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, object]:
    tag = _resolve_openneuro_snapshot_tag(dataset_id=dataset_id, snapshot_tag=snapshot_tag, api_url=api_url)
    root_files = _list_openneuro_files(
        dataset_id=dataset_id,
        snapshot_tag=tag,
        api_url=api_url,
        progress=progress,
        recursive=False,
    )

    participants_entry = next(
        (f for f in root_files if f.relative_path.lower().endswith("participants.tsv")),
        None,
    )

    participant_ids: List[str] = []
    participant_meta: Dict[str, object] = {}
    if participants_entry is not None:
        participants_content = requests.get(participants_entry.url, timeout=60).text
        participant_meta = _select_openneuro_subjects(
            participants_tsv_text=participants_content,
            diagnosis=diagnosis,
            min_age=min_age,
            n_subjects=n_subjects,
            strict_hc=strict_hc,
        )
        participant_ids = participant_meta["participant_ids"]
    elif strict_hc:
        raise RuntimeError("participants.tsv not found; cannot apply strict HC filtering")

    files = _list_openneuro_files(
        dataset_id=dataset_id,
        snapshot_tag=tag,
        api_url=api_url,
        progress=progress,
        recursive=True,
        allowed_subjects=participant_ids if participant_ids else None,
    )

    selected = _select_openneuro_bold_entries(
        files=files,
        participant_ids=participant_ids,
        task=task,
        n_subjects=n_subjects,
    )

    to_download = list(selected["entries"])
    if participants_entry is not None:
        to_download.insert(0, participants_entry)

    resolved = _download_openneuro_files(
        dataset_id=dataset_id,
        snapshot_tag=tag,
        entries=to_download,
        cache_root=cache_root,
        progress=progress,
    )

    local_bold_paths = [resolved[entry.relative_path] for entry in selected["entries"]]
    local_participants_path = (
        str(resolved[participants_entry.relative_path]) if participants_entry is not None else None
    )

    selected_ids = selected["participant_ids"]
    if strict_hc and not selected_ids:
        raise RuntimeError(
            f"No {dataset_id} subjects matched diagnosis={diagnosis}, min_age={min_age}, task={task}"
        )

    return {
        "openneuro_root": str(Path(cache_root) / dataset_id / tag / "uncompressed"),
        "dataset_id": dataset_id,
        "snapshot_tag": tag,
        "task": task,
        "participant_ids": selected_ids,
        "bold_files": [str(p) for p in local_bold_paths],
        "missing_ids": selected["missing_ids"],
        "participants_path": local_participants_path,
        "selection": participant_meta,
    }


def _download_openneuro_rest_bold_multi(
    dataset_ids: List[str],
    snapshot_tag: str | None,
    task: str,
    n_subjects: int,
    min_age: int,
    diagnosis: str,
    strict_hc: bool,
    api_url: str,
    cache_root: str | Path,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, object]:
    if not dataset_ids:
        raise ValueError("dataset_ids must contain at least one OpenNeuro dataset id.")

    records: List[Dict[str, str]] = []
    per_dataset: List[Dict[str, object]] = []
    skipped_datasets: List[Dict[str, str]] = []
    requested_total = int(n_subjects)

    for idx, dataset_id in enumerate(dataset_ids, start=1):
        remaining = requested_total - len(records)
        if remaining <= 0:
            break
        if progress:
            progress.update(
                stage="prepare_data:openneuro_dataset",
                current=idx,
                total=len(dataset_ids),
                message=f"dataset={dataset_id} remaining={remaining}",
            )

        try:
            source = _download_openneuro_rest_bold(
                dataset_id=dataset_id,
                snapshot_tag=snapshot_tag,
                task=task,
                n_subjects=remaining,
                min_age=min_age,
                diagnosis=diagnosis,
                strict_hc=strict_hc,
                api_url=api_url,
                cache_root=cache_root,
                progress=progress,
            )
        except Exception as exc:
            skipped_datasets.append({"dataset_id": dataset_id, "error": str(exc)})
            if progress:
                progress.update(
                    stage="prepare_data:openneuro_skip",
                    message=f"dataset={dataset_id} skipped: {exc}",
                )
            continue

        participant_ids = list(source["participant_ids"])
        bold_files = list(source["bold_files"])
        for pid, bold in zip(participant_ids, bold_files):
            records.append(
                {
                    "dataset_id": dataset_id,
                    "participant_id": pid,
                    "subject_key": _compose_subject_key(dataset_id, pid),
                    "bold_file": bold,
                }
            )

        per_dataset.append(
            {
                "dataset_id": dataset_id,
                "snapshot_tag": source["snapshot_tag"],
                "openneuro_root": source["openneuro_root"],
                "participants_path": source["participants_path"],
                "selection": source["selection"],
                "missing_ids": source["missing_ids"],
                "selected_count": len(participant_ids),
                "requested_count": remaining,
            }
        )

    if not records:
        joined = ",".join(dataset_ids)
        if skipped_datasets:
            details = "; ".join([f"{d['dataset_id']}({d['error']})" for d in skipped_datasets])
            raise RuntimeError(
                f"No subjects collected from datasets [{joined}] for task={task}, diagnosis={diagnosis}, min_age={min_age}. "
                f"Errors: {details}"
            )
        raise RuntimeError(
            f"No subjects collected from datasets [{joined}] for task={task}, diagnosis={diagnosis}, min_age={min_age}"
        )

    return {
        "records": records[:requested_total],
        "dataset_ids": dataset_ids,
        "requested_subjects": requested_total,
        "collected_subjects": min(len(records), requested_total),
        "per_dataset": per_dataset,
        "skipped_datasets": skipped_datasets,
    }


def prepare_openneuro_proxy(
    timeseries_root: str | Path,
    states: List[str],
    atlas_nodes_options: List[int],
    n_subjects: int,
    tr: float,
    min_age: int,
    diagnosis: str,
    dataset_id: str,
    dataset_ids: Optional[List[str]],
    snapshot_tag: str | None,
    task: str,
    strict_hc: bool,
    api_url: str,
    cache_root: str | Path,
    nuisance_include_compcor: bool,
    nuisance_compcor_components: int,
    nuisance_include_gsr: bool,
    nuisance_add_derivatives: bool,
    nuisance_add_quadratic: bool,
    nuisance_detrend: bool,
    nuisance_high_pass: float,
    nuisance_low_pass: float,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, object]:
    try:
        from nilearn.datasets import fetch_atlas_schaefer_2018
        from nilearn.maskers import NiftiLabelsMasker
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "nilearn is required for OpenNeuro mode. Install with `pip install .[neuro]`."
        ) from exc

    resolved_dataset_ids = dataset_ids if dataset_ids else [dataset_id]
    source = _download_openneuro_rest_bold_multi(
        dataset_ids=resolved_dataset_ids,
        snapshot_tag=snapshot_tag,
        task=task,
        n_subjects=n_subjects,
        min_age=min_age,
        diagnosis=diagnosis,
        strict_hc=strict_hc,
        api_url=api_url,
        cache_root=cache_root,
        progress=progress,
    )

    subject_records = list(source["records"])

    root = Path(timeseries_root)
    root.mkdir(parents=True, exist_ok=True)

    stats: Dict[str, int] = {}
    for node_idx, num_nodes in enumerate(atlas_nodes_options, start=1):
        if progress:
            progress.update(
                stage="prepare_data:openneuro_atlas",
                current=node_idx,
                total=len(atlas_nodes_options),
                message=f"parcellation num_nodes={num_nodes}",
            )

        atlas = fetch_atlas_schaefer_2018(n_rois=num_nodes)
        masker = NiftiLabelsMasker(
            labels_img=atlas.maps,
            standardize="zscore_sample",
            t_r=tr,
            detrend=nuisance_detrend,
            high_pass=(nuisance_high_pass if nuisance_high_pass > 0 else None),
            low_pass=(nuisance_low_pass if nuisance_low_pass > 0 else None),
        )
        node_root = root / str(num_nodes)
        node_root.mkdir(parents=True, exist_ok=True)

        written = 0
        for idx, record in enumerate(subject_records, start=1):
            pid = str(record["participant_id"])
            subject_key = str(record["subject_key"])
            dataset = str(record["dataset_id"])
            bold_path = Path(str(record["bold_file"]))
            nuisance = build_paper_nuisance_confounds(
                bold_path=bold_path,
                tr=tr,
                external_confounds=None,
                include_compcor=nuisance_include_compcor,
                compcor_components=nuisance_compcor_components,
                include_gsr=nuisance_include_gsr,
                add_derivatives=nuisance_add_derivatives,
                add_quadratic=nuisance_add_quadratic,
            )
            base_ts = masker.fit_transform(str(bold_path), confounds=nuisance)
            variants = _state_variants(base_ts, states=states, seed=idx + num_nodes)

            subject_dir = node_root / subject_key
            subject_dir.mkdir(parents=True, exist_ok=True)
            for state, ts in variants.items():
                np.save(subject_dir / f"{state}.npy", ts)
            written += 1

            if progress:
                progress.update(
                    stage="prepare_data:openneuro_subject",
                    current=idx,
                    total=len(subject_records),
                    message=f"nodes={num_nodes} dataset={dataset} subject={pid}",
                )

        stats[f"nodes_{num_nodes}"] = written

    return {
        "source": {
            "dataset": resolved_dataset_ids[0] if len(resolved_dataset_ids) == 1 else ",".join(resolved_dataset_ids),
            "datasets": resolved_dataset_ids,
            "snapshot_tag": (
                source["per_dataset"][0]["snapshot_tag"] if len(source["per_dataset"]) == 1 else ""
            ),
            "snapshot_tags": {
                item["dataset_id"]: item["snapshot_tag"] for item in source["per_dataset"]
            },
            "task": task,
            "strict_hc": strict_hc,
            "diagnosis": diagnosis,
            "min_age": min_age,
            "openneuro_root": (
                source["per_dataset"][0]["openneuro_root"] if len(source["per_dataset"]) == 1 else ""
            ),
            "participants_path": (
                source["per_dataset"][0]["participants_path"] if len(source["per_dataset"]) == 1 else ""
            ),
            "participants_paths": {
                item["dataset_id"]: item["participants_path"] for item in source["per_dataset"]
            },
            "missing_ids": [item["missing_ids"] for item in source["per_dataset"]],
            "selection": (
                source["per_dataset"][0]["selection"]
                if len(source["per_dataset"]) == 1
                else {"per_dataset": source["per_dataset"]}
            ),
            "requested_subjects": source["requested_subjects"],
            "collected_subjects": source["collected_subjects"],
            "skipped_datasets": source["skipped_datasets"],
        },
        "os_stats": stats,
        "hcp_stats": stats,
    }


def prepare_data(
    cfg: ExperimentConfig,
    mode: str,
    subjects: int,
    etth1_url: str = DEFAULT_ETTH1_URL,
    min_age: int = 18,
    diagnosis: str = "",
    openneuro_dataset: str = DEFAULT_OPENNEURO_DATASET,
    openneuro_datasets: str = "",
    openneuro_snapshot: str = "",
    openneuro_task: str = DEFAULT_OPENNEURO_TASK,
    openneuro_api_url: str = OPENNEURO_GRAPHQL_URL,
    progress: Optional[ProgressReporter] = None,
) -> Dict[str, object]:
    if progress:
        progress.update(stage="prepare_data:etth1", message="downloading ETTh1 (or using cached file)")
    etth1_path = download_etth1(cfg.data.etth1.csv_path, url=etth1_url)
    if progress:
        progress.update(stage="prepare_data:etth1", message=f"ready {etth1_path}")

    if mode == "synthetic":
        root = Path(cfg.data.os.timeseries_dir)
        for idx, num_nodes in enumerate(cfg.template.atlas_nodes_options, start=1):
            generate_synthetic_hcp(
                timeseries_dir=root / str(num_nodes),
                num_subjects=subjects,
                states=cfg.data.os.states,
                num_nodes=num_nodes,
            )
            if progress:
                progress.update(
                    stage="prepare_data:synthetic",
                    current=idx,
                    total=len(cfg.template.atlas_nodes_options),
                    message=f"generated subjects={subjects}, nodes={num_nodes}",
                )
        os_stats = {f"nodes_{n}": subjects for n in cfg.template.atlas_nodes_options}
    elif mode == "public_proxy":
        os_stats = prepare_public_fmri_proxy(
            timeseries_root=cfg.data.os.timeseries_dir,
            states=cfg.data.os.states,
            atlas_nodes_options=cfg.template.atlas_nodes_options,
            n_subjects=subjects,
            tr=cfg.data.os.tr,
            nuisance_include_compcor=cfg.data.os.nuisance_include_compcor,
            nuisance_compcor_components=cfg.data.os.nuisance_compcor_components,
            nuisance_include_gsr=cfg.data.os.nuisance_include_gsr,
            nuisance_add_derivatives=cfg.data.os.nuisance_add_derivatives,
            nuisance_add_quadratic=cfg.data.os.nuisance_add_quadratic,
            nuisance_detrend=cfg.data.os.nuisance_detrend,
            nuisance_high_pass=cfg.data.os.nuisance_high_pass,
            nuisance_low_pass=cfg.data.os.nuisance_low_pass,
            progress=progress,
        )
    elif mode in {"openneuro_hc", "openneuro"}:
        strict_hc = mode == "openneuro_hc"
        resolved_diagnosis = diagnosis if diagnosis else ("CONTROL" if strict_hc else "")
        resolved_dataset_ids = _parse_openneuro_dataset_ids(
            single_dataset=openneuro_dataset,
            datasets_csv=openneuro_datasets,
        )
        payload = prepare_openneuro_proxy(
            timeseries_root=cfg.data.os.timeseries_dir,
            states=cfg.data.os.states,
            atlas_nodes_options=cfg.template.atlas_nodes_options,
            n_subjects=subjects,
            tr=cfg.data.os.tr,
            min_age=min_age,
            diagnosis=resolved_diagnosis,
            dataset_id=resolved_dataset_ids[0],
            dataset_ids=resolved_dataset_ids,
            snapshot_tag=openneuro_snapshot or None,
            task=openneuro_task,
            strict_hc=strict_hc,
            api_url=openneuro_api_url,
            cache_root=Path(cfg.data.os.root_dir) / "openneuro",
            nuisance_include_compcor=cfg.data.os.nuisance_include_compcor,
            nuisance_compcor_components=cfg.data.os.nuisance_compcor_components,
            nuisance_include_gsr=cfg.data.os.nuisance_include_gsr,
            nuisance_add_derivatives=cfg.data.os.nuisance_add_derivatives,
            nuisance_add_quadratic=cfg.data.os.nuisance_add_quadratic,
            nuisance_detrend=cfg.data.os.nuisance_detrend,
            nuisance_high_pass=cfg.data.os.nuisance_high_pass,
            nuisance_low_pass=cfg.data.os.nuisance_low_pass,
            progress=progress,
        )
        os_stats = payload["os_stats"]
    else:
        raise ValueError(
            "Unsupported mode: "
            f"{mode}. Use 'public_proxy', 'openneuro_hc', 'openneuro', or 'synthetic'."
        )

    result = {
        "mode": mode,
        "etth1_csv": str(etth1_path),
        "os_timeseries_root": str(cfg.data.os.timeseries_dir),
        "os_stats": os_stats,
        "nuisance": {
            "strategy": cfg.data.os.nuisance_strategy,
            "include_compcor": cfg.data.os.nuisance_include_compcor,
            "compcor_components": cfg.data.os.nuisance_compcor_components,
            "include_gsr": cfg.data.os.nuisance_include_gsr,
            "add_derivatives": cfg.data.os.nuisance_add_derivatives,
            "add_quadratic": cfg.data.os.nuisance_add_quadratic,
            "detrend": cfg.data.os.nuisance_detrend,
            "high_pass": cfg.data.os.nuisance_high_pass,
            "low_pass": cfg.data.os.nuisance_low_pass,
        },
    }
    # Backward compatibility keys.
    result["hcp_timeseries_root"] = result["os_timeseries_root"]
    result["hcp_stats"] = result["os_stats"]
    if mode in {"openneuro_hc", "openneuro"}:
        result.update(payload["source"])
    return result
