"""h197 스크립트의 계약 시험.

이 파일이 존재하는 이유는 한 가지다. 이번 작업에서 **모듈 함수의 시그니처나
반환 구조를 기억으로 적어** 네 번 깨졌다:

1. `qc_decision(..., task=...)` — 그 인자는 없다
2. `decision["keep"]`, `decision["reasons"]` — 실제 키는 `passed`/`all_reasons`
3. `folds["pilot"]["n_subjects"]` — 실제 키는 `n`
4. `bank.k()` — `k` 는 `@property` 다

네 건 모두 **시험이 없는 스크립트**에서 났다. 시험이 있는 모듈 코드에서는 한 번도
나지 않았다. 그래서 스크립트에도 같은 수준의 접합 시험을 붙인다.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "h197"

#: 실행 가능한 파이썬 스크립트. 셸 스크립트와 requirements 는 제외.
PY_SCRIPTS = sorted(p.name for p in SCRIPT_DIR.glob("*.py")) if SCRIPT_DIR.is_dir() else []


def load_script(name: str):
    """숫자로 시작하는 파일명이라 일반 import 가 안 된다. 경로로 적재한다."""
    path = SCRIPT_DIR / name
    spec = importlib.util.spec_from_file_location(f"_h197_{path.stem}", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"적재 실패: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- 전 스크립트 적재 ---------------------------------------------------------

def test_script_directory_exists():
    assert SCRIPT_DIR.is_dir(), f"스크립트 디렉터리가 없다: {SCRIPT_DIR}"
    assert PY_SCRIPTS, "파이썬 스크립트가 0개다"


@pytest.mark.parametrize("name", PY_SCRIPTS)
def test_script_imports_cleanly(name):
    """적재만으로 깨지는 스크립트가 없어야 한다.

    import 시점 오류(잘못된 이름 import, 문법, 순환)를 전부 여기서 잡는다.
    """
    module = load_script(name)
    assert module is not None


@pytest.mark.parametrize("name", PY_SCRIPTS)
def test_script_has_module_docstring(name):
    module = load_script(name)
    assert (module.__doc__ or "").strip(), f"{name}: 모듈 docstring 이 없다"


@pytest.mark.parametrize("name", PY_SCRIPTS)
def test_script_does_not_run_on_import(name):
    """`if __name__ == "__main__"` 가드가 있어야 적재가 안전하다."""
    source = (SCRIPT_DIR / name).read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in source, f"{name}: main 가드가 없다"


# --- mobse.v2 접합부 계약 -----------------------------------------------------
# 스크립트가 실제로 부르는 것들. 이름·종류(property/함수)·인자를 직접 고정한다.

def test_graph_bank_k_is_a_property_not_a_method():
    """13_bank_demo.py 가 bank.k() 로 불러 깨졌던 건."""
    from mobse.v2.templates import GraphBank

    assert isinstance(inspect.getattr_static(GraphBank, "k"), property)
    assert callable(getattr(GraphBank, "fingerprint")), "fingerprint 는 메서드다"


def test_qc_decision_signature_and_keys():
    """10_wi02_extract.py 가 두 번 깨졌던 건."""
    from mobse.v2.preprocess import fd_quality, fixed_windows, qc_decision, window_fd_quality

    params = inspect.signature(qc_decision).parameters
    assert "residual_dof" in params
    assert "task" not in params, "task 인자는 존재하지 않는다"

    fd = [np.nan] + [0.05] * 300
    windows = fixed_windows(2.0, derivative_start_sec=4.0)
    decision = qc_decision(fd_quality(fd),
                           [window_fd_quality(fd, w) for w in windows],
                           residual_dof=49)
    assert set(decision) == {"passed", "all_reasons", "primary_reason"}


def test_build_folds_return_keys():
    """test_cohort.py 가 깨졌던 건과 같은 접합부."""
    from mobse.v2.splits import build_folds, make_groups

    folds = build_folds(make_groups(subjects=[f"ds002785:sub-{i:04d}"
                                              for i in range(1, 41)]))
    assert "n_subjects_total" in folds
    assert "n" in folds["pilot"] and "n_subjects" not in folds["pilot"]


def test_build_bank_and_transform_signatures():
    """13_bank_demo.py 가 부르는 것들."""
    from mobse.v2.features import fit_transform_on_training_rest, stack_window_features
    from mobse.v2.templates import bank_seed, build_bank, make_null_bank

    p = inspect.signature(fit_transform_on_training_rest).parameters
    assert {"rest_features", "fit_subjects", "n_components", "allowed_subjects"} <= set(p)
    p = inspect.signature(build_bank).parameters
    assert {"correlations", "pca_features", "fit_subjects", "seed", "k", "density"} <= set(p)
    assert "seed" in inspect.signature(make_null_bank).parameters
    assert bank_seed(0, 9) == 30009
    assert len(inspect.signature(stack_window_features).parameters) == 1


def test_write_jsonl_signature():
    """12_build_windows_manifest.py 가 부르는 것."""
    from mobse.v2.manifests import write_jsonl

    p = inspect.signature(write_jsonl).parameters
    assert {"path", "artifact", "records", "overwrite"} <= set(p)


# --- 13_bank_demo.py 를 합성 자료로 통째 실행 -----------------------------------

BANK_DEMO = "13_bank_demo.py"


def _synthetic_rest_manifest(tmp_path: Path, *, n_subjects=12, n_roi=100, n_samples=30):
    """QC 를 통과한 rest run 의 manifest 와 창 .npy 를 만든다."""
    rng = np.random.default_rng(20260917)
    runs = []
    # 세 가지 상태를 섞어 군집이 형성되게 한다
    bases = [rng.normal(size=(n_roi, 3)) for _ in range(3)]
    for s in range(n_subjects):
        subject = f"sub-{s + 1:04d}"
        windows = []
        for w in range(4):
            latent = rng.normal(size=(n_samples, 3)) + bases[w % 3].T.mean()
            block = latent @ bases[w % 3].T + rng.normal(scale=0.5,
                                                         size=(n_samples, n_roi))
            path = tmp_path / f"{subject}_win{w}.npy"
            np.save(path, block.astype(np.float32))
            windows.append({"path": str(path), "sha256": "b" * 64,
                            "shape": [n_samples, n_roi], "start_sec": 12.0 + 60.0 * w,
                            "source_frame_range": [14 + 80 * w, 94 + 80 * w]})
        runs.append({"record_type": "run", "status": "ok",
                     "run_key": f"ds002785/{subject}/na/restingstate/na/mb3",
                     "canonical_subject": f"ds002785:{subject}",
                     "windows": windows})
    manifest = tmp_path / "rest.jsonl"
    header = {"record_type": "header", "dataset": "ds002785",
              "task": "restingstate", "native_tr": 0.75}
    manifest.write_text(
        "\n".join(json.dumps(r) for r in [header] + runs) + "\n", encoding="utf-8")
    return manifest


@pytest.fixture(scope="module")
def bank_demo():
    if not (SCRIPT_DIR / BANK_DEMO).is_file():
        pytest.skip(f"{BANK_DEMO} 없음")
    pytest.importorskip("sklearn")
    return load_script(BANK_DEMO)


def test_bank_demo_loads_rest_windows(bank_demo, tmp_path):
    manifest = _synthetic_rest_manifest(tmp_path)
    windows, subjects = bank_demo.load_rest_windows(manifest)
    assert len(windows) == 48 and len(subjects) == 48
    assert len(set(subjects)) == 12
    assert windows[0].shape == (30, 100)


def test_bank_demo_skips_non_ok_runs(bank_demo, tmp_path):
    manifest = _synthetic_rest_manifest(tmp_path, n_subjects=3)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1]); record["status"] = "excluded"
    lines[1] = json.dumps(record)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    windows, _ = bank_demo.load_rest_windows(manifest)
    assert len(windows) == 8  # 3명 중 1명 제외 → 2명 × 4창


def test_bank_demo_properties_report(bank_demo):
    """bank_properties() 가 T05 가 요구하는 값을 전부 내는지."""
    identity = np.stack([np.eye(5) for _ in range(3)])
    props = bank_demo.bank_properties(identity)
    assert props["shape"] == [3, 5, 5]
    assert props["all_finite"] and props["nonnegative"]
    assert props["symmetric_max_asymmetry"] == 0.0
    assert props["spectral_radius"] == [1.0, 1.0, 1.0]
    assert len(props["offdiag_density"]) == 3


def test_bank_demo_end_to_end(bank_demo, tmp_path):
    """스크립트 main() 을 합성 자료로 끝까지 돌린다."""
    manifest = _synthetic_rest_manifest(tmp_path)
    report = tmp_path / "out" / "bank_demo.json"
    argv = sys.argv  # main() 은 argparse 를 쓰므로 sys.argv 로 호출한다
    try:
        sys.argv = ["13_bank_demo.py", "--manifest", str(manifest),
                    "--report", str(report), "--k", "3"]
        assert bank_demo.main() == 0
    finally:
        sys.argv = argv

    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["n_windows"] == 48 and result["n_subjects"] == 12
    assert result["bank_seed"] == 30009
    assert result["correlations_shape"] == [48, 100, 100]
    assert result["features_shape"] == [48, 4950]
    assert result["pca_shape"] == [48, 10]
    assert sum(result["cluster_sizes"]) == 48

    props = result["bank_properties"]
    assert props["nonnegative"] and props["all_finite"]
    assert props["symmetric_max_asymmetry"] < 1e-12
    for radius in props["spectral_radius"]:
        assert abs(radius - 1.0) < 1e-9, "self-loop 정규화가 깨졌다"
    for density in props["offdiag_density"]:
        assert abs(density - 0.20) < 0.01

    # T05 — joint permutation 은 spectrum 을 보존한다
    assert result["spectrum_max_abs_diff"] < 1e-9


def test_bank_demo_fails_on_empty_manifest(bank_demo, tmp_path):
    manifest = tmp_path / "empty.jsonl"
    manifest.write_text(json.dumps(
        {"record_type": "header", "dataset": "ds002785", "task": "restingstate"}) + "\n",
        encoding="utf-8")
    argv = sys.argv
    try:
        sys.argv = ["13_bank_demo.py", "--manifest", str(manifest),
                    "--report", str(tmp_path / "r.json")]
        assert bank_demo.main() == 1
    finally:
        sys.argv = argv

# --- 15_build_subjects.py 계약 ------------------------------------------------

BUILD_SUBJECTS = "15_build_subjects.py"


@pytest.fixture(scope="module")
def build_subjects_script():
    if not (SCRIPT_DIR / BUILD_SUBJECTS).is_file():
        pytest.skip(f"{BUILD_SUBJECTS} 없음")
    return load_script(BUILD_SUBJECTS)


def _extract_manifest(tmp_path: Path, task: str, subjects, *, dataset="ds002785",
                      status="ok"):
    """WI-02 형식의 run manifest 를 만든다."""
    header = {"record_type": "header", "dataset": dataset, "task": task}
    runs = [{"record_type": "run", "status": status,
             "canonical_subject": f"{dataset}:{s}",
             "run_key": f"{dataset}/{s}/na/{task}/na/seq"} for s in subjects]
    path = tmp_path / f"wi02_{dataset}_{task}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in [header] + runs) + "\n",
                    encoding="utf-8")
    return path


def _run_script(module, argv):
    saved = sys.argv
    try:
        sys.argv = argv
        return module.main()
    finally:
        sys.argv = saved


def test_build_subjects_happy_path(build_subjects_script, tmp_path):
    subjects = [f"sub-{i:04d}" for i in range(1, 11)]
    paths = [_extract_manifest(tmp_path, t, subjects)
             for t in ("emomatching", "workingmemory", "restingstate")]
    out = tmp_path / "cohort"
    rc = _run_script(build_subjects_script,
                     [BUILD_SUBJECTS, "--manifest", *map(str, paths),
                      "--output-dir", str(out)])
    assert rc == 0
    records = [json.loads(l) for l in (out / "subjects.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    assert len(records) == 10
    assert all(r["eligible"] for r in records)
    summary = json.loads((out / "cohort_summary.json").read_text(encoding="utf-8"))
    assert summary["n_eligible"] == 10
    assert not (out / "exclusions.jsonl").exists()


def test_build_subjects_refuses_missing_task_manifest(build_subjects_script, tmp_path):
    """rest 를 빼고 돌리면 전원 부적격이 된다 — 조용히 내지 않고 실패시킨다."""
    subjects = [f"sub-{i:04d}" for i in range(1, 6)]
    paths = [_extract_manifest(tmp_path, t, subjects)
             for t in ("emomatching", "workingmemory")]
    rc = _run_script(build_subjects_script,
                     [BUILD_SUBJECTS, "--manifest", *map(str, paths),
                      "--output-dir", str(tmp_path / "c")])
    assert rc == 1


def test_build_subjects_refuses_mixed_datasets(build_subjects_script, tmp_path):
    a = _extract_manifest(tmp_path, "emomatching", ["sub-0001"], dataset="ds002785")
    b = _extract_manifest(tmp_path, "workingmemory", ["sub-0001"], dataset="ds002790")
    c = _extract_manifest(tmp_path, "restingstate", ["sub-0001"], dataset="ds002785")
    rc = _run_script(build_subjects_script,
                     [BUILD_SUBJECTS, "--manifest", str(a), str(b), str(c),
                      "--output-dir", str(tmp_path / "c")])
    assert rc == 1


def test_build_subjects_writes_exclusions(build_subjects_script, tmp_path):
    subjects = [f"sub-{i:04d}" for i in range(1, 6)]
    paths = [_extract_manifest(tmp_path, "emomatching", subjects, status="excluded"),
             _extract_manifest(tmp_path, "workingmemory", subjects),
             _extract_manifest(tmp_path, "restingstate", subjects)]
    out = tmp_path / "cohort"
    rc = _run_script(build_subjects_script,
                     [BUILD_SUBJECTS, "--manifest", *map(str, paths),
                      "--output-dir", str(out)])
    assert rc == 0
    exclusions = [json.loads(l) for l in (out / "exclusions.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    assert len(exclusions) == 5
    assert all(e["all_reasons"] for e in exclusions)


def test_build_subjects_refuses_overwrite(build_subjects_script, tmp_path):
    subjects = ["sub-0001", "sub-0002"]
    paths = [_extract_manifest(tmp_path, t, subjects)
             for t in ("emomatching", "workingmemory", "restingstate")]
    argv = [BUILD_SUBJECTS, "--manifest", *map(str, paths),
            "--output-dir", str(tmp_path / "c")]
    assert _run_script(build_subjects_script, argv) == 0
    assert _run_script(build_subjects_script, argv) == 1  # 두 번째는 거부

# --- watcher 스크립트의 프로토콜 준수 ------------------------------------------

def test_piop2_watcher_does_not_split():
    """계획서 §9 — PIOP2 는 held-out 외부 코호트이므로 fold 로 나누지 않는다.

    12회차 계획에서 external.yaml 로 split 을 돌리려 했다가 잡은 오류다.
    5-fold outer CV 구조를 만들어 두면 프로토콜에 없는 산출물이 남아 나중에
    의미 있는 것으로 오인될 수 있다.
    """
    path = SCRIPT_DIR / "16_watch_and_process_piop2.sh"
    if not path.is_file():
        pytest.skip(f"{path.name} 없음")
    source = path.read_text(encoding="utf-8")
    assert "cli split" not in source, "PIOP2 watcher 가 split 을 부른다"
    assert "splits_piop2" not in source, "PIOP2 분할 산출 경로가 있다"
    assert "held-out" in source, "왜 분할하지 않는지 근거가 적혀 있어야 한다"


@pytest.mark.parametrize("name", ["14_watch_and_extract_piop1.sh",
                                  "16_watch_and_process_piop2.sh"])
def test_watchers_require_zero_part_files(name):
    """완료 판정에 '.part == 0' 이 반드시 들어가야 한다.

    7회차에서 로그의 구간 진입만 믿었다면 24개가 전송 중인 상태로 시작했을 것이다.
    """
    path = SCRIPT_DIR / name
    if not path.is_file():
        pytest.skip(f"{name} 없음")
    source = path.read_text(encoding="utf-8")
    assert "*.part" in source, f"{name}: .part 검사가 없다"
    assert "MAX_WAIT_SEC" in source, f"{name}: 무한 대기 방지 장치가 없다"


@pytest.mark.parametrize("name", ["14_watch_and_extract_piop1.sh",
                                  "16_watch_and_process_piop2.sh"])
def test_watchers_build_windows_from_target_tasks_only(name):
    """창 manifest 는 target 2종만 받는다 — rest 를 넣으면 labels.py 가 거부한다."""
    path = SCRIPT_DIR / name
    if not path.is_file():
        pytest.skip(f"{name} 없음")
    source = path.read_text(encoding="utf-8")
    if "12_build_windows_manifest.py" not in source:
        pytest.skip("창 manifest 단계가 없다")
    start = source.index("12_build_windows_manifest.py")
    block = source[start:start + 500]
    assert "restingstate" not in block, f"{name}: 창 manifest 에 rest 가 들어간다"


# --------------------------------------------------------------------------- #
# E12 5회차 — 호출부를 정적으로 검사한다
# --------------------------------------------------------------------------- #
#
# 위 `test_build_bank_and_transform_signatures` 는 **라이브러리 쪽 계약**만
# 고정한다. 계약이 존재하는지는 확인해도, 새로 쓴 스크립트가 그 계약대로
# 부르는지는 보지 않는다. 실제로 21_resource_benchmark.py 가
# `fit_transform_on_training_rest(feats)` 로 부르고도 suite 를 통과했고,
# 실행 시점에 TypeError 로 터졌다.
#
# 아래 시험은 스크립트의 AST 에서 mobse.v2 함수 호출을 찾아 **실제 시그니처에
# bind 해 본다.** 임포트만으로는 잡히지 않는 부류를 정적으로 잡는다.


def _resolve_library_callables(tree, module_source_name):
    """AST 의 import 문에서 `mobse.v2.*` 호출 가능 객체의 이름 매핑을 만든다.

    Returns:
        ``{"로컬이름": 객체}`` 와 ``{"모듈별칭": 모듈}`` 두 매핑.
    """
    import importlib

    names = {}
    modules = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.module or not node.module.startswith("mobse.v2"):
                continue
            for alias in node.names:
                target = alias.asname or alias.name
                try:
                    mod = importlib.import_module(node.module)
                except Exception:                                  # pragma: no cover
                    continue
                obj = getattr(mod, alias.name, None)
                if obj is None:
                    try:
                        modules[target] = importlib.import_module(
                            f"{node.module}.{alias.name}")
                    except Exception:                              # pragma: no cover
                        pass
                elif inspect.ismodule(obj):
                    modules[target] = obj
                elif callable(obj):
                    names[target] = obj
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("mobse.v2"):
                    try:
                        modules[alias.asname or alias.name] = \
                            importlib.import_module(alias.name)
                    except Exception:                              # pragma: no cover
                        pass
    return names, modules


class _Any:
    """bind 용 자리표시자."""


def _call_target(node, names, modules):
    """`ast.Call` 이 가리키는 라이브러리 callable 과 표시 이름."""
    f = node.func
    if isinstance(f, ast.Name) and f.id in names:
        return names[f.id], f.id
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        mod = modules.get(f.value.id)
        if mod is not None:
            obj = getattr(mod, f.attr, None)
            if callable(obj) and not inspect.isclass(obj):
                return obj, f"{f.value.id}.{f.attr}"
    return None, None


@pytest.mark.parametrize("name", PY_SCRIPTS)
def test_script_call_sites_match_library_signatures(name):
    """스크립트가 mobse.v2 함수를 실제 시그니처대로 부르는지 정적으로 확인한다."""
    path = SCRIPT_DIR / name
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names, modules = _resolve_library_callables(tree, name)
    if not names and not modules:
        pytest.skip(f"{name}: mobse.v2 임포트 없음")

    problems = []
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target, shown = _call_target(node, names, modules)
        if target is None:
            continue
        if any(isinstance(a, ast.Starred) for a in node.args) or \
                any(k.arg is None for k in node.keywords):
            continue                                   # *args/**kwargs 는 판정 불가
        try:
            sig = inspect.signature(target)
        except (TypeError, ValueError):                # pragma: no cover
            continue
        checked += 1
        try:
            sig.bind(*[_Any() for _ in node.args],
                     **{k.arg: _Any() for k in node.keywords})
        except TypeError as exc:
            problems.append(f"{name}:{node.lineno} {shown}(...) — {exc}")

    assert not problems, "\n".join(problems)
    assert checked >= 0


def _scan_source(src: str, name: str = "<scratch>"):
    """`test_script_call_sites_match_library_signatures` 의 검사 로직을 소스에 적용."""
    tree = ast.parse(src)
    names, modules = _resolve_library_callables(tree, name)
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target, shown = _call_target(node, names, modules)
        if target is None:
            continue
        if any(isinstance(a, ast.Starred) for a in node.args) or \
                any(k.arg is None for k in node.keywords):
            continue
        try:
            inspect.signature(target).bind(
                *[_Any() for _ in node.args],
                **{k.arg: _Any() for k in node.keywords})
        except TypeError as exc:
            problems.append(f"{name}:{node.lineno} {shown}(...) — {exc}")
    return problems


def test_call_site_checker_catches_the_actual_mistake_that_happened():
    """실제로 저질렀던 호출을 검사기가 잡는지 확인한다 (E12 5회차).

    `fit_transform_on_training_rest(feats)` 는 `fit_subjects` 가 빠져 있다.
    가드가 이 줄을 잡지 못하면 가드가 아니다.
    """
    bad = ("from mobse.v2 import features as F\n"
           "F.fit_transform_on_training_rest(feats)\n")
    problems = _scan_source(bad)
    assert len(problems) == 1, problems
    assert "fit_transform_on_training_rest" in problems[0]

    good = ("from mobse.v2 import features as F\n"
            "F.fit_transform_on_training_rest(feats, subs)\n")
    assert _scan_source(good) == []


def test_call_site_checker_handles_both_import_forms():
    from_form = ("from mobse.v2.templates import build_bank\n"
                 "build_bank(corr, pca)\n")            # fit_subjects, seed 누락
    assert _scan_source(from_form), "from-import 형태를 놓쳤다"

    mod_form = ("from mobse.v2 import templates as T\n"
                "T.build_bank(corr, pca, subs, seed=1)\n")
    assert _scan_source(mod_form) == []


def test_call_site_checker_ignores_starargs_rather_than_guessing():
    src = ("from mobse.v2 import templates as T\n"
           "T.build_bank(*args, **kw)\n")
    assert _scan_source(src) == [], "*args/**kwargs 는 판정 불가이므로 건너뛰어야 한다"


# --------------------------------------------------------------------------- #
# 마감 절차 3단계 — 인용 수치 대조기가 실제로 잡는가
# --------------------------------------------------------------------------- #


def _crosscheck_module():
    return load_script("22_crosscheck_reported_numbers.py")


def _fake_source():
    """대조를 통과하는 최소 자료. 각 시험이 여기서 한 군데씩 어긋뜨린다."""
    cells = []
    for n in (126, 189):
        for pi in (0.05, 0.10, 0.20, 0.30):
            for delta in (0.00, 0.02, 0.04):
                cells.append({"n_subjects": n, "pi": pi, "rho_latent": 0.0,
                              "delta_true": delta,
                              "p_lower_gt_0": 0.100 if delta == 0.02 else 0.010,
                              "p_lower_gt_delta": 0.010})
    mde = [{"n_subjects": 126, "pi": 0.05, "rho_latent": 0.0, "mde": 0.041}]
    prec = {"cells": cells, "minimum_detectable_effect": mde}
    res = {"cells_inner_scale": {"A": {"epoch": {"median_s": 0.100},
                                       "peak_gpu_bytes": 100 * 1048576}},
           "cells_outer_scale": {"A": {"epoch": {"median_s": 0.200},
                                       "peak_gpu_bytes": 100 * 1048576}},
           "fit_budget": {"total": 768}}
    lock = {"endpoint": {"n_primary_oof": 126, "n_external": 189},
            "cohorts": {"piop1": {"folds": {"split_hash": "s" * 64}},
                        "piop2": {"folds": None}},
            "wi07_completion_targets": {"window_prediction_rows": 126 * 2 * 4 * 3 * 4},
            "lock_hash": "L" * 64}
    md_prec = ("0.100 0.010–0.010 0.010–0.010 0.041 ")
    md_res = ("0.100 – 0.100 s 0.200 – 0.200 s 100.0–100.0 MiB 768")
    report = "0.100 " + "L" * 12 + " " + "s" * 12
    return {"prec": prec, "res": res, "lock": lock,
            "md_prec": md_prec, "md_res": md_res, "report": report}


def test_crosscheck_passes_on_consistent_documents():
    mod = _crosscheck_module()
    assert mod.crosscheck(_fake_source()) == []


def test_crosscheck_catches_a_wrong_quoted_number():
    mod = _crosscheck_module()
    src = _fake_source()
    src["md_prec"] = src["md_prec"].replace("0.100", "0.900")
    fails = mod.crosscheck(src)
    assert fails and any("δ=0.02" in f for f in fails), fails


def test_crosscheck_catches_a_missing_mde_row():
    mod = _crosscheck_module()
    src = _fake_source()
    src["md_prec"] = src["md_prec"].replace("0.041", "")
    assert any("MDE" in f for f in mod.crosscheck(src))


def test_crosscheck_catches_piop2_being_split():
    """§9 위반은 문장이 아니라 잠금에서 잡아야 한다."""
    mod = _crosscheck_module()
    src = _fake_source()
    src["lock"]["cohorts"]["piop2"]["folds"] = {"split_hash": "x" * 64}
    assert any("§9" in f for f in mod.crosscheck(src))


def test_crosscheck_allows_the_corrected_phrase_only_inside_a_quote():
    mod = _crosscheck_module()
    src = _fake_source()
    src["report"] += "\n> 하한 > δ 는 48개 칸 어디서도 0.02 를 넘지 않는다.\n"
    assert mod.crosscheck(src) == [], "인용(blockquote)은 허용해야 한다"
    src["report"] += "\n하한 > δ 는 48개 칸 어디서도 0.02 를 넘지 않는다.\n"
    assert any("과잉 일반화" in f for f in mod.crosscheck(src)), "인용 밖은 잡아야 한다"


def _gate_ok():
    return {"wi03_measurement_lock": {"lock_hash": "L" * 64,
                                      "chain": ["O" * 12, "L" * 12]},
            "gates": [{"checks": [{"note": "잠금 " + "L" * 12 + " 로 잠갔다"}]}]}


def test_crosscheck_gate_passes_with_current_lock():
    mod = _crosscheck_module()
    src = _fake_source()
    src["gate"] = _gate_ok()
    assert mod.crosscheck(src) == []


def test_crosscheck_gate_catches_stale_lock_in_verdict_text():
    """rev24 사고 재현: G1 판정 문장이 대체된 잠금을 인용."""
    mod = _crosscheck_module()
    src = _fake_source()
    src["gate"] = _gate_ok()
    src["gate"]["gates"][0]["checks"][0]["note"] = "잠금 " + "O" * 12 + " 로 잠갔다"
    assert any("대체된 잠금" in f for f in mod.crosscheck(src))


def test_crosscheck_gate_catches_stale_lock_hash_field():
    mod = _crosscheck_module()
    src = _fake_source()
    src["gate"] = _gate_ok()
    src["gate"]["wi03_measurement_lock"]["lock_hash"] = "O" * 64
    assert any("현행 잠금이 아니다" in f for f in mod.crosscheck(src))
