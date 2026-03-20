# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI业务中台 — 企业级AI平台，三层架构：React 前端 → Python AI网关 → Java 业务编排层，底层 Docker Compose 基础设施（8个服务）。

## Repository Structure

```
AI业务中台/
├── frontend/          # React 18 + Vite 5 + TypeScript + Ant Design 5
├── ai-gateway/        # Python FastAPI + LangChain + LangGraph
├── business-server/   # Java Spring Boot 3.x + MyBatis-Plus
├── docker/            # Docker Compose 基础设施编排
└── docs/              # 架构设计文档（16篇）
```

## Quick Start Commands

```bash
# 基础设施
cd docker && docker compose up -d

# AI网关 (Python 3.11+)
cd ai-gateway && pip install -e . && uvicorn app.main:app --reload --port 8000

# 业务编排 (Java 17+)
cd business-server && mvn spring-boot:run

# 前端
cd frontend && npm install && npm run dev
```

## Architecture

### 请求流向

```
前端(:5173) ──→ AI网关(:8000)     ──→ Ollama/Milvus/ES/ClickHouse
             └→ 业务编排(:8080)   ──→ PostgreSQL/Redis/RabbitMQ
```

### 三层职责

- **前端** (T5/T6): UI渲染、AI对话（assistant-ui）、动态UI（json-render）、数据可视化（ECharts）
- **AI网关** (T4.1): 意图分类（4类：chat/knowledge/query/task）、RAG混合检索（Milvus向量+ES关键词+RRF融合）、Text2SQL（Vanna.ai）、LLM调用（Ollama Qwen2.5:7b）
- **业务编排** (T2/T4.2): 待办聚合（适配器模式: ERP/CRM/OA）、知识库管理、审计日志

### API端点

| 路径 | 层 | 说明 |
|------|-----|------|
| `POST /api/v1/chat` | AI网关 | SSE流式对话 |
| `POST /api/v1/knowledge/search` | AI网关 | RAG知识检索 |
| `POST /api/v1/query/text2sql` | AI网关 | 自然语言查数 |
| `GET /api/v1/tasks/aggregate` | 业务编排 | 多系统待办聚合 |
| `POST /api/v1/knowledge/documents` | 业务编排 | 文档管理 |
| `GET /api/v1/audit/logs` | 业务编排 | 审计日志 |

## Service Ports

| 服务 | 端口 |
|------|------|
| 前端 (Vite) | 5173 |
| AI网关 (FastAPI) | 8000 |
| 业务编排 (Spring Boot) | 8080 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Milvus | 19530 |
| RabbitMQ | 5672 / 15672(管理) |
| Elasticsearch | 9200 |
| MinIO | 9000 / 9001(控制台) |
| ClickHouse | 8123 |
| Ollama | 11434 |

## Key Technical Decisions

- **数据库Schema**: 6张核心表定义在 `docker/init-scripts/init-postgres.sql`，字段命名和结构严格对齐 `docs/AI业务中台_整体技术架构文档.md` 4.1节
- **RAG策略**: 向量(Milvus BGE-M3) + 关键词(ES BM25) + RRF融合 + BGE-Reranker-v2重排序
- **Text2SQL**: 基于 Vanna.ai，使用 Ollama 本地推理 + Milvus 向量存储
- **动态UI**: AI网关返回 JSON Spec，前端通过 `@json-render/react` 渲染 Card/Table/Metric/List/Form/Chart 组件
- **适配器模式**: `BaseSystemAdapter` 抽象基类，子类实现 `fetchTasks()` / `executeAction()` 对接外部系统
- **前端状态**: Zustand 4.x 全局状态 + TanStack Query 服务端状态

## Configuration

- AI网关配置集中在 `ai-gateway/app/core/config.py`（pydantic-settings，从 `.env` 读取）
- 业务编排配置在 `business-server/src/main/resources/application-dev.yml`
- 前端API地址通过 `vite.config.ts` 代理和 `.env` 中 `VITE_API_BASE_URL` / `VITE_BUSINESS_API_URL` 控制
- Docker基础设施默认凭据见 `docker/.env.example`

## Reference Documents

核心架构文档（实现时务必对齐）：
- `docs/AI业务中台_整体技术架构文档.md` — 完整架构设计，4.1节为数据库Schema权威定义
- `docs/AI业务中台_MVP一期实施文档.md` — MVP范围，5.1-5.5节为接口规范
