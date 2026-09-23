#!/usr/bin/env python3
"""문서가 인용한 수치를 원자료와 대조한다 — 마감 절차 3단계.

해시 검증(`17_verify_gate_hashes.py`)은 "파일이 기록과 같은가"를 보증하지,
"그 파일을 옳게 요약했는가"는 보증하지 않는다. rev23 재검수에서 서술 오류
2건이 이 단계에서만 잡혔다(보고서 부록 V.7).

문서의 모든 표 칸을 파싱하지는 않는다. **핵심 주장 위주의 대조**다.

Usage:
    python scripts/h197/22_crosscheck_reported_numbers.py results/redesign_v1/<release>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load(release: Path):
    return {
        "prec": json.loads((release / "provenance/wi03_precision/precision_scenarios.json").read_text(encoding="utf-8")),
        "res": json.loads((release / "provenance/wi03_resource/resource_benchmark.json").read_text(encoding="utf-8")),
        "lock": json.loads((release / "locks/measurement_lock.json").read_text(encoding="utf-8")),
        "md_prec": (release / "reports/precision_scenarios.md").read_text(encoding="utf-8"),
        "md_res": (release / "reports/resource_budget.md").read_text(encoding="utf-8"),
        "report": (release / "reports/wi00_wi01_execution_report_2026-09-17.md").read_text(encoding="utf-8"),
        "gate": json.loads((release / "gate_evidence.json").read_text(encoding="utf-8")),
    }


def _strings(node: Any):
    """중첩 구조 안의 모든 문자열."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def crosscheck_gate_lock_citation(lock: Dict[str, Any], gate: Dict[str, Any]) -> List[str]:
    """gate evidence 가 **현행** 잠금을 가리키는지 대조한다 (2026-09-23 추가).

    rev24 의 G1 판정 문장이 3세대 전 잠금(1c1fba…)을 인용한 채 남아 있었다.
    보고서 인용만 대조하던 3단계가 증거 파일 안의 같은 오류를 보지 못했다.

    - `wi03_measurement_lock.lock_hash` 와 `chain` 의 끝이 현행 잠금과 같아야 한다
    - `gates` 의 판정 문장에 **대체된** 잠금의 해시(앞 12자)가 나오면 실패
      (대체 이력은 `wi03_measurement_lock.chain`·`supersedes` 에만 둔다)
    """
    fails: List[str] = []
    cur = lock["lock_hash"]
    rec = gate.get("wi03_measurement_lock") or {}
    if rec.get("lock_hash") != cur:
        fails.append(f"gate_evidence 의 lock_hash 가 현행 잠금이 아니다: "
                     f"{str(rec.get('lock_hash'))[:12]} ≠ {cur[:12]}")
    chain = list(rec.get("chain") or [])
    if not chain or not cur.startswith(str(chain[-1]).rstrip("…")[:12]):
        fails.append("gate_evidence 의 잠금 사슬 끝이 현행 잠금이 아니다")
    old = {str(h).rstrip("…")[:12] for h in chain[:-1]}
    sup = (lock.get("supersedes") or {}).get("lock_hash")
    if sup:
        old.add(sup[:12])
    old.discard(cur[:12])
    for text in _strings(gate.get("gates") or []):
        for h in sorted(old):
            if h and h in text:
                fails.append(f"gate_evidence gates 판정 문장이 대체된 잠금 {h} 를 인용한다")
    return fails


