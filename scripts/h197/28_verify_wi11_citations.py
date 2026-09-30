#!/usr/bin/env python3
"""WI-11 연구 결과 패키지가 인용한 수치를 원자료와 대조한다 — 마감 3b 단계.

해시는 "파일이 바뀌지 않았다" 만 보증한다. 이 스크립트는 "그 파일을 옳게
요약했는가" 를 본다. 수치는 문서에서 문자열로 찾고, 값은 산출물에서 다시
읽어 만든다. **기록된 참은 참이 아니다.**

산출물은 data root 아래 09-28·09-29 실행 폴더에 있어 저장소 해시 검사
대상이 아니므로, `--data-root` 없이는 이 대조를 할 수 없다.

Usage:
    python scripts/h197/28_verify_wi11_citations.py \
        --data-root /mnt/data/mp2026/MoBSE_dataset \
        --repo-root . \
        --release results/redesign_v1/20260917_3c458d507e82_nocfg
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DATA_ROOT = Path("/mnt/data/mp2026/MoBSE_dataset")
DEFAULT_RELEASE = Path("results/redesign_v1/20260917_3c458d507e82_nocfg")
DOC_REL = Path("reports/wi11_research_package_2026-09-29.md")
MAIN_REL = Path("main_oof/20260928_1cd4054_main_a2")
AUX_REL = Path("main_oof/20260928_1cd4054_aux_a1")
NULL_SENS_REL = Path("null_sens/20260929_97e434a_a1")


def load(path: Path) -> Dict[str, Any]:
    """JSON 산출물 하나를 읽는다.

    Args:
        path: 읽을 파일의 절대 경로.

    Returns:
        파싱된 객체.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def crosscheck(doc_text: str, st: Dict[str, Any], cm: Dict[str, Any],
               ck: Dict[str, Any], ns: Dict[str, Any],
               dg: Dict[str, Any]) -> List[str]:
    """문서의 인용 수치를 산출물과 대조하고 불일치 사유를 모은다.

    Args:
        doc_text: WI-11 문서 본문 (빼기표를 ASCII 하이픈으로 통일한 것).
        st: main OOF `statistics.json`.
        cm: 보조 비교 `comparison_statistics.json`.
        ck: main OOF `completion_check.json`.
        ns: null 민감도 `null_sensitivity.json`.
        dg: A-S 진단 `as_diagnostic.json`.

    Returns:
        불일치 사유 문자열의 목록. 비어 있으면 대조 통과.
    """
    fails: List[str] = []

    def need(s: str, why: str) -> None:
        if s not in doc_text:
            fails.append(f"{why}: '{s}' 가 문서에 없다")

    # primary
    h1 = st["primary_contrasts"]["H1_A_minus_B"]
    h2 = st["primary_contrasts"]["H2_A_minus_C"]
    need(f"{h1['point_estimate']:+.4f}", "H1 점추정")
    need(f"[{h1['ci_lo']:+.4f}, {h1['ci_hi']:+.4f}]", "H1 CI")
    need(f"{h2['point_estimate']:+.4f}", "H2 점추정")
    need(f"[{h2['ci_lo']:+.4f}, {h2['ci_hi']:+.4f}]", "H2 CI")
    if st["both_primary_lower_gt_0"] is not False:
        fails.append("both_primary_lower_gt_0 가 false 가 아니다")

    # 칸별 BA (main 4 + aux 3)
    for cell in ("A", "B", "C", "D"):
        need(f"{st['cell_balanced_accuracy'][cell]['point_estimate']:.4f}", f"{cell} BA")
    for cell in ("S", "NG", "SG"):
        need(f"{cm['cell_balanced_accuracy'][cell]['point_estimate']:.4f}", f"{cell} BA")

    # 보조 contrast
    for name, key in (("A−S", "A_minus_S"), ("A−NG", "A_minus_NG"), ("A−SG", "A_minus_SG")):
        v = cm["auxiliary_contrasts"][key]
        need(f"{v['point_estimate']:+.4f}", f"{name} 점추정")
        need(f"[{v['ci_lo']:+.4f}, {v['ci_hi']:+.4f}]", f"{name} CI")

    # 완료 기준·누설
    need(str(ck["checks"]["window_prediction_rows"]).replace("12096", "12,096"), "창 예측 행")
    if ck["checks"]["train_subject_in_own_test_predictions"] != 0:
        fails.append("main 누설이 0 이 아니다")
    for seed, rec in ns["sensitivity_seeds"].items():
        if rec["train_subject_in_own_test_predictions"] != 0:
            fails.append(f"null seed {seed} 누설이 0 이 아니다")

    # null 민감도 범위
    pts = ns["null_spread"]["H2_A_minus_C_points"] + [ns["null_spread"]["primary_point"]]
    if not (min(pts) >= -0.016001 and max(pts) <= 0.000001):
        fails.append(f"A−C 다섯 판이 [−0.016, 0.000] 밖이다: {pts}")
    need("[-0.016, 0.000]", "null 민감도 범위 문구")

    # 진단
    need(str(dg["A_error_shape"]["wrong_runs_total"]), "A 오답 run 수")
    need(str(dg["subject_overlap_with_A"]["A_imperfect"]), "A 감점자 수")
    if dg["subject_overlap_with_A"]["A_imperfect_but_S_perfect"] != \
            dg["subject_overlap_with_A"]["A_imperfect"]:
        fails.append("A 감점자 전원이 S 만점이라는 진술이 자료와 다르다")
    need(str(dg["wrong_runs_by_cell"]["A"]["wrong_runs_with_margin_below_0.1"]), "margin<0.1 오답 수")

    # 자료 흐름
    need(str(st["bootstrap"]["n_subjects"]), "N")
    need("1,295", "Wave 1 run")
    need("157", "PIOP1 적격")
    need("189", "PIOP2 적격")

    # 잠금
    need("9b7b11cf8576", "측정 잠금")
    need("bcf1fec22676", "구현 잠금")
    need("ace5f4a41446", "split_hash")
    need("2a7d7d7f", "config_hash")

    return fails


