#!/usr/bin/env python3
"""band-pass 와 nuisance 회귀의 **순서** 가 결과를 바꾸는지 정량 비교한다.

계획서 §3.2 는 "nuisance와 filter를 일관되게 처리하는 하나의 검증된 구현·버전을
고정"하라고 요구하고, 구체적 명세는 "pilot 기술 검증에서 기록하고 main 전에
동결"하라고 정했다. **이 스크립트는 동결하지 않는다.** 선택지 사이의 차이를
합성 신호로 수치화해, pilot 에서 근거를 갖고 고를 수 있게 준비할 뿐이다.

비교하는 세 처리:
  A. regress_then_filter  — nuisance 를 원신호에서 회귀한 뒤 잔차를 필터링
  B. filter_both          — 신호와 nuisance 를 **같은 필터로** 거른 뒤 회귀
  X. filter_then_regress_unfiltered — 신호만 필터링하고 **거르지 않은** nuisance 로 회귀

핵심 쟁점은 **X** 다. 널리 알려진 결과(Hallquist et al., 2013, NeuroImage)로,
신호만 필터링한 뒤 원래의(거르지 않은) nuisance 로 회귀하면 nuisance 가 통과대역
안으로 **되돌아온다** — regressor 가 갖고 있는 통과대역 밖 성분이 필터링된 신호에는
없어서 적합이 틀어지기 때문이다. A 와 B 는 둘 다 이 함정을 피하는 처리이며,
이 probe 는 셋의 차이를 수치로 보여 준다.

**초판 정정.** 첫 판은 X 를 아예 넣지 않아 "문헌이 경고하는 순서"를 시험하지
않았고, filtfilt 의 edge transient 를 run 전체에서 채점해 B 를 과도하게 나쁘게
보이게 했다. 지금은 (1) X 를 추가하고, (2) **분석 구간 [12,252) 안에서만**
채점한다 — 어차피 창을 잘라 쓰는 구간이 거기이고, 양 끝 edge 는 계획서가 이미
버리는 부분이다.

출력은 "얼마나 되돌아오는가"의 수치다. 판단은 사람이 한다 — 이 스크립트는
계획서 §3.2 의 명세를 동결하지 않는다.

## 이 probe 로는 순서를 고를 수 없다 (2026-09-17 확인)

돌려 보고 나서야 분명해졌다. 합성 신호에서 **nuisance 가 설계행렬과 정확히
같게** 만들어지므로, "먼저 회귀"(A)는 **구성상 최적**이 된다 — 남길 것이 없다.
그 결과 A 가 잔차 1–5%, B·X 가 6–22% 로 나오는데, 이건 세 처리의 우열이 아니라
**합성의 구조가 A 에게 유리하게 짜였다**는 사실의 반영일 뿐이다.

실제로 문제가 되는 국면은 정반대다 — nuisance **모형이 불완전해서** 설계로
잡지 못한 성분을 필터가 잡아야 하는 경우다. 그 국면은 실제 confounds 와 실제
BOLD 가 있어야 만들어진다. 계획서 §3.2 가 이 명세를 "pilot 기술 검증에서
기록하고 main 전에 동결"하라고 정한 이유가 여기서 확인된다.

**그래도 하나는 얻었다.** 세 처리의 결과가 단위 진폭 신호에서 최대 0.65 만큼
갈린다. 즉 순서 선택은 장식이 아니며, 아무거나 골라 두고 넘어갈 수 없다.
pilot 에서 실자료로 골라 동결해야 한다.

이 스크립트는 그 pilot 실행의 뼈대로 남긴다 — `synth()` 를 실제 run 로더로
바꾸면 그대로 쓸 수 있다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from scipy.signal import butter, filtfilt

LOW_HZ = 0.008
HIGH_HZ = 0.100


def bandpass(data: np.ndarray, tr: float, *, order: int = 5,
             low: float = LOW_HZ, high: float = HIGH_HZ) -> np.ndarray:
    """0-phase Butterworth band-pass. 축 0 이 시간이다."""
    nyquist = 0.5 / tr
    if high >= nyquist:
        raise ValueError(f"통과대역 상한 {high} Hz 가 Nyquist {nyquist} Hz 이상이다")
    b, a = butter(order, [low / nyquist, high / nyquist], btype="band")
    return filtfilt(b, a, data, axis=0)


def regress(data: np.ndarray, design: np.ndarray) -> np.ndarray:
    """최소제곱 잔차."""
    beta, *_ = np.linalg.lstsq(design, data, rcond=None)
    return data - design @ beta


def synth(n_frames: int, tr: float, seed: int = 20260917
          ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """신호 + nuisance 를 만든다.

    nuisance 는 **통과대역 밖 성분을 일부러 크게** 넣는다 (매우 느린 drift 와
    호흡대역 빠른 성분). 이것이 A 에서 되돌아오는지를 보는 것이 목적이다.

    Returns:
        (관측신호, nuisance 설계, 정답 신경신호)
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n_frames) * tr

    # 관심 신호: 통과대역 안쪽 0.02·0.05 Hz
    neural = (np.sin(2 * np.pi * 0.02 * t) + 0.6 * np.sin(2 * np.pi * 0.05 * t))
    neural = neural[:, None]

    # nuisance: 아주 느린 drift(0.002 Hz, 통과대역 아래) + 빠른 호흡(0.20 Hz, 위)
    slow = np.sin(2 * np.pi * 0.002 * t)
    fast = np.sin(2 * np.pi * 0.20 * t)
    design = np.column_stack([np.ones(n_frames), slow, fast,
                              rng.normal(size=n_frames) * 0.1])

    weights = np.array([[0.0], [3.0], [2.0], [0.5]])
    observed = neural + design @ weights
    return observed, design, neural


