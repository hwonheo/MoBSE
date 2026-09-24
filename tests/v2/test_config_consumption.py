"""잠긴 config 키 ↔ 코드에서 그 값을 소비하는 지점 대응표 (남은 작업 3).

E21(band-pass)·E22(deterministic)·rev38(model_seeds) 는 모두 "config 에 잠겨
검사는 받지만 어디서도 그 값을 쓰지 않는" 키였다. 이 시험은 ``config.SCHEMA``
의 ``locked_to`` 키마다 **소비 함수**를 표로 고정하고, 각 함수의 AST 가 그
상수 이름(``X`` 또는 ``mod.X``)이나 config 키 문자열(``cfg["a.b"]``)을 실제로
참조하는지 본다.

한계 — 정적 검사다. 참조는 적용의 **필요조건**일 뿐 충분조건이 아니다. 값이
실제 동작을 바꾸는지는 개별 spy·결과 시험(E21·E22·P8·결정 12)이 맡는다. 이
시험이 막는 것은 (1) 새 잠긴 키가 표 없이 추가되는 것, (2) 소비 지점이
리팩터링 중 조용히 사라지는 것, (3) 두 학습 루프(``fitting.train_fold``,
``baselines.fit_mlp``) 가 서로 다른 학습 상수 집합을 읽게 되는 것이다.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Tuple

import pytest

V2 = Path(__file__).resolve().parents[2] / "mobse" / "v2"

#: 잠긴 키 → 소비 함수 ("module.function"). 정의 모듈의 검사 함수가 아니라
#: 값이 계산·분기에 들어가는 지점을 적는다.
CONSUMERS: Dict[str, Tuple[str, ...]] = {
    "timing.analysis_start_s": ("preprocess.target_times",),
    "timing.analysis_end_s": ("preprocess.target_times",),
    "timing.target_grid_s": ("preprocess.target_times",),
    "timing.window_len_s": ("preprocess.fixed_windows",),
    "timing.window_starts_s": ("preprocess.fixed_windows", "labels.build_window_records"),
    "timing.samples_per_window": ("preprocess.fixed_windows",),
    "qc.fd_mean_max": ("preprocess.qc_decision",),
    "qc.fd_spike": ("preprocess.fd_quality",),
    "qc.fd_spike_ratio_max": ("preprocess.qc_decision",),
    "qc.min_residual_dof": ("preprocess.qc_decision", "extract.summarize_design"),
    "splits.pilot_seed": ("splits.select_pilot",),
    "splits.outer_seed": ("splits.build_folds",),
    "splits.inner_seed_base": ("splits.build_folds",),
    "splits.external_seed": ("splits.build_folds",),
    "splits.pilot_cap": ("splits.select_pilot",),
    "splits.pilot_fraction": ("splits.select_pilot",),
    "bank.k": ("templates.cluster_rest", "cli.run_fit"),
    "bank.n_init": ("templates.cluster_rest",),
    "bank.max_iter": ("templates.cluster_rest",),
    "bank.edge_density": ("templates.sparsify_positive", "cli.run_fit"),
    "bank.seed_base": ("templates.bank_seed",),
    "bank.null_seed": ("templates.make_null_bank", "cli.run_fit"),
    "train.learning_rates": ("train.build_grid",),
    "train.dropouts": ("train.build_grid",),
    "train.weight_decays": ("train.build_grid",),
    "train.batch_size": ("fitting.train_fold", "baselines.fit_mlp", "cli.run_fit"),
    "train.max_epochs": ("fitting.train_fold", "baselines.fit_mlp", "cli.run_fit"),
    "train.min_updates": ("fitting.train_fold", "baselines.fit_mlp", "cli.run_fit"),
    "train.patience": ("fitting.train_fold", "baselines.fit_mlp", "cli.run_fit"),
    "train.min_delta": ("fitting.train_fold", "baselines.fit_mlp", "cli.run_fit"),
    "train.grad_clip": ("fitting.train_fold", "baselines.fit_mlp", "cli.run_fit"),
    "train.model_seeds": ("cli.run_fit", "cli._check_fit_grid", "fitting.train_fold",
                          "baselines.fit_mlp"),
    "train.cells": ("train.select_config", "evaluate.primary_contrasts"),
    "stats.bootstrap_seed": ("statistics.paired_bootstrap", "cli.run_report"),
    "stats.n_bootstrap": ("statistics.paired_bootstrap", "cli.run_report"),
    "stats.familywise_pct": ("statistics.paired_bootstrap", "cli.run_report"),
    "stats.nominal_pct": ("cli.run_report",),
    "stats.threshold": ("statistics.classify", "cli.run_evaluate"),
}

#: 아직 소비 경로가 없는 잠긴 키와 그 이유. 소비 지점이 생기면 CONSUMERS 로 옮긴다
#: (``test_pending_keys_have_no_consumer_yet`` 이 그때 실패해 알린다).
PENDING: Dict[str, str] = {
    "bank.null_seeds_sensitivity": "민감도 null 실행 경로 미구현 (fit·CLI 배선 전)",
}

#: 두 학습 루프가 같은 규칙을 읽는지 보는 train 상수.
TRAIN_LOOP_CONSTANTS: FrozenSet[str] = frozenset(
    {"BATCH_SIZE", "MAX_EPOCHS", "MIN_UPDATES", "PATIENCE", "MIN_DELTA", "GRAD_CLIP"})


@lru_cache(maxsize=None)
def _locked() -> Dict[str, Tuple[str, str]]:
    """config.py AST 에서 ``key → (정의 모듈, 상수 이름)``."""
    tree = ast.parse((V2 / "config.py").read_text(encoding="utf-8"))
    out: Dict[str, Tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(v, ast.Call):
                for kw in v.keywords:
                    if kw.arg == "locked_to" and isinstance(kw.value, ast.Attribute):
                        out[k.value] = (kw.value.value.id, kw.value.attr)
    return out


@lru_cache(maxsize=None)
def _functions(module: str) -> Dict[str, ast.AST]:
    tree = ast.parse((V2 / f"{module}.py").read_text(encoding="utf-8"))
    out: Dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
    return out


def _references(func: ast.AST, const: str, key: str) -> bool:
    for n in ast.walk(func):
        if isinstance(n, ast.Name) and n.id == const:
            return True
        if isinstance(n, ast.Attribute) and n.attr == const:
            return True
        if isinstance(n, ast.Constant) and n.value == key:
            return True
    return False


def _train_constants(module: str, func: str) -> FrozenSet[str]:
    f = _functions(module)[func]
    names = {n.id for n in ast.walk(f) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute)}
    return frozenset(names & TRAIN_LOOP_CONSTANTS)


def test_locked_key_count_is_known():
    assert len(_locked()) == 39


def test_every_locked_key_is_in_exactly_one_table():
    locked = set(_locked())
    assert not set(CONSUMERS) & set(PENDING)
    assert set(CONSUMERS) | set(PENDING) == locked, (
        set(CONSUMERS) | set(PENDING)) ^ locked


@pytest.mark.parametrize("key", sorted(CONSUMERS))
def test_consumer_references_locked_value(key):
    _, const = _locked()[key]
    for target in CONSUMERS[key]:
        module, func = target.split(".")
        funcs = _functions(module)
        assert func in funcs, f"{key}: 소비 함수 {target} 가 없다"
        assert _references(funcs[func], const, key), (
            f"{key}: {target} 가 {const} / \"{key}\" 를 참조하지 않는다")


@pytest.mark.parametrize("key", sorted(PENDING))
def test_pending_keys_have_no_consumer_yet(key):
    """소비 지점이 생기면 이 시험이 실패한다 — 그때 CONSUMERS 로 옮긴다."""
    module, const = _locked()[key]
    hits = []
    for path in sorted(V2.glob("*.py")):
        if path.stem == "config":
            continue
        for name, f in _functions(path.stem).items():
            if _references(f, const, key):
                hits.append(f"{path.stem}.{name}")
    assert hits == [], f"{key} 가 이제 소비된다: {hits} — CONSUMERS 로 옮길 것"


def test_two_training_loops_read_the_same_train_constants():
    """``train_fold`` 와 ``fit_mlp`` 는 별도 구현이다 (부록 AI). 둘이 읽는 학습
    상수 집합이 같아야 결정 12 류 변경이 한쪽에만 반영되는 일을 막는다."""
    a = _train_constants("fitting", "train_fold")
    b = _train_constants("baselines", "fit_mlp")
    assert a == b == TRAIN_LOOP_CONSTANTS, (sorted(a), sorted(b))


def _top_level_definers(const: str) -> Tuple[str, ...]:
    out = []
    for path in sorted(V2.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AnnAssign) else [])
            if any(isinstance(t, ast.Name) and t.id == const for t in targets):
                out.append(path.stem)
    return tuple(out)


def test_locked_constant_duplicates_are_known_and_equal():
    """대응표는 이름으로 참조를 찾는다. 같은 이름의 상수가 다른 모듈에도 있으면
    그 값이 잠긴 값과 같아야 한다 (지금은 ``evaluate.CELLS`` 하나)."""
    import importlib
    dups = {}
    for key, (module, const) in _locked().items():
        definers = _top_level_definers(const)
        assert module in definers, f"{key}: {module}.{const} 정의 없음"
        if len(definers) > 1:
            dups[const] = definers
    assert dups == {"CELLS": ("evaluate", "train")}, dups
    locked = importlib.import_module("mobse.v2.train").CELLS
    assert tuple(importlib.import_module("mobse.v2.evaluate").CELLS) == tuple(locked)
