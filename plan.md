# Sprint 1 实施计划 — 6大偏差修复

根据用户选择：Neo4j先预留双路、Java层保持单体补齐核心能力、完整认证+权限链路。

---

## 动态UI专项迭代（对齐文档 3.5）

1. `frontend/package.json` 安装 `@json-render/core`, `@json-render/react`, `zod` 并在 `DynamicRenderer` 中落地 `defineCatalog` + `Renderer`（Card/Table/Metric/List/Form/Tag/Chart + actions: view_detail/refresh/export）。
2. 新建 `frontend/src/components/dynamic-ui/catalog.ts`（或同级文件）抽离组件目录定义，编写 `Renderer` 包装组件（含 loading / fallback 到 Ant Design 逻辑，便于渐进迁移）。
3. 改造 `DynamicRenderer.tsx`：优先走 json-render 渲染；若 schema 校验失败则输出友好错误并退回手写组件；新增图表、Tag 等示例渲染。
4. 扩展 `ai-gateway/app/services/dynamic_ui_service.py`：输出符合 catalog schema 的 spec（knowledge→Card+List+actions，query→Card+Metric+Table+Chart, task→List/Form/Tag, task意图支持 actions）。
5. 验证 SSE 事件 `ui_spec` → 前端 renderer 整体链路（可通过 mock 数据 / 单元测试 `DynamicRenderer`），并在 `frontend/src/types` 中补齐 props 类型（含 actions、Chart option 等）。
6. 在 `docs/AI业务中台_MVP一期实施文档.md` 或新增补充文档记录最终 json-render 集成方式，确保研发/AI 网关对齐。

## 阶段一：AI网关核心能力（Python层）

### 1.1 RAG双路检索引擎 `rag_service.py`
重写 `ai-gateway/app/services/rag_service.py`：
- **向量检索**：pymilvus 连接 Milvus，创建/获取 `documents` Collection，BGE-M3 embedding 编码 query，执行向量搜索
- **关键词检索**：elasticsearch AsyncElasticsearch 连接 ES，BM25 全文检索 `documents` 索引
- **RRF融合**：保留现有 `_reciprocal_rank_fusion` 算法，整合双路结果
- **BGE-Reranker**：FlagEmbedding FlagReranker 对融合结果重排序
- **Neo4j预留**：search() 方法中留 `graph_results` 占位 + 抽象接口 `_graph_search()`
- 从 Settings 读取所有连接配置

### 1.2 LangGraph对话工作流
新建 `ai-gateway/app/services/workflow.py`：
- 使用 `langgraph.graph.StateGraph` 构建工作流
- State: `{messages, intent, rag_results, sql_result, ui_spec, response}`
- 节点：`classify_intent` → 路由 → `rag_search` | `text2sql` | `task_dispatch` | `chat_response` → `generate_ui` → `format_response`
- 条件边：根据 intent 路由到对应节点

重写 `ai-gateway/app/api/routes/chat.py`：
- 调用 workflow.astream_events() 获取流式输出
- 通过 `EventSourceResponse` 推送 SSE 事件
- 事件类型：`intent`(意图识别结果)、`content`(文本块)、`ui_spec`(动态UI)、`sources`(引用来源)、`done`(结束)

### 1.3 LLM服务实现 `llm_service.py`
重写：
- 使用 `langchain_ollama.ChatOllama` 初始化 LLM
- `chat()`: invoke 同步调用，返回完整文本
- `stream_chat()`: astream 流式调用，yield 文本块
- 支持 system prompt + message history

### 1.4 意图分类器增强 `intent_classifier.py`
重写：
- 使用 LLM 进行意图分类（LangChain prompt + structured output）
- 保留关键词兜底逻辑
- 返回 IntentType + confidence score

### 1.5 Text2SQL服务打通 `text2sql_service.py`
重写：
- `_get_vanna()` 增加 Milvus 和 Postgres 连接配置
- `query()`: 调用 `vn.ask(question)` → 获取 SQL → 通过 asyncpg 安全执行 → 返回结果集
- SQL安全：白名单校验（仅允许 SELECT）、超时限制、行数限制
- `train()`: 支持 DDL 导入（`vn.train(ddl=...)`) 和问答对训练
- 新增 `train_from_schema()`: 自动导入 init-postgres.sql 中的表结构

