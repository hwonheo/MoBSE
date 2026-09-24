"""Artifact 스키마와 provenance — 지침서 §2 의 계약을 코드로 고정한다.

의존성은 표준 라이브러리 뿐이다.

지침서 §2 는 11종 artifact 의 필수 필드와 검증 규칙을 표로 규정한다. 그 표를
문서로만 두면 구현이 조용히 어긋나므로 여기서 기계가 읽을 수 있는 형태로 못박고,
쓰기 시점에 검증한다. 필드가 빠지거나 타입이 맞지 않으면 **실패한다**.

핵심 규칙:

* `run_key` 는 ``dataset/subject/session/task/run/acquisition`` 이며 없는 BIDS
  entity 도 정해진 빈값으로 직렬화한다. 조용히 합치지 않는다.
* `canonical_subject` 는 **dataset prefix 를 포함해야 한다**. PIOP1/PIOP2 가 같은
  ``sub-0001…`` 네임스페이스를 쓰기 때문이다(차단 항목 U17). prefix 가 없으면 실패한다.
* `release_id` 는 ``YYYYMMDD_<short-code-hash>_<config-hash-prefix>`` 다.
* 같은 release 결과를 덮어쓰지 않는다. 실패 재시도는 attempt 번호를 붙인다.
* 경로·entity 에 개인정보를 추가하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "v2.0"
EMPTY_ENTITY = "na"
RUN_KEY_FIELDS = ("dataset", "subject", "session", "task", "run", "acquisition")
RELEASE_ID_RE = re.compile(r"^\d{8}_[0-9a-f]{6,16}_[0-9a-zA-Z]{3,16}$")
SUBJECT_RE = re.compile(r"^(?P<dataset>[A-Za-z0-9]+):(?P<subject>sub-[A-Za-z0-9]+)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """스키마 위반. 조용한 기본값으로 넘어가지 않는다."""


# --------------------------------------------------------------------------- #
# 키
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RunKey:
    """BIDS entity 로 구성한 run 식별자. 없는 entity 는 `EMPTY_ENTITY` 다."""

    dataset: str
    subject: str
    session: str = EMPTY_ENTITY
    task: str = EMPTY_ENTITY
    run: str = EMPTY_ENTITY
    acquisition: str = EMPTY_ENTITY

    def __post_init__(self) -> None:
        for f in RUN_KEY_FIELDS:
            v = getattr(self, f)
            if not v:
                raise ManifestError(f"run_key 의 {f} 가 비어 있다. 빈값은 {EMPTY_ENTITY!r} 로 쓴다")
            if "/" in v:
                raise ManifestError(f"run_key 의 {f} 에 '/' 가 들어갈 수 없다: {v!r}")

    def __str__(self) -> str:
        return "/".join(getattr(self, f) for f in RUN_KEY_FIELDS)

    @classmethod
    def parse(cls, text: str) -> "RunKey":
        parts = text.split("/")
        if len(parts) != len(RUN_KEY_FIELDS):
            raise ManifestError(
                f"run_key 는 {len(RUN_KEY_FIELDS)} 개 필드여야 한다: {text!r}")
        return cls(*parts)

    @property
    def canonical_subject(self) -> str:
        """dataset prefix 를 붙인 subject 키 (U17)."""
        return f"{self.dataset}:{self.subject}"


def validate_canonical_subject(value: str) -> str:
    """dataset prefix 가 붙은 subject 키인지 확인한다.

    Raises:
        ManifestError: prefix 가 없으면. PIOP1/PIOP2 가 같은 ``sub-0001…``
            네임스페이스를 쓰므로 prefix 없는 키는 216건의 위양성을 만든다.
    """
    if not SUBJECT_RE.match(value):
        raise ManifestError(
            f"canonical_subject 에 dataset prefix 가 없다: {value!r} "
            "(예: 'ds002785:sub-0001'). 차단 항목 U17")
    return value


def make_release_id(date: str, code_hash: str, config_hash: str) -> str:
    """``YYYYMMDD_<code>_<config>`` 형식의 release_id 를 만든다."""
    rid = f"{date}_{code_hash[:12]}_{config_hash[:8]}"
    if not RELEASE_ID_RE.match(rid):
        raise ManifestError(f"release_id 형식 위반: {rid!r}")
    return rid


# --------------------------------------------------------------------------- #
# 스키마
# --------------------------------------------------------------------------- #

_STR, _INT, _FLOAT, _BOOL, _LIST, _DICT = "str", "int", "float", "bool", "list", "dict"
_TYPES = {_STR: str, _INT: int, _FLOAT: (int, float), _BOOL: bool,
          _LIST: list, _DICT: dict}

#: artifact 이름 → (필수 필드 → 타입). 지침서 §2 표를 그대로 옮긴 것이다.
SCHEMAS: Dict[str, Dict[str, str]] = {
    "source_runs": {
        "schema_version": _STR, "run_key": _STR, "dataset": _STR,
        "canonical_subject": _STR, "group_id": _STR, "task": _STR,
        "source_path": _STR, "source_sha256": _STR,
        "native_tr": _FLOAT, "n_volumes": _INT,
        "derivative_start_sec": _FLOAT, "discarded_volumes": _INT,
        "event_origin": _STR, "atlas_id": _STR, "atlas_hash": _STR,
        "roi_order_hash": _STR,
    },
    "preprocessing": {
        "schema_version": _STR, "run_key": _STR, "code_hash": _STR,
        "env_hash": _STR, "config_hash": _STR, "nuisance_columns": _LIST,
        "design_rank": _INT, "residual_dof": _INT, "filter_spec": _DICT,
        "resample_spec": _DICT, "original_grid": _DICT, "derived_grid": _DICT,
        "output_sha256": _STR,
    },
    "windows": {
        "schema_version": _STR, "window_key": _STR, "run_key": _STR,
        "start_sec": _FLOAT, "end_sec": _FLOAT, "source_frame_range": _LIST,
        "target_grid": _FLOAT, "n_samples": _INT, "n_roi": _INT,
        "qc_flags": _LIST, "data_sha256": _STR,
        "observed_label": _STR, "label_source": _STR,
    },
    "exclusions": {
        "schema_version": _STR, "key": _STR, "key_level": _STR, "stage": _STR,
        "all_reasons": _LIST, "primary_reason": _STR, "rule_version": _STR,
    },
    "subjects": {
        "schema_version": _STR, "canonical_subject": _STR, "group_id": _STR,
        "cohort": _STR, "eligible": _BOOL, "assignment": _STR,
        "assignment_reason": _STR,
    },
    "fit_manifest": {
        "schema_version": _STR, "fit_id": _STR, "parent_release": _STR,
        "role": _STR, "cell": _STR, "folds": _DICT, "model_seed": _INT,
        "bank_seed": _INT, "null_seed": _INT, "fit_subjects": _LIST,
        "scaler_id": _STR, "pca_id": _STR, "bank_id": _STR,
        "code_hash": _STR, "env_hash": _STR, "config_hash": _STR,
        "source_hash": _STR, "split_hash": _STR,
    },
    "window_predictions": {
        "schema_version": _STR, "canonical_subject": _STR, "group_id": _STR,
        "run_key": _STR, "window_key": _STR, "truth": _INT, "p_class1": _FLOAT,
        "cell": _STR, "model_seed": _INT, "scope": _STR,
        "checkpoint_sha256": _STR, "fit_id": _STR,
    },
    # 결정 14 4c-i — S 후보 fit 한 칸의 창 예측. A–D·NG·SG 의 window_predictions 와
    # 따로 둔다: cell 자리가 없고(후보·설정이 식별자), logistic 은 seed 가 없다.
    # 2×2 집계(evaluate)로 새어 들어가지 않게 artifact 이름부터 다르다 (구현 선택).
    "s_window_predictions": {
        "schema_version": _STR, "canonical_subject": _STR, "group_id": _STR,
        "run_key": _STR, "window_key": _STR, "truth": _INT, "p_class1": _FLOAT,
        "candidate": _STR, "setting_id": _STR, "scope": _STR,
        "model_sha256": _STR, "s_fit_id": _STR,
    },
    "run_predictions": {
        "schema_version": _STR, "canonical_subject": _STR, "run_key": _STR,
        "truth": _INT, "ensemble_p": _FLOAT, "n_windows": _INT, "n_seeds": _INT,
        "threshold": _FLOAT, "prediction": _INT, "cell": _STR,
    },
}

#: 값이 SHA256 hex 여야 하는 필드.
_HASH_FIELDS = {"source_sha256", "output_sha256", "data_sha256",
                "checkpoint_sha256", "model_sha256", "atlas_hash", "roi_order_hash"}

#: 허용된 label_source. cluster ID 를 label 로 쓰는 것을 막는다 (T11).
ALLOWED_LABEL_SOURCES = {"task_metadata", "bids_entity"}

#: 허용된 cell 이름.
ALLOWED_CELLS = {"A", "B", "C", "D"}

#: §6 구조 비교 이름 (결정 14). `models.COMPARATOR_SPEC`·`baselines.COMPARATOR_ORDER`
#: 와 같아야 한다 (시험이 고정). fit 단위 산출물에서만 cell 자리에 올 수 있다.
COMPARATOR_CELLS = {"NG", "SG"}

#: fit 한 번이 만드는 산출물 — 여기서만 구조 비교 이름을 받는다. run·subject 집계와
#: 2×2 요인 분석(run_predictions 등)은 A–D 만 받는다 (구현 선택, 결정 14 4단계).
FIT_SCOPED_ARTIFACTS = frozenset({"fit_manifest", "window_predictions"})
FIT_CELLS = ALLOWED_CELLS | COMPARATOR_CELLS


def validate_record(artifact: str, record: Mapping[str, Any]) -> None:
    """한 레코드가 해당 artifact 스키마를 만족하는지 확인한다.

    Raises:
        ManifestError: 알 수 없는 artifact, 필수 필드 누락, 타입 불일치,
            SHA256 형식 위반, dataset prefix 없는 subject, 금지된 label_source,
            알 수 없는 cell.
    """
    if artifact not in SCHEMAS:
        raise ManifestError(f"알 수 없는 artifact: {artifact!r}. "
                            f"허용: {sorted(SCHEMAS)}")
    spec = SCHEMAS[artifact]
    missing = [k for k in spec if k not in record]
    if missing:
        raise ManifestError(f"{artifact}: 필수 필드 누락 {missing}")

    for key, kind in spec.items():
        value = record[key]
        if value is None:
            raise ManifestError(f"{artifact}.{key} 가 None 이다. "
                                "미상은 명시적 실패로 다룬다")
        if not isinstance(value, _TYPES[kind]) or (kind != _BOOL and isinstance(value, bool)):
            raise ManifestError(
                f"{artifact}.{key} 타입 불일치: {kind} 를 기대했으나 "
                f"{type(value).__name__}")

    for key in _HASH_FIELDS & set(record):
        if not SHA256_RE.match(str(record[key])):
            raise ManifestError(f"{artifact}.{key} 가 SHA256 hex 가 아니다: "
                                f"{record[key]!r}")

    if "canonical_subject" in record:
        validate_canonical_subject(str(record["canonical_subject"]))
    if "run_key" in record:
        RunKey.parse(str(record["run_key"]))
    if "label_source" in record and record["label_source"] not in ALLOWED_LABEL_SOURCES:
        raise ManifestError(
            f"label_source 가 허용 목록에 없다: {record['label_source']!r}. "
            f"허용: {sorted(ALLOWED_LABEL_SOURCES)}. cluster ID 를 label 로 쓸 수 없다 (T11)")
    allowed_cells = FIT_CELLS if artifact in FIT_SCOPED_ARTIFACTS else ALLOWED_CELLS
    if "cell" in record and record["cell"] not in allowed_cells:
        raise ManifestError(f"알 수 없는 cell: {record['cell']!r} "
                            f"({artifact} 허용: {sorted(allowed_cells)})")


# --------------------------------------------------------------------------- #
# 직렬화
# --------------------------------------------------------------------------- #


def write_jsonl(path: Path, artifact: str, records: Iterable[Mapping[str, Any]],
                *, overwrite: bool = False) -> Dict[str, Any]:
    """검증한 레코드를 JSONL 로 쓴다.

    Args:
        overwrite: False(기본)이고 파일이 이미 있으면 실패한다. 지침서 §2 는
            같은 release 결과를 덮어쓰지 않는다고 규정한다.

    Returns:
        ``{"path", "n_records", "sha256", "unique_keys"}``.

    Raises:
        ManifestError: 스키마 위반, 키 중복, 기존 파일 덮어쓰기 시도.
    """
    path = Path(path)
    if path.exists() and not overwrite:
        raise ManifestError(f"이미 존재한다: {path}. 같은 release 를 덮어쓰지 않는다. "
                            "재시도는 attempt 번호를 붙인다")
    key_fields = _primary_key_fields(artifact)
    seen: Dict[str, int] = {}
    rows: List[str] = []
    for i, rec in enumerate(records):
        validate_record(artifact, rec)
        if key_fields:
            k = "|".join(str(rec[f]) for f in key_fields)
            if k in seen:
                raise ManifestError(
                    f"{artifact}: {'+'.join(key_fields)} 중복 {k!r} "
                    f"(행 {seen[k]} 와 {i})")
            seen[k] = i
        rows.append(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    blob = "\n".join(rows) + ("\n" if rows else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(blob, encoding="utf-8")
    return {"path": str(path), "n_records": len(rows),
            "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "unique_keys": len(seen)}


def read_jsonl(path: Path, artifact: Optional[str] = None) -> List[Dict[str, Any]]:
    """JSONL 을 읽는다. `artifact` 를 주면 각 레코드를 검증한다."""
    records = [json.loads(line) for line in
               Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if artifact:
        for rec in records:
            validate_record(artifact, rec)
    return records


def _primary_key_fields(artifact: str) -> Optional[Tuple[str, ...]]:
    """중복 검출에 쓸 키 필드 조합. 매핑에 없으면 ``None``.

    `exclusions` 는 한 파일에 여러 stage(run/window/subject 단계)의 기록이
    섞일 수 있으므로 `key` 하나로는 유일하지 않다. 복합키를 쓴다 — 개정 E16.
    """
    return {
        "source_runs": ("run_key",),
        "preprocessing": ("run_key",),
        "windows": ("window_key",),
        "subjects": ("canonical_subject",),
        "exclusions": ("stage", "key_level", "key"),
        # WI-07 산출물. 완료기준 행 수(expected_prediction_rows)가
        # window = N × task × 창 × seed × cell, run = N × task × cell 이므로
        # 한 파일 안의 유일 단위는 아래와 같다. scope 는 파일 단위로 고정이라
        # 키에 넣지 않는다 — 넣으면 키가 넓어져 중복을 놓친다.
        "window_predictions": ("cell", "model_seed", "window_key"),
        "s_window_predictions": ("candidate", "setting_id", "window_key"),
        "run_predictions": ("cell", "run_key"),
    }.get(artifact)


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #


def sha256_file(path: Path) -> str:
    """파일의 SHA256. 없으면 실패한다 — 미상을 빈 문자열로 넘기지 않는다."""
    p = Path(path)
    if not p.is_file():
        raise ManifestError(f"해시할 파일이 없다: {p}")
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    """정렬된 JSON 직렬화의 SHA256. dict 순서에 의존하지 않는다."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def code_hash(paths: Sequence[Path]) -> str:
    """경로 목록의 내용 해시. 파일명 정렬 후 각 파일 해시를 다시 해시한다.

    해시에는 **파일명만** 넣는다. 저장소 위치(절대경로 prefix)를 넣으면 같은
    코드를 다른 디렉터리에서 돌렸을 때 값이 달라진다 (E19, 2026-09-23: 모듈
    17개 sha 가 전부 같은데 code_hash 만 바뀐 사고).

    Raises:
        ManifestError: 서로 다른 경로에 같은 파일명이 있어 구분할 수 없을 때.
    """
    items = sorted((Path(p).name, Path(p)) for p in paths)
    names = [n for n, _ in items]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ManifestError(f"code_hash: 파일명이 겹친다 {dup}")
    digests = [f"{n}:{sha256_file(q)}" for n, q in items]
    return hashlib.sha256("\n".join(digests).encode("utf-8")).hexdigest()


