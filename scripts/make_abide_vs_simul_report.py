#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from mobse.viz import save_multi, set_nature_style


PALETTE: Dict[str, str] = {
    "abide": "#4A90E2",
    "simulation": "#E27396",
}

FONT: Dict[str, float] = {
    "title": 15,
    "title_pad": 10,
    "axis_label": 13,
    "legend": 11,
    "tick": 11,
}

LINE: Dict[str, float] = {
    "main": 2.8,
}

FIGURE_DEFAULTS: Dict[str, object] = {
    "dpi": 300,
    "style": "whitegrid",
    "context": "paper",
    "font_scale": 1.2,
    "tight_layout_pad": 3.0,
}


def _load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _os_block(payload: Dict[str, object]) -> Dict[str, object]:
    # Backward compatibility: old eval payloads use only "hcp".
    return payload.get("os") or payload.get("hcp") or {}


def _extract_subject_count(prepare_payload: Dict[str, object]) -> int:
    if "subjects_collected" in prepare_payload:
        return int(prepare_payload["subjects_collected"])

    stats = prepare_payload.get("os_stats") or prepare_payload.get("hcp_stats") or {}
    if isinstance(stats, dict):
        vals = []
        for v in stats.values():
            try:
                vals.append(int(v))
            except Exception:
                continue
        if vals:
            return int(max(vals))
    return 0


def _extract_blocks(
    eval_payload: Dict[str, object],
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float]]:
    os_eval = _os_block(eval_payload)
    os_metrics = (os_eval.get("metrics") or {}) if isinstance(os_eval, dict) else {}
    os_profile = (os_eval.get("profile") or {}) if isinstance(os_eval, dict) else {}

    et_eval = eval_payload.get("etth1") or {}
    et_metrics = (et_eval.get("metrics") or {}) if isinstance(et_eval, dict) else {}
    et_profile = (et_eval.get("profile") or {}) if isinstance(et_eval, dict) else {}
    return os_metrics, os_profile, et_metrics, et_profile


def _num(x) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _subject_balance_note(abide_n: int, sim_n: int) -> str:
    if abide_n <= 0 or sim_n <= 0:
        return "Note: subject count is missing in one side; interpret comparisons carefully."
    hi = max(abide_n, sim_n)
    lo = min(abide_n, sim_n)
    if lo == 0:
        return "Note: subject count is missing in one side; interpret comparisons carefully."
    ratio = hi / lo
    if ratio >= 3.0:
        return "Note: subject counts are highly imbalanced; direct performance comparison is descriptive only."
    if ratio >= 1.5:
        return "Note: subject counts are moderately imbalanced; interpret performance gaps with caution."
    return "Note: subject counts are broadly comparable."


def _apply_theme() -> None:
    set_nature_style()



def _style_axis(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=FONT["title"], fontweight="bold", pad=FONT["title_pad"])
    ax.set_ylabel(ylabel, fontsize=FONT["axis_label"])
    ax.tick_params(labelsize=FONT["tick"])
    ax.legend(fontsize=FONT["legend"], frameon=True)


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    save_multi(path, fig)
    plt.close(fig)