def main(argv: List[str]) -> int:
    """CLI 진입점.

    Args:
        argv: `sys.argv`.

    Returns:
        불일치가 있으면 1, 없으면 0.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument("--repo-root", type=Path,
                    default=Path(__file__).resolve().parents[2])
    ap.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    args = ap.parse_args(argv[1:])

    data_root = args.data_root.resolve()
    doc_path = (args.repo_root.resolve() / args.release / DOC_REL).resolve()
    if not doc_path.is_file():
        print(f"WI-11 문서가 없다: {doc_path}")
        return 2

    main_dir = data_root / MAIN_REL
    aux_dir = data_root / AUX_REL
    null_dir = data_root / NULL_SENS_REL
    needed = {
        "statistics.json": main_dir / "report/statistics.json",
        "comparison_statistics.json": aux_dir / "report_comparison/comparison_statistics.json",
        "completion_check.json": main_dir / "summary/completion_check.json",
        "null_sensitivity.json": null_dir / "summary/null_sensitivity.json",
        "as_diagnostic.json": aux_dir / "diagnostic/as_diagnostic.json",
    }
    missing = [str(p) for p in needed.values() if not p.is_file()]
    if missing:
        # 검사하지 못한 것을 통과로 세지 않는다.
        for path in missing:
            print(f"[MISSING] {path}")
        print(f"WI-11 인용 수치 대조: 산출물 없음 {len(missing)}건 — 대조 불가")
        return 2

    # 문서는 활자용 빼기표 (U+2212) 를 쓴다. 대조는 ASCII 하이픈으로 통일한다 —
    # 표기 차이를 불일치로 세면 없는 오류를 만든다.
    doc_text = doc_path.read_text(encoding="utf-8").replace("−", "-")
    fails = crosscheck(
        doc_text,
        load(needed["statistics.json"]),
        load(needed["comparison_statistics.json"]),
        load(needed["completion_check.json"]),
        load(needed["null_sensitivity.json"]),
        load(needed["as_diagnostic.json"]),
    )
    for f in fails:
        print(f"[MISMATCH] {f}")
    print(f"WI-11 인용 수치 대조: 실패 {len(fails)}건")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