def crosscheck(src: Dict[str, Any]) -> List[str]:
    """실패 목록을 돌려준다. 빈 목록이면 통과."""
    prec, res, lock = src["prec"], src["res"], src["lock"]
    md_prec, md_res, report = src["md_prec"], src["md_res"], src["report"]
    fails: List[str] = []

    def chk(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    def cell(n, pi, rho, delta):
        for c in prec["cells"]:
            if (c["n_subjects"], c["pi"], c["rho_latent"], c["delta_true"]) == (n, pi, rho, delta):
                return c
        raise KeyError((n, pi, rho, delta))

    for n in (126, 189):
        for pi in (0.05, 0.10, 0.20, 0.30):
            s = f"{cell(n, pi, 0.0, 0.02)['p_lower_gt_0']:.3f}"
            chk(s in md_prec, f"precision_scenarios.md: N={n} π={pi} δ=0.02 값 {s} 없음")
            if n == 126:
                chk(s in report, f"보고서: N=126 π={pi} 값 {s} 없음")

    for row in prec["minimum_detectable_effect"]:
        s = f"{row['mde']:.3f}"
        chk(s in md_prec,
            f"precision_scenarios.md: MDE N={row['n_subjects']} π={row['pi']} "
            f"ρ={row['rho_latent']} = {s} 없음")

    c2 = [c for c in prec["cells"] if c["delta_true"] == 0.02]
    lo2 = min(c["p_lower_gt_delta"] for c in c2)
    hi2 = max(c["p_lower_gt_delta"] for c in c2)
    chk(f"{lo2:.3f}–{hi2:.3f}" in md_prec.replace("**", ""),
        f"precision_scenarios.md: δ_true=0.02 의 P(하한>δ) 범위 {lo2:.3f}–{hi2:.3f} 인용 없음")
    # 정정된 과잉 일반화 문구가 되살아나지 않는지 본다. 부록 V.7 은 그 문장을
    # **인용**하므로 blockquote(`> `) 줄은 허용한다 — 인용까지 막으면 자기 기록을
    # 남길 수 없다.
    revived = [f"{tag}:{i+1}" for tag, text in (("precision", md_prec), ("report", report))
               for i, line in enumerate(text.splitlines())
               if "48개 칸 어디서도" in line and not line.lstrip().startswith(">")]
    chk(not revived,
        f"과잉 일반화 문구 '48개 칸 어디서도' 가 인용 밖에 남아 있다 (부록 V.7): {revived}")

    zero = [c["p_lower_gt_0"] for c in prec["cells"] if c["delta_true"] == 0.0]
    chk(f"{min(zero):.3f}–{max(zero):.3f}" in md_prec.replace("**", ""),
        f"δ=0 보정 범위 {min(zero):.3f}–{max(zero):.3f} 인용 없음")

    for scale in ("cells_inner_scale", "cells_outer_scale"):
        meds = [res[scale][c]["epoch"]["median_s"] for c in res[scale]]
        s = f"{min(meds):.3f} – {max(meds):.3f} s"
        chk(s in md_res or s.replace(" – ", "–") in md_res,
            f"resource_budget.md: {scale} epoch 범위 '{s}' 인용 없음")

    peaks = [res[s][c]["peak_gpu_bytes"] / 1048576
             for s in ("cells_inner_scale", "cells_outer_scale") for c in res[s]]
    s = f"{min(peaks):.1f}–{max(peaks):.1f} MiB"
    chk(s in md_res, f"resource_budget.md: peak GPU '{s}' 인용 없음")

    chk(str(res["fit_budget"]["total"]) in md_res, "resource_budget.md: fit 합계 인용 없음")

    ep = lock["endpoint"]
    chk(ep["n_primary_oof"] == 126 and ep["n_external"] == 189, "lock 의 N 이 126/189 가 아니다")
    chk(lock["cohorts"]["piop2"]["folds"] is None, "PIOP2 에 folds 가 있다 (§9 위반)")
    chk(lock["wi07_completion_targets"]["window_prediction_rows"]
        == ep["n_primary_oof"] * 2 * 4 * 3 * 4, "WI-07 window 행 수 공식 불일치")
    chk(lock["lock_hash"][:12] in report, "보고서의 lock_hash 인용 불일치")
    chk(lock["cohorts"]["piop1"]["folds"]["split_hash"][:12] in report,
        "보고서의 split_hash 인용 불일치")
    if "gate" in src:
        fails.extend(crosscheck_gate_lock_citation(lock, src["gate"]))
    return fails


def main(argv: List[str]) -> int:
    release = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    fails = crosscheck(load(release))
    for f in fails:
        print(f"[MISMATCH] {f}")
    print(f"인용 수치 대조: 실패 {len(fails)}건")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
