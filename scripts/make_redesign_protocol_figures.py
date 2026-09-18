"""Figures for the MoBSE redesign protocol (v1.1, 2026-09-17).

이 스크립트는 재설계 프로토콜/작업지침서의 설계를 그림으로 만든다. 모델 성능
결과는 아직 존재하지 않으므로 성능 그림은 만들지 않는다. 그리는 것은
(1) A-D 2x2 요인 설계, (2) 분석 파이프라인과 leakage 경계, (3) 시간축 모형과
기존 파생물 배제 근거, (4) G0 감사 현황이다.

스타일은 `mobse/viz.py`의 `set_nature_style()`(Nature 관례: 7.2 in 2단 폭,
font 8pt, spine top/right 제거, dpi 300)을 그대로 상속하고 `save_multi()`로
PNG/PDF 쌍을 저장한다. 기존 관행 대비 두 가지만 의도적으로 확장한다.
  - `pdf.fonttype = 42` (TrueType): 기존 스크립트에는 설정이 없어 PDF 텍스트가
    편집 불가 형태로 남을 수 있었다. 편집 가능한 벡터 텍스트를 보장한다.
  - manifest에 code/data SHA256과 생성 시각을 기록한다. 기존 manifest에는 해시와
    시각이 없으나, 재설계 프로토콜은 모든 산출물의 hash 추적을 요구한다.

색상은 house palette에서 가져오되 categorical 대비를 검증한 3색만 데이터
식별에 사용한다(#10B981 / #4F46E5 / #F59E0B). 회색 계열은 grid/축/비데이터
상자에만 쓴다. routing 축은 색이 아니라 hatch(빗금)로 구분하고, 모든 표식에
직접 라벨을 붙여 색 단독으로 정보를 전달하지 않는다.

Usage:
    PYTHONPATH=. python3 scripts/make_redesign_protocol_figures.py
    PYTHONPATH=. python3 scripts/make_redesign_protocol_figures.py --only rd3

Figures 는 `docs/experiments/figures_redesign_2026-09-17/` 에 저장된다.
기존 `docs/manuscript_final_2026-03-31/figures/`(2026-03-31 lock)는 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from mobse.viz import save_multi, set_nature_style

# --------------------------------------------------------------------------- #
# 상수
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "experiments" / "figures_redesign_2026-09-17"
PROTOCOL_DOC = "docs/experiments/mobse_redesign_protocol_2026-09-17.md"
INSTRUCTIONS_DOC = "docs/experiments/mobse_redesign_work_instructions_2026-09-17.md"
AUDIT_RELEASE = "results/redesign_v1/20260917_3c458d507e82_nocfg"

# 검증된 categorical 3색 (dataviz validator: lightness/chroma/CVD/normal-vision PASS,
# contrast WARN 은 모든 표식에 직접 라벨을 붙여 해소).
C_BRAIN = "#10B981"   # training-rest brain bank / 제안 구성
C_NULL = "#4F46E5"    # joint ROI-permuted null bank / legacy 조건
C_MARK = "#F59E0B"    # primary contrast 강조

# status / chrome (데이터 식별에 쓰지 않음)
C_BLOCK = "#EF4444"
C_INK = "#1F2937"
C_INK2 = "#4B5563"
C_INK3 = "#6B7280"
C_GRID = "#E5E7EB"
C_CANVAS = "#F9FAFB"
C_CHROME = "#9CA3AF"

HATCH_FIXED = "///"   # routing = 입력 비의존 fixed mixture
HATCH_NONE = None     # routing = FC 입력 의존 dynamic gate

# Wave 1(h197, 2026-09-17) 에서 확정된 run 수·native TR.
# 출처: aomic_wave1/wave1_audit/wave1_summary.json — 각 task 내 TR·volume 분산 0.
# native TR 은 raw sidecar 의 RepetitionTime 이며, run 수는 fMRIPrep confounds 기준.
# (label, n_runs, n_volumes, measured_tr)
RUN_ROWS = [
    ("PIOP1 emomatching  (primary target)", 208, 135, 2.00),
    ("PIOP1 workingmemory  (primary target)", 207, 162, 2.00),
    ("PIOP1 restingstate  (bank source)", 210, 480, 0.75),
    ("PIOP2 emomatching  (external)", 222, 135, 2.00),
    ("PIOP2 workingmemory  (external)", 224, 160, 2.00),
    ("PIOP2 restingstate  (external bank)", 224, 240, 2.00),
]

TR_DOCUMENTED = 2.0   # 계획서 D1 인용값
TR_LEGACY = 0.75      # scripts/stream_aomic_extract.py:485 기본값 (실측 확인)
ANALYSIS_START = 12.0
ANALYSIS_END = 252.0
WINDOW_STARTS = (12.0, 72.0, 132.0, 192.0)
WINDOW_LEN = 60.0
TARGET_GRID = 2.0


# --------------------------------------------------------------------------- #
# 공통 유틸
# --------------------------------------------------------------------------- #


def sha256_file(path: Path) -> Optional[str]:
    """파일의 SHA256 hex digest. 파일이 없으면 None."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe_source(path: Path) -> Dict[str, object]:
    """source 항목을 검증 가능한 형태로 기술한다.

    파일이면 SHA256, 디렉터리면 파일 수와 (상대경로, 바이트) 목록의 SHA256을
    기록한다. 존재하지 않으면 kind="missing".
    """
    if path.is_file():
        return {"kind": "file", "sha256": sha256_file(path)}
    if path.is_dir():
        entries = sorted(
            (q.relative_to(path).as_posix(), q.stat().st_size)
            for q in path.rglob("*") if q.is_file()
        )
        blob = "\n".join(f"{name}\t{size}" for name, size in entries)
        return {
            "kind": "directory",
            "n_files": len(entries),
            "listing_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        }
    return {"kind": "missing"}


def git_head(repo_root: Path) -> Optional[str]:
    """현재 git HEAD commit. 확인 불가 시 None."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=20, check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout.strip() or None


def apply_style() -> None:
    """house style + 이 스크립트의 의도적 확장을 적용."""
    set_nature_style()
    plt.rcParams.update({
        "pdf.fonttype": 42,   # 편집 가능한 TrueType 텍스트 (기존 스크립트 미설정)
        "ps.fonttype": 42,
    })


def panel_label(fig: plt.Figure, x: float, y: float, letter: str) -> None:
    """패널 라벨을 하나의 방식으로 통일한다(figure 좌표, bold 10pt)."""
    fig.text(x, y, letter, fontsize=10, fontweight="bold", color=C_INK,
             ha="left", va="top")


def blank_axes(ax: plt.Axes, xlim: Tuple[float, float] = (0, 1),
               ylim: Tuple[float, float] = (0, 1)) -> plt.Axes:
    """스키매틱용 좌표축 제거."""
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return ax


def rounded_box(ax: plt.Axes, x: float, y: float, w: float, h: float,
                label: str, *, facecolor: str = "white",
                edgecolor: str = C_INK3, hatch: Optional[str] = None,
                fontsize: float = 7.0, fontweight: str = "normal",
                textcolor: str = C_INK, lw: float = 0.7,
                alpha: float = 1.0, pad: float = 0.012) -> FancyBboxPatch:
    """라운드 사각형 + 중앙 라벨. 좌표는 axes 데이터 좌표."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad={pad},rounding_size=0.015",
        facecolor=facecolor, edgecolor=edgecolor, linewidth=lw,
        hatch=hatch, alpha=alpha, zorder=2,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fontsize, fontweight=fontweight, color=textcolor,
            zorder=3, linespacing=1.35)
    return box


