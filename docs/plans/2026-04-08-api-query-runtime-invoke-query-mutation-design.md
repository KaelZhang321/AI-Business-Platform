# /api-query runtime invoke 查询/变更接口设计

## 1. 背景

当前 `/api-query` 的执行阶段以 `ApiExecutor` 为核心，按照目录项里的 `method + path` 直接调用 business-server 或下游业务接口。

本次改造的目标是把 `ui_api_endpoints` 中维护的业务接口统一切到 business-server 提供的 runtime invoke 入口：

- `POST /ai-platform/api/v1/ui-builder/runtime/endpoints/{id}/invoke`

其中：

- `{id}` 对应 `ui_api_endpoints.id`
- runtime invoke 的 URL 必须可配置
- runtime invoke 请求壳中的保留 query 参数 `id` 必须可配置
- `/api-query` 需要同时支持 `GET` 型查询接口和 `POST` 型查询接口
- 变更接口必须被明确识别并阻断，不能依赖 HTTP 方法猜测

因此，本次设计将 `/api-query` 的安全边界从“只允许 GET”升级为“只允许被显式标记为查询语义的接口”。

## 2. 已确认结论

### 2.1 目录安全字段

在 `ui_api_endpoints` 增加安全字段：

- `operation_safety`

字段取值：

- `query`
- `mutation`

语义定义：

- `query`：查询接口，可以被 `/api-query` 消费
- `mutation`：变更接口，禁止进入 `/api-query`

### 2.2 支持的接口范围

本阶段 `/api-query` 支持：

- `GET + operation_safety=query`
- `POST + operation_safety=query`

本阶段 `/api-query` 禁止：

- `GET + operation_safety=mutation`
- `POST + operation_safety=mutation`
- 其他 HTTP 方法

### 2.3 参数落位规则

对 `ui_api_endpoints` 中的查询接口：

- `GET` 请求
  - 业务参数全部进入 runtime invoke 的 `queryParams`
  - `body` 固定为空对象 `{}`
- `POST` 请求
  - 业务参数全部进入 runtime invoke 的 `body`
  - `queryParams` 只保留 runtime invoke 固定字段

### 2.4 保留 query 参数

runtime invoke 请求壳中需要固定携带保留 query 参数：

- `id`

该值不再写死为 `27`，改为环境变量配置，例如：

- `API_QUERY_RUNTIME_RESERVED_ID=27`

若业务参数中也出现 `id`，不得覆盖该保留值，以环境变量值为准。

### 2.5 向量库索引策略

`operation_safety` 需要进入 API Catalog 向量库，并作为 Milvus 顶层字段存储。

但本阶段有一个重要约束：

- `retriever.py` 的 `_build_filter_expr()` 不增加 `operation_safety in ["query"]`
- 检索阶段不默认附带 `operation_safety=query`

也就是说：

- mutation 接口仍可能进入语义召回候选集
- 但它们必须在候选后校验、Planner 校验和执行器阶段被硬拦截

这样做的原因是：

- 保持当前检索链路“语义优先”的行为，不因为新安全字段改变召回排序与覆盖面
- 同时让 `operation_safety` 在召回结果中可见、可审计、可用于后续校验

## 3. 目标

### 3.1 目标

- 为 `ui_api_endpoints` 建立显式的查询/变更安全语义
- 将 `ui_api_endpoints` 的执行统一切换到 runtime invoke
- 支持 `GET`/`POST` 两类查询接口的不同参数装配方式
- 让 `operation_safety` 进入 MySQL 元数据、网关目录对象和 Milvus 顶层 schema
- 保持 `/api-query` 既有的检索、规划、DAG 执行和 UI 渲染主链路
- 提供清晰的灰度和回滚路径

### 3.2 非目标

- 本阶段不执行任何 `mutation` 接口
- 不改变 `/api-query` 的外部请求/响应契约
- 不重写现有 Planner、Dynamic UI、快照链路
- 不在本阶段引入更复杂的语义分类，如 `export_query`、`async_query`

## 4. 现状分析

### 4.1 当前安全边界问题

当前 `/api-query` 的安全边界主要锚定在 `method == GET`，分别出现在：

- 目录映射阶段的 `security_rules.read_only`
- 路由层 `_ensure_read_only_entry()`
- Planner 校验
- 旧执行器的 HTTP 方法白名单

这个模型的问题是：

