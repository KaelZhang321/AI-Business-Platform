# business-server AGENT.md

## 1. 模块定位

`business-server` 是整个 AI Business Platform 的业务编排层，技术栈为 `Java 21 + Spring Boot 3.4.7 + MyBatis-Plus 3.5.10 + Spring Security + Flowable + RabbitMQ + Redis + MinIO + ClickHouse`。

它在整体架构里的职责不是做大模型推理，而是承接企业业务侧的编排与治理，主要包括：

- 对前端提供业务 API。
- 对 AI 网关提供知识库、审计、缓存失效等业务支撑。
- 聚合外部业务系统的待办任务。
- 提供认证鉴权、数据权限、限流、脱敏、工作流、审计分析等通用能力。

仓库整体分为：

- `frontend/`：React 前端。
- `ai-gateway/`：FastAPI + LangChain/LangGraph 的 AI 网关。
- `business-server/`：当前这个 Spring Boot 业务服务。
- `docker/`：本地基础设施编排。
- `docs/`：产品和技术设计文档。

## 2. business-server 现在的真实结构

启动入口：

- `src/main/java/com/lzke/ai/AiBusinessApplication.java`

核心包划分以当前代码为准：

- `annotation/`：`@RateLimit`、`@Sensitive`、`@ColumnPermission` 等注解。
- `aspect/`：限流切面，当前主要是 `RateLimitAspect`。
- `application/`：应用服务和入参 DTO，负责聚合业务流程。
- `config/`：Security、MyBatis-Plus、Cache、RabbitMQ、MinIO、ClickHouse、Flowable 等配置。
- `controller/`：目前主要放认证控制器 `AuthController`。
- `domain/entity/`：MyBatis-Plus 实体，对应数据库表。
- `exception/`：统一错误码、业务异常、全局异常处理。
- `infrastructure/persistence/mapper/`：Mapper 接口。
- `infrastructure/system/`：外部系统适配器，负责 ERP/CRM/OA 等系统接入。
- `interfaces/rest/`：面向前端或外部调用的 REST API。
- `interfaces/dto/`：统一响应体和页面展示 DTO。
- `listener/`：RabbitMQ 消费者。
- `security/`：JWT、用户主体、行级数据权限、脱敏工具。
- `serializer/`：序列化时的列权限/敏感字段处理。
- `service/`：基础领域服务或集成服务，如工作流、存储、统计、用户、开关等。

资源目录：

- `src/main/resources/application*.yml`：环境配置。
- `src/main/resources/mapper/*.xml`：MyBatis XML。
- `src/main/resources/processes/general-approval.bpmn20.xml`：Flowable 示例审批流程。

当前大致规模：

- `88` 个 Java 源文件。
- `12` 个 Mapper XML。
- 目前没有发现 `src/test` 下的测试代码。

## 3. 主要业务能力

### 3.1 认证与权限

入口：

- `src/main/java/com/lzke/ai/controller/AuthController.java`

核心链路：

- 登录：`/api/v1/auth/login`
- 刷新令牌：`/api/v1/auth/refresh`
- 当前用户：`/api/v1/auth/me`

实现方式：

- `UserService` 负责账号校验与权限构建。
- `JwtTokenProvider` + `JwtAuthenticationFilter` 完成 JWT 认证。
- `SecurityConfig` 控制匿名路径和接口鉴权。
- `UserPermission` 会把角色映射成前端可消费的 abilities。

当前角色模型比较轻量：

- `admin`
- `user`
- `viewer`

### 3.2 多系统待办聚合

入口：

- `src/main/java/com/lzke/ai/interfaces/rest/TaskController.java`
- API：`GET /api/v1/tasks/aggregate`

核心链路：

- `TaskApplicationService` 注入 `List<BaseSystemAdapter>`。
- 各适配器并发拉取待办：`CompletableFuture + orTimeout(10s)`。
- 聚合后统一转换为 `TaskVO`，按优先级排序并手动分页。
- 结果通过 Spring Cache 缓存到 `tasks`。

已接入的外部系统适配器位于 `infrastructure/system/`：

- `ErpAdapter`
- `CrmAdapter`
- `OaAdapter`
- `ReservationAdapter`
- `BizCenterAdapter`
- `System360Adapter`

适配器基类 `BaseSystemAdapter` 负责：

- 从 `system_adapters` 表读取接入配置。
- 调用外部 HTTP API。
- 解析认证头。
- 做简单断路器控制。
- 提供统一字段映射扩展点。

### 3.3 知识库文档管理

入口：

- `src/main/java/com/lzke/ai/interfaces/rest/KnowledgeController.java`

主要 API：

