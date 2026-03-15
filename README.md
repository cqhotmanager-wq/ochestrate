# Enterprise Agent Platform

企业级智能体平台一期工程骨架，支持：

- 多智能体编排（Planner/Retriever/Executor/Reviewer）
- 统一请求响应协议（UnifiedRequest/UnifiedResponse）
- JWT + Refresh 认证、用户管理、租户隔离
- Redis 队列 + MySQL 状态持久化 + 任务恢复
- ToolHub 工具中心（文件/网络/搜索/数据库/办公工具）
- Skill Center + SKILL.md 双源技能加载与系统提示词注入
- RAG 摄取与检索接口（可扩展 Milvus/MySQL）
- 审计日志与基础指标

## Runtime Versions

- `langchain==1.2.1`
- `langgraph==1.1.2`

## Quick Start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Main APIs

- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `POST /v1/users`
- `POST /v1/agent/run`
- `POST /v1/tasks/submit`
- `GET /v1/tasks/{task_id}`
- `POST /v1/feedback`
- `POST /v1/knowledge/ingest-text`
- `POST /v1/skills`

## Chinese Documentation

- 详细中文文档：`docs/中文使用说明.md`
- MySQL 示例建表：`docs/sql/mysql_schema.sql`
- Tool 安全策略：`config/tool_security.yaml`
