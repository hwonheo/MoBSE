"""R2T T1 검증기 패치 F4R1 — F4R (`t1_rel`) 과 같은 알고리즘 · 규칙 + (a) 엄격한 기록 검증 (b) oracle 재적합 실패 기록. **합성 자료만.**

사전 규칙: `docs/experiments/r2t_t1_rel1_patch_2026-10-17.md` 0 절. `t1_rel` · F4 · F4R 고정본은 바꾸지 않고 불러 쓴다.

* `run_fold` 는 `t1_rel.run_fold` 와 같고, oracle 진단의 train 재적합 기록을 `F4R.oracle_refits` · `oracle_failures` 에 남긴다 (0.4).
* `verify_strict` 는 상태별 예상 배열 (0.2) 의 누락 · 여분 · shape · dtype · 비유한 값 · fallback 동일성 · 중단 시 부재,
  손상된 npz, 기록 누락, 사람별 NMSE · Δ 재계산 불일치, 판정 플래그를 모두 명시적 실패로 돌려준다.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, List

import numpy as np

import r2t_lib as R
import select_rules as SR
import t1
import t1_reg as F1
import t1_reg2 as F2
import t1_reg3 as F3
from t1_rel import (NORMAL, NUMERIC, _audit, eval_keep, fit_candidate, fit_is_finite_spd, save_run, summarize_deltas,  # noqa: F401
                    tuned_baseline, tuned_best_candidates, verdict_rel)
import t1_rel as T

CODE_FILES = T.CODE_FILES + ("t1_rel1.py",)


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
        ts, refits = [], {}
        for en2, a2 in F2.em_candidates(cfg):
            if en2 not in cand_fit:
                refits[en2] = {"status": "skipped", "reason": "inner 적합 실패로 후보에서 빠짐 (inner_fits 참조)"}
                continue
            if en2 == en:
                f2 = f
                refits[en2] = {"status": "ok", "reason": "선택 a — train_fit 기록과 같음", "same_as": "train_fit"}
            else:
                f2, r2 = fit_candidate(t1.t1_windows(rest, train), K, a2, kw)
                refits[en2] = r2
            if f2 is None:
                continue
            for name, lam2, tau2 in F1.candidates(cfg, te):
                for h2 in F3.h_candidates(cfg):
                    ts.append((f"a={en2}|{name}|h={h2}",
                               float(t1.subject_nmse(task, test, train, masks, n_roi, F3.make_mix_pred_h(f2, lam2, tau2, h2)).mean())))
        failed = {k: v for k, v in refits.items() if v["status"] == "failed"}
        mixrec["test_scores"] = ts
        mixrec["oracle_refits"] = refits
        mixrec["oracle_failures"] = {
            "n_failed_a": len(failed), "failed_a": sorted(failed),
            "n_numeric_restarts": sum(v.get("numeric_failures", 0) for v in failed.values()),
            "n_normal_restarts": sum(v["counts"].get(s, 0) for v in failed.values() for s in NORMAL),
            "n_skipped_a": sum(v["status"] == "skipped" for v in refits.values()),
            "candidate_set_reduced": bool(failed) or any(v["status"] == "skipped" for v in refits.values())}
    return rec



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
    out["selection_audit"] = [{lab: _audit1(r[lab], lab) for lab in ("BEST", "BEST-T", "F4R") if lab in r} for r in folds]
    out["verdict"] = verdict_rel(folds, main["ci"] if main else None, nonfinite)
    return out




def _audit1(block: dict, label: str):
    a = _audit(block)
    if a is not None and label == "F4R":
        a["oracle_candidate_set_reduced"] = block.get("oracle_failures", {}).get("candidate_set_reduced")
    return a


def save_run1(prefix, res, spec, cfg):
    """`t1_rel.save_run` 과 같은 형식 + F4R1 코드 해시."""
    save_run(prefix, res, spec, cfg)
    import hashlib
    import json
    p = Path(prefix).with_suffix(".json")
    doc = json.loads(p.read_text())
    d = Path(__file__).resolve().parent
    doc["code_sha256"] = {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in CODE_FILES}
    doc["schema"] = "r2t-t1-rel1-run-0.1"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=float))


# ---------------------------------------------------------------- 엄격한 검증 (0.2)

def load_arrays_strict(npz_path):
    """(arrays 또는 None, 문제 목록). 손상 · 잘림 · 형식 오류를 예외 대신 문제로."""
    try:
        with np.load(npz_path, allow_pickle=False) as z:
            return {k: np.array(z[k]) for k in z.files}, []
    except (OSError, ValueError, EOFError, zipfile.BadZipFile, KeyError) as e:
        return None, [f"npz 읽기 실패: {type(e).__name__}: {e}"]


def expected_methods(status: str, best_tuned: bool):
    base = ["BEST"] + (["BEST-T"] if best_tuned else [])
    if status in ("ok", "fallback"):
        return base + ["F4R"], []
    if status == "stop_numerical":
        return base, ["F4R"]
    return None, None


def verify_strict(doc: dict, arrays, task: Dict[str, List[np.ndarray]], n_roi: int) -> dict:
    problems, n_arr, n_sc = [], 0, 0
    if arrays is None:
        problems.append("예측 배열 없음 (npz 읽기 실패)")
        arrays = {}
    try:
        masks = [np.array(m) for m in doc["masks"]]
        folds = doc["folds"]
        best_tuned = bool(doc["config"]["reliability"]["best_tuned"])
    except (KeyError, TypeError) as e:
        return {"ok": False, "problems": problems + [f"기록 구조 누락: {e!r}"], "n_arrays_checked": 0, "n_subject_scores_rechecked": 0}
    subjects = sorted(s for f in folds for s in f["test"])
    if len(subjects) != len(set(subjects)) or len(subjects) != doc.get("n_subjects"):
        problems.append("test 명단이 사람마다 정확히 한 번이 아니다")
    n_msk = len(masks[0]) if masks else 0
    expected_keys = set()
    statuses = []
    for f in folds:
        k = f["fold"]
        st = f.get("F4R", {}).get("fold_status")
        statuses.append(st)
        need, forbid = expected_methods(st, best_tuned)
        if need is None:
            problems.append(f"fold {k}: 알 수 없는 상태 {st!r}")
            continue
        if set(f["inner_train"]) & set(f["test"]) or set(f["inner_val"]) & set(f["test"]) or set(f["train"]) & set(f["test"]):
            problems.append(f"fold {k}: 명단 겹침")
        if sorted(f["inner_train"] + f["inner_val"]) != sorted(f["train"]):
            problems.append(f"fold {k}: inner 명단 ≠ train")
        for m in forbid:
            if f"fold{k}__{m}" in arrays:
                problems.append(f"fold {k}: 상태 {st} 인데 {m} 배열이 있음")
            if m in f.get("nmse", {}):
                problems.append(f"fold {k}: 상태 {st} 인데 {m} 점수가 있음")
        n_w = len(task[f["test"][0]]) if f["test"] else 0
        L = task[f["test"][0]][0].shape[0] if f["test"] else 0
        for m in need:
            key = f"fold{k}__{m}"
            expected_keys.add(key)
            if key not in arrays:
                problems.append(f"fold {k}: {m} 예측 배열 누락")
                continue
            P = arrays[key]
            n_arr += 1
            shape = (len(f["test"]), n_w, len(masks), L, n_msk)
            if P.shape != shape:
                problems.append(f"fold {k}: {m} shape {P.shape} ≠ 예상 {shape}")
                continue
            if not np.issubdtype(P.dtype, np.floating):
                problems.append(f"fold {k}: {m} dtype {P.dtype} 실수 아님")
                continue
            if not np.all(np.isfinite(P)):
                problems.append(f"fold {k}: {m} 비유한 값 {int((~np.isfinite(P)).sum())} 개")
                continue
            saved = f.get("nmse", {}).get(m)
            if saved is None or len(saved) != len(f["test"]):
                problems.append(f"fold {k}: {m} 사람별 점수 기록 누락 · 길이 불일치")
                continue
            for si, s in enumerate(f["test"]):
                terms = []
                for j, msk in enumerate(masks):
                    obs = np.setdiff1d(np.arange(n_roi), msk)
                    v = t1.t1_target_variance(task, f["train"], obs, msk)
                    for wi, win in enumerate(task[s]):
                        _, y = t1.t1_split(win, obs, msk)
                        terms.append(R.nmse_terms(y, P[si, wi, j], v).ravel())
                re = float(np.mean(np.concatenate(terms)))
                n_sc += 1
                if re != saved[si]:
                    problems.append(f"fold {k}: {m} {s} 재계산 {re!r} ≠ 저장 {saved[si]!r}")
                if doc.get("per_subject_nmse", {}).get(m, {}).get(s) != saved[si]:
                    problems.append(f"fold {k}: {m} {s} per_subject_nmse 불일치 · 누락")
        if st == "fallback" and f"fold{k}__F4R" in arrays and f"fold{k}__BEST" in arrays:
            if not np.array_equal(arrays[f"fold{k}__F4R"], arrays[f"fold{k}__BEST"]):
                problems.append(f"fold {k}: fallback 인데 F4R 배열 ≠ BEST 배열")
    extra = sorted(set(arrays) - expected_keys - {f"fold{f['fold']}__{m}" for f in folds for m in ("F4R",)
                                                     if f.get("F4R", {}).get("fold_status") == "stop_numerical"})
    if extra:
        problems.append(f"예상하지 않은 배열 key: {extra}")
    # Δ 기록 (0.2)
    deltas = doc.get("deltas", {})
    has_stop = "stop_numerical" in statuses
    want = []
    if not has_stop:
        want.append("BEST − F4R (31 명, 주지표)")
        if best_tuned:
            want.append("BEST-T − F4R (31 명, 공정성)")
    if "ok" in statuses:
        want += ["BEST − F4R (성공 fold 한정, 참고)", "MIX-p − F4R (성공 fold 한정, 기전 보조)"]
    for name in want:
        if name not in deltas:
            problems.append(f"Δ 기록 누락: {name}")
    if has_stop and "BEST − F4R (31 명, 주지표)" in deltas:
        problems.append("중단 fold 가 있는데 주지표 Δ 가 있음")
    pairs = {"BEST − F4R (31 명, 주지표)": ("BEST", "F4R"), "BEST-T − F4R (31 명, 공정성)": ("BEST-T", "F4R"),
             "BEST − F4R (성공 fold 한정, 참고)": ("BEST", "F4R"), "MIX-p − F4R (성공 fold 한정, 기전 보조)": ("MIX-p", "F4R")}
    cfgb = doc["config"]["bootstrap"]
    for name, dd in deltas.items():
        if name not in pairs:
            problems.append(f"알 수 없는 Δ 기록: {name}")
            continue
        a, b = pairs[name]
        ids = sorted(dd.get("per_subject", {}))
        try:
            d = np.array([doc["per_subject_nmse"][a][s] - doc["per_subject_nmse"][b][s] for s in ids])
        except KeyError as e:
            problems.append(f"Δ 재계산 불가 ({name}): {e!r}")
            continue
        if len(d) == 0:
            problems.append(f"Δ 사람 없음: {name}")
            continue
        ci = list(R.subject_bootstrap(d, cfgb["n"], seed=cfgb["seed"]))
        sd = float(np.std(d, ddof=1)) if len(d) > 1 else None
        if not (np.array_equal(d, np.array([dd["per_subject"][s] for s in ids])) and float(d.mean()) == dd.get("mean")
                and sd == dd.get("sd") and ci == dd.get("ci") and dd.get("n") == len(ids)):
            problems.append(f"Δ 재계산 불일치: {name}")
    flags = doc.get("verdict", {}).get("flags", [])
    if has_stop != any("R4" in x for x in flags) or ("fallback" in statuses) != any("R3" in x for x in flags):
        problems.append("판정 플래그가 fold 상태와 맞지 않음")
    if doc.get("verdict", {}).get("fold_status") != statuses:
        problems.append("verdict.fold_status ≠ fold 기록")
    return {"ok": not problems, "problems": problems, "n_arrays_checked": n_arr, "n_subject_scores_rechecked": n_sc}


def verify_prefix(prefix, task, n_roi) -> dict:
    import json
    prefix = Path(prefix)
    try:
        doc = json.loads(prefix.with_suffix(".json").read_text())
    except (OSError, ValueError) as e:
        return {"ok": False, "problems": [f"json 읽기 실패: {type(e).__name__}: {e}"], "n_arrays_checked": 0, "n_subject_scores_rechecked": 0}
    if not prefix.with_suffix(".npz").exists():
        return {"ok": False, "problems": ["npz 파일 없음"], "n_arrays_checked": 0, "n_subject_scores_rechecked": 0}
    arrays, probs = load_arrays_strict(prefix.with_suffix(".npz"))
    out = verify_strict(doc, arrays, task, n_roi)
    out["problems"] = probs + out["problems"]
    out["ok"] = not out["problems"]
    return out
