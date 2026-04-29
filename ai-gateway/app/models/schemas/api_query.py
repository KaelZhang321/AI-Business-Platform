from __future__ import annotations

from enum import Enum
from typing import Any, List, Literal

from pydantic import BaseModel, Field


class ApiQueryRequest(BaseModel):
    """`api_query` 的自然语言请求模型。

    功能：
        只承载自然语言入口，统一由网关负责路由、召回、参数提取和规划。

    返回值约束：
        - `query` 必填，避免入口协议出现二义性
        - `envs` / `tag_names` 参与 Milvus 标量过滤
    """

    query: str = Field(..., min_length=1, max_length=500, description="用户自然语言输入")
    conversation_id: str | None = Field(None, description="对话 ID（保留，用于未来多轮记忆）")
    top_k: int = Field(3, ge=1, le=5, description="候选接口数量")
    envs: list[str] = Field(default_factory=list, description="可选的环境过滤，如 prod / dev")
    tag_names: list[str] = Field(default_factory=list, description="可选的业务标签过滤，如 合同管理")
    selection_context: dict[str, Any] | None = Field(
        None,
        description="user_select 续跑上下文（可选）",
    )


class ApiQueryBusinessIntent(BaseModel):
    """第二阶段输出的业务意图对象。

    功能：
        把第二阶段识别出的业务写意图收敛成稳定契约，供前端渲染层、审计链路
        与后续 Java 安全代理共同消费。

    返回值约束：
        - `code` 必须是对外稳定的业务意图编码，而不是前端物理动作名
        - `risk_level` 仅表达审计提示，不授予任何真实写权限
    """

    code: str = Field(..., description="业务意图编码")
    name: str = Field(..., description="业务意图名称")
    category: Literal["read", "write"] = Field(..., description="业务意图分类")
    description: str | None = Field(None, description="业务意图说明")
    risk_level: str | None = Field(None, description="业务意图风险等级提示")


class ApiQueryExecutionStatus(str, Enum):
    """api_query 执行状态枚举。

    约束：
        - `SUCCESS` 表示成功拿到可渲染数据
        - `EMPTY` 表示接口成功执行但无数据
        - `ERROR` 表示上游调用失败
        - `SKIPPED` 表示网关为保护链路主动跳过执行
        - `PARTIAL_SUCCESS` 预留给未来多步骤场景
    """

    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class ApiQueryRoutingResult(BaseModel):
    """第二阶段内部路由结果。

    功能：
        同时承载轻量路由与候选内路由的结构化结果，避免两套临时 dict 并行存在。
    """

    selected_api_id: str | None = Field(None, description="路由命中的接口 ID")
    query_domains: list[str] = Field(default_factory=list, description="本次查询命中的业务域")
    business_intents: list[str] = Field(default_factory=list, description="路由阶段识别出的业务意图编码")
    is_multi_domain: bool = Field(False, description="是否命中多个业务域")
    reasoning: str | None = Field(None, description="路由阶段的简要判定说明")
    route_status: Literal["ok", "fallback"] = Field("ok", description="轻量路由是否正常完成")
    route_error_code: str | None = Field(None, description="路由失败时的结构化错误码")
    params: dict[str, Any] = Field(default_factory=dict, description="提取后的接口参数")


class ApiQueryPlanStep(BaseModel):
    """第三阶段 DAG 中的单个只读执行步骤。

    功能：
        将 Planner 生成的图纸收敛成稳定的步骤对象，供网关做白名单校验、
        JSONPath 依赖绑定与拓扑执行。

    返回值约束：
        - `api_id` 对应 `ui_api_endpoints.id`，供前端和审计链路稳定识别接口实体
        - `api_path` 必须命中第二阶段召回出的查询安全接口
        - `depends_on` 只描述前置步骤 ID，不描述执行器细节
        - `params` 允许包含字面量和 JSONPath 绑定表达式
    """

    step_id: str = Field(..., min_length=1, description="DAG 内部唯一步骤标识")
    api_id: str | None = Field(None, description="步骤对应的接口 ID，对齐 ui_api_endpoints.id")
    api_path: str = Field(..., min_length=1, description="步骤对应的目标接口路径")
    params: dict[str, Any] = Field(default_factory=dict, description="步骤参数，可包含 JSONPath 绑定")
    depends_on: list[str] = Field(default_factory=list, description="前置依赖步骤 ID 列表")


