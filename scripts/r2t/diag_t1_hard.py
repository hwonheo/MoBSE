#!/usr/bin/env python3
"""R2T T1 어려운 세계 병목 분해 (결정 88) — **합성 · 진단용**. oracle 은 병목을 가르는 데만 쓴다 (모델 성능 아님).

fold 0 만 (승인 분할 그대로) 로 사다리를 잰다. 창 안에서 상태가 바뀔 수 있으므로 oracle 은 **frame 별 참 상태**를 쓴다.
* POP-K1 · POP-Kt-true : 큰 독립 표본 (같은 세계 · 다른 사람) 의 pooled · 상태별 공분산 (oracle 상한)
* LAB-K-true · LAB-K-true-λ : fold train rest 를 frame 참 상태로 나눠 가중 LW (λ 0 · F1 λ 격자 중 test 최선)
* EM-λ (F1 λ · τ = fold 선택 대신 τ_ESS 고정) 와 EM 상태 복원 정확도 (창 다수 상태 기준)
* BEST (fold 0 선택), F1 MIX-a
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diag_t1 as D  # noqa: E402
import eval_t1_hard as EH  # noqa: E402
import mix as M  # noqa: E402
import r2t_lib as R  # noqa: E402
import synth_t1_hard as H  # noqa: E402
import t1  # noqa: E402
import t1_reg as F  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def frame_pred(fit, states_of, lam):
    """pred(s, i, x, o, m): frame 마다 그 frame 참 상태 성분의 (λ 정규화) 조건부 평균."""
    cache = {}

    def pred(s, i, x, o, m):
        key = tuple(m)
        if key not in cache:
            cache[key] = [F._coef(c, o, m, lam) for c in fit.covs]
        st = states_of(s, i)
        return np.stack([x[t] @ cache[key][st[t]].T for t in range(len(x))])
    return pred


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--world", required=True)
    ap.add_argument("--n-roi", type=int, default=100)
    ap.add_argument("--n-pop", type=int, default=600)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    kw, seed = EH.parse(a.world)
    wk = dict(n_roi=a.n_roi, n_states=kw["ns"], sep=kw["sep"], dwell=kw["dwell"], phase=kw["phase"], rho=kw["rho"])
    cfg = t1.load_config(ROOT / "configs" / "r2t" / "t1_pilot_reg.json")
    ids, rest, task, left, states = H.make(n_subjects=31, seed=seed, **wk)
    w = H.HardWorld(seed=seed, **wk)
    X, lab = [], []
    for j in range(a.n_pop):
        d = w.subject(f"POP{j:04d}")
        X.append(H._z(d["task"])); lab.append(d["task_states"])
    X, lab = np.concatenate(X), np.concatenate(lab)
    ns = kw["ns"]
    pop = D._fit(np.stack([X[lab == k].T @ X[lab == k] / (lab == k).sum() for k in range(ns)]), [(lab == k).mean() for k in range(ns)])
    pop1 = D._fit((X.T @ X / len(X))[None], [1.0])
    masks = R.make_masks(a.n_roi, .2, 10, seed=cfg["mask"]["seed"], left=left)
    test = t1.person_folds(ids, 5, cfg["split"]["fold_seed"])[0]
    train = sorted(set(ids) - set(test))
    tst = lambda s, i: states[s][1][15 * i:15 * i + 15]
    ev = lambda p: float(D.nmse_by_window(task, test, train, masks, a.n_roi, p).mean())
    res = {"POP-K1": ev(frame_pred(pop1, lambda s, i: np.zeros(15, int), 0.0)), "POP-Kt-true": ev(frame_pred(pop, tst, 0.0))}
    Xw = t1.t1_windows(rest, train)
    fl = np.concatenate([states[s][0] for s in train])                     # frame 상태 (rest)
    Xf = Xw.reshape(-1, a.n_roi)
    labfit = D._fit(np.stack([M.weighted_lw(Xf, (fl == k).astype(float))[0] for k in range(ns)]), [(fl == k).mean() for k in range(ns)])
    res["LAB-K-true"] = ev(frame_pred(labfit, tst, 0.0))
    res["LAB-K-true-λbest"] = min((ev(frame_pred(labfit, tst, lam)), lam) for lam in cfg["mix"]["cond_lambda_candidates"])
    rec = F.run_fold(rest, task, train, test, masks, a.n_roi, cfg, 0)
    res["BEST"] = float(rec["nmse"]["BEST"].mean())
    out = {"world": a.world, "params": kw, "fold": 0, "best": rec["best"], "mix": rec["mix"], "mix_pick": rec.get("mix_pick")}
    if rec["mix"] == "ok":
        res["F1 MIX-a"] = float(rec["nmse"]["MIX-a"].mean())
        res["F1 MIX-p"] = float(rec["nmse"]["MIX-p"].mean())
    em = M.fit_mixture(Xw, cfg["mix"]["K"], train, **t1._fit_kw(cfg))
    out["em_status"] = em.status
    if em.status == "ok":
        wl = np.array([np.bincount(states[s][0][15 * i:15 * i + 15], minlength=ns).argmax() for s in train for i in range(8)])
        ll = M.window_loglik(Xw, em.covs) + np.log(em.pis)
        resp = np.exp(ll - M._logsumexp(ll, 1)[:, None])
        cont = np.stack([resp[wl == j].sum(0) for j in range(ns)])
        r_, c_ = linear_sum_assignment(-cont)
        out["em_state_acc_matched"] = float(cont[r_, c_].sum() / len(wl))
        out["em_cov_err_rel"] = [float(np.linalg.norm(em.covs[c] - pop.covs[r]) / np.linalg.norm(pop.covs[r])) for r, c in zip(r_, c_)]
    out["pop_state_dist_rel"] = [float(np.linalg.norm(pop.covs[i] - pop.covs[j]) / np.linalg.norm(pop.covs[i]))
                                 for i in range(ns) for j in range(i + 1, ns)]
    out["nmse_fold0"] = res
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
