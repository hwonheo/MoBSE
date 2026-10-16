#!/usr/bin/env python3
"""I3 본 실행 읽기 진단 (결정 71) — 기존 fit 산출만 읽는다 (새 학습 없음).

칸마다 선택 epoch · val loss (선택 시점 · epoch 0) · val/test 확률 SD · 블록 위치별 · outer 별 정확도 (seed 평균 p 를 0.5 로 자름).

Usage:
    python3 scripts/i3_diag/read_diag.py data/i3/main/20261016_1bc3622d_a1
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

run = Path(sys.argv[1])
cells = sorted(p.name for p in (run / "fits").iterdir())
print("| 칸 | 선택 epoch 중앙 [min–max] | epoch 수 | val loss 선택 (중앙) | val loss ep0 | val p SD | test p SD | 블록 0–7 정확도 (seed 평균 p) | outer 0–4 정확도 |")
print("|---|---|---:|---:|---:|---:|---:|---|---|")
for c in cells:
    sel, nep, vl, vl0, vsd, tsd = [], [], [], [], [], []
    probs = defaultdict(list)  # (subject, block) -> [p]
    lab, outer_of = {}, {}
    for f in sorted((run / "fits" / c).glob("outer*/seed*/summary.json")):
        s = json.loads(f.read_text())
        sel.append(s["selected_epoch"]); nep.append(s["n_epochs"]); vl.append(s["val_loss"])
        vsd.append(s["val_p_sd"]); tsd.append(s["test_p_sd"])
        ep = [json.loads(l) for l in (f.parent / "epochs.jsonl").read_text().splitlines()]
        vl0.append(ep[0]["val_loss"])
        k = int(f.parent.parent.name[5:])
        for l in (f.parent / "predictions.jsonl").read_text().splitlines():
            r = json.loads(l)
            probs[(r["subject"], r["block"])].append(r["p1"]); lab[(r["subject"], r["block"])] = r["label"]
            outer_of[r["subject"]] = k
    byb, byo = defaultdict(list), defaultdict(list)
    for key, ps in probs.items():
        ok = int((sum(ps) / len(ps) >= 0.5) == lab[key])
        byb[key[1]].append(ok); byo[outer_of[key[0]]].append(ok)
    bb = " ".join(f"{sum(byb[b]) / len(byb[b]):.2f}" for b in range(8))
    oo = " ".join(f"{sum(byo[o]) / len(byo[o]):.2f}" for o in range(5))
    print(f"| {c} | {st.median(sel):.0f} [{min(sel)}–{max(sel)}] | {st.median(nep):.0f} | {st.median(vl):.4f} | "
          f"{st.median(vl0):.4f} | {st.median(vsd):.3f} | {st.median(tsd):.3f} | {bb} | {oo} |")
