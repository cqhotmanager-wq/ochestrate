from __future__ import annotations

from pathlib import Path

from app.agents.intent import IntentAnalyzer
from app.agents.planner import PlannerAgent
from app.agents.reviewer import ReflectionEngine
from app.embeddings.service import EmbeddingConfig, EmbeddingService
from app.memory.service import MemoryService
from app.core.dependencies import ServiceContainer
from app.schemas.api import IntentSummary, UnifiedRequest
from app.skills.center import SkillCenter
from app.skills.context import SkillContextService
from app.skills.registry import SkillRegistryService
from app.storage.repositories.long_memory_repo import LongTermMemoryRepository
from app.storage.repositories.skill_registry_repo import SkillRegistryRepository
from app.storage.vector_gateway import VectorStoreGateway


def test_intent_analyzer_marks_unclear_input() -> None:
    analyzer = IntentAnalyzer()
    request = UnifiedRequest(session_id="s1", input="help", task_type="qa")
    intent = analyzer.analyze(request)
    assert intent.needs_clarification is True
    assert intent.clarifications


def test_orchestrator_returns_needs_clarification_without_execution() -> None:
    container = ServiceContainer()
    request = UnifiedRequest(tenant_id="t1", user_id="u1", session_id="s1", input="help", task_type="qa")
    response = container.orchestrator.run(request)

    assert response.status == "needs_clarification"
    assert response.task_graph is None
    assert response.execution_trace == []


def test_planner_builds_dag_with_parallel_group() -> None:
    planner = PlannerAgent()
    request = UnifiedRequest(session_id="s1", task_type="automation", input="send email and search web")
    intent = IntentSummary(goal="automation", constraints=[], expected_output=[], assumption_flags=[])
    graph = planner.plan(request=request, intent=intent)

    assert graph.parallel_groups
    assert graph.parallel_groups[0] == ["memory_retrieval", "skill_retrieval"]
    execution_nodes = [node for node in graph.nodes if node.node_type in {"tool", "model"}]
    assert execution_nodes
    for node in execution_nodes:
        assert set(node.depends_on) == {"memory_retrieval", "skill_retrieval"}


def test_reflection_retry_limit_is_one() -> None:
    engine = ReflectionEngine()
    first = engine.reflect(node_id="n1", result={}, error="boom", retry_count=0)
    second = engine.reflect(node_id="n1", result={}, error="boom", retry_count=1)
    assert first.decision == "retry"
    assert second.decision == "fail"


def test_skill_registry_vector_retrieval_top_k(tmp_path: Path) -> None:
    center = SkillCenter(storage_dir=tmp_path / "skills")
    center.generate_skill(
        skill_id="db_ops",
        version="1.0.0",
        name="Database Ops",
        prompt_template="Use database tools for SQL execution.",
        config={},
    )
    center.generate_skill(
        skill_id="web_ops",
        version="1.0.0",
        name="Web Ops",
        prompt_template="Use web tools for search and fetch.",
        config={},
    )

    context_service = SkillContextService(
        skill_center=center,
        scan_dirs=[tmp_path / "skill-md"],
        skill_scan_glob="**/SKILL.md",
    )
    registry = SkillRegistryService(
        context_service=context_service,
        repository=SkillRegistryRepository(session_factory=None),
        embedding_service=EmbeddingService(EmbeddingConfig(model="mock"), env="test"),
        vector_gateway=VectorStoreGateway(
            milvus_uri="http://localhost:19530",
            use_milvus=False,
        ),
    )

    registry.sync(tenant_id="t1", known_tools=["database_tool", "web_search_tool"])
    results = registry.retrieve(tenant_id="t1", query="SQL database migration", top_k=1)

    assert len(results) == 1
    assert results[0].name


def test_long_term_memory_structured_write_and_search() -> None:
    memory = MemoryService(
        short_turns=2,
        long_ttl_days=30,
        long_term_repository=LongTermMemoryRepository(session_factory=None),
        embedding_service=EmbeddingService(EmbeddingConfig(model="mock"), env="test"),
        vector_gateway=VectorStoreGateway(milvus_uri="http://localhost:19530", use_milvus=False),
    )

    memory.record_outcome(
        tenant_id="t1",
        user_id="u1",
        task="perform database migration",
        solution="apply alembic upgrade head",
        success=True,
        lessons_learned="validate migration in staging",
        tags=["migration"],
    )

    hits = memory.read_long(tenant_id="t1", user_id="u1", query="database migration", limit=3)
    assert hits
    assert "task:perform database migration" in hits[0]
