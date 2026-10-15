#!/usr/bin/env python3
"""I1 보고서 그림 (모식도 3 · 결과 7) 을 본 실행 산출에서 만든다.

결과 그림 (4–8) 은 run 폴더의 ``analysis/*.json`` · ``diag/collapse_20261012/diag_collapse.json`` ·
``{aomic,abide}/<모델>/orig/k0/r1/f*/d1.json`` 만 읽는다. 읽기 전에 분석 산출의 sha256 을 보고서에
적은 값과 대조하고, 다르면 그림을 만들지 않는다. 그림 9 (2.1 판) 는 ABIDE MoBSE 확장 실행 (결정 59) 의
``analysis/*.json`` (963 명 공통 분석) 만 읽고, 같은 방식으로 sha256 을 대조한다. 그림 10 (2.3 판) 은
ADHD-200 확장 실행 (결정 65) 의 ``analysis/adhd200/*.json`` 만 읽고, 역시 sha256 을 대조한다. 모식도 (1–3) 의 행렬 · 노드 그림은 **개념도**이며 실제 자료가 아니다.

SVG 의 글자는 경로로 넣으므로 (``svg.fonttype = path``) 보는 쪽에 글꼴이 없어도 같게 보인다.

Usage:
    .venv/bin/python scripts/reports/make_i1_figures.py --run-root <run 폴더 또는 그 사본> \
        --abide963-root <확장 run 폴더 또는 그 사본> --adhd-root <ADHD-200 run 폴더 또는 그 사본> \
        --out results/i1/reports/figs
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

EXPECTED_SHA12 = {
    "analysis/aomic/bqn.json": "28b175dce707", "analysis/aomic/bnt.json": "374944e55ec0",
    "analysis/aomic/han.json": "89a07cf9c85e", "analysis/aomic/mobse_mean.json": "15cb501a8925",
    "analysis/aomic/mobse_embedding.json": "6cef00596fea", "analysis/aomic/fc_logistic.json": "715a440d66ad",
    "analysis/aomic/fc_mlp.json": "290cfc3c7923", "analysis/aomic/s1_logistic.json": "de4a051690d9",
    "analysis/abide/bqn.json": "993c1e990e87", "analysis/abide/bnt.json": "79d130c26bfd",
    "analysis/abide/han.json": "ecd9ee51b747", "analysis/abide/fc_logistic.json": "af82d07fe32e",
    "analysis/abide/fc_mlp.json": "883d12adaea3", "analysis/abide/s1_logistic.json": "f06187567f8c",
    "analysis/abide_site/bqn.json": "4fa4f5ca95f8",
    "diag/collapse_20261012/diag_collapse.json": "628d470f5b02",
}
EXPECTED_SHA12_963 = {
    "analysis/mobse_mean.json": "ff640c14bae2", "analysis/mobse_embedding.json": "821cb4bf43c6",
    "analysis/bqn.json": "6cc9e7177f93", "analysis/bnt.json": "4f1c6c739545", "analysis/han.json": "0825cdb89a1f",
}
EXPECTED_SHA12_ADHD = {
    "analysis/adhd200/mobse_mean.json": "5ff5c10d1992", "analysis/adhd200/mobse_embedding.json": "a10050bb6c3e",
    "analysis/adhd200/bqn.json": "f67b639849a9", "analysis/adhd200/bnt.json": "35898d7a9294",
    "analysis/adhd200/han.json": "bc2c6c338872", "analysis/adhd200/fc_logistic.json": "752bc847e3ee",
    "analysis/adhd200/fc_mlp.json": "41ef8c41d573", "analysis/adhd200/s1_logistic.json": "41745c8ca877",
}

BRAND, ACCENT, INK, INK3, LINE, WASH, WARN = "#14416E", "#1F8A8C", "#10151C", "#6B7787", "#D3DBE4", "#F2F5F8", "#B37500"
NULL_COLOR = {"n0": "#9AA5B1", "n1": BRAND, "n2": ACCENT, "n3": WARN}
NULL_NAME = {"n0": "n0 이름표만 바꿈 (점검)", "n1": "n1 무작위로 섞기", "n2": "n2 돌리기 (이웃 유지)", "n3": "n3 연결 상대 바꾸기"}
PUBLIC = (("bqn", "BQN"), ("bnt", "BNT"), ("han", "Han"))
W = 6.7  # 그림 폭 (인치) — A4 본문 폭 약 170 mm


def setup_fonts() -> None:
    """한글 글꼴 (Pretendard) 을 쓰고, 없으면 시스템 고딕으로 둔다."""
    for p in Path.home().glob("Library/Fonts/Pretendard-*.otf"):
        font_manager.fontManager.addfont(str(p))
    names = {f.name for f in font_manager.fontManager.ttflist}
    family = "Pretendard" if "Pretendard" in names else "AppleGothic"
    plt.rcParams.update({
        "font.family": family, "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
        "axes.edgecolor": INK3, "axes.linewidth": .6, "xtick.color": INK3, "ytick.color": INK,
        "xtick.labelsize": 7.5, "ytick.labelsize": 8, "axes.spines.top": False, "axes.spines.right": False,
        "svg.fonttype": "path", "svg.hashsalt": "i1-report", "axes.unicode_minus": False, "figure.dpi": 100,
    })


def sha12(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def load_all(run: Path, expected: Dict[str, str] = EXPECTED_SHA12) -> Dict[str, dict]:
    """sha 를 대조한 뒤 분석 산출을 읽는다."""
    bad = [f"{rel}: {sha12(run / rel)} ≠ {exp}" for rel, exp in expected.items() if sha12(run / rel) != exp]
    if bad:
        raise SystemExit("분석 산출이 보고서의 sha 와 다르다:\n" + "\n".join(bad))
    return {rel: json.loads((run / rel).read_text(encoding="utf-8")) for rel in expected}


def save(fig, out: Path, name: str) -> None:
    fig.savefig(out / name, format="svg", bbox_inches="tight", pad_inches=.04, metadata={"Date": None})
    plt.close(fig)
    print("wrote", out / name)


def box(ax, x, y, w, h, text, fc="white", ec=BRAND, color=INK, size=8, weight="normal", lw=1.0):
    patch = ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012",
                                        fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color, weight=weight,
            linespacing=1.35)
    return patch


def arrow(ax, x0, y0, x1, y1, color=INK3, lw=1.1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=9, color=color, lw=lw))


def toy_fc(seed: int = 7, n: int = 12) -> np.ndarray:
    """세 묶음 구조를 가진 개념용 연결성 행렬 (실제 자료 아님)."""
    rng = np.random.default_rng(seed)
    g = np.repeat([0, 1, 2], n // 3)
    m = np.where(g[:, None] == g[None, :], .75, .1) + rng.normal(0, .12, (n, n))
    m = (m + m.T) / 2
    np.fill_diagonal(m, 1)
    return m


# ───────────────────────────── 모식도

def fig1_pipeline(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(W, 3.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    m = toy_fc()
    perm = np.random.default_rng(3).permutation(len(m))
    for y, mat, lab in ((.60, m, "원래 연결성 행렬"), (.13, m[perm][:, perm], "영역을 뒤섞은 행렬")):
        ia = ax.inset_axes([.115, y, .13, .27])
        ia.imshow(mat, cmap="RdBu_r", vmin=-1, vmax=1)
        ia.set_xticks([])
        ia.set_yticks([])
        for s in ia.spines.values():
            s.set_color(LINE)
        ax.text(.18, y - .045, lab, ha="center", fontsize=7.5, color=INK3)
    box(ax, 0, .40, .085, .22, "fMRI\n시계열", fc=WASH, ec=LINE)
    arrow(ax, .087, .55, .112, .70)
    arrow(ax, .087, .47, .112, .30)
    for y, lab, auc in ((.66, "모델 학습", "AUC\n(원판)"), (.19, "같은 모델 ·\n같은 절차로 학습", "AUC\n(뒤섞음)")):
        arrow(ax, .25, y + .07, .30, y + .07)
        box(ax, .30, y - .02, .17, .18, lab, fc="white")
        arrow(ax, .47, y + .07, .51, y + .07)
        box(ax, .51, y - .02, .10, .18, auc, fc=WASH, ec=LINE)
    arrow(ax, .61, .74, .655, .56, color=BRAND)
    arrow(ax, .61, .26, .655, .44, color=BRAND)
    box(ax, .655, .36, .165, .28, "Δ = 원판 − 뒤섞음", fc=BRAND, ec=BRAND, color="white", weight="bold")
    ax.text(.835, .62, "Δ 가 0 보다 확실히 큼", fontsize=7.8, color=BRAND, weight="bold")
    ax.text(.835, .555, "→ 모델이 영역 정보를 씀", fontsize=7.8, color=INK)
    ax.text(.835, .43, "Δ 가 0 근처", fontsize=7.8, color=INK3, weight="bold")
    ax.text(.835, .365, "→ 쓰지 않음, 또는\n   쓸 수 없는 구조", fontsize=7.8, color=INK, va="top")
    ax.text(.5, -.03, "반복: 뒤섞기 5 판 × seed 3 × fold 5 → 학습을 다시 할 때의 흔들림까지 넣은 구간 (재학습 포함 CI) 으로 판정",
            ha="center", fontsize=7.6, color=INK3)
    ax.text(0, .99, "행렬 그림은 개념도 (실제 자료 아님)", fontsize=6.8, color=INK3, va="top")
    save(fig, out, "pipeline.svg")


def _ring(ax, cx, cy, r, colors, edges, label):
    n = len(colors)
    ang = np.pi / 2 - 2 * np.pi * np.arange(n) / n
    xy = np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang)]
    for a, b in edges:
        ax.plot(*xy[[a, b]].T, color=LINE, lw=.9, zorder=1)
    cmap = plt.get_cmap("tab10")
    for (x, y), c in zip(xy, colors):
        ax.scatter(x, y, s=46, color=cmap(c), edgecolor="white", lw=.6, zorder=2)
        ax.text(x, y, str(c + 1), ha="center", va="center", fontsize=5.2, color="white", zorder=3, weight="bold")
    ax.text(cx, cy - r - .34, label, ha="center", fontsize=7, color=INK3)


def fig2_nulls(out: Path) -> None:
    n = 8
    ident = list(range(n))
    edges = [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (6, 7), (0, 4), (2, 6), (1, 5)]
    rng = np.random.default_rng(11)
    p_same = list(rng.permutation(n))
    pa, pb = list(rng.permutation(n)), list(rng.permutation(n))
    rot = lambda k: ident[k:] + ident[:k]  # noqa: E731
    rew_a = [(0, 3), (1, 6), (2, 5), (4, 7), (0, 2), (3, 6), (1, 4), (5, 7), (2, 7)]
    rew_b = [(0, 5), (1, 3), (2, 4), (6, 7), (0, 6), (3, 5), (1, 7), (2, 6), (4, 5)]
    panels = [
        ("원래", "영역 번호 = 뇌의 같은 자리", (ident, edges), (ident, edges)),
        ("n0 이름표만 바꿈", "모든 사람에게 같은 순서로\n→ 성능이 그대로여야 정상", (p_same, edges), (p_same, edges)),
        ("n1 무작위로 섞기", "사람마다 다른 순서로", (pa, edges), (pb, edges)),
        ("n2 돌리기", "이웃은 이웃으로 남게\n(좌우 반구 안에서)", (rot(2), edges), (rot(5), edges)),
        ("n3 연결 상대 바꾸기", "영역은 그대로, 연결을\n다른 상대로 바꿈", (ident, rew_a), (ident, rew_b)),
    ]
    fig, axes = plt.subplots(1, 5, figsize=(W, 2.35))
    for ax, (title, sub, a, b) in zip(axes, panels):
        ax.set_xlim(-1.1, 1.1)
        ax.set_ylim(-3.0, 1.35)
        ax.set_aspect("equal")
        ax.axis("off")
        _ring(ax, 0, .55, .55, a[0], a[1], "사람 A")
        _ring(ax, 0, -1.3, .55, b[0], b[1], "사람 B")
        ax.set_title(title, fontsize=8, color=BRAND if title != "원래" else INK, weight="bold", pad=2)
        ax.text(0, -2.45, sub, ha="center", va="top", fontsize=6.6, color=INK, linespacing=1.3)
    fig.text(.01, -.02, "점 = 뇌 영역 (숫자는 원래 자리), 선 = 연결. 개념도 (실제 자료 아님). "
             "점 색이 원래 자리와 어긋날수록 영역 정보가 망가진 것.", fontsize=6.6, color=INK3)
    save(fig, out, "nulls.svg")


def fig3_design(out: Path) -> None:
    rows = ["BQN", "BNT", "Han", "MoBSE mean", "MoBSE embedding"]
    cols = ["AOMIC (쉬운 문제, 126 명)", "ABIDE (어려운 문제, 1,009 명 · 963 명)"]
    cells = {
        (0, 0): ("in", "입력 뒤섞기 n0–n3\n255 회 학습"), (0, 1): ("in", "입력 뒤섞기 n0–n3\n255 회 + 기관 분할 90 회"),
        (1, 0): ("in", "입력 뒤섞기 n0–n3\n255 회 학습"), (1, 1): ("in", "입력 뒤섞기 n0–n3\n255 회 학습"),
        (2, 0): ("in", "입력 뒤섞기 n0–n3\n255 회 학습"), (2, 1): ("in", "입력 뒤섞기 n0–n3\n255 회 학습"),
        (3, 0): ("pr", "prior 만 뒤섞기 1 종 (무작위)\nv1 결과 재사용 · 새 학습 없음"), (3, 1): ("same", "입력 뒤섞기 n0–n2 (2.1 판)\n963 명 · 180 회 학습"),
        (4, 0): ("pr", "prior 만 뒤섞기 3 종\n(무작위 · 돌리기 · 연결 바꾸기)"), (4, 1): ("same", "입력 뒤섞기 n0–n2 (2.1 판)\n963 명 · 180 회 학습"),
    }
    style = {"in": ("#E7EEF6", BRAND), "pr": ("#E2F1F1", ACCENT), "same": ("#E7EEF6", BRAND)}
    fig, ax = plt.subplots(figsize=(W, 2.9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    x0, cw, rh, top = .17, .34, .135, .80
    for j, c in enumerate(cols):
        ax.text(x0 + cw * j + cw / 2, top + .07, c, ha="center", fontsize=8, weight="bold", color=INK)
    for i, r in enumerate(rows):
        y = top - rh * (i + 1)
        ax.text(x0 - .015, y + rh / 2, r, ha="right", va="center", fontsize=8.2, weight="bold",
                color=ACCENT if r.startswith("MoBSE") else BRAND)
        for j in range(2):
            kind, txt = cells[(i, j)]
            fc, ec = style[kind]
            b = box(ax, x0 + cw * j + .006, y + .008, cw - .012, rh - .016, txt, fc=fc, ec=ec, size=7.1)
            if kind == "same":
                b.set_linestyle((0, (3, 2)))
                b.set_linewidth(1.4)
    yb = top - rh * 3
    ax.plot([x0 - .16, x0 + cw + .006], [yb, yb], color=INK3, lw=.8, ls=(0, (4, 3)))
    lx = x0 + 2 * cw + .03
    ax.text(lx, top - .03, "읽는 법", fontsize=8, weight="bold", color=INK, va="top")
    notes = [(BRAND, "■ 입력 뒤섞기: 모델에 들어가는\n   연결성 · 시계열을 뒤섞음"),
             (ACCENT, "■ prior 뒤섞기: 입력은 그대로,\n   MoBSE 안의 영역 정보만 뒤섞음"),
             (BRAND, "■ 점선 테두리 = 2.1 판 추가 실행:\n   공개 모델과 같은 fold · seed ·\n   입력 뒤섞기 (963 명 공통)"),
             (INK, "AOMIC 열의 점선 위 · 아래는\n뒤섞는 대상이 달라 Δ 를\n나란히 비교할 수 없음")]
    yy = top - .11
    for c, t in notes:
        ax.text(lx, yy, t, fontsize=6.9, color=c if c != INK else INK, va="top", linespacing=1.3)
        yy -= .15 if t.count("\n") < 2 else .2
    save(fig, out, "design.svg")


# ───────────────────────────── 결과

def fig4_delta(A: Dict[str, dict], out: Path) -> None:
    rows = []
    for ds, dsn in (("aomic", "AOMIC"), ("abide", "ABIDE")):
        for m, mn in PUBLIC:
            rows.append((f"{mn} · {dsn}", A[f"analysis/{ds}/{m}.json"]["all"]["conditions"]))
    rows.append(("BQN · ABIDE 기관 분할", A["analysis/abide_site/bqn.json"]["all"]["conditions"]))
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(W, 5.0), gridspec_kw={"height_ratios": [7, 2.6], "hspace": .55})
    off = {"n0": .27, "n1": .09, "n2": -.09, "n3": -.27}
    for i, (lab, conds) in enumerate(rows):
        y = len(rows) - 1 - i
        if i % 2 == 0:
            ax.axhspan(y - .5, y + .5, color=WASH, zorder=0, lw=0)
        for c, cond in conds.items():
            lo, hi = cond["retrain_ci95"]
            ax.plot([lo, hi], [y + off[c]] * 2, color=NULL_COLOR[c], lw=2.2, solid_capstyle="butt")
            ax.scatter(cond["delta_mean"], y + off[c], s=16, color=NULL_COLOR[c], zorder=3, edgecolor="white", lw=.4)
    ax.axvline(0, color=INK, lw=.8)
    ax.axhline(3.5, color=INK3, lw=.6, ls=(0, (3, 3)))
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_ylim(-.6, len(rows) - .4)
    ax.set_xlim(-.05, .5)
    ax.set_xlabel("Δ = 원판 AUC − 뒤섞은 AUC (점 = 평균, 막대 = 재학습 포함 95 % CI)")
    ax.set_title("공개 모델 세 종 — 입력을 뒤섞음: 모든 뒤섞기 방법에서 Δ > 0 (n0 점검만 0)", loc="left", color=BRAND, weight="bold")
    for c in ("n0", "n1", "n2", "n3"):
        ax.plot([], [], color=NULL_COLOR[c], lw=2.2, label=NULL_NAME[c])
    ax.legend(loc="lower right", fontsize=7, frameon=True, framealpha=.95, edgecolor=LINE)
    ax.text(.49, 3.4, "ABIDE (어려움)", ha="right", fontsize=7, color=INK3, va="top")
    ax.text(.49, 3.6, "AOMIC (쉬움)", ha="right", fontsize=7, color=INK3, va="bottom")

    mm = A["analysis/aomic/mobse_mean.json"]["all"]["conditions"]
    me = A["analysis/aomic/mobse_embedding.json"]["all"]["conditions"]
    mrows = [("embedding · 연결 바꾸기", me["prior_rewire"], WARN), ("embedding · 돌리기", me["prior_spin"], ACCENT),
             ("embedding · 무작위", me["prior_permutation"], BRAND), ("mean (등변) · 무작위", mm["prior_permutation"], BRAND)]
    for y, (lab, cond, col) in enumerate(mrows):
        lo, hi = cond["retrain_ci95"]
        bx.plot([lo, hi], [y, y], color=col, lw=2.2)
        bx.scatter(cond["delta_mean"], y, s=16, color=col, zorder=3, edgecolor="white", lw=.4)
    bx.axvline(0, color=INK, lw=.8)
    bx.set_yticks(range(len(mrows)))
    bx.set_yticklabels([r[0] for r in mrows])
    bx.set_xlim(-.03, .03)
    bx.set_ylim(-.6, len(mrows) - .4)
    bx.set_xlabel("Δ (가로 눈금이 위 그림의 약 9 배 확대 — 같은 축에 놓고 비교하지 말 것)")
    bx.set_title("MoBSE (AOMIC 만) — prior 만 뒤섞음: embedding 은 셋 다 0 포함 · mean 은 지표 따라 부호가 바뀜",
                 loc="left", color=ACCENT, weight="bold", fontsize=8.2)
    save(fig, out, "delta.svg")


def fig5_auc(A: Dict[str, dict], out: Path) -> None:
    items = [("fc_logistic", "FC\nlogistic"), ("fc_mlp", "FC-MLP"), ("s1_logistic", "S1"), ("bqn", "BQN"),
             ("bnt", "BNT"), ("han", "Han"), ("mobse_mean", "MoBSE\nmean"), ("mobse_embedding", "MoBSE\nembedding")]
    fig, ax = plt.subplots(figsize=(W, 2.6))
    x = np.arange(len(items))
    for k, (ds, col, lab) in enumerate((("aomic", BRAND, "AOMIC (쉬움)"), ("abide", WARN, "ABIDE (어려움)"))):
        for i, (m, _) in enumerate(items):
            rel = f"analysis/{ds}/{m}.json"
            xi = x[i] + (k - .5) * .38
            if rel not in A:
                ax.text(xi, .515, "963 명\n그림 9", ha="center", va="bottom", fontsize=6, color=INK3)
                continue
            v = A[rel]["all"]["orig_auc_mean"]
            ax.bar(xi, v - .5, bottom=.5, width=.36, color=col, label=lab if i == 0 else None)
            ax.text(xi, v + .006, f"{v:.3f}", ha="center", fontsize=5.8, color=INK, rotation=90, va="bottom")
    ax.axvspan(2.5, 2.52, color=INK3)
    ax.axhline(.5, color=INK3, lw=.6)
    ax.set_xticks(x)
    ax.set_xticklabels([n for _, n in items])
    ax.set_ylim(.5, 1.1)
    ax.set_ylabel("원판 AUC (0.5 = 동전 던지기)")
    ax.text(1, 1.075, "단순 기준선", ha="center", fontsize=7, color=INK3)
    ax.text(5, 1.075, "그래프 딥러닝 모델", ha="center", fontsize=7, color=INK3)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), fontsize=7, frameon=False, ncol=2)
    save(fig, out, "auc.svg")


def fig6_retrain(A: Dict[str, dict], out: Path) -> None:
    cases = [
        ("ABIDE · BQN · n1 (효과 큼)", A["analysis/abide/bqn.json"]["all"]["conditions"]["n1"], BRAND),
        ("ABIDE · Han · n3 (효과 중간)", A["analysis/abide/han.json"]["all"]["conditions"]["n3"], WARN),
        ("MoBSE embedding · 연결 바꾸기", A["analysis/aomic/mobse_embedding.json"]["all"]["conditions"]["prior_rewire"], WARN),
        ("MoBSE embedding · 무작위", A["analysis/aomic/mobse_embedding.json"]["all"]["conditions"]["prior_permutation"], BRAND),
    ]
    fig, axes = plt.subplots(len(cases), 1, figsize=(W, 3.6), gridspec_kw={"hspace": 1.05})
    rng = np.random.default_rng(0)
    for ax, (lab, c, col) in zip(axes, cases):
        d = np.array(list(c["delta_by_pair"].values()))
        lo, hi = c["retrain_ci95"]
        span = max(abs(lo), abs(hi), abs(d).max()) * 1.35
        ax.axvspan(lo, hi, color=col, alpha=.15, lw=0)
        ax.scatter(d, rng.uniform(-.25, .25, len(d)), s=14, color=col, edgecolor="white", lw=.4, zorder=3)
        ax.axvline(0, color=INK, lw=.8)
        ax.set_xlim(min(-span * .3, lo - span * .15), span) if lo > 0 else ax.set_xlim(-span, span)
        ax.set_ylim(-.5, .5)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        rate = c["single_excludes_zero_rate"]
        verdict = "0 을 넘음" if lo > 0 else "0 을 포함"
        ax.set_title(f"{lab} — 점 {len(d)} 개 = 학습 {len(d)} 번의 Δ · 띠 = 재학습 포함 CI ({verdict}) · "
                     f"한 번만 학습한 CI 가 0 을 벗어난 비율 {rate:.2f}", loc="left", fontsize=7.2, color=INK)
    axes[-1].set_xlabel("Δ (그림마다 가로 눈금이 다름)")
    save(fig, out, "retrain.svg")


def fig7_d1(run: Path, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(W, 2.2))
    labels = []
    for i, (ds, dsn) in enumerate((("aomic", "AOMIC"), ("abide", "ABIDE"))):
        for j, (m, mn) in enumerate(PUBLIC):
            y = 5 - (i * 3 + j)
            labels.append((y, f"{mn} · {dsn}"))
            v = [json.loads((run / ds / m / "orig/k0/r1" / f"f{f}" / "d1.json").read_text())["max_abs_diff_p1"]
                 for f in range(3)]
            ax.plot([min(v), max(v)], [y, y], color=LINE, lw=3, zorder=1)
            ax.scatter(v, [y] * 3, s=20, color=BRAND if ds == "aomic" else WARN, zorder=2, edgecolor="white", lw=.4)
    ax.axvline(0, color=ACCENT, lw=1.2)
    ax.text(.008, 5.55, "순서에 무관한 (등변) 모델이면 여기 (0)", color=ACCENT, fontsize=7, va="bottom")
    ax.set_yticks([y for y, _ in labels])
    ax.set_yticklabels([l for _, l in labels])
    ax.set_ylim(-.6, 6.1)
    ax.set_xlim(-.02, 1.02)
    ax.set_xlabel("영역 순서만 바꾼 같은 입력에서 예측 확률이 가장 크게 달라진 값 (학습 끝난 원판, fold 3 개)")
    save(fig, out, "d1.svg")


def fig8_collapse(A: Dict[str, dict], out: Path) -> None:
    groups = [(f"{mn} · {dsn}", A[f"analysis/{ds}/{m}.json"]) for ds, dsn in (("aomic", "AOMIC"), ("abide", "ABIDE"))
              for m, mn in PUBLIC]
    groups.append(("BQN · ABIDE 기관 분할", A["analysis/abide_site/bqn.json"]))
    dc = A["diag/collapse_20261012/diag_collapse.json"]
    fig, ax = plt.subplots(figsize=(W, 2.3))
    for i, (lab, d) in enumerate(groups):
        y = len(groups) - 1 - i
        n, c = d["n_fits"], d["n_collapsed_fits"]
        ax.barh(y, n - c, color="#C9D6E3", height=.6)
        ax.barh(y, c, left=n - c, color="#A5342E", height=.6)
        ax.text(n + 3, y, f"{c}/{n}" if c else f"0/{n}", va="center", fontsize=7, color=INK)
    tot_c = sum(f["collapsed"] for f in dc["fits"])
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([g[0] for g in groups][::-1])
    ax.set_xlim(0, 300)
    ax.set_xlabel(f"학습 횟수 (빨강 = 붕괴: 모든 사람에게 같은 답) · 합계 {tot_c}/{dc['n_fits']:,}")
    save(fig, out, "collapse.svg")


def fig9_same(B: Dict[str, dict], out: Path) -> None:
    """2.1 판 — ABIDE 963 명, 다섯 모델이 같은 fold · seed · 입력 뒤섞기. 왼쪽 원판 · 뒤섞은 AUC, 오른쪽 Δ."""
    models = [("mobse_mean", "MoBSE mean"), ("mobse_embedding", "MoBSE embedding"),
              ("bqn", "BQN"), ("bnt", "BNT"), ("han", "Han")]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(W, 3.0), gridspec_kw={"width_ratios": [1, 1.45], "wspace": .08},
                                 sharey=True)
    off = {"n0": .27, "n1": .09, "n2": -.09, "n3": -.27}
    for i, (m, name) in enumerate(models):
        y = len(models) - 1 - i
        a = B[f"analysis/{m}.json"]["all"]
        conds = a["conditions"]
        for z in (ax, bx):
            if i % 2 == 0:
                z.axhspan(y - .5, y + .5, color=WASH, zorder=0, lw=0)
        orig = a["orig_auc_mean"]
        nul = conds["n1"]["null_auc_mean"]
        ax.plot([nul, orig], [y, y], color=LINE, lw=3, zorder=1, solid_capstyle="butt")
        ax.scatter(nul, y, s=22, color=NULL_COLOR["n1"], zorder=3, edgecolor="white", lw=.4,
                   label="n1 뒤섞은 AUC" if i == 0 else None)
        ax.scatter(orig, y, s=26, color=INK, marker="D", zorder=3, edgecolor="white", lw=.4,
                   label="원판 AUC" if i == 0 else None)
        ax.text(orig + .008, y, f"{orig:.3f}", va="center", fontsize=6.6, color=INK)
        for c, cond in conds.items():
            lo, hi = cond["retrain_ci95"]
            bx.plot([lo, hi], [y + off[c]] * 2, color=NULL_COLOR[c], lw=2.2, solid_capstyle="butt")
            bx.scatter(cond["delta_mean"], y + off[c], s=14, color=NULL_COLOR[c], zorder=3, edgecolor="white", lw=.4)
        if m.startswith("mobse"):
            bx.text(.005, y + off["n3"], "n3 해당 없음", va="center", fontsize=6.2, color=INK3)
    for z in (ax, bx):
        z.axhline(2.5, color=INK3, lw=.6, ls=(0, (3, 3)))
        z.set_ylim(-.6, len(models) - .4)
    ax.axvline(.5, color=INK3, lw=.6)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([n for _, n in models][::-1])
    ax.set_xlim(.47, .82)
    ax.set_xlabel("AUC (0.5 = 동전 던지기)")
    ax.set_title("원판과 뒤섞은 AUC — 출발점이 다름", loc="left", color=BRAND, weight="bold", fontsize=8.2)
    bx.axvline(0, color=INK, lw=.8)
    bx.set_xlim(-.05, .3)
    bx.set_xlabel("Δ = 원판 AUC − 뒤섞은 AUC (막대 = 재학습 포함 95 % CI)")
    bx.set_title("Δ — 다섯 모델 모두 n1 · n2 에서 0 을 넘음", loc="left", color=BRAND, weight="bold", fontsize=8.2)
    for c in ("n0", "n1", "n2", "n3"):
        bx.plot([], [], color=NULL_COLOR[c], lw=2.2, label=NULL_NAME[c])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = bx.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(.5, -.02), ncol=3, fontsize=6.8, frameon=False)
    save(fig, out, "same.svg")


def fig10_adhd(C: Dict[str, dict], out: Path) -> None:
    """2.3 판 — ADHD-200 541 명, 다섯 모델이 같은 fold · seed · 입력 뒤섞기. 왼쪽 원판 · 뒤섞은 AUC, 오른쪽 Δ."""
    models = [("mobse_mean", "MoBSE mean"), ("mobse_embedding", "MoBSE embedding"),
              ("bqn", "BQN"), ("bnt", "BNT"), ("han", "Han")]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(W, 3.0), gridspec_kw={"width_ratios": [1, 1.45], "wspace": .08},
                                 sharey=True)
    off = {"n0": .27, "n1": .09, "n2": -.09, "n3": -.27}
    for i, (m, name) in enumerate(models):
        y = len(models) - 1 - i
        d = C[f"analysis/adhd200/{m}.json"]
        a = d["all"]
        conds = a["conditions"]
        for z in (ax, bx):
            if i % 2 == 0:
                z.axhspan(y - .5, y + .5, color=WASH, zorder=0, lw=0)
        orig = a["orig_auc_mean"]
        nul = conds["n1"]["null_auc_mean"]
        ax.plot([nul, orig], [y, y], color=LINE, lw=3, zorder=1, solid_capstyle="butt")
        ax.scatter(nul, y, s=22, color=NULL_COLOR["n1"], zorder=3, edgecolor="white", lw=.4,
                   label="n1 뒤섞은 AUC" if i == 0 else None)
        ax.scatter(orig, y, s=26, color=INK, marker="D", zorder=3, edgecolor="white", lw=.4,
                   label="원판 AUC" if i == 0 else None)
        ax.text(max(orig, nul) + .006, y, f"{orig:.3f}", va="center", fontsize=6.6, color=INK)
        for c, cond in conds.items():
            lo, hi = cond["retrain_ci95"]
            bx.plot([lo, hi], [y + off[c]] * 2, color=NULL_COLOR[c], lw=2.2, solid_capstyle="butt")
            bx.scatter(cond["delta_mean"], y + off[c], s=14, color=NULL_COLOR[c], zorder=3, edgecolor="white", lw=.4)
        if m.startswith("mobse"):
            bx.text(.005, y + off["n3"], "n3 해당 없음", va="center", fontsize=6.2, color=INK3)
        if d["n_collapsed_fits"]:
            bx.text(.205, y, f"붕괴 {d['n_collapsed_fits']}/{d['n_fits']}", va="center", fontsize=6.4, color="#A5342E")
    for z in (ax, bx):
        z.axhline(2.5, color=INK3, lw=.6, ls=(0, (3, 3)))
        z.set_ylim(-.6, len(models) - .4)
    fcl = C["analysis/adhd200/fc_logistic.json"]["all"]["orig_auc_mean"]
    ax.axvline(fcl, color=ACCENT, lw=.9, ls=(0, (2, 2)))
    ax.text(fcl, len(models) - .45, f"FC logistic {fcl:.3f}", ha="center", va="bottom", fontsize=6.2, color=ACCENT)
    ax.axvline(.5, color=INK3, lw=.6)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([n for _, n in models][::-1])
    ax.set_xlim(.47, .67)
    ax.set_xlabel("AUC (0.5 = 동전 던지기)")
    ax.set_title("원판과 뒤섞은 AUC", loc="left", color=BRAND, weight="bold", fontsize=8.2)
    bx.axvline(0, color=INK, lw=.8)
    bx.set_xlim(-.06, .26)
    bx.set_xlabel("Δ = 원판 AUC − 뒤섞은 AUC (막대 = 재학습 포함 95 % CI)")
    bx.set_title("Δ — BQN · BNT 는 n1–n3 이 0 을 넘고, 나머지는 0 포함", loc="left", color=BRAND, weight="bold",
                 fontsize=8.2)
    for c in ("n0", "n1", "n2", "n3"):
        bx.plot([], [], color=NULL_COLOR[c], lw=2.2, label=NULL_NAME[c])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = bx.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(.5, -.02), ncol=3, fontsize=6.8, frameon=False)
    save(fig, out, "adhd.svg")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-root", type=Path, required=True)
    ap.add_argument("--abide963-root", type=Path, required=True, help="ABIDE MoBSE 확장 run 폴더 (결정 59) 또는 그 사본")
    ap.add_argument("--adhd-root", type=Path, required=True, help="ADHD-200 run 폴더 (결정 65) 또는 그 사본")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    setup_fonts()
    A = load_all(a.run_root)
    B = load_all(a.abide963_root, EXPECTED_SHA12_963)
    C = load_all(a.adhd_root, EXPECTED_SHA12_ADHD)
    a.out.mkdir(parents=True, exist_ok=True)
    fig1_pipeline(a.out)
    fig2_nulls(a.out)
    fig3_design(a.out)
    fig4_delta(A, a.out)
    fig5_auc(A, a.out)
    fig6_retrain(A, a.out)
    fig7_d1(a.run_root, a.out)
    fig8_collapse(A, a.out)
    fig9_same(B, a.out)
    fig10_adhd(C, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
