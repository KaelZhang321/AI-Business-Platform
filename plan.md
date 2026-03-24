# AI业务中台 — 待办任务清单

> **基准文档**：`docs/AI业务中台_整体技术架构文档.md` V1.0
> **审查日期**：2026-03-23
> **审查方法**：逐层对比架构文档与实际代码，标注差异项

---

## 总体完成度

| 层 | 完成度 | 剩余差距 |
|---|---|---|
| AI网关 (Python) | ~99% | — |
| 业务编排 (Java) | ~99% | — |
| 前端 (React) | ~99% | — |
| 基础设施 (Docker) | ~99% | — |

---

## Sprint 2：MVP核心功能补齐

### S2-1. AI网关 — Task节点对接业务编排层（文档 1.3 流程3）

**现状**：`chat_workflow.py` 的 `_handle_task` 节点返回硬编码占位文本，未调用业务编排层。

- [x] `ai-gateway/app/services/chat_workflow.py`：`_handle_task` 节点通过 httpx 调用 `http://localhost:8080/api/v1/tasks/aggregate`，将返回的任务列表传给 `dynamic_ui_service` 生成 UI Spec
- [x] `ai-gateway/app/services/dynamic_ui_service.py`：task 意图的 UI Spec 使用实际任务数据填充，支持 actions（view_detail / trigger_task）
- [x] `ai-gateway/app/core/config.py`：新增 `business_server_url: str = "http://localhost:8080"` 配置项

### S2-2. AI网关 — 二级意图分类（文档 3.1）

**现状**：仅支持4个一级意图（chat/knowledge/query/task），缺少二级分类。

- [x] `ai-gateway/app/models/schemas.py`：新增 `SubIntentType` 枚举（knowledge_policy / knowledge_product / knowledge_medical / data_customer / data_sales / data_operation / task_query / task_create / task_approve）
- [x] `ai-gateway/app/services/intent_classifier.py`：LLM Prompt 返回一级+二级意图；`IntentResult` 增加 `sub_intent` 字段；关键词规则扩展二级匹配
- [x] `ai-gateway/app/services/chat_workflow.py`：`ChatState` 增加 `sub_intent` 字段，各处理节点可根据 sub_intent 做精细化处理

### S2-3. AI网关 — 动态UI服务增强（文档 3.4）

**现状**：完全硬编码模板生成，Chart 仅支持 bar 类型。

- [x] `ai-gateway/app/services/dynamic_ui_service.py`：根据数据特征自动选择 Chart 类型（柱状图/折线图/饼图），当前后端只生成 bar 而前端已支持 line/pie/scatter/radar
- [x] `ai-gateway/app/services/dynamic_ui_service.py`：Metric 组件支持 sum/count/avg/min/max 等多种聚合方式（当前仅 mean）
- [x] `ai-gateway/app/services/dynamic_ui_service.py`：LLM 辅助生成 UI Spec 接口（`_llm_generate_spec()`，配置 `LLM_UI_SPEC_ENABLED=true` 启用，默认回退规则模式）

### S2-4. 业务编排 — RabbitMQ 消费者实现（文档 4.3）

**现状**：仅声明了3个队列（task.sync / document.process / audit.log），无消费者/生产者。

- [x] `business-server/.../config/RabbitMQConfig.java`：补充 Exchange 声明（DirectExchange）和 Binding 配置
- [x] 新建 `business-server/.../listener/DocumentProcessListener.java`：监听 `document.process` 队列，触发文档分块/向量化流程（调用 AI 网关）
- [x] 新建 `business-server/.../listener/AuditLogListener.java`：监听 `audit.log` 队列，异步写入审计日志
- [x] `business-server/.../service/KnowledgeApplicationService.java`：`createDocument()` 中通过 `RabbitTemplate.convertAndSend()` 发送文档处理消息

### S2-5. 业务编排 — 补齐缺失的系统适配器（文档 2.3）

**现状**：已实现 ERP/CRM/OA 三个适配器，缺失预约系统/业务中台/360系统。

- [x] 新建 `business-server/.../adapter/ReservationAdapter.java`：继承 BaseSystemAdapter，对接预约系统 API
- [x] 新建 `business-server/.../adapter/BizCenterAdapter.java`：继承 BaseSystemAdapter，对接业务中台 API
- [x] 新建 `business-server/.../adapter/System360Adapter.java`：继承 BaseSystemAdapter，对接360系统 API
- [x] `docker/init-scripts/init-mysql.sql`：`system_adapters` 表补充6条预置数据

