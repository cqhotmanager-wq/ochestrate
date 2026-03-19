# Enterprise Agent Platform

Phase-2 baseline with durable persistence for auth/task/audit/feedback/knowledge.

## Configuration Overview

The service reads configuration from environment variables (`AGENT_*`). It does **not** auto-load `.env` by default.

Primary entry points:

- Database: `AGENT_MYSQL_DSN` (see `app/core/config.py`)
- Model routing: `config/model_routing.yaml`
- Middleware auth context: `app/middleware/auth_context.py`

Default baseline:

- MySQL DSN: `mysql+pymysql://root:123456@127.0.0.1:3306/ochestrate`
- API prefix: `/v1`
- Runtime policy:
  - `AGENT_ENV=prod`: MySQL/Redis are required and startup fails if unavailable
  - `AGENT_ENV=dev|test`: in-memory fallback is allowed

## Model Routing Config

Edit `config/model_routing.yaml`:

- `default_provider`
- `providers.local` / `providers.cloud`
- `rules` (route by `task_type + sensitivity`)
- `fallback_order`

Built-in provider clients are currently `local` and `cloud` (`app/models/providers.py`).

## Middleware/Auth Config

- Middleware registration: `app.main: app.add_middleware(AuthContextMiddleware)`
- Route-level auth enforcement: `app/auth/deps.py` via `require_auth_context`
- `AGENT_AUTH_BOOTSTRAP_ADMIN_ENABLED` is effective
- `AGENT_AUTH_REQUIRE_ENABLED` is currently a config field only (not wired as a global bypass switch)

## Startup Runbook (PowerShell + uv)

1. Install dependencies

```powershell
uv sync --extra dev
```

2. Start infrastructure

```powershell
docker compose up -d mysql etcd minio milvus
```

3. Set runtime environment variables

```powershell
$env:AGENT_ENV = "dev"
$env:AGENT_MYSQL_DSN = "mysql+pymysql://root:123456@127.0.0.1:3306/ochestrate"
$env:AGENT_MODEL_ROUTING_PATH = "config/model_routing.yaml"
$env:AGENT_TOOL_SECURITY_PATH = "config/tool_security.yaml"
$env:AGENT_JWT_SECRET = "change-this-secret"

# Recommended when Redis is not running
$env:AGENT_TASK_QUEUE_BACKEND = "memory"
```

4. Run migration

```powershell
uv run alembic upgrade head
```

5. Start API

```powershell
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

6. Minimal first-use flow

```powershell
# Health check
curl http://127.0.0.1:8000/health

# Bootstrap admin
curl -X POST http://127.0.0.1:8000/v1/auth/bootstrap-admin `
  -H "Content-Type: application/json" `
  -d "{\"tenant_id\":\"acme\",\"username\":\"admin\",\"password\":\"admin123\",\"role\":\"admin\",\"status\":\"active\"}"

# Login
curl -X POST http://127.0.0.1:8000/v1/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"tenant_id\":\"acme\",\"username\":\"admin\",\"password\":\"admin123\"}"
```

## Core APIs

- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `POST /v1/users`
- `POST /v1/agent/run`
- `POST /v1/tasks/submit`
- `GET /v1/tasks/{task_id}`
- `GET /v1/tasks/{task_id}/events` (SSE, pushes status updates and final result)
- `POST /v1/feedback`
- `POST /v1/knowledge/ingest-text`
- `POST /v1/skills`

## Docs

- Architecture: `docs/architecture.md`
- Chinese guide: `docs/中文使用说明.md`
- Developer handbook: `docs/开发手册.md`
- MySQL schema: `docs/sql/mysql_schema.sql`