def band_power(data: np.ndarray, tr: float, low: float, high: float) -> float:
    """[low, high) 대역의 평균 파워."""
    spectrum = np.fft.rfft(data[:, 0])
    freqs = np.fft.rfftfreq(data.shape[0], d=tr)
    sel = (freqs >= low) & (freqs < high)
    if not sel.any():
        return 0.0
    return float(np.mean(np.abs(spectrum[sel]) ** 2))


def analysis_slice(n_frames: int, tr: float, discarded: int = 2) -> slice:
    """원 acquisition 시각 [12,252) 에 해당하는 frame 구간.

    edge transient 는 이 바깥에 있고, 계획서는 어차피 이 구간만 쓴다.
    """
    start_sec = discarded * tr
    lo = int(np.ceil((12.0 - start_sec) / tr))
    hi = int(np.ceil((252.0 - start_sec) / tr))
    return slice(max(lo, 0), min(hi, n_frames))


def compare(n_frames: int, tr: float, order: int) -> Dict[str, object]:
    """세 처리의 결과를 정답 신호와 비교한다. 채점은 분석 구간 안에서만."""
    observed, design, truth = synth(n_frames, tr)
    keep = analysis_slice(n_frames, tr)

    a = bandpass(regress(observed, design), tr, order=order)

    filtered_design = bandpass(design, tr, order=order)
    filtered_design[:, 0] = 1.0  # intercept 는 필터링하지 않는다
    filtered_signal = bandpass(observed, tr, order=order)
    b = regress(filtered_signal, filtered_design)

    # X — 문헌이 경고하는 순서: 신호만 거르고 원래 regressor 로 회귀
    x = regress(filtered_signal, design)

    reference = bandpass(truth, tr, order=order)

    def score(vec: np.ndarray) -> Dict[str, float]:
        vec = vec[keep]
        ref = reference[keep]
        residual = vec - ref
        return {
            "corr_with_truth": float(np.corrcoef(vec[:, 0], ref[:, 0])[0, 1]),
            "rmse_vs_truth": float(np.sqrt(np.mean(residual ** 2))),
            "residual_rms_pct_of_signal": float(
                100 * np.sqrt(np.mean(residual ** 2)) / np.sqrt(np.mean(ref ** 2))),
            "inband_power": band_power(vec, tr, LOW_HZ, HIGH_HZ),
        }

    return {
        "n_frames": n_frames, "tr": tr, "t_run_sec": n_frames * tr,
        "butter_order": order,
        "scored_frames": [keep.start, keep.stop],
        "A_regress_then_filter": score(a),
        "B_filter_both_then_regress": score(b),
        "X_filter_then_regress_unfiltered": score(x),
        "A_vs_B_max_abs_diff_in_window": float(np.max(np.abs(a[keep] - b[keep]))),
        "A_vs_X_max_abs_diff_in_window": float(np.max(np.abs(a[keep] - x[keep]))),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--orders", type=int, nargs="+", default=[2, 3, 5])
    args = ap.parse_args()

    combos = [("piop1_target", 135, 2.00), ("piop1_wm", 162, 2.00),
              ("piop1_rest", 480, 0.75), ("piop2_rest", 240, 2.00)]
    results = []
    for name, n, tr in combos:
        for order in args.orders:
            entry = compare(n, tr, order)
            entry["combo"] = name
            results.append(entry)

    report = {
        "purpose": "band-pass 와 nuisance 회귀 순서의 영향을 정량화한다. 동결하지 않는다.",
        "protocol_note": "계획서 §3.2 — filter 명세는 pilot 기술 검증에서 기록하고 main 전에 동결",
        "bandpass_hz": [LOW_HZ, HIGH_HZ],
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    print("채점 구간: 원 시각 [12,252) — filtfilt edge 는 이 바깥이다")
    print(f"{'combo':14s} {'TR':>5s} {'ord':>4s} "
          f"{'A resid%':>9s} {'B resid%':>9s} {'X resid%':>9s} "
          f"{'|A-B|':>8s} {'|A-X|':>8s}")
    for r in results:
        a = r["A_regress_then_filter"]
        b = r["B_filter_both_then_regress"]
        x = r["X_filter_then_regress_unfiltered"]
        print(f"{r['combo']:14s} {r['tr']:5.2f} {r['butter_order']:4d} "
              f"{a['residual_rms_pct_of_signal']:9.2f} "
              f"{b['residual_rms_pct_of_signal']:9.2f} "
              f"{x['residual_rms_pct_of_signal']:9.2f} "
              f"{r['A_vs_B_max_abs_diff_in_window']:8.4f} "
              f"{r['A_vs_X_max_abs_diff_in_window']:8.4f}")
    print(f"\n보고서: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
