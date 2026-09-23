"""runtime config 스키마 검증 (WI-05, T02 조용한 default 금지)."""

from __future__ import annotations

import copy
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

from mobse.v2 import preprocess, splits, statistics, templates, train
from mobse.v2.config import (
    SCHEMA,
    ConfigError,
    canonical_json,
    config_hash,
    load_config,
    release_id,
    validate_config,
)

CONFIG_DIR = pathlib.Path(__file__).resolve().parents[2] / "configs" / "redesign_v1"
SHIPPED = sorted(CONFIG_DIR.glob("*.yaml"))


@pytest.fixture
def raw():
    assert SHIPPED, f"배포 config 가 없다: {CONFIG_DIR}"
    return yaml.safe_load((CONFIG_DIR / "main.yaml").read_text(encoding="utf-8"))


# --- 배포 config 자체 ---------------------------------------------------------

def test_shipped_configs_exist():
    assert {p.name for p in SHIPPED} == {"pilot.yaml", "main.yaml", "external.yaml"}


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: p.name)
def test_shipped_config_validates(path):
    flat = load_config(path)
    assert len(flat) == len(SCHEMA)


def test_shipped_configs_have_distinct_hashes():
    hashes = {p.name: config_hash(load_config(p)) for p in SHIPPED}
    assert len(set(hashes.values())) == len(hashes), f"config hash 충돌: {hashes}"


# --- 조용한 default 금지 (T02) ------------------------------------------------

def test_unknown_key_is_rejected(raw):
    bad = copy.deepcopy(raw)
    bad["train"]["lr"] = 0.01  # 오타
    with pytest.raises(ConfigError, match="미지의 키"):
        validate_config(bad)


def test_missing_key_is_rejected(raw):
    bad = copy.deepcopy(raw)
    del bad["stats"]["threshold"]
    with pytest.raises(ConfigError, match="필수 키 누락"):
        validate_config(bad)


def test_all_problems_reported_at_once(raw):
    bad = copy.deepcopy(raw)
    bad["train"]["typo_one"] = 1
    bad["bank"]["typo_two"] = 2
    del bad["qc"]["fd_spike"]
    with pytest.raises(ConfigError) as info:
        validate_config(bad)
    assert "3건" in str(info.value), str(info.value)


def test_empty_config_rejected():
    with pytest.raises(ConfigError):
        validate_config({})


def test_non_mapping_rejected():
    with pytest.raises(ConfigError, match="mapping"):
        validate_config([1, 2, 3])  # type: ignore[arg-type]


# --- config 가 코드 상수를 덮어쓰지 못한다 -------------------------------------

@pytest.mark.parametrize(
    "section,key,value,constant",
    [
        ("timing", "analysis_end_s", 300.0, preprocess.ANALYSIS_END),
        ("qc", "fd_mean_max", 0.5, preprocess.FD_MEAN_MAX),
        ("splits", "outer_seed", 1, splits.OUTER_SEED),
        ("bank", "null_seed", 42, templates.NULL_SEED_PRIMARY),
        ("train", "max_epochs", 999, train.MAX_EPOCHS),
        ("train", "min_updates", 800, train.MIN_UPDATES),
        ("stats", "n_bootstrap", 100, statistics.N_BOOTSTRAP),
    ],
)
def test_constant_override_is_rejected(raw, section, key, value, constant):
    bad = copy.deepcopy(raw)
    assert bad[section][key] != value, "픽스처가 이미 같은 값이면 시험이 무의미하다"
    bad[section][key] = value
    with pytest.raises(ConfigError, match="코드 상수와 불일치"):
        validate_config(bad)
    assert validate_config(raw)[f"{section}.{key}"] == pytest.approx(constant) \
        if isinstance(constant, float) else True


def test_sequence_constants_compare_by_value(raw):
    """YAML 은 list, 코드는 tuple 이다. 표현 차이로 실패하면 안 된다."""
    flat = validate_config(raw)
    assert tuple(flat["train.model_seeds"]) == train.MODEL_SEEDS
    assert tuple(flat["timing.window_starts_s"]) == preprocess.WINDOW_STARTS
    assert tuple(flat["stats.familywise_pct"]) == statistics.FAMILYWISE_PCT


