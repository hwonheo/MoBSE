"""WI-02 창 산출물 → `windows.jsonl` (label 부착 포함).

계획서 §1 이 target 을 못박았다 — "주 target은 AOMIC PIOP1의 `emomatching=0`,
`workingmemory=1` **run identity**다". 즉 label 은 run 의 task entity 에서 나오며,
events.tsv 의 내용이나 군집 결과에서 나오지 않는다.

이 구분이 T11 의 전부다:

* `label_source` 는 `task_metadata` 뿐이다. `manifests.ALLOWED_LABEL_SOURCES` 가
  cluster ID 계열을 이미 거부하지만, 여기서는 **애초에 그런 경로를 만들지 않는다.**
* restingstate 는 bank source 이지 분류 대상이 아니다. label 을 붙이지 않고
  창 레코드도 만들지 않는다 — 만들면 3-class 문제로 조용히 번진다.
* events.tsv 는 provenance 기록용이며, 여기서 feature 나 label 로 들어오지 않는다
  (계획서 §3.2: "events의 task 정답을 회귀한 feature를 classifier에 넣지 않는다").
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from mobse.v2.manifests import ManifestError, RunKey, validate_record
from mobse.v2.features import N_ROI_DEFAULT
from mobse.v2.preprocess import SAMPLES_PER_WINDOW, TARGET_GRID, WINDOW_STARTS

__all__ = [
    "LabelError",
    "CLASS_LABELS",
    "LABEL_SOURCE",
    "NON_CLASSIFICATION_TASKS",
    "label_of",
    "window_key",
    "build_window_records",
]


class LabelError(RuntimeError):
    """label 또는 창 레코드 구성 전제가 깨졌다."""


#: 계획서 §1 — emomatching=0, workingmemory=1. 순서가 곧 class index 다.
CLASS_LABELS: Tuple[str, ...] = ("emomatching", "workingmemory")

#: 유일하게 허용되는 label 출처.
LABEL_SOURCE = "task_metadata"

#: 분류 대상이 아닌 task. bank 학습에만 쓰인다.
NON_CLASSIFICATION_TASKS: Tuple[str, ...] = ("restingstate",)

SCHEMA_VERSION = "wi02-windows-0.1"


def label_of(task: str) -> str:
    """task entity 에서 label 을 정한다.

    Args:
        task: BIDS task entity.

    Returns:
        `CLASS_LABELS` 중 하나.

    Raises:
        LabelError: 분류 대상이 아닌 task 이거나 알 수 없는 task 일 때.
            기본값으로 넘기지 않는다 — 조용히 3-class 로 번지는 경로를 막는다.
    """
    if task in NON_CLASSIFICATION_TASKS:
        raise LabelError(
            f"{task!r} 는 분류 대상이 아니다 (bank source). label 을 붙이지 않는다")
    if task not in CLASS_LABELS:
        raise LabelError(
            f"알 수 없는 task: {task!r}. 허용: {list(CLASS_LABELS)}. "
            "계획서 §1 의 target 은 이 둘뿐이다")
    return task


def class_index(task: str) -> int:
    """label 의 class index. emomatching=0, workingmemory=1."""
    return CLASS_LABELS.index(label_of(task))


def window_key(run_key: str, window_index: int) -> str:
    """`<run_key>#win-<n>` 형식의 창 식별자.

    run_key 는 '/' 로 나뉘므로 구분자를 '#' 로 둔다.

    Raises:
        ManifestError: run_key 형식이 어긋나면.
        LabelError: 창 index 가 범위를 벗어나면.
    """
    RunKey.parse(run_key)  # 형식 검증 — 실패하면 ManifestError
    if not 0 <= window_index < len(WINDOW_STARTS):
        raise LabelError(
            f"창 index 가 범위를 벗어났다: {window_index} "
            f"(0..{len(WINDOW_STARTS) - 1})")
    return f"{run_key}#win-{window_index}"


def build_window_records(header: Mapping[str, Any],
                         runs: Sequence[Mapping[str, Any]],
                         *, n_roi: int = N_ROI_DEFAULT
                         ) -> List[Dict[str, Any]]:
    """WI-02 manifest 의 run 레코드에서 `windows` 스키마 레코드를 만든다.

    QC 를 통과한(`status == "ok"`) run 만 대상이다. 제외된 run 의 창은 만들지
    않는다 — 만들어 두고 나중에 거르면 "몇 개는 남아 있더라"가 생긴다.

    Args:
        header: WI-02 manifest 헤더 (`task` 를 여기서 읽는다).
        runs: run 레코드 목록.
        n_roi: ROI 수. 창 배열의 둘째 축과 대조한다.

    Returns:
        `manifests.SCHEMAS["windows"]` 를 만족하는 레코드 목록.

    Raises:
        LabelError: 분류 대상이 아닌 task, 창 수가 4개가 아닌 run,
            표본 수·ROI 수 불일치.
        ManifestError: 생성한 레코드가 스키마를 위반하면 (자기 검증).
    """
    task = str(header.get("task") or "")
    label = label_of(task)  # rest 면 여기서 실패한다

    out: List[Dict[str, Any]] = []
    for run in runs:
        if run.get("status") != "ok":
            continue
        run_key = str(run.get("run_key") or "")
        windows = run.get("windows") or []
        if len(windows) != len(WINDOW_STARTS):
            raise LabelError(
                f"{run_key}: 창이 {len(windows)}개다 (기대 {len(WINDOW_STARTS)}). "
                "부분 창으로 진행하지 않는다")

        for index, window in enumerate(windows):
            shape = list(window.get("shape") or [])
            if shape != [SAMPLES_PER_WINDOW, n_roi]:
                raise LabelError(
                    f"{run_key} 창 {index}: 형상 {shape} != "
                    f"[{SAMPLES_PER_WINDOW}, {n_roi}]")
            start = float(window["start_sec"])
            expected_start = float(WINDOW_STARTS[index])
            if abs(start - expected_start) > 1e-9:
                raise LabelError(
                    f"{run_key} 창 {index}: 시작 {start} != {expected_start}")

            record = {
                "schema_version": SCHEMA_VERSION,
                "window_key": window_key(run_key, index),
                "run_key": run_key,
                "start_sec": start,
                "end_sec": start + SAMPLES_PER_WINDOW * TARGET_GRID,
                "source_frame_range": list(window["source_frame_range"]),
                "target_grid": float(TARGET_GRID),
                "n_samples": int(SAMPLES_PER_WINDOW),
                "n_roi": int(n_roi),
                "qc_flags": list(run.get("qc_decision", {}).get("all_reasons", [])),
                "data_sha256": str(window["sha256"]),
                "observed_label": label,
                "label_source": LABEL_SOURCE,
            }
            validate_record("windows", record)  # 자기 검증
            out.append(record)
    return out