def fit_id(*, role: str, cell: str, outer_fold: int, inner_fold: int,
           model_seed: int, config_id: int, split_hash: str, config_hash: str) -> str:
    """재현 가능한 fit 식별자. 같은 입력이면 항상 같은 값이다.

    ``cell`` 은 A–D 또는 §6 구조 비교(NG·SG) 이름이다. ``config_id`` 는 공통 grid
    번호(0–7)다 — inner grid 는 같은 (cell, fold, seed=42) 에서 8 개 config 를
    학습하므로, 이것이 빠지면 서로 다른 fit 이 같은 식별자를 갖는다 (rev42 정정).
    접두는 바꾸지 않는다; config_id 는 해시 payload 에만 들어간다.
    """
    if cell not in FIT_CELLS:
        raise ManifestError(f"알 수 없는 cell: {cell!r}")
    if isinstance(config_id, bool) or not isinstance(config_id, int) or config_id < 0:
        raise ManifestError(f"config_id 는 0 이상 정수여야 한다: {config_id!r}")
    payload = {"role": role, "cell": cell, "outer_fold": outer_fold,
               "inner_fold": inner_fold, "model_seed": model_seed,
               "config_id": config_id,
               "split_hash": split_hash, "config_hash": config_hash}
    return f"{role}-{cell}-o{outer_fold}i{inner_fold}s{model_seed}-{sha256_obj(payload)[:12]}"


