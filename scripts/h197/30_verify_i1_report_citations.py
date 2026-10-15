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
  * (2.1 판) 확장 run root ``analysis/*.json`` · ``kept_subjects.json`` · ``status.txt`` ·
    ``abide/mobse_*/…/summary.json`` 과 확장 잠금 ``lock.json`` — 963 명 공통 분석 (결정 59)
  * (2.3 판) ADHD-200 run root ``analysis/adhd200/*.json`` · ``mobse/kept_subjects.json`` ·
    ``status.txt`` · ``mobse/status.txt`` · ``driver_adhd200.log`` · ``fails_*.json`` ·
    ``mobse/abide/mobse_*/…/summary.json`` 과 ADHD-200 잠금 ``lock.json`` (결정 65)

문서의 모든 수치를 덮지는 않는다 — 잠금 해시 · 잠금 전 측정 (BrainGB · smoke) ·
산출 크기처럼 위 파일에 없는 값은 대조 대상이 아니다.

이 파일은 ``scripts/i1/`` 에 두지 않는다 — I1 잠금의 code_hash 가 ``scripts/i1/*.py`` 를 해시한다.

Usage:
    python scripts/h197/30_verify_i1_report_citations.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset \
        --doc results/i1/reports/i1_report_2026-10-13.md \
        --lock results/i1_mobse_abide/locks/lock.json \
        --adhd-lock results/i1_adhd200/locks/lock.json
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
EXT_REL = Path("i1_mobse_abide/main/20261013_64e75f1c_a1")
ADHD_REL = Path("adhd200/main/20261014_9903dc89_a1")
MOBSE = ("mobse_mean", "mobse_embedding")
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


def crosscheck_ext(doc: str, ext: Path, lock: Path) -> List[str]:
    """2.1 판 — ABIDE MoBSE 확장 실행 (963 명 공통 분석) 의 인용 수치를 대조한다.

    Args:
        doc: 보고서 본문 (빼기표를 ASCII 하이픈으로 바꾼 것).
        ext: 확장 run root.
        lock: 확장 잠금 ``lock.json``.

    Returns:
        불일치 사유 문자열의 목록.
    """
    fails: List[str] = []
    checked = [0]

    def need(s: str, why: str) -> None:
        checked[0] += 1
        if s not in doc:
            fails.append(f"[2.1] {why}: '{s}' 가 문서에 없다")

    def must(ok: bool, why: str) -> None:
        checked[0] += 1
        if not ok:
            fails.append(f"[2.1] {why}")

    an = ext / "analysis"
    B = {m: load(an / f"{m}.json") for m in MOBSE + PUBLIC}
    for m in MOBSE + PUBLIC:
        need(sha12(an / f"{m}.json"), f"sha {m}.json")
    need(sha12(ext / "kept_subjects.json"), "sha kept_subjects.json")
    kept = load(ext / "kept_subjects.json")
    must(kept["n_kept"] == 963 == len(kept["kept"]), f"963 명이 아니다: {kept['n_kept']}")
    need(f"{1009 - kept['n_kept']} 명", "뺀 사람 수")
    L = load(lock)
    for v, why in ((L["lock_hash"], "lock_hash"), (L["code"]["code_hash"], "code_hash"),
                   (L["data"]["data_hash"], "data_hash"), (L["public_predictions"]["bundle_hash"], "공개 예측 묶음")):
        need(v[:12], f"확장 잠금 {why}")

    for m in MOBSE + PUBLIC:
        d = B[m]
        a = d["all"]
        must(d["incomplete_units"] == [], f"{m} incomplete_units 가 비어 있지 않다")
        must(a["n_items"] == 963, f"{m} n_items {a['n_items']} ≠ 963")
        must(d["n_fits"] == (180 if m in MOBSE else 255), f"{m} n_fits {d['n_fits']}")
        need(f"{a['orig_auc_mean']:.4f}", f"{m} 원판 AUC")
        conds = ("n0", "n1", "n2") if m in MOBSE else NULLS
        must(sorted(a["conditions"]) == sorted(conds), f"{m} 조건이 {conds} 가 아니다")
        for c in conds:
            cond = a["conditions"][c]
            need(delta_text(cond), f"{m} {c} Δ")
            if c == "n0":
                must(cond["retrain_ci95"][0] <= 0 <= cond["retrain_ci95"][1], f"{m} n0 CI 가 0 을 포함하지 않는다")
            elif c in ("n1", "n2"):
                must(cond["retrain_ci95"][0] > 0, f"{m} {c} 재학습 포함 CI 하한이 0 을 넘지 않는다")
        if m in MOBSE:
            need(f"{d['n_collapsed_fits']}/{d['n_fits']}", f"{m} 붕괴 수")
            need(delta_text(d["excluding_collapsed"]["conditions"]["n1"]), f"{m} n1 붕괴 뺀 민감도")
            must(d["excluding_collapsed"]["conditions"]["n1"]["retrain_ci95"][0] > 0, f"{m} 붕괴 뺀 n1 하한 ≤ 0")
            for c in ("n1", "n2"):
                need(f"{a['conditions'][c]['single_excludes_zero_rate']:.3f}", f"{m} {c} 단일 CI 비율")
        else:
            must(all(a["conditions"][c]["single_excludes_zero_rate"] == 1.0 for c in NULLS[1:]),
                 f"{m} 단일 CI 비율이 모두 1.000 이 아니다")
    for m in ("bqn", "bnt"):
        need(f"{B[m]['n_collapsed_fits']}/{B[m]['n_fits']}", f"{m} 붕괴 수")
    must(B["han"]["n_collapsed_fits"] == 0, "Han 붕괴가 0 이 아니다")

    po = [B[m]["all"]["orig_auc_mean"] for m in PUBLIC]
    need(f"{min(po):.4f}–{max(po):.4f}", "공개 모델 원판 범위 (963 명)")
    mn = [B[m]["all"]["conditions"][c]["null_auc_mean"] for m in MOBSE for c in ("n1", "n2")]
    pn = [B[m]["all"]["conditions"][c]["null_auc_mean"] for m in PUBLIC for c in ("n1", "n2")]
    need(f"{min(mn):.3f}–{max(mn):.3f}", "MoBSE 뒤섞은 AUC 범위")
    need(f"{min(pn):.3f}–{max(pn):.3f}", "공개 모델 뒤섞은 AUC 범위")

    summ = [load(p) for p in sorted((ext / "abide").glob("mobse_*/*/k*/r*/f*/summary.json"))]
    must(len(summ) == 360, f"summary.json {len(summ)} ≠ 360")
    ne = [x["n_epochs"] for x in summ]
    need(f"{min(ne)}–{max(ne)} epoch", "MoBSE epoch 수 범위")

    st = (ext / "status.txt").read_text(encoding="utf-8").splitlines()
    for ph, tot in (("prep", 60), ("fit", 360)):
        hit = [l for l in st if f"END {ph} 실패 0 경과" in l]
        must(len(hit) == 1, f"status END {ph} 실패 0 줄이 하나가 아니다")
        if hit:
            sec = int(re.search(r"경과 (\d+) s", hit[0]).group(1))
            need(f"{sec:,} s", f"{ph} 경과")
    t0 = st[0].split()[0]
    t1 = next(l.split()[0] for l in st if l.endswith("ALL_DONE"))
    hours = (datetime.fromisoformat(t1.replace("Z", "+00:00"))
             - datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds() / 3600
    need(f"{hours:.1f} 시간", "확장 전체 벽시계")
    must(load(ext / "fails_prep.json") == [] and load(ext / "fails_fit.json") == [], "fails_*.json 이 비어 있지 않다")

    print(f"2.1 판 대조 항목 {checked[0]}")
    return fails


def crosscheck_adhd(doc: str, run: Path, lock: Path) -> List[str]:
    """2.3 판 — ADHD-200 확장 실행 (541 명, 결정 65) 의 인용 수치를 대조한다.

    Args:
        doc: 보고서 본문 (빼기표를 ASCII 하이픈으로 바꾼 것).
        run: ADHD-200 run root.
        lock: ADHD-200 잠금 ``lock.json``.

    Returns:
        불일치 사유 문자열의 목록.
    """
    fails: List[str] = []
    checked = [0]

    def need(s: str, why: str) -> None:
        checked[0] += 1
        if s not in doc:
            fails.append(f"[2.3] {why}: '{s}' 가 문서에 없다")

    def must(ok: bool, why: str) -> None:
        checked[0] += 1
        if not ok:
            fails.append(f"[2.3] {why}")

    an = run / "analysis" / "adhd200"
    models = MOBSE + PUBLIC + BASELINES
    C = {m: load(an / f"{m}.json") for m in models}
    for m in models:
        need(sha12(an / f"{m}.json"), f"sha {m}.json")
    kept_p = run / "mobse" / "kept_subjects.json"
    need(sha12(kept_p), "sha kept_subjects.json")
    kept = load(kept_p)
    must(kept["n_kept"] == 541 == len(kept["kept"]), f"541 명이 아니다: {kept['n_kept']}")
    need(f"{kept['n_kept']} 명", "대상 수")
    L = load(lock)
    for v, why in ((L["lock_hash"], "lock_hash"), (L["code"]["code_hash"], "code_hash"),
                   (L["data"]["data_hash"], "data_hash")):
        need(v[:12], f"ADHD-200 잠금 {why}")

    n_fits = {"mobse_mean": 180, "mobse_embedding": 180, "bqn": 255, "bnt": 255, "han": 255,
              "fc_logistic": 5, "fc_mlp": 15, "s1_logistic": 5}
    positive = ("bqn", "bnt")  # n1–n3 하한 > 0 으로 적은 모델
    for m in models:
        d = C[m]
        a = d["all"]
        must(d["incomplete_units"] == [], f"{m} incomplete_units 가 비어 있지 않다")
        must(a["n_items"] == 541, f"{m} n_items {a['n_items']} ≠ 541")
        must(d["n_fits"] == n_fits[m], f"{m} n_fits {d['n_fits']} ≠ {n_fits[m]}")
        need(f"{a['orig_auc_mean']:.4f}", f"{m} 원판 AUC")
        if m in BASELINES:
            continue
        conds = ("n0", "n1", "n2") if m in MOBSE else NULLS
        must(sorted(a["conditions"]) == sorted(conds), f"{m} 조건이 {conds} 가 아니다")
        for c in conds:
            cond = a["conditions"][c]
            lo, hi = cond["retrain_ci95"]
            need(delta_text(cond), f"{m} {c} Δ")
            if m in positive and c != "n0":
                must(lo > 0, f"{m} {c} 하한이 0 을 넘지 않는다")
            else:
                must(lo <= 0 <= hi, f"{m} {c} CI 가 0 을 포함하지 않는다")
        if m in MOBSE:
            must(d["n_collapsed_fits"] == 0, f"{m} 붕괴가 0 이 아니다")
            must(all(v["single_excludes_zero_rate"] == 0.0 for v in a["conditions"].values()),
                 f"{m} 단일 CI 비율이 모두 0.000 이 아니다")
        need(f"{d['n_collapsed_fits']}/{d['n_fits']}", f"{m} 붕괴 수")
    must(C["han"]["n_collapsed_fits"] == 0, "Han 붕괴가 0 이 아니다")

    # 붕괴 단위 (뒤섞기 판 · seed) 와 붕괴 뺀 민감도
    for m, name in (("bqn", "BQN"), ("bnt", "BNT")):
        d = C[m]
        tot = {}
        for u in d["all"]["units"]:
            tot[u.split("/")[0]] = tot.get(u.split("/")[0], 0) + 1
        col = {}
        for u in d["collapsed_units"]:
            col[u.split("/")[0]] = col.get(u.split("/")[0], 0) + 1
        parts = [f"원판 {col.get('orig', 0)}/{tot['orig']}"] + [f"{c} {col.get(c, 0)}/{tot[c]}" for c in NULLS]
        need(f"{name} " + " · ".join(parts), f"{m} 붕괴 단위")
        exc = d["excluding_collapsed"]["conditions"]
        for c, v in exc.items():
            if v["n_pairs"] == 1:
                need(f"{c} 1 짝 ({v['delta_mean']:+.4f})", f"{m} {c} 붕괴 뺀 1 짝")
            else:
                need(f"{c} {v['n_pairs']} 짝 {delta_text(v)}", f"{m} {c} 붕괴 뺀 민감도")
    eq = C["bqn"]["excluding_collapsed"]["conditions"]
    must(sorted(eq) == ["n0", "n1", "n3"] and eq["n3"]["retrain_ci95"][0] <= 0,
         "BQN 붕괴 뺀 조건 · n3 판정이 문서와 다르다")
    et = C["bnt"]["excluding_collapsed"]["conditions"]
    must(sorted(et) == ["n0", "n2", "n3"] and et["n2"]["retrain_ci95"][0] > 0 and et["n3"]["retrain_ci95"][0] > 0,
         "BNT 붕괴 뺀 조건 · 판정이 문서와 다르다")
    pn = [C[m]["all"]["conditions"][c]["null_auc_mean"] for m in positive for c in NULLS[1:]]
    need(f"{min(pn):.3f}–{max(pn):.3f}", "BQN · BNT 뒤섞은 AUC 범위")

    # 단일 CI 비율
    for m, conds in (("han", NULLS[1:]), ("bqn", NULLS[1:]), ("bnt", NULLS)):
        for c in conds:
            need(f"{c} {C[m]['all']['conditions'][c]['single_excludes_zero_rate']:.3f}", f"{m} {c} 단일 CI 비율")

    # 범위
    mo = [C[m]["all"]["orig_auc_mean"] for m in MOBSE + PUBLIC]
    need(f"{min(mo):.3f}–{max(mo):.3f}", "다섯 모델 원판 범위")
    bo = [C[m]["all"]["orig_auc_mean"] for m in BASELINES]
    need(f"{min(bo):.3f}–{max(bo):.3f}", "기준선 범위")
    need(f"FC logistic {C['fc_logistic']['all']['orig_auc_mean']:.3f}", "FC logistic (3 자리)")

    summ = [load(p) for p in sorted((run / "mobse" / "abide").glob("mobse_*/*/k*/r*/f*/summary.json"))]
    must(len(summ) == 360, f"MoBSE summary.json {len(summ)} ≠ 360")
    ne = sorted({x["n_epochs"] for x in summ})
    need(f"{ne[0]} epoch" if len(ne) == 1 else f"{ne[0]}–{ne[-1]} epoch", "MoBSE epoch 수")

    # 비용
    st = (run / "status.txt").read_text(encoding="utf-8").splitlines()
    t0 = next(l.split()[0] for l in st if " BEGIN lock " in l)
    t1 = next(l.split()[0] for l in st if l.endswith("ALL_DONE"))
    hours = (datetime.fromisoformat(t1.replace("Z", "+00:00"))
             - datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds() / 3600
    need(f"{hours:.1f} 시간", "ADHD-200 전체 벽시계")
    mst = (run / "mobse" / "status.txt").read_text(encoding="utf-8").splitlines()
    for ph in ("prep", "fit"):
        hit = [l for l in mst if f"END {ph} 실패 0 경과" in l]
        must(len(hit) == 1, f"mobse status END {ph} 실패 0 줄이 하나가 아니다")
        if hit:
            sec = int(re.search(r"경과 (\d+) s", hit[0]).group(1))
            need(f"{sec:,} s", f"MoBSE {ph} 경과")
    log = run / "driver_adhd200.log"
    need(f"{log_seconds(log, 'nulls_n3', 5):,} s", "n3 생성 경과")
    for m in ("bnt", "han"):
        a = log_seconds(log, f"fits_{m}_orig-n0-n1-n2", 180)
        b = log_seconds(log, f"fits_{m}_n3", 75)
        need(f"{a:,} s + {b:,} s", f"{m} 255 회 경과")
        need(f"{(a + b) / 3600:.1f} 시간", f"{m} 255 회 시간")
    need(f"{log_seconds(log, 'fits_bqn_orig-n0-n1-n2', 79):,} s", "BQN 마지막 구간 경과")
    fl = sorted(run.glob("fails_*.json")) + sorted((run / "mobse").glob("fails_*.json"))
    must(len(fl) == 11 and all(load(p) == [] for p in fl), f"fails_*.json {len(fl)} 개가 모두 빈 목록이 아니다")

    print(f"2.3 판 대조 항목 {checked[0]}")
    return fails


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
    ap.add_argument("--ext-run", type=Path, default=EXT_REL, help="data root 상대 확장 run root (2.1 판)")
    ap.add_argument("--lock", type=Path, default=None, help="확장 잠금 lock.json — 주면 2.1 판 항목도 대조")
    ap.add_argument("--adhd-run", type=Path, default=ADHD_REL, help="data root 상대 ADHD-200 run root (2.3 판)")
    ap.add_argument("--adhd-lock", type=Path, default=None, help="ADHD-200 잠금 lock.json — 주면 2.3 판 항목도 대조")
    a = ap.parse_args()
    run = a.data_root / a.run
    if not (run / "status.txt").is_file():
        raise SystemExit(f"run root 가 아니다: {run}")
    doc = a.doc.read_text(encoding="utf-8").replace("−", "-")
    fails = crosscheck(doc, run)
    if a.lock is not None:
        fails += crosscheck_ext(doc, a.data_root / a.ext_run, a.lock)
    if a.adhd_lock is not None:
        fails += crosscheck_adhd(doc, a.data_root / a.adhd_run, a.adhd_lock)
    for f in fails:
        print("FAIL", f)
    print("불일치", len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
