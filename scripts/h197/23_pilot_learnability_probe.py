#!/usr/bin/env python3
"""pilot fit 이 chance 에 머무는 이유를 가른다 — 배선 결함인가 표본 크기인가.

pilot 기술 검증(계획서 §4-2)에서 inner validation BA 가 정확히 0.5 로 나왔다.
그것만으로는 두 가지를 구분할 수 없다.

* **배선 결함** — label 이 손실에 닿지 않거나 입력이 뭉개져 어떤 자료로도 못 배운다.
* **표본 크기** — 자료에 신호가 있어도 13명/104창으로는 못 배운다.

가르는 방법은 둘이다.

1. **학습 집합에서의 성능.** 학습 자료조차 맞히지 못하면 배선을 의심한다.
2. **같은 창 자질의 선형 기준선.** FC Fisher-z 로 logistic regression 을 돌려
   train→val 을 본다. 선형 모형이 쉽게 가르면 신경망 쪽을 의심하고, 선형도
   못 가르면 이 규모의 한계로 읽는다.

**이 스크립트는 가설 검정이 아니다.** pilot 은 계획서 §4-2 의 기술 검증용이며
주 결과로 쓰지 않는다.

Usage:
    python scripts/h197/23_pilot_learnability_probe.py \
        --splits <folds.json> --rest-manifest <...> \
        --task-manifests <emo.jsonl> <wm.jsonl> \
        --outer-fold 0 --inner-fold 0 --out <report.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mobse.v2 import fitting as FIT                                  # noqa: E402
from mobse.v2 import templates as TPL                                # noqa: E402


def probe_linear(train: FIT.EncodedSet, evaluate: FIT.EncodedSet,
                 transform: FIT.FoldTransform, train_refs, eval_refs,
                 seed: int = 0) -> Dict[str, Any]:
    """같은 창의 FC Fisher-z 로 logistic regression 기준선을 만든다."""
    from sklearn.linear_model import LogisticRegression
    from mobse.v2 import features as F

    def z_of(refs):
        arrays = [FIT.read_window(r, verify=False) for r in refs]
        _, z = F.stack_window_features(arrays)
        return z

    ztr, zev = z_of(train_refs), z_of(eval_refs)
    clf = LogisticRegression(max_iter=5000, C=1.0, random_state=seed).fit(ztr, train.y)
    out = {}
    for name, z, refs, y in (("train", ztr, train_refs, train.y),
                             ("val", zev, eval_refs, evaluate.y)):
        p1 = clf.predict_proba(z)[:, 1]
        rp = FIT.run_probabilities(refs, p1)
        out[name] = {
            "window_accuracy": float(((p1 >= 0.5).astype(int) == y).mean()),
            "balanced_accuracy": FIT._balanced_accuracy_from_runs(rp),
            "n_windows": int(len(y)),
        }
    out["n_features"] = int(ztr.shape[1])
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--splits", required=True, type=Path)
    ap.add_argument("--rest-manifest", required=True, type=Path)
    ap.add_argument("--task-manifests", required=True, type=Path, nargs="+")
    ap.add_argument("--outer-fold", type=int, default=0)
    ap.add_argument("--inner-fold", type=int, default=0)
    ap.add_argument("--cell", default="A")
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--model-seed", type=int, default=42)
    ap.add_argument("--max-epochs", type=int, default=50)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv[1:])

    folds = json.loads(args.splits.read_text(encoding="utf-8"))
    fold = FIT.resolve_fold_subjects(folds, args.outer_fold, args.inner_fold)
    rest = FIT.refs_from_extract_manifest(args.rest_manifest, labelled=False)
    task_refs: List[FIT.WindowRef] = []
    for mp in args.task_manifests:
        task_refs += FIT.refs_from_extract_manifest(mp, labelled=True)

    transform = FIT.fit_fold_transform(
        rest, fold.train, bank_seed=TPL.bank_seed(args.outer_fold, args.inner_fold),
        verify=False)
    train_refs = FIT.select_refs(task_refs, fold.train)
    eval_refs = FIT.select_refs(task_refs, fold.evaluate)
    train_set = FIT.encode_windows(train_refs, transform, verify=False)
    eval_set = FIT.encode_windows(eval_refs, transform, verify=False)

    result, model = FIT.train_fold(
        train_set, eval_set, transform, cell=args.cell, config_id=args.config_id,
        model_seed=args.model_seed, fold=fold, device=args.device,
        max_epochs=args.max_epochs)

    import torch

    dev = torch.device(args.device)
    train_probs = FIT._forward_probs(
        model, torch.as_tensor(train_set.x).to(dev),
        torch.as_tensor(train_set.pca).to(dev), batch_size=32)
    train_run = FIT.run_probabilities(train_refs, train_probs)

    payload = {
        "schema_version": "pilot_learnability_probe_v1",
        "not_a_hypothesis_test": ("pilot 은 계획서 §4-2 의 기술 검증이다. "
                                  "주 결과로 쓰지 않는다"),
        "fold": {"outer": args.outer_fold, "inner": args.inner_fold,
                 "n_train_subjects": len(fold.train),
                 "n_eval_subjects": len(fold.evaluate),
                 "n_train_windows": len(train_set), "n_eval_windows": len(eval_set)},
        "network": {
            "cell": args.cell, "config_id": args.config_id,
            "best_epoch": result.best_epoch, "epochs_run": result.epochs_run,
            "val_losses": result.val_losses,
            "train_window_accuracy": float(
                ((train_probs >= 0.5).astype(int) == train_set.y).mean()),
            "train_balanced_accuracy": FIT._balanced_accuracy_from_runs(train_run),
            "val_balanced_accuracy": result.eval_balanced_accuracy,
            "val_loss": result.eval_loss,
            "p_class1_train": {"min": float(train_probs.min()),
                               "max": float(train_probs.max()),
                               "mean": float(train_probs.mean()),
                               "sd": float(train_probs.std())},
        },
        "linear_baseline": probe_linear(train_set, eval_set, transform,
                                        train_refs, eval_refs),
        "transform": result.transform,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("fold", "network", "linear_baseline")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
