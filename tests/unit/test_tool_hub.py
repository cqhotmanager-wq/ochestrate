from __future__ import annotations

from pathlib import Path

from app.observability.audit import AuditLogger
from app.observability.metrics import MetricsRegistry
from app.tools.base import ToolCall
from app.tools.hub import ToolHub


class DummyTool:
    name = "dummy"
    description = "dummy tool"
    required_roles = ["employee"]
    idempotent = True

    def __init__(self) -> None:
        self.calls = 0

    def run(self, params: dict[str, str]) -> dict[str, str]:
        self.calls += 1
        return {"ok": "true", **params}


def test_tool_hub_idempotency_and_permission(tmp_path: Path) -> None:
    audit = AuditLogger(tmp_path / "audit.log")
    hub = ToolHub(metrics=MetricsRegistry(), audit=audit)
    tool = DummyTool()
    hub.register(tool)

    call = ToolCall(
        tool_name="dummy",
        user_role="employee",
        idempotency_key="x1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        user_id="user-1",
        params={"k": "v"},
    )
    r1 = hub.invoke(call)
    r2 = hub.invoke(call)
    assert r1.output == r2.output
    assert r2.cache_hit is True
    assert tool.calls == 1

    denied = ToolCall(
        tool_name="dummy",
        user_role="intern",
        idempotency_key="x2",
        trace_id="trace-1",
        tenant_id="tenant-1",
        user_id="user-1",
        params={},
    )
    try:
        hub.invoke(denied)
        assert False, "expected permission error"
    except PermissionError:
        assert True
