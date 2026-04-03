# ai-gateway 融合会议 BI 能力设计方案

## 1. 背景

当前存在两个相关项目：

- `AI-Business-Platform/ai-gateway`：AI 网关，已经提供对话、知识检索、通用 Text2SQL、MCP 工具等能力
- `ai-bi-new/backend`：会议 BI 专项服务，提供固定 BI 看板接口、会议 BI 问数、企业微信推送

本次目标是将 `ai-bi-new` 中的会议 BI 能力融合进 `ai-gateway`，形成统一入口与统一部署形态。

## 2. 已确认边界

### 2.1 第一阶段范围

第一阶段仅迁移以下能力：

- 固定 BI 看板接口
- 会议 BI 问数能力

第一阶段明确不包含：

- 企业微信长连接
- Webhook 推送
- 企业微信状态控制接口

### 2.2 数据源策略

第一阶段保留直连会议 BI MySQL 数据库，继续访问 `meeting_*` 业务表。

不采用通过 `business-server` 间接取数的方式。

### 2.3 接口规范策略

固定 BI 看板接口保留业务语义，但响应风格统一到 `ai-gateway` 现有模型体系，不继续沿用 `ai-bi-new` 的 `ApiResponse[data]` 包装。

### 2.4 通用问数融合策略

`text2sql_service.py` 被定义为通用问数统一入口。

当意图识别命中“会议 BI 问数”时，入口不变，但内部自动切换到会议 BI 专用执行器。

这意味着：

- 对外维持统一问数入口
- 对内隔离会议 BI 业务语义
- 不再保留独立的 BI AI 查询主入口

## 3. 当前通用问数能力分析

基于现有源码，`ai-gateway` 的通用问数能力具有以下特点：

### 3.1 已有优势

- 已经存在统一入口：`/api/v1/query/text2sql`
- 已经接入 3 条调用链：HTTP 路由、ChatWorkflow、MCP Tool
- 已经具备基础 SQL 安全拦截
- 已经具备查询结果到 UI Spec 的转换能力

### 3.2 现有限制

- `Text2SQLService` 当前同时承担 Vanna 初始化、SQL 生成、SQL 执行、训练、UI 生成，职责过重
- `database` 参数当前没有真正实现多库切换
- 通用问数目前只绑定一个 `database_url`
- ChatWorkflow 的 query 节点只传 `message`，没有传 `sub_intent`、`conversation_id`、`context`
- 当前返回结构偏通用查询，不包含会议 BI 问数常见的“业务结论回答”语义
- 当前训练入口更偏平台默认 schema 训练，不适合直接承载会议 BI 的强业务语义训练

### 3.3 结论

现有通用问数适合继续作为统一接入门面，不适合直接塞入会议 BI 的业务规则、训练语料和数据源逻辑。

因此融合设计必须采用：

- 统一入口
- 内部分流
- 执行器隔离

## 4. 总体架构决策

采用“统一问数入口 + 会议 BI 域模块 + 执行器分流”的方案。

### 4.1 核心原则

- 保留 `Text2SQLService` 作为统一问数门面
- 将当前通用问数逻辑下沉为 `GenericQueryExecutor`
- 新增 `MeetingBIQueryExecutor` 承接会议 BI 问数逻辑
- 通过二级意图 `data_meeting_bi` 驱动门面做执行器切换
- 固定 BI 看板接口独立为 `/api/v1/bi/*`

### 4.2 不采用的方案

不采用以下方案：

- 将会议 BI 规则直接合并到现有 `Text2SQLService` 的 prompt、训练逻辑和数据库连接中
- 在 `ChatWorkflow` 中直接旁路 `Text2SQLService`，单独写一个 BI 问数分支
- 保留 `ai-bi-new` 的独立 BI AI 查询主入口并与统一问数入口并存

原因：

- 会污染通用问数能力边界
- 会导致 HTTP / Chat / MCP 三条入口分叉
- 会让后续企业微信二期继续叠加技术债

## 5. 目录与模块设计

### 5.1 现有文件改造

- `ai-gateway/app/models/schemas.py`
- `ai-gateway/app/services/intent_classifier.py`
- `ai-gateway/app/services/text2sql_service.py`
- `ai-gateway/app/services/chat_workflow.py`
- `ai-gateway/app/api/routes/query.py`
- `ai-gateway/app/mcp_server/tools.py`
- `ai-gateway/app/core/config.py`
- `ai-gateway/app/main.py`

