from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    QUERY = "query"
    TASK = "task"


class SubIntentType(str, Enum):
    """二级意图分类"""
    # 知识问答
    KNOWLEDGE_POLICY = "knowledge_policy"
    KNOWLEDGE_PRODUCT = "knowledge_product"
    KNOWLEDGE_MEDICAL = "knowledge_medical"
    # 数据查询
    DATA_CUSTOMER = "data_customer"
    DATA_SALES = "data_sales"
    DATA_OPERATION = "data_operation"
    DATA_MEETING_BI = "data_meeting_bi"
    # 任务操作
    TASK_QUERY = "task_query"
    TASK_CREATE = "task_create"
    TASK_APPROVE = "task_approve"
    # 通用
    GENERAL = "general"


class SSEEvent(BaseModel):
    """SSE 事件封装"""
    event_type: str = Field(..., description="事件类型: intent/content/ui_spec/sources/done")
    data: Any = Field(..., description="事件数据")


class IntentResult(BaseModel):
    """意图分类结果"""
    intent: IntentType = Field(..., description="识别的意图类型")
    sub_intent: SubIntentType = Field(SubIntentType.GENERAL, description="二级意图")
    confidence: float = Field(..., ge=0, le=1, description="置信度")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入消息")
    conversation_id: str | None = Field(None, description="会话ID，空则新建")
    user_id: str = Field(..., description="用户ID")
    context: dict[str, Any] | None = Field(None, description="上下文信息")
    stream: bool = Field(True, description="是否开启SSE流式返回")


class ChatResponse(BaseModel):
    conversation_id: str
    intent: IntentType
    content: str
    ui_spec: dict[str, Any] | None = Field(None, description="动态UI规格")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="引用来源")


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., description="检索查询")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数")
    doc_types: list[str] | None = Field(None, description="文档类型过滤")


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeResult]
    total: int


class KnowledgeResult(BaseModel):
    doc_id: str
    title: str
    content: str
    score: float
    doc_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApiQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="用户自然语言输入")
    conversation_id: str | None = Field(None, description="对话 ID（保留，用于未来多轮记忆）")
    top_k: int = Field(3, ge=1, le=5, description="候选接口数量")


class ApiQueryBusinessIntent(BaseModel):
    code: str = Field(..., description="业务意图编码")
    name: str = Field(..., description="业务意图名称")
    category: Literal["read", "write"] = Field(..., description="业务意图分类")
    description: str | None = Field(None, description="业务意图说明")


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
    selected_api_id: str | None = Field(None, description="路由命中的接口 ID")
    query_domains: list[str] = Field(default_factory=list, description="本次查询命中的业务域")
    business_intents: list[str] = Field(default_factory=list, description="路由阶段识别出的业务意图编码")
    is_multi_domain: bool = Field(False, description="是否命中多个业务域")
    reasoning: str | None = Field(None, description="路由阶段的简要判定说明")
    route_status: Literal["ok", "fallback"] = Field("ok", description="轻量路由是否正常完成")
    route_error_code: str | None = Field(None, description="路由失败时的结构化错误码")
    params: dict[str, Any] = Field(default_factory=dict, description="提取后的接口参数")


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
    code: str = Field(..., description="前端动作编码")
    description: str = Field(..., description="前端动作说明")
    enabled: bool = Field(True, description="当前运行时是否已启用")
    params_schema: dict[str, Any] = Field(default_factory=dict, description="动作参数约束")


class ApiQueryDetailRuntime(BaseModel):
    enabled: bool = Field(False, description="是否具备详情运行时信息")
    api_id: str | None = Field(None, description="详情查询使用的接口 ID")
    route_url: str | None = Field(None, description="建议调用的网关路由")
    identifier_field: str | None = Field(None, description="可用于跳转详情的主键字段")
    query_param: str | None = Field(None, description="详情查询时建议使用的参数名")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    template_code: str | None = Field(None, description="命中预设模板时的模板编码")
    fallback_mode: str | None = Field(None, description="未命中模板时的回退模式")


class ApiQueryPaginationRuntime(BaseModel):
    enabled: bool = Field(False, description="是否具备分页运行时信息")
    api_id: str | None = Field(None, description="分页刷新使用的接口 ID")
    total: int = Field(0, ge=0, description="总记录数")
    page_size: int | None = Field(None, ge=1, description="当前页大小")
    current_page: int | None = Field(None, ge=1, description="当前页码")
    page_param: str | None = Field(None, description="页码参数名")
    page_size_param: str | None = Field(None, description="分页大小参数名")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    mutation_target: str | None = Field(None, description="前端局部刷新目标路径")


