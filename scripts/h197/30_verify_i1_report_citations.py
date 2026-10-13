#!/usr/bin/env python3
"""I1 보고서가 인용한 수치를 h197 본 실행 산출과 대조한다 (v1 의 28 번과 같은 역할).

해시는 "파일이 바뀌지 않았다" 만 보증한다. 이 스크립트는 "그 파일을 옳게
요약했는가" 를 본다. 값은 산출물에서 다시 읽어 문서와 같은 형식으로 만들고,
그 문자열이 문서에 있는지 찾는다. **기록된 참은 참이 아니다.**

읽는 것 (모두 run root 아래, 새 계산은 형식 맞춤 · 최솟값 · 최댓값 · 합뿐):
  * ``analysis/{aomic,abide,abide_site}/*.json`` — 원판 AUC · Δ · 재학습 포함 CI · D3 · 붕괴 수
  * ``diag/collapse_20261012/diag_collapse.json`` · ``diag/mobse_mean_20261007/diag_mobse_mean.json``
  * ``{aomic,abide}/<모델>/orig/k0/r1/f{0,1,2}/d1.json`` — 학습 뒤 등변성 (D1)
  * ``status.txt`` · ``driver_{aomic,abide}.log`` — 벽시계 · 단계 경과 시간

문서의 모든 수치를 덮지는 않는다 — 잠금 해시 · 잠금 전 측정 (BrainGB · smoke) ·
산출 크기처럼 위 파일에 없는 값은 대조 대상이 아니다.

이 파일은 ``scripts/i1/`` 에 두지 않는다 — I1 잠금의 code_hash 가 ``scripts/i1/*.py`` 를 해시한다.

Usage:
    python scripts/h197/30_verify_i1_report_citations.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset \
        --doc results/i1/reports/i1_report_2026-10-13.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DATA_ROOT = Path("/mnt/data/mp2026/MoBSE_dataset")
RUN_REL = Path("i1/main/20261005_ac3bad06_a2")
PUBLIC = ("bqn", "bnt", "han")
NULLS = ("n0", "n1", "n2", "n3")
BASELINES = ("fc_logistic", "fc_mlp", "s1_logistic")
EMB_CONDS = ("prior_permutation", "prior_spin", "prior_rewire")


def load(path: Path) -> Dict[str, Any]:
    """JSON 산출물 하나를 읽는다.

    Args:
        path: 읽을 파일의 절대 경로.

    Returns:
        파싱된 객체.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def sha12(path: Path) -> str:
    """파일 sha256 의 앞 12 자."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def delta_text(cond: Dict[str, Any], nd: int = 4) -> str:
    """Δ 점추정과 재학습 포함 CI 를 문서 형식 (``+0.1234 [+0.1000, +0.1500]``) 으로 만든다."""
    lo, hi = cond["retrain_ci95"]
    return f"{cond['delta_mean']:+.{nd}f} [{lo:+.{nd}f}, {hi:+.{nd}f}]"


def log_seconds(log: Path, stage: str, total: int) -> int:
    """driver 로그에서 ``<stage> <total>/<total> … 경과 N s`` 의 N 을 읽는다."""
    pat = re.compile(rf"\s{re.escape(stage)} {total}/{total} 실패 0 .*경과 (\d+) s")
    hits = [int(m.group(1)) for m in map(pat.search, log.read_text(encoding="utf-8").splitlines()) if m]
    if not hits:
        raise SystemExit(f"로그에 {stage} {total}/{total} 줄이 없다: {log}")
    return hits[-1]


def crosscheck(doc: str, run: Path) -> List[str]:
    """문서의 인용 수치를 run root 산출과 대조하고 불일치 사유를 모은다.

    Args:
        doc: 보고서 본문 (빼기표 U+2212 를 ASCII 하이픈으로 바꾼 것).
        run: 본 실행 run root.

    Returns:
        불일치 사유 문자열의 목록. 비어 있으면 대조 통과.
    """
    fails: List[str] = []
    checked = [0]

    def need(s: str, why: str) -> None:
        checked[0] += 1
        if s not in doc:
            fails.append(f"{why}: '{s}' 가 문서에 없다")

    def must(ok: bool, why: str) -> None:
        checked[0] += 1
        if not ok:
            fails.append(why)

    an = run / "analysis"
    A = {ds: {p.stem: load(p) for p in sorted((an / ds).glob("*.json"))}
         for ds in ("aomic", "abide", "abide_site")}

    # 분석 산출 sha256 앞 12 자
    for ds in A:
        for p in sorted((an / ds).glob("*.json")):
            need(sha12(p), f"sha {ds}/{p.name}")
    for rel in ("diag/collapse_20261012/diag_collapse.json", "diag/mobse_mean_20261007/diag_mobse_mean.json"):
        need(sha12(run / rel), f"sha {rel}")

    # 원판 · 기준선 AUC (D4)
    for ds in ("aomic", "abide"):
        for m in PUBLIC + BASELINES:
            need(f"{A[ds][m]['all']['orig_auc_mean']:.4f}", f"{ds} {m} 원판 AUC")
    need(f"{A['abide_site']['bqn']['all']['orig_auc_mean']:.4f}", "site BQN 원판 AUC")
    for m in ("mobse_mean", "mobse_embedding"):
        need(f"{A['aomic'][m]['all']['orig_auc_mean']:.4f}", f"aomic {m} 원판 AUC")
    ab_orig = [A["abide"][m]["all"]["orig_auc_mean"] for m in PUBLIC]
    need(f"{min(ab_orig):.3f}–{max(ab_orig):.3f}", "ABIDE 공개 모델 원판 범위")
    need(f"{A['abide']['fc_logistic']['all']['orig_auc_mean']:.3f}", "ABIDE FC logistic (3 자리)")

    # Δ 와 재학습 포함 CI, D3
    for ds in ("aomic", "abide"):
        for m in PUBLIC:
            d = A[ds][m]
            must(d["n_fits"] == 255, f"{ds} {m} n_fits {d['n_fits']} ≠ 255")
            must(d["incomplete_units"] == [], f"{ds} {m} incomplete_units 가 비어 있지 않다")
            for c in NULLS:
                cond = d["all"]["conditions"][c]
                need(delta_text(cond), f"{ds} {m} {c} Δ")
                if c == "n0":
                    must(cond["n_pairs"] == 3 and cond["single_excludes_zero_rate"] == 0.0,
                         f"{ds} {m} n0 D3 가 0/3 이 아니다")
                    must(cond["retrain_ci95"][0] <= 0 <= cond["retrain_ci95"][1], f"{ds} {m} n0 CI 가 0 을 포함하지 않는다")
                else:
                    must(cond["n_pairs"] == 15 and cond["single_excludes_zero_rate"] == 1.0,
                         f"{ds} {m} {c} D3 가 15/15 가 아니다")
                    must(cond["retrain_ci95"][0] > 0, f"{ds} {m} {c} 재학습 포함 CI 하한이 0 을 넘지 않는다")
    site = A["abide_site"]["bqn"]
    sc = site["all"]["conditions"]["n1"]
    need(delta_text(sc), "site n1 Δ")
    must(sc["n_pairs"] == 15 and sc["single_excludes_zero_rate"] == 1.0, "site n1 D3 가 15/15 가 아니다")

    # C2 문장의 크기 범위
    def rng(ds_list, conds):
        v = [A[ds][m]["all"]["conditions"][c]["delta_mean"] for ds in ds_list for m in PUBLIC for c in conds]
        return f"{min(v):.2f}–{max(v):.2f}"
    need(rng(["aomic"], ["n3"]), "AOMIC n3 Δ 범위")
    need(rng(["abide"], ["n3"]), "ABIDE n3 Δ 범위")
    need(rng(["aomic", "abide"], ["n1", "n2"]), "n1 · n2 Δ 범위")

    # ABIDE D3: seed 간 SD · 단일 CI 반폭 중앙값 범위 (공개 모델 n1–n3)
    sd = [A["abide"][m]["all"]["conditions"][c]["delta_sd_between_runs"] for m in PUBLIC for c in NULLS[1:]]
    hw = [A["abide"][m]["all"]["conditions"][c]["single_halfwidth_median"] for m in PUBLIC for c in NULLS[1:]]
    need(f"{min(sd):.4f}–{max(sd):.4f}", "ABIDE seed 간 SD 범위")
    need(f"{min(hw):.4f}–{max(hw):.4f}", "ABIDE 단일 CI 반폭 범위")

    # MoBSE (AOMIC)
    mm = A["aomic"]["mobse_mean"]["all"]["conditions"]["prior_permutation"]
    need(delta_text(mm), "MoBSE mean Δ")
    need(f"{mm['single_excludes_zero_rate']:.2f}", "MoBSE mean D3 비율")
    for c in EMB_CONDS:
        ec = A["aomic"]["mobse_embedding"]["all"]["conditions"][c]
        need(delta_text(ec), f"MoBSE embedding {c} Δ")
        need(f"{ec['single_excludes_zero_rate']:.2f}", f"MoBSE embedding {c} D3 비율")
        must(ec["retrain_ci95"][0] <= 0 <= ec["retrain_ci95"][1], f"MoBSE embedding {c} CI 가 0 을 포함하지 않는다")
    dm = load(run / "diag/mobse_mean_20261007/diag_mobse_mean.json")
    ens_ba = sorted({round(v["d_ba"], 3) + 0.0 for v in dm["ensemble"].values()})
    must(ens_ba == [-0.016, 0.0], f"v1 방식 Δ(BA) 가 {{−0.016, 0}} 이 아니다: {ens_ba}")
    must(all(v["d_ba_ci95"][0] <= 0 <= v["d_ba_ci95"][1] for v in dm["ensemble"].values()),
         "v1 방식 Δ(BA) CI 가 모두 0 을 포함하지 않는다")

    # 붕괴 fit (분석 json 과 진단 json 이 같은지도 본다)
    col = {(ds, m): A[ds][m]["n_collapsed_fits"] for ds in ("aomic", "abide") for m in PUBLIC}
    col[("abide_site", "bqn")] = site["n_collapsed_fits"]
    for (ds, m), n in col.items():
        tot = A[ds][m]["n_fits"]
        if n:
            need(f"{n}/{tot}", f"{ds} {m} 붕괴 수")
        else:
            must(m == "han", f"{ds} {m} 붕괴 0 은 Han 에만 기대한다")
    dc = load(run / "diag/collapse_20261012/diag_collapse.json")
    n_fit_all = sum(A[ds][m]["n_fits"] for (ds, m) in col)
    n_col_all = sum(col.values())
    must(dc["n_fits"] == n_fit_all, f"진단 fit 수 {dc['n_fits']} ≠ 분석 fit 수 {n_fit_all}")
    must(sum(f["collapsed"] for f in dc["fits"]) == n_col_all, "진단 붕괴 수 ≠ 분석 붕괴 수")
    need(f"{n_col_all}/{n_fit_all:,}", "붕괴 합계")
    exc = A["abide"]["bqn"]["excluding_collapsed"]["conditions"]
    need(delta_text(exc["n3"], 3), "ABIDE BQN n3 붕괴 뺀 민감도")
    must(exc["n1"]["n_pairs"] == 1 and exc["n2"]["n_pairs"] == 1, "ABIDE BQN n1 · n2 뺀 뒤 짝 수가 1 이 아니다")
    must(site["excluding_collapsed"]["conditions"] == {}, "site 의 뺀 민감도가 계산돼 있다")

    # D1 학습판 (orig k0 r1, fold 0–2)
    d1_all = []
    for ds in ("aomic", "abide"):
        for m in PUBLIC:
            vals = []
            for f in range(3):
                d1 = load(run / ds / m / "orig/k0/r1" / f"f{f}" / "d1.json")
                must(d1["self_diff"] == 0.0, f"{ds} {m} f{f} self_diff ≠ 0")
                vals.append(d1["max_abs_diff_p1"])
            d1_all += vals
            need(" · ".join(f"{v:.3f}" for v in vals), f"{ds} {m} D1 학습판")
    need(f"{min(d1_all):.2f}–{max(d1_all):.3f}", "D1 최대 차 범위")

    # 비용: 벽시계 · 단계 경과
    st = (run / "status.txt").read_text(encoding="utf-8").splitlines()
    t0 = next(l.split()[0] for l in st if " START " in l)
    t1 = next(l.split()[0] for l in st if l.endswith("ALL_DONE"))
    hours = (datetime.fromisoformat(t1.replace("Z", "+00:00"))
             - datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds() / 3600
    need(f"{hours:.1f} 시간", "전체 벽시계")
    for log, stage, tot in (("driver_aomic.log", "nulls_n3", 5), ("driver_abide.log", "nulls_n3", 5),
                            ("driver_aomic.log", "fits_bqn", 255), ("driver_abide.log", "fits_bqn", 255),
                            ("driver_abide.log", "abide_fits_han_rerun_failed", 149),
                            ("driver_abide.log", "site", 90)):
        need(f"{log_seconds(run / log, stage, tot):,} s", f"{log} {stage} 경과")

    print(f"대조 항목 {checked[0]}")
    return fails


def main() -> int:
    """대조를 실행하고 결과를 출력한다. 불일치가 있으면 1 을 돌려준다."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument("--run", type=Path, default=RUN_REL, help="data root 상대 run root")
    ap.add_argument("--doc", type=Path, required=True, help="대조할 보고서 (md)")
    a = ap.parse_args()
    run = a.data_root / a.run
    if not (run / "status.txt").is_file():
        raise SystemExit(f"run root 가 아니다: {run}")
    doc = a.doc.read_text(encoding="utf-8").replace("−", "-")
    fails = crosscheck(doc, run)
    for f in fails:
        print("FAIL", f)
    print("불일치", len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