### 1.6 动态UI服务实现 `dynamic_ui_service.py`
重写：
- 根据 intent 和数据类型生成 json-render 兼容的 UI Spec
- `data_query` → Table + Chart 组合
- `knowledge` → Card + List（来源列表）
- `task_operation` → List + Tag（任务列表）
- Spec 格式严格对齐前端 UISpec 类型定义

### 1.7 知识检索路由 `knowledge.py`
重写：调用 RAGService.search()，返回实际检索结果

### 1.8 数据查询路由 `query.py`
重写：调用 Text2SQLService.query()，返回实际查询结果 + chart_spec

### 1.9 Schemas补充 `schemas.py`
- 新增 `SSEEvent` model（event_type, data）
- ChatRequest 增加 `session_id` 字段
- 新增 `TrainRequest` / `TrainResponse` 用于 Text2SQL 训练
- 新增 `IntentResult(intent, confidence)` 用于意图分类返回

### 1.10 Config增强 `config.py`
- 新增 `neo4j_uri`, `neo4j_user`, `neo4j_password`（预留，默认空）
- 新增 `embedding_model` = "BAAI/bge-m3"
- 新增 `reranker_model` = "BAAI/bge-reranker-v2-m3"

### 1.11 应用生命周期 `main.py`
- lifespan 中初始化 Milvus collection、ES index、LLM、Embedding model
- 关闭时清理连接
- 新增 `/api/v1/query/train` 路由（Text2SQL训练）

---

## 阶段二：业务编排层增强（Java层）

### 2.1 添加依赖 `pom.xml`
新增：
- `spring-boot-starter-security` — JWT认证
- `jjwt-api` + `jjwt-impl` + `jjwt-jackson` 0.12.x — JWT令牌
- `caffeine` 3.1.x — 本地缓存

### 2.2 JWT认证体系
新建文件：
- `config/SecurityConfig.java` — Spring Security 配置，放行 `/api/v1/auth/**` 和 `/health`，其余需 JWT
- `security/JwtTokenProvider.java` — JWT 生成/验证/解析，密钥从配置读取
- `security/JwtAuthenticationFilter.java` — OncePerRequestFilter，解析 Authorization header
- `controller/AuthController.java` — `POST /api/v1/auth/login`（用户名密码登录）、`GET /api/v1/auth/me`（当前用户信息+角色权限）
- `model/dto/LoginRequest.java` / `LoginResponse.java`
- `model/dto/UserPermission.java` — 包含 role + abilities 列表（对齐前端 CASL）

### 2.3 Caffeine+Redis 二级缓存
新建 `config/CacheConfig.java`：
- Caffeine L1 缓存：taskCache(5min TTL, 100条)、userCache(10min TTL, 50条)
- Redis L2 缓存：通过 RedisTemplate 手动管理
- `CacheService.java`：`get(key)` 先查 L1 → L2 → DB，`put(key)` 同时写 L1+L2

### 2.4 Mapper层（MyBatis-Plus）
新建：
- `mapper/UserMapper.java` — `extends BaseMapper<User>`，新增 `selectByUsername()`
- `mapper/TaskMapper.java` — `extends BaseMapper<Task>`
- `mapper/DocumentMapper.java` — `extends BaseMapper<Document>`
- `mapper/AuditLogMapper.java` — `extends BaseMapper<AuditLog>`

### 2.5 Entity补充
新建 `model/entity/User.java` — 对应 users 表，补充 `password_hash` 字段
修改 `init-postgres.sql` — users 表新增 `password_hash VARCHAR(255)` 字段，默认管理员插入 bcrypt 密码

### 2.6 Service层完善
重写：
- `KnowledgeService.java`：注入 DocumentMapper，实现 createDocument（存PG、发MQ）、listDocuments（分页查询）
- `AuditService.java`：注入 AuditLogMapper，实现 queryLogs 分页查询
- `TaskAggregatorService.java`：增加 L1+L2 缓存，过期后才调 adapter
- 新建 `UserService.java`：登录验证、用户信息查询

### 2.7 Adapter增强
重写 ErpAdapter/CrmAdapter/OaAdapter：
- 从 `system_adapters` 表读取配置（endpoint, auth_type, config）
- 使用 RestTemplate 发起 HTTP 请求到外部系统
- 错误隔离：Circuit Breaker 模式（简单实现：失败计数 + 熔断 + 恢复检测）
- 响应映射：将外部系统字段映射为内部 Task 格式