# --- 타입·선택지 --------------------------------------------------------------

def test_bool_not_accepted_where_int_expected(raw):
    bad = copy.deepcopy(raw)
    bad["runtime"]["num_workers"] = True
    with pytest.raises(ConfigError, match="bool"):
        validate_config(bad)


def test_negative_num_workers_rejected(raw):
    bad = copy.deepcopy(raw)
    bad["runtime"]["num_workers"] = -1
    with pytest.raises(ConfigError, match="음수 불가"):
        validate_config(bad)


def test_backend_choice_locked(raw):
    """U21 — backend 는 dense 외에 선택지가 없다."""
    bad = copy.deepcopy(raw)
    bad["runtime"]["backend"] = "pyg"
    with pytest.raises(ConfigError, match="허용되지 않는 값"):
        validate_config(bad)


def test_deterministic_cannot_be_disabled(raw):
    bad = copy.deepcopy(raw)
    bad["runtime"]["deterministic"] = False
    with pytest.raises(ConfigError, match="허용되지 않는 값"):
        validate_config(bad)


def test_delta_locked_to_protocol(raw):
    """계획서 §2 의 실질 동등 한계 0.02 는 config 로 바뀌지 않는다."""
    bad = copy.deepcopy(raw)
    bad["stats"]["delta"] = 0.05
    with pytest.raises(ConfigError, match="허용되지 않는 값"):
        validate_config(bad)


# --- 파일 적재 (glob fallback 금지, U20) --------------------------------------

def test_missing_file_does_not_fall_back(tmp_path):
    with pytest.raises(ConfigError, match="자동 탐색하지 않는다"):
        load_config(tmp_path / "does_not_exist.yaml")


def test_empty_file_rejected(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="비어 있다"):
        load_config(path)


def test_malformed_yaml_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("a: [1, 2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML 파싱 실패"):
        load_config(path)


# --- 해시 결정성 --------------------------------------------------------------

def test_canonical_json_is_key_order_independent(raw):
    flat = validate_config(raw)
    shuffled = dict(reversed(list(flat.items())))
    assert canonical_json(flat) == canonical_json(shuffled)


def test_list_and_tuple_hash_identically(raw):
    flat = validate_config(raw)
    tupled = {k: (tuple(v) if isinstance(v, list) else v) for k, v in flat.items()}
    assert config_hash(flat) == config_hash(tupled)


def test_hash_changes_when_a_path_changes(raw):
    flat = validate_config(raw)
    before = config_hash(flat)
    flat = dict(flat)
    flat["paths.output_root"] = "results/other"
    assert config_hash(flat) != before


def test_config_hash_rejects_too_short_length(raw):
    with pytest.raises(ConfigError):
        config_hash(validate_config(raw), length=2)


# --- release_id ---------------------------------------------------------------

def test_release_id_format():
    rid = release_id("20260917", "3c458d507e82ab", "fd6c8a2799")
    assert rid == "20260917_3c458d507e82_fd6c8a27"


@pytest.mark.parametrize(
    "date,code,cfg",
    [
        ("2026-09-17", "3c458d507e82", "fd6c8a27"),   # 구분자 있음
        ("20260917", "3c458d", "fd6c8a27"),           # code 너무 짧음
        ("20260917", "3c458d507e82", "fd6c"),         # config 너무 짧음
        ("20260917", "3C458D507E82", "fd6c8a27"),     # 대문자
        ("20260917", "3c458d507e82", ""),             # 빈 값
    ],
)
def test_release_id_rejects_bad_input(date, code, cfg):
    with pytest.raises(ConfigError):
        release_id(date, code, cfg)


def test_schema_covers_every_shipped_field(raw):
    """배포 config 가 스키마에 없는 섹션을 들고 있지 않은지 역방향 확인."""
    sections = {k.split(".", 1)[0] for k in SCHEMA}
    assert set(raw) == sections
