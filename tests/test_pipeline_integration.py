import subprocess
import sys
from pathlib import Path

import yaml

from mobse.data.synthetic import generate_synthetic_etth1, generate_synthetic_hcp


def run_cmd(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def test_full_pipeline_synthetic(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]

    data_root = tmp_path / "data"
    os_dir = data_root / "os" / "timeseries" / "100"
    etth_csv = data_root / "ETTh1.csv"

    states = ["rest", "wm", "motor", "language", "attention"]
    generate_synthetic_hcp(os_dir, num_subjects=10, states=states, num_nodes=100)
    generate_synthetic_etth1(etth_csv, rows=1200)

    artifacts_dir = tmp_path / "artifacts"
    config = {
        "data": {
            "os": {
                "timeseries_dir": str(data_root / "os" / "timeseries"),
                "subjects_limit": 10,
                "states": states,
                "window_len": 32,
                "stride": 16,
                "train_ratio": 0.7,
                "val_ratio": 0.15,
            },
            "etth1": {
                "csv_path": str(etth_csv),
                "seq_len": 48,
                "pred_len": 12,
                "train_ratio": 0.7,
                "val_ratio": 0.15,
            },
        },
        "template": {
            "atlas_nodes_options": [100],
            "sparsity_levels": [0.2],
            "default_sparsity": 0.2,
        },
        "model": {
            "arch": "mobse",
            "hidden_dim": 16,
            "num_nodes": 100,
            "num_graph_layers": 1,
            "num_experts": 5,
            "routing_k": 2,
            "routing_mode": "soft",
            "etth1_in_dim": 7,
            "etth1_out_dim": 1,
        },
        "train": {
            "tasks": ["os", "etth1"],
            "batch_size": 16,
            "epochs": 1,
            "seeds": [42],
            "device": "cpu",
            "use_amp": False,
        },
        "eval": {
            "profile_batches": 2,
            "latency_warmup": 1,
            "output_prefix": "eval",
        },
        "artifacts": {
            "root_dir": str(artifacts_dir),
            "run_id": "testrun",
        },
    }

    cfg_path = tmp_path / "config.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    run_cmd([sys.executable, "-m", "mobse.cli", "build_templates", "--config", str(cfg_path)], cwd=repo_root)
    run_cmd([sys.executable, "-m", "mobse.cli", "train", "--config", str(cfg_path)], cwd=repo_root)

    ckpt = artifacts_dir / "testrun" / "checkpoints" / "model_seed42_best.pt"
    assert ckpt.exists()

    run_cmd(
        [
            sys.executable,
            "-m",
            "mobse.cli",
            "evaluate",
            "--config",
            str(cfg_path),
            "--checkpoint",
            str(ckpt),
        ],
        cwd=repo_root,
    )

    eval_json = artifacts_dir / "testrun" / "logs" / "eval_mobse.json"
    assert eval_json.exists()

    run_cmd(
        [
            sys.executable,
            "-m",
            "mobse.cli",
            "report",
            "--config",
            str(cfg_path),
            "--eval-glob",
            str(artifacts_dir / "*" / "logs" / "eval_*.json"),
        ],
        cwd=repo_root,
    )

    assert (artifacts_dir / "testrun" / "reports" / "summary_table.csv").exists()
