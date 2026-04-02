from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yaml


def _run(cmd: List[str], cwd: Path) -> None:
    print("[run]", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _load_yaml(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(payload: Dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def _set(d: Dict, *keys: str, value) -> None:
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def _read_eval(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run MoBSE vs legacy model comparison on ds000243 templates.")
    ap.add_argument(
        "--base-config",
        default="configs/2026-04-01/ds000243_rest_templates_100_200_20260401.yaml",
        help="Base config yaml",
    )
    ap.add_argument("--study-id", default="ds000243_modelcomp_20260402", help="Study id prefix for run ids")
    ap.add_argument("--nodes", default="100,200", help="Comma-separated node sizes")
    ap.add_argument("--sparsities", default="0.1,0.2", help="Comma-separated sparsity values")
    ap.add_argument("--seeds", default="42", help="Comma-separated seeds")
    ap.add_argument(
        "--models",
        default="mobse,transformer,sparse_transformer,moe",
        help="Comma-separated model arches",
    )
    ap.add_argument(
        "--template-run-id",
        default="ds000243_rest_templates_100_200_20260401",
        help="Run id that contains canonical template banks for node/sparsity",
    )
    ap.add_argument(
        "--windows100-run-id",
        default="ds000243_rest_templates_100_200_20260401",
        help="Run id that contains os_windows_nodes100.npz",
    )
    ap.add_argument(
        "--windows200-run-id",
        default="ds000243_rest_templates_n200_windows_20260402",
        help="Run id that contains os_windows_nodes200.npz",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Skip runs that already have eval outputs",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    base_cfg_path = repo_root / args.base_config
    base = _load_yaml(base_cfg_path)

    nodes = [int(x.strip()) for x in args.nodes.split(",") if x.strip()]
    sparsities = [float(x.strip()) for x in args.sparsities.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    models = [x.strip() for x in args.models.split(",") if x.strip()]

    cfg_dir = repo_root / "configs" / "2026-04-02" / args.study_id
    cfg_dir.mkdir(parents=True, exist_ok=True)
    out_dir = repo_root / "artifacts" / "current_canonical" / args.study_id / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict] = []
    for model_arch in models:
        for node in nodes:
            for sp in sparsities:
                for seed in seeds:
                    run_id = f"{args.study_id}_{model_arch}_n{node}_sp{int(sp*100)}_s{seed}"
                    logs_dir = repo_root / "artifacts" / "current_canonical" / run_id / "logs"
                    existing_eval = sorted(logs_dir.glob("eval_*.json"))
                    if args.resume and existing_eval:
                        payload = _read_eval(existing_eval[-1])
                        rows.append(
                            {
                                "run_id": run_id,
                                "model_arch": model_arch,
                                "seed": seed,
                                "nodes": node,
                                "sparsity": sp,
                                "checkpoint": payload.get("checkpoint", ""),
                                "template_path": payload.get("template_path", ""),
                                "os_accuracy": float(payload["os"]["metrics"]["accuracy"]),
                                "os_f1_macro": float(payload["os"]["metrics"]["f1_macro"]),
                                "os_latency_ms": float(payload["os"]["profile"]["latency_ms_mean"]),
                                "os_flops": float(payload["os"]["profile"]["flops"]),
                                "os_routing_entropy": float(payload["os"]["metrics"].get("routing_entropy", 0.0)),
                                "os_routing_stability": float(payload["os"]["metrics"].get("routing_stability", 0.0)),
                            }
                        )
                        print("[skip-existing]", run_id, flush=True)
                        continue

                    cfg = copy.deepcopy(base)
                    _set(cfg, "artifacts", "root_dir", value="artifacts/current_canonical")
                    _set(cfg, "artifacts", "run_id", value=run_id)
                    _set(cfg, "model", "arch", value=model_arch)
                    _set(cfg, "model", "num_nodes", value=node)
                    _set(cfg, "template", "default_sparsity", value=sp)
                    _set(cfg, "train", "seeds", value=[seed])
                    _set(cfg, "train", "epochs", value=1)
                    _set(cfg, "train", "tasks", value=["os"])
                    _set(cfg, "train", "device", value="cpu")
                    template_path = (
                        f"artifacts/current_canonical/{args.template_run_id}/templates/"
                        f"atlas{node}_sp{int(sp*100)}_template_bank.npz"
                    )
                    windows_run = args.windows100_run_id if node == 100 else args.windows200_run_id
                    windows_path = (
                        f"artifacts/current_canonical/{windows_run}/templates/os_windows_nodes{node}.npz"
                    )
                    _set(cfg, "model", "template_bank_path", value=template_path)
                    _set(cfg, "model", "os_windows_path", value=windows_path)

                    if model_arch == "mobse":
                        _set(cfg, "model", "num_experts", value=1)
                        _set(cfg, "model", "routing_k", value=1)
                        _set(cfg, "model", "routing_mode", value="soft")
                        _set(cfg, "model", "use_template_prior", value=True)
                    elif model_arch == "moe":
                        _set(cfg, "model", "num_experts", value=4)
                        _set(cfg, "model", "routing_k", value=2)
                        _set(cfg, "model", "routing_mode", value="soft")
                        _set(cfg, "model", "use_template_prior", value=False)
                    else:
                        _set(cfg, "model", "use_template_prior", value=False)

                    cfg_path = cfg_dir / f"{run_id}.yaml"
                    _save_yaml(cfg, cfg_path)

                    _run([sys.executable, "-m", "mobse.cli", "train", "--config", str(cfg_path)], cwd=repo_root)
                    ckpt = repo_root / "artifacts" / "current_canonical" / run_id / "checkpoints" / f"model_seed{seed}_best.pt"
                    _run(
                        [
                            sys.executable,
                            "-m",
                            "mobse.cli",
                            "evaluate",
                            "--config",
                            str(cfg_path),
                            "--checkpoint",
                            str(ckpt),
                            "--no-progress",
                        ],
                        cwd=repo_root,
                    )
                    eval_path = (
                        repo_root
                        / "artifacts"
                        / "current_canonical"
                        / run_id
                        / "logs"
                        / f"eval_{model_arch}.json"
                    )
                    if not eval_path.exists():
                        # fallback for output prefix mismatch
                        logs_dir = repo_root / "artifacts" / "current_canonical" / run_id / "logs"
                        cands = sorted(logs_dir.glob("eval_*.json"))
                        if not cands:
                            raise FileNotFoundError(f"No eval json found under {logs_dir}")
                        eval_path = cands[-1]

                    payload = _read_eval(eval_path)
                    row = {
                        "run_id": run_id,
                        "model_arch": model_arch,
                        "seed": seed,
                        "nodes": node,
                        "sparsity": sp,
                        "checkpoint": payload.get("checkpoint", ""),
                        "template_path": payload.get("template_path", ""),
                        "os_accuracy": float(payload["os"]["metrics"]["accuracy"]),
                        "os_f1_macro": float(payload["os"]["metrics"]["f1_macro"]),
                        "os_latency_ms": float(payload["os"]["profile"]["latency_ms_mean"]),
                        "os_flops": float(payload["os"]["profile"]["flops"]),
                        "os_routing_entropy": float(payload["os"]["metrics"].get("routing_entropy", 0.0)),
                        "os_routing_stability": float(payload["os"]["metrics"].get("routing_stability", 0.0)),
                    }
                    rows.append(row)
                    print("[done]", run_id, flush=True)

    df = pd.DataFrame(rows).sort_values(["model_arch", "nodes", "sparsity", "seed"])
    csv_path = out_dir / "model_comparison_seedwise.csv"
    summary_path = out_dir / "model_comparison_summary.csv"
    md_path = out_dir / "model_comparison_summary.md"
    manifest_path = out_dir / "model_comparison_manifest.json"

    df.to_csv(csv_path, index=False)
    summary = (
        df.groupby(["model_arch", "nodes", "sparsity"], as_index=False)
        .agg(
            os_accuracy_mean=("os_accuracy", "mean"),
            os_f1_mean=("os_f1_macro", "mean"),
            os_latency_ms_mean=("os_latency_ms", "mean"),
            os_flops_mean=("os_flops", "mean"),
        )
        .sort_values(["nodes", "sparsity", "model_arch"])
    )
    summary.to_csv(summary_path, index=False)

    md_lines = [
        "| model_arch | nodes | sparsity | os_accuracy_mean | os_f1_mean | os_latency_ms_mean | os_flops_mean |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, r in summary.iterrows():
        md_lines.append(
            "| {model_arch} | {nodes} | {sparsity:.2f} | {os_accuracy_mean:.6f} | {os_f1_mean:.6f} | {os_latency_ms_mean:.6f} | {os_flops_mean:.2f} |".format(
                **r.to_dict()
            )
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    manifest = {
        "study_id": args.study_id,
        "base_config": args.base_config,
        "models": models,
        "nodes": nodes,
        "sparsities": sparsities,
        "seeds": seeds,
        "rows": int(len(df)),
        "outputs": {
            "seedwise_csv": str(csv_path),
            "summary_csv": str(summary_path),
            "summary_md": str(md_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
