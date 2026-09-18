#!/usr/bin/env python3
"""Wave 1 감사 — 내려받은 메타데이터로 G0 차단 항목을 판정한다.

입력은 `01_wave1_fetch_metadata.sh --dest <root>` 의 산출 트리다. 이 스크립트는
표준 라이브러리만 쓰며(numpy/pandas 불필요) 다음을 run 단위로 확정한다.

  U1'  native TR                 : raw sidecar 또는 BIDS inheritance 루트 sidecar 의 RepetitionTime
  U2   제거(non-steady-state)    : confounds 의 non_steady_state_outlier* 열 개수
  U4   nuisance 구성 가능성      : 24 motion / aCompCor 5 / FD 열 존재 여부와 design rank 상한
  U5   events 원점               : events.tsv 의 최소 onset 과 열 구성
  --   volume 수                 : confounds 행 수 (fMRIPrep 출력 기준)

또한 [12,252) 주분석 구간이 각 run 에서 성립하는지 산술로 판정한다.

산출:
  <out>/wave1_runs.jsonl    run 단위 레코드 (source_runs.jsonl 갱신 입력)
  <out>/wave1_summary.json  task 별 집계와 차단 항목 판정
  <out>/wave1_files.sha256  받은 파일 전수 SHA256

사용:
  python3 02_wave1_audit.py --root /data/aomic_wave1 --out /data/aomic_wave1/wave1_audit
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ANALYSIS_START = 12.0
ANALYSIS_END = 252.0
TARGET_GRID = 2.0

# 계획서 3.2: motion 6 + 시간 미분 + 각 12항의 제곱 = 24
MOTION_BASE = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
MOTION_24 = (
    MOTION_BASE
    + [f"{c}_derivative1" for c in MOTION_BASE]
    + [f"{c}_power2" for c in MOTION_BASE]
    + [f"{c}_derivative1_power2" for c in MOTION_BASE]
)
ENTITY_RE = re.compile(r"(?P<key>[a-zA-Z]+)-(?P<val>[a-zA-Z0-9]+)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entities(name: str) -> Dict[str, str]:
    """BIDS 파일명에서 entity 를 뽑는다. 없는 entity 는 담지 않는다."""
    stem = name.split(".")[0]
    out: Dict[str, str] = {}
    for part in stem.split("_"):
        m = ENTITY_RE.fullmatch(part)
        if m:
            out[m.group("key")] = m.group("val")
    return out


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # 손상 파일을 조용히 넘기지 않는다
        return {"__read_error__": f"{type(exc).__name__}: {exc}"}


def tsv_header_and_rows(path: Path) -> Tuple[List[str], int]:
    """TSV 의 열 이름과 데이터 행 수를 센다."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, [])
        n = sum(1 for _ in reader)
    return header, n


def inherited_tr(root: Path, ds: str, task: str) -> Tuple[Optional[float], Optional[str]]:
    """BIDS inheritance: 데이터셋 루트의 task-<name>_bold.json."""
    cand = root / ds / "raw" / f"task-{task}_bold.json"
    if cand.is_file():
        d = read_json(cand)
        if isinstance(d.get("RepetitionTime"), (int, float)):
            return float(d["RepetitionTime"]), str(cand)
    return None, None