class ApiQueryTemplateRuntime(BaseModel):
    enabled: bool = Field(False, description="是否命中模板快路")
    template_code: str | None = Field(None, description="模板编码")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    render_mode: str | None = Field(None, description="模板渲染模式")
    fallback_mode: str | None = Field(None, description="模板未命中时的回退模式")


class ApiQueryAuditRuntime(BaseModel):
    enabled: bool = Field(False, description="是否启用写前快照审计")
    snapshot_required: bool = Field(False, description="是否要求生成快照")
    snapshot_id: str | None = Field(None, description="快照 ID，未生成时为空")
    risk_level: str = Field("none", description="审计风险等级")


class ApiQueryUIRuntime(BaseModel):
    mode: Literal["read_only"] = Field("read_only", description="当前 `api_query` 的运行模式")
    components: list[str] = Field(default_factory=list, description="当前 spec 使用到的组件类型")
    ui_actions: list[ApiQueryUIAction] = Field(default_factory=list, description="当前运行时动作定义")
    detail: ApiQueryDetailRuntime = Field(default_factory=ApiQueryDetailRuntime, description="详情运行时提示")
    pagination: ApiQueryPaginationRuntime = Field(
        default_factory=ApiQueryPaginationRuntime,
        description="分页运行时提示",
    )
    template: ApiQueryTemplateRuntime = Field(default_factory=ApiQueryTemplateRuntime, description="模板运行时提示")
    audit: ApiQueryAuditRuntime = Field(default_factory=ApiQueryAuditRuntime, description="审计运行时提示")


class ApiQueryRuntimeMetadataResponse(BaseModel):
    version: str = Field("v1", description="运行时元数据版本")
    business_intent_categories: list[str] = Field(default_factory=lambda: ["read", "write"])
    ui_runtime: ApiQueryUIRuntime = Field(..., description="UI 运行时元数据")
    template_scenarios: list[dict[str, Any]] = Field(default_factory=list, description="模板场景说明")


class ApiQueryResponse(BaseModel):
    trace_id: str = Field(..., description="网关生成或透传的链路追踪 ID")
    query_domains: list[str] = Field(default_factory=list, description="本次查询命中的业务域")
    execution_status: ApiQueryExecutionStatus = Field(
        ApiQueryExecutionStatus.SUCCESS,
        description="本次接口执行状态",
    )
    api_id: str | None = Field(None, description="命中的接口 ID")
    api_path: str | None = Field(None, description="接口路径")
    params: dict[str, Any] = Field(default_factory=dict, description="提取的参数")
    business_intents: list[ApiQueryBusinessIntent] = Field(default_factory=list, description="识别出的业务意图")
    context_pool: dict[str, ApiQueryContextStepResult] = Field(
        default_factory=dict,
        description="强类型执行结果总线，供渲染层或调试使用",
    )
    ui_runtime: ApiQueryUIRuntime | None = Field(None, description="前端运行时元数据")
    ui_spec: dict[str, Any] | None = Field(None, description="json-render UI Spec")
    data_count: int = Field(0, description="数据条数")
    total: int = Field(0, description="总记录数（分页时）")
    error: str | None = Field(None, description="错误信息（接口调用失败时）")


class QueryDomain(str, Enum):
    GENERIC = "generic"
    MEETING_BI = "meeting_bi"


class Text2SQLRequest(BaseModel):
    question: str = Field(..., description="自然语言查询问题")
    database: str = Field("default", description="目标数据库")
    domain: QueryDomain | None = Field(None, description="查询域，空则由服务自动判定")
    conversation_id: str | None = Field(None, description="会话ID，用于多轮问数场景")


class Text2SQLResponse(BaseModel):
    sql: str = Field(..., description="生成的SQL")
    explanation: str = Field(..., description="SQL解释")
    domain: QueryDomain = Field(QueryDomain.GENERIC, description="实际命中的查询域")
    answer: str | None = Field(None, description="自然语言结论回答")
    results: list[dict[str, Any]] = Field(default_factory=list, description="查询结果")
    chart_spec: dict[str, Any] | None = Field(None, description="可视化图表规格")


class TrainItem(BaseModel):
    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="对应的SQL语句")


class TrainRequest(BaseModel):
    items: list[TrainItem] = Field(..., description="训练数据列表")


class TrainResponse(BaseModel):
    status: str = "ok"
    count: int = Field(..., description="训练条目数")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    services: dict[str, str] = Field(default_factory=dict)