### 5.2 新增模块

```text
ai-gateway/app/
  api/routes/
    bi.py
  bi/
    ai/
      context_store.py
      query_executor.py
      training_data.py
      vanna_client.py
    db/
      session.py
      dependencies.py
    schemas/
      common.py
      kpi.py
      registration.py
      customer.py
      source.py
      operations.py
      achievement.py
      progress.py
      proposal.py
      ai_query.py
    services/
      kpi_service.py
      registration_service.py
      customer_service.py
      source_service.py
      operations_service.py
      achievement_service.py
      progress_service.py
      proposal_service.py
      chart_store.py
  services/
    generic_query_executor.py
```

### 5.3 职责划分

- `Text2SQLService`
  - 统一问数入口
  - domain 解析
  - 执行器分发
- `GenericQueryExecutor`
  - 平台通用问数
- `MeetingBIQueryExecutor`
  - 会议 BI 专用问数
- `bi/services/*`
  - 固定 BI 看板接口
- `bi/db/*`
  - 会议 BI 数据连接与依赖

## 6. 意图与路由设计

### 6.1 意图扩展

在 `SubIntentType` 中新增：

- `data_meeting_bi`

### 6.2 分类规则

当问题命中以下语义时，一级意图仍为 `query`，二级意图为 `data_meeting_bi`：

- 会议
- 报名
- 签到
- 客户画像
- 大区
- 到院
- 成交
- ROI
- 方案情报
- 会议运营

### 6.3 问数入口路由规则

`Text2SQLService.query(...)` 的 domain 决策优先级：

1. 显式传入 `domain`
2. `sub_intent == data_meeting_bi`
3. 默认 `generic`

### 6.4 各入口行为

- Chat：
  - 自动依赖意图识别分流
- HTTP `/api/v1/query/text2sql`：
  - 支持显式传 `domain`
- MCP `text2sql(...)`：
  - 支持显式传 `domain`

原则：

- Chat 自动分流
- Direct API / MCP 显式分流

## 7. 数据流设计

### 7.1 Chat 链路

```text
User Message
  -> IntentClassifier
  -> IntentType=query, SubIntentType=data_meeting_bi
  -> ChatWorkflow._handle_query
  -> Text2SQLService.query(question, sub_intent, conversation_id, context)
  -> MeetingBIQueryExecutor
  -> Text2SQLResponse
```

### 7.2 通用问数链路

```text
/api/v1/query/text2sql
  -> Text2SQLService.query(question, domain=None)
  -> resolve_domain() = generic
  -> GenericQueryExecutor
```

### 7.3 固定 BI 看板链路

```text
/api/v1/bi/*
  -> bi route
  -> bi service
  -> meeting_bi_database
```

## 8. 配置设计

### 8.1 保留现有通用问数配置

- `database_url`
- `text2sql_api_key`
- `text2sql_base_url`
- `text2sql_model`
- `text2sql_timeout_seconds`
- `text2sql_max_rows`

### 8.2 新增会议 BI 配置

- `meeting_bi_enabled`
- `meeting_bi_database_url`
- `meeting_bi_api_key`
- `meeting_bi_base_url`
- `meeting_bi_model`
- `meeting_bi_max_rows`
- `meeting_bi_context_ttl_seconds`
- `meeting_bi_train_on_startup`

### 8.3 配置原则

- 通用问数连接池与会议 BI 连接池必须独立
- 通用问数训练配置与会议 BI 训练配置必须独立
- 第一阶段建议 `meeting_bi_train_on_startup=false`
- 第一阶段采用懒加载初始化 + 单例缓存

## 9. `ai-bi-new` 迁移映射

### 9.1 迁移逻辑并改风格

从 `ai-bi-new/backend/app/` 迁入以下逻辑：

- `services/*.py` -> `ai-gateway/app/bi/services/*.py`
- `schemas/*.py` -> `ai-gateway/app/bi/schemas/*.py`
- `ai/context_store.py` -> `ai-gateway/app/bi/ai/context_store.py`
- `ai/query_executor.py` -> `ai-gateway/app/bi/ai/query_executor.py`
- `ai/training_data.py` -> `ai-gateway/app/bi/ai/training_data.py`
- `ai/vanna_client.py` -> `ai-gateway/app/bi/ai/vanna_client.py`
- `db/session.py` -> `ai-gateway/app/bi/db/session.py`

### 9.2 不保留原结构的部分