### S2-6. 业务编排 — JWT Token 刷新机制

**现状**：JWT 仅支持签发，无刷新/吊销机制。

- [x] `business-server/.../security/JwtTokenProvider.java`：新增 `generateRefreshToken()` 方法，refresh token 有效期7天
- [x] `business-server/.../controller/AuthController.java`：新增 `POST /api/v1/auth/refresh` 端点
- [x] `frontend/src/services/auth.ts`：Axios interceptor 在 401 时自动尝试 refresh token

### S2-7. 前端 — Markdown 渲染与代码高亮（文档 2.1）

**现状**：AIChat 中 assistant-ui 的消息仅为纯文本渲染，缺少 Markdown 和代码高亮。

- [x] `frontend/package.json`：安装 `react-markdown` + `remark-gfm` + `rehype-highlight`（或 `prismjs`）
- [x] `frontend/src/components/chat/AIChat.tsx`：AssistantMessage 组件中集成 Markdown 渲染器，支持表格/列表/代码块语法高亮

### S2-8. 前端 — Form 组件 onSubmit 回调

**现状**：DynamicRenderer 中 Form 组件的提交按钮无功能。

- [x] `frontend/src/components/dynamic-ui/DynamicRenderer.tsx`：Form 组件补充 `onSubmit` 回调，将表单数据通过 action（trigger_task）发送到后端

---

## Sprint 3：增强功能与集成

### S3-1. AI网关 — MCP Server 实现（文档 2.2 / 4.2）

**现状**：`fastmcp>=0.4.0` 依赖已列入 pyproject.toml，但无任何实现代码。

- [x] 新建 `ai-gateway/app/mcp/server.py`：使用 FastMCP 创建 MCP Server 实例
- [x] 新建 `ai-gateway/app/mcp/tools.py`：注册 MCP 工具集（rag_search / text2sql / task_query / knowledge_search）
- [x] `ai-gateway/app/main.py`：挂载 MCP Server 路由（`/mcp`）

### S3-2. AI网关 — ModelRouter 模型路由（文档 2.2）

**现状**：LLMService 硬编码 Ollama 单一后端，无路由/切换/负载均衡。

- [x] 新建 `ai-gateway/app/services/model_router.py`：ModelRouter 类，支持按策略路由到不同后端（Ollama / vLLM / OpenAI API）
- [x] `ai-gateway/app/services/llm_service.py`：改为通过 ModelRouter 获取后端，支持 fallback（本地模型失败时切换到外部 API）
- [x] `ai-gateway/app/core/config.py`：新增 `openai_api_key`/`openai_base_url` 配置（ModelRouter 自动组装后端列表）

### S3-3. AI网关 — LangSmith 追踪集成（文档 4.2）

**现状**：完全缺失，无 LangChain/LangGraph 调用链路可观测性。

- [x] `ai-gateway/pyproject.toml`：新增 `langsmith` 依赖
- [x] `ai-gateway/app/core/config.py`：新增 `langsmith_api_key`、`langsmith_project` 配置
- [x] `ai-gateway/app/main.py`：lifespan 中初始化 LangSmith tracing（设置环境变量 `LANGCHAIN_TRACING_V2=true`）

### S3-4. 业务编排 — MinIO 对象存储集成（文档 4.5 / 5.3）

**现状**：Docker 中 MinIO 已运行，但 Java 层无集成代码，文档上传无文件存储。

- [x] `business-server/pom.xml`：新增 `minio` SDK 依赖
- [x] 新建 `business-server/.../config/MinIOConfig.java`：MinIO 客户端配置
- [x] 新建 `business-server/.../service/StorageService.java`：文件上传/下载/删除（S3 兼容 API）
- [x] `business-server/.../controller/KnowledgeController.java`：新增 `POST /api/v1/knowledge/documents/upload` 文件上传端点
- [x] `business-server/.../resources/application-dev.yml`：新增 MinIO 连接配置

### S3-5. 业务编排 — ClickHouse 审计日志分析（文档 4.3 / 5.3）

**现状**：审计日志仅存于 MySQL，未流向 ClickHouse 做分析查询。