### 2.8 配置更新
`application.yml` 新增：
- `jwt.secret`, `jwt.expiration`（JWT配置）
- caffeine cache 配置

---

## 阶段三：前端状态与权限（React层）

### 3.1 新增依赖 `package.json`
- `@casl/ability` + `@casl/react` — RBAC权限
- `jwt-decode` — JWT解码（无需密钥验证，仅解码payload）

### 3.2 认证服务
新建 `frontend/src/services/auth.ts`：
- `login(username, password)` → POST /api/v1/auth/login → 存储 JWT 到 localStorage
- `getMe()` → GET /api/v1/auth/me → 返回用户信息+权限
- `logout()` → 清除 token
- Axios interceptor：自动附加 Authorization header，401 自动跳转登录

### 3.3 CASL权限定义
新建 `frontend/src/abilities/index.ts`：
- `defineAbilityFor(role)` 函数
- admin: 全部 CRUD
- user: read tasks/documents, create conversations
- viewer: 只读
- 权限维度：`manage | read | create | update | delete` × `Task | Document | Audit | Conversation | User`

### 3.4 权限组件
新建 `frontend/src/components/auth/Can.tsx`：
- 包装 `@casl/react` 的 `Can` 组件
- 新建 `ProtectedRoute.tsx`：路由守卫，未登录跳 `/login`，权限不足显示 403

### 3.5 登录页
新建 `frontend/src/pages/Login.tsx`：
- 用户名+密码表单（Ant Design Form）
- 调用 auth.login()
- 成功后跳转 /workspace

### 3.6 Zustand Store增强 `useAppStore.ts`
重写：
- 新增 `token`, `abilities`, `isAuthenticated` 状态
- `login()` action：调用 auth API → 存 token → 解析用户 → 更新 abilities
- `logout()` action：清除所有状态
- 所有组件改用 store 状态替代局部 useState

### 3.7 MainLayout改造 `MainLayout.tsx`
- 用 `useAppStore` 替代局部 `useState`（chatVisible、sidebarCollapsed）
- 顶栏新增：用户头像 + 用户名 + 退出按钮
- 菜单项根据 CASL ability 动态过滤
- 新增审计日志菜单项（仅 admin 可见）

### 3.8 AIChat改造 `AIChat.tsx`
重写消息处理：
- 使用 `EventSource` (SSE) 连接 `/api/v1/chat`
- 解析 SSE 事件流：intent → content(逐块拼接) → ui_spec → sources → done
- 收到 `ui_spec` 事件时调用 DynamicRenderer 渲染
- 收到 `sources` 事件时展示引用来源列表
- 使用 useAppStore 中的 user_id 发送请求

### 3.9 DynamicRenderer改造 `DynamicRenderer.tsx`
保持现有 Ant Design 手动渲染逻辑（json-render 库尚不成熟），但：
- 确保 UISpec 类型定义与后端 dynamic_ui_service 输出一致
- 增加 `loading` 状态支持
- Chart 组件增加更多图表类型支持（散点图、雷达图）

### 3.10 路由更新 `App.tsx`
- 新增 `/login` 路由 → Login 页面
- 新增 `/audit` 路由 → AuditLog 页面（admin only）
- 包裹 ProtectedRoute 守卫

### 3.11 新增审计日志页
新建 `frontend/src/pages/AuditLog.tsx`：
- 审计日志表格（intent、model、tokens、latency、status）
- 筛选：用户、意图类型、时间范围

### 3.12 API层更新 `api.ts`
- 新增 `authAPI.login()`, `authAPI.me()`
- Axios interceptor 统一注入 JWT token
- 401响应拦截 → 自动 logout + 跳转登录

### 3.13 Vite代理更新 `vite.config.ts`
- `/api/v1/auth/**` 代理到业务编排层 `:8080`
- `/api/v1/tasks/**`, `/api/v1/knowledge/documents/**`, `/api/v1/audit/**` 代理到 `:8080`
- `/api/v1/chat`, `/api/v1/knowledge/search`, `/api/v1/query/**` 代理到 `:8000`

---

## 阶段四：数据库与基础设施

