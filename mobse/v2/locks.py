"""측정 잠금 — 재설계 지침서 WI-03 / gate G1 구현.

WI-03 의 완료 기준은 "실제 N과 분할 hashes가 고정되며 pilot은 모든 main/final
fit에서 제외된다"이다. 이 모듈은 그 고정을 **파일 하나**로 만들고, 그 파일이
여전히 참인지 **다시 계산해서** 확인한다.

왜 필요한가. 개정 P7 로 적격자가 153 → 157 로 4명 늘자 pilot 31명 중 24명이
교체되고 공통 main pool subject 의 outer fold 가 65% 바뀌었다(보고서 부록 U.3.1).
seed 를 고정해도 **그룹 목록이 바뀌면 배정이 전부 바뀐다.** 그래서 분할을
소비하는 단계를 시작하기 전에 코호트·분할·코드·설정을 한 번에 잠근다.

잠금 파일은 두 가지를 담는다.

* **고정 대상의 해시** — manifest, subjects, exclusions, 창 manifest, folds,
  atlas, config, 코드, 계획서·지침서.
* **파생 불변식** — pilot ∩ main_pool = ∅, pilot ∪ main_pool = 적격집합,
  outer test 가 main pool 을 분할, **pilot 이 어떤 fold 의 train/test 에도 없음**.

불변식은 잠금 시점에 기록만 하는 것이 아니라 `verify_lock()` 이 folds 파일을
다시 읽어 매번 재확인한다. 기록된 참은 참이 아니다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .manifests import ManifestError, sha256_file

SCHEMA_VERSION = "measurement_lock_v1"

#: `lock_hash` 를 계산할 때 본문에서 제외하는 최상위 필드.
_EXCLUDED_FROM_LOCK_HASH = ("lock_hash",)


class LockError(RuntimeError):
    """잠금 생성·검증 규칙 위반."""


# --------------------------------------------------------------------------- #
# 해시
# --------------------------------------------------------------------------- #


def canonical_lock_json(body: Mapping[str, Any]) -> str:
    """`lock_hash` 를 뺀 본문의 정규 직렬화."""
    payload = {k: v for k, v in body.items() if k not in _EXCLUDED_FROM_LOCK_HASH}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def lock_hash(body: Mapping[str, Any]) -> str:
    """잠금 본문 자체의 sha256. 파일이 나중에 손대어졌는지 잡는다."""
    return hashlib.sha256(canonical_lock_json(body).encode("utf-8")).hexdigest()


def file_record(path: Path, *, base: Optional[Path] = None,
                **extra: Any) -> Dict[str, Any]:
    """파일 하나의 잠금 레코드. 파일이 없으면 실패한다 — 빈 해시를 쓰지 않는다."""
    p = Path(path)
    rel = str(p.relative_to(base)) if base is not None else str(p)
    rec: Dict[str, Any] = {"path": rel, "sha256": sha256_file(p),
                           "bytes": p.stat().st_size}
    rec.update(extra)
    return rec


# --------------------------------------------------------------------------- #
# 파생 불변식
# --------------------------------------------------------------------------- #


def fold_invariants(folds: Mapping[str, Any],
                    eligible: Sequence[str]) -> Dict[str, Any]:
    """`folds.json` 의 파생 불변식을 **계산해서** 돌려준다.

    Args:
        folds: `folds.json` 을 읽은 매핑.
        eligible: 적격 subject 전체.

    Returns:
        불변식 이름 → 결과. 모든 값이 True 여야 잠금이 성립한다.

    Raises:
        LockError: 구조가 기대와 다르면.
    """
    try:
        pilot = set(folds["pilot"]["subjects"])
        pool = set(folds["main_pool"]["subjects"])
        outer = folds["outer_folds"]
    except (KeyError, TypeError) as exc:                      # pragma: no cover
        raise LockError(f"folds 구조가 기대와 다르다: {exc}") from exc

    elig = set(eligible)
    tests: List[set] = []
    inv: Dict[str, Any] = {}

    inv["pilot_and_main_pool_disjoint"] = not (pilot & pool)
    inv["pilot_union_main_pool_is_eligible"] = (pilot | pool) == elig
    inv["n_pilot"] = len(pilot)
    inv["n_main_pool"] = len(pool)
    inv["n_eligible"] = len(elig)

    test_train_ok = True
    union_ok = True
    pilot_absent = True
    inner_ok = True
    for fold in outer:
        te = set(fold["test_subjects"])
        tr = set(fold["train_subjects"])
        tests.append(te)
        test_train_ok &= not (te & tr)
        union_ok &= (te | tr) == pool
        pilot_absent &= not (pilot & (te | tr))
        for innr in fold.get("inner", []):
            itr = set(innr["train_subjects"])
            iva = set(innr["val_subjects"])
            inner_ok &= (not (itr & iva)) and ((itr | iva) == tr) and (not (iva & te))
            pilot_absent &= not (pilot & (itr | iva))

    inv["outer_test_train_disjoint"] = bool(test_train_ok)
    inv["outer_test_union_train_is_main_pool"] = bool(union_ok)
    inv["outer_tests_mutually_disjoint"] = all(
        not (a & b) for i, a in enumerate(tests) for b in tests[i + 1:])
    inv["outer_tests_partition_main_pool"] = set().union(*tests) == pool if tests else False
    inv["inner_structure_valid"] = bool(inner_ok)
    # WI-03 완료 기준의 핵심 문장이다.
    inv["pilot_absent_from_every_fit"] = bool(pilot_absent)
    inv["outer_test_sizes"] = [len(t) for t in tests]
    return inv


def failed_invariants(inv: Mapping[str, Any]) -> List[str]:
    """`fold_invariants` 결과에서 거짓인 불리언 불변식 이름."""
    return sorted(k for k, v in inv.items() if isinstance(v, bool) and not v)


# --------------------------------------------------------------------------- #
# 검증
# --------------------------------------------------------------------------- #


def _walk_file_records(node: Any, trail: str = "") -> List[tuple]:
    """잠금 본문에서 `{"path", "sha256"}` 모양의 레코드를 모두 찾는다."""
    found: List[tuple] = []
    if isinstance(node, dict):
        if isinstance(node.get("path"), str) and isinstance(node.get("sha256"), str):
            found.append((trail or "root", node["path"], node["sha256"]))
        for k, v in node.items():
            found.extend(_walk_file_records(v, f"{trail}/{k}" if trail else str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found.extend(_walk_file_records(v, f"{trail}[{i}]"))
    return found


#: 잠금 본문의 최상위 절 → 그 절의 상대 경로를 푸는 root 이름.
SECTION_ROOTS = {"cohorts": "data_root", "environment": "repo_root"}


def verify_lock(lock: Mapping[str, Any], *, roots: Mapping[str, Path],
                folds_reader=None) -> Dict[str, List[str]]:
    """잠금이 여전히 참인지 **다시 계산해서** 확인한다.

    잠금은 서로 다른 두 기계에 걸쳐 있다. `cohorts` 의 경로는 h197 의 자료
    디렉터리 기준이고, `environment` 의 경로는 저장소 기준이다. 그래서 root 를
    절별로 받는다.

    Args:
        lock: 잠금 파일을 읽은 매핑.
        roots: ``{"data_root": Path, "repo_root": Path}``. 없는 root 의 절은
            건너뛰고 그 사실을 `skipped` 에 남긴다 — 조용히 통과시키지 않는다.
        folds_reader: 테스트용 주입점. 경로를 받아 folds 매핑을 돌려준다.

    Returns:
        ``{"ok", "mismatch", "missing", "invariant", "skipped"}``.
    """
    out: Dict[str, List[str]] = {"ok": [], "mismatch": [], "missing": [],
                                 "invariant": [], "skipped": []}

    if lock.get("schema_version") != SCHEMA_VERSION:
        out["mismatch"].append(
            f"schema_version: 기대 {SCHEMA_VERSION} 실제 {lock.get('schema_version')!r}")

    recorded = lock.get("lock_hash")
    recomputed = lock_hash(lock)
    if recorded != recomputed:
        out["mismatch"].append(
            f"lock_hash: 기록 {str(recorded)[:12]} 재계산 {recomputed[:12]} — 잠금 파일이 수정되었다")
    else:
        out["ok"].append("lock_hash")

    for section, root_name in SECTION_ROOTS.items():
        base = roots.get(root_name)
        records = _walk_file_records(lock.get(section, {}), section)
        if base is None:
            out["skipped"].append(f"{section}: {root_name} 이 주어지지 않아 {len(records)}건 미검사")
            continue
        for where, rel, expect in records:
            p = Path(base) / rel
            if not p.is_file():
                out["missing"].append(f"{where}: {rel}")
                continue
            try:
                got = sha256_file(p)
            except ManifestError as exc:                      # pragma: no cover
                out["missing"].append(f"{where}: {exc}")
                continue
            if got != expect:
                out["mismatch"].append(f"{where}: {rel} 기대 {expect[:12]} 실제 {got[:12]}")
            else:
                out["ok"].append(f"{where}: {rel}")

    data_root = roots.get("data_root")
    reader = folds_reader or (lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
    for name, cohort in (lock.get("cohorts") or {}).items():
        folds_rec = cohort.get("folds")
        if not folds_rec:
            continue
        if data_root is None:
            out["skipped"].append(f"cohorts/{name}: data_root 없음 — 불변식 미재확인")
            continue
        subj_rec = cohort.get("subjects") or {}
        try:
            folds = reader(Path(data_root) / folds_rec["path"])
            eligible = [json.loads(line)["canonical_subject"]
                        for line in (Path(data_root) / subj_rec["path"])
                        .read_text(encoding="utf-8").splitlines()
                        if line.strip() and json.loads(line).get("eligible")]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            out["missing"].append(f"cohorts/{name}: 불변식 재확인 불가 — {exc}")
            continue
        inv = fold_invariants(folds, eligible)
        bad = failed_invariants(inv)
        if bad:
            out["invariant"].append(f"cohorts/{name}: {bad}")
        else:
            out["ok"].append(f"cohorts/{name}: 불변식 {len([k for k,v in inv.items() if isinstance(v,bool)])}건")
        recorded_inv = folds_rec.get("invariants") or {}
        drift = sorted(k for k, v in recorded_inv.items()
                       if k in inv and inv[k] != v)
        if drift:
            out["mismatch"].append(f"cohorts/{name}: 기록된 불변식과 재계산이 다르다 {drift}")

    return out


def lock_is_clean(result: Mapping[str, Sequence[str]]) -> bool:
    """`verify_lock` 결과가 전부 통과인지.

    `skipped` 가 있으면 **깨끗하지 않다.** 검사하지 못한 것을 통과로 세지 않는다.
    """
    return not (result["mismatch"] or result["missing"]
                or result["invariant"] or result.get("skipped"))