def arrow(ax: plt.Axes, start: Tuple[float, float], end: Tuple[float, float],
          *, color: str = C_INK3, lw: float = 0.8, style: str = "-",
          mutation: float = 7.0, connection: str = "arc3,rad=0.0",
          zorder: int = 1) -> None:
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=mutation,
        linewidth=lw, linestyle=style, color=color,
        connectionstyle=connection, shrinkA=1.5, shrinkB=1.5, zorder=zorder,
    ))


# --------------------------------------------------------------------------- #
# RD1 — 2x2 요인 설계와 주 대조
# --------------------------------------------------------------------------- #


def figure_rd1() -> plt.Figure:
    """A-D 2x2 요인 설계(panel a)와 공통 forward 경로(panel b)."""
    fig = plt.figure(figsize=(7.2, 4.05))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.02], wspace=0.13,
                          left=0.035, right=0.985, top=0.885, bottom=0.095)

    # ---------------- panel a : 2x2 cells ---------------- #
    ax = blank_axes(fig.add_subplot(gs[0, 0]))
    ax.text(0.0, 1.035, "a  Factorial design: bank alignment \u00d7 routing",
            fontsize=8, fontweight="bold", color=C_INK, ha="left", va="bottom",
            transform=ax.transAxes)

    cell_w, cell_h = 0.300, 0.230
    col_x = (0.290, 0.670)          # column gap = 0.080
    row_y = (0.595, 0.275)          # row gap    = 0.090

    cells = [
        (0, 0, "A", C_BRAIN, HATCH_NONE, "training-rest bank\n+ FC-dependent gate"),
        (0, 1, "B", C_BRAIN, HATCH_FIXED, "training-rest bank\n+ fixed mixture"),
        (1, 0, "C", C_NULL, HATCH_NONE, "ROI-permuted null\n+ FC-dependent gate"),
        (1, 1, "D", C_NULL, HATCH_FIXED, "ROI-permuted null\n+ fixed mixture"),
    ]
    for r, c, cid, color, hatch, desc in cells:
        x, y = col_x[c], row_y[r]
        rounded_box(ax, x, y, cell_w, cell_h, "", facecolor=color,
                    edgecolor=color, hatch=hatch, alpha=0.18, lw=1.0)
        ax.text(x + cell_w / 2, y + cell_h - 0.056, cid, fontsize=11,
                fontweight="bold", color=color, ha="center", va="center")
        ax.text(x + cell_w / 2, y + 0.068, desc, fontsize=6.0, color=C_INK2,
                ha="center", va="center", linespacing=1.4)

    # 축 라벨
    for c, lab in ((0, "FC-dependent\n(dynamic gate)"),
                   (1, "input-independent\n(fixed mixture)")):
        ax.text(col_x[c] + cell_w / 2, row_y[0] + cell_h + 0.062, lab,
                fontsize=6.6, color=C_INK, ha="center", va="center",
                linespacing=1.3)
    ax.text((col_x[0] + col_x[1] + cell_w) / 2, row_y[0] + cell_h + 0.142,
            "Routing", fontsize=7.2, fontweight="bold", color=C_INK,
            ha="center", va="center")

    for r, lab in ((0, "training-rest\nbrain bank"),
                   (1, "joint ROI-permuted\nnull bank")):
        ax.text(col_x[0] - 0.030, row_y[r] + cell_h / 2, lab, fontsize=6.6,
                color=C_INK, ha="right", va="center", linespacing=1.3)
    ax.text(0.022, (row_y[0] + row_y[1] + cell_h) / 2, "Graph bank",
            fontsize=7.2, fontweight="bold", color=C_INK, ha="center",
            va="center", rotation=90)

    # 주 대조: 셀 사이 여백에만 그린다 (셀 위로 겹치지 않음)
    gap_x = (col_x[0] + cell_w + col_x[1]) / 2
    ax.annotate("", xy=(col_x[1] - 0.006, row_y[0] + cell_h / 2),
                xytext=(col_x[0] + cell_w + 0.006, row_y[0] + cell_h / 2),
                arrowprops=dict(arrowstyle="<|-|>", color=C_MARK, lw=1.2,
                                mutation_scale=7))
    ax.text(gap_x, row_y[0] + cell_h / 2 + 0.036, "H1", fontsize=7.0,
            fontweight="bold", color=C_MARK, ha="center", va="center")

    gap_y = (row_y[1] + cell_h + row_y[0]) / 2
    ax.annotate("", xy=(col_x[0] + cell_w / 2, row_y[1] + cell_h + 0.006),
                xytext=(col_x[0] + cell_w / 2, row_y[0] - 0.006),
                arrowprops=dict(arrowstyle="<|-|>", color=C_MARK, lw=1.2,
                                mutation_scale=7))
    ax.text(col_x[0] + cell_w / 2 - 0.032, gap_y, "H2", fontsize=7.0,
            fontweight="bold", color=C_MARK, ha="right", va="center")

    # 대조 정의는 그리드 밖 텍스트 블록으로
    ax.text(0.022, 0.212,
            "H1   A \u2212 B > 0      gain from FC-dependent routing",
            fontsize=6.4, color=C_INK, ha="left", va="center")
    ax.text(0.022, 0.155,
            "H2   A \u2212 C > 0      gain from an anatomically aligned bank",
            fontsize=6.4, color=C_INK, ha="left", va="center")
    ax.text(0.022, 0.098,
            "secondary   (A\u2212B) \u2212 (C\u2212D)      interaction",
            fontsize=6.4, color=C_INK3, ha="left", va="center")
    ax.text(0.022, 0.041,
            "\u03b4 = 0.02 balanced accuracy; decision from the paired-bootstrap CI "
            "lower bound",
            fontsize=6.0, color=C_INK3, ha="left", va="center")

    handles = [
        mpatches.Patch(facecolor=C_BRAIN, alpha=0.18, edgecolor=C_BRAIN,
                       label="training-rest brain bank"),
        mpatches.Patch(facecolor=C_NULL, alpha=0.18, edgecolor=C_NULL,
                       label="ROI-permuted null bank"),
        mpatches.Patch(facecolor="white", edgecolor=C_INK3, hatch=HATCH_FIXED,
                       label="fixed mixture (hatched)"),
    ]
    ax.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
              fontsize=6.0, bbox_to_anchor=(0.5, -0.012), handlelength=1.3,
              columnspacing=1.2, handletextpad=0.45)

    # ---------------- panel b : forward path ---------------- #
    ax2 = blank_axes(fig.add_subplot(gs[0, 1]))
    ax2.text(0.0, 1.035, "b  Shared forward path (common to A\u2013D)", fontsize=8,
             fontweight="bold", color=C_INK, ha="left", va="bottom",
             transform=ax2.transAxes)

    rounded_box(ax2, 0.175, 0.870, 0.480, 0.092,
                "BOLD window   [30 samples \u00d7 100 ROI]", facecolor=C_CANVAS,
                edgecolor=C_CHROME, fontsize=6.3)

    rounded_box(ax2, 0.030, 0.650, 0.420, 0.125,
                "Shared ROI encoder\nConv1d 1\u219216\u219232, mean\u2016std\nLinear 64\u219232",
                facecolor="white", edgecolor=C_INK3, fontsize=6.0)
    rounded_box(ax2, 0.550, 0.650, 0.420, 0.125,
                "shrinkage FC \u2192 Fisher-z\nfrozen scaler / PCA-10",
                facecolor="white", edgecolor=C_INK3, fontsize=6.0)
    arrow(ax2, (0.330, 0.868), (0.240, 0.777), connection="arc3,rad=0.12")
    arrow(ax2, (0.500, 0.868), (0.760, 0.777), connection="arc3,rad=-0.12")

    rounded_box(ax2, 0.550, 0.435, 0.420, 0.130,
                "Gate\ndynamic: PCA10\u219232\u21923\u2192softmax\nfixed: 3 learned logits",
                facecolor=C_MARK, edgecolor=C_MARK, alpha=0.18, fontsize=6.0)
    arrow(ax2, (0.760, 0.650), (0.760, 0.567))

    rounded_box(ax2, 0.030, 0.435, 0.420, 0.130,
                "Frozen bank  S\u2081 S\u2082 S\u2083\n(excluded from optimizer)",
                facecolor=C_BRAIN, edgecolor=C_BRAIN, alpha=0.18, fontsize=6.2)
    arrow(ax2, (0.240, 0.650), (0.240, 0.567))

    rounded_box(ax2, 0.140, 0.262, 0.720, 0.098,
                "S(x) = \u03a3\u2096 \u03c0\u2096(x) \u00b7 S\u2096      (no renormalisation)",
                facecolor=C_CANVAS, edgecolor=C_INK3, fontsize=6.6)
    arrow(ax2, (0.240, 0.435), (0.370, 0.362))
    arrow(ax2, (0.760, 0.435), (0.630, 0.362))

    rounded_box(ax2, 0.140, 0.098, 0.720, 0.098,
                "graph layer \u00d72  \u2192  ROI mean pool  \u2192  Linear(32\u21922)",
                facecolor="white", edgecolor=C_INK3, fontsize=6.3)
    arrow(ax2, (0.500, 0.262), (0.500, 0.198))

    ax2.text(0.500, 0.030,
             "B and D compute FC but never route it into prediction",
             fontsize=6.0, color=C_INK3, ha="center", va="center")
    return fig


