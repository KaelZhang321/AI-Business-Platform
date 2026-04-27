from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class HealthQuadrantSingleExamItem(BaseModel):
    """单项体检条目。"""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str | None = Field(None, alias="itemId", description="单项体检条目ID")
    item_text: str | None = Field(None, alias="itemText", description="单项体检项目名称")
    abnormal_indicator: str | None = Field(None, alias="abnormalIndicator", description="单项体检异常指标")


class HealthQuadrantRequest(BaseModel):
    """四象限分析请求。"""
    sex: str = Field(..., description="性别：男/女")
    age: int | None = Field(None, description="年龄")
    study_id: str = Field(..., min_length=1, description="体检主单号 StudyID")
    quadrant_type: Literal["exam", "treatment"] = Field(..., description="四象限类型：体检或治疗")
    single_exam_items: list[HealthQuadrantSingleExamItem] = Field(
        default_factory=list,
        description="单项体检条目列表（可选，可多条）",
    )
    chief_complaint_text: str | None = Field(None, description="主诉文本（可选）")


class HealthQuadrantBucket(BaseModel):
    """单个象限结果。"""

    q_code: str = Field(..., description="象限编码")
    q_name: str = Field(..., description="象限名称")
    abnormal_indicators: list[str] = Field(default_factory=list, description="该象限命中的异常指标条目")
    recommendation_plans: list[str] = Field(default_factory=list, description="该象限推荐方案")


class HealthQuadrantResponse(BaseModel):
    """体检/治疗双四象限结果。"""

    quadrants: list[HealthQuadrantBucket] = Field(..., min_length=4, max_length=4, description="四象限结果")


class HealthQuadrantConfirmRequest(BaseModel):
    """四象限确认入库请求。"""

    study_id: str = Field(..., min_length=1, description="体检主单号 StudyID")
    quadrant_type: Literal["exam", "treatment"] = Field(..., description="四象限类型：体检或治疗")
    single_exam_items: list[HealthQuadrantSingleExamItem] = Field(
        default_factory=list,
        description="单项体检条目列表（可选，可多条）",
    )
    chief_complaint_text: str | None = Field(None, description="主诉文本列表（可选，可多条）")
    quadrants: list[HealthQuadrantBucket] = Field(..., min_length=4, max_length=4, description="确认后的四象限结果")


class HealthQuadrantConfirmResponse(BaseModel):
    """四象限确认入库响应。"""

    success: bool = Field(True, description="是否保存成功")


class HealthQuadrantQueryEnvelopeResponse(BaseModel):
    """健康四象限查询统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: HealthQuadrantResponse = Field(..., description="健康四象限数据")


class HealthQuadrantConfirmEnvelopeResponse(BaseModel):
    """健康四象限确认统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: HealthQuadrantConfirmResponse = Field(..., description="确认结果")


class SmartMealMealType(str, Enum):
    """智能订餐餐次枚举。"""

    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"


class SmartMealRiskIdentifyRequest(BaseModel):
    """智能订餐风险识别请求。"""

    id_card_no: str = Field(..., min_length=1, description="客户密文身份证号")
    campus_id: str = Field(..., min_length=1, description="预约院区ID")
    sex: str = Field(..., min_length=1, description="性别")
    age: int = Field(..., ge=0, le=130, description="年龄")
    meal_type: list[SmartMealMealType] = Field(..., min_length=1, description="餐次列表")
    reservation_date: str = Field(..., min_length=1, description="订餐日期，格式 YYYY-MM-DD")
    package_code: str = Field(..., min_length=1, description="套餐编码")


class SmartMealRiskItem(BaseModel):
    """智能订餐风险明细。"""

    ingredient: str = Field(..., description="食材名称")
    intolerance_level: str = Field(..., description="不耐受级别")
    source_dish: str = Field(..., description="来源菜品")


