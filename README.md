# AI业务中台

企业级AI业务中台，集成多源系统数据与AI能力，提供统一的智能工作台。

## 技术架构

| 层级 | 技术栈 | 路径 |
|------|--------|------|
| 前端 (T5/T6) | React 18 + Vite 5 + TypeScript 5 + Ant Design 5 + Tailwind CSS | `frontend/` |
| AI网关 (T4.1) | Python 3.11+ / FastAPI + LangChain 0.3 + LangGraph 0.2 | `ai-gateway/` |
| 业务编排 (T2/T4.2) | Java 17 / Spring Boot 3.3 + MyBatis-Plus 3.5.9 | `business-server/` |
| 基础设施 | Docker Compose（8个服务） | `docker/` |

### 请求流向

```
前端(:5173) ──→ AI网关(:8000)     ──→ Ollama / Milvus / ES / ClickHouse
             └→ 业务编排(:8080)   ──→ PostgreSQL / Redis / RabbitMQ
```

前端 Vite 代理自动按路径分流：`/api/v1/tasks`、`/api/v1/knowledge/documents`、`/api/v1/audit` → :8080，其余 `/api` → :8000。

## 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Node.js | 18+ | 前端构建 |
| Python | 3.11+ | AI网关 |
| JDK | **17**（必须） | 业务编排层，Lombok 不兼容 JDK 23+ |
| Maven | 3.9+ | Java 构建 |
| Docker | 24+ | 基础设施 |

> **JDK 注意**：如系统默认 JDK 非 17，需手动指定：
> ```bash
> export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
> ```

## 快速启动

### 1. 启动基础设施

```bash
cd docker
cp .env.example .env
docker compose up -d
```

### 2. 启动 AI 网关

```bash
cd ai-gateway
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

### 3. 启动业务编排层

```bash
cd business-server
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
mvn spring-boot:run
```

服务运行在 http://localhost:8080

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 进入统一工作台。

## 项目结构

```
AI业务中台/
├── frontend/                          # React 前端
│   ├── src/
│   │   ├── components/chat/           # AI对话组件 (assistant-ui)
│   │   ├── components/dynamic-ui/     # 动态UI渲染 (7种组件类型)
│   │   ├── layouts/MainLayout.tsx     # 主布局（导航+对话+内容）
│   │   ├── pages/                     # Workspace / KnowledgeBase
│   │   ├── stores/useAppStore.ts      # Zustand 全局状态
│   │   ├── services/api.ts            # 双API客户端
│   │   └── types/index.ts             # 全局类型定义
│   └── vite.config.ts                 # 分层代理配置
├── ai-gateway/                        # Python AI网关
│   ├── app/
│   │   ├── api/routes/                # chat(SSE) / knowledge / query
│   │   ├── services/                  # 意图分类 / RAG / Text2SQL / LLM / 动态UI
│   │   ├── models/schemas.py          # Pydantic 请求响应模型
│   │   └── core/config.py             # pydantic-settings 配置
│   └── pyproject.toml                 # Python 依赖
├── business-server/                   # Java 业务编排层
│   ├── src/main/java/com/lzke/ai/
│   │   ├── controller/                # Task / Knowledge / Audit
│   │   ├── service/                   # 待办聚合 / 知识库 / 审计
│   │   ├── adapter/                   # BaseSystemAdapter + ERP/CRM/OA
│   │   ├── mapper/                    # 6个 MyBatis-Plus Mapper
│   │   ├── model/entity/              # 6个实体 (对齐文档4.1节)
│   │   ├── model/dto/                 # 请求参数 DTO
│   │   ├── model/vo/                  # 响应视图 VO + 统一ApiResponse
│   │   └── config/                    # Web/Redis/RabbitMQ/MyBatisPlus
│   └── pom.xml
├── docker/                            # 基础设施
│   ├── docker-compose.yml             # 8个服务编排
│   └── init-scripts/init-postgres.sql # 6张核心表 Schema
└── docs/                              # 架构设计文档（16篇）
```

## 服务端口

| 服务 | 端口 |
|------|------|
| 前端 (Vite) | 5173 |
| AI网关 (FastAPI) | 8000 |
| 业务编排 (Spring Boot) | 8080 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Milvus | 19530 |
| RabbitMQ | 5672 / 15672 (管理界面) |
| Elasticsearch | 9200 |
| MinIO | 9000 / 9001 (控制台) |
| ClickHouse | 8123 |
| Ollama | 11434 |

## API 端点

| 路径 | 层 | 说明 |
|------|-----|------|
| `POST /api/v1/chat` | AI网关 | SSE流式对话（意图分类→路由→响应） |
| `POST /api/v1/knowledge/search` | AI网关 | RAG混合检索（向量+关键词+RRF融合） |
| `POST /api/v1/query/text2sql` | AI网关 | 自然语言转SQL（Vanna.ai） |
| `GET /health` | AI网关 | 健康检查 |
| `GET /api/v1/tasks/aggregate` | 业务编排 | 多系统待办聚合（ERP/CRM/OA） |
| `POST /api/v1/knowledge/documents` | 业务编排 | 知识库文档管理 |
| `GET /api/v1/knowledge/documents` | 业务编排 | 文档列表（分页） |
| `GET /api/v1/audit/logs` | 业务编排 | 审计日志查询（分页） |

## 数据库 Schema

6张核心表定义在 `docker/init-scripts/init-postgres.sql`，严格对齐架构文档 4.1 节：

| 表名 | 说明 |
|------|------|
| `users` | 用户表 |
| `system_adapters` | 系统适配器配置表 |
| `tasks` | 待办任务表（多系统聚合） |
| `documents` | 知识库文档表 |
| `conversations` | 会话历史表（逐条消息） |
| `audit_logs` | AI调用审计日志 |

## 项目文档

详细架构设计文档见 `docs/` 目录，核心参考：

- `docs/AI业务中台_整体技术架构文档.md` — 完整架构设计，4.1节为数据库 Schema 权威定义
- `docs/AI业务中台_MVP一期实施文档.md` — MVP范围，5.1-5.5节为接口规范