class ApiQueryExecutionPlan(BaseModel):
    """第三阶段 Planner 输出的只读执行计划。

    功能：
        作为 Stage-3 的核心中间态，承接“大模型图纸”与“物理执行总线”之间的
        契约，避免后续流程直接消费松散 dict。

    返回值约束：
        - `plan_id` 必须稳定存在，便于日志追踪和问题复盘
        - `steps` 至少包含一个步骤
    """

    plan_id: str = Field(..., min_length=1, description="执行计划唯一标识")
    steps: list[ApiQueryPlanStep] = Field(default_factory=list, min_length=1, description="执行步骤列表")


class ApiQueryExecutionResult(BaseModel):
    """网关内部使用的执行结果包装。

    功能：
        把“成功 / 空结果 / 错误 / 跳过”统一成同一条只读执行总线，避免 route
        层再用 `None`、异常或零散字符串去猜状态。

    入参业务含义：
        各字段由执行器或 route 填充，不直接暴露给前端动作层。

    返回值约束：
        - `status` 决定当前节点能否进入渲染
        - `error_code` / `retryable` 只在错误或跳过场景下有意义
        - `meta` 用于承载截断、缺参等运行时附加信息
    """

    status: ApiQueryExecutionStatus = Field(..., description="执行结果状态")
    data: list[dict[str, Any]] | dict[str, Any] | None = Field(None, description="接口执行后的原始数据")
    total: int = Field(0, ge=0, description="总记录数")
    error: str | None = Field(None, description="错误信息")
    error_code: str | None = Field(None, description="结构化错误码")
    retryable: bool = Field(False, description="当前错误是否可重试")
    trace_id: str | None = Field(None, description="执行链路 Trace ID")
    skipped_reason: str | None = Field(None, description="跳过执行时的原因")
    meta: dict[str, Any] = Field(default_factory=dict, description="执行附加元数据")


class ApiQueryExecutionErrorDetail(BaseModel):
    """供 `context_pool` 消费的结构化错误详情。

    功能：
        将上游 HTTP 错误、超时、缺参跳过等场景统一转换为 Renderer 可判别的错误对象。

    返回值约束：
        `message` 必须始终可展示给前端提示层；`code` 与 `retryable` 供后续策略判断。
    """

    code: str | None = Field(None, description="结构化错误码")
    message: str = Field(..., description="错误信息")
    retryable: bool = Field(False, description="是否可重试")


class ApiQueryContextStepResult(BaseModel):
    """`context_pool` 中单个步骤的强类型结果。

    功能：
        为 Renderer 提供稳定的步骤级事实输入，而不是把原始接口返回直接拍平成数组。

    返回值约束：
        - `data` 必须是已经过网关裁剪后的可渲染数据
        - `error` 与 `skipped_reason` 二选一或同时为空
        - `meta` 仅承载运行时说明，不承载前端动作定义
    """

    status: ApiQueryExecutionStatus = Field(..., description="步骤执行状态")
    domain: str | None = Field(None, description="步骤所属业务域")
    api_id: str | None = Field(None, description="步骤对应的接口 ID")
    api_path: str | None = Field(None, description="步骤对应的接口路径")
    method: str | None = Field(None, description="步骤对应的 HTTP 方法")
    data: list[dict[str, Any]] | dict[str, Any] | None = Field(None, description="供渲染层消费的步骤数据")
    total: int = Field(0, ge=0, description="步骤总记录数")
    error: ApiQueryExecutionErrorDetail | None = Field(None, description="结构化错误信息")
    skipped_reason: str | None = Field(None, description="步骤被跳过时的原因")
    meta: dict[str, Any] = Field(default_factory=dict, description="步骤附加元数据")


class ApiQueryUIAction(BaseModel):
    """前端运行时动作定义。"""

    code: str = Field(..., description="前端动作编码")
    description: str = Field(..., description="前端动作说明")
    enabled: bool = Field(True, description="当前运行时是否已启用")
    params_schema: dict[str, Any] = Field(default_factory=dict, description="动作参数约束")


