#!/usr/bin/env python3
"""I1 D2 null 입력 생성기 — 표준 ``abide.npy`` 를 조건별로 변환한다 (계획서 초안 §3 D2, 결정 38 · 41).

공개 모델 코드는 고치지 않는다 — null 은 전부 **입력 변환**이다. 저장소 넷 (BNT · BQN · Han · BrainGB) 은
``timeseires`` · ``corr`` · ``label`` · ``site`` 만 읽는다 [코드]. ``pcorr`` 는 아무도 읽지 않으므로 출력에서 **뺀다**
(변환하지 않은 값이 남아 있다가 나중에 잘못 쓰이는 일을 막는다 — 읽으려 하면 KeyError 로 드러난다).

조건 (순열 규약: 새 ROI i 자리에 옛 ROI ``p[i]`` 가 온다 — ``corr[p][:, p]``, ``timeseires[p]``):

* ``n0`` 일관 재배열 — 모든 피험자에 같은 무작위 순열 (대조, 아무것도 깨지 않음).
* ``n1`` 피험자별 무작위 순열 — 피험자 사이 ROI 대응을 깬다.
* ``n2`` 피험자별 spin — ``mobse.v3.templates.vasa_permutation`` (반구 안 회전 + 일대일 배정). 반구는 중심 x 부호
  (결정 41-3, v3 규칙 그대로). CC200 은 반구를 걸친 parcel 이 있다 (``cc200_coords.json`` 의 ``cross_frac``).
* ``n3`` 피험자별 가중 · 부호 null — Rubinov & Sporns 2011 (결정 41-2). 시계열은 **그대로** 둔다
  (FC 와 시계열이 어긋나는 것은 기록된 한계).

``n3`` 의 구현: 이진 단계는 bctpy ``randmio_und_signed`` 를 그대로 쓰고, 가중치 배정은 bctpy
``null_model_und_sign`` 을 옮기되 **한 곳을 고쳤다**. bctpy 0.6.1 (설치판, 모듈의 ``__version__`` 은 0.6.0 으로 보고) 은 음수 쪽에서 ``W0 = s * Wv`` 로
음수 가중치에 −1 을 곱해 **양수로** 넣는다 — 2026-10-03 실측, ABIDE 첫 피험자에서 음수 edge 3,029 → 0.
여기서는 부호마다 크기 ``s · W`` 로 strength · 정렬 · 배정을 하고 마지막에 부호 ``s`` 를 곱한다.
양수 쪽은 bctpy 와 같은 계산이다.

seed: 피험자 · 조건마다 ``SeedSequence([BASE_SEED, 조건 번호, k, 피험자 index])`` 의 첫 uint32. ``n0`` 은 피험자 index 대신 −1 → 0.

Usage (h197, venv-i1):
    PYTHONPATH=. python scripts/i1/null_inputs.py --npy <abide.npy> --coords <cc200_coords.json> \\
        --kind n2 --k 0 --out <dir> [--n-subj 8] [--workers 10]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

BASE_SEED = 20261003
KIND_CODE = {"n0": 0, "n1": 1, "n2": 2, "n3": 3}


def seed_for(kind: str, k: int, subj: int) -> int:
    ss = np.random.SeedSequence([BASE_SEED, KIND_CODE[kind], k, subj + 1])
    return int(ss.generate_state(1)[0])


def signed_null(W: np.ndarray, seed: int, bin_swaps: int = 5, wei_freq: float = 0.1) -> np.ndarray:
    """Rubinov–Sporns 가중 · 부호 null (bctpy ``null_model_und_sign`` 의 부호 수정판). 대각은 0 으로 둔다."""
    import bct

    rng = np.random.RandomState(seed)
    W = np.array(W, dtype=float, copy=True)
    if not np.allclose(W, W.T):
        raise ValueError("대칭이 아니다")
    n = len(W)
    np.fill_diagonal(W, 0)
    Ap, An = W > 0, W < 0
    if np.count_nonzero(Ap) < n * (n - 1):
        W_r, _ = bct.randmio_und_signed(W, bin_swaps, seed=rng)
        Ap_r, An_r = W_r > 0, W_r < 0
    else:
        Ap_r, An_r = Ap, An
    W0 = np.zeros((n, n))
    period = int(np.round(1 / wei_freq))
    for s, Acur, A_rcur in ((1, Ap, Ap_r), (-1, An, An_r)):
        M = s * W                                    # 이 부호의 크기 (≥ 0) — bctpy 는 여기서 부호를 잃는다
        S = np.sum(M * Acur, axis=0)
        Wv = np.sort(M[np.where(np.triu(Acur))])
        i, j = np.where(np.triu(A_rcur))
        Lij, = np.where(np.triu(A_rcur).flat)
        P = np.outer(S, S)
        for m in np.arange(Wv.size, 0, -period, dtype=int):
            Oind = np.argsort(P.flat[Lij])
            R = rng.permutation(m)[:min(m, period)]
            for r in R:
                o = Oind[r]
                W0.flat[Lij[o]] = s * Wv[r]
                f = 1 - Wv[r] / S[i[o]]
                P[i[o], :] *= f
                P[:, i[o]] *= f
                f = 1 - Wv[r] / S[j[o]]
                P[j[o], :] *= f
                P[:, j[o]] *= f
                S[i[o]] -= Wv[r]
                S[j[o]] -= Wv[r]
            O = Oind[R]
            Lij, i, j = np.delete(Lij, O), np.delete(i, O), np.delete(j, O)
            Wv = np.delete(Wv, R)
    return W0 + W0.T


def _n3_one(args):
    W, seed = args
    W0 = signed_null(W, seed)
    iu = np.triu_indices(len(W), 1)
    sp = lambda A: (A * (A > 0)).sum(0)              # noqa: E731
    sn = lambda A: (-A * (A < 0)).sum(0)             # noqa: E731
    chk = {
        "n_pos_equal": int((W[iu] > 0).sum()) == int((W0[iu] > 0).sum()),
        "n_neg_equal": int((W[iu] < 0).sum()) == int((W0[iu] < 0).sum()),
        "weights_multiset_equal": bool(np.allclose(np.sort(W[iu]), np.sort(W0[iu]))),
        "r_pos_strength": float(np.corrcoef(sp(W), sp(W0))[0, 1]),
        "r_neg_strength": float(np.corrcoef(sn(W), sn(W0))[0, 1]),
        "r_edges": float(np.corrcoef(W[iu], W0[iu])[0, 1]),
    }
    return W0, chk


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npy", required=True, type=Path)
    ap.add_argument("--coords", required=True, type=Path, help="cc200_coords.json (n2 에서 씀, 나머지는 ROI 수 확인)")
    ap.add_argument("--kind", required=True, choices=sorted(KIND_CODE))
    ap.add_argument("--k", required=True, type=int, help="같은 조건의 몇 번째 null 인가 (0 부터)")
    ap.add_argument("--out", required=True, type=Path, help="출력 폴더 — 이미 abide.npy 가 있으면 멈춘다")
    ap.add_argument("--n-subj", type=int, default=None, help="smoke 용 — 앞 n 명만")
    ap.add_argument("--workers", type=int, default=1, help="n3 병렬 프로세스 수")
    args = ap.parse_args(argv[1:])

    out_npy = args.out / "abide.npy"
    if out_npy.exists():
        print(f"이미 있다 — 덮어쓰지 않는다: {out_npy}", file=sys.stderr)
        return 2
    t0 = time.time()
    data = np.load(args.npy, allow_pickle=True).item()
    corr, ts = np.asarray(data["corr"]), np.asarray(data["timeseires"])
    n = len(corr) if args.n_subj is None else args.n_subj
    corr, ts = corr[:n], ts[:n]
    coords = json.loads(args.coords.read_text())
    v = corr.shape[1]
    if coords["n_roi"] != v:
        raise SystemExit(f"좌표 ROI 수 {coords['n_roi']} ≠ FC ROI 수 {v}")

    new_corr, new_ts = np.empty_like(corr), np.empty_like(ts)
    perms, seeds, checks = None, [], []
    if args.kind in ("n0", "n1", "n2"):
        perms = np.empty((n, v), dtype=np.int32)
        if args.kind == "n2":
            from mobse.v3.templates import vasa_permutation
            xyz, left = np.asarray(coords["coords_mm"]), np.asarray(coords["is_left"], dtype=bool)
        for s in range(n):
            seed = seed_for(args.kind, args.k, -1 if args.kind == "n0" else s)
            seeds.append(seed)
            if args.kind == "n2":
                p = vasa_permutation(xyz, left, seed=seed)
                assert np.array_equal(left[p], left), "spin 이 반구를 넘었다"
            else:
                p = np.random.Generator(np.random.PCG64(seed)).permutation(v)
            perms[s] = p
            new_corr[s] = corr[s][p][:, p]
            new_ts[s] = ts[s][p]
        moved = float(np.mean(perms != np.arange(v)))
        summary = {"frac_roi_moved": moved}
    else:
        seeds = [seed_for("n3", args.k, s) for s in range(n)]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for s, (W0, chk) in enumerate(pool.map(_n3_one, [(corr[s], seeds[s]) for s in range(n)], chunksize=1)):
                new_corr[s] = W0
                checks.append(chk)
        new_ts[:] = ts
        summary = {
            "all_sign_counts_equal": all(c["n_pos_equal"] and c["n_neg_equal"] for c in checks),
            "all_weights_multiset_equal": all(c["weights_multiset_equal"] for c in checks),
            **{f"{key}_min": float(np.min([c[key] for c in checks])) for key in ("r_pos_strength", "r_neg_strength")},
            **{f"{key}_median": float(np.median([c[key] for c in checks]))
               for key in ("r_pos_strength", "r_neg_strength", "r_edges")},
        }

    args.out.mkdir(parents=True, exist_ok=True)
    out = {"timeseires": new_ts, "corr": new_corr, "label": np.asarray(data["label"])[:n],
           "site": np.asarray(data["site"])[:n]}
    np.save(out_npy, out, allow_pickle=True)
    if perms is not None:
        np.save(args.out / "perms.npy", perms)
    meta = {
        "schema_version": "i1-null-inputs-0.1", "kind": args.kind, "k": args.k, "n_subj": n,
        "base_seed": BASE_SEED, "seed_rule": "SeedSequence([BASE_SEED, KIND_CODE[kind], k, subj+1]).generate_state(1)[0]; n0 은 subj=-1",
        "input_npy_sha256": sha256_file(args.npy), "coords_sha256": sha256_file(args.coords),
        "output_npy_sha256": sha256_file(out_npy), "dropped_keys": ["pcorr"],
        "summary": summary, "seconds": round(time.time() - t0, 1),
        "seeds_first5": seeds[:5],
    }
    if checks:
        meta["per_subject_checks"] = checks
    (args.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(json.dumps({k: meta[k] for k in ("kind", "k", "n_subj", "summary", "seconds")}, ensure_ascii=False))
    ok = True if args.kind != "n3" else (summary["all_sign_counts_equal"] and summary["all_weights_multiset_equal"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