class SmartMealRiskIdentifyEnvelopeResponse(BaseModel):
    """智能订餐风险识别响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: list[SmartMealRiskItem] = Field(default_factory=list, description="冲突食材列表")


class SmartMealPackageRecommendRequest(BaseModel):
    """智能订餐套餐推荐请求。

    功能：
        定义套餐推荐入口契约。只强制身份证号与餐次必填，其余画像特征按“缺失即缺失”
        的业务约定传递，不在网关层做兜底补齐，避免把用户显式输入覆盖为历史脏画像。

    Args:
        id_card_no: 客户身份证号（密文），用于外部接口与行为数据关联。
        campus_id: 预约院区 ID，仅允许在该院区菜单范围内推荐套餐。
        meal_type: 餐次列表，限定为 BREAKFAST/LUNCH/DINNER。
        reservation_date: 订餐日期，决定命中的周菜单与星期菜单配置。
        age: 年龄，可选。
        sex: 性别，可选。
        health_tags: 健康标签，可选。
        diet_preferences: 用餐偏好，可选。
        dietary_restrictions: 忌口自然语言列表，可选。
        abnormal_indicators: 异常指标字典，可选。键为异常类别，值为该类别下的异常描述列表。
            示例：
            {
              "血糖异常": ["糖化HbA1c升高", "空腹血糖8.3"],
              "体重": ["超重"],
              "血脂异常": ["甘油三酯升高", "HDL-C升高"]
            }
    """

    id_card_no: str = Field(..., min_length=1, description="客户密文身份证号")
    campus_id: str = Field(..., min_length=1, description="预约院区ID")
    meal_type: list[SmartMealMealType] = Field(..., min_length=1, description="餐次列表")
    reservation_date: str = Field(..., min_length=1, description="订餐日期，格式 YYYY-MM-DD")
    age: int | None = Field(None, ge=0, le=130, description="年龄")
    sex: str | None = Field(None, description="性别")
    health_tags: list[str] = Field(default_factory=list, description="健康标签")
    diet_preferences: list[str] = Field(default_factory=list, description="用餐偏好")
    dietary_restrictions: list[str] = Field(default_factory=list, description="忌口自然语言")
    abnormal_indicators: Dict[str, List[str]] = Field(default_factory=dict, description="异常指标字典")


class SmartMealPackageRecommendItem(BaseModel):
    """智能订餐套餐推荐项。"""

    package_code: str = Field(..., description="套餐编码")
    package_name: str = Field(..., description="套餐名称")
    match_score: float = Field(..., description="匹配度绝对评分，保留两位小数")
    reason: str = Field(..., description="推荐理由")


class SmartMealPackageRecommendEnvelopeResponse(BaseModel):
    """智能订餐套餐推荐响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: list[SmartMealPackageRecommendItem] = Field(default_factory=list, description="推荐结果")


class TranscriptExtractRequest(BaseModel):
    """Transcript 信息提取请求模型。

    功能：
        对外暴露统一的 transcript 抽取入口，只允许调用方提供任务编码与原始转写文本，
        避免前端感知 prompt、模型后端等实现细节。

    入参业务含义：
        - `task_code`：前端选择的业务任务编码，服务层会再映射为内部 `service_code`
        - `transcript`：待分析的原始语音转写文本

    返回值约束：
        Pydantic 接收 snake_case，同时对外文档和序列化口径统一使用 camelCase。

    Edge Cases：
        - 兼容历史 snake_case 入参，减少联调期字段改名带来的阻塞
        - 文本只做最小非空校验，具体裁剪和清洗交由服务层处理
    """

    model_config = ConfigDict(populate_by_name=True)

    task_code: str = Field(..., alias="taskCode", min_length=1, description="抽取任务编码")
    transcript: str = Field(..., min_length=1, description="原始语音转写文本")


class TranscriptExtractData(BaseModel):
    """Transcript 信息提取结果。

    功能：
        统一承载当前请求命中的任务编码、运行时服务编码以及模型返回的结构化结果，
        让前端只消费稳定外壳，不需要感知内部路由细节。

    入参业务含义：
        - `task_code`：前端提交的任务编码
        - `service_code`：服务层最终命中的运行时服务编码
        - `result`：模型输出并经 JSON 解析后的结果对象

    返回值约束：
        `result` 必须是 JSON object；数组或纯文本会在服务层被拦截并报错。

    Edge Cases：
        三个任务可以共享同一外层 schema，同时保留各自 `result` 字段的演进空间。
    """

    model_config = ConfigDict(populate_by_name=True)

    task_code: str = Field(..., alias="taskCode", description="抽取任务编码")
    service_code: str = Field(..., alias="serviceCode", description="运行时服务编码")
    result: dict[str, Any] = Field(default_factory=dict, description="结构化提取结果")


class TranscriptExtractEnvelopeResponse(BaseModel):
    """Transcript 信息提取统一响应壳。"""

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("ok", description="响应消息")
    data: TranscriptExtractData = Field(..., description="Transcript 提取结果")


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


