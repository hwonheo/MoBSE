"""재설계 v2 runtime config 스키마와 검증기 (WI-05 산출물).

설계 원칙은 셋이다.

1. **조용한 default 금지** (지침서 T02). 미지의 키는 오타로 보고 거부한다.
   빠진 필수 키도 거부한다. "없으면 알아서" 경로를 두지 않는다.
2. **코드 상수가 단일 출처.** seed·창 경계·grid 같은 값은 각 모듈의 상수가
   정본이고, config 는 그것을 *다시 적어* 잠근다. 둘이 어긋나면 실패시킨다.
   config 가 상수를 덮어쓰지 못하게 하려는 것이다.
3. **config hash 가 release_id 에 들어간다.** 따라서 직렬화가 결정적이어야
   한다(`canonical_json`). dict 순서·부동소수 표기에 따라 해시가 흔들리면
   release 식별자가 흔들린다.

사용:
    from mobse.v2.config import load_config, config_hash, release_id
    cfg = load_config(Path("configs/redesign_v1/primary.yaml"))
    rid = release_id("20260917", code_hash, config_hash(cfg))
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

from mobse.v2 import preprocess, splits, statistics, templates, train

__all__ = [
    "ConfigError",
    "FieldSpec",
    "SCHEMA",
    "validate_config",
    "load_config",
    "canonical_json",
    "config_hash",
    "release_id",
    "RELEASE_ID_PATTERN",
]


class ConfigError(ValueError):
    """config 가 스키마를 위반했다. 호출자는 이것을 삼키지 않는다."""


RELEASE_ID_PATTERN = re.compile(r"^\d{8}_[0-9a-f]{12}_[0-9a-f]{8}$")


@dataclass(frozen=True)
class FieldSpec:
    """config 한 필드의 계약.

    Attributes:
        types: 허용 파이썬 타입.
        locked_to: 코드 상수 값. None 이 아니면 config 값이 이것과 같아야 한다.
        choices: 허용 값 집합 (None 이면 제한 없음).
        check: 추가 술어. 실패 시 메시지를 돌려주고, 통과하면 None 을 돌려준다.
        doc: 이 필드가 왜 있는지.
    """

    types: Tuple[type, ...]
    doc: str
    locked_to: Any = None
    choices: Tuple[Any, ...] | None = None
    check: Callable[[Any], str | None] | None = None


def _positive(value: Any) -> str | None:
    return None if value > 0 else "0보다 커야 한다"


def _probability(value: Any) -> str | None:
    return None if 0.0 <= value <= 1.0 else "[0, 1] 범위여야 한다"


def _as_tuple(value: Any) -> Any:
    """YAML 이 list 로 읽어 오는 값을 상수(tuple)와 비교 가능하게 만든다."""
    return tuple(value) if isinstance(value, list) else value


# 스키마는 평면 dotted key 로 둔다. 중첩 dict 를 쓰면 "어느 깊이까지 unknown 을
# 거부할 것인가"가 애매해져 조용한 default 가 다시 생긴다.
SCHEMA: Dict[str, FieldSpec] = {
    # --- 식별 ---
    "meta.name": FieldSpec((str,), "config 이름. release 경로에 쓰지 않는다(해시를 쓴다)."),
    "meta.protocol_version": FieldSpec((str,), "이 config 가 따르는 계획서 판본", choices=("1.1",)),
    "meta.role": FieldSpec(
        (str,), "이 config 가 담당하는 단계",
        choices=("pilot", "main", "external", "sensitivity", "null"),
    ),
    # --- 시간축 (preprocess.py 가 정본) ---
    "timing.analysis_start_s": FieldSpec((int, float), "원 acquisition clock 기준 분석 시작", locked_to=preprocess.ANALYSIS_START),
    "timing.analysis_end_s": FieldSpec((int, float), "분석 끝 (배타)", locked_to=preprocess.ANALYSIS_END),
    "timing.target_grid_s": FieldSpec((int, float), "재표본 격자", locked_to=preprocess.TARGET_GRID),
    "timing.window_len_s": FieldSpec((int, float), "고정 창 길이", locked_to=preprocess.WINDOW_LEN),
    "timing.window_starts_s": FieldSpec((list, tuple), "4개 창 시작", locked_to=preprocess.WINDOW_STARTS),
    "timing.samples_per_window": FieldSpec((int,), "창당 표본 수", locked_to=preprocess.SAMPLES_PER_WINDOW),
    # --- QC (preprocess.py 가 정본) ---
    "qc.fd_mean_max": FieldSpec((int, float), "run 평균 FD 상한", locked_to=preprocess.FD_MEAN_MAX),
    "qc.fd_spike": FieldSpec((int, float), "spike 판정 FD", locked_to=preprocess.FD_SPIKE),
    "qc.fd_spike_ratio_max": FieldSpec((int, float), "spike 비율 상한", locked_to=preprocess.FD_SPIKE_RATIO_MAX),
    "qc.min_residual_dof": FieldSpec((int,), "nuisance 회귀 후 최소 자유도", locked_to=preprocess.MIN_RESIDUAL_DOF),
    # --- 분할 (splits.py 가 정본) ---
    "splits.pilot_seed": FieldSpec((int,), "pilot 표집 seed", locked_to=splits.PILOT_SEED),
    "splits.outer_seed": FieldSpec((int,), "outer 5-fold seed", locked_to=splits.OUTER_SEED),
    "splits.inner_seed_base": FieldSpec((int,), "inner seed = base + fold", locked_to=splits.INNER_SEED_BASE),
    "splits.external_seed": FieldSpec((int,), "외부 코호트 seed", locked_to=splits.EXTERNAL_SEED),
    "splits.pilot_cap": FieldSpec((int,), "pilot 상한", locked_to=splits.PILOT_CAP),
    "splits.pilot_fraction": FieldSpec((int, float), "pilot 비율", locked_to=splits.PILOT_FRACTION),
    "splits.n_outer_folds": FieldSpec((int,), "outer fold 수", choices=(5,)),
    "splits.n_inner_folds": FieldSpec((int,), "inner fold 수", choices=(3,)),
    # --- bank / null (templates.py 가 정본) ---
    "bank.k": FieldSpec((int,), "K-means K", locked_to=templates.K_DEFAULT),
    "bank.n_init": FieldSpec((int,), "K-means 재시작 수", locked_to=templates.N_INIT),
    "bank.max_iter": FieldSpec((int,), "K-means 최대 반복", locked_to=templates.MAX_ITER),
    "bank.edge_density": FieldSpec((int, float), "양의 상위 edge 비율", locked_to=templates.EDGE_DENSITY),
    "bank.seed_base": FieldSpec((int,), "bank seed = base + 100*outer + inner", locked_to=templates.BANK_SEED_BASE),
    "bank.null_seed": FieldSpec((int,), "joint ROI permutation 주 seed", locked_to=templates.NULL_SEED_PRIMARY),
    "bank.null_seeds_sensitivity": FieldSpec((list, tuple), "민감도 seed", locked_to=templates.NULL_SEEDS_SENSITIVITY),
    "bank.pca_components": FieldSpec((int,), "PCA 차원", choices=(10,)),
    # --- 학습 (train.py 가 정본) ---
    "train.learning_rates": FieldSpec((list, tuple), "grid 축 1", locked_to=train.LEARNING_RATES),
    "train.dropouts": FieldSpec((list, tuple), "grid 축 2", locked_to=train.DROPOUTS),
    "train.weight_decays": FieldSpec((list, tuple), "grid 축 3", locked_to=train.WEIGHT_DECAYS),
    "train.batch_size": FieldSpec((int,), "배치 크기", locked_to=train.BATCH_SIZE),
    "train.max_epochs": FieldSpec((int,), "epoch 상한 (P8: 200)", locked_to=train.MAX_EPOCHS),
    "train.min_updates": FieldSpec((int,), "최소 optimizer update (P8)", locked_to=train.MIN_UPDATES),
    "train.patience": FieldSpec((int,), "early stopping 인내", locked_to=train.PATIENCE),
    "train.min_delta": FieldSpec((int, float), "개선 판정 하한 (엄격 부등호)", locked_to=train.MIN_DELTA),
    "train.grad_clip": FieldSpec((int, float), "gradient clipping", locked_to=train.GRAD_CLIP),
    "train.model_seeds": FieldSpec((list, tuple), "3-seed ensemble", locked_to=train.MODEL_SEEDS),
    "train.cells": FieldSpec((list, tuple), "2x2 cell 이름", locked_to=train.CELLS),
    # --- 통계 (statistics.py 가 정본) ---
    "stats.bootstrap_seed": FieldSpec((int,), "paired group bootstrap seed", locked_to=statistics.BOOTSTRAP_SEED),
    "stats.n_bootstrap": FieldSpec((int,), "bootstrap 반복", locked_to=statistics.N_BOOTSTRAP),
    "stats.familywise_pct": FieldSpec((list, tuple), "주 contrast 2개용 97.5% CI", locked_to=statistics.FAMILYWISE_PCT),
    "stats.nominal_pct": FieldSpec((list, tuple), "보조 지표용 95% CI", locked_to=statistics.NOMINAL_PCT),
    "stats.threshold": FieldSpec((int, float), "분류 임계", locked_to=statistics.THRESHOLD),
    "stats.delta": FieldSpec((int, float), "실질 동등 한계 (계획서 §2)", choices=(0.02,)),
    # --- 경로 (glob fallback 금지, U20) ---
    "paths.source_manifest": FieldSpec((str,), "run 원본 manifest — 명시 경로만"),
    "paths.split_manifest": FieldSpec((str,), "분할 manifest — 명시 경로만"),
    "paths.atlas_spec": FieldSpec((str,), "atlas 사양 — 명시 경로만"),
    "paths.output_root": FieldSpec((str,), "release 출력 루트"),
    # --- 실행 ---
    "runtime.backend": FieldSpec((str,), "그래프 연산 backend. dense 고정 (U21)", choices=("dense",)),
    "runtime.device": FieldSpec((str,), "연산 장치", choices=("cpu", "cuda")),
    "runtime.deterministic": FieldSpec((bool,), "결정적 실행 강제", choices=(True,)),
    "runtime.num_workers": FieldSpec((int,), "DataLoader worker 수", check=lambda v: None if v >= 0 else "음수 불가"),
}


def _flatten(mapping: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
    """중첩 dict 를 dotted key 로 편다."""
    flat: Dict[str, Any] = {}
    for key, value in mapping.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{path}."))
        else:
            flat[path] = value
    return flat


def validate_config(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """config 를 스키마에 대해 검증하고 평면 dict 를 돌려준다.

    Args:
        raw: 중첩 dict (보통 YAML 파싱 결과).

    Returns:
        dotted key -> 값 의 평면 dict.

    Raises:
        ConfigError: 누락·미지 키·타입 불일치·상수 불일치·범위 위반.
            모든 위반을 한 번에 모아 보고한다 — 고칠 때마다 다시 돌리지 않게.
    """
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config 최상위가 mapping 이 아니다: {type(raw).__name__}")

    flat = _flatten(raw)
    problems: List[str] = []

    unknown = sorted(set(flat) - set(SCHEMA))
    for key in unknown:
        problems.append(f"미지의 키 {key!r} — 오타이거나 스키마에 없는 항목이다")

    missing = sorted(set(SCHEMA) - set(flat))
    for key in missing:
        problems.append(f"필수 키 누락 {key!r} ({SCHEMA[key].doc})")

    for key in sorted(set(flat) & set(SCHEMA)):
        spec = SCHEMA[key]
        value = flat[key]
        # bool 은 int 의 하위형이라 명시적으로 갈라 준다.
        if isinstance(value, bool) and bool not in spec.types:
            problems.append(f"{key}: bool 은 허용되지 않는다 (허용: {[t.__name__ for t in spec.types]})")
            continue
        if not isinstance(value, spec.types):
            problems.append(
                f"{key}: 타입 {type(value).__name__} — 허용 {[t.__name__ for t in spec.types]}"
            )
            continue
        if spec.locked_to is not None:
            expected = _as_tuple(spec.locked_to)
            actual = _as_tuple(value)
            if actual != expected:
                problems.append(
                    f"{key}: 코드 상수와 불일치 (config={actual!r}, 코드={expected!r}). "
                    "config 는 상수를 덮어쓸 수 없다"
                )
                continue
        if spec.choices is not None and _as_tuple(value) not in spec.choices:
            problems.append(f"{key}: 허용되지 않는 값 {value!r} (허용: {list(spec.choices)})")
            continue
        if spec.check is not None:
            message = spec.check(value)
            if message:
                problems.append(f"{key}: {message}")

    if problems:
        raise ConfigError(
            f"config 위반 {len(problems)}건:\n  - " + "\n  - ".join(problems)
        )
    return flat


def load_config(path: Path) -> Dict[str, Any]:
    """YAML config 를 읽어 검증한다.

    Args:
        path: config 파일 경로. 존재하지 않으면 실패한다 (탐색하지 않는다).

    Returns:
        검증된 평면 config.

    Raises:
        ConfigError: 파일 부재 또는 스키마 위반.
    """
    import yaml  # 지연 import — config 를 쓰지 않는 경로에 의존성을 강제하지 않는다

    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config 파일 없음: {path} (자동 탐색하지 않는다 — U20)")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 파싱 실패: {path}: {exc}") from exc
    if raw is None:
        raise ConfigError(f"config 가 비어 있다: {path}")
    return validate_config(raw)


def canonical_json(flat: Mapping[str, Any]) -> str:
    """해시용 결정적 직렬화.

    키를 정렬하고, list 를 tuple 과 구분 없이 list 로 통일하며, 구분자를
    고정한다. 이 문자열이 바뀌면 release_id 가 바뀐다.
    """

    def normalize(value: Any) -> Any:
        if isinstance(value, tuple):
            return [normalize(v) for v in value]
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if isinstance(value, float) and value.is_integer():
            return value  # 1.0 을 1 로 접지 않는다 — 타입 정보가 해시에 남게
        return value

    payload = {k: normalize(flat[k]) for k in sorted(flat)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def config_hash(flat: Mapping[str, Any], length: int = 8) -> str:
    """config 의 sha256 앞 `length` 자리. release_id 의 마지막 성분."""
    if length < 4:
        raise ConfigError(f"config_hash length 가 너무 짧다: {length}")
    return hashlib.sha256(canonical_json(flat).encode("utf-8")).hexdigest()[:length]


def release_id(date: str, code_hash: str, cfg_hash: str) -> str:
    """`YYYYMMDD_<code12>_<config8>` 을 만든다 (지침서 §3).

    Args:
        date: `YYYYMMDD`.
        code_hash: 코드 해시. 앞 12자리를 쓴다.
        cfg_hash: `config_hash` 결과. 앞 8자리를 쓴다.

    Raises:
        ConfigError: 형식이 어긋나면.
    """
    if not re.fullmatch(r"\d{8}", date):
        raise ConfigError(f"date 는 YYYYMMDD 여야 한다: {date!r}")
    for name, value in (("code_hash", code_hash), ("cfg_hash", cfg_hash)):
        if not re.fullmatch(r"[0-9a-f]+", value or ""):
            raise ConfigError(f"{name} 는 소문자 16진 문자열이어야 한다: {value!r}")
    if len(code_hash) < 12:
        raise ConfigError(f"code_hash 가 12자리 미만이다: {code_hash!r}")
    if len(cfg_hash) < 8:
        raise ConfigError(f"cfg_hash 가 8자리 미만이다: {cfg_hash!r}")
    rid = f"{date}_{code_hash[:12]}_{cfg_hash[:8]}"
    if not RELEASE_ID_PATTERN.fullmatch(rid):  # pragma: no cover - 위 검사로 도달 불가
        raise ConfigError(f"release_id 형식 위반: {rid}")
    return rid
