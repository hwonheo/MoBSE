"""핀 목록이 release 의 import closure 를 덮는지 suite 안에서 강제한다.

PyYAML(legacy suite ModuleNotFoundError)·seaborn(figure 경로) 두 건이 초판 핀에서
빠졌던 사고의 재발 방지다. 근본 원인은 핀을 계획서 서술에서 역산한 것이었으므로,
검사는 소스 AST 를 기준으로 한다. scripts/h197/07_verify_import_closure.py 를
subprocess 가 아니라 모듈로 불러 같은 코드를 쓴다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = REPO_ROOT / "scripts" / "h197" / "07_verify_import_closure.py"

RELEASE_SCOPE = [
    "mobse/v2",
    "tests/v2",
    "scripts/h197",
    "scripts/make_redesign_protocol_figures.py",
    "mobse/viz.py",
]
RELEASE_REQUIREMENTS = ["scripts/h197/requirements-v2.txt"]
REPO_REQUIREMENTS = RELEASE_REQUIREMENTS + ["scripts/h197/requirements-legacy-extra.txt"]


def _load_guard():
    """가드 스크립트를 모듈로 적재한다 (파일명이 숫자로 시작해 import 불가)."""
    spec = importlib.util.spec_from_file_location("_import_closure_guard", GUARD_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - 환경 오류
        raise RuntimeError(f"가드 스크립트 적재 실패: {GUARD_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _missing(guard, scan: List[str], requirements: List[str]) -> List[dict]:
    """주어진 scope 에서 핀이 덮지 못하는 third-party import 를 돌려준다."""
    files = guard.iter_python_files([REPO_ROOT / p for p in scan])
    assert files, f"스캔 대상이 0개다: {scan}"
    modules: Dict[str, List[str]] = {}
    for path in files:
        for name in guard.top_level_imports(path):
            modules.setdefault(name, []).append(str(path.relative_to(REPO_ROOT)))
    pinned: Dict[str, str] = {}
    for req in requirements:
        pinned.update(guard.parse_requirements(REPO_ROOT / req))
    missing, _covered = guard.classify(modules, pinned, guard.first_party_names(REPO_ROOT))
    return missing


@pytest.fixture(scope="module")
def guard():
    if not GUARD_PATH.is_file():
        pytest.skip(f"가드 스크립트 없음: {GUARD_PATH}")
    return _load_guard()


def test_guard_script_exists():
    assert GUARD_PATH.is_file(), "import closure 가드 스크립트가 사라졌다"


def test_release_scope_pins_cover_imports(guard):
    missing = _missing(guard, RELEASE_SCOPE, RELEASE_REQUIREMENTS)
    assert not missing, (
        "release scope 에 핀 없는 third-party import: "
        + ", ".join(f"{m['module']} <- {m['imported_by'][0]}" for m in missing)
    )


def test_repo_scope_pins_cover_imports(guard):
    missing = _missing(guard, ["mobse", "tests", "scripts"], REPO_REQUIREMENTS)
    assert not missing, (
        "repo scope 에 핀 없는 third-party import: "
        + ", ".join(f"{m['module']} <- {m['imported_by'][0]}" for m in missing)
    )


def test_pyyaml_and_seaborn_regression(guard):
    """실제로 놓쳤던 두 건이 다시 빠지면 즉시 잡힌다."""
    pinned: Dict[str, str] = {}
    for req in RELEASE_REQUIREMENTS:
        pinned.update(guard.parse_requirements(REPO_ROOT / req))
    assert "pyyaml" in pinned, "PyYAML 핀이 사라졌다 (legacy suite 가 죽는다)"
    assert "seaborn" in pinned, "seaborn 핀이 사라졌다 (figure 생성이 죽는다)"


def test_torch_geometric_never_pinned(guard):
    """U21 guard — backend 분기를 막기 위해 절대 핀에 들어가면 안 된다."""
    pinned: Dict[str, str] = {}
    for req in REPO_REQUIREMENTS:
        pinned.update(guard.parse_requirements(REPO_ROOT / req))
    for forbidden in ("torch-geometric", "torch-scatter", "torch-sparse"):
        assert forbidden not in pinned, f"{forbidden} 이 핀에 들어갔다 (U21 위반)"
