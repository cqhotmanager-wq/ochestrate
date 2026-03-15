from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import socket
from urllib.parse import urlparse

import yaml


@dataclass
class ToolSecurityConfig:
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
        resolved = target.resolve()
        for allowed in self.allowed_directories:
            try:
                resolved.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    def is_domain_allowed(self, url: str) -> bool:
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
