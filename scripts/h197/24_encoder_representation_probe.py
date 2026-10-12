#!/usr/bin/env python3
"""ROI encoder 의 pooled feature 가 신호를 담고 있는지 본다.

`23_pilot_learnability_probe.py` 가 다음을 보였다 — 같은 창의 FC Fisher-z 로
logistic regression 을 돌리면 validation BA 1.00 인데, 계획서 §6 의 신경망은
**학습 집합조차 0.5** 다. 표본 부족으로는 설명되지 않는다. 자기 학습 자료를
못 맞히는 모형은 표본이 적은 것이 아니라 표현이 무너진 것이다.

이 스크립트는 그 지점을 특정한다.

* `pooled` = ROI mean pooling 직후의 32차원. 여기서 두 class 가 갈리는가?
* 갈린다면 문제는 **머리(head)·최적화**, 갈리지 않는다면 **표현(encoder+graph)** 이다.
* 비교로 raw ROI mean/variance 200차원(계획서 §6 의 S 후보 1)도 같이 잰다.

계획서 §6 이 "구조 비교: ROI encoder pooled feature + PCA FC10 fusion MLP" 를
필수 비교로 두었으므로, 이 측정은 사전 계획 안에 있다.

Usage:
    python scripts/h197/24_encoder_representation_probe.py --splits <folds.json> ... --out <json>
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


def _linear_score(xtr, ytr, xev, yev, refs_tr, refs_ev, seed=0) -> Dict[str, Any]:
    """같은 자질에 logistic regression 을 돌려 train/val 성능을 돌려준다."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    sc = StandardScaler().fit(xtr)
    clf = LogisticRegression(max_iter=5000, random_state=seed).fit(sc.transform(xtr), ytr)
    out = {}
    for name, x, y, refs in (("train", xtr, ytr, refs_tr), ("val", xev, yev, refs_ev)):
        p1 = clf.predict_proba(sc.transform(x))[:, 1]
        out[name] = {
            "window_accuracy": float(((p1 >= 0.5).astype(int) == y).mean()),
            "balanced_accuracy": FIT._balanced_accuracy_from_runs(
                FIT.run_probabilities(refs, p1)),
        }
    out["n_features"] = int(xtr.shape[1])
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

    import torch

    folds = json.loads(args.splits.read_text(encoding="utf-8"))
    fold = FIT.resolve_fold_subjects(folds, args.outer_fold, args.inner_fold)
    rest = FIT.refs_from_extract_manifest(args.rest_manifest, labelled=False)
    task_refs: List[FIT.WindowRef] = []
    for mp in args.task_manifests:
        task_refs += FIT.refs_from_extract_manifest(mp, labelled=True)

    transform = FIT.fit_fold_transform(
        rest, fold.train, bank_seed=TPL.bank_seed(args.outer_fold, args.inner_fold),
        verify=False)
    refs_tr = FIT.select_refs(task_refs, fold.train)
    refs_ev = FIT.select_refs(task_refs, fold.evaluate)
    train_set = FIT.encode_windows(refs_tr, transform, verify=False)
    eval_set = FIT.encode_windows(refs_ev, transform, verify=False)

    result, model = FIT.train_fold(
        train_set, eval_set, transform, cell=args.cell, config_id=args.config_id,
        model_seed=args.model_seed, fold=fold, device=args.device,
        max_epochs=args.max_epochs)

    dev = torch.device(args.device)

    def pooled_of(enc: FIT.EncodedSet) -> np.ndarray:
        """graph layer 까지 통과한 뒤 ROI mean pooling 직후의 32차원."""
        model.eval()
        outs = []
        with torch.no_grad():
            for s in range(0, len(enc), 32):
                x = torch.as_tensor(enc.x[s:s + 32]).to(dev)
                pca = torch.as_tensor(enc.pca[s:s + 32]).to(dev)
                w = model.routing_weights(x.shape[0], pca, x.device)
                sm = model.mix(w)
                h = model.encoder(x)
                for layer in model.graph_layers:
                    h = layer(h, sm)
                outs.append(h.mean(dim=1).cpu().numpy())
        return np.concatenate(outs)

    def encoder_only(enc: FIT.EncodedSet) -> np.ndarray:
        """graph 이전, ROI encoder 출력의 ROI 평균."""
        model.eval()
        outs = []
        with torch.no_grad():
            for s in range(0, len(enc), 32):
                x = torch.as_tensor(enc.x[s:s + 32]).to(dev)
                outs.append(model.encoder(x).mean(dim=1).cpu().numpy())
        return np.concatenate(outs)

    def raw_moments(refs) -> np.ndarray:
        """계획서 §6 S 후보 1 — raw ROI mean/variance 200 features."""
        rows = []
        for r in refs:
            a = FIT.read_window(r, verify=False)          # (n_samples, n_roi)
            rows.append(np.concatenate([a.mean(axis=0), a.var(axis=0)]))
        return np.stack(rows)

    ptr, pev = pooled_of(train_set), pooled_of(eval_set)
    etr, eev = encoder_only(train_set), encoder_only(eval_set)
    mtr, mev = raw_moments(refs_tr), raw_moments(refs_ev)

    payload: Dict[str, Any] = {
        "schema_version": "encoder_representation_probe_v1",
        "not_a_hypothesis_test": "pilot 기술 검증이다. 주 결과로 쓰지 않는다 (계획서 §4-2)",
        "fold": {"n_train_windows": len(train_set), "n_eval_windows": len(eval_set)},
        "network_after_training": {
            "train_balanced_accuracy": FIT._balanced_accuracy_from_runs(
                FIT.run_probabilities(refs_tr, FIT._forward_probs(
                    model, torch.as_tensor(train_set.x).to(dev),
                    torch.as_tensor(train_set.pca).to(dev), batch_size=32))),
            "val_balanced_accuracy": result.eval_balanced_accuracy,
            "best_epoch": result.best_epoch,
        },
        "pooled_feature_statistics": {
            "dim": int(ptr.shape[1]),
            "between_sample_sd_mean": float(ptr.std(axis=0).mean()),
            "between_sample_sd_max": float(ptr.std(axis=0).max()),
            "abs_mean": float(np.abs(ptr).mean()),
        },
        "linear_probe_on_pooled_after_graph": _linear_score(
            ptr, train_set.y, pev, eval_set.y, refs_tr, refs_ev),
        "linear_probe_on_encoder_output_before_graph": _linear_score(
            etr, train_set.y, eev, eval_set.y, refs_tr, refs_ev),
        "linear_probe_on_raw_roi_moments_S1": _linear_score(
            mtr, train_set.y, mev, eval_set.y, refs_tr, refs_ev),
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
