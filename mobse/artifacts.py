from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mobse.config import ExperimentConfig


@dataclass
class ArtifactPaths:
    root: Path
    templates: Path
    checkpoints: Path
    logs: Path
    reports: Path


class ArtifactManager:
    def __init__(self, cfg: ExperimentConfig):
        run_dir = Path(cfg.artifacts.root_dir) / str(cfg.artifacts.run_id)
        self.paths = ArtifactPaths(
            root=run_dir,
            templates=run_dir / "templates",
            checkpoints=run_dir / "checkpoints",
            logs=run_dir / "logs",
            reports=run_dir / "reports",
        )

    def ensure_dirs(self) -> ArtifactPaths:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.templates.mkdir(parents=True, exist_ok=True)
        self.paths.checkpoints.mkdir(parents=True, exist_ok=True)
        self.paths.logs.mkdir(parents=True, exist_ok=True)
        self.paths.reports.mkdir(parents=True, exist_ok=True)
        return self.paths
