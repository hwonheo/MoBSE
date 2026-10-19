"""R2T T1 경로 (결정 87) — 전처리된 task 신호의 가린 ROI 복원 (모델 단계). 기존 W-local 경로 (`r2t_lib` · `mix` ·
`select_rules`) 는 바꾸지 않고 함수만 불러 쓴다.

T1 처리 규칙 (계획서 v1.3 §2, pilot 설계 v1):
* 입력 · 정답은 기존 산출 값 그대로 (run 단위 회귀 · ROI z-score). 창 안 추가 처리 없음 (항등).
* 가린 ROI 값은 정답에만. 관측 열만 모델로 간다 (``t1_split``).
* NMSE 분모 v_r = 그 fold **train** 사람 task 창의 정답 분산 (test 는 받지 않음).
* prior · ridge · 혼합은 fold train 사람의 rest 창만으로. BEST · τ 는 inner train 적합 → inner val 로 선택 → fold train 재적합.
* τ 후보 {0, τ_ESS, 1}. T1 판 ρ̂ 은 창 · ROI 마다 평균을 뺀 뒤 lag-1 자기상관 (T1 창은 평균이 0 이 아니라서) — train 만.
* 혼합 실패 fold 는 "실패" (G1 대체 없음), τ̂ = 0 은 "적응 미선택".

실제 자료 값을 읽는 ``load_real`` 은 ``allow_real_data=True`` 없이는 거부한다. 결정 87 범위에서는 호출하지 않는다.
``preflight`` 는 manifest · 파일 목록 · npy 헤더 (shape · dtype) 만 읽는다.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

import mix as M
import r2t_lib as R
import select_rules as SR

Windows = Dict[str, List[np.ndarray]]


# ---------------------------------------------------------------- 설정 · 자료 모양

def load_config(path) -> dict:
    return json.loads(Path(path).read_text())


def cut_windows(series: np.ndarray, length: int, start: int = 0) -> List[np.ndarray]:
    """(T × R) → 겹치지 않는 length frame 창 (start 부터, 남는 frame 은 버림)."""
    return [np.array(series[i:i + length]) for i in range(start, series.shape[0] - length + 1, length)]


def left_from_atlas_tsv(path) -> np.ndarray:
    """Schaefer dseg tsv (index · name) → 열 순서 (index 1..n → 0..n−1) 의 좌반구 bool."""
    rows = [ln.split("\t") for ln in Path(path).read_text().splitlines()[1:] if ln.strip()]
    idx = np.array([int(r[0]) for r in rows])
    if not np.array_equal(idx, np.arange(1, len(rows) + 1)):
        raise ValueError("atlas index 가 1..n 연속이 아니다")
    return np.array(["_LH_" in r[1] for r in rows])


def person_folds(ids: Sequence[str], n_folds: int, seed: int) -> List[List[str]]:
    """사람 단위 fold — 정렬한 id 를 seed 로 섞어 array_split. 각 사람은 정확히 한 fold 의 test."""
    ids = sorted(ids)
    perm = np.random.default_rng(seed).permutation(len(ids))
    return [sorted(ids[i] for i in part) for part in np.array_split(perm, n_folds)]


# ---------------------------------------------------------------- T1 처리 (항등)

def t1_split(window: np.ndarray, obs: np.ndarray, msk: np.ndarray):
    if np.intersect1d(obs, msk).size:
        raise R.LeakError("관측 ROI 와 가린 ROI 가 겹친다")
    return np.array(window[:, obs], copy=True), np.array(window[:, msk], copy=True)


def t1_frames(windows: Windows, ids: Sequence[str]) -> np.ndarray:
    return np.concatenate([w for s in ids for w in windows[s]])


def t1_windows(windows: Windows, ids: Sequence[str]) -> np.ndarray:
    return np.stack([w for s in ids for w in windows[s]])


def t1_stack(windows: Windows, ids, obs, msk):
    X = np.concatenate([w[:, obs] for s in ids for w in windows[s]])
    Y = np.concatenate([w[:, msk] for s in ids for w in windows[s]])
    return X, Y


def t1_target_variance(task: Windows, train_ids, obs, msk) -> np.ndarray:
    _, Y = t1_stack(task, train_ids, obs, msk)
    return np.maximum(Y.var(0), R.VAR_FLOOR)


def rho_hat_t1(Xw: np.ndarray) -> float:
    return SR.rho_hat(Xw - Xw.mean(axis=1, keepdims=True))


def tau_ess_t1(Xw: np.ndarray) -> float:
    rho = float(np.clip(rho_hat_t1(Xw), 0.0, 0.99))
    return (1 - rho) / (1 + rho)


# ---------------------------------------------------------------- 평가

def subject_nmse(task: Windows, eval_ids, v_ids, masks, n_roi, make_pred) -> np.ndarray:
    R.check_disjoint(v_ids, eval_ids)
    per = {s: [] for s in eval_ids}
    for msk in masks:
        obs = np.setdiff1d(np.arange(n_roi), msk)
        v = t1_target_variance(task, v_ids, obs, msk)
        pred = make_pred(obs, msk)
        for s in eval_ids:
            for win in task[s]:
                x, y = t1_split(win, obs, msk)
                per[s].append(R.nmse_terms(y, pred(x, obs, msk), v).ravel())
    return np.array([np.mean(np.concatenate(per[s])) for s in eval_ids])


def _baseline(name: str, rest: Windows, fit_ids):
    if name in ("G1-LW", "G1-OAS"):
        g = R.fit_prior(t1_frames(rest, fit_ids), "lw" if name == "G1-LW" else "oas", fit_ids)
        return lambda obs, msk: (lambda x, o, m: g.predict(x, o, m))
    lam = float(name.split("=")[1])

    def make(obs, msk):
        X, Y = t1_stack(rest, fit_ids, obs, msk)
        rg = R.fit_ridge(X, Y, lam, fit_ids)
        return lambda x, o, m: rg.predict(x)
    return make


def _fit_kw(cfg) -> dict:
    m = cfg["mix"]
    return {"seed": m["em_seed"], "n_init": m["n_init"], "max_iter": m["max_iter"], "tol": m["tol"],
            "min_occupancy": m["min_occupancy"], "eig_floor": m["eig_floor_rel"]}


def _mix_pred(fit, tau):
    return lambda obs, msk: (lambda x, o, m: M.predict_adaptive(fit, x, o, m, tau=tau)[0])


# ---------------------------------------------------------------- fold 한 판

def run_fold(rest: Windows, task: Windows, train, test, masks, n_roi: int, cfg: dict, fold: int) -> dict:
    R.check_disjoint(train, test)
    tie = cfg["selection"]["tie"]
    inner_tr, inner_va = R.subject_split(train, cfg["split"]["inner_val_frac"], seed=cfg["split"]["inner_seed"])   # 모든 fold 같은 seed (설계 문서 그대로), train 명단이 달라 분할은 fold 마다 다름
    best_scores = [(b, float(subject_nmse(task, inner_va, inner_tr, masks, n_roi, _baseline(b, rest, inner_tr)).mean()))
                   for b in cfg["best_candidates"]]
    best = SR._pick(best_scores, tie)
    rec = {"fold": fold, "train": list(train), "test": list(test), "inner_train": inner_tr, "inner_val": inner_va,
           "best": best, "best_scores": best_scores,
           "nmse": {"BEST": subject_nmse(task, test, train, masks, n_roi, _baseline(best, rest, train))}}
    K, kw = cfg["mix"]["K"], _fit_kw(cfg)
    Xi = t1_windows(rest, inner_tr)
    fi = M.fit_mixture(Xi, K, inner_tr, **kw)
    rec["inner_mix_status"] = fi.status
    if fi.status != "ok":
        rec.update(mix="실패", mix_reason=f"inner: {fi.reason}")
        return rec
    te = tau_ess_t1(Xi)
    grid = [("0", 0.0), ("ess", te), ("1", 1.0)]
    assert [g[0] for g in grid] == cfg["mix"]["tau_candidates"]
    tau_scores = [(lab, float(subject_nmse(task, inner_va, inner_tr, masks, n_roi, _mix_pred(fi, t)).mean()))
                  for lab, t in grid]
    lab = SR._pick(tau_scores, tie)
    rec.update(tau_label=lab, tau=dict(grid)[lab], tau_ess=te, tau_scores=tau_scores)
    f = M.fit_mixture(t1_windows(rest, train), K, train, **kw)
    rec["mix_status"] = f.status
    if f.status != "ok":
        rec.update(mix="실패", mix_reason=f"train: {f.reason}")
        return rec
    mp = SR.pooled_prior(f)
    rec["nmse"]["MIX-a"] = subject_nmse(task, test, train, masks, n_roi, _mix_pred(f, rec["tau"]))
    rec["nmse"]["MIX-p"] = subject_nmse(task, test, train, masks, n_roi, lambda o, m: (lambda x, oo, mm: mp.predict(x, oo, mm)))
    rec["nmse"]["MIX-f"] = subject_nmse(task, test, train, masks, n_roi,
                                        lambda o, m: (lambda x, oo, mm: M.predict_fixed(f, x, oo, mm)))
    rec.update(mix="ok", pis=f.pis.tolist(), shrinkage=f.shrinkage.tolist(),
               cond=[float(np.linalg.cond(c)) for c in f.covs])
    return rec


# ---------------------------------------------------------------- 전체 · 판정

def verdict(folds: List[dict], delta_ci, nonfinite: bool, cfg: dict) -> dict:
    fails = sum(1 for r in folds if r.get("mix") != "ok")
    flags = []
    if nonfinite:
        flags.append("중단: 비유한 예측")
    if fails > cfg["stop_rules"]["mix_fail_folds_max"]:
        flags.append(f"중단: 혼합 실패 fold {fails}/{len(folds)}")
    ok = [r for r in folds if r.get("mix") == "ok"]
    if delta_ci is not None and delta_ci[2] < 0:
        flags.append("K>1 경로 중단 권고: Δ 상한 < 0")
    if ok and all(r["tau"] == 0.0 for r in ok):
        flags.append("적응 경로 중단 권고: 모든 fold τ̂ = 0")
    stop = any(f.startswith("중단") for f in flags)
    return {"flags": flags, "stop": stop, "mix_fail_folds": fails,
            "next": "중단 · 보고" if stop else "기술값 보고 → 본 분석 잠금 여부를 묻는다"}


def run_pipeline(rest: Windows, task: Windows, subjects: Sequence[str], cfg: dict, left: np.ndarray) -> dict:
    n_roi = len(left)
    bad = sorted({s for d in (rest, task) for s in subjects for w in d[s] if not np.all(np.isfinite(w))})
    if bad:                                                   # 선택 단계가 비유한 점수를 비교하지 못하므로 시작 전에 멈춘다
        return {"n_subjects": len(subjects), "nonfinite_input_subjects": len(bad),
                "verdict": {"flags": ["중단: 비유한 입력"], "stop": True, "mix_fail_folds": None, "next": "중단 · 보고"}}
    masks = R.make_masks(n_roi, cfg["mask"]["frac"], cfg["mask"]["n_masks"], seed=cfg["mask"]["seed"], left=left)
    tests = person_folds(subjects, cfg["split"]["n_folds"], cfg["split"]["fold_seed"])
    seen = sorted(s for t in tests for s in t)
    if seen != sorted(subjects) or len(seen) != len(set(seen)):
        raise R.LeakError("각 사람이 정확히 한 번 test 에 들어가지 않는다")
    folds = []
    for k, test in enumerate(tests):
        train = sorted(set(subjects) - set(test))
        folds.append(run_fold(rest, task, train, test, masks, n_roi, cfg, k))
    per = {}
    for r in folds:
        for m, arr in r["nmse"].items():
            for s, v in zip(r["test"], arr):
                per.setdefault(m, {})[s] = float(v)
    nonfinite = any(not np.isfinite(v) for d in per.values() for v in d.values())
    ok_subj = sorted(s for r in folds if r.get("mix") == "ok" for s in r["test"])
    delta_ci = None
    if ok_subj and not nonfinite:
        d = R.delta(np.array([per["BEST"][s] for s in ok_subj]), np.array([per["MIX-a"][s] for s in ok_subj]))
        delta_ci = R.subject_bootstrap(d, cfg["bootstrap"]["n"], seed=cfg["bootstrap"]["seed"])
    aux = {}
    if ok_subj and not nonfinite:
        for a, b in (("MIX-a", "MIX-p"), ("MIX-a", "MIX-f"), ("MIX-p", "BEST")):
            dd = R.delta(np.array([per[b][s] for s in ok_subj]), np.array([per[a][s] for s in ok_subj]))
            aux[f"{a} 대 {b}"] = R.subject_bootstrap(dd, cfg["bootstrap"]["n"], seed=cfg["bootstrap"]["seed"])
    out = {"n_subjects": len(subjects), "n_ok_subjects": len(ok_subj), "masks": [m.tolist() for m in masks],
           "per_subject_nmse": per, "delta_best_minus_mixa": delta_ci,
           "delta_sd": float(np.std(d, ddof=1)) if delta_ci else None, "aux": aux,
           "folds": [{k: v for k, v in r.items() if k != "nmse"} for r in folds],
           "delta_report_only": cfg["delta_report_only"]}
    out["verdict"] = verdict(folds, delta_ci, nonfinite, cfg)
    return out


# ---------------------------------------------------------------- 실제 자료 (이번 범위에서는 호출하지 않음)

def pilot_subjects(cfg, root=".") -> List[str]:
    f = json.loads((Path(root) / cfg["subjects"]["source"]).read_text())
    raw = f["pilot"]["subjects"]                       # 형식 "ds002785:sub-XXXX" — 파일 · manifest 는 접두어 없는 이름
    prefixes = {x.split(":", 1)[0] for x in raw}
    if prefixes != {cfg["subjects"]["dataset"]}:
        raise ValueError(f"pilot 목록의 dataset 접두어가 {prefixes} — {cfg['subjects']['dataset']} 만 허용")
    subs = sorted(x.split(":", 1)[1] for x in raw)
    if len(subs) != cfg["subjects"]["expected_n"]:
        raise ValueError(f"pilot 인원 {len(subs)} ≠ {cfg['subjects']['expected_n']}")
    return subs


def _npy_header(fh):
    version = np.lib.format.read_magic(fh)
    reader = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}[version]
    shape, fortran, dtype = reader(fh)
    return list(shape), str(dtype)


def preflight(cfg, root=".") -> dict:
    """manifest · 파일 존재 · npy 헤더만 읽는다 (값을 읽지 않음)."""
    root = Path(root)
    subs = pilot_subjects(cfg, root)
    man = json.loads((root / cfg["data"]["task_manifest"]).read_text())["runs"]
    mrec = {r["subject"]: r for r in man}
    problems, shapes = [], {"task": set(), "rest": set()}
    for s in subs:
        r = mrec.get(s)
        if r is None or r["status"] != "ok" or r["n_frames"] != cfg["data"]["task_frames"] or not r["qc_passed_wi02"]:
            problems.append(f"{s}: manifest 조건 불충족")
        tp = root / cfg["data"]["task_full_ts"].format(s=s)
        if not tp.is_file():
            problems.append(f"{s}: task 파일 없음")
        else:
            with zipfile.ZipFile(tp) as z, z.open(f"{cfg['data']['task_key']}.npy") as fh:
                sh, dt = _npy_header(fh)
                shapes["task"].add((tuple(sh), dt))
        for i in range(cfg["data"]["rest_windows_per_subject"]):
            rp = root / cfg["data"]["rest_window"].format(s=s, i=i)
            if not rp.is_file():
                problems.append(f"{s}: rest 창 {i} 없음")
                continue
            with open(rp, "rb") as fh:
                sh, dt = _npy_header(fh)
                shapes["rest"].add((tuple(sh), dt))
    left = left_from_atlas_tsv(root / cfg["data"]["atlas_tsv"])
    return {"n_subjects": len(subs), "problems": problems,
            "task_shapes": sorted(map(str, shapes["task"])), "rest_shapes": sorted(map(str, shapes["rest"])),
            "atlas_lh": int(left.sum()), "atlas_n": int(len(left)), "values_read": False}


def load_real(cfg, root=".", *, allow_real_data: bool = False):
    """실제 값 적재 — 승인 (pilot 실행) 전에는 거부한다."""
    if not allow_real_data:
        raise PermissionError("실제 자료 값 적재는 pilot 실행 승인 뒤에만 (결정 87 범위 밖)")
    root = Path(root)
    subs = pilot_subjects(cfg, root)
    L = cfg["window"]["length"]
    task = {s: cut_windows(np.load(root / cfg["data"]["task_full_ts"].format(s=s))[cfg["data"]["task_key"]].astype(float), L)
            for s in subs}
    rest = {s: [w for i in range(cfg["data"]["rest_windows_per_subject"])
                for w in cut_windows(np.load(root / cfg["data"]["rest_window"].format(s=s, i=i)).astype(float), L)]
            for s in subs}
    return subs, rest, task
