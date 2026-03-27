from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class Item:
    item_id: str
    category: str
    status: str
    summary: str
    evidence: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _exists(path: str) -> Tuple[bool, str]:
    p = Path(path)
    return p.exists(), str(p)


def _read_raw_metrics_seed_count(path: Path) -> int:
    if not path.exists():
        return 0
    seeds = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = str(row.get("source", ""))
            m = re.search(r"eval_seed(\d+)_", src)
            if m:
                seeds.add(int(m.group(1)))
    return len(seeds)


def _has_etth1_only_config(config_root: Path) -> bool:
    for path in config_root.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*tasks:\s*\[\s*etth1\s*\]\s*$", text, flags=re.MULTILINE):
            return True
    return False


def _max_seed_count_in_artifacts(artifacts_root: Path) -> Tuple[int, str]:
    max_count = 0
    max_run = ""
    for csv_path in artifacts_root.glob("*/reports/raw_metrics.csv"):
        count = _read_raw_metrics_seed_count(csv_path)
        if count > max_count:
            max_count = count
            max_run = str(csv_path.parent.parent.name)
    return max_count, max_run


def _phase2_sweep_prior_coverage(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"exists": False}
    priors = set()
    routings = set()
    sparsities = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            priors.add(str(row.get("template_prior", "")).strip())
            routings.add(str(row.get("routing_mode", "")).strip())
            sparsities.add(str(row.get("sparsity", "")).strip())
    return {
        "exists": True,
        "priors": sorted(p for p in priors if p),
        "routings": sorted(r for r in routings if r),
        "sparsities": sorted(s for s in sparsities if s),
    }


def _train_log_has_norm_fields(path: Path) -> Tuple[bool, bool]:
    if not path.exists():
        return False, False
    payload = json.loads(path.read_text(encoding="utf-8"))
    history = payload.get("history", [])
    if not history:
        return True, False
    keys = set(history[0].keys())
    has_norm = "train_etth1_loss_norm" in keys and "val_score_components" in keys
    return True, has_norm


