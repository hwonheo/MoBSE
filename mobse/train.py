from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import torch
import torch.nn as nn

from mobse.artifacts import ArtifactPaths
from mobse.config import ExperimentConfig
from mobse.data import create_etth1_dataloaders, create_os_dataloaders
from mobse.io import resolve_template_inputs
from mobse.losses import compute_etth1_loss
from mobse.metrics import classification_metrics, forecasting_metrics, routing_metrics
from mobse.models import build_model
from mobse.progress import ProgressReporter
from mobse.templates import load_template_bank
from mobse.utils import dump_json, get_device, set_seed


def _cycle(loader: Iterable):
    while True:
        for item in loader:
            yield item


def _canonical_task(task: str) -> str:
    return "os" if task == "hcp" else task


def _prepare_dataloaders(cfg: ExperimentConfig, windows_path: Path):
    os_loaders = create_os_dataloaders(
        npz_path=windows_path,
        batch_size=cfg.train.batch_size,
        train_ratio=cfg.data.os.train_ratio,
        val_ratio=cfg.data.os.val_ratio,
        seed=cfg.data.os.random_seed,
    )
    etth_loaders = create_etth1_dataloaders(
        csv_path=cfg.data.etth1.csv_path,
        target_col=cfg.data.etth1.target_col,
        seq_len=cfg.data.etth1.seq_len,
        pred_len=cfg.data.etth1.pred_len,
        train_ratio=cfg.data.etth1.train_ratio,
        val_ratio=cfg.data.etth1.val_ratio,
        batch_size=cfg.train.batch_size,
    )

    sample_os = next(iter(os_loaders["train"]))["x"]
    sample_etth = next(iter(etth_loaders["train"]))["x"]
    cfg.model.num_nodes = int(sample_os.shape[-1])
    cfg.model.etth1_in_dim = int(sample_etth.shape[-1])
    cfg.model.os_num_classes = len(cfg.data.os.states)
    return os_loaders, etth_loaders


def _forward_loss(model, batch, task: str, device: torch.device, cfg: ExperimentConfig):
    task = _canonical_task(task)
    x = batch["x"].to(device)
    y = batch["y"].to(device)
    out = model(x, task=task)
    if task == "os":
        logits = out["logits"]
        loss = nn.CrossEntropyLoss()(logits, y)
        pred = torch.argmax(logits, dim=-1)
        return loss, pred, y, out.get("routing_weights")

    pred = out["pred"]
    loss = compute_etth1_loss(
        pred=pred,
        target=y,
        loss_type=cfg.train.etth1_loss_type,
        huber_delta=cfg.train.etth1_huber_delta,
    )
    return loss, pred, y, out.get("routing_weights")


def _evaluate_task(model, loader, task: str, device: torch.device, cfg: ExperimentConfig):
    task = _canonical_task(task)
    model.eval()
    losses = []
    preds = []
    gts = []
    routings = []

    with torch.no_grad():
        for batch in loader:
            loss, pred, gt, routing = _forward_loss(model, batch, task, device, cfg)
            losses.append(float(loss.item()))
            preds.append(pred.detach().cpu())
            gts.append(gt.detach().cpu())
            if routing is not None and routing.numel() > 0:
                routings.append(routing.detach().cpu())

    summary = {"loss": float(np.mean(losses) if losses else 0.0)}
    if task == "os":
        y_true = torch.cat(gts).numpy().tolist() if gts else []
        y_pred = torch.cat(preds).numpy().tolist() if preds else []
        summary.update(classification_metrics(y_true, y_pred))
    else:
        y_true = torch.cat(gts).numpy() if gts else np.array([])
        y_pred = torch.cat(preds).numpy() if preds else np.array([])
        summary.update(forecasting_metrics(y_true, y_pred))

    if routings:
        routing_arr = torch.cat(routings).numpy()
    else:
        routing_arr = np.array([])
    summary.update(routing_metrics(routing_arr))
    return summary


def _estimate_task_loss_scales(
    model: nn.Module,
    cfg: ExperimentConfig,
    os_loader,
    etth_loader,
    tasks: list[str],
    device: torch.device,
) -> Dict[str, float]:
    num_batches = max(1, int(cfg.train.task_loss_norm_batches))
    scales: Dict[str, float] = {"os": 1.0, "etth1": 1.0}
    loader_map = {"os": os_loader, "etth1": etth_loader}
    was_training = model.training
    model.eval()

    with torch.no_grad():
        for task in tasks:
            losses = []
            for i, batch in enumerate(loader_map[task]):
                if i >= num_batches:
                    break
                loss, _, _, _ = _forward_loss(model, batch, task, device, cfg)
                losses.append(float(loss.item()))
            if losses:
                scales[task] = float(max(np.mean(losses), 1e-6))

    if was_training:
        model.train()
    return scales