- [x] `business-server/pom.xml`：新增 `clickhouse-jdbc` 依赖
- [x] 新建 `business-server/.../config/ClickHouseConfig.java`：ClickHouse 数据源配置
- [x] 新建 `business-server/.../service/AnalyticsService.java`：审计日志统计分析（按意图/模型/时间段聚合）
- [x] `business-server/.../listener/AuditLogListener.java`：MQ 消费后双写 PG + ClickHouse
- [x] `business-server/.../controller/AuditController.java`：新增分析查询端点

### S3-6. 业务编排 — 数据脱敏（文档 7.2）

**现状**：完全缺失，敏感字段（手机号、身份证、姓名）以明文返回。

- [x] 新建 `business-server/.../security/DataMaskingUtil.java`：脱敏工具类（手机号: 138****1234，身份证: 110***********1234，姓名: 张*）
- [x] 新建 `business-server/.../annotation/Sensitive.java`：自定义注解 `@Sensitive(type = SensitiveType.PHONE)` + `SensitiveType` 枚举
- [x] 新建 `business-server/.../serializer/SensitiveJsonSerializer.java`：Jackson 序列化拦截器，自动脱敏标注字段

### S3-7. 业务编排 — API 限流（文档 7.2）

**现状**：无任何限流机制。

- [x] `business-server/pom.xml`：新增 `spring-boot-starter-aop` + 自定义限流注解
- [x] 新建 `business-server/.../annotation/RateLimit.java`：自定义限流注解 `@RateLimit(permits=100, period=60)`
- [x] 新建 `business-server/.../aspect/RateLimitAspect.java`：AOP 切面，基于 Redis INCR + EXPIRE 实现滑动窗口限流
- [x] 在核心 Controller 方法上添加 `@RateLimit` 注解（TaskController / KnowledgeController / AuditController）

### S3-8. 前端 — SSO / Keycloak 集成预留（文档 7.1）

**现状**：本地用户名密码认证，无 SSO 集成。

- [x] `frontend/src/services/auth.ts`：新增 `loginWithSSO()` / `isSSOEnabled()` 方法，通过环境变量配置 Keycloak
- [x] `frontend/src/pages/Login.tsx`：新增"企业SSO登录"按钮（条件渲染，`VITE_KEYCLOAK_URL` 配置启用）

---

## Sprint 4：生产就绪与高级功能

### S4-1. 业务编排 — Flowable 工作流引擎（文档 2.3 / 4.3）

**现状**：完全缺失，架构文档规划的 WorkflowService 未实现。

- [x] `business-server/pom.xml`：新增 `flowable-spring-boot-starter-process` 7.1.0 依赖
- [x] 新建 `business-server/.../service/WorkflowService.java`：流程部署/启动/审批/查询/认领
- [x] 新建 `business-server/.../interfaces/rest/WorkflowController.java`：`/api/v1/workflow/*` 端点（deploy/start/tasks/complete/claim）
- [x] 在 `resources/processes/general-approval.bpmn20.xml` 新建通用审批流程 BPMN（提交→主管审批→通过/驳回循环）

### S4-2. 业务编排 — Spring Cloud Alibaba / Nacos（文档 2.3 / 4.3）

**现状**：单体 Spring Boot 应用，无服务注册/配置中心。

- [x] `business-server/pom.xml`：新增 `spring-cloud-starter-alibaba-nacos-config` + `nacos-discovery`（BOM 管理 2023.0.3.2）
- [x] `docker/docker-compose.yml`：新增 Nacos Server 服务（v2.3.1 standalone 模式，端口 8848/9848）
- [x] `business-server/.../resources/bootstrap.yml`：Nacos 注册中心和配置中心地址（默认 `NACOS_ENABLED=false`，按需启用）

### S4-3. 业务编排 — 行列级数据权限（文档 7.1）

**现状**：RBAC 仅到角色级别，缺少行级/列级权限控制。

- [x] 新建 `business-server/.../security/DataPermissionInterceptor.java`：MyBatis-Plus InnerInterceptor，根据用户角色自动追加 `WHERE user_id = ?` 条件（admin 全量，user/viewer 仅自己）
- [x] 新建 `business-server/.../annotation/ColumnPermission.java`：列级权限注解 `@ColumnPermission(roles={"admin"})`
- [x] 新建 `business-server/.../serializer/ColumnPermissionSerializer.java`：Jackson ContextualSerializer，不满足角色时输出 null/fallback
- [x] `config/MyBatisPlusConfig.java`：注册 DataPermissionInterceptor 到拦截器链