- 不能表达“POST 但本质是查询”的接口
- 不能表达“GET 但语义上是变更”的接口
- 无法为未来的接口治理提供明确语义

### 4.2 当前 API Catalog 向量库问题

当前 Milvus `api_catalog` collection 的顶层字段包括：

- `domain`
- `env`
- `status`
- `tag_name`
- `method`
- `path`

但不包括 `operation_safety`。

同时，当前 retriever 的过滤表达式只支持：

- `domain`
- `env`
- `status`
- `tag_name`

这意味着如果不扩展 schema：

- 安全语义只能留在 MySQL 目录侧
- 召回结果里无法稳定读取该字段
- 后续链路无法基于向量库中的顶层字段做审计或断言

### 4.3 当前 OpenAPI 参数模型问题

当前 OpenAPI 导入主要提取的是：

- `requestBody.content.<mediaType>.schema`

这对 `POST` 查询接口足够，但对 `GET` 查询接口不够，因为 GET 接口的参数通常声明在：

- `parameters`

因此，如果本阶段要真正支持 `GET + query`，必须扩展元数据导入链路，让 GET 接口的 query/path 参数也能进入网关目录 schema。

## 5. 数据模型设计

### 5.1 business-server 表结构

在 `ui_api_endpoints` 新增字段：

```sql
ALTER TABLE ui_api_endpoints
ADD COLUMN operation_safety VARCHAR(16) NOT NULL DEFAULT 'mutation' COMMENT '接口安全语义: query/mutation';
```

默认值建议为 `mutation`，理由：

- 比默认 `query` 更安全
- 历史数据不会被意外放行
- 允许通过运营脚本或人工标注把真正的查询接口切换到 `query`

### 5.2 网关目录对象

`ApiCatalogEntry` 新增顶层字段：

- `operation_safety: Literal["query", "mutation"]`

同时保留在 `security_rules` 中镜像写入：

- `security_rules.operation_safety`
- `security_rules.query_safe`

其中：

- `query_safe = (operation_safety == "query")`

设计原则：

- 顶层字段用于程序逻辑和向量库结构化存储
- `security_rules` 镜像字段用于向后兼容与调试可读性

## 6. 向量库设计

### 6.1 indexer.py 是否需要增加该字段

需要。

而且要做成 Milvus 顶层字段，而不是只放进 `security_rules` JSON。

理由：

- 召回结果需要稳定带回该字段
- 后续校验逻辑不能依赖从 JSON 壳子里零散读取
- 顶层字段便于后续扩展为可选过滤条件或审计指标

### 6.2 Milvus schema 扩展

在 `api_catalog` collection 的 schema 中新增：

- `operation_safety: VARCHAR(16)`

并为其建立倒排索引：

- `INVERTED`

注意：

- 这是 schema 漂移，会触发 collection 重建
- 需要重跑 indexer 全量入库

### 6.3 indexer.py 写入内容

`indexer.py` 需要：

- schema 增加 `operation_safety`
- `collection.insert(data)` 时增加该列

同时继续保留：

- `security_rules.operation_safety`
- `security_rules.query_safe`

### 6.4 retriever.py 读取内容

`retriever.py` 需要：

- `_OUTPUT_FIELDS` 增加 `operation_safety`
- `_build_entry_from_fields()` 回填 `ApiCatalogEntry.operation_safety`

但明确不做：

- `_build_filter_expr()` 增加 `operation_safety` 默认过滤
- 检索请求默认附带 `operation_safety=query`

这一点是本次设计的硬约束。

### 6.5 检索阶段为什么不默认过滤

当前决策不是“安全前移到召回阶段”，而是：

- 检索阶段保持纯语义召回
- 安全校验放在候选后

这样做的结果是：

- mutation 接口可能被召回
- 但不能被选中进入真实执行

因此安全依赖于后续三道硬闸：

1. 候选选中后的准入校验
2. Planner 校验
3. 执行器最终拦截

## 7. 元数据导入设计

### 7.1 GET 查询接口

对 `GET + query` 接口，元数据导入必须读取 OpenAPI：

- `parameters`

重点支持：

- `in: query`
- `in: path`

并将其整理为参数 schema，供第二阶段参数提取使用。

### 7.2 POST 查询接口

对 `POST + query` 接口，继续读取：

- `requestBody.content.<mediaType>.schema`

