# Architecture Overview

## Core Runtime

- `FastAPI` API gateway as the unified entry.
- `LangGraph` orchestrator pipeline: planner -> retriever -> executor -> reviewer.
- `LangChain` prompt templating for consistent input assembly.
- `LlamaIndex` chunk splitting in ingestion pipeline (with fallback splitter).

## Data Plane

- `MySQL` for transactional metadata (users, sessions, tasks, audit indexes, feedback records).
- `Milvus` for semantic vectors (knowledge chunks, memory vectors, skill vectors).
- In-memory defaults are included for local development and CI.

## Capability Plane

- Tool hub: permission guard, idempotency keys, audit events.
- Extended tools: file (`json/doc/docx/xlsx/pdf/txt/csv`), web fetch, web search, database query/execute.
- Skill center: generation, versioning, dynamic load from local storage.
- Skill context service: loads skills from SkillCenter + `SKILL.md` directories and injects `name/description/skill_path`.
- Memory service: short-term rolling session window and long-term TTL memory.
- Learning pipeline: explicit feedback ingestion + offline processing API.
- Prompt assembly service: layered prompt with policy/skills/tools/task/evidence/memory sections.

## APIs

- `POST /v1/agent/run`: unified synchronous inference.
- `POST /v1/tasks/submit`, `GET /v1/tasks/{task_id}`: async automation tasks.
- `POST /v1/feedback`: explicit feedback ingestion.
- `POST /v1/knowledge/ingest-text`: text-to-chunk ingestion.
- `POST /v1/skills`: generate and persist a skill template.