def _compute_val_score(
    cfg: ExperimentConfig,
    tasks: list[str],
    val_os: Dict[str, float],
    val_etth: Dict[str, float],
    task_loss_scales: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    mode = str(cfg.train.selection_metric).strip().lower()
    if mode not in {"raw_loss", "weighted_raw_loss", "weighted_normalized_loss"}:
        raise ValueError(
            "train.selection_metric must be one of "
            "['raw_loss', 'weighted_raw_loss', 'weighted_normalized_loss']"
        )

    components: Dict[str, float] = {}
    if "os" in tasks:
        os_raw = float(val_os["loss"])
        if mode == "raw_loss":
            components["os"] = os_raw
        elif mode == "weighted_raw_loss":
            components["os"] = cfg.train.os_loss_weight * os_raw
        else:
            components["os"] = cfg.train.os_loss_weight * (os_raw / task_loss_scales["os"])

    if "etth1" in tasks:
        et_raw = float(val_etth["loss"])
        if mode == "raw_loss":
            components["etth1"] = et_raw
        elif mode == "weighted_raw_loss":
            components["etth1"] = cfg.train.etth1_loss_weight * et_raw
        else:
            components["etth1"] = cfg.train.etth1_loss_weight * (et_raw / task_loss_scales["etth1"])

    return float(sum(components.values())), components


def _train_one_seed(
    cfg: ExperimentConfig,
    paths: ArtifactPaths,
    template_path: Path,
    windows_path: Path,
    seed: int,
    seed_index: int,
    total_seeds: int,
    progress: ProgressReporter | None = None,
) -> Tuple[Path, Dict[str, object]]:
    set_seed(seed)
    device = get_device(cfg.train.device)

    os_loaders, etth_loaders = _prepare_dataloaders(cfg, windows_path=windows_path)

    template_bank = load_template_bank(template_path, cfg.data.os.states)
    template_tensor = torch.tensor(template_bank, dtype=torch.float32, device=device)

    model = build_model(cfg, template_bank=template_tensor).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.train.learning_rate,
        weight_decay=cfg.train.weight_decay,
    )
    scaler = torch.amp.GradScaler(device=device.type, enabled=(cfg.train.use_amp and device.type == "cuda"))

    tasks = [_canonical_task(task) for task in cfg.train.tasks if _canonical_task(task) in {"os", "etth1"}]
    if not tasks:
        raise ValueError("train.tasks must include at least one of ['os', 'etth1']")

    os_iter = _cycle(os_loaders["train"])
    etth_iter = _cycle(etth_loaders["train"])
    steps_per_epoch = max(
        len(os_loaders["train"]) if "os" in tasks else 0,
        len(etth_loaders["train"]) if "etth1" in tasks else 0,
    )
    steps_per_epoch = max(1, steps_per_epoch)

    best_score = float("inf")
    best_ckpt = paths.checkpoints / f"model_seed{seed}_best.pt"
    best_epoch = 0
    epochs_without_improvement = 0
    history = []
    task_loss_scales = (
        _estimate_task_loss_scales(
            model=model,
            cfg=cfg,
            os_loader=os_loaders["train"],
            etth_loader=etth_loaders["train"],
            tasks=tasks,
            device=device,
        )
        if cfg.train.normalize_task_losses and len(tasks) > 1
        else {"os": 1.0, "etth1": 1.0}
    )

    for epoch in range(1, cfg.train.epochs + 1):
        model.train()
        running_raw = {"os": [], "etth1": []}
        running_norm = {"os": [], "etth1": []}

        for _ in range(steps_per_epoch):
            optimizer.zero_grad(set_to_none=True)
            total_loss = 0.0

            for task in tasks:
                batch = next(os_iter) if task == "os" else next(etth_iter)
                weight = cfg.train.os_loss_weight if task == "os" else cfg.train.etth1_loss_weight
                with torch.amp.autocast(device_type=device.type, enabled=(cfg.train.use_amp and device.type == "cuda")):
                    loss, _, _, _ = _forward_loss(model, batch, task, device, cfg)
                    normalized = loss / task_loss_scales[task]
                    weighted = weight * normalized
                total_loss = total_loss + weighted
                running_raw[task].append(float(loss.item()))
                running_norm[task].append(float(normalized.item()))

            scaler.scale(total_loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=cfg.train.grad_clip_norm)
            scaler.step(optimizer)
            scaler.update()

        val_os = (
            _evaluate_task(model, os_loaders["val"], task="os", device=device, cfg=cfg)
            if "os" in tasks
            else {"loss": 0.0}
        )
        val_etth = (
            _evaluate_task(model, etth_loaders["val"], task="etth1", device=device, cfg=cfg)
            if "etth1" in tasks
            else {"loss": 0.0}
        )
        val_score, val_score_components = _compute_val_score(
            cfg=cfg,
            tasks=tasks,
            val_os=val_os,
            val_etth=val_etth,
            task_loss_scales=task_loss_scales,
        )

        epoch_log = {
            "epoch": epoch,
            "train_os_loss": float(np.mean(running_raw["os"]) if running_raw["os"] else 0.0),
            "train_etth1_loss": float(np.mean(running_raw["etth1"]) if running_raw["etth1"] else 0.0),
            "train_os_loss_norm": float(np.mean(running_norm["os"]) if running_norm["os"] else 0.0),
            "train_etth1_loss_norm": float(np.mean(running_norm["etth1"]) if running_norm["etth1"] else 0.0),
            "val_os": val_os,
            "val_etth1": val_etth,
            "val_os_loss_norm": float(val_os["loss"] / task_loss_scales["os"]),
            "val_etth1_loss_norm": float(val_etth["loss"] / task_loss_scales["etth1"]),
            "val_score_components": val_score_components,
            "val_score": float(val_score),
        }
        # Backward compatibility keys for old analysis scripts.
        epoch_log["train_hcp_loss"] = epoch_log["train_os_loss"]
        epoch_log["val_hcp"] = val_os
        history.append(epoch_log)
        if progress:
            progress.update(
                stage="train:epoch",
                current=epoch,
                total=cfg.train.epochs,
                message=(
                    f"seed={seed} ({seed_index}/{total_seeds}) "
                    f"val_score={val_score:.5f} "
                    f"train_os={epoch_log['train_os_loss']:.5f} "
                    f"train_etth1={epoch_log['train_etth1_loss']:.5f} "
                    f"val_os={val_os['loss']:.5f} "
                    f"val_etth1={val_etth['loss']:.5f}"
                ),
            )

        improved = val_score < (best_score - float(cfg.train.early_stopping_min_delta))
        if improved:
            best_score = val_score
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(
                {
                    "seed": seed,
                    "model_state_dict": model.state_dict(),
                    "cfg_model": vars(cfg.model),
                    "cfg_data": {
                        "states": cfg.data.os.states,
                        "pred_len": cfg.data.etth1.pred_len,
                    },
                    "template_path": str(template_path),
                },
                best_ckpt,
            )
        else:
            epochs_without_improvement += 1

        if (
            cfg.train.early_stopping_patience > 0
            and epochs_without_improvement >= cfg.train.early_stopping_patience
        ):
            if progress:
                progress.update(
                    stage="train:early_stop",
                    message=(
                        f"seed={seed} best_epoch={best_epoch} "
                        f"patience={cfg.train.early_stopping_patience}"
                    ),
                )
            break

    if best_ckpt.exists():
        best_payload = torch.load(best_ckpt, map_location=device)
        model.load_state_dict(best_payload["model_state_dict"])

    test_os = (
        _evaluate_task(model, os_loaders["test"], task="os", device=device, cfg=cfg)
        if "os" in tasks
        else {}
    )
    test_etth = (
        _evaluate_task(model, etth_loaders["test"], task="etth1", device=device, cfg=cfg)
        if "etth1" in tasks
        else {}
    )

    summary = {
        "seed": seed,
        "best_val_score": best_score,
        "best_epoch": best_epoch,
        "test_os": test_os,
        "test_etth1": test_etth,
        "history": history,
        "checkpoint": str(best_ckpt),
        "task_loss_scales": task_loss_scales,
        "selection_metric": cfg.train.selection_metric,
        "etth1_loss_type": cfg.train.etth1_loss_type,
    }
    summary["test_hcp"] = test_os
    dump_json(summary, paths.logs / f"train_seed{seed}.json")
    return best_ckpt, summary


def run_training(
    cfg: ExperimentConfig,
    paths: ArtifactPaths,
    progress: ProgressReporter | None = None,
) -> Dict[str, object]:
    template_path, windows_path = resolve_template_inputs(cfg)
    total_seeds = len(cfg.train.seeds)

    summaries = []
    checkpoints = []
    for seed_idx, seed in enumerate(cfg.train.seeds, start=1):
        if progress:
            progress.update(
                stage="train:seed",
                current=seed_idx,
                total=total_seeds,
                message=f"seed={seed}",
            )
        ckpt, summary = _train_one_seed(
            cfg=cfg,
            paths=paths,
            template_path=template_path,
            windows_path=windows_path,
            seed=seed,
            seed_index=seed_idx,
            total_seeds=total_seeds,
            progress=progress,
        )
        checkpoints.append(str(ckpt))
        summaries.append(summary)

    result = {
        "template_path": str(template_path),
        "windows_path": str(windows_path),
        "checkpoints": checkpoints,
        "seeds": summaries,
    }
    dump_json(result, paths.logs / "train_summary.json")
    return result
