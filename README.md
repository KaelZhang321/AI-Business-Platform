# AI业务中台 (AI Business Platform)

企业级AI业务中台，集成多源系统数据与AI能力，提供统一的智能工作台。

[![Java](https://img.shields.io/badge/Java-17-blue.svg)](https://www.oracle.com/java/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19-cyan.svg)](https://react.dev/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.3.6-brightgreen.svg)](https://spring.io/projects/spring-boot)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

## 项目简介

本项目是一个**面向企业的AI集成平台**，通过AI技术打通企业内部各业务系统（ERP、CRM、OA、预约、业务中台、360），实现：

- **统一工作台** — 一个界面聚合所有待办事项，6 个系统并行拉取
- **智能问答** — GraphRAG 三路融合检索（向量 + 关键词 + 知识图谱）
- **自然语言查数** — Text2SQL 自然语言转 SQL，自动生成可视化图表
- **动态 UI 生成** — AI 实时生成 7 种组件（Card/Table/Metric/List/Form/Tag/Chart）
- **工作流审批** — Flowable BPMN 引擎，通用审批流程

## 技术架构

```
                      ┌→ Nginx(:80) ──────────────────────────────┐
  前端(:5173) ──→ AI网关(:8000)     ──→ Ollama/Milvus/ES/ClickHouse/Neo4j
               └→ 业务编排(:8080)   ──→ MySQL/Redis/☁RabbitMQ/☁Nacos
                      └→ 监控: ☁Prometheus + ☁Grafana（云服务）
```

### 三层职责

| 层 | 技术栈 | 职责 |
|----|--------|------|
| **前端** | React 19 + Vite 5 + Ant Design 5 + Tailwind CSS | AI 对话、动态 UI 渲染（7 种组件）、数据可视化（ECharts） |
| **AI 网关** | Python 3.11+ / FastAPI + LangChain + LangGraph | 意图分类（4 类 + 9 子类）、GraphRAG、Text2SQL、LLM 多后端路由、MCP Server |
| **业务编排** | Java 17 / Spring Boot 3.3.6 + MyBatis-Plus 3.5.9 | 待办聚合（6 系统适配器）、知识库、审计日志 + ClickHouse、Flowable 工作流、数据权限 |

## 核心功能

### AI 对话（SSE 流式）
- 4 类一级意图自动分类：闲聊 / 知识检索 / 数据查询 / 任务管理
- 9 类二级意图精细路由：政策/产品/医疗知识、客户/销售/运营数据、任务查询/创建/审批
- 统一 SSE 信封格式（STREAM_START → STREAM_CHUNK → STREAM_END）
- Markdown 渲染 + 代码语法高亮

### GraphRAG 混合检索
- 三路融合：Milvus 向量（BGE-M3）+ ES 关键词（BM25）+ Neo4j 图谱
- RRF 融合排序 + BGE-Reranker-v2 重排序
- 意图自适应权重（FACTUAL / RELATIONAL / REASONING）
- Milvus 语义缓存（相似度 > 0.95 直接命中）

### Text2SQL 自然语言查数
- 基于 Vanna.ai，火山引擎 ARK（OpenAI 兼容接口）推理
- SQL 安全校验（黑名单 + 注释检测 + 多语句防护 + 自动 LIMIT）
- 自动生成可视化 UI Spec（Table + Metric + Chart 智能选型）

### 动态 UI 渲染
- AI 网关返回 JSON Spec → 前端 `@json-render/react` 渲染
- 7 种组件：Card / Table / Metric / List / Form / Tag / Chart
- 图表自动选型：柱状图 / 折线图 / 饼图 / 散点图 / 雷达图

### 待办聚合
- 适配器模式对接 6 个外部系统：ERP / CRM / OA / 预约 / 业务中台 / 360
- CompletableFuture 并行调用 + 断路器保护 + Caffeine/Redis 二级缓存

### 工作流引擎
- Flowable 7.1.0 BPMN 引擎
- 通用审批流程（提交 → 主管审批 → 通过/驳回）
- 流程部署 / 启动 / 认领 / 完成全生命周期

### 安全体系
- JWT 认证 + Refresh Token + SSO/Keycloak 预留
- RBAC + CASL 前端权限 + 行级/列级数据权限（MyBatis-Plus 拦截器）
- 数据脱敏（`@Sensitive` 注解：手机号/身份证/姓名）
- API 限流（`@RateLimit` + Redis 滑动窗口）
- SQL 安全（Text2SQL 黑名单 + JSqlParser AST 改写）
- Nginx 安全头 + CORS 域名白名单

## 快速开始

### 环境要求

| 工具 | 版本要求 |
|------|---------|
| Node.js | >= 18 |
| Python | >= 3.11 |
| JDK | **17**（Lombok 不兼容 JDK 23+） |
| Maven | >= 3.9 |
| Docker | >= 24 |

### 1. 启动基础设施

```bash
cd docker
cp .env.example .env   # 修改所有 <CHANGE_ME> 密码
docker compose up -d
```

### 2. 启动 AI 网关

```bash
cd ai-gateway
cp .env.example .env   # 配置 TEXT2SQL_API_KEY 等连接地址
pip install -e .
uvicorn app.main:app --reload --port 8000
```

API 文档：http://localhost:8000/docs

### 3. 启动业务编排

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
cd business-server
mvn spring-boot:run -Dspring-boot.run.profiles=dev

# 如需 Nacos 注册/配置中心（云环境）：
# mvn spring-boot:run -Pnacos -Dspring-boot.run.profiles=dev
```

Swagger 文档：http://localhost:8080/swagger-ui.html

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173（开发模式）或 http://localhost:80（Nginx 代理）

## 项目结构

```
AI业务中台/
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/         # chat / dynamic-ui / auth / ErrorBoundary
│   │   ├── pages/              # Workspace / KnowledgeBase / AuditLog / Login
│   │   ├── services/           # API 客户端（createClient 工厂）+ 认证服务
│   │   ├── stores/             # Zustand 状态管理
│   │   ├── abilities/          # CASL 前端权限定义
│   │   └── types/              # TypeScript 类型定义
│   └── vite.config.ts          # 分层代理规则
│
├── ai-gateway/                 # Python AI 网关
│   └── app/
│       ├── api/                # FastAPI 路由（chat / knowledge / query）
│       ├── services/           # 核心服务
│       │   ├── chat_workflow.py       # LangGraph 对话工作流
│       │   ├── intent_classifier.py   # 意图分类（4 类 + 9 子类）
│       │   ├── rag_service.py         # GraphRAG 三路融合检索
│       │   ├── text2sql_service.py    # Vanna.ai + ARK OpenAI 接口
│       │   ├── model_router.py        # 多后端 LLM 路由
│       │   ├── dynamic_ui_service.py  # JSON Spec UI 生成
│       │   └── semantic_cache.py      # Milvus 语义缓存
│       ├── mcp_server/         # MCP Server（FastMCP）
│       └── core/               # 配置 / 错误码
│
├── business-server/            # Java 业务编排（DDD 分层）
│   └── src/main/java/com/lzke/ai/
│       ├── domain/entity/      # 数据库实体（12 张表）
│       ├── application/        # DTO / VO
│       ├── infrastructure/     # MyBatis-Plus Mapper
│       ├── service/            # 业务服务
│       ├── controller/         # REST Controller
│       ├── interfaces/rest/    # 接口层
│       ├── security/           # JWT / RBAC / 数据权限 / 脱敏
│       ├── config/             # SecurityConfig / PasswordEncoderConfig / FlowableConfig
│       ├── adapter/            # 外部系统适配器（6 个）
│       ├── annotation/         # @RateLimit / @Sensitive 自定义注解
│       ├── aspect/             # 限流 / 脱敏 AOP 切面
│       └── listener/           # RabbitMQ 消费者
│
├── docker/                     # 基础设施
│   ├── docker-compose.yml            # 9 个本地服务
│   ├── docker-compose.ai-gateway.yml # AI 网关容器编排
│   ├── docker-compose.business-server.yml # 业务编排容器编排
│   ├── init-scripts/           # MySQL 初始化（12 张表）
│   ├── nginx/                  # Nginx 反向代理配置
│   ├── prometheus/             # Prometheus 抓取 + 告警规则
│   └── grafana/                # Grafana Dashboard 配置
│
└── docs/                       # 项目文档（7 个分类目录）
    ├── 00_产品全景与价值矩阵/   # 业务需求分析 + 产品价值矩阵
    ├── 01_产品设计/             # P1-P8 产品线详细设计（每线 4 篇）
    ├── 02_产品原型/             # 交互原型
    ├── 03_技术架构方案/         # 整体架构 + MVP 实施 + 集成指南
    ├── 04_技术补充方案/         # 6 篇补充方案
    ├── 05_技术优化方案/         # 6 篇优化方案
    └── 99_其他/                 # 架构审查 + 修改指南
```

## 服务端口

### 本地 Docker 服务（9 个）

| 服务 | 端口 | 用途 |
|------|------|------|
| Nginx | 80 | 反向代理统一入口 |
| MySQL | 3306 | 主数据库 |
| Redis | 6379 | 缓存 / 会话 / 限流 |
| Milvus | 19530 | 向量检索 |
| Elasticsearch | 9200 | 全文搜索 |
| MinIO | 9000 | 对象存储（S3 兼容） |
| ClickHouse | 8123 | OLAP 审计分析 |
| Ollama | 11434 | 本地 LLM |
| Neo4j | 7474 / 7687 | 知识图谱 |

### 云服务（配置指向云地址）

| 服务 | 用途 |
|------|------|
| RabbitMQ | 异步消息队列（文档处理/审计日志/缓存失效） |
| Prometheus + Grafana | 整体监控系统（复用） |
| Nacos | 服务注册 / 配置中心（Maven profile `-Pnacos` 按需引入） |

### 应用服务

| 服务 | 端口 |
|------|------|
| 前端（Vite） | 5173 |
| AI 网关（FastAPI） | 8000 |
| 业务编排（Spring Boot） | 8080 |

## API 端点

### AI 网关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat` | SSE 流式对话 |
| POST | `/api/v1/knowledge/search` | RAG 知识检索 |
| POST | `/api/v1/query/text2sql` | 自然语言转 SQL |
| POST | `/api/v1/query/train` | 导入训练数据 |
| POST | `/api/v1/query/train-schema` | 从 DDL 自动训练 |
| SSE | `/mcp` | MCP Server |
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus 指标 |

### 业务编排

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/tasks/aggregate` | 多系统待办聚合 |
| GET/POST | `/api/v1/knowledge/documents` | 文档列表 / 创建 |
| POST | `/api/v1/knowledge/documents/upload` | 文件上传（MinIO） |
| GET | `/api/v1/audit/logs` | 审计日志查询 |
| GET | `/api/v1/audit/analytics/*` | ClickHouse 统计分析 |
| POST | `/api/v1/auth/login` | JWT 登录 |
| POST | `/api/v1/auth/refresh` | Token 刷新 |
| GET/POST | `/api/v1/workflow/*` | Flowable 工作流 |
| GET | `/actuator/prometheus` | Prometheus 指标 |

## 数据库设计

12 张核心表定义在 `docker/init-scripts/init-mysql.sql`：

| 表名 | 用途 |
|------|------|
| `users` | 用户信息与角色 |
| `system_adapters` | 系统适配器配置（6 条预置） |
| `tasks` | 待办任务（多系统聚合） |
| `documents` | 知识库文档 |
| `conversations` | AI 对话历史 |
| `audit_logs` | 审计日志 |
| `api_keys` | 应用级密钥管理 |
| `knowledge_bases` | 知识库元数据 |
| `workflows` | 自定义工作流 |
| `workflow_executions` | 工作流执行记录 |
| `agents` | 智能体配置 |
| `cost_logs` | 成本日志 |

## 技术栈

| 类别 | 技术 |
|------|------|
| 前端框架 | React 19 + TypeScript 5 + Vite 5 |
| UI 组件 | Ant Design 5 + Tailwind CSS |
| AI 对话 | assistant-ui 0.12+ |
| 动态渲染 | @json-render/react 0.14 + ECharts |
| 状态管理 | Zustand 4 + TanStack Query 5 |
| AI 网关 | FastAPI + LangChain 0.3 + LangGraph 0.2 |
| 向量检索 | Milvus（BGE-M3）+ BGE-Reranker-v2 |
| Text2SQL | Vanna.ai + 火山引擎 ARK |
| 知识图谱 | Neo4j 5 + APOC |
| MCP | FastMCP |
| 业务框架 | Spring Boot 3.3.6 + MyBatis-Plus 3.5.9 |
| 工作流 | Flowable 7.1.0 |
| 缓存 | Caffeine + Redis + Redisson |
| 消息队列 | RabbitMQ（云服务） |
| 对象存储 | MinIO（S3 兼容） |
| 分析库 | ClickHouse |
| 监控 | Prometheus + Grafana + Micrometer + prometheus-client |
| 追踪 | LangSmith |

## 配置说明

| 配置文件 | 说明 |
|----------|------|
| `docker/.env` | 基础设施密码（从 `.env.example` 复制） |
| `ai-gateway/.env` | AI 网关连接地址和 API Key |
| `business-server/src/main/resources/application-dev.yml` | Spring Boot 开发环境（MySQL） |
| `business-server/src/main/resources/application-docker.yml` | Docker 生产环境（PostgreSQL） |
| `business-server/src/main/resources/bootstrap.yml` | Nacos 配置（需 `-Pnacos` 构建才生效） |
| `frontend/vite.config.ts` | API 代理分层规则 |

## 文档

完整项目文档位于 `docs/` 目录，按 7 个分类组织：

| 目录 | 内容 |
|------|------|
| `00_产品全景与价值矩阵/` | 业务需求分析报告、产品全景与价值矩阵、行业标准对比 |
| `01_产品设计/` | P1-P8 产品线详细设计（每线含需求/功能/交互/迭代 4 篇） |
| `02_产品原型/` | 核心功能交互原型 |
| `03_技术架构方案/` | 整体技术架构文档（权威参考）、MVP 一期实施文档、json-render 集成指南 |
| `04_技术补充方案/` | 6 篇：命名规范 / Agent 选型 / 离线模式 / 存储运维 / WebRTC / 统一认证 |
| `05_技术优化方案/` | 6 篇：医疗合规 / P6 技术栈 / 缓存策略 / API 版本 / GraphRAG / 容量规划 |
| `99_其他/` | 技术架构审查报告、文档修改执行指南 |

## License

MIT License
