from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "enterprise-agent-platform"
    env: str = "dev"
    api_prefix: str = "/v1"

    mysql_dsn: str = "mysql+pymysql://root:123456@127.0.0.1:3306/ochestrate"
    milvus_uri: str = "http://localhost:19530"

    model_routing_path: Path = Path("config/model_routing.yaml")
    tool_security_path: Path = Path("config/tool_security.yaml")

    max_context_tokens: int = 4096
    short_memory_turns: int = 12
    long_memory_default_ttl_days: int = 180

    skill_storage_dir: Path = Path("config/skills")
    skill_scan_dirs: list[Path] = [Path("config/skills"), Path.home() / ".codex" / "skills"]
    skill_scan_glob: str = "**/SKILL.md"
    prompt_skill_max_items: int = 100

    audit_log_path: Path = Path("logs/audit.log")
    worker_poll_interval_seconds: float = 0.2
    task_queue_backend: str = "redis"
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "agent_tasks"

    jwt_secret: str = "replace-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7

    auth_require_enabled: bool = True
    auth_bootstrap_admin_enabled: bool = True

    skill_cache_ttl_seconds: int = 60
    retrieval_cache_ttl_seconds: int = 30

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        case_sensitive=False,
        extra="ignore",
    )