### S4-4. 基础设施 — Neo4j 图数据库部署（文档 3.2 / v1.5 GraphRAG）

**现状**：AI 网关已预留 Neo4j 接口和配置，但 Docker 中未部署。

- [x] `docker/docker-compose.yml`：新增 Neo4j 服务（neo4j:5-community，端口 7474/7687，含 APOC 插件）
- [x] `docker/.env.example`：新增 NEO4J_PASSWORD 环境变量

### S4-5. 基础设施 — 监控与可观测性（文档 4.5）

**现状**：无 Prometheus/Grafana/SkyWalking 等监控组件。

- [x] `docker/docker-compose.yml`：新增 Prometheus（v2.51.0，端口 9090）+ Grafana（v10.4.0，端口 3000）服务
- [x] 新建 `docker/prometheus/prometheus.yml`：抓取 AI 网关 `/metrics` 和业务编排 `/actuator/prometheus`
- [x] `business-server/pom.xml`：新增 `spring-boot-starter-actuator` + `micrometer-registry-prometheus` 依赖
- [x] `ai-gateway/pyproject.toml`：新增 `prometheus-client` 依赖
- [x] `ai-gateway/app/main.py`：新增 `/metrics` 端点 + HTTP 中间件（request_count + request_latency 指标）
- [x] `application-dev.yml`：Actuator 暴露 health/info/prometheus/metrics 端点

### S4-6. 基础设施 — Nginx 反向代理（文档 6.2）

**现状**：前端通过 Vite 代理直连后端，无统一入口。

- [x] 新建 `docker/nginx/nginx.conf`：反向代理配置（tasks/documents/audit/auth/workflow → :8080，/api|/mcp|/health → :8000，/ → :5173，含 SSE 支持）
- [x] `docker/docker-compose.yml`：新增 Nginx 服务（端口 80）

### S4-7. 基础设施 — 缺失的数据库表（文档 5.2）

**现状**：6张核心表已建，但架构文档核心数据模型中还有多个实体未建表。

- [x] `docker/init-scripts/init-mysql.sql`：新增 `api_keys` 表（应用级密钥管理，含 rate_limit/permissions/expires_at）
- [x] `docker/init-scripts/init-mysql.sql`：新增 `knowledge_bases` 表（知识库元数据，含 embedding_model/chunk_strategy 配置）
- [x] `docker/init-scripts/init-mysql.sql`：新增 `workflows` + `workflow_executions` 表（自定义工作流记录）
- [x] `docker/init-scripts/init-mysql.sql`：新增 `agents` 表（智能体配置，含 model/system_prompt/tools/temperature）
- [x] `docker/init-scripts/init-mysql.sql`：新增 `cost_logs` 表（独立成本日志，含 provider/cost_usd）

---

## 代码质量优化

> **审查日期**：2026-03-24
> **审查方法**：四层并行审计（AI网关/业务编排/前端/基础设施），共发现83个问题

### 第一轮：CRITICAL 安全与稳定性（已完成）

- [x] **Java 包结构统一**：`model/entity/` → `domain/entity/`、`model/dto/` → `application/dto/`、`mapper/` → `infrastructure/persistence/mapper/`，删除旧目录，MapperScan 收敛为单一路径
- [x] **XML Mapper namespace 修正**：TaskMapper.xml / DocumentMapper.xml namespace 对齐新包路径
- [x] **DataPermissionInterceptor SQL注入修复**：字符串拼接 → JSqlParser AST 安全改写 + MetaObject 替代反射
- [x] **Text2SQL 连接池**：`asyncpg.connect()` 逐次连接 → `asyncpg.create_pool()` 连接池复用
- [x] **Text2SQL 事件循环阻塞**：Vanna.ai 同步调用 → `asyncio.to_thread()` 包装
- [x] **Text2SQL 删除未使用 import**：移除 `import json`
- [x] **前端 401 刷新竞态条件**：可变全局状态 → 共享 Promise 模式，消除并发 401 重复刷新

### 第二轮：数据完整性与配置规范化（已完成）

