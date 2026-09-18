#!/usr/bin/env python3
"""Wave 1 confounds 로 run 단위 mean FD 를 계산한다 (표준 라이브러리만).

계획서 §3.3 의 두 QC 기준 중 **run 전체 mean FD ≤ 0.2 mm 만** 적용한다.
고정 window 별 FD>0.5 비율 기준은 window 매핑이 필요하므로 WI-02 의 몫이다.
따라서 여기서 나오는 N 은 **QC 통과 N 이 아니라 상한**이다.

fMRIPrep 의 framewise_displacement 첫 행은 정의상 결측(n/a)이며, 계획서 §3.3 이
"구조적 첫 FD 결측만 별도 표시"하라고 요구하므로 분모에서 제외하고 그 수를 센다.

사용:
  python3 05_run_level_fd.py --root /mnt/data/mp2026/MoBSE_dataset/aomic_wave1 \
      --runs /mnt/data/mp2026/MoBSE_dataset/aomic_wave1/wave1_audit/wave1_runs.jsonl \
      --out  /mnt/data/mp2026/MoBSE_dataset/aomic_wave1/wave1_audit/run_level_fd.json
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Dict, List, Optional

FD_MAX_MEAN = 0.2
FD_SPIKE = 0.5


def fd_series(path: Path) -> Dict[str, object]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if "framewise_displacement" not in (reader.fieldnames or []):
            return {"error": "framewise_displacement column absent"}
        vals: List[float] = []
        missing = 0
        for i, row in enumerate(reader):
            raw = (row.get("framewise_displacement") or "").strip()
            try:
                vals.append(float(raw))
            except ValueError:
                missing += 1
                if i != 0:
                    return {"error": f"non-structural FD gap at row {i} ({raw!r})"}
    if not vals:
        return {"error": "no finite FD values"}
    spikes = sum(1 for v in vals if v > FD_SPIKE)
    return {
        "n_frames_total": len(vals) + missing,
        "n_fd_observed": len(vals),
        "n_structural_missing": missing,
        "mean_fd": statistics.fmean(vals),
        "max_fd": max(vals),
        "n_spikes_gt_0p5": spikes,
        "spike_ratio": spikes / len(vals),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    recs = [json.loads(l) for l in args.runs.read_text(encoding="utf-8").splitlines() if l.strip()]
    out: List[Dict[str, object]] = []
    for r in recs:
        p = Path(r["confounds_path"])
        if not p.is_file():
            p = args.root / p.name  # 경로가 옮겨진 경우 대비
        row = {
            "run_key": r["run_key"], "dataset": r["dataset"], "task": r["task"],
            "canonical_subject": r["canonical_subject"],
            "a_comp_cor_ge5": r["a_comp_cor_ge5"],
        }
        row.update(fd_series(p) if p.is_file() else {"error": f"missing: {p}"})
        out.append(row)

    ok = [r for r in out if "error" not in r]
    errs = [r for r in out if "error" in r]

    # dataset × task 요약
    summary: Dict[str, Dict[str, object]] = {}
    for key in sorted({(r["dataset"], r["task"]) for r in ok}):
        rs = [r for r in ok if (r["dataset"], r["task"]) == key]
        fds = [r["mean_fd"] for r in rs]
        summary[f"{key[0]}/{key[1]}"] = {
            "n_runs": len(rs),
            "median_mean_fd": round(statistics.median(fds), 4),
            "pass_mean_fd_le_0.2": sum(1 for v in fds if v <= FD_MAX_MEAN),
            "median_spike_ratio": round(statistics.median(r["spike_ratio"] for r in rs), 4),
            "structural_missing_all_equal_1": all(r["n_structural_missing"] == 1 for r in rs),
        }

    # subject 수준 교집합 (run-level mean FD 기준만 적용한 상한)
    cohort: Dict[str, Dict[str, int]] = {}
    for ds in sorted({r["dataset"] for r in ok}):
        sets: Dict[str, set] = {}
        for r in ok:
            if r["dataset"] != ds:
                continue
            if not r["a_comp_cor_ge5"] or r["mean_fd"] > FD_MAX_MEAN:
                continue
            sets.setdefault(r["task"], set()).add(r["canonical_subject"])
        emo = sets.get("emomatching", set())
        wm = sets.get("workingmemory", set())
        rest = sets.get("restingstate", set())
        cohort[ds] = {
            "emomatching": len(emo), "workingmemory": len(wm), "restingstate": len(rest),
            "emo_and_wm": len(emo & wm), "emo_and_wm_and_rest": len(emo & wm & rest),
        }

    payload = {
        "criterion_applied": "run-level mean FD <= 0.2 mm, plus aCompCor>=5",
        "criterion_not_applied": ("고정 window 별 FD>0.5 비율 <= 10% (window 매핑 필요, WI-02), "
                                  "nonfinite/constant ROI, design rank 실측"),
        "warning": "여기의 N 은 상한이며 QC 통과 N 이 아니다.",
        "fd_thresholds": {"mean_fd_max": FD_MAX_MEAN, "spike": FD_SPIKE},
        "n_runs": len(out), "n_ok": len(ok), "n_error": len(errs),
        "errors": errs[:20],
        "by_dataset_task": summary,
        "cohort_upper_bound": cohort,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({"by_dataset_task": summary, "cohort_upper_bound": cohort,
                      "n_error": len(errs)}, indent=2, ensure_ascii=False))
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