作为业务 body 的 schema。

### 7.3 网关统一参数 schema 口径

本阶段建议采用以下统一口径：

- `GET + query`：`param_schema` 表示 query/path 参数结构
- `POST + query`：`param_schema` 表示 body 结构

更细的拆分例如：

- `query_param_schema`
- `body_schema`
- `path_param_schema`

可作为下一阶段再引入，不在本阶段扩大范围。

## 8. 执行架构设计

### 8.1 LegacyApiExecutor

保留现有 `ApiExecutor`，用于：

- builtin / 特殊条目
- 不走 runtime invoke 的历史路径

### 8.2 RuntimeInvokeExecutor

新增 `RuntimeInvokeExecutor`，用于：

- `ui_api_endpoints` 中 `operation_safety=query` 的条目
- `method in {GET, POST}` 的查询接口

统一请求：

- `POST {API_QUERY_RUNTIME_INVOKE_URL_TEMPLATE}`

### 8.3 ExecutorRouter

新增执行器路由层：

- builtin / 特殊条目 -> `LegacyApiExecutor`
- `operation_safety=query && method in {GET, POST}` -> `RuntimeInvokeExecutor`
- 其他情况在前置校验阶段直接阻断，不进入执行器

`ApiDagExecutor` 保持不变，只替换底层 `call()` 的执行器来源。

## 9. runtime invoke 请求模型

### 9.1 环境变量

新增配置：

- `API_QUERY_RUNTIME_INVOKE_URL_TEMPLATE`
- `API_QUERY_RUNTIME_FLOW_NUM`
- `API_QUERY_RUNTIME_RESERVED_ID`
- `API_QUERY_RUNTIME_CREATED_BY`
- `API_QUERY_RUNTIME_TIMEOUT_SECONDS`
- `API_QUERY_RUNTIME_ENABLED`

示例：

```env
API_QUERY_RUNTIME_INVOKE_URL_TEMPLATE=https://beta-ai-platform.kaibol.net/ai-platform/api/v1/ui-builder/runtime/endpoints/{id}/invoke
API_QUERY_RUNTIME_FLOW_NUM=1212
API_QUERY_RUNTIME_RESERVED_ID=27
API_QUERY_RUNTIME_CREATED_BY=
API_QUERY_RUNTIME_TIMEOUT_SECONDS=8.0
API_QUERY_RUNTIME_ENABLED=true
```

### 9.2 请求壳

统一使用：

```json
{
  "flowNum": "1212",
  "queryParams": {
    "id": "27"
  },
  "createdBy": "",
  "useSampleWhenEmpty": false,
  "body": {}
}
```

其中：

- URL 路径中的 `{id}` 替换为目录条目的 `entry.id`
- `queryParams.id` 使用环境变量 `API_QUERY_RUNTIME_RESERVED_ID`
- `useSampleWhenEmpty` 固定为 `false`

## 10. 参数装配规则

### 10.1 GET + query

业务参数全部进入 `queryParams`，`body` 固定为空对象：

```json
{
  "flowNum": "1212",
  "queryParams": {
    "id": "27",
    "customerId": "C001",
    "pageNum": 1,
    "pageSize": 20
  },
  "createdBy": "",
  "useSampleWhenEmpty": false,
  "body": {}
}
```

### 10.2 POST + query

业务参数全部进入 `body`，`queryParams` 只保留固定字段：

```json
{
  "flowNum": "1212",
  "queryParams": {
    "id": "27"
  },
  "createdBy": "",
  "useSampleWhenEmpty": false,
  "body": {
    "customerId": "C001",
    "filters": {
      "level": "A"
    }
  }
}
```

### 10.3 保留参数冲突

若提取参数中包含 `id`：

- 不允许覆盖保留值
- 以环境变量值为准
- 业务侧的 `id` 丢弃，并记录调试日志

## 11. 安全校验链路

由于检索阶段不默认按 `operation_safety` 过滤，所以安全链路必须后移并做多层兜底。

### 11.1 候选选定后校验

在 route 层选出候选条目后，立即校验：

- `entry.operation_safety == "query"`
- `entry.method in {"GET", "POST"}`
- `entry.status == "active"`

不满足则直接阻断。

### 11.2 direct 模式校验

`direct` 模式绕过语义召回，因此必须复用同样的校验逻辑。

### 11.3 Planner 校验

`planner.validate_plan(...)` 中新增校验：