# --------------------------------------------------------------------------- #
# RD2 — 분석 파이프라인과 fit 경계
# --------------------------------------------------------------------------- #


def figure_rd2() -> plt.Figure:
    """G0-G5 파이프라인(panel a)과 fold 내부 fit 경계(panel b)."""
    fig = plt.figure(figsize=(7.2, 5.0))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.82, 1.18], hspace=0.26,
                          left=0.030, right=0.988, top=0.925, bottom=0.045)

    # ---------------- panel a : gate 흐름 ---------------- #
    ax = blank_axes(fig.add_subplot(gs[0, 0]))
    ax.text(0.0, 1.015, "a  From runs to conclusions \u2014 required artefact per gate",
            fontsize=8, fontweight="bold", color=C_INK, ha="left", va="bottom",
            transform=ax.transAxes)

    stages = [
        ("G0\nProvenance", "source_runs\ntiming audit", C_BLOCK, "blocked"),
        ("G1\nMeasurement", "QC \u00b7 pilot\nfolds.json", C_CHROME, "planned"),
        ("G2\nImplementation", "T01\u2013T16\nCLI lock", C_CHROME, "planned"),
        ("G3\nInternal", "480+60 fits\nOOF \u00b7 CI", C_CHROME, "planned"),
        ("G4\nExternal", "PIOP2\n96+12 fits", C_CHROME, "planned"),
        ("G5\nInterpretation", "claim\u2013evidence\nrepro package", C_CHROME, "planned"),
    ]
    n = len(stages)
    bw, gap = 0.140, 0.0232
    x0 = 0.010
    top, height = 0.560, 0.360
    for i, (title, payload, color, status) in enumerate(stages):
        x = x0 + i * (bw + gap)
        rounded_box(ax, x, top, bw, height, "", facecolor=color,
                    edgecolor=color, alpha=0.14, lw=1.0)
        ax.text(x + bw / 2, top + height - 0.082, title, fontsize=6.8,
                fontweight="bold", color=C_INK, ha="center", va="center",
                linespacing=1.3)
        ax.text(x + bw / 2, top + 0.098, payload, fontsize=6.0, color=C_INK2,
                ha="center", va="center", linespacing=1.4)
        ax.text(x + bw / 2, top - 0.075, status, fontsize=6.2,
                fontweight="bold" if status == "blocked" else "normal",
                color=C_BLOCK if status == "blocked" else C_INK3,
                ha="center", va="center")
        if i < n - 1:
            arrow(ax, (x + bw + 0.002, top + height / 2),
                  (x + bw + gap - 0.002, top + height / 2),
                  color=C_INK3, lw=0.8, mutation=6)

    ax.text(x0, 0.300,
            "Current state: G0 blocked \u2014 no AOMIC source BOLD, sidecar JSON, "
            "confounds or events found locally (WI-01, measured).",
            fontsize=6.3, color=C_INK2, ha="left", va="center")
    ax.text(x0, 0.185,
            "No model sweep starts before G0 is resolved.",
            fontsize=6.3, color=C_INK2, ha="left", va="center")
    ax.text(x0, 0.055,
            "Significance is not an execution gate: with data and design locked, "
            "external validation proceeds even if internal results are negative.",
            fontsize=6.3, color=C_INK3, ha="left", va="center", style="italic")

    # ---------------- panel b : fit scope ---------------- #
    ax2 = blank_axes(fig.add_subplot(gs[1, 0]))
    ax2.text(0.0, 1.015,
             "b  Fit boundary inside a fold \u2014 which subjects each component is fitted on",
             fontsize=8, fontweight="bold", color=C_INK, ha="left", va="bottom",
             transform=ax2.transAxes)

    # 왼쪽: subject pool
    rounded_box(ax2, 0.010, 0.775, 0.210, 0.135,
                "QC-eligible subjects\n(grouped by group_id)", facecolor=C_CANVAS,
                edgecolor=C_CHROME, fontsize=6.2)
    rounded_box(ax2, 0.010, 0.565, 0.210, 0.135,
                "pilot  min(32, \u230a0.2N\u230b)\nexcluded from every main and final fit",
                facecolor=C_BLOCK, edgecolor=C_BLOCK, alpha=0.13, fontsize=5.8)
    rounded_box(ax2, 0.010, 0.355, 0.210, 0.135,
                "main pool\nouter 5-fold \u00d7 inner 3-fold",
                facecolor="white", edgecolor=C_INK3, fontsize=6.2)
    arrow(ax2, (0.115, 0.775), (0.115, 0.702), color=C_INK3, lw=0.8, mutation=6)
    arrow(ax2, (0.115, 0.565), (0.115, 0.492), color=C_INK3, lw=0.8, mutation=6)

    # 가운데: fit scope
    fit_x, fit_w = 0.268, 0.455
    ax2.add_patch(FancyBboxPatch(
        (fit_x, 0.300), fit_w, 0.590,
        boxstyle="round,pad=0.010,rounding_size=0.02",
        facecolor=C_BRAIN, edgecolor=C_BRAIN, alpha=0.09, linewidth=1.1,
        linestyle=(0, (4, 2)), zorder=1,
    ))
    ax2.text(fit_x + fit_w / 2, 0.945,
             "fit scope = training subjects of this fold only",
             fontsize=6.5, fontweight="bold", color=C_BRAIN, ha="center",
             va="center")

    steps = [
        "training-rest windows (4 / subject)",
        "Ledoit\u2013Wolf FC \u2192 Fisher-z (4,950)",
        "StandardScaler + PCA-10  (rest only)",
        "K-means K=3 \u2192 raw correlation centroid",
        "top 20% positive edges \u2192 normalised S\u2096",
    ]
    sy, step, bh = 0.800, 0.115, 0.068
    for i, txt in enumerate(steps):
        y = sy - i * step
        rounded_box(ax2, fit_x + 0.016, y, fit_w - 0.032, bh, txt,
                    facecolor="white", edgecolor=C_INK3, fontsize=5.9,
                    lw=0.6, pad=0.005)
        if i < len(steps) - 1:
            arrow(ax2, (fit_x + fit_w / 2, y), (fit_x + fit_w / 2, y - 0.040),
                  color=C_INK3, lw=0.7, mutation=5)

    arrow(ax2, (0.222, 0.423), (fit_x + 0.012, 0.560), color=C_BRAIN, lw=1.0,
          mutation=7, connection="arc3,rad=-0.12")

    # 오른쪽: 평가 단위
    ev_x, ev_w = 0.762, 0.226
    rounded_box(ax2, ev_x, 0.760, ev_w, 0.145,
                "one config shared by A\u2013D\njoint 8-grid selection \u00b7 common E",
                facecolor=C_MARK, edgecolor=C_MARK, alpha=0.16, fontsize=5.9)
    rounded_box(ax2, ev_x, 0.545, ev_w, 0.145,
                "run probability\nmean over 4 windows \u00d7 3 seeds",
                facecolor="white", edgecolor=C_INK3, fontsize=5.9)
    rounded_box(ax2, ev_x, 0.300, ev_w, 0.175,
                "paired bootstrap\n10,000 \u00d7 group resampling\n97.5% CI (family-wise)",
                facecolor="white", edgecolor=C_INK3, fontsize=5.9)
    arrow(ax2, (ev_x + ev_w / 2, 0.760), (ev_x + ev_w / 2, 0.697), color=C_INK3,
          lw=0.8, mutation=6)
    arrow(ax2, (ev_x + ev_w / 2, 0.545), (ev_x + ev_w / 2, 0.482), color=C_INK3,
          lw=0.8, mutation=6)
    arrow(ax2, (fit_x + fit_w + 0.012, 0.620), (ev_x - 0.008, 0.820),
          color=C_INK3, lw=0.8, mutation=6, connection="arc3,rad=-0.18")

    ax2.text(0.010, 0.175,
             "Rest scans of pilot, outer-test and inner-validation subjects never "
             "enter the scaler / PCA / K-means / bank fit; validation transforms never refit.",
             fontsize=6.2, color=C_INK2, ha="left", va="center")
    ax2.text(0.010, 0.065,
             "The statistical unit is the subject; window, seed and fold counts are "
             "never counted as N.",
             fontsize=6.2, color=C_INK3, ha="left", va="center")
    return fig


