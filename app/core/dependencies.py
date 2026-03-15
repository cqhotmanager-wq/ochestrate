from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.retriever import RetrieverAgent
from app.agents.reviewer import ReviewerAgent
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
from app.rag.store import InMemoryKnowledgeStore
from app.skills.center import SkillCenter
from app.skills.context import SkillContextService
from app.tools.database_tool import DatabaseTool
from app.tools.file_tool import FileTool
from app.tools.hub import ToolHub
from app.tools.office import CreateCalendarEventTool, SendEmailTool
from app.tools.security import ToolSecurityConfig
from app.tools.web_tools import WebFetchTool, WebSearchTool
from app.workers.task_worker import TaskManager


class ServiceContainer:
    def __init__(self) -> None:
        self.settings = Settings()
        self.workspace = Path.cwd()
        self.trace = TraceService()
        self.metrics = MetricsRegistry()
        self.audit = AuditLogger(self.settings.audit_log_path)

        self.memory_service = MemoryService(
            short_turns=self.settings.short_memory_turns,
            long_ttl_days=self.settings.long_memory_default_ttl_days,
        )
        self.context_manager = ContextManager(max_tokens=self.settings.max_context_tokens)

        self.knowledge_store = InMemoryKnowledgeStore()
        self.ingestion_pipeline = IngestionPipeline()
        self.rag_retriever = HybridRetriever(self.knowledge_store)

        self.skill_center = SkillCenter(storage_dir=self.settings.skill_storage_dir)
        self.skill_context = SkillContextService(
            skill_center=self.skill_center,
            scan_dirs=self.settings.skill_scan_dirs,
            skill_scan_glob=self.settings.skill_scan_glob,
        )
        self.learning_pipeline = EnterpriseLearningPipeline()
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
        self.task_manager = TaskManager(
            orchestrator=self.orchestrator,
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


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    return ServiceContainer()

