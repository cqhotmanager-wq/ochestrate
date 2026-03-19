"""日志配置：初始化全局日志格式、级别与输出行为。"""

from __future__ import annotations

import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter
except Exception:  # pragma: no cover
    JsonFormatter = None


def configure_logging() -> None:
    # 步骤：执行 `configure_logging` 的核心处理逻辑。
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if JsonFormatter is not None:
        formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)



