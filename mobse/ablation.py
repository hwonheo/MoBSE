from __future__ import annotations

import copy
from itertools import product
from typing import Dict, List

from mobse.artifacts import ArtifactManager
from mobse.config import ExperimentConfig
from mobse.evaluate import run_evaluation
from mobse.train import run_training
from mobse.utils import dump_json


def run_ablation_suite(
    cfg: ExperimentConfig,
    atlas_nodes: List[int],
    sparsities: List[float],
    routing_modes: List[str],
    expert_counts: List[int],
    architectures: List[str],
    template_priors: List[bool],
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []

    for num_nodes, sparsity, routing_mode, n_experts, arch, use_prior in product(
        atlas_nodes, sparsities, routing_modes, expert_counts, architectures, template_priors
    ):
        run_cfg = copy.deepcopy(cfg)
        run_cfg.model.num_nodes = num_nodes
        run_cfg.template.default_sparsity = sparsity
        run_cfg.model.routing_mode = routing_mode
        run_cfg.model.num_experts = n_experts
        run_cfg.model.arch = arch
        run_cfg.model.use_template_prior = use_prior
        run_cfg.artifacts.run_id = (
            f"abl_{arch}_n{num_nodes}_sp{int(sparsity*100)}_rt{routing_mode}_e{n_experts}_prior{int(use_prior)}"
        )

        manager = ArtifactManager(run_cfg)
        paths = manager.ensure_dirs()

        train_result = run_training(run_cfg, paths)
        eval_result = run_evaluation(run_cfg, paths)

        row = {
            "run_id": run_cfg.artifacts.run_id,
            "arch": arch,
            "num_nodes": num_nodes,
            "sparsity": sparsity,
            "routing_mode": routing_mode,
            "num_experts": n_experts,
            "use_template_prior": use_prior,
            "train": train_result,
            "eval": eval_result,
        }
        dump_json(row, paths.logs / "ablation_result.json")
        results.append(row)

    return results