- [x] **6张新表 Entity 类**：ApiKey / KnowledgeBase / Workflow / WorkflowExecution / Agent / CostLog 对齐 init-mysql.sql 4.1.7-4.1.12
- [x] **6个 Mapper 接口 + XML**：继承 BaseMapper，namespace 正确
- [x] **RAGService 命名冲突**：`_neo4j_driver` 字段与方法同名 → 字段 `_neo4j` + 方法 `_neo4j_client()`
- [x] **RAGService 资源泄漏**：新增 `close()` 方法释放 ES / Neo4j / ClickHouse 连接
- [x] **main.py 生命周期管理**：lifespan 创建共享 `app.state.rag_service`，shutdown 调用 `close()`
- [x] **FK ON DELETE 策略**：9处外键补充 CASCADE（conversations/api_keys/workflow_executions）/ SET NULL（tasks/audit_logs/knowledge_bases/workflows/agents/cost_logs）
- [x] **ClickHouse 密码环境变量化**：硬编码 → `${CLICKHOUSE_PASSWORD:-clickhouse_dev}` 模式
- [x] **Ollama 健康检查**：docker-compose 新增 healthcheck（curl /api/tags）
- [x] **Nginx 安全响应头**：X-Frame-Options / X-Content-Type-Options / X-XSS-Protection / Referrer-Policy / Permissions-Policy

### 待办：后续优化（HIGH/MEDIUM）

- [x] **Python**: ModelRouter/ChatWorkflow httpx 客户端生命周期管理
- [x] **Python**: MCP tools 每次调用创建新服务实例 → 共享单例
- [x] **Java**: 适配器类重复 helper 方法（firstNonNull/coalesce）→ 提取到 BaseSystemAdapter
- [x] **Java**: JwtAuthenticationFilter 静默吞吃所有异常 → 区分认证失败/系统异常
- [x] **Java**: PageQuery 缺少 @Min/@Max 验证
- [x] **Java**: KnowledgeApplicationService 缺少 @Transactional 边界
- [x] **Java**: DocumentProcessListener TODO（文档处理逻辑未实现）
- [x] **前端**: AIChat forceRender 反模式
- [x] **前端**: Vite alias `'@': '/src'` → `path.resolve(__dirname, './src')`
- [x] ~~**前端**: 缺少 ESLint 配置~~ — 已存在 `eslint.config.mjs`（TS/React/a11y/import 插件完整）
- [x] **前端**: aria-label 补充（AIChat 关闭按钮/输入框/发送按钮）

---

## Sprint 5：技术方案落地（基于 docs/04-05 补充/优化方案审查）

> **审查日期**：2026-03-24
> **审查方法**：12篇技术补充/优化方案逐篇对照代码库，提取 P8 核心平台未落地项
> **参考文档**：`docs/04_技术补充方案/` (6篇) + `docs/05_技术优化方案/` (6篇)

### S5-1. 统一错误码与异常体系（优化方案10）— P0

**现状**：无统一异常类，Controller 直接抛原生异常，无业务错误码体系。

- [x] 新建 `business-server/.../exception/BusinessException.java`：业务异常基类，含 code + message
- [x] 新建 `business-server/.../exception/ErrorCode.java`：错误码枚举（1000通用/2000认证/3000AI/4000知识库/5000工作流/6000业务规则/7000外部系统）
- [x] 新建 `business-server/.../exception/GlobalExceptionHandler.java`：`@RestControllerAdvice` 统一异常处理，返回 `ApiResponse` 格式
- [x] AI 网关同步定义 Python 错误码常量，对齐 Java 层码段

### S5-2. Docker 资源限制（优化方案12）— P0

**现状**：docker-compose.yml 所有服务无 mem_limit / cpus 限制，单服务可吞噬宿主机全部资源。

- [x] `docker/docker-compose.yml`：为所有 13 个服务添加 `deploy.resources.limits`（CPU + 内存上限）
- [x] 关键服务资源参考：MySQL 4C16G、Milvus 4C16G、ES 4C8G、Redis 2C4G、Ollama 4C8G

### S5-3. Springdoc / Swagger UI（优化方案10）— P1

**现状**：业务编排层无 API 文档自动生成，AI 网关依赖 FastAPI 内置 `/docs` 已可用。

- [x] `business-server/pom.xml`：新增 `springdoc-openapi-starter-webmvc-ui` 依赖
- [x] `application-dev.yml`：配置 Springdoc 分组（业务API / 管理API）
- [x] 所有 Controller 方法补充 `@Operation` / `@Parameter` 注解（渐进式）

### S5-4. Prometheus Exporters + 告警规则（补充方案04）— P1

**现状**：Prometheus/Grafana 已部署，但 exporters 全部注释、无 Grafana Dashboard、无告警规则。

