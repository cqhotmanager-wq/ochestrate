# Enterprise Agent Platform (Phase 1)

This repository contains a production-oriented scaffold for an enterprise intelligent agent platform with:

- Multi-agent orchestration (`Planner`, `Retriever`, `Executor`, `Reviewer`)
- Unified LLM input/output and configuration-driven model routing
- RAG ingestion and retrieval interfaces (MySQL + Milvus ready)
- Tool hub with permission, idempotency, audit hooks, and enterprise tools
- Skill center with template generation, versioning, and dynamic loading
- Context management, summarization, short/long-term memory
- Feedback collection and offline enterprise learning pipeline
- Prompt assembly with per-request skill/tool injection into system prompt

## Quick Start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Chinese Docs

- 中文详细手册: [docs/中文使用说明.md](/D:/go-git/ochestrate/docs/中文使用说明.md)
- MySQL 建表脚本: [docs/sql/mysql_schema.sql](/D:/go-git/ochestrate/docs/sql/mysql_schema.sql)

## API Endpoints

- `POST /v1/agent/run`
- `POST /v1/tasks/submit`
- `GET /v1/tasks/{task_id}`
- `POST /v1/feedback`
- `POST /v1/knowledge/ingest-text`
- `POST /v1/skills`
- `GET /v1/skills/{skill_id}/{version}`
- `POST /v1/webhook/tool-callback`
- `GET /health`

## Runtime Versions

- `langchain==1.2.1`
- `langgraph==1.0.10` (compatible with langchain 1.2.1 requirement `<1.1.0`)

## Architecture

- `app/api`: API gateway routes
- `app/orchestration`: multi-agent workflow
- `app/models`: model router and provider abstraction
- `app/rag`: ingestion/retrieval services
- `app/tools`: tool registry and execution hub
- `app/skills`: skill generation/loading/versioning
- `app/memory`: short-term and long-term memory services
- `app/context`: token budget and context packing
- `app/learning`: feedback processing pipeline
- `app/storage`: MySQL and Milvus adapters
- `app/observability`: trace, metrics, audit

## Notes

- This phase focuses on a stable platform foundation and standard interfaces.
- Several integrations are implemented as production-ready interfaces with in-memory defaults so the project can run locally without external services.

## Infrastructure

```bash
docker compose up -d mysql etcd minio milvus
```

## Tool Security Config

- See `config/tool_security.yaml` for file/domain/db-write controls.