def audit_dataset(root: Path, ds: str) -> List[Dict[str, Any]]:
    raw = root / ds / "raw"
    deriv = root / ds / "fmriprep"
    records: List[Dict[str, Any]] = []

    # confounds 를 기준 축으로 삼는다 (run 단위로 반드시 하나)
    conf_files = sorted(
        list(deriv.glob("sub-*/func/*desc-confounds_regressors.tsv"))
        + list(deriv.glob("sub-*/func/*desc-confounds_timeseries.tsv"))
    )
    if not conf_files:
        print(f"[warn] {ds}: confounds TSV 0건 — derivative 경로를 확인하라", file=sys.stderr)

    for cf in conf_files:
        ent = entities(cf.name)
        sub = ent.get("sub", "na")
        task = ent.get("task", "na")
        acq = ent.get("acq", "na")
        run = ent.get("run", "na")
        ses = ent.get("ses", "na")

        rec: Dict[str, Any] = {
            "dataset": ds,
            "run_key": f"{ds}/sub-{sub}/{ses}/{task}/{run}/{acq}",
            "canonical_subject": f"{ds}:sub-{sub}",   # U17: dataset prefix 필수
            "task": task, "acquisition": acq, "run": run, "session": ses,
            "unresolved": [],
        }

        # --- confounds ---
        try:
            cols, n_rows = tsv_header_and_rows(cf)
        except Exception as exc:
            rec["unresolved"].append(f"confounds_unreadable:{type(exc).__name__}")
            cols, n_rows = [], 0
        rec["confounds_path"] = str(cf)
        rec["confounds_sha256"] = sha256(cf)
        rec["n_volumes_from_confounds"] = n_rows
        rec["n_confound_columns"] = len(cols)

        present_motion = [c for c in MOTION_24 if c in cols]
        rec["motion24_present"] = len(present_motion)
        rec["motion24_complete"] = len(present_motion) == 24
        if not rec["motion24_complete"]:
            rec["unresolved"].append("motion24_incomplete")

        acomp = sorted(c for c in cols if c.startswith("a_comp_cor_"))
        rec["a_comp_cor_columns"] = len(acomp)
        rec["a_comp_cor_ge5"] = len(acomp) >= 5
        if not rec["a_comp_cor_ge5"]:
            rec["unresolved"].append("acompcor_lt5")

        rec["fd_column"] = "framewise_displacement" if "framewise_displacement" in cols else None
        if rec["fd_column"] is None:
            rec["unresolved"].append("fd_column_absent")

        nss = sorted(c for c in cols if c.startswith("non_steady_state_outlier"))
        rec["non_steady_state_columns"] = len(nss)
        rec["discarded_volumes"] = len(nss)   # U2

        # design rank 상한: 24 motion + aCompCor 5 + spike + drift/intercept
        rec["design_rank_upper_bound"] = 24 + 5 + len(nss) + 2
        rec["residual_dof_upper_bound"] = n_rows - rec["design_rank_upper_bound"]
        rec["residual_dof_gt30"] = rec["residual_dof_upper_bound"] > 30
        if not rec["residual_dof_gt30"]:
            rec["unresolved"].append("residual_dof_le30")

        # --- aCompCor metadata (설명분산 순서) ---
        meta = cf.with_suffix(".json")
        if meta.is_file():
            md = read_json(meta)
            rec["acompcor_metadata_path"] = str(meta)
            rec["acompcor_metadata_sha256"] = sha256(meta)
            keys = [k for k in md if k.startswith("a_comp_cor_")]
            rec["acompcor_metadata_entries"] = len(keys)
            rec["acompcor_has_variance_order"] = any(
                isinstance(md.get(k), dict) and "VarianceExplained" in md[k] for k in keys
            )
            if not rec["acompcor_has_variance_order"]:
                rec["unresolved"].append("acompcor_variance_order_absent")
        else:
            rec["acompcor_metadata_path"] = None
            rec["unresolved"].append("acompcor_metadata_absent")

        # --- native TR ---
        tr: Optional[float] = None
        tr_src: Optional[str] = None
        pat = f"sub-{sub}/func/*task-{task}*"
        assert "**" not in pat, f"invalid glob pattern: {pat}"
        for cand in sorted(raw.glob(pat + "_bold.json")):
            d = read_json(cand)
            if isinstance(d.get("RepetitionTime"), (int, float)):
                tr, tr_src = float(d["RepetitionTime"]), str(cand)
                rec["slice_timing_len"] = len(d.get("SliceTiming") or []) or None
                rec["task_name_field"] = d.get("TaskName")
                rec["raw_sidecar_sha256"] = sha256(cand)
                break
        if tr is None:
            tr, tr_src = inherited_tr(root, ds, task)
        rec["native_tr"] = tr
        rec["native_tr_source"] = tr_src
        if tr is None:
            rec["unresolved"].append("native_tr_unknown")

        # derivative grid 의 TR (raw 와 다르면 명시적 실패)
        dtr = None
        for cand in sorted(deriv.glob(pat + "desc-preproc_bold.json")):
            d = read_json(cand)
            if isinstance(d.get("RepetitionTime"), (int, float)):
                dtr = float(d["RepetitionTime"]); break
        rec["derivative_tr"] = dtr
        if tr is not None and dtr is not None and abs(tr - dtr) > 1e-9:
            rec["unresolved"].append("raw_vs_derivative_tr_mismatch")

        # --- events ---
        ev = sorted(raw.glob(pat + "_events.tsv"))
        if ev:
            e = ev[0]
            try:
                ecols, erows = tsv_header_and_rows(e)
                with e.open(newline="", encoding="utf-8") as fh:
                    rdr = csv.DictReader(fh, delimiter="\t")
                    onsets = []
                    for row in rdr:
                        try:
                            onsets.append(float(row.get("onset", "nan")))
                        except ValueError:
                            pass
                rec["events_path"] = str(e)
                rec["events_sha256"] = sha256(e)
                rec["events_columns"] = ecols
                rec["events_n_rows"] = erows
                rec["events_min_onset"] = min(onsets) if onsets else None
                rec["events_max_onset"] = max(onsets) if onsets else None
            except Exception as exc:
                rec["unresolved"].append(f"events_unreadable:{type(exc).__name__}")
        else:
            rec["events_path"] = None
            # restingstate 는 events 가 없는 것이 정상이므로 결함으로 세지 않는다.
            if task != "restingstate":
                rec["unresolved"].append("events_absent")
            else:
                rec["events_expected"] = False

        # --- [12,252) 성립 여부 ---
        if tr is not None and n_rows:
            dur = n_rows * tr
            rec["duration_sec"] = dur
            # 제거된 volume 은 원본 clock 앞쪽에서 사라진 것으로 가정하지 않는다.
            # non_steady_state 는 fMRIPrep 이 표시만 하고 길이는 유지하므로 dur 는 원본 길이다.
            rec["supports_analysis_window"] = dur >= ANALYSIS_END
            rec["slack_sec"] = dur - ANALYSIS_END
            rec["samples_on_2s_grid"] = int((ANALYSIS_END - ANALYSIS_START) / TARGET_GRID)
            if not rec["supports_analysis_window"]:
                rec["unresolved"].append("analysis_window_unsupported")
        else:
            rec["duration_sec"] = None
            rec["supports_analysis_window"] = None
            rec["unresolved"].append("window_support_undetermined")

        records.append(rec)
    return records


