from __future__ import annotations

import uuid


class TraceService:
    def new_trace_id(self) -> str:
        return str(uuid.uuid4())

