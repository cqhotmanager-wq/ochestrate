from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.tools.security import ToolSecurityConfig


class DatabaseTool:
    name = "database_tool"
    description = "Run SQL query/execute with confirm-write policy controls."
    required_roles = ["employee", "manager", "admin"]
    idempotent = False

    def __init__(self, dsn: str, security: ToolSecurityConfig) -> None:
        self._dsn = dsn
        self._security = security
        self._engine: Engine | None = None

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        operation = str(params.get("operation", "query")).lower()
        sql = str(params.get("sql") or "").strip()
        if not sql:
            raise ValueError("sql is required")
        tenant_id = str(params.get("_tenant_id") or "").strip()
        tenant_column = str((params.get("options") or {}).get("tenant_column", "tenant_id")).strip()

        if self._security.db_write_protection_enabled and self._is_write_sql(sql):
            confirm = bool(params.get(self._security.db_confirm_field, False))
            if not confirm:
                raise PermissionError(
                    f"write SQL requires explicit '{self._security.db_confirm_field}=true'"
                )
        if self._security.db_require_tenant_scope:
            self._ensure_tenant_scope(sql=sql, tenant_id=tenant_id, tenant_column=tenant_column)

        engine = self._get_engine()
        if operation == "query":
            with engine.connect() as conn:
                rows = conn.execute(text(sql))
                result = [dict(row._mapping) for row in rows]
            return {"operation": "query", "rows": result, "count": len(result)}
        if operation == "execute":
            with engine.begin() as conn:
                result = conn.execute(text(sql))
                rowcount = int(result.rowcount if result.rowcount is not None else 0)
            return {"operation": "execute", "affected_rows": rowcount}
        raise ValueError(f"unsupported operation '{operation}'")

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._dsn, pool_pre_ping=True)
        return self._engine

    @staticmethod
    def _is_write_sql(sql: str) -> bool:
        match = re.match(r"^\s*([a-zA-Z]+)", sql)
        keyword = (match.group(1).upper() if match else "")
        return keyword in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "REPLACE",
            "MERGE",
            "CREATE",
            "ALTER",
            "DROP",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
        }

    @staticmethod
    def _ensure_tenant_scope(sql: str, tenant_id: str, tenant_column: str) -> None:
        """
        粗粒度租户约束：要求 SQL 中出现 tenant 字段过滤，避免跨租户全表操作。
        """
        if not tenant_id:
            raise PermissionError("tenant scope check failed: tenant_id is required")
        normalized = " ".join(sql.lower().split())
        column = tenant_column.lower()
        if f"{column} =" in normalized or f"{column}=" in normalized:
            return
        if f":{column}" in normalized or f"%({column})s" in normalized:
            return
        raise PermissionError(f"tenant scope check failed: missing '{tenant_column}' condition")
