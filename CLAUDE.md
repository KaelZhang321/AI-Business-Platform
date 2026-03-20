# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI业务中台 — 企业级AI平台，三层架构：React 前端 → Python AI网关 → Java 业务编排层，底层 Docker Compose 基础设施（8个服务）。

## Repository Structure

```
AI业务中台/
├── frontend/          # React 18 + Vite 5 + TypeScript 5 + Ant Design 5 + Tailwind CSS
├── ai-gateway/        # Python 3.11+ / FastAPI + LangChain 0.3 + LangGraph 0.2
├── business-server/   # Java 17 / Spring Boot 3.3.6 + MyBatis-Plus 3.5.9
├── docker/            # Docker Compose 基础设施编排（8个服务）
└── docs/              # 架构设计文档（16篇）
```

## Quick Start Commands

```bash
# 基础设施
cd docker && docker compose up -d

# AI网关 (Python 3.11+)
cd ai-gateway && pip install -e . && uvicorn app.main:app --reload --port 8000

# 业务编排 (Java 17 必须，Lombok 不兼容 JDK 23+)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
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

Vite 代理分层规则（`vite.config.ts`）：
- `/api/v1/tasks/**`, `/api/v1/knowledge/documents/**`, `/api/v1/audit/**` → `:8080`（业务编排）
- 其余 `/api/**` → `:8000`（AI网关）

### 三层职责

- **前端** (T5/T6): UI渲染、AI对话（assistant-ui 0.12+）、动态UI渲染（自定义 DynamicRenderer 支持 Card/Table/Metric/List/Form/Tag/Chart 7种组件）、数据可视化（ECharts）
- **AI网关** (T4.1): 意图分类（4类：chat/knowledge/query/task）、RAG混合检索（Milvus向量+ES关键词+RRF融合）、Text2SQL（Vanna.ai）、LLM调用（Ollama Qwen2.5:7b）
- **业务编排** (T2/T4.2): 待办聚合（适配器模式: ERP/CRM/OA）、知识库管理、审计日志

### API端点

| 路径 | 层 | 方法 | 说明 |
|------|-----|------|------|
| `/api/v1/chat` | AI网关 | POST | SSE流式对话 |
| `/api/v1/knowledge/search` | AI网关 | POST | RAG知识检索 |
| `/api/v1/query/text2sql` | AI网关 | POST | 自然语言查数 |
| `/health` | AI网关 | GET | 健康检查 |
| `/api/v1/tasks/aggregate` | 业务编排 | GET | 多系统待办聚合 |
| `/api/v1/knowledge/documents` | 业务编排 | GET/POST | 文档列表/创建 |
| `/api/v1/audit/logs` | 业务编排 | GET | 审计日志查询 |

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
- **动态UI**: AI网关返回 JSON Spec，前端通过自定义 `DynamicRenderer` 组件渲染 Card/Table/Metric/List/Form/Tag/Chart（后续 Sprint 集成 `@json-render/react`，当前需 React 19）
- **适配器模式**: `BaseSystemAdapter` 抽象基类，子类实现 `fetchTasks()` / `executeAction()` 对接外部系统（ERP/CRM/OA）
- **前端状态**: Zustand 4.x 全局状态 + TanStack Query 5.x 服务端状态
- **Java数据层**: MyBatis-Plus 3.5.9 BaseMapper + 分页拦截器(PaginationInnerInterceptor) + 自动填充(MetaObjectHandler)
- **统一响应**: 业务编排层所有接口使用 `ApiResponse<T>` 封装，分页使用 `PageResult<T>`

## Java Layer Conventions

- **Entity**: `model/entity/` — 对应数据库表，使用 `@TableName` + `@TableId(ASSIGN_UUID)` + Lombok `@Data`
- **DTO**: `model/dto/` — 请求参数对象，分页查询继承 `PageQuery` 基类
- **VO**: `model/vo/` — 响应视图对象，不暴露数据库字段细节
- **Mapper**: `mapper/` — 继承 `BaseMapper<Entity>`，XML 在 `resources/mapper/`
- **Service**: 通过 `@RequiredArgsConstructor` 注入 Mapper，使用 MyBatis-Plus LambdaQueryWrapper
- **Controller**: 使用 DTO 接收参数，返回 `ApiResponse<VO>` 或 `ApiResponse<PageResult<VO>>`

## Configuration

- AI网关配置集中在 `ai-gateway/app/core/config.py`（pydantic-settings，从 `.env` 读取）
- 业务编排配置在 `business-server/src/main/resources/application-dev.yml`
- 前端API地址通过 `vite.config.ts` 分层代理控制（业务编排接口→:8080，AI网关接口→:8000）
- Docker基础设施默认凭据见 `docker/.env.example`

## Build Requirements

- **JDK 17 必须**: Lombok 1.18.36 不兼容 JDK 23+，`pom.xml` 已配置 `maven-compiler-plugin` annotationProcessorPaths
- **MyBatis-Plus 3.5.9**: 分页插件需要 `mybatis-plus-jsqlparser` 独立依赖
- **React 18**: `@json-render/react` 需 React 19，当前已移除，使用自定义 DynamicRenderer

## Reference Documents

核心架构文档（实现时务必对齐）：
- `docs/AI业务中台_整体技术架构文档.md` — 完整架构设计，4.1节为数据库Schema权威定义
- `docs/AI业务中台_MVP一期实施文档.md` — MVP范围，5.1-5.5节为接口规范