### 4.1 PostgreSQL Schema更新 `init-postgres.sql`
- users 表新增 `password_hash VARCHAR(255)` 字段
- 默认 admin 用户插入 bcrypt hash 密码（admin123）

---

## 文件变更清单

### 新建文件（~15个）
| 文件 | 说明 |
|------|------|
| `ai-gateway/app/services/workflow.py` | LangGraph 对话工作流 |
| `business-server/.../security/JwtTokenProvider.java` | JWT令牌工具 |
| `business-server/.../security/JwtAuthenticationFilter.java` | JWT过滤器 |
| `business-server/.../config/SecurityConfig.java` | Spring Security配置 |
| `business-server/.../config/CacheConfig.java` | Caffeine+Redis缓存 |
| `business-server/.../controller/AuthController.java` | 认证接口 |
| `business-server/.../service/UserService.java` | 用户服务 |
| `business-server/.../service/CacheService.java` | 缓存服务 |
| `business-server/.../model/entity/User.java` | 用户实体 |
| `business-server/.../model/dto/LoginRequest.java` | 登录请求DTO |
| `business-server/.../model/dto/LoginResponse.java` | 登录响应DTO |
| `business-server/.../mapper/UserMapper.java` | 用户Mapper |
| `business-server/.../mapper/TaskMapper.java` | 任务Mapper |
| `business-server/.../mapper/DocumentMapper.java` | 文档Mapper |
| `business-server/.../mapper/AuditLogMapper.java` | 审计Mapper |
| `frontend/src/services/auth.ts` | 认证服务 |
| `frontend/src/abilities/index.ts` | CASL权限定义 |
| `frontend/src/components/auth/ProtectedRoute.tsx` | 路由守卫 |
| `frontend/src/pages/Login.tsx` | 登录页 |
| `frontend/src/pages/AuditLog.tsx` | 审计日志页 |

### 修改文件（~20个）
| 文件 | 改动 |
|------|------|
| `ai-gateway/app/services/rag_service.py` | 完整双路检索+RRF+Reranker |
| `ai-gateway/app/services/llm_service.py` | ChatOllama实现 |
| `ai-gateway/app/services/intent_classifier.py` | LLM意图分类 |
| `ai-gateway/app/services/text2sql_service.py` | Vanna完整对接 |
| `ai-gateway/app/services/dynamic_ui_service.py` | UI Spec生成 |
| `ai-gateway/app/api/routes/chat.py` | LangGraph工作流+SSE |
| `ai-gateway/app/api/routes/knowledge.py` | 对接RAG服务 |
| `ai-gateway/app/api/routes/query.py` | 对接Text2SQL+训练API |
| `ai-gateway/app/models/schemas.py` | 新增Schema类型 |
| `ai-gateway/app/core/config.py` | 新增配置项 |
| `ai-gateway/app/main.py` | 生命周期+新路由 |
| `business-server/pom.xml` | 新增依赖 |
| `business-server/.../service/KnowledgeService.java` | Mapper实现 |
| `business-server/.../service/AuditService.java` | Mapper实现 |
| `business-server/.../service/TaskAggregatorService.java` | 缓存增强 |
| `business-server/.../config/WebConfig.java` | 安全相关调整 |
| `business-server/src/.../resources/application.yml` | JWT+缓存配置 |
| `frontend/package.json` | 新增CASL+jwt-decode |
| `frontend/src/App.tsx` | 新增路由 |
| `frontend/src/stores/useAppStore.ts` | 认证状态 |
| `frontend/src/layouts/MainLayout.tsx` | Store替代useState |
| `frontend/src/components/chat/AIChat.tsx` | SSE流式对话 |
| `frontend/src/services/api.ts` | JWT interceptor |
| `frontend/vite.config.ts` | 分层代理 |
| `docker/init-scripts/init-postgres.sql` | password_hash字段 |

---

## 实施顺序

1. **基础设施** → DB Schema更新（password_hash）
2. **AI网关** → config → schemas → llm_service → intent_classifier → rag_service → text2sql_service → dynamic_ui_service → workflow → routes → main
3. **业务编排** → pom → Entity/Mapper → CacheService → UserService → JWT → SecurityConfig → AuthController → Service完善
4. **前端** → package.json → auth service → CASL abilities → store → Login → ProtectedRoute → App路由 → MainLayout → AIChat(SSE) → AuditLog页