- 引用的每一步接口必须是 `operation_safety=query`
- 方法只能是 `GET` 或 `POST`

否则拒绝进入执行阶段。

### 11.4 执行器最终校验

`RuntimeInvokeExecutor` 在发送 HTTP 之前再次校验：

- `operation_safety == query`
- `method in {GET, POST}`

这样即使上层漏检，也不会把 mutation 接口真正打到 business-server。

## 12. 响应处理设计

business-server runtime invoke 返回的是统一包壳：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

因此 `RuntimeInvokeExecutor` 需要：

1. 解析外层 JSON
2. 若 `code != 200`，转换为统一错误结果
3. 若 `code == 200`，取 `data`
4. 将 `data` 继续交给现有 `response_data_path` 抽取逻辑

这样可以保证现有：

- `response_data_path`
- `field_labels`
- `DynamicUIService`

不需要为 runtime invoke 单独分叉。

## 13. 兼容策略

### 13.1 不变项

- `/api-query` 外部请求契约
- `/api-query` 响应契约
- `execution_plan`
- `ui_runtime`
- `ui_spec`
- builtin / 特殊条目的旧执行链

### 13.2 变化项

- `ui_api_endpoints` 增加 `operation_safety`
- `ApiCatalogEntry` 增加 `operation_safety`
- Milvus schema 增加顶层字段 `operation_safety`
- 检索结果会带回 `operation_safety`
- 但检索阶段默认行为不因该字段变化

### 13.3 回滚策略

通过 `API_QUERY_RUNTIME_ENABLED=false` 可以整体回退到旧执行器。

注意：

- 表结构新增字段不会回滚
- Milvus schema 扩展会触发 collection 重建，但不影响旧逻辑可恢复运行

## 14. 测试设计

### 14.1 表结构与注册表映射测试

- `operation_safety=query` 正确映射到 `ApiCatalogEntry.operation_safety`
- `security_rules.query_safe == true`
- `operation_safety=mutation` 正确映射为不可执行

### 14.2 indexer/retriever 测试

- Milvus schema 正确新增顶层字段 `operation_safety`
- `indexer.py` 正确写入该字段
- `retriever.py` 正确读出该字段
- `_build_filter_expr()` 保持原状，不新增 `operation_safety` 默认过滤

### 14.3 元数据导入测试

- GET 接口的 OpenAPI `parameters` 被正确转换为参数 schema
- POST 接口的 `requestBody` 被正确转换为参数 schema

### 14.4 RuntimeInvokeExecutor 测试

- URL `{id}` 替换正确
- 保留 query 参数 `id` 来自环境变量
- GET 接口参数进入 `queryParams`
- POST 接口参数进入 `body`
- `useSampleWhenEmpty=false` 恒成立
- runtime invoke 响应拆壳正确

### 14.5 API 集成测试

- `GET + query` 放行并成功执行
- `POST + query` 放行并成功执行
- `GET + mutation` 阻断
- `POST + mutation` 阻断
- builtin 条目继续走旧执行链
- mutation 接口即使被召回，也不能进入真实执行

## 15. 风险与限制

### 15.1 风险

- 由于检索阶段不默认按 `operation_safety` 过滤，mutation 接口可能进入候选集
- 如果后续校验漏掉任一层，会带来安全风险
- 历史数据如果未及时补齐 `operation_safety`，会导致接口被默认视为 mutation 而无法执行

### 15.2 限制

- 当前仍依赖单一 `param_schema` 契约，尚未拆分 query/body/path 三类参数 schema
- 若 POST 查询接口 body 很复杂，第一版仍可能需要加强递归校验与装配逻辑

## 16. 实施步骤

1. 在 `ui_api_endpoints` 增加 `operation_safety`
2. 历史数据默认写入 `mutation`
3. 人工或脚本回填真正的 `query` 接口
4. 扩展 OpenAPI 导入逻辑，补 GET `parameters`
5. 扩展 `ApiCatalogEntry` 与 `registry_source`
6. 扩展 `indexer.py` Milvus schema 与写入数据
7. 扩展 `retriever.py` 输出字段回填
8. 新增 `RuntimeInvokeExecutor`
9. 新增执行器路由层
10. 改路由层 / direct 模式 / Planner / 执行器的安全校验逻辑
11. 增加配置项与测试
12. 通过开关灰度启用