class ApiQueryDetailRequestRuntime(BaseModel):
    """详情二跳请求契约。

    功能：
        把“第二次详情请求怎么发”从散落字段收口为稳定子对象，避免前端继续把
        `identifier_param / mode / response_mode` 混在一层里自行约定。
    """

    mode: Literal["direct"] = Field("direct", description="详情二跳固定走直达快路")
    response_mode: Literal["full_spec"] = Field("full_spec", description="详情二跳当前固定返回整页 Spec")
    param_source: Literal["queryParams", "body"] | None = Field(None, description="详情参数的归属位置")
    identifier_param: str | None = Field(None, description="详情查询使用的主键参数名")
    request_schema_fields: list[str] | None = Field(
        None,
        description="详情接口 request_schema 的顶层字段白名单，仅供网关内部生成 ui_spec 使用。",
        exclude=True,
    )


class ApiQueryDetailSourceRuntime(BaseModel):
    """详情主键取值契约。

    功能：
        前端点击列表行查看详情时，需要知道“从当前行哪个字段取值”。这层信息如果不显式
        暴露，就会逼着前端反向解析表格列或执行计划，导致契约再次漂移。
    """

    identifier_field: str | None = Field(None, description="从当前行提取详情主键值的字段名")
    value_type: str | None = Field(None, description="主键值类型提示")
    required: bool = Field(False, description="是否要求该主键值必须存在")


class ApiQueryDetailRuntime(BaseModel):
    """详情页运行时契约。"""

    enabled: bool = Field(False, description="是否具备详情运行时信息")
    api_id: str | None = Field(None, description="详情查询使用的接口 ID")
    route_url: str | None = Field(None, description="建议调用的网关路由")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    request: ApiQueryDetailRequestRuntime = Field(
        default_factory=ApiQueryDetailRequestRuntime,
        description="详情二跳请求约束",
    )
    source: ApiQueryDetailSourceRuntime = Field(
        default_factory=ApiQueryDetailSourceRuntime,
        description="详情主键取值约束",
    )
    render_mode: str = Field("dynamic_ui", description="详情渲染策略，template_first 表示模板优先")
    template_code: str | None = Field(None, description="详情模板编码")
    fallback_mode: str = Field("dynamic_ui", description="模板未命中时的兜底模式")
    detail_view_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="详情字段元数据（display/required/exclude/groups）",
    )


class ApiQueryListPaginationRuntime(BaseModel):
    """列表分页运行时契约。"""

    enabled: bool = Field(False, description="当前列表是否支持分页二跳")
    total: int = Field(0, ge=0, description="总记录数")
    page_size: int | None = Field(None, ge=1, description="当前页大小")
    current_page: int | None = Field(None, ge=1, description="当前页码")
    page_param: str | None = Field(None, description="页码参数名")
    page_size_param: str | None = Field(None, description="分页大小参数名")
    mutation_target: str | None = Field(None, description="前端局部刷新的目标路径")


class ApiQueryListFilterFieldRuntime(BaseModel):
    """列表筛选字段定义。"""

    name: str = Field(..., description="筛选字段名")
    label: str = Field(..., description="筛选字段展示名")
    value_type: str = Field(..., description="筛选字段值类型")
    component: Literal["input", "number", "select"] = Field(
        "input",
        description="筛选组件类型，仅暴露当前渲染层已支持的组件集合。",
    )
    required: bool = Field(False, description="当前筛选字段是否必填")


class ApiQueryListTableFieldRuntime(BaseModel):
    """列表表格列定义。

    功能：
        该结构用于把“首屏列表列白名单”提升为显式 runtime 契约，避免渲染层从首行数据猜列导致
        首屏字段失控。组合列通过 `source_fields` 显式表达来源字段，由渲染层生成派生列。
    """

    name: str = Field(..., description="列表字段名或组合列派生字段名")
    title: str | None = Field(None, description="列表列标题")
    source_fields: list[str] = Field(default_factory=list, description="组合列来源字段；为空表示普通单字段列")
    separator: str = Field("", description="组合列字段之间的连接符")
    empty_value: str = Field("-", description="组合列所有字段为空时的展示值")


