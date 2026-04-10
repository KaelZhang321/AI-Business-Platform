from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from app.models.schemas import (
    ApiQueryPatchContext,
    ApiQueryExecutionPlan,
    ApiQueryExecutionStatus,
    ApiQueryRequest,
    ApiQueryResponse,
    ApiQueryResponseMode,
    ApiQueryRoutingResult,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.dag_executor import DagStepExecutionRecord
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters


class ApiQueryRouteHintSummary(BaseModel):
    """第二阶段路由摘要。

    功能：
        外层图后续只需要知道“路由选中了谁、命中了哪些域、为什么降级”，不需要把
        整个 `ApiQueryRoutingResult` 原样塞进 state。
    """

    selected_api_id: str | None = Field(None, description="候选内最终命中的接口 ID")
    query_domains: list[str] = Field(default_factory=list, description="路由命中的业务域")
    business_intent_codes: list[str] = Field(default_factory=list, description="路由识别出的业务意图编码")
    route_status: str = Field("ok", description="路由阶段整体状态")
    route_error_code: str | None = Field(None, description="路由失败时的结构化错误码")
    reasoning: str | None = Field(None, description="路由阶段的解释说明")


class ApiQueryState(TypedDict, total=False):
    """`/api-query` 外层 Control State。

    功能：
        这里只允许放图推进真正需要的轻量事实，后续 LangGraph 外层工作流会基于这份
        控制状态做节点流转，而不是依赖 route 内部的大量局部变量。
    """

    request_mode: str
    query_text: str
    trace_id: str
    interaction_id: str | None
    conversation_id: str | None
    route_hint_summary: ApiQueryRouteHintSummary | None
    candidate_ids: list[str]
    query_domains_hint: list[str]
    business_intent_codes: list[str]
    plan: ApiQueryExecutionPlan | None
    execution_status: ApiQueryExecutionStatus | None
    response_mode: ApiQueryResponseMode
    patch_context: ApiQueryPatchContext | None
    error_code: str | None
    degrade_reason: str | None
    degrade_stage: str | None
    ui_spec: dict[str, Any] | None
    ui_runtime: ApiQueryUIRuntime | None
    response: ApiQueryResponse | None


class ApiQueryExecutionState(TypedDict, total=False):
    """`/api-query` 内层执行状态边界。

    功能：
        这份状态描述的是“执行子图需要追踪什么”，与外层 Control State 分层，避免把
        执行噪声直接扩散到整个请求工作流。
    """

    plan: ApiQueryExecutionPlan
    trace_id: str
    records_by_step_id: dict[str, DagStepExecutionRecord]
    execution_order: list[str]
    errors: list[str]
    aggregate_status: ApiQueryExecutionStatus | None


@dataclass(slots=True)
class ApiQueryDegradeContext:
    """统一降级出口的运行时事实。

    功能：
        外层 workflow 要把第二、三阶段失败统一汇总到 `build_response`。这些失败场景除了
        `error_code` 之外，还需要标题、提示文案和域/意图上下文，因此单独抽成请求期
        运行时对象，避免把一批只服务最终收口的字段继续塞进 control state。
    """

    stage: str
    title: str
    message: str
    error_code: str
    query_domains: list[str] = field(default_factory=list)
    business_intent_codes: list[str] = field(default_factory=list)
    reasoning: str | None = None


@dataclass(slots=True)
class ApiQueryMutationFormContext:
    """mutation 表单快路运行时事实。

    功能：
        当第三阶段识别出单候选 mutation 接口时，workflow 不执行变更，而是把
        目录实体与 LLM 提取的预填参数打包在这里，供 response builder 构造
        预填表单 UI。

    入参业务含义：
        - `entry`：mutation 接口目录实体
        - `pre_fill_params`：LLM 从用户 NL 中提取的预填参数
        - `business_intent_code`：写意图编码（如 saveToServer）
    """

    entry: ApiCatalogEntry
    pre_fill_params: dict[str, Any] = field(default_factory=dict)
    business_intent_code: str = "saveToServer"


@dataclass(slots=True)
class ApiQueryRuntimeContext:
    """`/api-query` 运行时上下文。

    功能：
        这里承接不适合进入 graph state 的重量级或敏感对象，例如 `user_token`、原始
        候选对象和步骤白名单映射。这样后续状态图快照里不会混入敏感信息。

    入参业务含义：
        - `user_context`：第二阶段参数提取使用的用户上下文
        - `user_token`：透传给业务系统的授权头
        - `retrieval_filters`：自然语言链路下的检索过滤条件，供响应快照复盘
        - `candidates`：原始候选对象，仅请求期内使用
        - `step_entries`：`step_id -> ApiCatalogEntry` 的执行白名单
        - `route_hint`：第二阶段原始路由结果，仅供后续规划节点消费
        - `request_body`：原始请求对象，只在节点内部拆字段，不进入 graph state
        - `degrade_context`：待统一收口的降级事实
        - `execution_state`：执行节点生成的内层状态快照
        - `mutation_form_context`：mutation 表单快路的预填数据，不经过执行图
        - `log_prefix`：当前请求统一日志前缀
    """

    user_context: dict[str, Any] = field(default_factory=dict)
    user_token: str | None = None
    retrieval_filters: ApiCatalogSearchFilters | None = None
    candidates: list[Any] = field(default_factory=list)
    step_entries: dict[str, ApiCatalogEntry] = field(default_factory=dict)
    route_hint: ApiQueryRoutingResult | None = None
    request_body: ApiQueryRequest | None = None
    degrade_context: ApiQueryDegradeContext | None = None
    execution_state: ApiQueryExecutionState | None = None
    mutation_form_context: ApiQueryMutationFormContext | None = None
    log_prefix: str = ""


def summarize_route_hint(route_hint: ApiQueryRoutingResult) -> ApiQueryRouteHintSummary:
    """把第二阶段原始结果压缩成可安全进入控制状态的摘要。"""

    return ApiQueryRouteHintSummary(
        selected_api_id=route_hint.selected_api_id,
        query_domains=list(route_hint.query_domains),
        business_intent_codes=list(route_hint.business_intents),
        route_status=route_hint.route_status,
        route_error_code=route_hint.route_error_code,
        reasoning=route_hint.reasoning,
    )


def build_execution_state(
    *,
    plan: ApiQueryExecutionPlan,
    trace_id: str,
    records_by_step_id: dict[str, DagStepExecutionRecord],
    execution_order: list[str],
) -> ApiQueryExecutionState:
    """构造当前阶段的执行状态快照。"""

    return {
        "plan": plan,
        "trace_id": trace_id,
        "records_by_step_id": records_by_step_id,
        "execution_order": list(execution_order),
        "errors": [
            record.execution_result.error
            for step_id in execution_order
            if (record := records_by_step_id[step_id]).execution_result.error
        ],
        "aggregate_status": None,
    }
