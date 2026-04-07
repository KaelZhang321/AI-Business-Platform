from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IntentType(str, Enum):
    """聊天主工作流的一级意图枚举。"""

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
    """意图分类结果。"""

    intent: IntentType = Field(..., description="识别的意图类型")
    sub_intent: SubIntentType = Field(SubIntentType.GENERAL, description="二级意图")
    confidence: float = Field(..., ge=0, le=1, description="置信度")


class ChatRequest(BaseModel):
    """聊天入口请求模型。"""

    message: str = Field(..., description="用户输入消息")
    conversation_id: str | None = Field(None, description="会话ID，空则新建")
    user_id: str = Field(..., description="用户ID")
    context: dict[str, Any] | None = Field(None, description="上下文信息")
    stream: bool = Field(True, description="是否开启SSE流式返回")


class ChatResponse(BaseModel):
    """聊天入口响应模型。"""

    conversation_id: str
    intent: IntentType
    content: str
    ui_spec: dict[str, Any] | None = Field(None, description="动态UI规格")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="引用来源")


class KnowledgeSearchRequest(BaseModel):
    """知识检索请求模型。"""

    query: str = Field(..., description="检索查询")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数")
    doc_types: list[str] | None = Field(None, description="文档类型过滤")


class KnowledgeSearchResponse(BaseModel):
    """知识检索响应模型。"""

    results: list[KnowledgeResult]
    total: int


class KnowledgeResult(BaseModel):
    """知识检索命中结果。"""

    doc_id: str
    title: str
    content: str
    score: float
    doc_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApiQueryMode(str, Enum):
    """`api_query` 请求模式枚举。"""

    NL = "nl"
    DIRECT = "direct"


class ApiQueryDirectQuery(BaseModel):
    """`/api-query` 直达快路载荷。

    功能：
        承载“前端已经拿到目标接口 ID 与参数”的二跳场景输入，让详情、分页和刷新
        不必再回到自然语言链路重复消耗 LLM 与 Milvus。

    返回值约束：
        - `api_id` 必须对应注册表中的稳定接口主键
        - `params` 即使为空也必须显式传入，避免前后端对“缺省参数”理解不一致

    Edge Cases:
        - `params={}` 是合法输入，但 `params` 这个键本身不能缺失
    """

    api_id: str = Field(..., min_length=1, description="目标接口 ID，对应 `ui_api_endpoints.id`")
    params: dict[str, Any] = Field(..., description="直达模式下的显式接口参数")


class ApiQueryRequest(BaseModel):
    """`api_query` 的自然语言请求模型。

    功能：
        同时承载两种入口模式：

        1. `nl`：自然语言主链路，继续走路由、召回、参数提取和规划
        2. `direct`：二跳快路，前端已知 `api_id + params` 时直接执行只读查询

    返回值约束：
        - `mode` 缺省时必须按 `nl` 处理，以兼容历史前端
        - `envs` / `tag_names` 仅在 `nl` 模式下参与 Milvus 标量过滤
        - `direct` 模式下不要求 `query`，但必须提供 `direct_query`

    Edge Cases:
        - `direct` 模式不会因为 `query` 为空而失败；真正的硬校验落在 `direct_query`
        - 历史请求只传 `query` 时，仍会被完整视作 `nl` 模式
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mode": "nl",
                    "query": "查询张三客户",
                    "conversation_id": "conv_001",
                    "top_k": 3,
                    "envs": ["prod"],
                    "tag_names": ["客户管理"],
                },
                {
                    "mode": "direct",
                    "conversation_id": "conv_001",
                    "direct_query": {
                        "api_id": "customer_detail",
                        "params": {"customerId": "C001"},
                    },
                },
            ]
        }
    )

    mode: ApiQueryMode = Field(ApiQueryMode.NL, description="请求模式：`nl` 或 `direct`")
    query: str | None = Field(None, min_length=1, max_length=500, description="用户自然语言输入")
    conversation_id: str | None = Field(None, description="对话 ID（保留，用于未来多轮记忆）")
    top_k: int = Field(3, ge=1, le=5, description="候选接口数量")
    envs: list[str] = Field(default_factory=list, description="可选的环境过滤，如 prod / dev")
    tag_names: list[str] = Field(default_factory=list, description="可选的业务标签过滤，如 合同管理")
    direct_query: ApiQueryDirectQuery | None = Field(None, description="直达快路模式的显式接口调用信息")

    @model_validator(mode="after")
    def validate_mode_contract(self) -> ApiQueryRequest:
        """校验 `nl/direct` 双模式请求契约。

        功能：
            这里把“入口长什么样”固定在 schema 层，而不是让 route 再手写多套
            if/else 兜底。这样 OpenAPI、FastAPI 校验和实际实现可以共享同一份事实。

        Raises:
            ValueError: 当 `mode` 与实际载荷组合不合法时抛出。
        """
        if self.mode == ApiQueryMode.DIRECT:
            if self.direct_query is None:
                raise ValueError("mode=direct 时必须提供 direct_query")
            return self

        if not self.query:
            raise ValueError("mode=nl 时必须提供 query")
        return self


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
        - `api_path` 必须命中第二阶段召回出的 GET 接口
        - `depends_on` 只描述前置步骤 ID，不描述执行器细节
        - `params` 允许包含字面量和 JSONPath 绑定表达式
    """

    step_id: str = Field(..., min_length=1, description="DAG 内部唯一步骤标识")
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


