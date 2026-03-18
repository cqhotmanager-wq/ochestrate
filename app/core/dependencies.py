"""依赖容器：组装服务、仓储、工具与运行时回退策略。"""

from __future__ import annotations

from functools import lru_cache
import logging
from pathlib import Path
import socket
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.retriever import RetrieverAgent
from app.agents.reviewer import ReviewerAgent
from app.auth.service import AuthService
from app.context.manager import ContextManager
from app.core.config import Settings
from app.learning.pipeline import EnterpriseLearningPipeline
from app.memory.service import MemoryService
from app.models.router import ModelRouter
from app.observability.audit import AuditLogger
from app.observability.metrics import MetricsRegistry
from app.observability.tracing import TraceService
from app.orchestration.service import OrchestratorService
from app.prompts.assembly import PromptAssemblyService
from app.rag.ingestion import IngestionPipeline
from app.rag.retriever import HybridRetriever
from app.rag.store import KnowledgeStore
from app.skills.center import SkillCenter
from app.skills.context import SkillContextService
from app.storage.orm import create_session_factory
from app.storage.repositories.auth_repo import AuthRepository
from app.storage.repositories.feedback_repo import FeedbackRepository
from app.storage.repositories.knowledge_repo import KnowledgeRepository
from app.storage.repositories.task_repo import TaskRepository
from app.tools.database_tool import DatabaseTool
from app.tools.file_tool import FileTool
from app.tools.hub import ToolHub
from app.tools.office import CreateCalendarEventTool, SendEmailTool
from app.tools.security import ToolSecurityConfig
from app.tools.web_tools import WebFetchTool, WebSearchTool
from app.workers.queue_backend import InMemoryQueueBackend, QueueBackend, RedisQueueBackend
from app.workers.task_worker import TaskManager

logger = logging.getLogger(__name__)