# --------------------------------------------------------------------------- #
# RD3 — 시간축 모형과 기존 파생물 배제 근거
# --------------------------------------------------------------------------- #


def figure_rd3() -> plt.Figure:
    """[12,252)초 window 규칙(a)과 확정된 native TR vs 기존 추출 가정(b)."""
    fig = plt.figure(figsize=(7.2, 4.7))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.62, 1.0], hspace=0.48,
                          left=0.052, right=0.985, top=0.910, bottom=0.140)

    # ---------------- panel a : window 배치 ---------------- #
    ax = fig.add_subplot(gs[0, 0])
    ax.set_xlim(-8, 340)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([0, 12, 72, 132, 192, 252, 324])
    ax.set_xlabel("Original acquisition clock (s)", fontsize=7.0)
    ax.tick_params(axis="x", labelsize=6.4, colors=C_INK2)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C_CHROME)
    ax.set_title("a  Fixed-window rule \u2014 selected on the original acquisition clock",
                 fontsize=8, fontweight="bold", color=C_INK, loc="left", pad=6)

    ax.axhspan(0.30, 0.66, xmin=0.0, xmax=1.0, color=C_CANVAS, zorder=0)
    ax.add_patch(mpatches.Rectangle((0, 0.30), 12, 0.36, facecolor=C_BLOCK,
                                    alpha=0.16, edgecolor="none", zorder=1))
    ax.text(6, 0.755, "guard\n0\u201312 s", fontsize=5.9, color=C_BLOCK,
            ha="center", va="center", linespacing=1.3)

    for i, st in enumerate(WINDOW_STARTS):
        ax.add_patch(mpatches.Rectangle(
            (st + 1.0, 0.32), WINDOW_LEN - 2.0, 0.32, facecolor=C_BRAIN,
            alpha=0.24, edgecolor=C_BRAIN, linewidth=0.8, zorder=2))
        ax.text(st + WINDOW_LEN / 2, 0.48, f"W{i + 1}\n30 samples",
                fontsize=6.0, color=C_INK, ha="center", va="center",
                linespacing=1.3, zorder=3)

    ax.annotate("", xy=(ANALYSIS_START, 0.855), xytext=(ANALYSIS_END, 0.855),
                arrowprops=dict(arrowstyle="<|-|>", color=C_MARK, lw=1.0,
                                mutation_scale=7))
    ax.text((ANALYSIS_START + ANALYSIS_END) / 2, 0.905,
            "Primary analysis interval  [12, 252) s  =  240 s  =  120 samples @ 2 s grid",
            fontsize=6.6, fontweight="bold", color=C_MARK, ha="center",
            va="bottom")

    ax.plot([ANALYSIS_END, ANALYSIS_END], [0.24, 0.70], color=C_MARK, lw=0.9,
            linestyle=(0, (3, 2)), zorder=4)
    ax.text(258, 0.46,
            "Supported by all six\ndataset \u00d7 task combinations\n(panel b)",
            fontsize=5.9, color=C_INK2, ha="left", va="center", linespacing=1.4)
    ax.text(-6, 0.13,
            "Nuisance regression and filtering run at native TR, then resampling to the 2 s grid. "
            "The 12 s guard is not re-applied at the derivative start point.",
            fontsize=6.1, color=C_INK3, ha="left", va="center")

    # ---------------- panel b : 확정 TR vs 기존 추출 가정 ---------------- #
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_title("b  Native TR confirmed \u2014 and what the existing extraction assumed instead",
                  fontsize=8, fontweight="bold", color=C_INK, loc="left", pad=6)

    ypos = list(range(len(RUN_ROWS)))[::-1]
    h = 0.30
    off = h / 2 + 0.02

    for y, (label, n_runs, vol, tr) in zip(ypos, RUN_ROWS):
        true_dur = vol * tr
        legacy_dur = vol * TR_LEGACY
        matches = abs(tr - TR_LEGACY) < 1e-9
        if matches:
            ax2.barh([y], [true_dur], height=h, color=C_BRAIN,
                     edgecolor="white", linewidth=0.8)
            ax2.text(true_dur + 10, y,
                     f"{true_dur:g} s   TR = {tr:g} s   (extraction happened to match)",
                     fontsize=5.9, color=C_INK2, va="center", ha="left")
        else:
            ax2.barh([y + off], [true_dur], height=h, color=C_BRAIN,
                     edgecolor="white", linewidth=0.8)
            ax2.barh([y - off], [legacy_dur], height=h, color=C_NULL,
                     edgecolor="white", linewidth=0.8, hatch=HATCH_FIXED,
                     alpha=0.55)
            ax2.text(true_dur + 10, y + off, f"{true_dur:g} s   TR = {tr:g} s",
                     fontsize=6.0, color=C_INK2, va="center", ha="left")
            ax2.text(legacy_dur + 10, y - off,
                     f"{legacy_dur:g} s   as extracted at TR = {TR_LEGACY:g} s",
                     fontsize=6.0, color=C_BLOCK, va="center", ha="left")

    ax2.axvline(ANALYSIS_END, color=C_BLOCK, lw=1.0, linestyle=(0, (4, 2)),
                zorder=5)
    ax2.text(ANALYSIS_END + 8, len(RUN_ROWS) - 0.28,
             f"required {ANALYSIS_END:g} s", fontsize=6.2, color=C_BLOCK,
             ha="left", va="center", fontweight="bold")

    ax2.set_yticks(ypos)
    ax2.set_yticklabels([f"{lab}\n{n} runs \u00b7 {vol} volumes"
                         for lab, n, vol, _tr in RUN_ROWS],
                        fontsize=5.8, linespacing=1.45)
    ax2.set_ylim(-0.62, len(RUN_ROWS) - 0.38)
    ax2.set_xlabel("Scan length (s)", fontsize=7.0)
    ax2.set_xlim(0, 760)
    ax2.tick_params(axis="both", labelsize=6.4, colors=C_INK2)
    for side in ("top", "right", "left"):
        ax2.spines[side].set_visible(False)
    ax2.spines["bottom"].set_color(C_CHROME)
    ax2.grid(axis="x", color=C_GRID, linestyle="--", linewidth=0.5, alpha=0.7)
    ax2.set_axisbelow(True)

    handles = [
        mpatches.Patch(facecolor=C_BRAIN, label="native TR (raw sidecar, Wave 1)"),
        mpatches.Patch(facecolor=C_NULL, alpha=0.55, hatch=HATCH_FIXED,
                       label="what the existing extraction assumed (TR = 0.75 s)"),
    ]
    ax2.legend(handles=handles, loc="upper right", frameon=False, fontsize=6.0,
               handlelength=1.5, handletextpad=0.5, labelspacing=0.5,
               bbox_to_anchor=(1.0, 1.02))

    ax2.text(0.0, -0.245,
             "Every combination clears the 252 s requirement at its native TR, so the "
             "[12, 252) s window design holds without revision.",
             fontsize=6.1, color=C_INK3, ha="left", va="top",
             transform=ax2.transAxes)
    ax2.text(0.0, -0.345,
             "The existing extraction applied TR = 0.75 s to every run. It is correct only for "
             "PIOP1 restingstate; both primary targets were filtered at 2.67\u00d7 the wrong rate.",
             fontsize=6.1, color=C_INK3, ha="left", va="top",
             transform=ax2.transAxes)
    return fig


