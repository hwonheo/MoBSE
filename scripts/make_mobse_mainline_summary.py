#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from mobse.viz import save_multi, set_nature_style


PALETTE = {
    "abide": "#4A90E2",
    "simulation": "#E27396",
}


def _load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _num(x) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _subject_count(prepare_payload: Dict[str, object]) -> int:
    if "subjects_collected" in prepare_payload:
        return int(prepare_payload["subjects_collected"])
    stats = prepare_payload.get("os_stats") or prepare_payload.get("hcp_stats") or {}
    if isinstance(stats, dict) and stats:
        vals = []
        for v in stats.values():
            try:
                vals.append(int(v))
            except Exception:
                continue
        if vals:
            return int(max(vals))
    return 0


def _os_block(payload: Dict[str, object]) -> Dict[str, object]:
    return payload.get("os") or payload.get("hcp") or {}


def _style() -> None:
    set_nature_style()



def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    save_multi(path, fig)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build MoBSE mainline summary table and figure package.")
    ap.add_argument("--abide-eval", required=True)
    ap.add_argument("--abide-prepare", required=True)
    ap.add_argument("--sim-eval", required=True)
    ap.add_argument("--sim-prepare", required=True)
    ap.add_argument("--out-dir", default="artifacts/current_canonical/abide_mobse_mainline_20260330/reports")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    abide_eval = _load_json(Path(args.abide_eval))
    abide_prepare = _load_json(Path(args.abide_prepare))
    sim_eval = _load_json(Path(args.sim_eval))
    sim_prepare = _load_json(Path(args.sim_prepare))

    a_os = _os_block(abide_eval)
    s_os = _os_block(sim_eval)
    a_m = a_os.get("metrics") or {}
    s_m = s_os.get("metrics") or {}
    a_p = a_os.get("profile") or {}
    s_p = s_os.get("profile") or {}

    rows = [
        {
            "run_id": str(abide_eval.get("run_id", "abide")),
            "n_subjects": _subject_count(abide_prepare),
            "os_loss": _num(a_m.get("loss")),
            "os_acc": _num(a_m.get("accuracy")),
            "os_f1": _num(a_m.get("f1_macro")),
            "routing_entropy": _num(a_m.get("routing_entropy")),
            "routing_stability": _num(a_m.get("routing_stability")),
            "latency_ms": _num(a_p.get("latency_ms_mean")),
            "flops": _num(a_p.get("flops")),
        },
        {
            "run_id": str(sim_eval.get("run_id", "simulation")),
            "n_subjects": _subject_count(sim_prepare),
            "os_loss": _num(s_m.get("loss")),
            "os_acc": _num(s_m.get("accuracy")),
            "os_f1": _num(s_m.get("f1_macro")),
            "routing_entropy": _num(s_m.get("routing_entropy")),
            "routing_stability": _num(s_m.get("routing_stability")),
            "latency_ms": _num(s_p.get("latency_ms_mean")),
            "flops": _num(s_p.get("flops")),
        },
    ]
    df = pd.DataFrame(rows)

    csv_path = out_dir / "mobse_mainline_summary.csv"
    df.to_csv(csv_path, index=False)

    _style()

    # Figure 1: OS quality metrics
    fig1 = out_dir / "fig_mobse_mainline_os_quality.png"
    metrics = ["os_loss", "os_acc", "os_f1"]
    titles = ["OS Loss", "OS Accuracy", "OS F1-macro"]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.0))
    for ax, m, title in zip(axes, metrics, titles):
        ax.bar(
            ["ABIDE", "Sim"],
            [df.iloc[0][m], df.iloc[1][m]],
            color=[PALETTE["abide"], PALETTE["simulation"]],
            edgecolor="#2c3e50",
            linewidth=0.3,
        )
        ax.set_title(title, fontweight="bold", pad=10)
        ax.set_ylabel("Value")
    _save(fig, fig1)

    # Figure 2: Efficiency metrics
    fig2 = out_dir / "fig_mobse_mainline_efficiency.png"
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5))
    for ax, m, title in zip(axes, ["latency_ms", "flops"], ["Latency (ms)", "FLOPs"]):
        ax.bar(
            ["ABIDE", "Sim"],
            [df.iloc[0][m], df.iloc[1][m]],
            color=[PALETTE["abide"], PALETTE["simulation"]],
            edgecolor="#2c3e50",
            linewidth=0.3,
        )
        ax.set_title(title, fontweight="bold", pad=10)
        ax.set_ylabel("Value")
    _save(fig, fig2)

    # Figure 3: OS routing usage profile
    usage_a = list((a_m.get("routing_usage") or []))
    usage_s = list((s_m.get("routing_usage") or []))
    usage_len = min(len(usage_a), len(usage_s))
    fig3 = out_dir / "fig_mobse_mainline_os_routing_usage.png"
    figures = [str(fig1), str(fig2)]
    if usage_len > 0:
        labels = [f"N{i+1}" for i in range(usage_len)]
        width = 0.38
        x = range(usage_len)
        fig, ax = plt.subplots(figsize=(7.2, 3.5))
        ax.bar(
            [i - width / 2 for i in x],
            [float(v) for v in usage_a[:usage_len]],
            width=width,
            label="ABIDE",
            color=PALETTE["abide"],
            edgecolor="#2c3e50",
            linewidth=0.3,
        )
        ax.bar(
            [i + width / 2 for i in x],
            [float(v) for v in usage_s[:usage_len]],
            width=width,
            label="Sim",
            color=PALETTE["simulation"],
            edgecolor="#2c3e50",
            linewidth=0.3,
        )
        ax.set_xticks(list(x), labels)
        ax.set_title("OS Routing Usage by Network Index", fontweight="bold", pad=10)
        ax.set_ylabel("Usage Ratio")
        ax.legend(frameon=True)
        _save(fig, fig3)
        figures.append(str(fig3))

    md_path = out_dir / "mobse_mainline_summary.md"
    lines: List[str] = []
    lines.append("# MoBSE Mainline Summary")
    lines.append("")
    lines.append("| run_id | n_subjects | os_loss | os_acc | os_f1 | routing_entropy | routing_stability | latency_ms | flops |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in df.iterrows():
        lines.append(
            f"| {r['run_id']} | {int(r['n_subjects'])} | {r['os_loss']:.6g} | {r['os_acc']:.6g} | {r['os_f1']:.6g} | {r['routing_entropy']:.6g} | {r['routing_stability']:.6g} | {r['latency_ms']:.6g} | {r['flops']:.6g} |"
        )
    lines.append("")
    lines.append("## Figures")
    lines.append("- `fig_mobse_mainline_os_quality.png`")
    lines.append("- `fig_mobse_mainline_efficiency.png`")
    if usage_len > 0:
        lines.append("- `fig_mobse_mainline_os_routing_usage.png`")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "summary_csv": str(csv_path),
        "summary_md": str(md_path),
        "figures": figures,
    }
    (out_dir / "mobse_mainline_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
