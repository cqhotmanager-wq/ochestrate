from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml


@dataclass
class ToolSecurityConfig:
    allowed_directories: list[Path]
    allowed_domains: list[str]
    fetch_timeout_seconds: int
    max_fetch_chars: int
    search_provider: str
    search_result_limit: int
    db_write_protection_enabled: bool
    db_confirm_field: str
    max_file_size_mb: int

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
            fetch_timeout_seconds=int(raw.get("fetch_timeout_seconds", 10)),
            max_fetch_chars=int(raw.get("max_fetch_chars", 8000)),
            search_provider=str(raw.get("search_provider", "duckduckgo")),
            search_result_limit=int(raw.get("search_result_limit", 5)),
            db_write_protection_enabled=bool(raw.get("db_write_protection_enabled", True)),
            db_confirm_field=str(raw.get("db_confirm_field", "confirm_write")),
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
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        if "*" in self.allowed_domains:
            return True
        return any(host == d.lower() or host.endswith(f".{d.lower()}") for d in self.allowed_domains)
