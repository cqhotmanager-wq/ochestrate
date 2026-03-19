"""追踪服务：生成 trace_id 以串联请求全链路。"""

from __future__ import annotations

import uuid


class TraceService:
    def new_trace_id(self) -> str:
        # 步骤：执行 `new_trace_id` 的核心处理逻辑。
        return str(uuid.uuid4())



