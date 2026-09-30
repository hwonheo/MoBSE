"""exploratory v2 config — `mobse/v3/config.py` (결정 33).

두 가지를 본다. (1) 검증기가 v1 과 같은 엄격함을 유지하는가 — 조용한 default
금지, 상수 덮어쓰기 금지. (2) **잠긴 키마다 그 값을 쓰는 곳이 있는가** — v1 에서
"잠겨 검사는 받지만 아무도 안 쓰는 키" 사고(E21·E22·rev38)가 세 번 났다.
"""
from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest
import yaml

from mobse.v3 import config as C
from mobse.v3 import fitting as FIT3
from mobse.v3 import subsample as SUB
from mobse.v3 import templates as T3
from mobse.v3 import train as TR3

SMOKE = Path(__file__).resolve().parents[2] / "configs" / "exploratory_v2" / "smoke.yaml"


@pytest.fixture
def raw():
    return yaml.safe_load(SMOKE.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 파일과 검증기
# --------------------------------------------------------------------------- #


def test_smoke_config_validates():
    cfg = C.load_config(SMOKE)
    assert len(cfg) == len(C.SCHEMA)
    assert cfg["meta.role"] == "smoke"


def test_missing_file_is_refused_not_searched(tmp_path):
    with pytest.raises(C.ConfigError, match="자동 탐색하지 않는다"):
        C.load_config(tmp_path / "없는파일.yaml")


def test_unknown_key_is_a_typo(raw):
    raw["train"]["max_epochs"] = 400          # v1 의 규칙은 v3 에 없다
    with pytest.raises(C.ConfigError, match="미지의 키"):
        C.validate_config(raw)


def test_missing_key_is_refused(raw):
    del raw["train"]["update_budget"]
    with pytest.raises(C.ConfigError, match="필수 키 누락"):
        C.validate_config(raw)


def test_config_cannot_override_a_code_constant(raw):
    raw["train"]["update_budget"] = 4000
    with pytest.raises(C.ConfigError, match="코드 상수와 불일치"):
        C.validate_config(raw)


def test_all_problems_are_reported_at_once(raw):
    raw["train"]["update_budget"] = 4000
    raw["bank"]["pca_components"] = 20
    del raw["curve"]["levels"]
    with pytest.raises(C.ConfigError) as exc:
        C.validate_config(raw)
    assert "위반 3건" in str(exc.value)


def test_bool_is_not_an_int_here(raw):
    raw["train"]["batch_size"] = True
    with pytest.raises(C.ConfigError, match="bool 은 허용되지 않는다"):
        C.validate_config(raw)


# --------------------------------------------------------------------------- #
# 결정 33 이 정한 값
# --------------------------------------------------------------------------- #


def test_v1_training_rule_keys_are_gone():
    """v3 의 통화는 update 예산 하나다 — epoch 상한·최소 update 키가 없어야 한다."""
    assert "train.max_epochs" not in C.SCHEMA
    assert "train.min_updates" not in C.SCHEMA
    assert C.SCHEMA["train.update_budget"].locked_to == TR3.UPDATE_BUDGET


def test_pca_grid_is_not_opened(raw):
    raw["bank"]["pca_components"] = 20
    with pytest.raises(C.ConfigError, match="허용되지 않는 값"):
        C.validate_config(raw)


def test_null_m_is_twenty(raw):
    raw["nulls"]["m_per_kind"] = 100
    with pytest.raises(C.ConfigError, match="허용되지 않는 값"):
        C.validate_config(raw)


def test_carry_unit_is_update_not_epoch(raw):
    raw["train"]["carry_unit"] = "epoch"
    with pytest.raises(C.ConfigError, match="허용되지 않는 값"):
        C.validate_config(raw)


def test_grid_is_selected_at_the_largest_level(raw):
    assert raw["curve"]["grid_selection_level"] == max(SUB.LOW_SAMPLE_LEVELS)
    raw["curve"]["grid_selection_level"] = 40
    with pytest.raises(C.ConfigError, match="허용되지 않는 값"):
        C.validate_config(raw)


@pytest.mark.parametrize("value,message", [
    (["embedding"], "정확히 2 개"),
    (["embedding", "readout", "mean"], "정확히 2 개"),
    (["mean", "mean"], "중복"),
    (["embedding", "pca"], "알 수 없는 구조"),
])
def test_roi_structures_must_be_exactly_two_known_names(raw, value, message):
    raw["cells"]["roi_structures"] = value
    with pytest.raises(C.ConfigError, match=message):
        C.validate_config(raw)


def test_the_yaml_section_is_nulls_because_yaml_eats_a_bare_null():
    """따옴표 없는 ``null`` 은 YAML 이 None 으로 읽는다. 절 이름이 그래서 ``nulls`` 다."""
    assert yaml.safe_load("null:\n  a: 1") == {None: {"a": 1}}
    assert all(not k.startswith("null.") for k in C.SCHEMA)
    assert any(k.startswith("nulls.") for k in C.SCHEMA)


# --------------------------------------------------------------------------- #
# 해시
# --------------------------------------------------------------------------- #


def test_config_hash_is_deterministic_and_order_free(raw):
    a = C.validate_config(raw)
    shuffled = {k: raw[k] for k in reversed(list(raw))}
    b = C.validate_config(shuffled)
    assert C.config_hash(a) == C.config_hash(b)


def test_choosing_other_roi_structures_changes_the_hash(raw):
    a = C.config_hash(C.validate_config(copy.deepcopy(raw)))
    raw["cells"]["roi_structures"] = ["mean", "embedding"]
    b = C.config_hash(C.validate_config(raw))
    assert a != b


# --------------------------------------------------------------------------- #
# 잠긴 키 ↔ 소비 지점
# --------------------------------------------------------------------------- #

#: 잠긴 키 → 그 값을 쓰는 곳. v1 에서 물려받은 키는 `tests/v2` 의 대응표가 이미
#: 지키므로 여기서는 **v3 가 새로 만든 키**만 상수 이름까지 대조한다.
V3_CONSUMERS = {
    "train.update_budget": ("UPDATE_BUDGET",
                            (TR3.epochs_for_budget, TR3.carry_epochs_to_outer,
                             FIT3.train_fold)),
    "train.epoch_sanity_ceiling": ("EPOCH_SANITY_CEILING", (TR3.epochs_for_budget,)),
    "nulls.kinds": ("NULL_KINDS", (T3.make_null_bank,)),
    "nulls.swaps_per_edge": ("SWAPS_PER_EDGE", (T3.degree_preserving_rewire,)),
    "curve.levels": ("LOW_SAMPLE_LEVELS", (SUB.subsample_curve,)),
    "curve.subsample_seed_base": ("SUBSAMPLE_SEED_BASE", (SUB.subsample_seed,)),
    # v1 의 값을 그대로 쓰지만 키 이름이 바뀐 둘 — 그래서 여기서도 대조한다.
    "cells.names": ("CELLS", (TR3.select_config,)),
    "nulls.primary_seed": ("NULL_SEED_PRIMARY", (T3.make_null_bank,)),
}


def test_every_new_v3_locked_key_has_a_consumer():
    """v3 가 새로 잠근 키는 전부 대응표에 있어야 한다 (E21 류 사고 방지)."""
    from mobse.v2.config import SCHEMA as V2_SCHEMA
    new_locked = {k for k, spec in C.SCHEMA.items()
                  if spec.locked_to is not None and k not in V2_SCHEMA}
    assert new_locked == set(V3_CONSUMERS), (
        f"대응표에 없는 새 잠긴 키: {sorted(new_locked - set(V3_CONSUMERS))}, "
        f"사라진 키: {sorted(set(V3_CONSUMERS) - new_locked)}")


@pytest.mark.parametrize("key", sorted(V3_CONSUMERS))
def test_each_consumer_actually_mentions_the_constant(key):
    const, funcs = V3_CONSUMERS[key]
    for fn in funcs:
        src = inspect.getsource(fn)
        assert const in src, f"{key}: {fn.__qualname__} 가 {const} 를 참조하지 않는다"
