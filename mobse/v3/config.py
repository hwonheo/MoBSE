"""exploratory v2 (코드 모듈 ``v3``) runtime config 스키마와 검증기 — 결정 33.

설계 원칙은 v1 과 같다. **조용한 default 금지** (미지의 키는 오타로 보고 거부),
**코드 상수가 단일 출처** (config 는 그것을 다시 적어 잠근다), **config hash 가
release_id 에 들어간다**. 해시·release_id·직렬화는 동결된 `mobse.v2.config` 의
것을 그대로 쓴다 — 그 부분은 스키마와 무관하다.

v1 스키마와 다른 곳만 적는다.

* `train.max_epochs`·`train.min_updates` 가 **없다.** v3 의 통화는 update 예산
  하나다 (`train.update_budget`, 결정 31-1·32).
* `train.carry_unit` 이 생겼다 — inner 의 공통 E 를 outer 로 옮기는 단위.
  `"update"` 로 고정한다 (구현 선택 2026-09-30, 설계안 §5.3.2).
* `cells.roi_structures` 가 생겼다. 결정 33 의 칸은 **A–D × 2 구조 = 8 칸**이므로
  정확히 두 개여야 한다. *어느* 둘인지는 결정 33 이 정하지 않았으므로 여기서도
  고르지 않는다 — config 파일이 고르고, 검증기는 개수와 이름만 본다.
* `nulls.*` 이 생겼다 — 세 종류 × M=20 (결정 28-3·33). 절 이름이 `null` 이
  아닌 이유: YAML 은 따옴표 없는 ``null`` 을 **None 으로 파싱한다.** 그대로
  두면 키가 ``None.kinds`` 가 되어 네 키가 통째로 미지의 키가 된다 (실제로
  2026-09-30 첫 작성에서 검증기가 잡았다).
* `curve.*` 가 생겼다 — 저표본 수준과 grid 선택 수준 (결정 30·33).
* `bank.pca_components` 는 10 고정이다. **grid 를 열지 않는다** (결정 33).

아직 정해지지 않아 스키마에 **넣지 않은 것**: endpoint 해상도. 정해지면 키를
더한다. 미리 자리를 만들어 두지 않는다 — 빈 자리는 조용한 default 가 된다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

from mobse.v2 import preprocess, splits, statistics, templates
from mobse.v2 import train as TR2      # grid 축은 v1 규칙 그대로다 (설계안 §7)
from mobse.v2.config import (  # 스키마와 무관한 부분은 동결된 v1 것을 쓴다
    RELEASE_ID_PATTERN,
    ConfigError,
    FieldSpec,
    canonical_json,
    config_hash,
    release_id,
)
from mobse.v2.config import _as_tuple, _flatten  # noqa: F401  (구현 선택: 사문 재작성 안 함)
from mobse.v3 import subsample as SUB
from mobse.v3 import templates as T3
from mobse.v3 import train as TR3
from mobse.v3.models import ROI_STRUCTURES

__all__ = [
    "ConfigError", "FieldSpec", "SCHEMA", "RELEASE_ID_PATTERN",
    "canonical_json", "config_hash", "load_config", "release_id",
    "validate_config",
]


def _positive(value: Any) -> "str | None":
    return None if value > 0 else "0보다 커야 한다"


def _two_roi_structures(value: Any) -> "str | None":
    """결정 33 의 칸은 A–D × **2** 구조다. 어느 둘인지는 여기서 고르지 않는다."""
    names = list(_as_tuple(value))
    if len(names) != 2:
        return f"정확히 2 개여야 한다 (결정 33: 8 칸 = A–D × 2 구조), 받은 값 {len(names)} 개"
    if len(set(names)) != 2:
        return f"중복이다: {names}"
    unknown = [n for n in names if n not in ROI_STRUCTURES]
    if unknown:
        return f"알 수 없는 구조 {unknown} (허용: {list(ROI_STRUCTURES)})"
    return None


SCHEMA: Dict[str, FieldSpec] = {
    # --- 식별 ---
    "meta.name": FieldSpec((str,), "config 이름. release 경로에 쓰지 않는다(해시를 쓴다)."),
    "meta.design_version": FieldSpec((str,), "설계 판본", choices=("exploratory_v2",)),
    "meta.role": FieldSpec((str,), "이 config 가 담당하는 단계",
                           choices=("smoke", "pilot", "main")),
    # --- 시간축·QC·분할: v1 에서 그대로 가져온다 (설계안 §7) ---
    "timing.analysis_start_s": FieldSpec((int, float), "분석 시작", locked_to=preprocess.ANALYSIS_START),
    "timing.analysis_end_s": FieldSpec((int, float), "분석 끝 (배타)", locked_to=preprocess.ANALYSIS_END),
    "timing.target_grid_s": FieldSpec((int, float), "재표본 격자", locked_to=preprocess.TARGET_GRID),
    "timing.window_len_s": FieldSpec((int, float), "고정 창 길이", locked_to=preprocess.WINDOW_LEN),
    "timing.window_starts_s": FieldSpec((list, tuple), "4개 창 시작", locked_to=preprocess.WINDOW_STARTS),
    "timing.samples_per_window": FieldSpec((int,), "창당 표본 수", locked_to=preprocess.SAMPLES_PER_WINDOW),
    "qc.fd_mean_max": FieldSpec((int, float), "run 평균 FD 상한", locked_to=preprocess.FD_MEAN_MAX),
    "qc.fd_spike": FieldSpec((int, float), "spike 판정 FD", locked_to=preprocess.FD_SPIKE),
    "qc.fd_spike_ratio_max": FieldSpec((int, float), "spike 비율 상한", locked_to=preprocess.FD_SPIKE_RATIO_MAX),
    "qc.min_residual_dof": FieldSpec((int,), "nuisance 회귀 후 최소 자유도", locked_to=preprocess.MIN_RESIDUAL_DOF),
    "splits.pilot_seed": FieldSpec((int,), "pilot 표집 seed", locked_to=splits.PILOT_SEED),
    "splits.outer_seed": FieldSpec((int,), "outer 5-fold seed", locked_to=splits.OUTER_SEED),
    "splits.inner_seed_base": FieldSpec((int,), "inner seed = base + fold", locked_to=splits.INNER_SEED_BASE),
    "splits.pilot_cap": FieldSpec((int,), "pilot 상한", locked_to=splits.PILOT_CAP),
    "splits.pilot_fraction": FieldSpec((int, float), "pilot 비율", locked_to=splits.PILOT_FRACTION),
    "splits.n_outer_folds": FieldSpec((int,), "outer fold 수", choices=(5,)),
    "splits.n_inner_folds": FieldSpec((int,), "inner fold 수", choices=(3,)),
    # --- bank ---
    "bank.k": FieldSpec((int,), "K-means K", locked_to=templates.K_DEFAULT),
    "bank.n_init": FieldSpec((int,), "K-means 재시작 수", locked_to=templates.N_INIT),
    "bank.max_iter": FieldSpec((int,), "K-means 최대 반복", locked_to=templates.MAX_ITER),
    "bank.edge_density": FieldSpec((int, float), "양의 상위 edge 비율", locked_to=templates.EDGE_DENSITY),
    "bank.seed_base": FieldSpec((int,), "bank seed = base + 100*outer + inner", locked_to=templates.BANK_SEED_BASE),
    "bank.pca_components": FieldSpec((int,), "gate PCA 차원. 결정 33 — 10 고정, grid 를 열지 않는다",
                                     choices=(10,)),
    # --- null (결정 28-3 · 33). 절 이름이 ``nulls`` 인 이유는 아래 주의 참고 ---
    "nulls.kinds": FieldSpec((list, tuple), "null 세 종류", locked_to=T3.NULL_KINDS),
    "nulls.m_per_kind": FieldSpec((int,), "종류당 표본 수 (결정 33)", choices=(20,)),
    "nulls.swaps_per_edge": FieldSpec((int,), "degree 보존 rewiring 의 edge 당 교환 시도",
                                     locked_to=T3.SWAPS_PER_EDGE),
    "nulls.primary_seed": FieldSpec((int,), "null 주 seed", locked_to=templates.NULL_SEED_PRIMARY),
    # --- 칸 (결정 33: A–D × 2 구조 = 8) ---
    "cells.names": FieldSpec((list, tuple), "2x2 cell 이름", locked_to=TR3.CELLS),
    "cells.roi_structures": FieldSpec((list, tuple), "ROI 정체 구조 2 개 (결정 28-2·33)",
                                      check=_two_roi_structures),
    # --- 학습 (mobse/v3/train.py 가 정본) ---
    "train.learning_rates": FieldSpec((list, tuple), "grid 축 1", locked_to=TR2.LEARNING_RATES),
    "train.dropouts": FieldSpec((list, tuple), "grid 축 2", locked_to=TR2.DROPOUTS),
    "train.weight_decays": FieldSpec((list, tuple), "grid 축 3", locked_to=TR2.WEIGHT_DECAYS),
    "train.batch_size": FieldSpec((int,), "배치 크기", locked_to=TR3.BATCH_SIZE),
    "train.update_budget": FieldSpec((int,), "모든 N 이 같게 받는 update 예산 (결정 31-1·32)",
                                     locked_to=TR3.UPDATE_BUDGET),
    "train.epoch_sanity_ceiling": FieldSpec((int,), "폭주 방어선. 규칙이 아니다",
                                            locked_to=TR3.EPOCH_SANITY_CEILING),
    "train.carry_unit": FieldSpec((str,), "공통 E 를 outer 로 옮기는 단위 (설계안 §5.3.2)",
                                  choices=("update",)),
    "train.patience": FieldSpec((int,), "early stopping 인내", locked_to=TR3.PATIENCE),
    "train.min_delta": FieldSpec((int, float), "개선 판정 하한", locked_to=TR3.MIN_DELTA),
    "train.grad_clip": FieldSpec((int, float), "gradient clipping", locked_to=TR3.GRAD_CLIP),
    "train.model_seeds": FieldSpec((list, tuple), "3-seed ensemble", locked_to=TR3.MODEL_SEEDS),
    # --- 저표본 곡선 (결정 30 · 33) ---
    "curve.levels": FieldSpec((list, tuple), "학습 subject 수 수준", locked_to=SUB.LOW_SAMPLE_LEVELS),
    "curve.subsample_seed_base": FieldSpec((int,), "fold 별 섞기 seed 바탕",
                                           locked_to=SUB.SUBSAMPLE_SEED_BASE),
    "curve.grid_selection_level": FieldSpec(
        (int,), "config grid 를 고르는 수준. 결정 33 — 가장 큰 수준에서 한 번 고르고 "
        "전 수준이 재사용한다", choices=(max(SUB.LOW_SAMPLE_LEVELS),)),
    # --- 통계 ---
    "stats.bootstrap_seed": FieldSpec((int,), "paired group bootstrap seed", locked_to=statistics.BOOTSTRAP_SEED),
    "stats.n_bootstrap": FieldSpec((int,), "bootstrap 반복", locked_to=statistics.N_BOOTSTRAP),
    "stats.familywise_pct": FieldSpec((list, tuple), "주 contrast 용 CI", locked_to=statistics.FAMILYWISE_PCT),
    "stats.nominal_pct": FieldSpec((list, tuple), "보조 지표용 CI", locked_to=statistics.NOMINAL_PCT),
    "stats.threshold": FieldSpec((int, float), "분류 임계", locked_to=statistics.THRESHOLD),
    "stats.delta": FieldSpec((int, float), "실질 동등 한계. v1 과 같은 0.02 를 유지한다 "
                             "(2026-09-30 권고 승인)", choices=(0.02,)),
    # --- 경로 (glob fallback 금지) ---
    "paths.source_manifest": FieldSpec((str,), "run 원본 manifest — 명시 경로만"),
    "paths.split_manifest": FieldSpec((str,), "분할 manifest — 명시 경로만"),
    "paths.atlas_spec": FieldSpec((str,), "atlas 사양 — 명시 경로만. spin null 이 ROI 좌표를 여기서 읽는다"),
    "paths.output_root": FieldSpec((str,), "release 출력 루트"),
    # --- 실행 ---
    "runtime.backend": FieldSpec((str,), "그래프 연산 backend", choices=("dense",)),
    "runtime.device": FieldSpec((str,), "연산 장치", choices=("cpu", "cuda")),
    "runtime.deterministic": FieldSpec((bool,), "결정적 실행 강제", choices=(True,)),
    "runtime.num_workers": FieldSpec((int,), "DataLoader worker 수",
                                     check=lambda v: None if v >= 0 else "음수 불가"),
}


def validate_config(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """config 를 v3 스키마에 대해 검증하고 평면 dict 를 돌려준다.

    규칙은 v1 과 같다 — 누락·미지 키·타입·상수 불일치·범위를 **한 번에 모아**
    보고한다. 고칠 때마다 다시 돌리지 않게 하기 위해서다.

    Args:
        raw: 중첩 dict (보통 YAML 파싱 결과).

    Returns:
        dotted key -> 값 의 평면 dict.

    Raises:
        ConfigError: 위반이 하나라도 있으면.
    """
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config 최상위가 mapping 이 아니다: {type(raw).__name__}")

    flat = _flatten(raw)
    problems: List[str] = []

    for key in sorted(set(flat) - set(SCHEMA)):
        problems.append(f"미지의 키 {key!r} — 오타이거나 스키마에 없는 항목이다")
    for key in sorted(set(SCHEMA) - set(flat)):
        problems.append(f"필수 키 누락 {key!r} ({SCHEMA[key].doc})")

    for key in sorted(set(flat) & set(SCHEMA)):
        spec = SCHEMA[key]
        value = flat[key]
        # bool 은 int 의 하위형이라 명시적으로 갈라 준다.
        if isinstance(value, bool) and bool not in spec.types:
            problems.append(
                f"{key}: bool 은 허용되지 않는다 (허용: {[t.__name__ for t in spec.types]})")
            continue
        if not isinstance(value, spec.types):
            problems.append(
                f"{key}: 타입 {type(value).__name__} — 허용 {[t.__name__ for t in spec.types]}")
            continue
        if spec.locked_to is not None:
            expected = _as_tuple(spec.locked_to)
            actual = _as_tuple(value)
            if actual != expected:
                problems.append(
                    f"{key}: 코드 상수와 불일치 (config={actual!r}, 코드={expected!r}). "
                    "config 는 상수를 덮어쓸 수 없다")
                continue
        if spec.choices is not None and _as_tuple(value) not in spec.choices:
            problems.append(f"{key}: 허용되지 않는 값 {value!r} (허용: {list(spec.choices)})")
            continue
        if spec.check is not None:
            message = spec.check(value)
            if message:
                problems.append(f"{key}: {message}")

    if problems:
        raise ConfigError(f"config 위반 {len(problems)}건:\n  - " + "\n  - ".join(problems))
    return flat


def load_config(path: Path) -> Dict[str, Any]:
    """YAML config 를 읽어 v3 스키마로 검증한다. 자동 탐색하지 않는다.

    Args:
        path: config 파일 경로.

    Returns:
        검증된 평면 config.

    Raises:
        ConfigError: 파일 부재 또는 스키마 위반.
    """
    import yaml  # 지연 import

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