原 `api/v1/*.py` 路由文件不按原样迁入，而是按 `ai-gateway` 路由风格重组。

### 9.3 第一阶段不迁内容

- `api/v1/wecom.py`
- `wecom/*`

## 10. 接口设计

### 10.1 保留的统一问数入口

- `/api/v1/query/text2sql`

### 10.2 新增固定 BI 接口入口

- `/api/v1/bi/kpi/overview`
- `/api/v1/bi/registration/chart`
- `/api/v1/bi/registration/matrix`
- `/api/v1/bi/registration/detail`
- `/api/v1/bi/customer/profile`
- `/api/v1/bi/source/distribution`
- `/api/v1/bi/source/target-arrival`
- `/api/v1/bi/source/target-detail`
- `/api/v1/bi/operations/kpi`
- `/api/v1/bi/operations/trend`
- `/api/v1/bi/achievement/chart`
- `/api/v1/bi/achievement/table`
- `/api/v1/bi/achievement/detail`
- `/api/v1/bi/progress/ranking`
- `/api/v1/bi/proposal/overview`
- `/api/v1/bi/proposal/detail`

### 10.3 明确不保留的第一阶段入口

不保留独立的：

- `/api/v1/ai/query`
- `/api/v1/ai/query/stream`

会议 BI AI 查询统一回收至：

- Chat 问数链路
- `/api/v1/query/text2sql`
- MCP `text2sql(...)`

## 11. 数据模型调整建议

### 11.1 `Text2SQLRequest`

建议新增：

- `domain: str | None`
- `conversation_id: str | None`

### 11.2 `Text2SQLResponse`

建议新增：

- `domain: str`
- `answer: str | None`

保留：

- `sql`
- `results`
- `chart_spec`

原因：

会议 BI 问数天然包含“SQL + 结果 + 业务结论 + 图表建议”四类输出，当前响应模型不足以完整承载。

## 12. 验证策略

### 12.1 通用问数不回归

- 不带 `domain` 时仍走 `generic`
- 原有 Chat 的普通 query 问题不误切到会议 BI

### 12.2 会议 BI 分流正确

验证以下问题能够命中 `data_meeting_bi`：

- 报名多少客户
- 各大区成交金额是多少
- ROI 是多少

并确认：

- 实际走 `MeetingBIQueryExecutor`
- 返回 `domain=meeting_bi`

### 12.3 固定 BI 看板接口正常

至少覆盖：

- 1 个汇总接口
- 1 个图表接口
- 1 个明细下钻接口

### 12.4 SQL 安全验证

- 非 `SELECT` 拒绝执行
- 多语句拒绝执行
- 注释注入拒绝执行
- 访问非会议 BI 白名单表拒绝执行

### 12.5 连接隔离验证

- 通用问数连接池独立于会议 BI 连接池
- 固定 BI 接口与 BI 问数共用 BI 数据源
- 不影响现有通用问数数据源

### 12.6 MCP 一致性验证

- MCP `text2sql(domain="meeting_bi")`
- HTTP `/api/v1/query/text2sql` with `domain=meeting_bi`

二者返回结构一致。

## 13. 实施顺序建议

### 第一批

- 扩展 schema
- 扩展 intent classifier
- 拆分配置

### 第二批

- 重构 `Text2SQLService` 为统一门面
- 下沉现有通用逻辑为 `GenericQueryExecutor`

### 第三批

- 接入 `MeetingBIQueryExecutor`
- 接入会议 BI 数据连接与训练配置

### 第四批

- 接入固定 BI 看板接口 `/api/v1/bi/*`
- 补齐验证用例与回归验证

## 14. 第二阶段预留

第二阶段再处理：

- 企业微信长连接
- Webhook 推送
- 状态接口
- 是否进一步把会议 BI 数据读取收口到 `business-server`

## 15. 最终决策总结

本次融合采用以下最终方案：

- `Text2SQLService` 继续作为统一问数入口
- 当意图命中会议 BI 问数时，内部切换到 `MeetingBIQueryExecutor`
- 会议 BI 固定报表接口独立挂载 `/api/v1/bi/*`
- 会议 BI 数据源与通用问数数据源严格隔离
- 第一阶段不引入企业微信能力

该方案兼顾了以下目标：

- 统一入口
- 业务语义隔离
- 最小化对现有通用问数链路的扰动
- 为第二阶段企业微信能力接入预留清晰挂点