class ApiQueryDetailRuntime(BaseModel):
    """详情页运行时契约。"""

    enabled: bool = Field(False, description="是否具备详情运行时信息")
    api_id: str | None = Field(None, description="详情查询使用的接口 ID")
    route_url: str | None = Field(None, description="建议调用的网关路由")
    identifier_field: str | None = Field(None, description="可用于跳转详情的主键字段")
    query_param: str | None = Field(None, description="详情查询时建议使用的参数名")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    template_code: str | None = Field(None, description="命中预设模板时的模板编码")
    fallback_mode: str | None = Field(None, description="未命中模板时的回退模式")


class ApiQueryPaginationRuntime(BaseModel):
    """分页运行时契约。"""

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
    """模板快路运行时契约。"""

    enabled: bool = Field(False, description="是否命中模板快路")
    template_code: str | None = Field(None, description="模板编码")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    render_mode: str | None = Field(None, description="模板渲染模式")
    fallback_mode: str | None = Field(None, description="模板未命中时的回退模式")


class ApiQueryAuditRuntime(BaseModel):
    """写前快照审计运行时契约。"""

    enabled: bool = Field(False, description="是否启用写前快照审计")
    snapshot_required: bool = Field(False, description="是否要求生成快照")
    snapshot_id: str | None = Field(None, description="快照 ID，未生成时为空")
    risk_level: str = Field("none", description="审计风险等级")


class ApiQueryUIRuntime(BaseModel):
    """`api_query` 返回给前端的运行时元数据总线。"""

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
    """`runtime-metadata` 接口响应模型。"""

    version: str = Field("v1", description="运行时元数据版本")
    business_intent_categories: list[str] = Field(default_factory=lambda: ["read", "write"])
    ui_runtime: ApiQueryUIRuntime = Field(..., description="UI 运行时元数据")
    template_scenarios: list[dict[str, Any]] = Field(default_factory=list, description="模板场景说明")


class ApiQueryResponse(BaseModel):
    """`api_query` 主接口响应模型。

    功能：
        把前端真正需要的最小读写编排 envelope 固定为 6 个字段，避免把
        `context_pool`、业务语义和调试锚点继续暴露到外部契约里。
    """

    trace_id: str = Field(..., description="网关生成或透传的链路追踪 ID")
    execution_status: ApiQueryExecutionStatus = Field(
        ApiQueryExecutionStatus.SUCCESS,
        description="本次接口执行状态",
    )
    execution_plan: ApiQueryExecutionPlan | None = Field(None, description="执行计划；写场景前端可据此识别后续接口")
    ui_runtime: ApiQueryUIRuntime | None = Field(None, description="前端运行时元数据")
    ui_spec: dict[str, Any] | None = Field(None, description="json-render UI Spec")
    error: str | None = Field(None, description="错误信息（接口调用失败时）")


class QueryDomain(str, Enum):
    """Text2SQL 当前支持的查询域枚举。"""

    GENERIC = "generic"
    MEETING_BI = "meeting_bi"


class Text2SQLRequest(BaseModel):
    """统一问数请求模型。"""

    question: str = Field(..., description="自然语言查询问题")
    database: str = Field("default", description="目标数据库")
    domain: QueryDomain | None = Field(None, description="查询域，空则由服务自动判定")
    conversation_id: str | None = Field(None, description="会话ID，用于多轮问数场景")


class Text2SQLResponse(BaseModel):
    """统一问数响应模型。"""

    sql: str = Field(..., description="生成的SQL")
    explanation: str = Field(..., description="SQL解释")
    domain: QueryDomain = Field(QueryDomain.GENERIC, description="实际命中的查询域")
    answer: str | None = Field(None, description="自然语言结论回答")
    results: list[dict[str, Any]] = Field(default_factory=list, description="查询结果")
    chart_spec: dict[str, Any] | None = Field(None, description="可视化图表规格")


class TrainItem(BaseModel):
    """Text2SQL 单条训练样本。"""

    question: str = Field(..., description="自然语言问题")
    sql: str = Field(..., description="对应的SQL语句")


class TrainRequest(BaseModel):
    """Text2SQL 训练请求。"""

    items: list[TrainItem] = Field(..., description="训练数据列表")


class TrainResponse(BaseModel):
    """Text2SQL 训练响应。"""

    status: str = "ok"
    count: int = Field(..., description="训练条目数")


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = "ok"
    version: str = "0.1.0"
    services: dict[str, str] = Field(default_factory=dict)
