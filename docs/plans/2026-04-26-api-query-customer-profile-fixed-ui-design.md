# /api-query 客户个人信息固定档案视图设计

## 背景

`/api/v1/api-query` 当前通过轻量路由、接口召回、DAG 规划、接口执行和动态 UI 生成返回 `ui_spec`。这条通用链路适合开放式问数，但“展示客户个人信息/客户健康档案”是高确定性的业务场景：接口集合、执行顺序、字段分区和页面顺序都应稳定，不应由 LLM 每次重新规划或由动态 UI 根据数据形态临时猜测。

本设计新增客户个人信息固定分支：当 query 命中客户档案查询语义时，固定读取 `ai-gateway/resources/ui_api_endpoints.xlsx` 中 `status='active'` 的 endpoint 元数据，先定位客户并完成唯一化判定，再调用客户档案相关接口，最后返回固定顺序的 `PlannerCard + PlannerDetailCard/PlannerInfoGrid/PlannerTable` UI Spec。若首跳客户查询返回重名或多个候选客户，必须先返回交互式 `wait select` 候选表，让用户选定客户后再继续下游接口和固定档案视图。

## 目标

1. 识别“展示客户个人信息/客户健康档案”类 query 后进入固定分支。
2. 接口清单以 `ui_api_endpoints.xlsx` 的 active endpoint 元数据为准。
3. 不使用 LLM 自由规划客户档案 DAG，避免漏接口、错顺序或错参数绑定。
4. 首跳客户查询存在多个候选时，先进入 `WAIT_SELECT_REQUIRED` 交互态；用户选定客户后才渲染档案分区。
5. UI 顺序严格按业务图片大标题顺序展示。
6. 普通分区卡片统一使用 `PlannerDetailCard`。
7. 资产概览使用 `PlannerInfoGrid`，资产明细使用 `PlannerTable`。
8. 单个分区失败不破坏整体档案结构，返回 `PARTIAL_SUCCESS` 并保留失败分区占位。

## 非目标

1. 不新增前端组件类型。
2. 不把所有 `/api-query` 查询都改成固定分支。
3. 不在第一版实现复杂配置后台。
4. 不展示编辑接口；编辑类 endpoint 不进入只读档案分支。

## 触发规则

采用“规则主导 + 关键词兜底”。query 同时满足以下条件时进入固定客户档案分支：

```text
命中客户信息关键词
AND
存在客户身份线索
```

客户信息关键词第一版包含：

1. 客户信息
2. 客户资料
3. 客户档案
4. 个人信息
5. 个人资料
6. 基础信息
7. 基础资料
8. 身份信息
9. 联系方式
10. 联系信息
11. 电子档案
12. 客户画像
13. 完整资料
14. 全部资料
15. 客户详情
16. 详细信息
17. 健康档案
18. 客户概况
19. 客户总览
20. 客户全貌

客户身份线索包括：

- `客户 + 名称`，例如“客户刘海坚”。
- `查询/查看/展示 + 名称 + 关键词`。
- 手机号模式。
- 身份证号模式。
- 客户ID/客户编号模式。

只命中关键词但没有客户身份线索时，不进入固定分支。例如“客户信息怎么维护”应继续走原通用流程。

## 接口元数据来源

接口清单来自：

```text
ai-gateway/resources/ui_api_endpoints.xlsx
Sheet1
status = active
```

当前确认：编辑接口已经从 active 清单中删除。`客户列表查询` 是固定首跳接口，其他 active endpoint 按固定展示顺序生成下游步骤。

首跳接口：

| 用途 | 名称 | api_id | path |
| --- | --- | --- | --- |
| 客户定位 | 客户列表查询 | `6bbc18329c3dde651603182a651569ab` | `/leczcore-crm/customerInquiry/getCustomerInfo` |

## 固定展示顺序

UI 展示顺序以用户提供的图片大标题为准，不按 Excel 行顺序展示。