class ServiceContainer:
    """应用级依赖容器。

    说明：
    - 该容器在进程内按单例创建，负责把配置、仓储、工具、模型、编排等组件一次性装配完成。
    - 业务代码通过 `get_container()` 获取容器实例，避免在路由层反复手工拼装依赖。
    """

    def __init__(self) -> None:
        # 1) 基础运行时能力：配置、工作目录、追踪、指标。
        self.settings = Settings()
        self.workspace = Path.cwd()
        self.trace = TraceService()
        self.metrics = MetricsRegistry()

        # 2) 数据面初始化：先尝试创建 MySQL 引擎，失败后按环境策略决定是否回退到内存模式。
        self.mysql_engine = self._build_mysql_engine(self.settings.mysql_dsn)
        self.mysql_session_factory: sessionmaker[Session] | None = (
            create_session_factory(self.mysql_engine) if self.mysql_engine is not None else None
        )

        # 3) 仓储与审计组件：任务仓储也被审计日志复用为持久化下沉点。
        self.task_repository = TaskRepository(self.mysql_session_factory)
        self.audit = AuditLogger(self.settings.audit_log_path, persistent_sink=self.task_repository)
        self.auth_repository = AuthRepository(self.mysql_session_factory)
        self.feedback_repository = FeedbackRepository(self.mysql_session_factory)
        self.knowledge_repository = KnowledgeRepository(self.mysql_session_factory)

        # 4) 认证服务：集中处理密码散列、Token 签发与刷新逻辑。
        self.auth_service = AuthService(
            repository=self.auth_repository,
            jwt_secret=self.settings.jwt_secret,
            jwt_algorithm=self.settings.jwt_algorithm,
            access_token_ttl_minutes=self.settings.access_token_ttl_minutes,
            refresh_token_ttl_days=self.settings.refresh_token_ttl_days,
        )

        # 5) 上下文与记忆：为编排层提供短期/长期记忆，以及统一上下文预算控制。
        self.memory_service = MemoryService(
            short_turns=self.settings.short_memory_turns,
            long_ttl_days=self.settings.long_memory_default_ttl_days,
        )
        self.context_manager = ContextManager(max_tokens=self.settings.max_context_tokens)

        # 6) 知识检索面：摄取管线 + 知识存储 + 检索器。
        self.knowledge_store = KnowledgeStore(repository=self.knowledge_repository)
        self.ingestion_pipeline = IngestionPipeline()
        self.rag_retriever = HybridRetriever(self.knowledge_store)

        # 7) 技能、学习与提示词装配。
        self.skill_center = SkillCenter(storage_dir=self.settings.skill_storage_dir)
        self.skill_context = SkillContextService(
            skill_center=self.skill_center,
            scan_dirs=self.settings.skill_scan_dirs,
            skill_scan_glob=self.settings.skill_scan_glob,
        )
        self.learning_pipeline = EnterpriseLearningPipeline(repository=self.feedback_repository)
        self.prompt_assembly = PromptAssemblyService(max_tokens=self.settings.max_context_tokens)

        # 8) 工具安全与工具中心。
        self.tool_security = ToolSecurityConfig.from_file(
            path=self.settings.tool_security_path,
            workspace=self.workspace,
        )
        self.tool_hub = ToolHub(metrics=self.metrics, audit=self.audit)
        self._register_tools()

        # 9) 模型路由与四阶段智能体编排。
        self.model_router = ModelRouter.from_file(self.settings.model_routing_path)
        self.planner = PlannerAgent()
        self.retriever = RetrieverAgent(self.rag_retriever)
        self.executor = ExecutorAgent(self.tool_hub)
        self.reviewer = ReviewerAgent()
        self.orchestrator = OrchestratorService(
            planner=self.planner,
            retriever=self.retriever,
            executor=self.executor,
            reviewer=self.reviewer,
            model_router=self.model_router,
            memory=self.memory_service,
            context_manager=self.context_manager,
            prompt_assembly=self.prompt_assembly,
            skill_context=self.skill_context,
            tool_hub=self.tool_hub,
            trace=self.trace,
            metrics=self.metrics,
            audit=self.audit,
            max_skill_items=self.settings.prompt_skill_max_items,
        )

        # 10) 异步任务执行面：队列后端 + 任务管理器。
        self.queue_backend = self._build_queue_backend()
        self.task_manager = TaskManager(
            orchestrator=self.orchestrator,
            queue_backend=self.queue_backend,
            task_repository=self.task_repository,
            poll_interval_seconds=self.settings.worker_poll_interval_seconds,
        )

    def _register_tools(self) -> None:
        """注册平台默认工具。

        说明：
        - 先构造 `WebFetchTool`，再将其复用给 `WebSearchTool`，避免重复实现抓取策略。
        - 工具权限和审计统一由 `ToolHub` 管控。
        """
        fetch_tool = WebFetchTool(self.tool_security)
        self.tool_hub.register(SendEmailTool())
        self.tool_hub.register(CreateCalendarEventTool())
        self.tool_hub.register(FileTool(self.tool_security, workspace=self.workspace))
        self.tool_hub.register(fetch_tool)
        self.tool_hub.register(WebSearchTool(self.tool_security, fetch_tool=fetch_tool))
        self.tool_hub.register(DatabaseTool(self.settings.mysql_dsn, security=self.tool_security))

    def _build_mysql_engine(self, dsn: str) -> Engine | None:
        """构建 MySQL 引擎并执行连通性探测。

        行为策略：
        - `prod` 环境：数据库不可用时直接抛错，阻止服务以降级模式启动。
        - `dev/test` 环境：记录告警并回退到内存仓储，便于本地开发与 CI。
        """
        try:
            engine = create_engine(dsn, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as exc:
            if self._is_prod_env():
                raise RuntimeError(f"mysql unavailable in prod: {exc}") from exc
            logger.warning("mysql unavailable, fallback to in-memory repository: %s", exc)
            return None

    def _build_queue_backend(self) -> QueueBackend:
        """按配置构建队列后端，并在必要时执行降级。"""
        backend = (self.settings.task_queue_backend or "memory").strip().lower()
        if backend == "redis":
            # 先做网络可达性探测，避免在不可达地址上长时间阻塞初始化。
            reachable = self._is_redis_reachable(self.settings.redis_url)
            if not reachable:
                if self._is_prod_env():
                    raise RuntimeError("redis backend required in prod but redis is unreachable")
                logger.warning("redis unavailable, fallback to in-memory queue")
                return InMemoryQueueBackend()
            try:
                return RedisQueueBackend(
                    redis_url=self.settings.redis_url,
                    queue_name=self.settings.redis_queue_name,
                )
            except Exception as exc:
                # Redis 客户端初始化失败也走同样的 prod/dev 分流策略。
                if self._is_prod_env():
                    raise RuntimeError(f"redis backend init failed in prod: {exc}") from exc
                logger.warning("redis backend init failed, fallback to memory queue: %s", exc)
                return InMemoryQueueBackend()
        return InMemoryQueueBackend()

    def _is_prod_env(self) -> bool:
        """是否为生产环境判定。"""
        return (self.settings.env or "").strip().lower() in {"prod", "production"}

    @staticmethod
    def _is_redis_reachable(redis_url: str) -> bool:
        """快速探测 Redis 主机端口连通性。"""
        parsed = urlparse(redis_url)
        host = parsed.hostname
        port = parsed.port or 6379
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    """获取进程级容器单例。"""
    return ServiceContainer()