def _state_labels(abide_prepare: Dict[str, object], default_len: int) -> List[str]:
    sizes = abide_prepare.get("network_sizes")
    if isinstance(sizes, dict) and sizes:
        keys = [str(k) for k in sizes.keys()]
        if len(keys) == default_len:
            return keys
    return [f"state{i+1}" for i in range(default_len)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ABIDE-vs-simulation eval comparison report and figures.")
    ap.add_argument("--abide-eval", required=True)
    ap.add_argument("--abide-prepare", required=True)
    ap.add_argument("--sim-eval", required=True)
    ap.add_argument("--sim-prepare", required=True)
    ap.add_argument("--out-dir", default="artifacts/current_canonical/abide_vs_simul150_fair_eval_20260330/reports")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    abide_eval = _load_json(Path(args.abide_eval))
    abide_prepare = _load_json(Path(args.abide_prepare))
    sim_eval = _load_json(Path(args.sim_eval))
    sim_prepare = _load_json(Path(args.sim_prepare))

    abide_n = _extract_subject_count(abide_prepare)
    sim_n = _extract_subject_count(sim_prepare)

    a_os_m, a_os_p, a_et_m, a_et_p = _extract_blocks(abide_eval)
    s_os_m, s_os_p, s_et_m, s_et_p = _extract_blocks(sim_eval)

    os_rows = [
        {"metric": "loss", "abide": _num(a_os_m.get("loss")), "simulation": _num(s_os_m.get("loss"))},
        {"metric": "accuracy", "abide": _num(a_os_m.get("accuracy")), "simulation": _num(s_os_m.get("accuracy"))},
        {"metric": "f1_macro", "abide": _num(a_os_m.get("f1_macro")), "simulation": _num(s_os_m.get("f1_macro"))},
        {"metric": "routing_entropy", "abide": _num(a_os_m.get("routing_entropy")), "simulation": _num(s_os_m.get("routing_entropy"))},
        {"metric": "routing_stability", "abide": _num(a_os_m.get("routing_stability")), "simulation": _num(s_os_m.get("routing_stability"))},
        {"metric": "latency_ms_mean", "abide": _num(a_os_p.get("latency_ms_mean")), "simulation": _num(s_os_p.get("latency_ms_mean"))},
        {"metric": "flops", "abide": _num(a_os_p.get("flops")), "simulation": _num(s_os_p.get("flops"))},
    ]
    os_df = pd.DataFrame(os_rows)
    os_df["diff_abide_minus_sim"] = os_df["abide"] - os_df["simulation"]

    et_rows = [
        {"metric": "loss", "abide": _num(a_et_m.get("loss")), "simulation": _num(s_et_m.get("loss"))},
        {"metric": "mae", "abide": _num(a_et_m.get("mae")), "simulation": _num(s_et_m.get("mae"))},
        {"metric": "mse", "abide": _num(a_et_m.get("mse")), "simulation": _num(s_et_m.get("mse"))},
        {"metric": "routing_entropy", "abide": _num(a_et_m.get("routing_entropy")), "simulation": _num(s_et_m.get("routing_entropy"))},
        {"metric": "routing_stability", "abide": _num(a_et_m.get("routing_stability")), "simulation": _num(s_et_m.get("routing_stability"))},
        {"metric": "latency_ms_mean", "abide": _num(a_et_p.get("latency_ms_mean")), "simulation": _num(s_et_p.get("latency_ms_mean"))},
        {"metric": "flops", "abide": _num(a_et_p.get("flops")), "simulation": _num(s_et_p.get("flops"))},
    ]
    et_df = pd.DataFrame(et_rows)
    et_df["diff_abide_minus_sim"] = et_df["abide"] - et_df["simulation"]

    os_csv = out_dir / "abide_vs_simul_os_metrics.csv"
    et_csv = out_dir / "abide_vs_simul_etth1_metrics.csv"
    os_df.to_csv(os_csv, index=False)
    et_df.to_csv(et_csv, index=False)

    _apply_theme()

    # Figure 1: OS core metrics
    core = os_df[os_df["metric"].isin(["accuracy", "f1_macro", "loss"])].copy()
    x = range(len(core))
    width = 0.38
    fig1 = out_dir / "fig_abide_vs_simul_os_core.png"
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.bar(
        [i - width / 2 for i in x],
        core["abide"],
        width=width,
        label=f"ABIDE (n={abide_n})",
        color=PALETTE["abide"],
        linewidth=LINE["main"] * 0.1,
        edgecolor="#2c3e50",
    )
    ax.bar(
        [i + width / 2 for i in x],
        core["simulation"],
        width=width,
        label=f"Simulation (n={sim_n})",
        color=PALETTE["simulation"],
        linewidth=LINE["main"] * 0.1,
        edgecolor="#2c3e50",
    )
    ax.set_xticks(list(x), core["metric"].tolist())
    _style_axis(ax, "A. ABIDE vs Simulation (OS Core Metrics)", "Value")
    _save(fig, fig1)

    # Figure 2: OS profile
    prof = os_df[os_df["metric"].isin(["latency_ms_mean", "flops"])].copy()
    x2 = range(len(prof))
    fig2 = out_dir / "fig_abide_vs_simul_os_profile.png"
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.bar(
        [i - width / 2 for i in x2],
        prof["abide"],
        width=width,
        label=f"ABIDE (n={abide_n})",
        color=PALETTE["abide"],
        linewidth=LINE["main"] * 0.1,
        edgecolor="#2c3e50",
    )
    ax.bar(
        [i + width / 2 for i in x2],
        prof["simulation"],
        width=width,
        label=f"Simulation (n={sim_n})",
        color=PALETTE["simulation"],
        linewidth=LINE["main"] * 0.1,
        edgecolor="#2c3e50",
    )
    ax.set_xticks(list(x2), prof["metric"].tolist())
    _style_axis(ax, "B. ABIDE vs Simulation (OS Profile)", "Value")
    _save(fig, fig2)

    # Figure 3: ETTh1 core metrics
    et_core = et_df[et_df["metric"].isin(["loss", "mae", "mse"])].copy()
    x3 = range(len(et_core))
    fig3 = out_dir / "fig_abide_vs_simul_etth1_core.png"
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.bar(
        [i - width / 2 for i in x3],
        et_core["abide"],
        width=width,
        label=f"ABIDE (n={abide_n})",
        color=PALETTE["abide"],
        linewidth=LINE["main"] * 0.1,
        edgecolor="#2c3e50",
    )
    ax.bar(
        [i + width / 2 for i in x3],
        et_core["simulation"],
        width=width,
        label=f"Simulation (n={sim_n})",
        color=PALETTE["simulation"],
        linewidth=LINE["main"] * 0.1,
        edgecolor="#2c3e50",
    )
    ax.set_xticks(list(x3), et_core["metric"].tolist())
    _style_axis(ax, "C. ABIDE vs Simulation (ETTh1 Core Metrics)", "Value")
    _save(fig, fig3)

    # Figure 4: Routing usage (OS task)
    os_usage_a = list((a_os_m.get("routing_usage") or [])) if isinstance(a_os_m, dict) else []
    os_usage_s = list((s_os_m.get("routing_usage") or [])) if isinstance(s_os_m, dict) else []
    usage_len = min(len(os_usage_a), len(os_usage_s))
    fig4 = out_dir / "fig_abide_vs_simul_os_routing_usage.png"
    if usage_len > 0:
        labels = _state_labels(abide_prepare, usage_len)
        os_usage_a = [float(v) for v in os_usage_a[:usage_len]]
        os_usage_s = [float(v) for v in os_usage_s[:usage_len]]
        x4 = range(usage_len)
        fig, ax = plt.subplots(figsize=(7.2, 3.5))
        ax.bar(
            [i - width / 2 for i in x4],
            os_usage_a,
            width=width,
            label=f"ABIDE (n={abide_n})",
            color=PALETTE["abide"],
            linewidth=LINE["main"] * 0.1,
            edgecolor="#2c3e50",
        )
        ax.bar(
            [i + width / 2 for i in x4],
            os_usage_s,
            width=width,
            label=f"Simulation (n={sim_n})",
            color=PALETTE["simulation"],
            linewidth=LINE["main"] * 0.1,
            edgecolor="#2c3e50",
        )
        ax.set_xticks(list(x4), labels, rotation=20, ha="right")
        _style_axis(ax, "D. ABIDE vs Simulation (OS Routing Usage)", "Usage Ratio")
        _save(fig, fig4)

    md = out_dir / "abide_vs_simul_eval_report.md"
    lines = []
    lines.append("# ABIDE vs Simulation Eval Comparison")
    lines.append("")
    lines.append("## Inputs")
    lines.append(f"- ABIDE eval: `{args.abide_eval}`")
    lines.append(f"- ABIDE prepare: `{args.abide_prepare}`")
    lines.append(f"- Simulation eval: `{args.sim_eval}`")
    lines.append(f"- Simulation prepare: `{args.sim_prepare}`")
    lines.append("")
    lines.append("## Data Summary")
    lines.append(f"- ABIDE subjects collected: `{abide_n}`")
    lines.append(f"- Simulation subjects collected: `{sim_n}`")
    lines.append(f"- {_subject_balance_note(abide_n, sim_n)}")
    lines.append("")
    lines.append("## OS Metrics (ABIDE - Simulation)")
    lines.append("")
    lines.append("| metric | ABIDE | Simulation | diff |")
    lines.append("|---|---:|---:|---:|")
    for _, row in os_df.iterrows():
        lines.append(
            f"| {row['metric']} | {row['abide']:.6g} | {row['simulation']:.6g} | {row['diff_abide_minus_sim']:.6g} |"
        )
    lines.append("")
    lines.append("## ETTh1 Metrics (ABIDE - Simulation)")
    lines.append("")
    lines.append("| metric | ABIDE | Simulation | diff |")
    lines.append("|---|---:|---:|---:|")
    for _, row in et_df.iterrows():
        lines.append(
            f"| {row['metric']} | {row['abide']:.6g} | {row['simulation']:.6g} | {row['diff_abide_minus_sim']:.6g} |"
        )
    lines.append("")
    lines.append("## Discussion (Limitations and Interpretation)")
    lines.append("")
    lines.append("- **Window-level split caveat**: default split is index-randomized at window level; windows from one subject can appear across train/val/test, so reported OS scores can be optimistic.")
    lines.append("- **State-generation mismatch**: ABIDE states are node-masked by a cohort-derived network partition, while simulation states are generated by temporal transforms/noise; this creates different class-separability regimes.")
    lines.append("- **Cohort heterogeneity remains**: ABIDE and development-fMRI proxy differ in acquisition/site/population, so this report is a controlled benchmark comparison, not direct clinical equivalence.")
    lines.append("- **Preprocessing dependency**: conclusions still depend on nuisance strategy and denoising choices; strict subject-level split and denoising sensitivity should be reported together.")
    lines.append("")
    lines.append("## Figures")
    lines.append(f"- `fig_abide_vs_simul_os_core.png`")
    lines.append(f"- `fig_abide_vs_simul_os_profile.png`")
    lines.append(f"- `fig_abide_vs_simul_etth1_core.png`")
    if usage_len > 0:
        lines.append(f"- `fig_abide_vs_simul_os_routing_usage.png`")
    md.write_text("\n".join(lines), encoding="utf-8")

    figures = [str(fig1), str(fig2), str(fig3)]
    if usage_len > 0:
        figures.append(str(fig4))
    manifest = {
        "report_md": str(md),
        "os_metrics_csv": str(os_csv),
        "etth1_metrics_csv": str(et_csv),
        "figures": figures,
        "abide_subjects": int(abide_n),
        "simulation_subjects": int(sim_n),
    }
    manifest_path = out_dir / "abide_vs_simul_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
