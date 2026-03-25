# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI业务中台 — 企业级AI平台，三层架构：React 前端 → Python AI网关 → Java 业务编排层，底层 Docker Compose 本地基础设施（9个服务）+ 云服务（RabbitMQ/Prometheus/Grafana/Nacos）。

## Repository Structure

```
AI业务中台/
├── frontend/          # React 19 + Vite 5 + TypeScript 5 + Ant Design 5 + Tailwind CSS
├── ai-gateway/        # Python 3.11+ / FastAPI + LangChain 0.3 + LangGraph 0.2
├── business-server/   # Java 17 / Spring Boot 3.3.6 + MyBatis-Plus 3.5.9
├── docker/            # Docker Compose 基础设施编排（13个服务）
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
                    ┌→ Nginx(:80) ─────────────────────────────┐
前端(:5173) ──→ AI网关(:8000)     ──→ Ollama/Milvus/ES/ClickHouse/Neo4j
             └→ 业务编排(:8080)   ──→ MySQL/Redis/☁RabbitMQ/☁Nacos
                    └→ 监控: ☁Prometheus + ☁Grafana（云服务）
```

Vite 代理分层规则（`vite.config.ts`）：
- `/api/v1/tasks/**`, `/api/v1/knowledge/documents/**`, `/api/v1/audit/**` → `:8080`（业务编排）
- 其余 `/api/**` → `:8000`（AI网关）

### 三层职责

- **前端** (T5/T6): UI渲染、AI对话（assistant-ui 0.12+）、动态UI渲染（自定义 DynamicRenderer 支持 Card/Table/Metric/List/Form/Tag/Chart 7种组件）、数据可视化（ECharts）
- **AI网关** (T4.1): 意图分类（4类+9子类）、GraphRAG混合检索（Milvus向量+ES关键词+Neo4j图谱+RRF融合+BGE-Reranker）、Text2SQL（Vanna.ai+连接池）、LLM调用（ModelRouter多后端路由）、MCP Server、Prometheus 指标
- **业务编排** (T2/T4.2): 待办聚合（适配器模式: ERP/CRM/OA/预约/业务中台/360）、知识库管理、审计日志+ClickHouse分析、Flowable工作流、行列级数据权限、API限流、数据脱敏

### API端点

| 路径 | 层 | 方法 | 说明 |
|------|-----|------|------|
| `/api/v1/chat` | AI网关 | POST | SSE流式对话 |
| `/api/v1/knowledge/search` | AI网关 | POST | RAG知识检索 |
| `/api/v1/query/text2sql` | AI网关 | POST | 自然语言查数 |
| `/mcp` | AI网关 | SSE | MCP Server |
| `/health` | AI网关 | GET | 健康检查 |
| `/metrics` | AI网关 | GET | Prometheus 指标 |
| `/api/v1/tasks/aggregate` | 业务编排 | GET | 多系统待办聚合 |
| `/api/v1/knowledge/documents` | 业务编排 | GET/POST | 文档列表/创建 |
| `/api/v1/knowledge/documents/upload` | 业务编排 | POST | 文件上传(MinIO) |
| `/api/v1/audit/logs` | 业务编排 | GET | 审计日志查询 |
| `/api/v1/auth/login` | 业务编排 | POST | JWT登录 |
| `/api/v1/auth/refresh` | 业务编排 | POST | Token刷新 |
| `/api/v1/workflow/*` | 业务编排 | GET/POST | Flowable工作流 |
| `/actuator/prometheus` | 业务编排 | GET | Prometheus 指标 |

## Service Ports

| 服务 | 端口 |
|------|------|
| Nginx (反向代理) | 80 |
| 前端 (Vite) | 5173 |
| AI网关 (FastAPI) | 8000 |
| 业务编排 (Spring Boot) | 8080 |
| MySQL | 3306 |
| Redis | 6379 |
| Milvus | 19530 |
| Elasticsearch | 9200 |
| MinIO | 9000 |
| ClickHouse | 8123 |
| Ollama | 11434 |
| Neo4j | 7474 / 7687 |
| ☁ RabbitMQ | 云服务（应用配置指向云地址） |
| ☁ Prometheus | 云服务（复用整体监控系统） |
| ☁ Grafana | 云服务（复用整体监控系统） |
| ☁ Nacos | 云服务（应用配置指向云地址） |