class ApiQueryListFiltersRuntime(BaseModel):
    """列表筛选运行时契约。"""

    enabled: bool = Field(False, description="当前列表是否支持筛选二跳")
    fields: list[ApiQueryListFilterFieldRuntime] = Field(default_factory=list, description="允许前端展示的筛选字段")


class ApiQueryListQueryContextRuntime(BaseModel):
    """列表查询上下文契约。

    功能：
        它是分页、改筛选条件等二跳请求的唯一正式参数来源，目的是让前端不再解析
        `execution_plan.steps[*].params` 这种内部执行细节。
    """

    enabled: bool = Field(False, description="当前列表是否允许沿用查询上下文继续二跳")
    current_params: dict[str, Any] = Field(default_factory=dict, description="当前已经生效的完整查询参数")
    page_param: str | None = Field(None, description="页码参数名")
    page_size_param: str | None = Field(None, description="分页大小参数名")
    preserve_on_pagination: list[str] = Field(default_factory=list, description="翻页时必须保留的筛选字段")
    reset_page_on_filter_change: bool = Field(True, description="筛选条件变更后是否强制回到第一页")


class ApiQueryListRuntime(BaseModel):
    """列表交互运行时契约。"""

    enabled: bool = Field(False, description="当前结果是否具备列表二跳能力")
    api_id: str | None = Field(None, description="列表二跳继续使用的接口 ID")
    route_url: str | None = Field(None, description="建议调用的网关路由")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    param_source: Literal["queryParams", "body"] | None = Field(None, description="列表参数的归属位置")
    request_schema_fields: list[str] | None = Field(
        None,
        description="列表接口 request_schema 的顶层字段白名单，仅供网关内部生成 ui_spec 使用。",
        exclude=True,
    )
    pagination: ApiQueryListPaginationRuntime = Field(
        default_factory=ApiQueryListPaginationRuntime,
        description="列表分页运行时契约",
    )
    filters: ApiQueryListFiltersRuntime = Field(
        default_factory=ApiQueryListFiltersRuntime,
        description="列表筛选运行时契约",
    )
    table_fields: list[ApiQueryListTableFieldRuntime] = Field(
        default_factory=list,
        description="列表列白名单；为空时按历史规则自动推断",
    )
    query_context: ApiQueryListQueryContextRuntime = Field(
        default_factory=ApiQueryListQueryContextRuntime,
        description="列表查询上下文契约",
    )


class ApiQueryFormOptionSourceRuntime(BaseModel):
    """表单选项来源契约。"""

    type: str = Field(..., description="选项来源类型")
    dict_code: str | None = Field(None, description="当类型为 dict 时的字典编码")


class ApiQueryFormFieldRuntime(BaseModel):
    """表单字段运行时契约。

    功能：
        `ui_runtime.form.fields` 描述的是提交契约，而不是页面组件树。它只回答：
        1. 这个字段最终以什么 key 提交
        2. 当前值从哪个 `state_path` 读取
        3. 该字段是用户填写、上下文透传还是字典选择
    """

    name: str = Field(..., description="字段业务名")
    description: str = Field(None, description="字段描述")
    value_type: str = Field(..., description="字段值类型")
    state_path: str = Field(..., description="字段绑定到 `ui_spec.state` 的路径")
    submit_key: str = Field(..., description="提交给后端时使用的 payload 键名")
    required: bool = Field(False, description="该字段提交时是否必填")
    writable: bool = Field(False, description="当前字段是否允许用户编辑")
    source_kind: Literal["context", "user_input", "dictionary", "derived"] = Field(
        "context",
        description="字段值来源类型",
    )
    option_source: ApiQueryFormOptionSourceRuntime | None = Field(None, description="选择型字段的选项来源")


class ApiQueryFormSubmitRuntime(BaseModel):
    """表单提交流程契约。"""

    business_intent: str | None = Field(None, description="当前表单对应的业务意图编码")
    confirm_required: bool = Field(False, description="是否要求用户显式确认后再提交")