- `POST /api/v1/knowledge/documents`
- `POST /api/v1/knowledge/documents/upload`
- `GET /api/v1/knowledge/documents`

核心链路：

1. `KnowledgeApplicationService.createDocument` 写入 `documents` 表。
2. 发送 `document.process` MQ 消息。
3. 同时发送 `cache.invalidation` 消息，通知其他服务失效缓存。
4. `DocumentProcessListener` 消费消息后，调用 AI 网关 `POST /api/v1/knowledge/ingest`。
5. 成功后回写文档状态和 `chunk_count`，失败则标记为 `failed`。

文件上传走：

- `StorageService`
- `MinIOConfig`

支持白名单文件格式，最大文件大小 `100MB`。

### 3.4 审计日志与分析

入口：

- `src/main/java/com/lzke/ai/interfaces/rest/AuditController.java`

主要能力：

- 分页查询审计日志。
- 基于 ClickHouse 做按意图、按模型、按小时统计。

核心链路：

- `AuditLogListener` 消费 `audit.log` 队列。
- 审计数据先写 MySQL `audit_logs`，再调用 `AnalyticsService` 写 ClickHouse。
- 查询列表走 MySQL，聚合分析走 ClickHouse。

### 3.5 工作流

入口：

- `src/main/java/com/lzke/ai/interfaces/rest/WorkflowController.java`
- `src/main/java/com/lzke/ai/service/WorkflowService.java`

当前支持：

- 流程部署
- 流程定义列表
- 启动流程
- 查询用户任务/候选组任务
- 完成任务
- 认领任务

流程引擎使用：

- `Flowable 7.1.0`
- BPMN 资源目录：`src/main/resources/processes/`

默认自带一个示例流程：

- `general-approval.bpmn20.xml`

### 3.6 横切能力

已经落地的横切能力包括：

- `RateLimitAspect`：基于 Redis 的接口限流。
- `DataPermissionInterceptor`：对 `tasks`、`audit_logs`、`conversations` 追加行级权限条件。
- `GlobalExceptionHandler`：统一错误返回为 `ApiResponse`。
- `FeatureFlagService`：配置驱动的功能开关，支持全局开关和白名单。
- `CacheConfig`：Caffeine + Redis 组合缓存。

## 4. 对外 API 概览

主要控制器如下：

- `AuthController`：认证相关。
- `TaskController`：多系统待办聚合。
- `KnowledgeController`：知识库文档与上传。
- `AuditController`：审计查询与统计。
- `WorkflowController`：Flowable 工作流。
- `FeatureFlagController`：功能开关查询。

接口返回统一使用：

- `ApiResponse<T>`
- 分页统一使用 `PageResult<T>`

## 5. 数据与集成依赖

本模块直接依赖的基础设施包括：

- MySQL：主业务库，实体表主要在 `domain/entity/`。
- Redis：缓存、限流、Feature Flag 缓存。
- RabbitMQ：文档处理、审计日志、缓存失效。
- MinIO：知识库附件/文件存储。
- ClickHouse：审计分析。
- Flowable：审批工作流。
- Nacos：通过 `-Pnacos` 按需接入配置中心和注册中心。

当前实体对应表包括：

- `users`
- `tasks`
- `documents`
- `audit_logs`
- `system_adapters`
- `workflows`
- `workflow_executions`
- `knowledge_bases`
- `agents`
- `api_keys`
- `cost_logs`
- `conversations`

## 6. 本地开发方式

常用命令：

```bash
cd business-server
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

如需 Nacos：

```bash
cd business-server
mvn spring-boot:run -Pnacos -Dspring-boot.run.profiles=dev
```

测试与构建：

```bash
cd business-server
mvn test
mvn -DskipTests compile
```

接口文档：

- Swagger UI: `http://localhost:8080/swagger-ui.html`

关键配置文件：

- `src/main/resources/application.yml`
- `src/main/resources/application-dev.yml`
- `src/main/resources/application-docker.yml`
- `src/main/resources/bootstrap.yml`

## 7. 阅读代码时建议先看哪些文件

如果要快速理解整个 `business-server`，推荐按这个顺序看：

1. `src/main/java/com/lzke/ai/AiBusinessApplication.java`
2. `src/main/resources/application-dev.yml`
3. `src/main/java/com/lzke/ai/config/SecurityConfig.java`
4. `src/main/java/com/lzke/ai/interfaces/rest/TaskController.java`
5. `src/main/java/com/lzke/ai/application/task/TaskApplicationService.java`
6. `src/main/java/com/lzke/ai/infrastructure/system/BaseSystemAdapter.java`
7. `src/main/java/com/lzke/ai/interfaces/rest/KnowledgeController.java`
8. `src/main/java/com/lzke/ai/application/knowledge/KnowledgeApplicationService.java`
9. `src/main/java/com/lzke/ai/listener/DocumentProcessListener.java`
10. `src/main/java/com/lzke/ai/interfaces/rest/AuditController.java`
11. `src/main/java/com/lzke/ai/listener/AuditLogListener.java`
12. `src/main/java/com/lzke/ai/service/WorkflowService.java`

