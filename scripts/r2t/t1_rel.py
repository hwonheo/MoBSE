"""R2T T1 신뢰성 보완판 F4R — F4 와 같은 알고리즘 + 실패 분류 · 처리 규칙 + 감사 기록. **합성 자료만.**

사전 규칙: `docs/experiments/r2t_t1_reliability_2026-10-17.md` 0 절. F4 고정본 · `t1_reg4` 는 바꾸지 않고 불러 쓴다.

* 실패 분류 (0.2): restart 상태 ok · not_converged · sparse_component (정상 실패) · numerical · nonfinite (수치 실패).
* 처리 (0.3): R3 정상 실패로만 혼합이 안 되면 BEST fallback, R4 수치 실패가 섞이면 fold 중단 (stop_numerical),
  R5 수치 실패가 있었지만 진행되면 경고, R6 최종 적합 유한 · SPD 재검사, R7 31 명 분모.
* 기록 (0.4): 명단 · mask · 후보 점수 · 적합 기록 · 사람별 NMSE · 예측 배열 · Δ SD.
* 공정성 (0.5): BEST-T (43 후보, 같은 정보) 와 선택 과적합 진단 (낙관 · regret, test 최선은 oracle 진단값).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

import mix as M
import r2t_lib as R
import select_rules as SR
import t1
import t1_reg as F1
import t1_reg2 as F2
import t1_reg3 as F3
import t1_reg4 as F4

NORMAL = ("not_converged", "sparse_component")
NUMERIC = ("numerical", "nonfinite")
ROOT = Path(__file__).resolve().parents[2]
CODE_FILES = ("t1_rel.py", "t1_reg4.py", "t1_reg3.py", "t1_reg2.py", "t1_reg.py", "t1.py", "mix.py", "r2t_lib.py",
              "select_rules.py", "synth.py", "synth_mix.py", "synth_variants.py", "synth_t1.py", "synth_t1_hard.py")


# ---------------------------------------------------------------- 실패 분류 · 적합 기록

def fit_is_finite_spd(fit: M.MixFit) -> Optional[str]:
    """문제가 없으면 None, 있으면 이유."""
    if not (np.all(np.isfinite(fit.covs)) and np.all(np.isfinite(fit.pis)) and np.isfinite(fit.loglik)):
        return "비유한 공분산 · 비율 · 로그우도"
    for k, c in enumerate(fit.covs):
        if np.linalg.eigvalsh((c + c.T) / 2).min() <= 0:
            return f"성분 {k} 비 SPD (최소 고유값 ≤ 0)"
    return None


def fit_candidate(Xw: np.ndarray, K: int, a: Optional[float], kw: dict):
    """F4 와 같은 restart (`t1_reg4._one_run4`) 를 돌려 하나씩 분류 · 기록. 반환 (적합 또는 None, 기록)."""
    restarts, ok = [], []
    for i in range(kw["n_init"] if K > 1 else 1):
        r = F4._one_run4(Xw, K, kw["seed"] + i, kw["max_iter"], kw["tol"], kw["min_occupancy"], kw["eig_floor"], a)
        status, reason = r.status, r.reason
        if status == "ok":
            bad = fit_is_finite_spd(r)
            if bad:
                status, reason = "nonfinite", bad
        restarts.append({"seed": kw["seed"] + i, "status": status, "reason": reason, "n_iter": int(r.n_iter),
                         "loglik": float(r.loglik) if np.isfinite(r.loglik) else None,
                         "occupancy": [float(x) for x in r.occupancy] if r.occupancy.size else None})
        if status == "ok":
            ok.append((kw["seed"] + i, r))
    counts = dict(Counter(x["status"] for x in restarts))
    rec = {"status": "ok" if ok else "failed", "counts": counts, "restarts": restarts,
           "numeric_failures": sum(counts.get(s, 0) for s in NUMERIC)}
    if not ok:
        return None, rec
    seed, best = max(ok, key=lambda t: t[1].loglik)            # F4 (`fit_mixture4`) 와 같은 선택 (동률이면 앞 restart)
    rec["chosen_seed"] = seed
    return best, rec


# ---------------------------------------------------------------- 평가 (예측 보존)

def eval_keep(task, eval_ids, v_ids, masks, n_roi, make_pred, keep: bool):
    """`t1.subject_nmse` 와 같은 계산 + (선택) 예측 배열 (사람, 창, mask, frame, 가린 ROI)."""
    R.check_disjoint(v_ids, eval_ids)
    per = {s: [] for s in eval_ids}
    n_w = len(task[eval_ids[0]])
    L, nm = task[eval_ids[0]][0].shape[0], len(masks[0])
    P = np.full((len(eval_ids), n_w, len(masks), L, nm), np.nan) if keep else None
    for j, msk in enumerate(masks):
        obs = np.setdiff1d(np.arange(n_roi), msk)
        v = t1.t1_target_variance(task, v_ids, obs, msk)
        pred = make_pred(obs, msk)
        for si, s in enumerate(eval_ids):
            for wi, win in enumerate(task[s]):
                x, y = t1.t1_split(win, obs, msk)
                p = pred(x, obs, msk)
                per[s].append(R.nmse_terms(y, p, v).ravel())
                if keep:
                    P[si, wi, j] = p
    return np.array([np.mean(np.concatenate(per[s])) for s in eval_ids]), P


# ---------------------------------------------------------------- BEST-T (0.5)

def tuned_best_candidates(cfg) -> List[str]:
    bt = cfg["best_tuned"]
    g1 = [f"G1({a})|λ={lam:g}" for a in bt["g1_shrink"] for lam in bt["g1_cond_lambda"]]
    rg = [f"RIDGE λ={lam:g}" for lam in bt["ridge_lambda"]]
    return g1 + rg


def _g1_cov(frames: np.ndarray, a: str):
    from sklearn.covariance import OAS, LedoitWolf
    mu = frames.mean(0)
    if a in ("LW", "OAS"):
        est = {"LW": LedoitWolf, "OAS": OAS}[a]().fit(frames)
        return est.location_.copy(), est.covariance_.copy()
    X = frames - mu
    S = X.T @ X / len(X)
    m = np.trace(S) / S.shape[0]
    af = float(a)
    return mu, af * m * np.eye(S.shape[0]) + (1 - af) * S


def tuned_baseline(name: str, rest, fit_ids):
    if name.startswith("RIDGE"):
        return t1._baseline(name, rest, fit_ids)
    a, lam = name[3:].split(")|λ=")
    mu, cov = _g1_cov(t1.t1_frames(rest, fit_ids), a)
    lam = float(lam)

    def make(obs, msk):
        B = F1._coef(cov, obs, msk, lam)
        return lambda x, o, m: mu[msk] + (x - mu[obs]) @ B.T
    return make


# ---------------------------------------------------------------- fold 한 판

def run_fold(rest, task, train, test, masks, n_roi: int, cfg: dict, fold: int) -> dict:
    R.check_disjoint(train, test)
    tie = cfg["selection"]["tie"]
    rel = cfg["reliability"]
    keep, audit = rel["keep_predictions"], rel["selection_audit"]
    inner_tr, inner_va = R.subject_split(train, cfg["split"]["inner_val_frac"], seed=cfg["split"]["inner_seed"])
    rec = {"fold": fold, "train": list(train), "test": list(test), "inner_train": inner_tr, "inner_val": inner_va,
           "nmse": {}, "pred": {}}

    def score(make, ids_eval, ids_fit):
        return float(t1.subject_nmse(task, ids_eval, ids_fit, masks, n_roi, make).mean())

    # BEST (원래 7 후보) · BEST-T (43 후보)
    for label, cands, factory in (("BEST", cfg["best_candidates"], t1._baseline),
                                  ("BEST-T", tuned_best_candidates(cfg) if rel["best_tuned"] else [], tuned_baseline)):
        if not cands:
            continue
        sc = [(b, score(factory(b, rest, inner_tr), inner_va, inner_tr)) for b in cands]
        pick = SR._pick(sc, tie)
        nm, P = eval_keep(task, test, train, masks, n_roi, factory(pick, rest, train), keep)
        rec[label] = {"pick": pick, "inner_scores": sc}
        rec["nmse"][label] = nm
        if keep:
            rec["pred"][label] = P
        if audit:
            ts = [(b, float(t1.subject_nmse(task, test, train, masks, n_roi, factory(b, rest, train)).mean())) for b in cands]
            rec[label].update(test_scores=ts)

    # F4R 후보 선택
    K, kw = cfg["mix"]["K"], t1._fit_kw(cfg)
    Xi = t1.t1_windows(rest, inner_tr)
    te = t1.tau_ess_t1(Xi)
    cand_fit, cands, scores, inner_fits = {}, [], [], {}
    for en, a in F2.em_candidates(cfg):
        fi, frec = fit_candidate(Xi, K, a, kw)
        inner_fits[en] = frec
        if fi is None:
            continue
        cand_fit[en] = fi
        for name, lam, tau in F1.candidates(cfg, te):
            for h in F3.h_candidates(cfg):
                full = f"a={en}|{name}|h={h}"
                cands.append((full, en, a, lam, tau, h))
                scores.append((full, score(F3.make_mix_pred_h(fi, lam, tau, h), inner_va, inner_tr)))
    mixrec = {"tau_ess": te, "inner_fits": inner_fits, "inner_scores": scores,
              "inner_failed_candidates": [k for k, v in inner_fits.items() if v["status"] != "ok"]}
    rec["F4R"] = mixrec
    num_inner = sum(v["numeric_failures"] for v in inner_fits.values())

    def finish_fallback(stage: str, failed_recs: List[dict]):
        numeric = sum(r["numeric_failures"] for r in failed_recs)
        if numeric:                                                         # R4
            mixrec.update(fold_status="stop_numerical", reason=f"{stage}: 수치 실패 restart {numeric} 건으로 혼합 실패")
            return rec
        mixrec.update(fold_status="fallback", reason=f"{stage}: 정상 실패 (비수렴 · 점유율) 로 혼합 실패")   # R3
        rec["nmse"]["F4R"] = np.array(rec["nmse"]["BEST"], copy=True)
        if keep:
            rec["pred"]["F4R"] = np.array(rec["pred"]["BEST"], copy=True)
        return rec

    if not scores:
        return finish_fallback("inner", list(inner_fits.values()))
    pick = SR._pick(scores, tie)
    _, en, a, lam, tau, h = next(c for c in cands if c[0] == pick)
    mixrec.update(pick=pick, em_a=a, lam=lam, tau=tau, h=h)
    f, frec = fit_candidate(t1.t1_windows(rest, train), K, a, kw)
    mixrec["train_fit"] = frec
    if f is None:
        return finish_fallback("train", [frec])
    bad = fit_is_finite_spd(f)                                              # R6
    if bad:
        mixrec.update(fold_status="stop_numerical", reason=f"최종 적합 검사 실패: {bad}")
        return rec
    nm, P = eval_keep(task, test, train, masks, n_roi, F3.make_mix_pred_h(f, lam, tau, h), keep)
    rec["nmse"]["F4R"] = nm
    if keep:
        rec["pred"]["F4R"] = P
    rec["nmse"]["MIX-p"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_pooled_pred(f, lam))
    rec["nmse"]["MIX-f"] = t1.subject_nmse(task, test, train, masks, n_roi, F1.make_mix_pred(f, lam, 0.0, "fixed"))
    mixrec.update(fold_status="ok", reason="", pis=f.pis.tolist(),
                  numeric_warnings=num_inner + frec["numeric_failures"])            # R5
    if audit:                                                               # test 에서 모든 후보 (oracle 진단)
        ts = []
        for en2, a2 in F2.em_candidates(cfg):
            if en2 not in cand_fit:
                continue
            f2 = f if en2 == en else fit_candidate(t1.t1_windows(rest, train), K, a2, kw)[0]
            if f2 is None:
                continue
            for name, lam2, tau2 in F1.candidates(cfg, te):
                for h2 in F3.h_candidates(cfg):
                    ts.append((f"a={en2}|{name}|h={h2}",
                               float(t1.subject_nmse(task, test, train, masks, n_roi, F3.make_mix_pred_h(f2, lam2, tau2, h2)).mean())))
        mixrec["test_scores"] = ts
    return rec


# ---------------------------------------------------------------- 집계 · 판정

def _audit(block: dict) -> Optional[dict]:
    if "test_scores" not in block or "pick" not in block:
        return None
    inner = dict(block["inner_scores"])
    test = dict(block["test_scores"])
    if block["pick"] not in test:
        return None
    best_name = min(test, key=test.get)
    return {"n_candidates": len(block["inner_scores"]), "inner_score_of_pick": inner[block["pick"]],
            "test_score_of_pick": test[block["pick"]], "optimism": test[block["pick"]] - inner[block["pick"]],
            "test_best_candidate": best_name, "regret": test[block["pick"]] - test[best_name]}


def verdict_rel(folds, ci_main, nonfinite: bool) -> dict:
    st = [r["F4R"].get("fold_status") for r in folds]
    flags = []
    if nonfinite:
        flags.append("중단: 비유한 예측")
    n_stop = st.count("stop_numerical")
    if n_stop:
        flags.append(f"중단: 수치 오류로 혼합 실패 fold {n_stop}/{len(folds)} (R4)")
    n_fb = st.count("fallback")
    if n_fb:
        flags.append(f"혼합 실패 fold {n_fb}/{len(folds)} → BEST fallback (R3, 정상 실패)")
    warn = sum(r["F4R"].get("numeric_warnings", 0) for r in folds)
    if warn:
        flags.append(f"수치 실패 restart {warn} 건 (판정 유지, R5)")
    if ci_main is not None and ci_main[2] < 0:
        flags.append("K>1 경로 중단 권고: Δ 상한 < 0")
    ok = [r for r in folds if r["F4R"].get("fold_status") == "ok"]
    if ok and all(r["F4R"]["tau"] == 0.0 for r in ok):
        flags.append("적응 경로 중단 권고: 성공 fold 모두 τ̂ = 0")
    stop = any(f.startswith("중단") for f in flags)
    return {"flags": flags, "stop": stop, "fold_status": st, "next": "중단 · 보고" if stop else "기술값 보고"}


def summarize_deltas(per: Dict[str, Dict[str, float]], subjects, ok_subj, cfg) -> dict:
    nb, sd_seed = cfg["bootstrap"]["n"], cfg["bootstrap"]["seed"]
    out = {}

    def one(a, b, ids):
        d = R.delta(np.array([per[a][s] for s in ids]), np.array([per[b][s] for s in ids]))
        return {"per_subject": dict(zip(ids, d.tolist())), "mean": float(d.mean()),
                "sd": float(np.std(d, ddof=1)) if len(d) > 1 else None,
                "ci": list(R.subject_bootstrap(d, nb, seed=sd_seed)), "n": len(ids)}
    allp = sorted(subjects)
    if "F4R" in per and len(per["F4R"]) == len(allp):
        out["BEST − F4R (31 명, 주지표)"] = one("BEST", "F4R", allp)
        if "BEST-T" in per:
            out["BEST-T − F4R (31 명, 공정성)"] = one("BEST-T", "F4R", allp)
    if ok_subj:
        out["BEST − F4R (성공 fold 한정, 참고)"] = one("BEST", "F4R", ok_subj)
        out["MIX-p − F4R (성공 fold 한정, 기전 보조)"] = one("MIX-p", "F4R", ok_subj)
    return out


def run_pipeline(rest, task, subjects, cfg, left) -> dict:
    n_roi = len(left)
    bad = sorted({s for d in (rest, task) for s in subjects for w in d[s] if not np.all(np.isfinite(w))})
    if bad:
        return {"n_subjects": len(subjects), "nonfinite_input_subjects": len(bad), "folds": [], "per_subject_nmse": {},
                "deltas": {}, "verdict": {"flags": ["중단: 비유한 입력"], "stop": True, "fold_status": [], "next": "중단 · 보고"}}
    masks = R.make_masks(n_roi, cfg["mask"]["frac"], cfg["mask"]["n_masks"], seed=cfg["mask"]["seed"], left=left)
    tests = t1.person_folds(subjects, cfg["split"]["n_folds"], cfg["split"]["fold_seed"])
    seen = sorted(s for t in tests for s in t)
    if seen != sorted(subjects) or len(seen) != len(set(seen)):
        raise R.LeakError("각 사람이 정확히 한 번 test 에 들어가지 않는다")
    folds = [run_fold(rest, task, sorted(set(subjects) - set(test)), test, masks, n_roi, cfg, k) for k, test in enumerate(tests)]
    per = {}
    for r in folds:
        for m, arr in r["nmse"].items():
            for s, v in zip(r["test"], arr):
                per.setdefault(m, {})[s] = float(v)
    nonfinite = any(not np.isfinite(v) for d in per.values() for v in d.values())
    ok_subj = sorted(s for r in folds if r["F4R"].get("fold_status") == "ok" for s in r["test"])
    deltas = {} if nonfinite else summarize_deltas(per, subjects, ok_subj, cfg)
    main = deltas.get("BEST − F4R (31 명, 주지표)")
    out = {"n_subjects": len(subjects), "masks": [m.tolist() for m in masks], "per_subject_nmse": per, "deltas": deltas,
           "n_fallback_subjects": sum(len(r["test"]) for r in folds if r["F4R"].get("fold_status") == "fallback"),
           "n_stop_subjects": sum(len(r["test"]) for r in folds if r["F4R"].get("fold_status") == "stop_numerical"),
           "folds": folds}
    out["selection_audit"] = [{lab: _audit(r[lab]) for lab in ("BEST", "BEST-T", "F4R") if lab in r} for r in folds]
    out["verdict"] = verdict_rel(folds, main["ci"] if main else None, nonfinite)
    return out


# ---------------------------------------------------------------- 저장 · 왕복

def code_hashes() -> Dict[str, str]:
    d = ROOT / "scripts" / "r2t"
    return {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in CODE_FILES}


def save_run(prefix: Path, res: dict, spec: dict, cfg: dict) -> None:
    """<prefix>.json (기록) + <prefix>.npz (예측). 이미 있으면 거부."""
    prefix = Path(prefix)
    if prefix.with_suffix(".json").exists() or prefix.with_suffix(".npz").exists():
        raise FileExistsError(f"덮어쓰지 않는다: {prefix}")
    arrays, folds = {}, []
    for r in res["folds"]:
        f = {k: v for k, v in r.items() if k not in ("nmse", "pred")}
        f["nmse"] = {m: [float(x) for x in arr] for m, arr in r["nmse"].items()}
        for m, P in r.get("pred", {}).items():
            arrays[f"fold{r['fold']}__{m}"] = P
        folds.append(f)
    doc = {k: v for k, v in res.items() if k != "folds"}
    doc.update(folds=folds, spec=spec, config=cfg, code_sha256=code_hashes(), schema="r2t-t1-rel-run-0.1",
               synthetic_only=True, prediction_layout="fold{k}__{method}: (test 사람 순서, 창, mask, frame, 가린 ROI)")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=float))
    np.savez_compressed(prefix.with_suffix(".npz"), **arrays)


def load_run(prefix: Path):
    prefix = Path(prefix)
    return json.loads(prefix.with_suffix(".json").read_text()), dict(np.load(prefix.with_suffix(".npz")))


def verify_roundtrip(doc: dict, arrays: dict, task: Dict[str, List[np.ndarray]], n_roi: int) -> dict:
    """저장 예측 + 재생성 정답으로 사람별 NMSE · Δ (평균 · SD · CI) · 분리 성질을 다시 계산해 저장값과 비교."""
    masks = [np.array(m) for m in doc["masks"]]
    problems, n_checked = [], 0
    subjects = sorted(s for f in doc["folds"] for s in f["test"])
    if len(subjects) != len(set(subjects)) or len(subjects) != doc["n_subjects"]:
        problems.append("test 명단이 사람마다 정확히 한 번이 아니다")
    for f in doc["folds"]:
        if set(f["inner_train"]) & set(f["test"]) or set(f["inner_val"]) & set(f["test"]) or set(f["train"]) & set(f["test"]):
            problems.append(f"fold {f['fold']} 명단 겹침")
        if sorted(f["inner_train"] + f["inner_val"]) != sorted(f["train"]):
            problems.append(f"fold {f['fold']} inner 명단 ≠ train")
        for m, saved in f["nmse"].items():
            key = f"fold{f['fold']}__{m}"
            if key not in arrays:
                continue
            P = arrays[key]
            for si, s in enumerate(f["test"]):
                terms = []
                for j, msk in enumerate(masks):
                    obs = np.setdiff1d(np.arange(n_roi), msk)
                    v = t1.t1_target_variance(task, f["train"], obs, msk)
                    for wi, win in enumerate(task[s]):
                        _, y = t1.t1_split(win, obs, msk)
                        terms.append(R.nmse_terms(y, P[si, wi, j], v).ravel())
                re = float(np.mean(np.concatenate(terms)))
                n_checked += 1
                if re != saved[si] or doc["per_subject_nmse"][m][s] != saved[si]:
                    problems.append(f"fold {f['fold']} {m} {s}: 재계산 {re!r} ≠ 저장 {saved[si]!r}")
    cfgb = doc["config"]["bootstrap"]
    for name, dd in doc["deltas"].items():
        ids = sorted(dd["per_subject"])
        a, b = {"BEST − F4R (31 명, 주지표)": ("BEST", "F4R"), "BEST-T − F4R (31 명, 공정성)": ("BEST-T", "F4R"),
                "BEST − F4R (성공 fold 한정, 참고)": ("BEST", "F4R"),
                "MIX-p − F4R (성공 fold 한정, 기전 보조)": ("MIX-p", "F4R")}[name]
        d = np.array([doc["per_subject_nmse"][a][s] - doc["per_subject_nmse"][b][s] for s in ids])
        ci = list(R.subject_bootstrap(d, cfgb["n"], seed=cfgb["seed"]))
        sd = float(np.std(d, ddof=1)) if len(d) > 1 else None
        if not (np.allclose(d, [dd["per_subject"][s] for s in ids], rtol=0, atol=0) and float(d.mean()) == dd["mean"]
                and sd == dd["sd"] and ci == dd["ci"]):
            problems.append(f"Δ 재계산 불일치: {name}")
    return {"problems": problems, "n_subject_scores_rechecked": n_checked}
