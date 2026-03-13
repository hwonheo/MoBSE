from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import torch

from mobse.artifacts import ArtifactPaths
from mobse.config import ExperimentConfig
from mobse.io import resolve_template_inputs
from mobse.losses import compute_etth1_loss
from mobse.metrics import classification_metrics, forecasting_metrics, routing_metrics
from mobse.models import build_model
from mobse.profiling import estimate_flops, profile_latency_memory
from mobse.progress import ProgressReporter
from mobse.templates import load_template_bank
from mobse.train import _prepare_dataloaders
from mobse.utils import dump_json, get_device


def _canonical_task(task: str) -> str:
    return "os" if task == "hcp" else task


def _evaluate_loader(model, loader, task: str, device: torch.device, cfg: ExperimentConfig):
    task = _canonical_task(task)
    model.eval()
    losses = []
    preds = []
    gts = []
    routings = []

    with torch.no_grad():
        for batch in loader:
            x = batch["x"].to(device)
            y = batch["y"].to(device)
            out = model(x, task=task)
            if task == "os":
                logits = out["logits"]
                loss = torch.nn.functional.cross_entropy(logits, y)
                pred = torch.argmax(logits, dim=-1)
            else:
                pred = out["pred"]
                loss = compute_etth1_loss(
                    pred=pred,
                    target=y,
                    loss_type=cfg.train.etth1_loss_type,
                    huber_delta=cfg.train.etth1_huber_delta,
                )

            losses.append(float(loss.item()))
            preds.append(pred.detach().cpu())
            gts.append(y.detach().cpu())
            rw = out.get("routing_weights")
            if rw is not None and rw.numel() > 0:
                routings.append(rw.detach().cpu())

    result = {"loss": float(sum(losses) / max(len(losses), 1))}
    if task == "os":
        y_true = torch.cat(gts).numpy().tolist() if gts else []
        y_pred = torch.cat(preds).numpy().tolist() if preds else []
        result.update(classification_metrics(y_true, y_pred))
    else:
        y_true = torch.cat(gts).numpy() if gts else []
        y_pred = torch.cat(preds).numpy() if preds else []
        result.update(forecasting_metrics(y_true, y_pred))

    if routings:
        routing_arr = torch.cat(routings).numpy()
    else:
        routing_arr = torch.tensor([]).numpy()
    result.update(routing_metrics(routing_arr))
    return result


def run_evaluation(
    cfg: ExperimentConfig,
    paths: ArtifactPaths,
    checkpoint_path: Optional[str] = None,
    progress: ProgressReporter | None = None,
) -> Dict[str, object]:
    if progress:
        progress.update(stage="evaluate:setup", message="loading data/model")
    device = get_device(cfg.train.device)
    template_path, windows_path = resolve_template_inputs(cfg)
    os_loaders, etth_loaders = _prepare_dataloaders(cfg, windows_path)

    template_bank = load_template_bank(template_path, cfg.data.os.states)
    template_tensor = torch.tensor(template_bank, dtype=torch.float32, device=device)

    model = build_model(cfg, template_bank=template_tensor).to(device)

    if checkpoint_path is None:
        candidates = sorted(paths.checkpoints.glob("model_seed*_best.pt"))
        if not candidates:
            raise FileNotFoundError("No checkpoint found. Provide --checkpoint path.")
        ckpt_path = candidates[-1]
    else:
        ckpt_path = Path(checkpoint_path)

    ckpt = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])

    if progress:
        progress.update(stage="evaluate:metrics", message="computing task metrics")
    os_eval = _evaluate_loader(model, os_loaders["test"], task="os", device=device, cfg=cfg)
    etth_eval = _evaluate_loader(model, etth_loaders["test"], task="etth1", device=device, cfg=cfg)

    sample_os = next(iter(os_loaders["test"]))["x"].to(device)
    sample_etth = next(iter(etth_loaders["test"]))["x"].to(device)

    if progress:
        progress.update(stage="evaluate:profile", message="profiling latency/memory/flops")
    os_profile = profile_latency_memory(
        model=model,
        dataloader=os_loaders["test"],
        device=device,
        task="os",
        num_batches=cfg.eval.profile_batches,
        warmup=cfg.eval.latency_warmup,
    )
    etth_profile = profile_latency_memory(
        model=model,
        dataloader=etth_loaders["test"],
        device=device,
        task="etth1",
        num_batches=cfg.eval.profile_batches,
        warmup=cfg.eval.latency_warmup,
    )

    os_profile["flops"] = estimate_flops(model=model, sample_x=sample_os, task="os")
    etth_profile["flops"] = estimate_flops(model=model, sample_x=sample_etth, task="etth1")

    result = {
        "arch": cfg.model.arch,
        "run_id": cfg.artifacts.run_id,
        "checkpoint": str(ckpt_path),
        "template_path": str(template_path),
        "os": {"metrics": os_eval, "profile": os_profile},
        "etth1": {"metrics": etth_eval, "profile": etth_profile},
    }
    # Backward compatibility key for old report scripts.
    result["hcp"] = result["os"]

    out_path = paths.logs / f"{cfg.eval.output_prefix}_{cfg.model.arch}.json"
    dump_json(result, out_path)
    if progress:
        progress.update(stage="evaluate:done", message=f"saved={out_path}")
    return result
