"""工具安全策略：统一管理路径、域名、协议与数据库写保护。"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import socket
from urllib.parse import urlparse

import yaml


@dataclass
class ToolSecurityConfig:
    """工具安全配置。

    集中管理：
    - 文件系统访问白名单
    - 网络访问域名/协议约束
    - 私网访问阻断策略
    - 数据库写入确认与租户范围校验开关
    """

    allowed_directories: list[Path]
    allowed_domains: list[str]
    allowed_schemes: list[str] | None = None
    block_private_networks: bool = True
    fetch_timeout_seconds: int = 10
    max_fetch_chars: int = 8000
    max_redirects: int = 3
    search_provider: str = "duckduckgo"
    search_result_limit: int = 5
    db_write_protection_enabled: bool = True
    db_confirm_field: str = "confirm_write"
    db_require_tenant_scope: bool = True
    max_file_size_mb: int = 10

    @classmethod
    def from_file(cls, path: Path, workspace: Path) -> "ToolSecurityConfig":
        """从 YAML 读取安全策略，并把相对路径解析到当前工作区。"""
        # 步骤：执行 `from_file` 的核心处理逻辑。
        raw = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        dirs = raw.get("allowed_directories", ["data"])
        allowed_directories = []
        for d in dirs:
            p = Path(d)
            allowed_directories.append((p if p.is_absolute() else workspace / p).resolve())
        return cls(
            allowed_directories=allowed_directories,
            allowed_domains=raw.get("allowed_domains", ["*"]),
            allowed_schemes=[str(x).lower() for x in raw.get("allowed_schemes", ["https", "http"])],
            block_private_networks=bool(raw.get("block_private_networks", True)),
            fetch_timeout_seconds=int(raw.get("fetch_timeout_seconds", 10)),
            max_fetch_chars=int(raw.get("max_fetch_chars", 8000)),
            max_redirects=int(raw.get("max_redirects", 3)),
            search_provider=str(raw.get("search_provider", "duckduckgo")),
            search_result_limit=int(raw.get("search_result_limit", 5)),
            db_write_protection_enabled=bool(raw.get("db_write_protection_enabled", True)),
            db_confirm_field=str(raw.get("db_confirm_field", "confirm_write")),
            db_require_tenant_scope=bool(raw.get("db_require_tenant_scope", True)),
            max_file_size_mb=int(raw.get("max_file_size_mb", 10)),
        )

    def is_path_allowed(self, target: Path) -> bool:
        """校验目标路径是否在允许目录内（防目录穿越）。"""
        # 步骤：执行 `is_path_allowed` 的核心处理逻辑。
        resolved = target.resolve()
        for allowed in self.allowed_directories:
            try:
                resolved.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    def is_domain_allowed(self, url: str) -> bool:
        """校验 URL 协议与域名是否满足白名单规则。"""
        # 步骤：执行 `is_domain_allowed` 的核心处理逻辑。
        parsed = urlparse(url)
        schemes = [x.lower() for x in (self.allowed_schemes or ["https", "http"])]
        if parsed.scheme.lower() not in schemes:
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if "*" in self.allowed_domains:
            return True
        return any(host == d.lower() or host.endswith(f".{d.lower()}") for d in self.allowed_domains)

    def is_url_safe(self, url: str) -> bool:
        """统一校验 URL 的协议、域名与私网访问风险。"""
        # 步骤：执行 `is_url_safe` 的核心处理逻辑。
        parsed = urlparse(url)
        schemes = [x.lower() for x in (self.allowed_schemes or ["https", "http"])]
        if parsed.scheme.lower() not in schemes:
            return False
        if not self.is_domain_allowed(url):
            return False
        host = parsed.hostname
        if not host:
            return False
        if not self.block_private_networks:
            return True
        return not self._is_private_host(host)

    @staticmethod
    def _is_private_host(host: str) -> bool:
        """判断主机是否解析到私网/环回/保留地址。"""
        # 步骤：执行 `_is_private_host` 的核心处理逻辑。
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        except ValueError:
            pass

        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            return True

        for info in infos:
            candidate = info[4][0]
            try:
                ip = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return True
        return False