- [x] `docker/docker-compose.yml`：新增 mysqld-exporter、redis-exporter 服务
- [x] `docker/prometheus/prometheus.yml`：取消注释并配置 MySQL/Redis 抓取 job
- [x] 新建 `docker/prometheus/alert-rules.yml`：核心告警（MySQL连接>80%、Redis内存>80%、RabbitMQ队列>10000）
- [x] 新建 `docker/grafana/dashboards/`：MySQL面板 + Redis面板 + 总览面板（JSON provisioning）

### S5-5. 缓存防护体系（优化方案09）— P1

**现状**：Caffeine + Redis 二级缓存已配置，但无穿透/击穿/雪崩防护。

- [x] `business-server/pom.xml`：新增 `redisson-spring-boot-starter` 依赖（分布式锁）
- [x] 新建 `business-server/.../service/CacheProtectedService.java`：BloomFilter防穿透 + Redisson互斥锁防击穿 + TTL随机化防雪崩
- [x] 缓存键命名规范统一：`{产品}:{模块}:{实体}:{ID}` 模式

### S5-6. 缓存失效联动（优化方案09）— P2

**现状**：知识库文档更新后 RAG 缓存不会失效，可能返回过期结果。

- [x] `business-server/.../config/RabbitMQConfig.java`：新增 `cache.invalidation` 队列
- [x] `business-server/.../service/KnowledgeApplicationService.java`：文档创建/更新时发布缓存失效事件
- [x] AI 网关监听失效事件，清除对应知识库的 RAG 结果缓存

### S5-7. SSE 统一消息信封（优化方案10）— P2

**现状**：SSE 使用自定义 event 类型（intent/content/ui_spec/done/error），未遵循统一信封规范。

- [x] 定义统一信封 TypeScript 类型（MessageEnvelope: version/id/traceId/timestamp/source/type/payload）
- [x] AI 网关 SSE 输出改造为 STREAM_START / STREAM_CHUNK / STREAM_END / STREAM_ERROR 格式
- [x] 前端 SSE 解析层适配新信封格式（向后兼容旧格式）

### S5-8. GraphRAG 图谱查询接入融合（优化方案11）— P2

**现状**：Neo4j 已部署，driver 已预留，但图谱查询未接入 RAG 融合排序，实际仅二路（向量+关键词）。

- [x] 设计医疗知识图谱 Schema（疾病/药物/症状/检查 实体 + 关系模型）
- [x] 导入基础配伍禁忌图谱数据（Cypher LOAD CSV 或脚本）
- [x] `ai-gateway/app/services/rag_service.py`：实现 `_graph_search()` 方法，Cypher 查询实体关系
- [x] 融合排序器接入图谱结果，三路 RRF（向量0.4 + 关键词0.3 + 图谱0.3）
- [x] 意图自适应权重：FACTUAL / RELATIONAL / REASONING 不同配比

### S5-9. Spring AI 引入（补充方案02）— P3

**现状**：Java 层无 AI 框架集成，方案02 推荐 Spring AI 1.0+。

- [ ] `business-server/pom.xml`：新增 `spring-ai-starter` 依赖
- [ ] 评估 Java 层 AI 能力需求（模型调用/Embedding/Function Calling）

### S5-10. Feature Flag 服务（优化方案12）— P3

**现状**：无功能开关机制，新功能只能全量发布。

- [x] 新建 `business-server/.../config/FeatureFlagProperties.java`：`@ConfigurationProperties` 绑定 Nacos 动态配置
- [x] 新建 `business-server/.../service/FeatureFlagService.java`：全局开关 + 用户白名单两种模式 + Redis 缓存
- [x] 新建 `business-server/.../interfaces/rest/FeatureFlagController.java`：REST 查询端点
- [x] AI 网关 `app/services/feature_flags.py`：Python 侧 Feature Flag（本地环境变量 + 远程 HTTP 查询）

### S5-11. 语义缓存（优化方案09）— P3

**现状**：每次 RAG 检索都触发完整的 Embedding + Milvus + ES + LLM 调用链路，无语义级缓存。

- [x] AI 网关 `app/services/semantic_cache.py`：Milvus 缓存 Collection + Embedding 相似度检索（>0.95命中）
- [x] `chat_workflow.py` _handle_knowledge 注入缓存：命中直接返回，未命中走 RAG+LLM 后回写
- [x] `cache_invalidation.py` 联动：知识库更新时同步清除 Milvus 语义缓存