class ApiCatalogIndexJobStatus(str, Enum):
    """API Catalog 重建任务状态。

    功能：
        管理端重建入口已经从“同步执行重活”改成“异步触发后台子进程”，因此必须把任务状态
        提炼成正式枚举，避免前端或运维脚本继续通过字符串猜测当前任务是否还在运行。
    """

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ApiCatalogIndexJobResponse(BaseModel):
    """API Catalog 重建任务响应。

    功能：
        统一承载“任务是否刚创建、是否复用了正在运行的任务、当前执行到哪一步、最后输出了什么”
        这些管理端事实，让 HTTP 层不再暴露子进程实现细节。

    返回值约束：
        - `job_id` 必须稳定存在，便于后续轮询状态
        - `status` 只表达任务生命周期，不表达索引业务语义
        - `stdout_tail/stderr_tail` 只保留尾部片段，避免把完整离线日志塞回 API 响应

    Edge Cases:
        - 同一时刻只允许一个重建任务运行；复用已有任务时 `reused_existing_job=true`
        - 子进程还未结束时 `finished_at`、`exit_code` 允许为空
    """

    job_id: str = Field(..., min_length=1, description="重建任务唯一标识")
    status: ApiCatalogIndexJobStatus = Field(..., description="当前任务状态")
    message: str = Field(..., description="面向管理端的任务说明")
    reused_existing_job: bool = Field(False, description="是否复用了当前正在运行的任务")
    requested_at: datetime = Field(..., description="任务被路由层受理的时间")
    started_at: datetime | None = Field(None, description="子进程真正启动的时间")
    finished_at: datetime | None = Field(None, description="任务结束时间")
    pid: int | None = Field(None, description="后台索引子进程 PID")
    exit_code: int | None = Field(None, description="子进程退出码")
    command: list[str] = Field(default_factory=list, description="实际执行的命令")
    stdout_tail: str = Field("", description="标准输出尾部日志")
    stderr_tail: str = Field("", description="标准错误尾部日志")


class ApiCatalogGovernanceJobStatus(str, Enum):
    """API 数据治理任务状态。

    功能：
        面向“业务系统主动回调触发增量治理”的异步任务状态枚举。和索引重建任务拆分，
        是为了避免后续把“目录重建”和“治理增量收敛”混成同一条运维语义。
    """

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class SemanticCurationPhase(str, Enum):
    """字段治理阶段。

    功能：
        统一表达当前 run 处于冷启动（LLM 主导）还是稳态（规则主导）的治理阶段，便于后续
        门槛判定、审计报表和回放工具共享同一口径。
    """

    PLAN_C = "C"
    PLAN_B = "B"


class SemanticCurationMode(str, Enum):
    """字段治理执行模式。"""

    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"
    DRY_RUN = "DRY_RUN"


class SemanticCurationRunStatus(str, Enum):
    """字段治理 run 生命周期状态。

    功能：
        这组状态用于表达“本批数据是否仅完成提取、是否已进入待审、是否已完成发布/回滚”，
        防止调用方把“任务触发成功”误判成“规则已上线”。
    """

    INIT = "INIT"
    EXTRACTED = "EXTRACTED"
    PROPOSED = "PROPOSED"
    REVIEW_PENDING = "REVIEW_PENDING"
    PROMOTED = "PROMOTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ApiCatalogIncrementalGovernanceRequest(BaseModel):
    """增量治理触发请求。

    功能：
        业务系统接口元数据发生变更后，通过该请求体显式告知网关“哪几条 API 需要重新治理”。
        这比全量重建更可控，也更符合稳态阶段的增量探测策略。

    返回值约束：
        - `api_ids` 至少包含 1 个接口 ID
        - 同一批次允许重复传入，服务层会在任务内做去重
    """

    api_ids: list[str] = Field(default_factory=list, description="本次需要增量治理的接口 ID 列表")
    detect_mode: Literal["explicit", "updated_at"] = Field(
        "explicit",
        description="增量探测模式：explicit=显式传 ID，updated_at=按接口更新时间自动探测",
    )
    updated_since: datetime | None = Field(
        None,
        description="updated_at 探测窗口起点；为空时默认从最近已发布 run 开始",
    )
    max_scan: int = Field(500, ge=1, le=5000, description="updated_at 模式最大扫描 API 数")
    reason: str | None = Field(None, description="触发原因，便于审计与复盘")