# --------------------------------------------------------------------------- #
# RD4 — G0 감사 현황
# --------------------------------------------------------------------------- #


def figure_rd4() -> plt.Figure:
    """Wave 1 이후의 cohort 규모(a)와 G0 차단 항목 해소 현황(b)."""
    fig = plt.figure(figsize=(7.2, 3.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.30], wspace=0.24,
                          left=0.170, right=0.988, top=0.865, bottom=0.140)

    # ---------------- panel a : run inventory ---------------- #
    ax = fig.add_subplot(gs[0, 0])
    ax.set_title("a  Runs available after Wave 1", fontsize=8,
                 fontweight="bold", color=C_INK, loc="left", pad=6)

    ypos = list(range(len(RUN_ROWS)))[::-1]
    colors = [C_BRAIN if lab.startswith("PIOP1") else C_NULL
              for lab, _n, _v, _t in RUN_ROWS]
    hatches = [None if lab.startswith("PIOP1") else HATCH_FIXED
               for lab, _n, _v, _t in RUN_ROWS]
    counts = [n for _l, n, _v, _t in RUN_ROWS]

    bars = ax.barh(ypos, counts, height=0.55, color=colors, edgecolor="white",
                   linewidth=0.8)
    for bar, hatch, n in zip(bars, hatches, counts):
        bar.set_hatch(hatch)
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                f"{n}", fontsize=6.2, color=C_INK2, va="center", ha="left")

    ax.set_yticks(ypos)
    ax.set_yticklabels([lab.split("  (")[0] for lab, _n, _v, _t in RUN_ROWS],
                       fontsize=6.2)
    ax.set_xlabel("runs with fMRIPrep confounds", fontsize=7.0)
    ax.set_xlim(0, 270)
    ax.tick_params(axis="both", labelsize=6.4, colors=C_INK2)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C_CHROME)
    ax.grid(axis="x", color=C_GRID, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    # 각 막대의 y 라벨이 이미 dataset 을 직접 명시하므로 별도 legend 를 두지 않는다
    # (색 단독으로 정보를 전달하지 않는다는 규칙은 직접 라벨로 이미 충족).
    ax.text(0.0, -0.215,
            "PIOP2 carries a full emomatching cohort, so the external replication "
            "is no longer unprepared.",
            fontsize=5.9, color=C_INK3, ha="left", va="top", transform=ax.transAxes)

    # ---------------- panel b : 차단 항목 해소 현황 ---------------- #
    ax2 = blank_axes(fig.add_subplot(gs[0, 1]))
    ax2.set_title("b  G0 blockers after Wave 1", fontsize=8,
                  fontweight="bold", color=C_INK, loc="left", pad=6)

    rows = [
        ("U1", "native TR of both targets", True, "2.0 s, zero variance"),
        ("U2", "discarded volumes", True, "non_steady_state cols"),
        ("U4", "24 motion / aCompCor / FD", True, "4 runs to exclude"),
        ("U5", "events onset origin", True, "all task runs"),
        ("U11", "PIOP2 paired target", True, "222 emo runs"),
        ("U13", "execution interpreter", True, "h197 venv locked"),
        ("U14", "torch / scipy / sklearn", True, "torch 2.10 + CUDA 12.8"),
        ("U15", "OpenNeuro egress", True, "6,055 files fetched"),
        ("U3", "dummy volumes before archiving", False, "not determinable"),
        ("U6", "BOLD for the targets", False, "Wave 2"),
        ("U10", "family / duplicate metadata", False, "no column exists"),
        ("U26", "Wave 2 download volume", False, "probe pending"),
    ]
    y = 0.945
    step = 0.0785
    for code, desc, done, note in rows:
        col = C_BRAIN if done else C_BLOCK
        mark = "\u2713" if done else "\u2022"
        ax2.add_patch(mpatches.Rectangle((0.004, y - 0.029), 0.052, 0.058,
                                         facecolor=col, alpha=0.16,
                                         edgecolor="none"))
        ax2.text(0.030, y, code, fontsize=5.8, fontweight="bold", color=col,
                 ha="center", va="center")
        ax2.text(0.072, y, mark, fontsize=6.4, fontweight="bold", color=col,
                 ha="center", va="center")
        ax2.text(0.098, y, desc, fontsize=5.8, color=C_INK, ha="left",
                 va="center")
        ax2.text(0.996, y, note, fontsize=5.6, color=C_INK3, ha="right",
                 va="center")
        y -= step

    ax2.text(0.004, 0.022,
             "\u2713 resolved by Wave 1   \u2022 still open. "
             "U9 and U12 are retired by re-extraction; U17 by the dataset-prefixed subject key.",
             fontsize=5.6, color=C_INK3, ha="left", va="center")
    return fig


# --------------------------------------------------------------------------- #
# 산출물 기록
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FigureSpec:
    key: str
    slug: str
    builder: Callable[[], plt.Figure]
    caption: str
    role: str
    sources: Sequence[str]


FIGURES: Tuple[FigureSpec, ...] = (
    FigureSpec(
        key="rd1",
        slug="fig_rd1_factorial_design",
        builder=figure_rd1,
        role="manuscript",
        caption=(
            "RD1. 재설계의 2×2 요인 설계와 공통 forward 경로. (a) graph bank "
            "(training-rest brain vs joint ROI-permuted null)와 routing "
            "(FC 입력 의존 dynamic gate vs 입력 비의존 fixed mixture)의 교차로 "
            "A–D 네 cell을 정의한다. 주가설은 H1 (A−B>0, 입력 의존 routing의 이득)과 "
            "H2 (A−C>0, 정렬된 brain bank의 이득)이며 상호작용은 보조 분석이다. "
            "(b) 네 cell이 공유하는 forward 경로: ROI 공유 encoder, frozen bank, "
            "혼합 후 재정규화 없는 S(x), graph layer 2개와 분류 head."
        ),
        sources=(PROTOCOL_DOC,),
    ),
    FigureSpec(
        key="rd2",
        slug="fig_rd2_analysis_pipeline",
        builder=figure_rd2,
        role="manuscript",
        caption=(
            "RD2. 분석 파이프라인과 fit 경계. (a) G0–G5 gate별 필수 산출물과 현재 상태 — "
            "G0는 로컬 원본 부재로 blocked이며 이후 gate는 planned다. "
            "(b) fold 내부에서 scaler·PCA·K-means·bank가 오직 해당 fold의 training-rest로만 "
            "fit되고 pilot·outer test·inner validation은 모든 fit에서 제외됨을 보인다. "
            "통계 단위는 subject이며 window·seed·fold 수를 N으로 세지 않는다."
        ),
        sources=(PROTOCOL_DOC, INSTRUCTIONS_DOC),
    ),
    FigureSpec(
        key="rd3",
        slug="fig_rd3_timing_model",
        builder=figure_rd3,
        role="manuscript",
        caption=(
            "RD3. 시간축 모형과 확정된 native TR. (a) 원본 acquisition clock에서 12초 guard 이후 "
            "[12,252)초를 주분석 구간으로 하고 60초 window 4개(각 2초 grid 30 samples)를 고정 배치한다. "
            "(b) Wave 1에서 확보한 raw sidecar의 RepetitionTime으로 여섯 dataset×task 조합의 native TR이 "
            "모두 확정되었다(각 조합 내 분산 0). 두 primary target은 TR 2.0초이며, PIOP1 restingstate만 "
            "0.75초(multiband)다. 모든 조합이 252초 요건을 충족하므로 window 설계는 개정 없이 유지된다. "
            "기존 추출은 모든 run에 TR 0.75초를 적용했고, 이는 PIOP1 restingstate에서만 우연히 옳다 — "
            "두 primary target은 2.67배 잘못된 rate로 필터링되었으므로 해당 파생물은 재사용하지 않는다."
        ),
        sources=(
            PROTOCOL_DOC,
            "scripts/stream_aomic_extract.py",
            "data/aomic/piop1/timeseries/100",
            "data/aomic/piop2/timeseries/100",
            "data/legacy_phase2/os_phase2_openneuro/openneuro/ds002785/2.0.0/uncompressed/"
            "sub-0001/func/sub-0001_task-restingstate_acq-mb3_bold.nii.gz",
            "data/legacy_phase2/os_phase2_openneuro/openneuro/ds002790/2.0.0/uncompressed/"
            "sub-0001/func/sub-0001_task-restingstate_acq-seq_bold.nii.gz",
            f"{AUDIT_RELEASE}/reports/wi00_wi01_execution_report_2026-09-17.md",
        ),
    ),
    FigureSpec(
        key="rd4",
        slug="fig_rd4_g0_audit_status",
        builder=figure_rd4,
        role="audit",
        caption=(
            "RD4. Wave 1 이후의 cohort 규모와 G0 차단 항목 해소 현황. (a) fMRIPrep confounds가 "
            "존재하는 run 수 — PIOP2가 emomatching 222 run을 보유하므로 외부 검증 cohort가 "
            "구성 가능하다. (b) 차단 항목의 해소 여부. U1·U2·U4·U5·U11·U13·U14·U15가 Wave 1으로 "
            "해소되었고, U3(보관 전 dummy 제거 여부)·U6(target BOLD)·U10(가족/중복 metadata)·"
            "U26(Wave 2 용량)이 남는다. 이 그림은 감사 보고용이며 논문 figure가 아니다."
        ),
        sources=(
            f"{AUDIT_RELEASE}/provenance/source_runs.jsonl",
            f"{AUDIT_RELEASE}/provenance/missing_sources.json",
            f"{AUDIT_RELEASE}/reports/timing_audit.md",
            f"{AUDIT_RELEASE}/reports/wi00_wi01_execution_report_2026-09-17.md",
        ),
    ),
)


def write_manifest(spec: FigureSpec, out_dir: Path, created_at: str,
                   head: Optional[str]) -> Path:
    """기존 변형 B 스키마 + hash/시각 확장."""
    png = out_dir / f"{spec.slug}.png"
    pdf = out_dir / f"{spec.slug}.pdf"
    script_rel = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
    manifest = {
        "schema_version": "redesign_fig_manifest_v1",
        "figure_key": spec.key,
        "role": spec.role,
        "script": script_rel,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "figure_png": png.relative_to(REPO_ROOT).as_posix(),
        "figure_pdf": pdf.relative_to(REPO_ROOT).as_posix(),
        "figure_png_sha256": sha256_file(png),
        "figure_pdf_sha256": sha256_file(pdf),
        "sources": [
            {"path": s, **describe_source(REPO_ROOT / s)}
            for s in spec.sources
        ],
        "git_head": head,
        "created_at_utc": created_at,
        "style": {
            "base": "mobse.viz.set_nature_style",
            "extensions": ["pdf.fonttype=42", "ps.fonttype=42"],
            "categorical_palette": [C_BRAIN, C_NULL, C_MARK],
        },
        "notes": (
            "성능 결과를 포함하지 않는 설계·감사 figure. 수치는 계획서 본문과 "
            "WI-01 실측값에서만 가져왔다."
        ),
    }
    path = out_dir / f"figure_manifest_{spec.key}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def write_index(specs: Sequence[FigureSpec], out_dir: Path,
                created_at: str) -> None:
    """README + caption 문서 (기존 figures 폴더 관행과 동일한 3종 중 2종)."""
    readme = [
        "# Redesign protocol figures (2026-09-17)",
        "",
        f"생성 시각(UTC): {created_at}",
        "",
        "이 폴더는 재설계 프로토콜 v1.1 / 작업지침서 v1.0 의 **설계와 감사 현황**을 "
        "그린 figure 만 담는다. 모델 성능 결과는 아직 존재하지 않으므로 성능 figure 는 없다.",
        "",
        "`docs/manuscript_final_2026-03-31/figures/` (2026-03-31 lock) 와 분리된 별도 폴더이며, "
        "기존 `fig_f<N>_` 번호와 충돌하지 않도록 `fig_rd<N>_` 접두사를 쓴다.",
        "",
        "| Key | 파일 | 역할 | 내용 |",
        "|---|---|---|---|",
    ]
    for s in specs:
        first = s.caption.split(". ", 1)[-1].split(" (a)")[0].strip()
        readme.append(f"| {s.key.upper()} | `{s.slug}.{{png,pdf}}` | {s.role} | {first} |")
    readme += [
        "",
        "## 재현",
        "",
        "```bash",
        "PYTHONPATH=. python3 scripts/make_redesign_protocol_figures.py",
        "```",
        "",
        "각 figure 는 `figure_manifest_<key>.json` 에 스크립트/출력/입력 SHA256 과 "
        "git HEAD, 생성 시각을 기록한다. 기존 manifest 에는 hash·시각 필드가 없었으나 "
        "재설계 프로토콜이 모든 산출물의 hash 추적을 요구하므로 확장했다.",
        "",
        "## 스타일",
        "",
        "- `mobse.viz.set_nature_style()` 상속 (7.2 in 2단 폭, 8 pt, dpi 300, top/right spine 제거).",
        "- 저장은 `mobse.viz.save_multi()` 로 PNG/PDF 쌍.",
        "- `pdf.fonttype=42` 추가 — 기존 스크립트에는 설정이 없었다.",
        "- 데이터 식별 색은 검증된 3색만 사용: "
        f"`{C_BRAIN}`(brain bank/proposed), `{C_NULL}`(null bank/legacy), `{C_MARK}`(대조 강조). "
        "routing 축은 색이 아니라 빗금으로 구분하고 모든 표식에 직접 라벨을 붙인다.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")

    caps = ["# Figure captions — redesign protocol (2026-09-17)", ""]
    for s in specs:
        caps.append(f"- **{s.key.upper()}** (`{s.slug}`): {s.caption}")
        caps.append("")
    (out_dir / "figure_captions_redesign.md").write_text(
        "\n".join(caps), encoding="utf-8")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=None,
                        help="생성할 figure key (rd1 rd2 rd3 rd4)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    selected: List[FigureSpec] = [
        s for s in FIGURES if args.only is None or s.key in args.only
    ]
    if not selected:
        raise SystemExit(f"선택된 figure 없음: {args.only}")

    apply_style()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = git_head(REPO_ROOT)

    for spec in selected:
        fig = spec.builder()
        save_multi(out_dir / spec.slug, fig)
        plt.close(fig)
        manifest = write_manifest(spec, out_dir, created_at, head)
        print(f"[ok] {spec.slug}.png/.pdf  →  {manifest.name}")

    write_index(FIGURES, out_dir, created_at)
    print(f"[ok] README.md, figure_captions_redesign.md  →  {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