| 顺序 | 分区 | api_id | 组件 |
| --- | --- | --- | --- |
| 1 | 一、身份与联系信息 | `0f8095e4adbf36aff9c9c03fa00e6ae2` | `PlannerDetailCard` |
| 2 | 二、健康基础数据 | `0dee49c62d09654d0762e785af389448` | `PlannerDetailCard` |
| 3 | 三、健康状况与医疗史 | `060811e41afe85711ff9506163270f03` | `PlannerDetailCard` |
| 4 | 四、体检情况 | `5b413b7dbadfd4296e0b116f486b3f82` | `PlannerDetailCard` |
| 5 | 五、生活方式与习惯 | `f5c8f5fbe235ccfd7709b3b3aacc7aac` | `PlannerDetailCard` |
| 6 | 六、心理与情绪 | `6a23d924c321dcf0e497853a529d14ea` | `PlannerDetailCard` |
| 7 | 七、个人喜好与优势 | `64d1e630e1528f6a54de48aac0d05f22` | `PlannerDetailCard` |
| 8 | 八、健康目标与核心痛点 | `a1cb957146b519d1b6bb81c0f791550e` | `PlannerDetailCard` |
| 9 | 九、消费能力与背景 | `348b5fe307fc9ce132fc169f1f0f4809` | `PlannerDetailCard` |
| 10 | 十、客户关系与服务记录 | `f6b31bd13027951cd20ae199600d2c9c` | `PlannerDetailCard` |
| 11 | 十一、教育铺垫记录 | `272d276935627e6fdd241b8995b0e8d6` | `PlannerDetailCard` |
| 12 | 十二、注意事项 | `91957d29162df68b3cfe97ac9d831bf4` | `PlannerDetailCard` |
| 13 | 十三、综合分析及咨询记录 | `9b7c02932bbf582615026f74595183b8` | `PlannerDetailCard` |
| 14 | 十四、备注 | `7df31026c1502783990268e873e98b5d` | `PlannerDetailCard` |
| 15 | 十五、负责人及执行日期 | `40b083c05720a091e0d05c9a8d5db6f9` | `PlannerDetailCard` |
| 16 | 十六、历史购买储值方案/规划方案/剩余项目金 | `fa969d461ef059ab82f1dd6d3c2aa116` | 组合区 |

资产组合区拆成：

| 子区 | bizFieldKey | 组件 |
| --- | --- | --- |
| 资产概览 | `summaryCard` | `PlannerInfoGrid` |
| 历史购买储值方案 | `deliveryRecords` | `PlannerTable` |
| 规划方案 | `curePlanRecords` | `PlannerTable` |

## DAG 编排

固定分支不调用 LLM 生成自由 DAG。

1. 生成 `step_get_customer_info`。
2. 从 query 中抽取客户线索，填入 `customerInfo`，并带默认分页参数。
3. 执行客户主查询。
4. 对客户主查询结果做唯一化判定。
5. 若客户主查询返回 0 条，结束固定分支，不执行下游。
6. 若客户主查询返回 1 条，使用该客户继续下游步骤。
7. 若客户主查询返回多条，返回 `WAIT_SELECT_REQUIRED` 候选表，不执行任何档案下游接口。
8. 用户通过 `selection_context.user_select` 选定客户后，恢复固定分支，并使用选定客户继续下游步骤。
9. 主查询唯一化成功后，对其他 active endpoint 生成下游 steps。
10. 下游 steps 统一依赖选定客户结果。
11. 参数绑定优先消费 endpoint 的 `predecessor_specs`。
12. 常见绑定为从选定客户行的 `idCard` 绑定到下游接口的 `encryptedIdCard`。
13. 下游步骤并发执行。

计划示例：

```json
{
  "plan_id": "dag_customer_profile_fixed",
  "steps": [
    {
      "step_id": "step_get_customer_info",
      "api_id": "6bbc18329c3dde651603182a651569ab",
      "params": {"customerInfo": "刘海坚", "pageNo": 1, "pageSize": 10},
      "depends_on": []
    },
    {
      "step_id": "step_identity_contact",
      "api_id": "0f8095e4adbf36aff9c9c03fa00e6ae2",
      "params": {"encryptedIdCard": "$[step_get_customer_info.data][*].idCard"},
      "depends_on": ["step_get_customer_info"]
    }
  ]
}
```

## 客户唯一化与 Wait Select

固定客户档案分支必须先解决“到底是哪一个客户”的问题，不能在多客户候选上直接展示 `PlannerDetailCard`。

唯一化规则：

