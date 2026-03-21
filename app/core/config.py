"""应用配置模型：统一管理环境变量、默认值与开关项。"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型。

    所有配置项默认通过 `AGENT_` 前缀环境变量注入，例如 `AGENT_MYSQL_DSN`。
    """

    # 基础服务配置
    app_name: str = "enterprise-agent-platform"
    env: str = "dev"
    api_prefix: str = "/v1"

    # 基础数据存储
    mysql_dsn: str = "mysql+pymysql://root:123456@127.0.0.1:3306/ochestrate"
    milvus_uri: str = "http://localhost:19530"
    milvus_collection_name: str = "agent_vectors"
    vector_dimension: int = 64
    vector_use_milvus: bool = True

    # 模型路由与工具安全策略配置文件
    model_routing_path: Path = Path("config/model_routing.yaml")
    tool_security_path: Path = Path("config/tool_security.yaml")

    # 上下文与记忆策略
    max_context_tokens: int = 4096
    short_memory_turns: int = 12
    long_memory_default_ttl_days: int = 180

    # 技能配置
    skill_storage_dir: Path = Path("config/skills")
    skill_scan_dirs: list[Path] = [Path("config/skills"), Path.home() / ".codex" / "skills"]
    skill_scan_glob: str = "**/SKILL.md"
    prompt_skill_max_items: int = 100
    skill_retrieval_top_k: int = 5

    # Embedding service
    embedding_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_timeout_seconds: int = 20
    embedding_api_key: str = ""
    embedding_api_key_header: str = "Authorization"
    embedding_api_key_prefix: str = "Bearer"
    embedding_allow_mock_fallback: bool = True

    # 审计与异步任务配置
    audit_log_path: Path = Path("logs/audit.log")
    worker_poll_interval_seconds: float = 0.2
    task_queue_backend: str = "redis"
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "agent_tasks"

    # 认证配置
    jwt_secret: str = "replace-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7

    # 鉴权开关
    auth_require_enabled: bool = True
    auth_bootstrap_admin_enabled: bool = True

    # 缓存 TTL
    skill_cache_ttl_seconds: int = 60
    retrieval_cache_ttl_seconds: int = 30

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        case_sensitive=False,
        extra="ignore",
    )