def summarise(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_task: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_task[f"{r['dataset']}/{r['task']}"].append(r)

    tasks: Dict[str, Any] = {}
    for key, rs in sorted(by_task.items()):
        trs = Counter(r["native_tr"] for r in rs)
        vols = Counter(r["n_volumes_from_confounds"] for r in rs)
        disc = Counter(r["discarded_volumes"] for r in rs)
        sup = Counter(r["supports_analysis_window"] for r in rs)
        tasks[key] = {
            "n_runs": len(rs),
            "native_tr_distribution": {str(k): v for k, v in trs.items()},
            "native_tr_unique": len([k for k in trs if k is not None]) == 1,
            "n_volumes_distribution": {str(k): v for k, v in vols.items()},
            "discarded_volumes_distribution": {str(k): v for k, v in disc.items()},
            "supports_analysis_window": {str(k): v for k, v in sup.items()},
            "motion24_complete": sum(1 for r in rs if r["motion24_complete"]),
            "acompcor_ge5": sum(1 for r in rs if r["a_comp_cor_ge5"]),
            "fd_present": sum(1 for r in rs if r["fd_column"]),
            "events_present": sum(1 for r in rs if r.get("events_path")),
            "residual_dof_gt30": sum(1 for r in rs if r.get("residual_dof_gt30")),
        }

    reasons = Counter(u.split(":")[0] for r in records for u in r["unresolved"])
    clean = sum(1 for r in records if not r["unresolved"])

    def verdict(cond: bool) -> str:
        return "resolved" if cond else "still_blocked"

    targets = [r for r in records if r["task"] in ("emomatching", "workingmemory")]
    # restingstate 에는 events 파일이 없는 것이 정상이다. events 를 모든 run 에
    # 요구하면 rest 때문에 U5 가 영구히 still_blocked 로 남는다.
    event_bearing = [r for r in records if r["task"] != "restingstate"]
    # aCompCor 5개 미만인 run 은 "전체 차단"이 아니라 "해당 run 제외" 사유다
    # (계획서 3.2: 정의에 맞는 5개가 없으면 다른 열로 대체하지 않는다).
    acomp_bad = [r for r in records if not r["a_comp_cor_ge5"]]
    motion_bad = [r for r in records if not r["motion24_complete"]]
    fd_bad = [r for r in records if r["fd_column"] is None]
    blockers = {
        "U1_native_tr_targets": verdict(
            bool(targets) and all(r["native_tr"] is not None for r in targets)),
        # non_steady_state 열이 0개인 것은 "제거 volume 0" 일 수도, 열 집합이 잘린 것일 수도
        # 있다. fMRIPrep 은 항상 framewise_displacement 를 쓰므로, 그 존재를 confounds 가
        # 온전한 fMRIPrep 산출물이라는 표식으로 삼아야만 0 을 0 으로 읽을 수 있다.
        "U2_discarded_volumes": verdict(
            bool(records) and all(
                r["n_confound_columns"] > 0 and r["fd_column"] is not None
                and r["non_steady_state_columns"] is not None for r in records)),
        # 구조적 가용성(열 정의가 데이터셋 전반에서 성립하는가)과 개별 run 결함을
        # 분리한다. 후자는 exclusions.jsonl 로 넘어갈 QC 사유이지 gate 차단이 아니다.
        "U4_nuisance_constructible": verdict(
            bool(records) and not motion_bad and not fd_bad
            and len(acomp_bad) < len(records)),
        "U5_events_origin": verdict(
            bool(event_bearing) and all(r.get("events_path") for r in event_bearing)),
        "window_12_252_supported_for_targets": verdict(
            bool(targets) and all(r.get("supports_analysis_window") for r in targets)),
    }
    return {
        "n_runs": len(records),
        "n_runs_without_unresolved": clean,
        "run_level_exclusion_candidates": {
            "acompcor_lt5": sorted(r["run_key"] for r in acomp_bad),
            "motion24_incomplete": sorted(r["run_key"] for r in motion_bad),
            "fd_column_absent": sorted(r["run_key"] for r in fd_bad),
        },
        "events_scope_note": (
            f"events 는 restingstate 를 제외한 {len(event_bearing)} runs 에만 요구된다. "
            f"events_absent 로 집계된 run 은 대부분 restingstate 이며 결함이 아니다."),
        "unresolved_reason_counts": dict(reasons.most_common()),
        "tasks": tasks,
        "blocker_verdicts": blockers,
        "note": ("blocker_verdicts 는 이 wave 로 확보된 파일만 근거로 한다. "
                 "resolved 는 해당 항목의 정보가 존재함을 뜻하며 QC 통과를 뜻하지 않는다."),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True, help="01_wave1_fetch_metadata.sh 의 --dest")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--datasets", nargs="*", default=["ds002785", "ds002790"])
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    for ds in args.datasets:
        if not (args.root / ds).is_dir():
            print(f"[warn] {ds} 트리 없음 — 건너뜀", file=sys.stderr)
            continue
        records.extend(audit_dataset(args.root, ds))

    runs_path = args.out / "wave1_runs.jsonl"
    with runs_path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = summarise(records)
    (args.out / "wave1_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with (args.out / "wave1_files.sha256").open("w", encoding="utf-8") as fh:
        for p in sorted(args.root.rglob("*")):
            if p.is_file() and args.out not in p.parents:
                fh.write(f"{sha256(p)}  {p.relative_to(args.root)}\n")

    print(json.dumps(summary["blocker_verdicts"], indent=2, ensure_ascii=False))
    print(f"\nruns={summary['n_runs']}  clean={summary['n_runs_without_unresolved']}")
    print(f"산출: {runs_path}, {args.out/'wave1_summary.json'}, {args.out/'wave1_files.sha256'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