## Key Technical Decisions

- **数据库Schema**: 12张表定义在 `docker/init-scripts/init-mysql.sql`（users/system_adapters/tasks/documents/conversations/audit_logs/api_keys/knowledge_bases/workflows/workflow_executions/agents/cost_logs），含 FK ON DELETE 策略，严格对齐架构文档 4.1节
- **RAG策略**: 向量(Milvus BGE-M3) + 关键词(ES BM25) + RRF融合 + BGE-Reranker-v2重排序
- **Text2SQL**: 基于 Vanna.ai，使用火山引擎 ARK（OpenAI 兼容接口）推理 + Milvus 向量存储
- **动态UI**: AI网关返回 JSON Spec，前端通过 `@json-render/react` 0.14 + Ant Design 混合渲染 Card/Table/Metric/List/Form/Tag/Chart 7种组件，catalog.ts 定义 Zod schema + actions
- **适配器模式**: `BaseSystemAdapter` 抽象基类，子类实现 `fetchTasks()` / `executeAction()` 对接外部系统（ERP/CRM/OA/预约/业务中台/360）
- **前端状态**: Zustand 4.x 全局状态 + TanStack Query 5.x 服务端状态
- **Java数据层**: MyBatis-Plus 3.5.9 BaseMapper + 分页拦截器(PaginationInnerInterceptor) + 行级权限拦截器(DataPermissionInterceptor, JSqlParser安全改写) + 自动填充(MetaObjectHandler)
- **统一响应**: 业务编排层所有接口使用 `ApiResponse<T>` 封装，分页使用 `PageResult<T>`
- **工作流**: Flowable 7.1.0 BPMN引擎，通用审批流程（提交→主管审批→通过/驳回）
- **安全**: JWT认证 + RBAC + 行列级数据权限 + 数据脱敏(@Sensitive) + API限流(@RateLimit, Redis滑动窗口) + Nginx安全头
- **可观测性**: Prometheus + Grafana + Micrometer(Java) + prometheus_client(Python) + LangSmith追踪

## Java Layer Conventions (DDD 分层)

- **Entity**: `domain/entity/` — 对应数据库表，使用 `@TableName` + `@TableId(ASSIGN_UUID)` + Lombok `@Data`
- **DTO**: `application/dto/` — 请求参数对象，分页查询继承 `PageQuery` 基类
- **VO**: `application/vo/` — 响应视图对象，不暴露数据库字段细节
- **Mapper**: `infrastructure/persistence/mapper/` — 继承 `BaseMapper<Entity>`，XML 在 `resources/mapper/`
- **Service**: `service/` — 通过 `@RequiredArgsConstructor` 注入 Mapper，使用 MyBatis-Plus LambdaQueryWrapper
- **Controller**: `controller/` 或 `interfaces/rest/` — 使用 DTO 接收参数，返回 `ApiResponse<VO>` 或 `ApiResponse<PageResult<VO>>`
- **MapperScan**: 单一路径 `com.lzke.ai.infrastructure.persistence.mapper`

## Configuration

- AI网关配置集中在 `ai-gateway/app/core/config.py`（pydantic-settings，从 `.env` 读取）
- 业务编排配置在 `business-server/src/main/resources/application-dev.yml`，Nacos 配置在 `bootstrap.yml`（默认禁用）
- 前端API地址通过 `vite.config.ts` 分层代理控制（业务编排接口→:8080，AI网关接口→:8000）
- Docker基础设施默认凭据见 `docker/.env.example`

## Build Requirements

- **JDK 17 必须**: Lombok 1.18.36 不兼容 JDK 23+，`pom.xml` 已配置 `maven-compiler-plugin` annotationProcessorPaths
- **MyBatis-Plus 3.5.9**: 分页插件需要 `mybatis-plus-jsqlparser` 独立依赖
- **React 19**: 已升级至 React 19，`@json-render/react` 0.14 已集成

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
