from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml


def _parse_int_list(value: str) -> List[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def _parse_float_list(value: str) -> List[float]:
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _parse_str_list(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _parse_bool_list(value: str) -> List[bool]:
    out: List[bool] = []
    for x in _parse_str_list(value):
        low = x.lower()
        if low in {"1", "true", "t", "yes", "y"}:
            out.append(True)
        elif low in {"0", "false", "f", "no", "n"}:
            out.append(False)
        else:
            raise ValueError(f"Invalid bool token: {x}")
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(payload: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def _run(cmd: List[str], cwd: Path) -> None:
    print("[run]", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _set(d: Dict[str, Any], *keys: str, value: Any) -> None:
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def _read_eval(eval_path: Path) -> Dict[str, Any]:
    with eval_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _metric(payload: Dict[str, Any], task: str, metric: str, default: float = float("nan")) -> float:
    try:
        return float(payload[task]["metrics"][metric])
    except Exception:
        return default


def _routing_usage(payload: Dict[str, Any], task: str) -> str:
    try:
        usage = payload[task]["metrics"].get("routing_usage", [])
        if isinstance(usage, list):
            return json.dumps([float(x) for x in usage])
        return ""
    except Exception:
        return ""


def _score(payload: Dict[str, Any]) -> float:
    # Higher is better.
    os_acc = float(payload["os"]["metrics"]["accuracy"])
    os_f1 = float(payload["os"]["metrics"]["f1_macro"])
    et_mse = float(payload["etth1"]["metrics"]["mse"])
    os_lat = float(payload["os"]["profile"]["latency_ms_mean"])
    et_lat = float(payload["etth1"]["profile"]["latency_ms_mean"])
    return (os_acc + os_f1) - 0.01 * et_mse - 0.001 * (os_lat + et_lat)


def _template_path(study_id: str, node: int, sparsity: float) -> str:
    return (
        f"artifacts/{study_id}_templates_n{node}/templates/"
        f"atlas{node}_sp{int(sparsity * 100)}_template_bank.npz"
    )


def _windows_path(study_id: str, node: int) -> str:
    return f"artifacts/{study_id}_templates_n{node}/templates/os_windows_nodes{node}.npz"


def _build_template_stores(
    repo_root: Path,
    base_cfg: Dict[str, Any],
    study_id: str,
    nodes: List[int],
    sparsities: List[float],
    cfg_dir: Path,
) -> None:
    for node in nodes:
        cfg = copy.deepcopy(base_cfg)
        _set(cfg, "artifacts", "run_id", value=f"{study_id}_templates_n{node}")
        _set(cfg, "model", "num_nodes", value=node)
        _set(cfg, "template", "atlas_nodes_options", value=[node])
        _set(cfg, "template", "sparsity_levels", value=sparsities)
        _set(cfg, "template", "default_sparsity", value=0.2)
        cfg_path = cfg_dir / f"templates_n{node}.yaml"
        _save_yaml(cfg, cfg_path)
        _run([sys.executable, "-m", "mobse.cli", "build_templates", "--config", str(cfg_path)], cwd=repo_root)


def _run_sweep(
    repo_root: Path,
    base_cfg: Dict[str, Any],
    study_id: str,
    nodes: List[int],
    sparsities: List[float],
    routings: List[str],
    priors: List[bool],
    cfg_dir: Path,
    quick_epochs: int,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for node in nodes:
        for sp in sparsities:
            for routing in routings:
                for prior in priors:
                    run_id = f"{study_id}_n{node}_sp{int(sp*100)}_{routing}_{'prior' if prior else 'noprior'}_s42"
                    cfg = copy.deepcopy(base_cfg)
                    _set(cfg, "artifacts", "run_id", value=run_id)
                    _set(cfg, "model", "num_nodes", value=node)
                    _set(cfg, "model", "routing_mode", value=routing)
                    _set(cfg, "model", "use_template_prior", value=prior)
                    _set(cfg, "template", "default_sparsity", value=sp)
                    _set(cfg, "model", "template_bank_path", value=_template_path(study_id, node, sp))
                    _set(cfg, "model", "os_windows_path", value=_windows_path(study_id, node))
                    _set(cfg, "train", "epochs", value=quick_epochs)
                    _set(cfg, "train", "early_stopping_patience", value=1)
                    _set(cfg, "train", "early_stopping_min_delta", value=0.0005)
                    _set(cfg, "train", "seeds", value=[42])
                    cfg_path = cfg_dir / f"{run_id}.yaml"
                    _save_yaml(cfg, cfg_path)

                    _run([sys.executable, "-m", "mobse.cli", "train", "--config", str(cfg_path)], cwd=repo_root)
                    ckpt = f"artifacts/{run_id}/checkpoints/model_seed42_best.pt"
                    _run(
                        [
                            sys.executable,
                            "-m",
                            "mobse.cli",
                            "evaluate",
                            "--config",
                            str(cfg_path),
                            "--checkpoint",
                            ckpt,
                            "--no-progress",
                        ],
                        cwd=repo_root,
                    )
                    eval_path = repo_root / f"artifacts/{run_id}/logs/eval_mobse.json"
                    payload = _read_eval(eval_path)
                    row = {
                        "run_id": run_id,
                        "nodes": node,
                        "sparsity": sp,
                        "routing_mode": routing,
                        "template_prior": prior,
                        "os_accuracy": float(payload["os"]["metrics"]["accuracy"]),
                        "os_f1_macro": float(payload["os"]["metrics"]["f1_macro"]),
                        "etth1_mae": float(payload["etth1"]["metrics"]["mae"]),
                        "etth1_mse": float(payload["etth1"]["metrics"]["mse"]),
                        "os_latency_ms": float(payload["os"]["profile"]["latency_ms_mean"]),
                        "etth1_latency_ms": float(payload["etth1"]["profile"]["latency_ms_mean"]),
                        "os_flops": float(payload["os"]["profile"]["flops"]),
                        "os_routing_entropy": _metric(payload, "os", "routing_entropy"),
                        "os_routing_stability": _metric(payload, "os", "routing_stability"),
                        "etth1_routing_entropy": _metric(payload, "etth1", "routing_entropy"),
                        "etth1_routing_stability": _metric(payload, "etth1", "routing_stability"),
                        "os_routing_usage": _routing_usage(payload, "os"),
                        "etth1_routing_usage": _routing_usage(payload, "etth1"),
                        "score": _score(payload),
                    }
                    rows.append(row)
                    print("[done]", run_id, row["score"], flush=True)
    return pd.DataFrame(rows)


def _run_balanced3_for_topk(
    repo_root: Path,
    base_cfg: Dict[str, Any],
    study_id: str,
    top_rows: pd.DataFrame,
    cfg_dir: Path,
    bal_epochs: int,
) -> pd.DataFrame:
    out_rows: List[Dict[str, Any]] = []
    for _, row in top_rows.iterrows():
        node = int(row["nodes"])
        sp = float(row["sparsity"])
        routing = str(row["routing_mode"])
        prior = bool(row["template_prior"])
        run_id = f"{study_id}_top_bal3_n{node}_sp{int(sp*100)}_{routing}_{'prior' if prior else 'noprior'}"

        cfg = copy.deepcopy(base_cfg)
        _set(cfg, "artifacts", "run_id", value=run_id)
        _set(cfg, "model", "num_nodes", value=node)
        _set(cfg, "model", "routing_mode", value=routing)
        _set(cfg, "model", "use_template_prior", value=prior)
        _set(cfg, "template", "default_sparsity", value=sp)
        _set(cfg, "model", "template_bank_path", value=_template_path(study_id, node, sp))
        _set(cfg, "model", "os_windows_path", value=_windows_path(study_id, node))
        _set(cfg, "train", "epochs", value=bal_epochs)
        _set(cfg, "train", "early_stopping_patience", value=3)
        _set(cfg, "train", "early_stopping_min_delta", value=0.0005)
        _set(cfg, "train", "seeds", value=[42, 43, 44])
        cfg_path = cfg_dir / f"{run_id}.yaml"
        _save_yaml(cfg, cfg_path)

        _run([sys.executable, "-m", "mobse.cli", "train", "--config", str(cfg_path)], cwd=repo_root)
        for seed in [42, 43, 44]:
            ckpt = f"artifacts/{run_id}/checkpoints/model_seed{seed}_best.pt"
            _run(
                [
                    sys.executable,
                    "-m",
                    "mobse.cli",
                    "evaluate",
                    "--config",
                    str(cfg_path),
                    "--checkpoint",
                    ckpt,
                    "--no-progress",
                ],
                cwd=repo_root,
            )
            src = repo_root / f"artifacts/{run_id}/logs/eval_mobse.json"
            dst = repo_root / f"artifacts/{run_id}/logs/eval_seed{seed}_mobse.json"
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            payload = _read_eval(dst)
            out_rows.append(
                {
                    "run_id": run_id,
                    "seed": seed,
                    "nodes": node,
                    "sparsity": sp,
                    "routing_mode": routing,
                    "template_prior": prior,
                    "os_accuracy": float(payload["os"]["metrics"]["accuracy"]),
                    "os_f1_macro": float(payload["os"]["metrics"]["f1_macro"]),
                    "etth1_mae": float(payload["etth1"]["metrics"]["mae"]),
                    "etth1_mse": float(payload["etth1"]["metrics"]["mse"]),
                    "os_latency_ms": float(payload["os"]["profile"]["latency_ms_mean"]),
                    "etth1_latency_ms": float(payload["etth1"]["profile"]["latency_ms_mean"]),
                    "os_flops": float(payload["os"]["profile"]["flops"]),
                    "os_routing_entropy": _metric(payload, "os", "routing_entropy"),
                    "os_routing_stability": _metric(payload, "os", "routing_stability"),
                    "etth1_routing_entropy": _metric(payload, "etth1", "routing_entropy"),
                    "etth1_routing_stability": _metric(payload, "etth1", "routing_stability"),
                    "os_routing_usage": _routing_usage(payload, "os"),
                    "etth1_routing_usage": _routing_usage(payload, "etth1"),
                }
            )

        _run(
            [
                sys.executable,
                "-m",
                "mobse.cli",
                "report",
                "--config",
                str(cfg_path),
                "--eval-glob",
                f"artifacts/{run_id}/logs/eval_seed*_mobse.json",
                "--no-progress",
            ],
            cwd=repo_root,
        )
    return pd.DataFrame(out_rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase-2 ablation runner")
    ap.add_argument("--config", required=True, help="Base config path")
    ap.add_argument("--study-id", required=True, help="Study id prefix")
    ap.add_argument("--quick-epochs", type=int, default=6)
    ap.add_argument("--bal-epochs", type=int, default=12)
    ap.add_argument("--nodes", default="100,200", help="Comma-separated node sizes, e.g. 100,200")
    ap.add_argument("--sparsities", default="0.1,0.2,0.3", help="Comma-separated sparsity values")
    ap.add_argument("--routings", default="soft,hard", help="Comma-separated routing modes")
    ap.add_argument("--priors", default="true,false", help="Comma-separated booleans for template prior")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = Path(args.config)
    base_cfg = _load_yaml(cfg_path)

    nodes = _parse_int_list(args.nodes)
    sparsities = _parse_float_list(args.sparsities)
    routings = _parse_str_list(args.routings)
    priors = _parse_bool_list(args.priors)

    out_root = repo_root / "artifacts" / f"{args.study_id}_summary"
    out_reports = out_root / "reports"
    cfg_dir = out_root / "configs"
    out_reports.mkdir(parents=True, exist_ok=True)
    cfg_dir.mkdir(parents=True, exist_ok=True)

    _build_template_stores(
        repo_root=repo_root,
        base_cfg=base_cfg,
        study_id=args.study_id,
        nodes=nodes,
        sparsities=sparsities,
        cfg_dir=cfg_dir,
    )

    sweep = _run_sweep(
        repo_root=repo_root,
        base_cfg=base_cfg,
        study_id=args.study_id,
        nodes=nodes,
        sparsities=sparsities,
        routings=routings,
        priors=priors,
        cfg_dir=cfg_dir,
        quick_epochs=args.quick_epochs,
    )
    sweep = sweep.sort_values("score", ascending=False).reset_index(drop=True)
    sweep.to_csv(out_reports / "phase2_sweep_seed42.csv", index=False)

    top3 = sweep.head(3)
    top3.to_csv(out_reports / "phase2_top3_seed42.csv", index=False)
    bal3 = _run_balanced3_for_topk(
        repo_root=repo_root,
        base_cfg=base_cfg,
        study_id=args.study_id,
        top_rows=top3,
        cfg_dir=cfg_dir,
        bal_epochs=args.bal_epochs,
    )
    bal3.to_csv(out_reports / "phase2_top3_bal3_seed_metrics.csv", index=False)

    bal3_summary = (
        bal3.groupby(["run_id", "nodes", "sparsity", "routing_mode", "template_prior"], as_index=False)
        .agg(
            os_accuracy_mean=("os_accuracy", "mean"),
            os_accuracy_std=("os_accuracy", "std"),
            os_f1_macro_mean=("os_f1_macro", "mean"),
            os_f1_macro_std=("os_f1_macro", "std"),
            etth1_mae_mean=("etth1_mae", "mean"),
            etth1_mae_std=("etth1_mae", "std"),
            etth1_mse_mean=("etth1_mse", "mean"),
            etth1_mse_std=("etth1_mse", "std"),
            os_latency_ms_mean=("os_latency_ms", "mean"),
            etth1_latency_ms_mean=("etth1_latency_ms", "mean"),
            os_flops_mean=("os_flops", "mean"),
            os_routing_entropy_mean=("os_routing_entropy", "mean"),
            os_routing_entropy_std=("os_routing_entropy", "std"),
            os_routing_stability_mean=("os_routing_stability", "mean"),
            os_routing_stability_std=("os_routing_stability", "std"),
            etth1_routing_entropy_mean=("etth1_routing_entropy", "mean"),
            etth1_routing_entropy_std=("etth1_routing_entropy", "std"),
            etth1_routing_stability_mean=("etth1_routing_stability", "mean"),
            etth1_routing_stability_std=("etth1_routing_stability", "std"),
        )
        .sort_values(["os_accuracy_mean", "os_f1_macro_mean"], ascending=False)
    )
    bal3_summary.to_csv(out_reports / "phase2_top3_bal3_summary.csv", index=False)

    manifest = {
        "study_id": args.study_id,
        "source_config": str(cfg_path),
        "sweep_seed42": str(out_reports / "phase2_sweep_seed42.csv"),
        "top3_seed42": str(out_reports / "phase2_top3_seed42.csv"),
        "top3_bal3_seed_metrics": str(out_reports / "phase2_top3_bal3_seed_metrics.csv"),
        "top3_bal3_summary": str(out_reports / "phase2_top3_bal3_summary.csv"),
        "config_dir": str(cfg_dir),
    }
    (out_reports / "phase2_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