#: S 후보 이름. `baselines.CANDIDATE_ORDER` 와 같아야 한다 (시험이 고정).
S_CANDIDATES = ("S1_roi_mean_var_logreg", "S2_roi_mean_var_mlp",
                "S3_fc_fisher_z_logreg", "S4_fc_fisher_z_mlp")


def s_fit_id(*, role: str, candidate: str, setting_id: str, outer_fold: int,
             inner_fold: int, model_seed: Optional[int], split_hash: str,
             config_hash: str) -> str:
    """S 후보 fit 한 칸의 재현 가능한 식별자 (결정 14 4c-i).

    후보·설정·seed 가 모두 payload 에 들어간다 — 같은 fold 의 grid 16 설정(logistic)
    또는 8 config(MLP)가 서로 다른 식별자를 갖는다 (rev42 `fit_id` 정정과 같은 이유).
    logistic 은 seed 가 없어 ``None`` 이다.
    """
    if candidate not in S_CANDIDATES:
        raise ManifestError(f"알 수 없는 S 후보: {candidate!r}")
    if model_seed is not None and (isinstance(model_seed, bool)
                                   or not isinstance(model_seed, int)):
        raise ManifestError(f"model_seed 는 정수 또는 None 이어야 한다: {model_seed!r}")
    payload = {"role": role, "candidate": candidate, "setting_id": setting_id,
               "outer_fold": outer_fold, "inner_fold": inner_fold,
               "model_seed": model_seed, "split_hash": split_hash,
               "config_hash": config_hash}
    seed = "na" if model_seed is None else model_seed
    return (f"s-{role}-{candidate[:2]}-o{outer_fold}i{inner_fold}s{seed}-"
            f"{sha256_obj(payload)[:12]}")


def expected_prediction_rows(n_subjects: int, *, n_tasks: int = 2, n_windows: int = 4,
                             n_seeds: int = 3, n_cells: int = 4) -> Dict[str, int]:
    """WI-07 완료기준의 기대 행 수 (지침서 §3)."""
    return {
        "window_predictions": n_subjects * n_tasks * n_windows * n_seeds * n_cells,
        "run_predictions": n_subjects * n_tasks * n_cells,
        "checkpoints": n_cells * 5 * n_seeds,
    }


def assert_no_glob_fallback(resolved: Mapping[str, Optional[str]]) -> None:
    """필수 경로가 모두 명시되었는지 확인한다 (지침서 WI-06, T15).

    Raises:
        ManifestError: None 인 경로가 있으면. 기존 코드가 mtime 최신 파일이나
            glob 최후 항목으로 대체하던 동작(차단 항목 U20)을 금지한다.
    """
    missing = sorted(k for k, v in resolved.items() if not v)
    if missing:
        raise ManifestError(
            f"명시되지 않은 필수 경로: {missing}. glob·mtime 으로 대체하지 않는다 (U20)")
