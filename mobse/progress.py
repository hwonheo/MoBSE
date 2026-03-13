from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ProgressReporter:
    def __init__(self, file_path: str | Path, enabled: bool = True):
        self.file_path = Path(file_path)
        self.enabled = enabled
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.state: Dict[str, Any] = {
            "status": "running",
            "started_at": self._ts(),
            "updated_at": self._ts(),
            "stage": "init",
            "events": [],
        }
        self._persist()

    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _persist(self) -> None:
        self.state["updated_at"] = self._ts()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def update(
        self,
        stage: str,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "timestamp": self._ts(),
            "stage": stage,
            "message": message,
        }
        if current is not None:
            event["current"] = int(current)
        if total is not None:
            event["total"] = int(total)
        if current is not None and total not in (None, 0):
            event["percent"] = round(100.0 * float(current) / float(total), 2)
        if extra:
            event["extra"] = extra

        self.state["stage"] = stage
        self.state["last_event"] = event
        self.state["events"].append(event)
        if len(self.state["events"]) > 200:
            self.state["events"] = self.state["events"][-200:]
        self._persist()

        if self.enabled:
            prefix = f"[{stage}]"
            if "current" in event and "total" in event and event.get("total", 0) > 0:
                pct = event.get("percent", 0.0)
                prefix += f" {event['current']}/{event['total']} ({pct:.1f}%)"
            if message:
                print(f"{prefix} {message}")
            else:
                print(prefix)

    def done(self, message: str = "completed") -> None:
        self.state["status"] = "completed"
        self.update(stage="completed", message=message)

    def fail(self, message: str) -> None:
        self.state["status"] = "failed"
        self.update(stage="failed", message=message)