class ApiCatalogColdStartGovernanceRequest(BaseModel):
    """冷启动治理触发请求（Plan C）。

    功能：
        用于全量或范围化初始化语义字典提案，主要给首次上线或大规模重构后的重建场景使用。
    """

    api_ids: list[str] = Field(default_factory=list, description="可选，指定只对这些 API 执行冷启动治理")
    domains: list[str] = Field(default_factory=list, description="可选，限定治理的业务域")
    dry_run: bool = Field(False, description="是否仅生成提案不执行后续发布动作")
    reason: str | None = Field(None, description="触发原因")


class ApiCatalogGovernanceJobResponse(BaseModel):
    """增量治理任务响应。

    功能：
        给业务系统和运维平台返回统一任务句柄与处理摘要，避免调用方误把“触发成功”
        当成“治理已完成”。
    """

    job_id: str = Field(..., min_length=1, description="治理任务唯一标识")
    run_id: str | None = Field(None, description="本次任务关联的字段治理 run_id")
    status: ApiCatalogGovernanceJobStatus = Field(..., description="当前任务状态")
    message: str = Field(..., description="任务状态说明")
    reused_existing_job: bool = Field(False, description="是否复用了当前运行中的任务")
    requested_at: datetime = Field(..., description="任务受理时间")
    started_at: datetime | None = Field(None, description="任务开始执行时间")
    finished_at: datetime | None = Field(None, description="任务结束时间")
    reason: str | None = Field(None, description="触发原因")
    requested_by: str | None = Field(None, description="触发人或触发系统标识")
    total_apis: int = Field(0, ge=0, description="本次任务输入 API 数")
    indexed: int = Field(0, ge=0, description="治理成功并完成索引/图同步的 API 数")
    skipped: int = Field(0, ge=0, description="跳过处理的 API 数（如不存在）")
    failed_api_ids: list[str] = Field(default_factory=list, description="治理失败的 API ID 列表")
    error_summary: str = Field("", description="失败摘要")


class ApiCatalogGovernanceRunResponse(BaseModel):
    """字段治理 run 快照。

    功能：
        面向控制面返回单次治理 run 的生命周期事实，供运维平台判断“是否可发布”“是否可回滚”。
    """

    run_id: str = Field(..., min_length=1, description="治理 run 唯一标识")
    phase: SemanticCurationPhase = Field(..., description="治理阶段：C 冷启动 / B 稳态")
    mode: SemanticCurationMode = Field(..., description="执行模式：FULL / INCREMENTAL / DRY_RUN")
    status: SemanticCurationRunStatus = Field(..., description="run 生命周期状态")
    previous_run_id: str | None = Field(None, description="上一个已发布 run_id，用于回滚锚点")
    triggered_by: str | None = Field(None, description="触发人或触发系统")
    trigger_reason: str | None = Field(None, description="触发原因")
    high_coverage_rate: float | None = Field(None, ge=0.0, le=1.0, description="高置信覆盖率")
    low_pending_rate: float | None = Field(None, ge=0.0, le=1.0, description="低置信待审率")
    manual_reject_rate: float | None = Field(None, ge=0.0, le=1.0, description="人工驳回率")
    indexed: int = Field(0, ge=0, description="本次成功处理的 API 数")
    skipped: int = Field(0, ge=0, description="本次跳过 API 数")
    failed_count: int = Field(0, ge=0, description="本次失败 API 数")
    started_at: datetime = Field(..., description="run 开始时间")
    finished_at: datetime | None = Field(None, description="run 结束时间")
    error_message: str | None = Field(None, description="失败摘要")


class ApiCatalogGovernancePromoteRequest(BaseModel):
    """发布请求。

    功能：
        控制面确认某个 run 可以切为在线版本时使用。发布动作会触发三表 current_flag 原子切流。
    """

    reviewer: str | None = Field(None, description="审核人")
    note: str | None = Field(None, description="审核备注")


class ApiCatalogGovernanceRollbackRequest(BaseModel):
    """回滚请求。

    功能：
        当新版本规则导致图谱或渲染异常时，控制面通过指定历史 `run_id` 一键回滚在线版本。
    """

    target_run_id: str = Field(..., min_length=1, description="需要恢复为在线版本的目标 run_id")
    reason: str | None = Field(None, description="回滚原因")


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