class ApiQueryFormRuntime(BaseModel):
    """表单运行时契约。"""

    enabled: bool = Field(False, description="当前页面是否具备正式表单提交能力")
    form_code: str | None = Field(None, description="稳定的表单场景编码")
    mode: Literal["create", "edit", "confirm"] | None = Field(None, description="表单模式")
    api_id: str | None = Field(None, description="表单提交使用的接口 ID")
    route_url: str | None = Field(None, description="建议调用的 runtime invoke URL；无具体接口上下文时为空")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    request_schema_fields: list[str] | None = Field(
        None,
        description="表单提交接口 request_schema 的顶层字段白名单，仅供网关内部生成 ui_spec 使用。",
        exclude=True,
    )
    state_path: str | None = Field(None, description="表单根状态路径")
    fields: list[ApiQueryFormFieldRuntime] = Field(default_factory=list, description="表单字段运行时契约")
    submit: ApiQueryFormSubmitRuntime = Field(
        default_factory=ApiQueryFormSubmitRuntime,
        description="表单提交约束",
    )


class ApiQueryAuditRuntime(BaseModel):
    """写前快照审计运行时契约。"""

    enabled: bool = Field(False, description="是否启用写前快照审计")
    snapshot_required: bool = Field(False, description="是否要求生成快照")
    snapshot_id: str | None = Field(None, description="快照 ID，未生成时为空")
    risk_level: str = Field("none", description="审计风险等级")


class ApiQueryUIRuntime(BaseModel):
    """`api_query` 返回给前端的运行时元数据总线。"""

    mode: Literal["read_only"] = Field("read_only", description="当前 `api_query` 的运行模式")
    # 使用 `typing.List` 而不是 `list[...]`，是为了规避 Python 3.14 下类内字段名 `list`
    # 与内建泛型同名时的注解求值冲突，保证对外契约仍然保持 `ui_runtime.list` 不变。
    components: List[str] = Field(default_factory=list, description="当前 spec 使用到的组件类型")
    ui_actions: List[ApiQueryUIAction] = Field(default_factory=list, description="当前运行时动作定义")
    list: ApiQueryListRuntime = Field(default_factory=ApiQueryListRuntime, description="列表运行时提示")
    detail: ApiQueryDetailRuntime = Field(default_factory=ApiQueryDetailRuntime, description="详情运行时提示")
    form: ApiQueryFormRuntime = Field(default_factory=ApiQueryFormRuntime, description="表单运行时提示")
    audit: ApiQueryAuditRuntime = Field(default_factory=ApiQueryAuditRuntime, description="审计运行时提示")


class ApiQueryRuntimeMetadataResponse(BaseModel):
    """`runtime-metadata` 接口响应模型。"""

    version: str = Field("v1", description="运行时元数据版本")
    business_intent_categories: list[str] = Field(default_factory=lambda: ["read", "write"])
    ui_runtime: ApiQueryUIRuntime = Field(..., description="UI 运行时元数据")
    template_scenarios: list[dict[str, Any]] = Field(default_factory=list, description="模板场景说明")


class ApiQueryResponse(BaseModel):
    """`api_query` 主接口响应模型。

    功能：
        把前端真正需要的最小读写编排 envelope 固定为 5 个对外字段，避免把
        `context_pool`、运行时推导细节和调试锚点继续暴露到外部契约里。
    """

    trace_id: str = Field(..., description="网关生成或透传的链路追踪 ID")
    execution_status: ApiQueryExecutionStatus = Field(
        ApiQueryExecutionStatus.SUCCESS,
        description="本次接口执行状态",
    )
    execution_plan: ApiQueryExecutionPlan | None = Field(None, description="执行计划；写场景前端可据此识别后续接口")
    ui_runtime: ApiQueryUIRuntime | None = Field(
        None,
        description="后端内部运行时元数据；默认不进入 `/api-query` 对外响应。",
        exclude=True,
    )
    ui_spec: dict[str, Any] | None = Field(None, description="json-render UI Spec")
    error: str | None = Field(None, description="错误信息（接口调用失败时）")