def build_items(repo_root: Path) -> List[Item]:
    items: List[Item] = []

    required_files = [
        ("theory_note", "docs/concept/MoBSE_note.md"),
        ("phase2_report", "docs/experiments/phase2_report_2026-03-14.md"),
        ("baseline_benchmark", "docs/experiments/baseline_benchmark_2026-03-23.md"),
        ("etth1_storyline", "docs/experiments/etth1_storyline_top_journal_2026-03-27.md"),
        ("etth1_csv", "data/ETTh1.csv"),
        ("mobse_model_code", "mobse/models/mobse.py"),
        ("trainer_code", "mobse/train.py"),
        ("etth1_data_code", "mobse/data/etth1.py"),
    ]
    for item_id, rel in required_files:
        path = repo_root / rel
        if path.exists():
            summary = "required source present"
            if item_id == "etth1_csv":
                summary = f"raw ETTh1 present (sha256={_sha256(path)[:12]}...)"
            items.append(Item(item_id=item_id, category="core_sources", status="ready", summary=summary, evidence=rel))
        else:
            items.append(Item(item_id=item_id, category="core_sources", status="missing", summary="required source missing", evidence=rel))

    # Key experiment artifacts for ETTh1 storyline
    artifacts_required = [
        ("phase2_n100_sweep", "artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv"),
        ("phase2_n200_sweep", "artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_sweep_seed42.csv"),
        ("phase2_best_vs_best", "artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_best_vs_best_phase2_ds00_adult300_n100_20260314_vs_phase2_ds00_adult300_n200_20260314.csv"),
        ("phase2_figures_manifest", "artifacts/phase2_figures_20260314_n100_n200/phase2_figures_manifest.json"),
        ("baseline_summary", "artifacts/benchmark_wave_20260323/reports/baseline_benchmark_summary.csv"),
        ("openneuro_strict_vs_raw_paired", "artifacts/phase2_openneuro600_gsr_moe_n100_20260324__vs__phase2_openneuro_usable600_gsr_moe_n100_20260326/reports/followup_paired_stats.csv"),
    ]
    for item_id, rel in artifacts_required:
        ok, evidence = _exists(str(repo_root / rel))
        items.append(
            Item(
                item_id=item_id,
                category="experiment_artifacts",
                status="ready" if ok else "missing",
                summary="artifact present" if ok else "artifact missing",
                evidence=rel,
            )
        )

    # Prior on/off ablation coverage
    n100_cov = _phase2_sweep_prior_coverage(repo_root / "artifacts/phase2_ds00_adult300_n100_20260314_summary/reports/phase2_sweep_seed42.csv")
    n200_cov = _phase2_sweep_prior_coverage(repo_root / "artifacts/phase2_ds00_adult300_n200_20260314_summary/reports/phase2_sweep_seed42.csv")
    cov_ready = (
        n100_cov.get("exists")
        and n200_cov.get("exists")
        and set(n100_cov.get("priors", [])) >= {"False", "True"}
        and set(n200_cov.get("priors", [])) >= {"False", "True"}
    )
    items.append(
        Item(
            item_id="prior_onoff_ablation_coverage",
            category="claim_support",
            status="ready" if cov_ready else "partial",
            summary=f"n100 priors={n100_cov.get('priors', [])}, n200 priors={n200_cov.get('priors', [])}",
            evidence="phase2_sweep_seed42.csv (n100/n200)",
        )
    )

    # Loss stabilization before/after evidence
    old_path = repo_root / "artifacts/poc1_hc127_mps100/logs/train_seed42.json"
    new_path = repo_root / "artifacts/poc1_hc127_mps100_balanced/logs/train_seed42.json"
    old_exists, old_has_norm = _train_log_has_norm_fields(old_path)
    new_exists, new_has_norm = _train_log_has_norm_fields(new_path)
    if old_exists and new_exists and (not old_has_norm) and new_has_norm:
        status = "ready"
        summary = "before/after logs show introduction of normalized multi-task fields"
    elif old_exists and new_exists:
        status = "partial"
        summary = f"logs present but norm-field contrast unclear (old={old_has_norm}, new={new_has_norm})"
    else:
        status = "missing"
        summary = "before/after train logs missing"
    items.append(
        Item(
            item_id="loss_stabilization_evidence",
            category="claim_support",
            status=status,
            summary=summary,
            evidence="artifacts/poc1_hc127_mps100*/logs/train_seed42.json",
        )
    )

    # Gaps from storyline
    etth1_only = _has_etth1_only_config(repo_root / "configs")
    items.append(
        Item(
            item_id="etth1_only_control",
            category="open_gaps",
            status="ready" if etth1_only else "missing",
            summary="etth1-only control config exists" if etth1_only else "no etth1-only config found",
            evidence="configs/**/*.yaml tasks field",
        )
    )

    temporal_variant_markers = [
        "temporal encoder",
        "sequence encoder",
        "no mean pooling",
    ]
    code_text = (repo_root / "mobse/models/mobse.py").read_text(encoding="utf-8")
    has_temporal_variant = any(marker in code_text.lower() for marker in temporal_variant_markers)
    items.append(
        Item(
            item_id="temporal_bottleneck_control",
            category="open_gaps",
            status="ready" if has_temporal_variant else "missing",
            summary="temporal-encoder control appears implemented" if has_temporal_variant else "no temporal-encoder control implementation marker found",
            evidence="mobse/models/mobse.py",
        )
    )

    max_seed_count, max_seed_run = _max_seed_count_in_artifacts(repo_root / "artifacts")
    items.append(
        Item(
            item_id="high_power_10seed",
            category="open_gaps",
            status="ready" if max_seed_count >= 10 else "missing",
            summary=f"max detected seed count in raw_metrics: {max_seed_count}",
            evidence=max_seed_run if max_seed_run else "artifacts/*/reports/raw_metrics.csv",
        )
    )

    return items


def write_outputs(repo_root: Path, items: List[Item]) -> Dict[str, object]:
    out_dir = repo_root / "artifacts/journal_etth1_story_readiness_20260327/reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "readiness_items.csv"
    json_path = out_dir / "readiness_manifest.json"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["item_id", "category", "status", "summary", "evidence"],
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "item_id": item.item_id,
                    "category": item.category,
                    "status": item.status,
                    "summary": item.summary,
                    "evidence": item.evidence,
                }
            )

    status_counts: Dict[str, int] = {"ready": 0, "partial": 0, "missing": 0}
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "status_counts": status_counts,
        "items_csv": str(csv_path),
        "items_total": len(items),
    }
    json_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_json"] = str(json_path)
    return manifest


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    items = build_items(repo_root=repo_root)
    manifest = write_outputs(repo_root=repo_root, items=items)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
