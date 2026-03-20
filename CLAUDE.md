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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **AI业务中台** (501 symbols, 935 relationships, 24 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/AI业务中台/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/AI业务中台/context` | Codebase overview, check index freshness |
| `gitnexus://repo/AI业务中台/clusters` | All functional areas |
| `gitnexus://repo/AI业务中台/processes` | All execution flows |
| `gitnexus://repo/AI业务中台/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
