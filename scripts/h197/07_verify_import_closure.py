#!/usr/bin/env python3
"""requirements-v2.txt 의 import closure 검증 (표준 라이브러리만 사용).

PyYAML·seaborn 이 초판 핀에서 빠져 legacy suite 가 ModuleNotFoundError 로 죽은
사고의 재발 방지 guard 다. 근본 원인은 핀 목록을 "계획서가 말하는 알고리즘"에서
역산했다는 것이고, 올바른 기준은 "release 가 실제로 import 하는 것"이다.
따라서 이 스크립트는 문서가 아니라 소스의 AST 를 읽는다.

사용:
    python scripts/h197/07_verify_import_closure.py \
        --repo-root . \
        --requirements scripts/h197/requirements-v2.txt \
        --report results/.../provenance/import_closure.json

종료 코드:
    0  핀 목록이 import closure 를 덮는다
    1  덮지 못하는 third-party import 가 있다 (또는 입력 오류)
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

# import 이름 -> PyPI 배포판 이름. 둘이 다른 것만 적는다.
MODULE_TO_DISTRIBUTION: Dict[str, str] = {
    "yaml": "PyYAML",
    "sklearn": "scikit-learn",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "dateutil": "python-dateutil",
    "pkg_resources": "setuptools",
    "mpl_toolkits": "matplotlib",
}

# 핀에 없어도 되는 것. 이유를 반드시 적는다 (guard 가 변명 창구가 되지 않게).
DELIBERATE_EXCLUSIONS: Dict[str, str] = {
    "torch": "CUDA 변형이 호스트마다 달라 04_setup_venv.sh 가 따로 설치한다",
    "torch_geometric": "U21 guard — 설치되면 backend 가 갈라지므로 의도적으로 제외",
    "pytest": "pytest 는 핀에 있으나 조건부로 여기서도 허용",
}

FIRST_PARTY_EXTRA: Set[str] = {"mobse", "tests", "scripts", "conftest"}


def iter_python_files(roots: Iterable[Path]) -> List[Path]:
    """주어진 경로들 아래의 .py 파일을 모은다 (캐시·가상환경 제외)."""
    skip = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".backup"}
    out: List[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            out.append(root)
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in skip for part in path.parts):
                continue
            out.append(path)
    return out


def top_level_imports(path: Path) -> Set[str]:
    """한 파일의 절대 import 최상위 모듈명을 모은다. 상대 import 는 무시한다."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # 문법이 깨진 파일은 조용히 넘기지 않는다
        raise RuntimeError(f"AST 파싱 실패: {path}: {exc}") from exc
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # from . import x
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def parse_requirements(path: Path) -> Dict[str, str]:
    """requirements 파일에서 {정규화된 배포판명: 원문 줄} 을 만든다."""
    pinned: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)", line)
        if not match:
            continue
        pinned[normalize(match.group(1))] = raw.strip()
    return pinned


def normalize(name: str) -> str:
    """PEP 503 정규화 (대소문자·구분자 차이를 없앤다)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def first_party_names(repo_root: Path) -> Set[str]:
    """저장소 최상위의 패키지·모듈 이름을 first-party 로 본다."""
    names = set(FIRST_PARTY_EXTRA)
    for entry in repo_root.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and (entry / "__init__.py").exists():
            names.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py":
            names.add(entry.stem)
    return names


def classify(
    modules: Dict[str, List[str]],
    pinned: Dict[str, str],
    local: Set[str],
) -> Tuple[List[dict], List[str]]:
    """third-party import 를 핀 충족 여부로 나눈다."""
    stdlib = set(sys.stdlib_module_names)
    missing: List[dict] = []
    covered: List[str] = []
    for module in sorted(modules):
        if module in stdlib or module in local:
            continue
        if module in DELIBERATE_EXCLUSIONS:
            continue
        distribution = MODULE_TO_DISTRIBUTION.get(module, module)
        if normalize(distribution) in pinned:
            covered.append(module)
        else:
            missing.append(
                {
                    "module": module,
                    "expected_distribution": distribution,
                    "imported_by": sorted(modules[module])[:8],
                    "import_site_count": len(modules[module]),
                }
            )
    return missing, covered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--requirements",
        type=Path,
        nargs="+",
        required=True,
        help="핀 파일 (여러 개 주면 합집합으로 본다: release 핀 + legacy 추가 핀)",
    )
    parser.add_argument(
        "--scan",
        type=Path,
        nargs="+",
        default=None,
        help="검사할 하위 경로 (기본: mobse tests scripts)",
    )
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    if not repo_root.is_dir():
        print(f"[error] repo-root 없음: {repo_root}", file=sys.stderr)
        return 1
    for req in args.requirements:
        if not req.is_file():
            print(f"[error] requirements 없음: {req}", file=sys.stderr)
            return 1

    scan_roots = [repo_root / p for p in (args.scan or [Path("mobse"), Path("tests"), Path("scripts")])]
    files = iter_python_files(scan_roots)
    if not files:
        print("[error] 스캔 대상 .py 가 0개다 — 경로를 확인하라", file=sys.stderr)
        return 1

    modules: Dict[str, List[str]] = {}
    for path in files:
        for name in top_level_imports(path):
            modules.setdefault(name, []).append(str(path.relative_to(repo_root)))

    pinned: Dict[str, str] = {}
    for req in args.requirements:
        pinned.update(parse_requirements(req))
    local = first_party_names(repo_root)
    missing, covered = classify(modules, pinned, local)

    unused = sorted(
        dist
        for dist in pinned
        if dist not in {normalize(MODULE_TO_DISTRIBUTION.get(m, m)) for m in covered}
    )

    report = {
        "repo_root": str(repo_root),
        "requirements": [str(r) for r in args.requirements],
        "scanned_files": len(files),
        "scanned_roots": [str(p.relative_to(repo_root)) for p in scan_roots if p.exists()],
        "third_party_covered": covered,
        "third_party_missing": missing,
        "pinned_not_imported": unused,
        "deliberate_exclusions": DELIBERATE_EXCLUSIONS,
        "verdict": "pass" if not missing else "fail",
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[scan] {len(files)} files, roots={report['scanned_roots']}")
    print(f"[ok]   핀이 덮는 third-party: {', '.join(covered) or '(없음)'}")
    if unused:
        print(f"[note] 핀에 있으나 import 되지 않음: {', '.join(unused)}")
    if missing:
        print("[FAIL] 핀에 없는 third-party import:")
        for item in missing:
            sites = ", ".join(item["imported_by"])
            print(f"  - {item['module']} (배포판 {item['expected_distribution']}) <- {sites}")
        return 1
    print("[PASS] import closure 가 핀 목록에 모두 포함된다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
