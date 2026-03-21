"""Dependency container wiring for services and runtime policies."""

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
from app.agents.intent import IntentAnalyzer
from app.agents.planner import PlannerAgent
from app.agents.retriever import RetrieverAgent
from app.agents.reviewer import ReviewerAgent
from app.auth.service import AuthService
from app.context.manager import ContextManager
from app.core.config import Settings
from app.embeddings.service import EmbeddingConfig, EmbeddingService
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
from app.skills.registry import SkillRegistryService
from app.storage.orm import create_session_factory
from app.storage.repositories.auth_repo import AuthRepository
from app.storage.repositories.feedback_repo import FeedbackRepository
from app.storage.repositories.knowledge_repo import KnowledgeRepository
from app.storage.repositories.long_memory_repo import LongTermMemoryRepository
from app.storage.repositories.skill_registry_repo import SkillRegistryRepository
from app.storage.repositories.task_repo import TaskRepository
from app.storage.vector_gateway import VectorStoreGateway
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
    def __init__(self) -> None:
        self.settings = Settings()
        self.workspace = Path.cwd()
        self.trace = TraceService()
        self.metrics = MetricsRegistry()

        self.mysql_engine = self._build_mysql_engine(self.settings.mysql_dsn)
        self.mysql_session_factory: sessionmaker[Session] | None = (
            create_session_factory(self.mysql_engine) if self.mysql_engine is not None else None
        )

        self.task_repository = TaskRepository(self.mysql_session_factory)
        self.audit = AuditLogger(self.settings.audit_log_path, persistent_sink=self.task_repository)
        self.auth_repository = AuthRepository(self.mysql_session_factory)
        self.feedback_repository = FeedbackRepository(self.mysql_session_factory)
        self.knowledge_repository = KnowledgeRepository(self.mysql_session_factory)
        self.long_memory_repository = LongTermMemoryRepository(self.mysql_session_factory)
        self.skill_registry_repository = SkillRegistryRepository(self.mysql_session_factory)

        self.auth_service = AuthService(
            repository=self.auth_repository,
            jwt_secret=self.settings.jwt_secret,
            jwt_algorithm=self.settings.jwt_algorithm,
            access_token_ttl_minutes=self.settings.access_token_ttl_minutes,
            refresh_token_ttl_days=self.settings.refresh_token_ttl_days,
        )

        allow_mock_fallback = self.settings.embedding_allow_mock_fallback
        if self._is_prod_env():
            # In prod we default to strict cloud embedding behavior.
            allow_mock_fallback = False

        self.embedding_service = EmbeddingService(
            config=EmbeddingConfig(
                url=self.settings.embedding_url or None,
                model=self.settings.embedding_model,
                timeout_seconds=self.settings.embedding_timeout_seconds,
                api_key=self.settings.embedding_api_key or None,
                api_key_header=self.settings.embedding_api_key_header,
                api_key_prefix=self.settings.embedding_api_key_prefix,
                allow_mock_fallback=allow_mock_fallback,
            ),
            env=self.settings.env,
        )

        self.vector_gateway = VectorStoreGateway(
            milvus_uri=self.settings.milvus_uri,
            collection_name=self.settings.milvus_collection_name,
            dimension=self.settings.vector_dimension,
            use_milvus=self.settings.vector_use_milvus,
        )

        self.memory_service = MemoryService(
            short_turns=self.settings.short_memory_turns,
            long_ttl_days=self.settings.long_memory_default_ttl_days,
            long_term_repository=self.long_memory_repository,
            embedding_service=self.embedding_service,
            vector_gateway=self.vector_gateway,
        )
        self.context_manager = ContextManager(max_tokens=self.settings.max_context_tokens)

        self.knowledge_store = KnowledgeStore(repository=self.knowledge_repository)
        self.ingestion_pipeline = IngestionPipeline()
        self.rag_retriever = HybridRetriever(self.knowledge_store)

        self.skill_center = SkillCenter(storage_dir=self.settings.skill_storage_dir)
        self.skill_context = SkillContextService(
            skill_center=self.skill_center,
            scan_dirs=self.settings.skill_scan_dirs,
            skill_scan_glob=self.settings.skill_scan_glob,
        )
        self.skill_registry = SkillRegistryService(
            context_service=self.skill_context,
            repository=self.skill_registry_repository,
            embedding_service=self.embedding_service,
            vector_gateway=self.vector_gateway,
        )
        self.learning_pipeline = EnterpriseLearningPipeline(repository=self.feedback_repository)
        self.prompt_assembly = PromptAssemblyService(max_tokens=self.settings.max_context_tokens)

        self.tool_security = ToolSecurityConfig.from_file(
            path=self.settings.tool_security_path,
            workspace=self.workspace,
        )
        self.tool_hub = ToolHub(metrics=self.metrics, audit=self.audit)
        self._register_tools()

        self.model_router = ModelRouter.from_file(self.settings.model_routing_path)
        self.planner = PlannerAgent()
        self.retriever = RetrieverAgent(self.rag_retriever)
        self.executor = ExecutorAgent(self.tool_hub)
        self.reviewer = ReviewerAgent()
        self.intent_analyzer = IntentAnalyzer()
        self.orchestrator = OrchestratorService(
            planner=self.planner,
            executor=self.executor,
            reviewer=self.reviewer,
            model_router=self.model_router,
            memory=self.memory_service,
            context_manager=self.context_manager,
            prompt_assembly=self.prompt_assembly,
            skill_registry=self.skill_registry,
            tool_hub=self.tool_hub,
            trace=self.trace,
            metrics=self.metrics,
            audit=self.audit,
            intent_analyzer=self.intent_analyzer,
            max_skill_items=self.settings.prompt_skill_max_items,
            top_k_skills=self.settings.skill_retrieval_top_k,
        )

        self.queue_backend = self._build_queue_backend()
        self.task_manager = TaskManager(
            orchestrator=self.orchestrator,
            queue_backend=self.queue_backend,
            task_repository=self.task_repository,
            poll_interval_seconds=self.settings.worker_poll_interval_seconds,
        )

    def _register_tools(self) -> None:
        fetch_tool = WebFetchTool(self.tool_security)
        self.tool_hub.register(SendEmailTool())
        self.tool_hub.register(CreateCalendarEventTool())
        self.tool_hub.register(FileTool(self.tool_security, workspace=self.workspace))
        self.tool_hub.register(fetch_tool)
        self.tool_hub.register(WebSearchTool(self.tool_security, fetch_tool=fetch_tool))
        self.tool_hub.register(DatabaseTool(self.settings.mysql_dsn, security=self.tool_security))

    def _build_mysql_engine(self, dsn: str) -> Engine | None:
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
        backend = (self.settings.task_queue_backend or "memory").strip().lower()
        if backend == "redis":
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
                if self._is_prod_env():
                    raise RuntimeError(f"redis backend init failed in prod: {exc}") from exc
                logger.warning("redis backend init failed, fallback to memory queue: %s", exc)
                return InMemoryQueueBackend()
        return InMemoryQueueBackend()

    def _is_prod_env(self) -> bool:
        return (self.settings.env or "").strip().lower() in {"prod", "production"}

    @staticmethod
    def _is_redis_reachable(redis_url: str) -> bool:
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
    return ServiceContainer()