1. 若 query 明确携带客户ID、手机号或身份证号，并且首跳结果可唯一匹配一条客户记录，则直接继续固定档案 DAG。
2. 若 query 只携带姓名、昵称或模糊线索，即使首跳成功，也必须按返回记录数判定。
3. 首跳返回 1 条时，选定该客户并继续下游。
4. 首跳返回多条时，固定分支进入等待态，不调用 15 个下游档案接口，不返回任何普通分区 `PlannerDetailCard`。
5. 等待态 UI 使用候选客户 `PlannerTable`，表格列优先展示能帮助用户消歧的字段，例如客户姓名、客户ID、手机号脱敏、身份证号脱敏、性别、年龄、门店、负责人。
6. 用户点击“使用该客户继续”后，请求 `/api/v1/api-query` 时必须保留原始 `query`，并增加 `selection_context.user_select`。
7. 恢复执行时以用户选择的候选行作为唯一客户来源，后续所有下游接口都只能绑定该行的 `idCard/encryptedIdCard/customerId`，不能再使用 `[*]` 扩散到多个客户。

等待态响应复用现有通用机制：执行结果使用 `error_code = "WAIT_SELECT_REQUIRED"`、`skipped_reason = "wait_select_required"`、`meta.pause_type = "WAIT_SELECT"`，响应层会优先将候选行渲染为 `PlannerTable` 并暴露 `row_actions`。固定分支实现时可以复用这套机制，也可以生成等价的固定候选表；无论哪种方式，交互态都必须先于固定档案分区。

候选表动作示例：

```json
{
  "action": "remoteQuery",
  "label": "使用该客户继续",
  "params": {
    "api": "/api/v1/api-query",
    "queryParams": {},
    "body": {
      "query": "展示客户刘海坚的个人信息",
      "selection_context": {
        "user_select": {
          "6bbc18329c3dde651603182a651569ab:encryptedIdCard:idCard": "kdxU1k6LlgVyeEtBEk+osiKORU+yMascJD7Heg6B7jw="
        }
      }
    }
  }
}
```

如果前端动作框架会自动把 `body` 与当前请求体合并，`query` 可以由当前请求体继承；否则固定分支必须显式携带 `query`，因为 `ApiQueryRequest.query` 是必填字段。

## UI Spec 契约

根节点复用 `PlannerCard`：

```json
{
  "type": "PlannerCard",
  "props": {
    "title": "查询客户刘海坚的个人信息",
    "subtitle": "客户健康档案 · 固定档案视图",
    "renderMode": "customer_profile_fixed",
    "customer": {
      "name": "刘海坚",
      "customerId": "...",
      "encryptedIdCard": "..."
    }
  },
  "children": ["section_identity_contact", "section_health_basic"]
}
```

普通分区复用 `PlannerDetailCard`：

```json
{
  "type": "PlannerDetailCard",
  "props": {
    "title": "一、身份与联系信息",
    "bizFieldKey": "identityContact",
    "apiId": "0f8095e4adbf36aff9c9c03fa00e6ae2",
    "status": "SUCCESS",
    "items": [
      {"label": "客户姓名", "value": "刘海坚"},
      {"label": "联系电话", "value": "138****0000"}
    ]
  }
}
```

资产概览复用 `PlannerInfoGrid`：

```json
{
  "type": "PlannerInfoGrid",
  "props": {
    "title": "资产概览",
    "bizFieldKey": "summaryCard",
    "apiId": "fa969d461ef059ab82f1dd6d3c2aa116",
    "items": [
      {"label": "储值方案项目金数量", "value": "12"},
      {"label": "可用规划金额", "value": "13245060.0"}
    ]
  }
}
```

资产明细复用 `PlannerTable`：

```json
{
  "type": "PlannerTable",
  "props": {
    "title": "历史购买储值方案",
    "bizFieldKey": "deliveryRecords",
    "apiId": "fa969d461ef059ab82f1dd6d3c2aa116",
    "columns": [],
    "dataSource": []
  }
}
```

## 字段展示规则

1. `PlannerDetailCard.props.items` 顺序优先使用 `detail_view_meta.display_fields`。
2. 若无 `detail_view_meta.display_fields`，按 `response_schema.properties.result.properties` 顺序。
3. label 优先取 `response_schema` 字段 `description`。
4. 空值统一显示 `-`，但字段行保留。
5. `list[string]` 用中文顿号 `、` 拼接展示。
6. `dict` 默认不展开为长 JSON，避免破坏分区卡片可读性。
7. `list[object]` 在普通档案分区内降级为 “共 N 条记录”；资产分区的列表进入 `PlannerTable`。
8. 客户主查询结果可作为“一、身份与联系信息”的兜底来源，但主展示仍以身份与联系信息接口为准。

## 状态与错误处理

整体状态：

