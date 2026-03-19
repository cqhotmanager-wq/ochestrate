"""MySQL 适配器：负责连接延迟初始化与健康检查。"""

from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class MySQLAdapter:
    def __init__(self, dsn: str) -> None:
        # 步骤：执行 `__init__` 的核心处理逻辑。
        self._dsn = dsn
        self._engine: Engine | None = None

    def engine(self) -> Engine:
        # 延迟初始化连接引擎，避免进程启动时硬依赖数据库可达。
        if self._engine is None:
            self._engine = create_engine(self._dsn, pool_pre_ping=True)
        return self._engine

    def healthcheck(self) -> bool:
        # 步骤：执行 `healthcheck` 的核心处理逻辑。
        try:
            with self.engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


