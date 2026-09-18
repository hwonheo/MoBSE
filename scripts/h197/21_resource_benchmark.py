#!/usr/bin/env python3
"""자원 예산의 **측정** 부분 — 지침서 WI-03, 계획서 §7·§9.

계획서 §9 는 "동일 장비/batch/precision에서 FC·PCA 포함 end-to-end latency,
모델 latency, peak memory, parameter 수를 분리한다. 지원되지 않는 FLOPs 는
NA 다"라고 정한다. 그대로 분리해서 잰다.

**이 스크립트는 합성 자료로 잰다.** 계획서 §7 의 "pilot에서 peak memory·시간을
측정해 자원 계획을 만든다"를 대신하지 않는다. pilot fit 이 아직 구현되지 않아
그 전에 규모를 잡기 위한 것이고, 보고서에 그 한계를 적는다. 크기(창 수·batch·
epoch)는 실제 분할에서 가져오므로 규모 자체는 실측에 가깝다.

Usage:
    python scripts/h197/21_resource_benchmark.py --out /tmp/resource.json \
        [--device cuda] [--repeats 5]
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import features as F                                    # noqa: E402
from mobse.v2 import templates as T                                   # noqa: E402
from mobse.v2.models import CELL_SPEC, ModelConfig, build_cell        # noqa: E402
from mobse.v2.train import BATCH_SIZE, MAX_EPOCHS, fit_budget         # noqa: E402

N_ROI = 100
N_SAMPLES = 30


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize()


def time_it(fn, repeats: int, device: torch.device) -> Dict[str, float]:
    """`fn` 을 여러 번 재고 중앙값·최솟값을 돌려준다. 첫 회는 warm-up 으로 버린다."""
    fn()
    _sync(device)
    times: List[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        _sync(device)
        times.append(time.perf_counter() - t0)
    return {"median_s": float(np.median(times)), "min_s": float(min(times)),
            "max_s": float(max(times)), "repeats": repeats}


def synth_windows(rng: np.random.Generator, n: int) -> np.ndarray:
    """``(n, n_roi, n_samples)`` 합성 창. z-score 된 ROI 시계열 모양을 흉내낸다."""
    x = rng.standard_normal((n, N_ROI, N_SAMPLES))
    return (x - x.mean(axis=2, keepdims=True)) / x.std(axis=2, keepdims=True)


def bench_transform(rng: np.random.Generator, n_rest: int,
                    repeats: int) -> Dict[str, Any]:
    """FC → Fisher-z → scaler/PCA → K-means → bank 까지 한 번 적합하는 비용."""
    windows = synth_windows(rng, n_rest)
    cpu = torch.device("cpu")

    def fc_only():
        F.stack_window_features(list(windows))

    fc = time_it(fc_only, repeats, cpu)
    correlations, feats = F.stack_window_features(list(windows))
    # 창 하나당 subject 하나가 아니라, subject 당 rest 창 4개다.
    fit_subjects = [f"ds002785:sub-{i // 4:04d}" for i in range(n_rest)]

    def transform_fit():
        F.fit_transform_on_training_rest(feats, fit_subjects)

    tr = time_it(transform_fit, repeats, cpu)
    frozen = F.fit_transform_on_training_rest(feats, fit_subjects)
    pca = frozen.transform(feats)

    def bank_fit():
        T.build_bank(correlations, pca, fit_subjects, seed=T.bank_seed(0, 0))

    bank = time_it(bank_fit, repeats, cpu)
    return {"n_rest_windows": n_rest, "fc_fisherz": fc,
            "scaler_pca_kmeans": tr, "bank_build": bank,
            "total_median_s": fc["median_s"] + tr["median_s"] + bank["median_s"]}


def bench_cells(rng: np.random.Generator, n_train: int, device: torch.device,
                repeats: int) -> Dict[str, Any]:
    """cell 별 parameter 수, 1 epoch 학습 시간, 추론 latency, peak memory."""
    cfg = ModelConfig()
    brain = torch.as_tensor(
        np.stack([np.eye(N_ROI) for _ in range(cfg.n_experts)]), dtype=torch.float32)
    null = brain.clone()

    x = torch.as_tensor(synth_windows(rng, n_train), dtype=torch.float32)
    pca = torch.as_tensor(rng.standard_normal((n_train, cfg.pca_dim)), dtype=torch.float32)
    y = torch.as_tensor(rng.integers(0, 2, n_train), dtype=torch.long)
    x, pca, y = x.to(device), pca.to(device), y.to(device)

    out: Dict[str, Any] = {}
    for cell in sorted(CELL_SPEC):
        model = build_cell(cell, cfg, brain, null).to(device)
        opt = torch.optim.AdamW(model.parameters())
        lossf = torch.nn.CrossEntropyLoss()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)

        def one_epoch():
            model.train()
            order = torch.randperm(n_train, device=device)
            for s in range(0, n_train, BATCH_SIZE):
                idx = order[s:s + BATCH_SIZE]
                opt.zero_grad(set_to_none=True)
                res = model(x[idx], pca[idx])
                loss = lossf(res["logits"], y[idx])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()

        epoch = time_it(one_epoch, repeats, device)

        def infer():
            model.eval()
            with torch.no_grad():
                for s in range(0, n_train, BATCH_SIZE):
                    model(x[s:s + BATCH_SIZE], pca[s:s + BATCH_SIZE])

        inference = time_it(infer, repeats, device)
        rec: Dict[str, Any] = {
            "trainable_parameters": model.trainable_parameter_count(),
            "bank_is_frozen": model.bank_is_frozen(),
            "epoch": epoch,
            "inference_full_pass": inference,
            "flops": "NA (미지원 — 계획서 §9)",
        }
        if device.type == "cuda":
            rec["peak_gpu_bytes"] = int(torch.cuda.max_memory_allocated(device))
        out[cell] = rec
        del model, opt
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--n-main-pool", type=int, default=126)
    ap.add_argument("--seed", type=int, default=20260918)
    args = ap.parse_args(argv[1:])

    device = torch.device(args.device)
    rng = np.random.Generator(np.random.PCG64(args.seed))

    # 실제 분할에서 오는 크기.
    n_pool = args.n_main_pool
    n_outer_train = round(n_pool * 4 / 5)          # outer train subject
    n_inner_train = round(n_outer_train * 2 / 3)   # inner train subject
    sizes = {
        "main_pool_subjects": n_pool,
        "outer_train_subjects": n_outer_train,
        "inner_train_subjects": n_inner_train,
        "inner_train_windows": n_inner_train * 2 * 4,
        "outer_train_windows": n_outer_train * 2 * 4,
        "outer_train_rest_windows": n_outer_train * 4,
        "batch_size": BATCH_SIZE,
        "max_epochs": MAX_EPOCHS,
    }

    payload: Dict[str, Any] = {
        "schema_version": "resource_benchmark_v1",
        "synthetic": True,
        "does_not_replace": "계획서 §7 — pilot 에서 peak memory·시간을 측정한다",
        "machine": {
            "host": platform.node(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": str(device),
            "gpu": (torch.cuda.get_device_name(device) if device.type == "cuda" else None),
            "precision": "float32 (AMP 미사용)",
        },
        "sizes": sizes,
        "fit_budget": fit_budget(),
        "transform_per_fit": bench_transform(rng, sizes["outer_train_rest_windows"],
                                             args.repeats),
        "cells_inner_scale": bench_cells(rng, sizes["inner_train_windows"], device,
                                         args.repeats),
        "cells_outer_scale": bench_cells(rng, sizes["outer_train_windows"], device,
                                         args.repeats),
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(json.dumps({"out": str(args.out),
                      "fit_budget": payload["fit_budget"],
                      "inner_epoch_median_s": {
                          c: payload["cells_inner_scale"][c]["epoch"]["median_s"]
                          for c in sorted(CELL_SPEC)},
                      "transform_total_s": payload["transform_per_fit"]["total_median_s"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