| 场景 | execution_status | UI 行为 |
| --- | --- | --- |
| 客户主查询失败 | `ERROR` | 返回根卡片 + 错误提示，不执行下游 |
| 客户主查询为空 | `EMPTY` | 返回根卡片 + 未找到客户提示，不执行下游 |
| 客户主查询返回多条候选 | `SKIPPED` | 返回 `WAIT_SELECT_REQUIRED` 候选客户表，不执行下游，不展示档案分区 |
| 用户选定客户后续跑成功 | `SUCCESS` | 返回完整固定档案视图 |
| 主查询成功且全部分区成功 | `SUCCESS` | 返回完整固定档案视图 |
| 主查询成功但部分分区失败 | `PARTIAL_SUCCESS` | 保留所有分区顺序，失败分区显示错误占位 |
| 主查询成功但分区全为空 | `EMPTY` 或 `SUCCESS` | 返回固定骨架，分区显示暂无数据 |

分区失败仍输出 `PlannerDetailCard`：

```json
{
  "type": "PlannerDetailCard",
  "props": {
    "title": "二、健康基础数据",
    "bizFieldKey": "healthBasic",
    "apiId": "0dee49c62d09654d0762e785af389448",
    "status": "ERROR",
    "items": [
      {"label": "提示", "value": "该分区数据暂时获取失败"}
    ],
    "error": {
      "message": "业务接口调用失败",
      "recoverable": true
    }
  }
}
```

## 观测与审计

日志应能区分以下事件：

1. 是否命中客户档案固定分支。
2. 命中原因：关键词、身份线索、抽取出的 customerInfo。
3. Excel active endpoint 数量。
4. 客户主查询是否成功。
5. 首跳候选数量、是否进入 wait-select、用户最终选择的 binding key。
6. 下游成功、失败、空结果分区数量。
7. 参数绑定来源：`predecessor_specs`、兜底绑定、用户选择值或绑定失败。

建议结构化字段：

```text
trace_id
customer_profile_fixed=true|false
matched_keyword
customer_identifier_type
customer_endpoint_count
customer_candidate_count
wait_select_required=true|false
selected_customer_binding_key
profile_section_success_count
profile_section_error_count
profile_section_empty_count
```

## 测试验收

必须覆盖：

1. 命中关键词 + 客户身份线索，进入固定分支。
2. 只命中关键词但没有客户线索，不进入固定分支。
3. 有客户线索但 query 是单项查询，例如储值方案，不进入客户档案固定分支。
4. 从 Excel active endpoints 读取接口集合。
5. 客户主查询一定是第一步。
6. 下游分区步骤依赖客户主查询。
7. 参数绑定按 `predecessor_specs` 生成 `encryptedIdCard`。
8. `ui_spec.root` 是 `PlannerCard`。
9. 普通展示分区都是 `PlannerDetailCard`。
10. 分区顺序严格等于图片大标题顺序。
11. `十二、注意事项` 位于十一和十三之间，apiId 为 `91957d29162df68b3cfe97ac9d831bf4`。
12. 资产概览使用 `PlannerInfoGrid`。
13. 资产明细 `deliveryRecords/curePlanRecords` 使用 `PlannerTable`。
14. 单个下游接口失败时整体 `PARTIAL_SUCCESS`，失败分区仍保留卡片。
15. 客户主查询为空时不调用下游分区接口。
16. 客户主查询返回多条时，响应为 `SKIPPED/WAIT_SELECT_REQUIRED`，候选表包含完整候选客户字段。
17. 多客户等待态不生成任何普通档案分区 `PlannerDetailCard`，也不调用 15 个下游接口。
18. 选择候选客户后通过 `selection_context.user_select` 续跑，后续下游只绑定选定客户。
19. 明确唯一客户ID/手机号/身份证号且首跳唯一命中时，不进入 wait-select。
20. `list[string]` 字段能用 `、` 拼接展示。
21. 非客户档案查询继续走原 `/api-query` 通用流程。

## 实施建议

实现时优先保持改动边界清晰：

1. 新增客户档案意图识别 helper。
2. 新增 Excel active endpoint 装载/解析 helper，必要时做进程内缓存。
3. 新增客户唯一化 helper，复用现有 `WAIT_SELECT_REQUIRED` / `selection_context.user_select` 机制处理多客户候选。
4. 新增固定 DAG 构造器，复用现有 `ApiQueryExecutionPlan` 和 `ApiQueryPlanStep`。
5. 新增固定 UI spec 构造器，复用 `PlannerCard`、`PlannerDetailCard`、`PlannerInfoGrid`、`PlannerTable`。
6. 在 `ApiQueryWorkflow` 的 route/plan 分支中接入，避免污染普通查询路径。
