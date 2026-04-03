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


class ApiQueryUIAction(BaseModel):
    code: str = Field(..., description="前端动作编码")
    description: str = Field(..., description="前端动作说明")
    enabled: bool = Field(True, description="当前运行时是否已启用")
    params_schema: dict[str, Any] = Field(default_factory=dict, description="动作参数约束")


class ApiQueryDetailRuntime(BaseModel):
    enabled: bool = Field(False, description="是否具备详情运行时信息")
    identifier_field: str | None = Field(None, description="可用于跳转详情的主键字段")
    query_param: str | None = Field(None, description="详情查询时建议使用的参数名")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")


class ApiQueryPaginationRuntime(BaseModel):
    enabled: bool = Field(False, description="是否具备分页运行时信息")
    total: int = Field(0, ge=0, description="总记录数")
    page_size: int | None = Field(None, ge=1, description="当前页大小")
    current_page: int | None = Field(None, ge=1, description="当前页码")
    ui_action: str | None = Field(None, description="推荐的前端动作编码")
    mutation_target: str | None = Field(None, description="前端局部刷新目标路径")


class ApiQueryAuditRuntime(BaseModel):
    enabled: bool = Field(False, description="是否启用写前快照审计")
    snapshot_required: bool = Field(False, description="是否要求生成快照")
    snapshot_id: str | None = Field(None, description="快照 ID，未生成时为空")


class ApiQueryUIRuntime(BaseModel):
    mode: Literal["read_only"] = Field("read_only", description="当前 `api_query` 的运行模式")
    components: list[str] = Field(default_factory=list, description="当前 spec 使用到的组件类型")
    ui_actions: list[ApiQueryUIAction] = Field(default_factory=list, description="当前运行时动作定义")
    detail: ApiQueryDetailRuntime = Field(default_factory=ApiQueryDetailRuntime, description="详情运行时提示")
    pagination: ApiQueryPaginationRuntime = Field(
        default_factory=ApiQueryPaginationRuntime,
        description="分页运行时提示",
    )
    audit: ApiQueryAuditRuntime = Field(default_factory=ApiQueryAuditRuntime, description="审计运行时提示")


class ApiQueryRuntimeMetadataResponse(BaseModel):
    version: str = Field("v1", description="运行时元数据版本")
    business_intent_categories: list[str] = Field(default_factory=lambda: ["read", "write"])
    ui_runtime: ApiQueryUIRuntime = Field(..., description="UI 运行时元数据")
    template_scenarios: list[dict[str, Any]] = Field(default_factory=list, description="模板场景说明")


class ApiQueryResponse(BaseModel):
    trace_id: str = Field(..., description="网关生成或透传的链路追踪 ID")
    api_id: str | None = Field(None, description="命中的接口 ID")
    api_path: str | None = Field(None, description="接口路径")
    params: dict[str, Any] = Field(default_factory=dict, description="提取的参数")
    business_intents: list[ApiQueryBusinessIntent] = Field(default_factory=list, description="识别出的业务意图")
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
