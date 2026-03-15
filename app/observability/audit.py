from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_path: Path, persistent_sink: Any | None = None) -> None:
        self._log_path = log_path
        self._sink = persistent_sink
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, payload: dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")
        if self._sink is not None:
            try:
                self._sink.append_audit_event(event_id=event_id, event_type=event_type, payload=payload)
            except Exception:
                # File logging remains source of truth when DB sink fails.
                pass
        return event_id