---

## Sprint 6：生产就绪加固（四层代码审计）

> **审查日期**：2026-03-24
> **审查方法**：四层并行代码审计（AI网关/业务编排/前端/基础设施），共发现52个新问题
> **重点方向**：安全加固、可靠性提升、性能优化

### S6-1. Java 安全加固 — P0

**现状**：CORS 通配符、URL 拼接注入、文件上传无类型校验、工作流端点无权限验证。

- [x] `SecurityConfig.java`：CORS `allowedOriginPatterns("*")` → 显式域名白名单
- [x] `BaseSystemAdapter.java`：URL 字符串拼接 → `UriComponentsBuilder` 安全构造
- [x] `StorageService.java`：文件上传新增白名单校验（pdf/docx/txt/md/csv）+ 大小限制（100MB）
- [x] `WorkflowController.java`：deploy/start 端点补充 `@PreAuthorize` 权限

### S6-2. Docker 安全加固 — P0

**现状**：RabbitMQ/MinIO 管理界面外网暴露、ES 安全认证禁用、多服务弱密码。

- [x] `docker-compose.yml`：RabbitMQ 移除 `15672` 端口映射（仅内部访问）
- [x] `docker-compose.yml`：MinIO 移除 `9001` 端口映射（控制台走 Nginx 代理）
- [x] `docker-compose.yml`：ES 启用 `xpack.security.enabled=true` + 环境变量密码
- [x] `docker-compose.yml`：Redis 启用 AOF 持久化（`--appendonly yes --appendfsync everysec`）
- [x] `docker/.env.example`：补齐所有缺失变量（ES/Nacos/Grafana），密码改为 `<CHANGE_ME>` 占位

### S6-3. AI 网关可靠性提升 — P0

**现状**：DynamicUIService 每次创建新 LLMService 实例、缓存监听无重试、配置无范围校验。

- [x] `dynamic_ui_service.py`：`_llm_generate_spec` 中 LLMService 改为懒加载单例
- [x] `cache_invalidation.py`：新增指数退避重试（最多3次，5/10/20秒间隔）
- [x] `config.py`：关键配置添加 `Field(ge=, le=)` 范围约束（权重/阈值/限制数）
- [x] `.env.example`：数据库 URL 改为 MySQL 驱动（与 config.py 默认值一致）

### S6-4. 前端 Error Boundary + 流式错误处理 — P0

**现状**：无全局 Error Boundary（组件崩溃白屏）、SSE 流无超时/重连、Workspace 页面纯静态。

- [x] 新建 `frontend/src/components/ErrorBoundary.tsx`：全局错误捕获 + Ant Design Result 降级 UI
- [x] `main.tsx`：包裹 `<ErrorBoundary>` 到根组件
- [x] `AIChat.tsx`：SSE 流添加 30s 超时 + 友好错误提示（429/503 分类处理）
- [x] `Workspace.tsx`：接入 TanStack Query 加载待办/统计真实数据（loading/error/empty 三态）

### S6-5. Java 性能与可靠性 — P1

**现状**：适配器串行调用、HikariCP 未配置、AuditLogListener 无限重试、日期参数无校验。

- [ ] `TaskApplicationService.java`：适配器串行 → `CompletableFuture` 并行调用
- [ ] `application-dev.yml`：补充 HikariCP 连接池配置（max=20, min-idle=5）
- [ ] `AuditLogListener.java`：`basicNack` 无限重试 → 3次重试后进死信队列
- [ ] `AuditController.java`：日期参数 String → `@DateTimeFormat LocalDate` + 逻辑校验
- [ ] `application.yml`：移除 `profiles.active: dev` 硬编码，由启动参数指定

### S6-6. 前端 API 层与性能优化 — P1

**现状**：API 客户端配置不一致、React Query 无 staleTime、KnowledgeBase 页面静态。

- [x] `services/api.ts`：提取 `createClient()` 工厂函数，统一超时/拦截器/Token 注入
- [x] `AuditLog.tsx`：React Query 添加 `staleTime: 5min`、`gcTime: 10min`
- [x] `KnowledgeBase.tsx`：接入知识库 API 加载真实数据（同 Workspace 三态处理）

### S6-7. Nginx + Prometheus 运维增强 — P2

**现状**：Nginx 无 gzip/日志轮转、Prometheus 告警规则不完整。