## 8. 当前实现里需要注意的几点

这些点不是阻塞，但很值得接手时先知道：

- README 中有些目录说明和真实代码不完全一致。比如适配器实际在 `infrastructure/system/`，不是 README 里写的 `adapter/`。
- `business-server` 目前几乎没有测试代码，改动后更依赖手动验证和接口回归。
- `MyBatisPlusConfig` 里的分页拦截器使用的是 `DbType.POSTGRE_SQL`，但项目实际数据源和 Flowable 都在按 MySQL 配置，这里存在明显不一致，后续排查 SQL 方言问题时要优先关注。
- CORS 同时在 `SecurityConfig` 和 `WebConfig` 里都配置了一次，排查跨域问题时要同时看这两个位置。
- 待办聚合并不会把结果持久化到本地 `tasks` 表，当前主要是“实时拉取外部系统 + 聚合返回”。
- 文档处理链路依赖 AI 网关可用，如果 `DocumentProcessListener` 调用 `ai-gateway` 失败，文档状态会落成 `failed`。

### 8.1 UI Builder 模块约定

`UI Builder` 是 `business-server` 中新增的一块“接口文档 -> 页面配置 -> json-render spec”能力，代码主要集中在：

- `src/main/java/com/lzke/ai/interfaces/rest/UiBuilderController.java`
- `src/main/java/com/lzke/ai/application/ui/UiBuilderApplicationService.java`
- `src/main/java/com/lzke/ai/application/ui/UiBuilderMetadataService.java`
- `src/main/resources/db/ddl/ui_builder.sql`

后续维护时建议遵守下面这些规则：

- `UiBuilderApplicationService` 只负责运行时编排逻辑：
  包括 CRUD、OpenAPI 导入、接口联调、字段绑定、spec 生成和版本发布。
- 静态组装对象不要继续塞回 `UiBuilderApplicationService`：
  模块概览、节点类型、认证方式、表结构说明这类“不会随着业务数据变化”的内容，统一维护在 `UiBuilderMetadataService`。
- `json-render` 生成规则要保持稳定：
  最终产物必须始终输出 `root + elements` 的扁平结构，不要改成嵌套树，避免前端 `dynamic-ui` 渲染器失配。
- 接口源与接口定义之间当前通过 `ui_api_tags` 建了一层标签关系：
  OpenAPI 导入时会读取 operation 的 `tags` 数组，默认取第一个标签写入 `ui_api_tags`，接口定义通过 `tag_id` 关联该标签。
- UI Builder 新增类和关键方法时，要补充详细注释：
  至少写清楚这个类负责什么、输入输出是什么、为什么放在这一层，而不是只写一句“创建对象”这种低信息量注释。
- OpenAPI 导入优先支持 Swagger JSON 地址：
  当前建议使用 `/v3/api-docs` 这类直接返回 JSON 的地址。导入顺序是：`document` -> `documentUrl` -> 接口源 `docUrl`。
- 页面配置与绑定逻辑优先依赖“样例响应”：
  节点字段绑定不是直接请求线上接口动态渲染，而是先基于 `sample_response` 做配置、预览和发布。
- 如需扩展转换器，优先在服务内做“命名式内置转换器”：
  例如当前 `tableRows`，避免一上来就引入可执行脚本，先保证可控和可审计。

## 9. 如果后续要扩展

常见扩展入口：

- 新增业务 API：优先放到 `interfaces/rest/` + `application/`，保持控制器轻、流程逻辑集中。
- 新增外部系统接入：继承 `BaseSystemAdapter`，补充系统字段映射，并确认 `system_adapters` 表配置。
- 新增 MQ 链路：在 `RabbitMQConfig` 中补 Exchange/Queue/Binding，再新增 `listener/` 消费者。
- 新增审计分析维度：扩展 `AnalyticsService` 和 `AuditController`。
- 新增工作流：把 BPMN 放到 `src/main/resources/processes/`，再通过 `WorkflowService` 部署和调用。

## 10. 一句话总结

如果把整个仓库看成一个企业 AI 平台，那么 `business-server` 就是“把账号权限、待办聚合、知识库文档、审计分析、审批流程和外部系统接入真正落地起来”的那一层，是连接前端、AI 网关和企业基础设施的核心业务中枢。
