from __future__ import annotations

import time
from typing import Dict

import numpy as np
import torch


class _TaskWrapper(torch.nn.Module):
    def __init__(self, model: torch.nn.Module, task: str):
        super().__init__()
        self.model = model
        self.task = task

    def forward(self, x: torch.Tensor):
        out = self.model(x, task=self.task)
        return out.get("logits", out.get("pred"))


def estimate_flops(model: torch.nn.Module, sample_x: torch.Tensor, task: str) -> float:
    try:
        from thop import profile  # type: ignore

        wrapper = _TaskWrapper(model, task=task)
        flops, _ = profile(wrapper, inputs=(sample_x,), verbose=False)
        return float(flops)
    except Exception:
        params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        # Fallback heuristic if FLOPs tooling is unavailable.
        return float(params * sample_x.shape[0])


def profile_latency_memory(
    model: torch.nn.Module,
    dataloader,
    device: torch.device,
    task: str,
    num_batches: int,
    warmup: int,
) -> Dict[str, float]:
    model.eval()
    latencies = []
    seen = 0
    peak_mem_bytes = 0

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    elif device.type == "mps" and hasattr(torch, "mps"):
        try:
            torch.mps.empty_cache()
        except Exception:
            pass

    with torch.no_grad():
        for batch in dataloader:
            x = batch["x"].to(device)

            if seen < warmup:
                _ = model(x, task=task)
                if device.type == "cuda":
                    torch.cuda.synchronize(device)
                elif device.type == "mps" and hasattr(torch, "mps"):
                    try:
                        peak_mem_bytes = max(peak_mem_bytes, int(torch.mps.current_allocated_memory()))
                    except Exception:
                        pass
                seen += 1
                continue

            start = time.perf_counter()
            _ = model(x, task=task)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            elif device.type == "mps" and hasattr(torch, "mps"):
                try:
                    peak_mem_bytes = max(peak_mem_bytes, int(torch.mps.current_allocated_memory()))
                except Exception:
                    pass
            end = time.perf_counter()
            latencies.append((end - start) * 1000.0)

            seen += 1
            if len(latencies) >= num_batches:
                break

    if not latencies:
        latencies = [0.0]

    if device.type == "cuda":
        peak_mem = torch.cuda.max_memory_allocated(device) / (1024 * 1024)
    elif device.type == "mps":
        peak_mem = peak_mem_bytes / (1024 * 1024)
    else:
        peak_mem = 0.0

    return {
        "latency_ms_mean": float(np.mean(latencies)),
        "latency_ms_std": float(np.std(latencies)),
        "peak_memory_mb": float(peak_mem),
    }