- [ ] `nginx.conf`：新增 gzip 压缩 + 增强日志格式（含 request_time/upstream_time）
- [ ] `alert-rules.yml`：补充容器 CPU/内存、磁盘空间、RabbitMQ 队列深度告警规则

---

### 产品线专属（非 P8 核心，记录备忘）

> 以下方案针对其他产品线，当前代码库不涉及，仅记录关键待办。

- [ ] **补充方案01 命名规范**：全团队通知 T-Layer/Tier 命名规范、文档头编号标注
- [ ] **补充方案03 P3离线模式**：IndexedDB + Service Worker + 本地规则引擎（P3专属）
- [ ] **补充方案05 WebRTC会诊**：LiveKit Server 部署 + 视频会诊功能（P2 v3.0，Q3-Q4）
- [ ] **补充方案06 Part A SSO**：Keycloak 24.x 部署 + 8产品 OIDC 集成
- [ ] **补充方案06 Part B 零容错**：Drools 规则引擎 + 药物三级防护体系（P2/P3专属）
- [ ] **优化方案07 医疗合规**：DataClassification 四级分类注解、AI可解释性封装、等保三级整改
- [ ] **优化方案08 P6技术栈**：抽取 @lizkal/shared-* 共享 npm 包、移除 NestJS BFF

---

## 文档同步（低优先级）

- [x] `CLAUDE.md`：React 版本描述从 "React 18" 更新为 "React 19"（实际 package.json 为 `^19.2.4`）
- [x] `CLAUDE.md`：DynamicRenderer 描述更新为 "json-render + Ant Design 混合渲染"（当前描述为纯自定义）
- [x] `CLAUDE.md`：Docker 服务数 8→13、数据库表 6→12、Java 包路径 DDD 分层、新增 API 端点/端口/安全/监控描述
- [x] `docs/json-render集成指南.md`：7种组件 + Spec生成 + Action机制 + SSE事件流

---

## Sprint 1 已完成清单（归档）

<details>
<summary>点击展开 Sprint 1 完成项</summary>

### 动态UI专项
1. ✅ json-render 依赖安装与 DynamicRenderer 集成
2. ✅ catalog.ts 组件目录定义
3. ✅ DynamicRenderer 渲染器改造（7种组件 + actions）
4. ✅ dynamic_ui_service.py 后端 Spec 生成
5. ✅ SSE → 前端 renderer 链路打通

### AI网关
- ✅ RAG 三路融合检索（Milvus + ES + Neo4j预留 + RRF + BGE-Reranker）
- ✅ LangGraph 对话工作流（StateGraph + 条件路由）
- ✅ LLM 服务（Ollama httpx + 流式）
- ✅ 意图分类器（LLM + 关键词兜底）
- ✅ Text2SQL（Vanna.ai + SQL安全 + Schema训练）
- ✅ 动态UI Spec 生成
- ✅ 所有路由端点（chat/knowledge/query + train/train-schema）
- ✅ Config 完整配置 + Lifespan 生命周期管理

### 业务编排
- ✅ JWT 认证体系（SecurityConfig + JwtTokenProvider + JwtAuthenticationFilter + AuthController）
- ✅ Caffeine + Redis 二级缓存
- ✅ MyBatis-Plus Mapper 层（User/Task/Document/AuditLog）
- ✅ Entity/DTO/VO 完整模型
- ✅ ERP/CRM/OA 适配器（含断路器）
- ✅ 核心服务（Task聚合/Knowledge/Audit/User）
- ✅ RabbitMQ 队列声明

### 前端
- ✅ CASL 权限体系（3角色 + Can组件 + ProtectedRoute）
- ✅ 登录页 + 认证服务 + JWT拦截器
- ✅ Zustand Store（Auth + Chat + Sidebar）
- ✅ SSE 流式对话（5种事件类型）
- ✅ DynamicRenderer（7组件 + ECharts 5图表类型）
- ✅ 审计日志页（TanStack Query + 多过滤器）
- ✅ Vite 分层代理

### 基础设施
- ✅ Docker Compose 13服务（MySQL/Redis/Milvus/RabbitMQ/ES/MinIO/ClickHouse/Ollama/Neo4j/Prometheus/Grafana/Nginx/Nacos）
- ✅ MySQL 12张表 + 索引 + FK ON DELETE 策略 + 默认管理员

</details>
